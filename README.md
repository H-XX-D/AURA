# AURA

AURA is an experimental protocol-aware compression and data-movement toolkit for
AI systems. Its strongest current path is **AIWire**: a negotiated structure side
channel that lets peers move semantic deltas, control state, and blob metadata
over ordinary TCP, HTTP, WebSocket, broker, or LAN links instead of repeatedly
moving whole JSON-shaped frames.

AIWire is not just "compress each JSON frame." Peers handshake the structure
first: protocol identity, static dictionary, session templates, and optional
session-local structure updates. After that, agents send compact changes
against the handshaked structure instead of repeatedly moving whole JSON-shaped
frames.

AURA treats AI traffic as three logical lanes:

- **Semantic/message lane**: MCP, A2A, OpenAI-style, JSON-RPC, local-agent,
  trace, task, tool-call, and result messages. This is where AIWire and AIToken
  reduce repeated structure and move changed values.
- **Control/session lane**: handshakes, template discovery, dictionary diffs,
  ACK/NACK, resume, routing state, heartbeats, safety status, and session reset
  signals. Routine control can use handshake-pinned LUT entries as compact
  two-byte codes plus optional canonical JSON payloads; mission-critical control
  stays in explicit system messages. This lane must stay inspectable without
  decompressing the semantic stream.
- **Blob descriptor lane**: metadata for opaque bytes such as media, tensor
  chunks, model artifacts, logs, archives, and files. The bytes can stay in a
  normal blob/file/media transport while AIWire carries content type, hashes,
  chunk manifests, route, priority, and transfer status.

The project also includes broader template, semantic, metadata, and large-file
compression experiments. Treat those as research components. If you are trying
to move lots of small MCP/A2A/OpenAI-style messages between agents, services,
edge devices, and local machines, start with AIWire.

## What This Is Good For

AURA is useful when both sides of a link are under your control, the traffic has
repeated structure, and most messages are changes to already-known shapes:

- Agent-to-agent request/response loops
- Tool-call and tool-result streams
- MCP or JSON-RPC shaped messages
- A2A task, artifact, status, and handoff messages
- OpenAI-style function call and Structured Outputs traffic
- Local AI clusters where a Mac, workstation, and edge devices exchange many
  small messages
- Bandwidth-limited edge links that need to leave headroom for telemetry,
  media, control, and retry traffic
- Structured logs, traces, and operational events with repeated fields
- Opaque binary payload routing where agents need metadata, status, and content
  hashes without pulling the whole payload through the structured-message codec

AURA is not a drop-in replacement for gzip, zstd, brotli, TLS, or a message
broker. It is a protocol-aware structural and metadata side channel for
controlled environments.

The main metric is not compression ratio by itself. The question is how many
verified semantic exchanges fit through the link once bandwidth, p95 latency,
codec CPU, and enough in-flight agent work are all accounted for.

The safety point is that saved bytes become verification budget. When repeated
structure stops filling the link, agents can spend the headroom on ACK/NACK,
hash checks, route status, replay, challenge frames, and independent
double-checks. Mission-critical control does not depend on compact LUT decoding;
it remains explicit system control.

## Why AI-to-AI Traffic Fits

Modern agent protocols repeatedly send the same control fields: `jsonrpc`, `id`,
`method`, `params`, `result`, `error`, `message`, `parts`, `tool`, `arguments`,
`trace_id`, `task_id`, `status`, `metadata`, and schema fragments.

Stateless compression handles each frame independently and throws away useful
history. AIWire separates the stable structure from the changing values: the
side channel negotiates shared structure, then the data stream moves deltas,
tokens, and session-history-backed bytes. Whole frames remain useful at protocol
boundaries and as fallback, but they are not the target steady state.

Relevant public protocol context:

- [Model Context Protocol](https://modelcontextprotocol.io/specification/2025-03-26/basic)
- [A2A specification](https://github.com/a2aproject/A2A/blob/main/docs/specification.md)
- [JSON-RPC 2.0](https://www.jsonrpc.org/specification)
- [OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling)
- [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [Agent Communication Protocol](https://agentcommunicationprotocol.dev/introduction/welcome)

## Current Status

| Area | Status |
|---|---|
| AIWire structural side channel | Working Python path plus native C++ backend |
| AIWire lane model | Semantic lane implemented; control/session structures implemented for handshake, template, dictionary, and resume flow; blob descriptor lane specified |
| AIToken and AIToken+AIWire | Working structural-token path and combined small-frame path |
| Session templates | Discovery, forced handshake, SHA verification, bounded session dictionaries |
| Structured message helpers | Working canonical JSON encode/decode helpers |
| AI-to-AI benchmark harness | Working LAN, realistic-profile, and concurrent-agent tooling |
| General AURA compressor | Alpha research path |
| Large-file CLI | Experimental but usable for local tests |
| Production readiness | Not production-ready; use for prototyping and measurement |

The package targets CPython 3.10+.

## Benchmark Snapshot

On 2026-07-04, AURA was measured against protocol-shaped AI request/response
traffic on modeled 10 Mbps links. The most useful result is the native C++
AIWire/AIToken run:

| Codec | Backend | Completed 5s | Ex/s | Framed B/ex | BW cap ex/s | BW gain | Saved | p95 ms |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| raw | raw | 8,773 | 1,754.6 | 1,177.2 | 1,755.6 | 1.00x | -0.7% | 10.3 |
| zlib | zlib | 12,701 | 2,540.2 | 695.6 | 2,991.9 | 1.70x | 40.5% | 7.5 |
| aitoken | native | 12,643 | 2,528.6 | 350.3 | 5,303.4 | 3.02x | 70.0% | 7.5 |
| aiwire | native | 12,806 | 2,561.2 | 156.9 | 11,017.2 | 6.28x | 86.6% | 7.5 |
| aitoken_aiwire | native | 12,702 | 2,540.4 | 125.2 | 12,947.7 | 7.38x | 89.3% | 7.5 |

Read the metrics report:
[AI-to-AI Messaging Metrics](docs/perf/ai_to_ai_messaging_metrics_2026-07-04.md)

Live public-fixture TCP replay was also measured on 2026-07-04 with the
committed corpus, modeled 10 Mbps links in both directions, 64 concurrent
logical agents, one in-flight request per agent, updated session templates, and
fixture response SHA verification:

| Codec | Backend | Completed 2s | Ex/s | Framed B/ex | BW cap ex/s | BW gain | Saved | p95 ms |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| raw | raw | 4,509 | 2,254.5 | 1,105.3 | 2,254.5 | 1.00x | -0.7% | 28.89 |
| zlib | zlib | 7,731 | 3,865.5 | 643.2 | 3,864.9 | 1.71x | 41.4% | 16.77 |
| aiwire | native | 27,092 | 13,546.0 | 45.6 | 54,205.8 | 24.04x | 95.8% | 5.55 |
| aitoken_aiwire | aitoken+native | 23,696 | 11,848.0 | 32.3 | 77,285.6 | 34.28x | 97.1% | 6.34 |

In that run, raw and zlib filled the modeled 10 Mbps link. AIWire created much
more bandwidth headroom than 64 single-window agents could fully occupy, so the
next limiter was runtime/concurrency rather than bytes on the wire.

A separate Mac-to-Z6-and-Jetson-Nano LAN run showed the same direction of travel:
Python AIWire moved 55,337 verified exchanges in 5 seconds on the Z6 target
(`6.30x` raw) and averaged 20,887 verified exchanges in 5 seconds across four
Nano-class targets (`2.39x` raw).

Read the LAN report:
[AI-to-AI LAN Benchmark](docs/perf/ai_to_ai_lan_benchmark_2026-07-04.md)

The key interpretation is bandwidth proportionality. Smaller frames create room
for more messages, but the runtime must keep enough exchanges in flight to fill
that room. Raw JSON fills the modeled link quickly; AIWire and AIToken+AIWire
need more concurrent logical agents or larger per-agent windows before bandwidth
becomes the bottleneck again.

The generic `ProductionHybridCompressor` path is not the right fit for this
small-message workload yet. AIWire is the intended AURA path for high-volume
structured AI message streams.

## Fixture Corpus

The repo includes a deterministic public AIWire session corpus:
[public_session_corpus_v1.json](fixtures/aiwire_sessions/public_session_corpus_v1.json).
It contains synthetic MCP, A2A, OpenAI Responses, local agent, trace, handoff,
review, and memory-write messages plus the side-channel transcript around them:
forced handshake, session-template update, authenticated dictionary diff, ACK,
and resume negotiation.

Regenerate it with:

```bash
PYTHONPATH=src python tools/build_aiwire_session_fixture_corpus.py
```

Details:
[AIWire session fixtures](docs/aiwire_session_fixtures.md)

## Install

Python / PyPI:

```bash
pip install aura-compression
```

Python / local development:

```bash
git clone https://github.com/H-XX-D/AURA.git
cd AURA
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

JavaScript / npm:

```bash
npm i aura-compression
```

The npm package exposes dependency-free Node helpers for canonical AIWire
messages, the three-lane constants, blob descriptors, and a small zlib-backed
frame wrapper. The benchmarked AIWire engine remains the Python/native C++ path
in this repo.

Registry roles:

- **PyPI `aura-compression`** is the primary Python package for AIWire,
  AIToken, session-template negotiation, benchmark tooling, and the optional
  native backend.
- **npm `aura-compression`** is a lightweight JavaScript helper package for
  canonical AIWire messages, lane constants, blob descriptors, and small local
  frame round trips.

## Quick Start: AIWire

```python
from aura_compression import (
    AIWireSessionDecoder,
    AIWireSessionEncoder,
)

message = {
    "protocol": "mcp",
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
        "name": "read_file",
        "arguments": {
            "uri": "repo://service/path.py",
            "line_start": 10,
            "line_end": 30,
        },
    },
}

with AIWireSessionEncoder(level=3) as encoder, AIWireSessionDecoder() as decoder:
    session_delta = encoder.compress_message(message)
    restored = decoder.decompress_message(session_delta)

assert restored == message
print(encoder.stats.ratio)
```

For batch-style tests:

```python
from aura_compression import (
    build_delta_structured_ai_messages,
    build_structured_ai_messages,
    compress_ai_wire_frames,
    decompress_ai_wire_frames,
    summarize_ai_wire_corpus,
)

messages = build_structured_ai_messages(1024)
delta_messages = build_delta_structured_ai_messages(1024)
compressed, encode_stats = compress_ai_wire_frames(messages)
delta_compressed, delta_stats = compress_ai_wire_frames(delta_messages)
restored, decode_stats = decompress_ai_wire_frames(compressed)

assert len(restored) == len(messages)
print(encode_stats.as_dict())
print(delta_stats.as_dict())
print(summarize_ai_wire_corpus(delta_messages))
```

Node.js helper API:

```js
const {
  AIWireSessionEncoder,
  AIWireSessionDecoder,
  createBlobDescriptor,
} = require("aura-compression");

const encoder = new AIWireSessionEncoder({ threshold: 0 });
const decoder = new AIWireSessionDecoder();

const frame = encoder.compressMessage({
  protocol: "mcp",
  jsonrpc: "2.0",
  id: 1,
  method: "tools/call",
  params: { name: "read_file", arguments: { uri: "repo://service/path.py" } },
});

console.log(decoder.decompressMessage(frame));

const descriptor = createBlobDescriptor({
  blobId: "blob-1",
  contentType: "application/octet-stream",
  bytes: Buffer.from("opaque payload"),
  status: "available",
});

console.log(descriptor.digest);
```

## Benchmarking AIWire

For a fast local benchmark with stable corpus metrics:

```bash
PYTHONPATH=src python -m aura_compression.cli.benchmark \
  --profile small \
  --corpus delta

PYTHONPATH=src python -m aura_compression.cli.benchmark \
  --profile bursty \
  --corpus structured
```

Profiles are `small`, `medium`, and `bursty`; `--messages` can override the
profile count for focused smoke tests. Corpora are `structured` and `delta`.

The LAN benchmark harness can run a server on one machine and a client on
another:

```bash
# Target machine
PYTHONPATH=src python tools/stress_ai_wire_roundtrip_z6.py server \
  --host 0.0.0.0 \
  --port 8765 \
  --runs 5 \
  --link-mbps 10

# Client machine
PYTHONPATH=src python tools/stress_ai_wire_roundtrip_z6.py client \
  --host <target-host> \
  --port 8765 \
  --seconds 5 \
  --exchanges 20000 \
  --agent-count 16 \
  --pipeline-window 1 \
  --link-mbps 10 \
  --codecs raw,zlib,aitoken,aiwire,aitoken_aiwire
```

Codec meanings:

- `raw`: canonical structured JSON frames
- `zlib`: stateless zlib per frame
- `aitoken`: structural binary token representation
- `aura`: generic `ProductionHybridCompressor` per frame
- `aiwire`: stateful AURA AIWire structure side channel and delta stream
- `aitoken_aiwire`: AIToken structural frames carried through AIWire

Run a realistic multi-profile suite and extrapolate bandwidth-proportional
capacity:

```bash
PYTHONPATH=src python tools/run_aiwire_network_suite.py \
  --profiles lan_10m,wifi_busy,lte_good,edge_mesh \
  --seconds 5 \
  --agent-count 8 \
  --codecs raw,zlib,aiwire,aitoken_aiwire \
  --output /tmp/aura_aiwire_network_suite.json

python tools/extrapolate_aiwire_bandwidth.py \
  /tmp/aura_aiwire_network_suite.json \
  --bandwidth-mbps 1,5,10,50,100,1000 \
  --agent-counts 1,2,4,8,16,32 \
  --per-agent-window 1 \
  --output /tmp/aura_aiwire_bandwidth_extrapolation.md
```

The extrapolator reports both bandwidth capacity and latency-capped effective
capacity. It also projects how many concurrent logical agents are needed to
fill the link from the measured p95 latency and per-agent in-flight window.
High-RTT profiles need enough aggregate in-flight exchanges to fill the link.
In the stress tool, `--pipeline-window` is per logical agent, so aggregate
in-flight work is `agent_count * pipeline_window`.

For a fast, reproducible fixture-backed saturation model:

```bash
PYTHONPATH=src python tools/benchmark_aiwire_fixture_saturation.py \
  --fixture-corpus fixtures/aiwire_sessions/public_session_corpus_v1.json \
  --profiles lan_10m,wifi_busy,lte_good,edge_mesh \
  --codecs raw,zlib,aitoken,aiwire,aitoken_aiwire \
  --agent-counts 1,8,64 \
  --markdown-output /tmp/aura_aiwire_fixture_saturation.md \
  --format markdown
```

This uses the committed public session fixture and reports bytes per exchange,
bandwidth capacity, p95 latency-window capacity, required concurrent agents,
message throughput, and raw-bandwidth equivalent.

To replay the same public corpus over the live TCP harness:

```bash
# Target machine
PYTHONPATH=src python tools/stress_ai_wire_roundtrip_z6.py server \
  --host 0.0.0.0 \
  --port 8765 \
  --runs 4 \
  --fixture-corpus fixtures/aiwire_sessions/public_session_corpus_v1.json \
  --fixture-session-templates updated \
  --link-mbps 10

# Client machine
PYTHONPATH=src python tools/stress_ai_wire_roundtrip_z6.py client \
  --host <target-host> \
  --port 8765 \
  --seconds 2 \
  --exchanges 36 \
  --agent-count 64 \
  --pipeline-window 1 \
  --link-mbps 10 \
  --codecs raw,zlib,aiwire,aitoken_aiwire \
  --fixture-corpus fixtures/aiwire_sessions/public_session_corpus_v1.json \
  --fixture-session-templates updated \
  --force-session-templates \
  --output /tmp/aura_live_fixture_replay.json
```

In fixture mode, the client and server compare request/response corpus digests
during the handshake and the client verifies each replayed fixture response by
SHA-256.

## Transport Examples

AIWire frames are ordinary bytes after the session handshake. The repo includes
small examples for common transport boundaries. Each example now carries both
semantic frames and compact routine-control LUT frames so route/status control
stays inspectable without decompressing the semantic stream:

- [Length-prefixed TCP](examples/aiwire_tcp_transport.py)
- [WebSocket binary messages](examples/aiwire_websocket_transport.py)
- [HTTP POST with Server-Sent Events](examples/aiwire_http_streaming_transport.py)
- [Local broker/topic queue](examples/aiwire_local_broker.py)

Run them from the repo root with `PYTHONPATH=src`. The WebSocket example uses
the optional `websocket` extra. TCP uses an explicit length prefix; WebSocket,
SSE, and broker examples rely on their native message/event boundaries. All
examples keep mission-critical control out of the compact LUT path.

## General Compression API

The older hybrid compressor remains useful for research into templates,
metadata, large files, and strategy selection:

```python
from aura_compression import ProductionHybridCompressor

compressor = ProductionHybridCompressor(
    enable_aura=False,
    enable_fast_path=True,
    enable_audit_logging=False,
    template_sync_interval_seconds=None,
)

payload, method, metadata = compressor.compress("Order 42: status=ready")
restored = compressor.decompress(payload)

assert restored == "Order 42: status=ready"
print(method.name, metadata["ratio"])
```

Use this path for experiments. Use AIWire for AI-to-AI structure handshakes and
delta streams.

## Docs

- [Architecture](docs/architecture.md)
- [Roadmap](docs/ROADMAP.md)
- [Current project context](docs/AURA_SYSTEM_CONTEXT.md)
- [AIWire v1 protocol spec](docs/aiwire_v1_spec.md)
- [AIWire session dictionary safety](docs/aiwire_session_dictionary.md)
- [AIWire session fixtures](docs/aiwire_session_fixtures.md)
- [Realistic network benchmarks](docs/perf/realistic_network_benchmarks.md)
- [AI-to-AI messaging metrics](docs/perf/ai_to_ai_messaging_metrics_2026-07-04.md)
- [AI-to-AI LAN benchmark](docs/perf/ai_to_ai_lan_benchmark_2026-07-04.md)
- [AIWire fixture saturation benchmark](docs/perf/aiwire_fixture_saturation_2026-07-04.md)
- [Transport examples](examples/README.md)
- [Large-file and API notes](docs/api/compressor.md)

## Tests

```bash
PYTHONPATH=src pytest tests/test_ai_wire.py tests/test_ai_wire_token.py \
  tests/test_aiwire_benchmark_smoke.py tests/test_aiwire_session_fixtures.py \
  tests/test_aiwire_bandwidth_extrapolation.py \
  tests/test_aiwire_fixture_saturation.py tests/test_aiwire_stress_fixture_replay.py \
  tests/test_aiwire_network_profiles.py -q
pytest -q
```

Formatting checks used in this repo:

```bash
uvx black --check src/aura_compression tests tools
uvx isort --check-only src/aura_compression tests tools
```

## Roadmap Summary

The near-term roadmap is to harden AIWire first:

- Stabilize the AIWire v1 frame and handshake contract
- Keep the AIWire v1 side-channel and delta-frame spec aligned with tests
- Define the session-template update signal and delta/resync behavior
- Keep benchmark reports reproducible and public-safe
- Keep improving realistic MCP, A2A, OpenAI, local agent, and delta-shaped
  message corpora
- Keep public session fixture corpora deterministic and side-channel complete
- Improve ARM64/native backend performance for edge targets
- Expand transport examples beyond the current TCP, WebSocket, HTTP streaming,
  and local broker samples
- Define dictionary versioning and fallback behavior

Full details are in [docs/ROADMAP.md](docs/ROADMAP.md).

## Contributing

Focused benchmarks, protocol-shaped corpora, transport examples, and tests are
the most useful contributions right now. Keep changes narrow and include the
message shape or benchmark output that motivated the change.

## License

Licensed under Apache 2.0. See [LICENSE](LICENSE).

## Contact

- Author: Todd Hendricks
- Issues: https://github.com/H-XX-D/AURA/issues
