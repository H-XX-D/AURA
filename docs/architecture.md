# AURA Architecture

AURA is a Python-first compression research codebase with one clear current
product direction: **AIWire for handshaked structure and delta movement in
high-volume AI-to-AI messages**.

The supported application import boundary is `aura_compression.aiwire`.
Research components are grouped under `aura_compression.research`; historical
package-root imports remain compatibility aliases. See
[API Stability](api_stability.md).

The repo still contains broader hybrid compression components. Those are useful
for experiments and large-message research, but the most validated path today is
the AIWire structural side channel.

## Design Goal

AI-to-AI systems move many small structured messages:

- JSON-RPC requests and responses
- Tool calls and tool results
- Task state updates
- Agent handoffs
- Trace, review, and memory messages
- Schema-shaped model inputs and outputs

These messages are verbose, repetitive, and usually exchanged by systems that
control both ends of the link. AURA uses that structure instead of treating each
frame as unrelated text. The intended steady state is not "send a whole frame
more cheaply"; it is "handshake the structure, then send the change."

## High-Level Shape

```text
Application / agent runtime
        |
        v
Structured message semantics
MCP, A2A, OpenAI tool calls, local agent traces
        |
        v
AIWire side channel
handshake static dictionary + session templates + update signals
        |
        v
AIWire lanes
semantic messages + control/session state + blob descriptors
        |
        v
AIWire data path
canonical JSON boundary form -> tokens/deltas -> live session history
blob metadata -> route/type/status/hash side channel
        |
        v
Normal network transport
TCP, HTTP, WebSocket, local LAN, broker frame, file stream
```

The three lanes have different jobs:

- **Semantic/message lane**: structured agent traffic such as MCP, A2A,
  OpenAI-style tool calls, JSON-RPC, traces, handoffs, task state, and results.
- **Control/session lane**: handshake, template discovery, dictionary diffs,
  ACK/NACK, resume, routing status, heartbeat, safety state, and reset signals.
  Routine control can be handshake-pinned to compact LUT entries; mission-critical
  control remains explicit system control.
- **Blob descriptor lane**: metadata for opaque bytes. The referenced bytes can
  move through ordinary file, media, byte-stream, object-store, or shared-memory
  paths while AIWire carries type, route, status, hashes, and chunk manifests.

The rest of the repository supports adjacent research:

```text
General payloads
        |
        v
ProductionHybridCompressor
strategy selection, templates, metadata, BRIO, AURA-Lite, large-file paths
        |
        v
Experimental containers and analysis tools
```

## AIWire

Primary files:

- [`src/aura_compression/ai_wire.py`](../src/aura_compression/ai_wire.py)
- [`src/aura_compression/ai_wire_messages.py`](../src/aura_compression/ai_wire_messages.py)
- [`src/aura_compression/ai_wire_fixtures.py`](../src/aura_compression/ai_wire_fixtures.py)
- [`docs/aiwire_v1_spec.md`](aiwire_v1_spec.md)
- [`docs/aiwire_session_fixtures.md`](aiwire_session_fixtures.md)
- [`fixtures/aiwire_sessions/public_session_corpus_v1.json`](../fixtures/aiwire_sessions/public_session_corpus_v1.json)
- [`tests/test_ai_wire.py`](../tests/test_ai_wire.py)
- [`tests/test_aiwire_session_fixtures.py`](../tests/test_aiwire_session_fixtures.py)
- [`tools/stress_ai_wire_roundtrip_z6.py`](../tools/stress_ai_wire_roundtrip_z6.py)

AIWire provides:

- A stable protocol identity: `aura.aiwire`
- A versioned handshake shape
- Three logical lanes: semantic messages, control/session state, and blob
  descriptors
- A static dictionary tuned for AI protocol fields
- Session-template negotiation and update signals
- Authenticated append-only session dictionary diffs and ACKs
- Deterministic public session fixtures for replay and interop checks
- Compact delta movement against the handshaked structure
- Stateful session compression across frames
- Canonical JSON helpers for structured Python mappings
- Python encode/decode path using zlib
- Optional native backend loading through `libaura_aiwire`
- Stats for bytes in, bytes out, frame count, and ratio

### Why It Works

Generic zlib per frame pays setup cost every message and loses history after
each frame. AIWire keeps the useful history across a session, starts with a
dictionary containing common AI protocol terms, and lets peers agree on
session-specific structure before the hot path sends changes.

This matters for fields such as:

```text
jsonrpc, method, params, result, error, message, parts, metadata,
trace_id, task_id, tool_call_id, arguments, status, artifacts
```

On the local LAN benchmark, AIWire moved more verified request/response
exchanges than raw JSON and stateless zlib under the same modeled bandwidth.
The generated corpus now includes a delta-shaped helper that repeats the same
agent/task/session structures while moving only changed status, token,
argument, artifact, route, and trace values.
See [AI-to-AI LAN Benchmark](perf/ai_to_ai_lan_benchmark_2026-07-04.md).

## Structured Message Helpers

`ai_wire_messages.py` keeps test and benchmark traffic realistic without tying
the core codec to one vendor.

Important functions:

- `encode_ai_wire_message(message)`: converts bytes, strings, or mappings into
  canonical UTF-8 bytes.
- `decode_ai_wire_message(payload)`: decodes JSON payload bytes into Python
  values.
- `build_structured_ai_messages(count, seed)`: generates protocol-shaped test
  messages.
- `build_delta_structured_ai_messages(count, seed)`: generates stable-session
  delta-shaped traffic after structure has been handshaked.
- `build_ai_wire_messages(count, seed)`: generates encoded benchmark frames.
- `summarize_ai_wire_corpus(messages)`: reports corpus byte size, average frame
  size, protocol mix, top-level key counts, nested key counts, and delta value
  mix for benchmark comparison.

The generated corpus currently includes OpenAI-style responses, MCP tool calls,
A2A messages, local agent deltas, traces, handoffs, reviews, memory writes, and
stable-session delta traffic.

The package benchmark CLI exposes `--profile small|medium|bursty` and
`--corpus structured|delta` so local runs can compare quick smoke, default, and
bursty message-size mixes with the same corpus summary schema.

Benchmark corpora opt into a top-level `corpus_metadata` field with
`synthetic=true` and `public_safe=true`. The raw builders leave that field off
by default so committed session fixtures do not drift unless the fixture format
is intentionally revised.

`ai_wire_fixtures.py` builds saved session corpora that wrap those message
shapes in the AIWire side-channel lifecycle: forced handshake, initial session
templates, template update, authenticated append-only dictionary diff, ACK, and
resume negotiation. The public fixture lives at
[`fixtures/aiwire_sessions/public_session_corpus_v1.json`](../fixtures/aiwire_sessions/public_session_corpus_v1.json)
and is documented in
[`docs/aiwire_session_fixtures.md`](aiwire_session_fixtures.md).

## Handshake Model

AIWire peers should agree on:

- Protocol name
- Supported versions
- Static dictionary hash
- Session template hashes and limits
- Routine control LUT hash, count, and epoch
- Mission-critical system-control behavior
- Template update signal behavior
- Delta frame and resync behavior
- Compression level
- Flush mode
- Fallback codecs, when fallback is allowed

The dictionary and template hashes matter because the encoder and decoder must
share the same structural state. A mismatch should fail closed, request resync,
or fall back only when the caller explicitly allows another codec.

The implementation contract is documented in
[AIWire v1 Protocol Spec](aiwire_v1_spec.md).

## General Hybrid Compressor

Primary files:

- [`src/aura_compression/compressor.py`](../src/aura_compression/compressor.py)
- [`src/aura_compression/compressor_refactored.py`](../src/aura_compression/compressor_refactored.py)
- [`src/aura_compression/compression_engine.py`](../src/aura_compression/compression_engine.py)
- [`src/aura_compression/compression_strategy_manager.py`](../src/aura_compression/compression_strategy_manager.py)

This path coordinates broader compression strategies:

- Binary semantic templates
- AURA-Lite
- BRIO / BRIO Full
- Pattern semantic large-file compression
- Metadata sidechannel classification
- Persistent template cache
- Optional CUDA/native helpers

Use this path for experiments with structured text, logs, and larger payloads.
Do not assume it is faster or smaller for small AI messages. The 2026-07-04
benchmark showed the generic path is currently CPU-bound and near-neutral on
small per-frame AI JSON.

## Metadata Sidechannel

Primary files:

- [`src/aura_compression/metadata_sidechannel.py`](../src/aura_compression/metadata_sidechannel.py)
- [`docs/perf/metadata_sidechannel.md`](perf/metadata_sidechannel.md)

The metadata sidechannel is a research feature for routing and inspecting
compressed traffic without full decompression. It is useful for:

- Priority routing
- Security screening
- Message category classification
- Operational monitoring

This is adjacent to AIWire and informs the blob descriptor lane. AIWire's core
side channel is for negotiated message structure and session control; the blob
descriptor lane carries the smaller routing, type, status, hash, and chunk
metadata needed to keep opaque binaries out of the structured-message codec.

## Large-File Path

Primary files:

- [`tools/compress_large_file.py`](../tools/compress_large_file.py)
- [`src/aura_compression/pattern_semantic_large_file.py`](../src/aura_compression/pattern_semantic_large_file.py)

The large-file tooling is for local experiments with chunking, templates, and
container metadata. It is not the main AI-to-AI message path.

## Transport Boundary

AURA does not require a special network. It produces explicit side-channel
handshake/update messages and compact data frames that can be carried by normal
transports:

- Raw TCP frame streams:
  [`examples/aiwire_tcp_transport.py`](../examples/aiwire_tcp_transport.py)
- WebSocket messages:
  [`examples/aiwire_websocket_transport.py`](../examples/aiwire_websocket_transport.py)
- HTTP request/response bodies and Server-Sent Events payloads:
  [`examples/aiwire_http_streaming_transport.py`](../examples/aiwire_http_streaming_transport.py)
- Local broker messages:
  [`examples/aiwire_local_broker.py`](../examples/aiwire_local_broker.py)
- Files or replay logs

Security belongs at the transport/application boundary. For LAN services, bind
only to intended interfaces, authenticate peers, and avoid exposing local debug
ports unintentionally.

## Verification

Focused AIWire checks:

```bash
make test-aiwire
```

Full test suite:

```bash
make test
```

Formatting:

```bash
make format-check
```

## Current Risk Areas

- AIWire v1 needs a frozen handshake, template-update, delta-frame, and resync
  spec before other projects depend on it.
- Native backend support needs reproducible builds and ARM64 performance checks.
- The general hybrid compressor has more experimental surface than production
  hardening.
- Public docs and benchmark reports should avoid host-specific private details.
- Cross-version dictionary compatibility is covered in the fast AIWire gate;
  long-lived deployments still need a broader compatibility matrix as
  dictionaries evolve.
