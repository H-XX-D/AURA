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
| Explicit sidecar proxy | Working TCP ingress/egress sidecar for raw length-prefixed agent frames over an AIWire tunnel |
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

The follow-up Z6-to-Nano relay run on 2026-07-05 moved the client onto the Z6
and reached four Jetson Orin Nano-class targets from there. It used the public
fixture corpus, updated session templates, SHA-verified responses, modeled
10 Mbps links in both directions, 64 logical agents, and one in-flight request
per agent:

| Codec | Completed 5s avg | Ex/s avg | vs raw | Framed B/ex | BW cap ex/s | Saved | p95 ms | Util |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| raw | 11,272.0 | 2,254.4 | 1.00x | 1,105.4 | 2,254.3 | -0.7% | 28.89 | 100.0% |
| zlib | 19,328.3 | 3,865.7 | 1.71x | 643.2 | 3,865.2 | 41.4% | 16.95 | 100.0% |
| aiwire | 36,489.5 | 7,297.9 | 3.24x | 45.5 | 54,308.2 | 95.9% | 12.88 | 13.4% |

Raw and zlib saturated the modeled 10 Mbps link. AIWire averaged `3.24x` raw
and `1.89x` zlib, while using only `13.4%` of the modeled link because the
sustained session deltas were much smaller.

Read the Z6 relay report:
[AIWire Z6-to-Nano Relay Benchmark](docs/perf/z6_to_nano_aiwire_2026-07-05.md)

The n-ary follow-up used the Z6 as one coordinator for four Nano-class peers.
It probed each peer, accepted one fail-closed AIWire n-ary handshake contract
with the same static dictionary and 8 session templates, then ran concurrent
fixture replay across all four targets with a deterministic cluster variation
profile. That profile gives each peer different roles, routes, workloads,
epochs, queue depths, token windows, and telemetry while preserving SHA-verified
request/response checks. A 60-second-per-codec sustained run measured:

| Codec | Completed 60s group | Ex/s group | vs raw | Framed B/ex | BW cap ex/s | Saved | p95 avg | Util |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| raw | 259,065 | 4,317.8 | 1.00x | 2,313.0 | 4,317.0 | -0.3% | 68.75 | 100.0% |
| zlib | 287,744 | 4,795.7 | 1.11x | 1,219.3 | 8,187.8 | 47.1% | 60.77 | 58.6% |
| aiwire | 279,904 | 4,665.1 | 1.08x | 368.1 | 26,734.6 | 84.0% | 62.68 | 17.4% |

This aggregate run shows the next bottleneck clearly: AIWire created about
26,735 modeled exchanges/second of bandwidth capacity across the four 10 Mbps
links, but the Python coordinator and one-request windows only used `17.4%` of
that headroom.

A follow-up AIWire-only 60-second sweep widened the per-agent pipeline window
on the same n-ary cluster workload:

| Pipeline window | Aggregate window/target | Completed 60s group | Ex/s group | vs window 1 | Framed B/ex | p95 avg | Util |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 64 | 279,904 | 4,665.1 | 1.00x | 368.1 | 62.68 | 17.4% |
| 2 | 128 | 269,437 | 4,490.6 | 0.96x | 368.1 | 125.34 | 16.8% |
| 4 | 256 | 276,090 | 4,601.5 | 0.99x | 368.1 | 251.51 | 17.2% |
| 8 | 512 | 237,916 | 3,965.3 | 0.85x | 368.1 | 739.82 | 14.8% |

That sweep narrows the next engineering target. More queue depth on one Python
stream does not fill the saved bandwidth; it mostly increases tail latency.

The next experiment added real session sharding: each target server used
concurrent connection workers, and each target's modeled 10 Mbps budget was
split evenly across its replay sessions.

| Session shards/target | Total sessions | Completed 60s group | Ex/s group | vs window 1 | Framed B/ex | p95 avg | Util |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 4 | 279,904 | 4,665.1 | 1.00x | 368.1 | 62.68 | 17.4% |
| 2 | 8 | 225,284 | 3,754.7 | 0.80x | 370.3 | 156.09 | 14.1% |
| 4 | 16 | 186,690 | 3,111.5 | 0.67x | 370.2 | 391.54 | 11.6% |
| 8 | 32 | 145,821 | 2,430.4 | 0.52x | 370.3 | 1,065.96 | 9.1% |

That result rules out Python thread sharding as the fix. AIWire still saves the
bytes, but the current Python coordinator/server hot path loses throughput and
tail latency as session count rises.

A follow-up replaced the thread worker pool with forked server processes while
keeping the same Z6 coordinator, four Nano-class targets, 60-second windows,
10 Mbps-per-target model, and AIWire-only session shard sweep:

| Server worker mode | Session shards/target | Total sessions | Completed 60s group | Ex/s group | vs window 1 | Framed B/ex | p95 avg | Util |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 1 | 4 | 279,904 | 4,665.1 | 1.00x | 368.1 | 62.68 | 17.4% |
| processes | 2 | 8 | 224,431 | 3,740.5 | 0.80x | 370.3 | 154.95 | 14.0% |
| processes | 4 | 16 | 185,747 | 3,095.8 | 0.66x | 370.2 | 391.69 | 11.6% |
| processes | 8 | 32 | 144,208 | 2,403.5 | 0.52x | 370.3 | 1,068.25 | 9.0% |

That also missed the target. The useful conclusion is narrower: AIWire is
already bandwidth-proportional at the byte level, but Python worker fan-out
around the current harness does not convert that saved bandwidth into more
completed messages. The next measurement path is the opt-in asyncio coordinator
loop in `tools/stress_ai_wire_roundtrip_z6.py`; after that, the remaining
ceiling belongs in a native coordinator/server loop rather than more Python
workers.

Read the n-ary relay report:
[AIWire N-ary Z6-to-Nano Benchmark](docs/perf/aiwire_nary_z6_to_nano_2026-07-05.md)

The key interpretation is bandwidth proportionality. Smaller frames create room
for more messages, but the runtime must keep enough exchanges in flight to fill
that room. Raw JSON fills the modeled link quickly; AIWire and AIToken+AIWire
need true runtime parallelism before bandwidth becomes the bottleneck again.

On 2026-07-06, the local realistic-profile suite was rerun with the native
backend, asyncio coordinator, public fixture replay, 64 logical agents,
profile-specific pipeline windows, and 5 seconds per codec/profile:

| Profile | Raw ex/s | Native AIWire ex/s | AIWire util | AIToken+AIWire ex/s | AIToken+AIWire util | Best p95 |
|---|---:|---:|---:|---:|---:|---:|
| lan_10m | 1,079.8 | 6,735.4 (6.24x) | 99.9% | 9,419.8 (8.72x) | 41.0% | 114.7 ms |
| wifi_busy | 1,280.4 | 7,976.8 (6.23x) | 96.9% | 9,509.2 (7.43x) | 34.5% | 435.4 ms |
| lte_good | 1,042.2 | 6,583.0 (6.32x) | 95.7% | 8,932.8 (8.57x) | 38.8% | 731.9 ms |
| edge_mesh | 616.4 | 3,885.0 (6.30x) | 97.5% | 9,225.0 (14.97x) | 66.9% | 413.2 ms |

Native AIWire now fills the modeled links in this local suite; AIToken+AIWire
saves more bytes and completes more messages, but at roughly 108 framed bytes
per exchange it still leaves bandwidth headroom, so runtime/concurrency is the
next limit.

Full reports:
[AIWire Native Asyncio Network Suite](docs/perf/aiwire_native_asyncio_network_suite_2026-07-06.md)
and
[AIWire Native Asyncio Bandwidth Extrapolation](docs/perf/aiwire_native_asyncio_bandwidth_extrapolation_2026-07-06.md).

The explicit sidecar proxy was then run over a real LAN hop to one Jetson Orin
Nano-class edge target. The native backend was built on the edge target, the
SSH-managed preflight passed, and a 60-second sidecar run verified 1,358
request/response exchanges. Raw framed traffic averaged 2,345.4 bytes per
exchange; AIWire semantic traffic averaged 367.0 bytes per exchange, saving
84.4% of semantic bytes with a 46.29 ms p95 round trip. The result confirms the
sidecar path preserves the sustained-handshake byte savings over a real edge
hop; completed exchange rate is still limited by the current single-connection
request/response loop rather than modeled 10 Mbps link capacity.

Read the proxy edge report:
[AIWire Explicit Proxy Nano Edge Run](docs/perf/aiwire_proxy_nano_engineer_2026-07-06.md).

The same sidecar path was then extended to two reachable Jetson Orin Nano-class
edge targets. Both targets used the native backend, both passed SSH-managed
preflight, and the runner used per-target `remote_root` settings for mixed edge
checkout paths. A 60-second parallel run verified 2,709 exchanges as a group:
45.1 exchanges/second, 2,322.4 raw framed bytes per exchange, 364.2 AIWire
semantic bytes per exchange, and 84.3% semantic-byte savings with a 47.98 ms max
p95 round trip. The result scaled the current single-connection sidecar path
almost linearly from one to two edge targets, while preserving the same
sustained-handshake byte reduction.

Read the two-edge proxy report:
[AIWire Explicit Proxy Two-Edge Run](docs/perf/aiwire_proxy_two_nano_2026-07-06.md).

The next run added a third reachable Jetson Orin Nano-class edge target with
the same native sidecar path. A 60-second parallel run verified 4,075 exchanges
as a group: 67.9 exchanges/second, 2,311.8 raw framed bytes per exchange,
363.6 AIWire semantic bytes per exchange, 84.3% semantic-byte savings, and a
47.98 ms max p95 round trip. The result keeps the same shape as the one- and
two-edge sidecar runs: roughly 22.6 exchanges/second per target, stable
sustained-handshake byte reduction, and remaining headroom on the modeled
10 Mbps links.

Read the three-edge proxy report:
[AIWire Explicit Proxy Three-Edge Run](docs/perf/aiwire_proxy_three_nano_2026-07-06.md).

On 2026-07-07, the proxy runner's ready-target workflow was validated against a
mixed six-target lab shape. Preflight found three ready edge targets, two
reachable hosts blocked on batch SSH auth, and one host blocked on SSH TCP. The
runner wrote a generated ready-only targets file, then a 60-second run against
that file verified 4,076 exchanges as a group: 67.9 exchanges/second, 2,311.7
raw framed bytes per exchange, 363.6 AIWire semantic bytes per exchange,
84.3% semantic-byte savings, 6.36x modeled bandwidth capacity gain, and a
47.92 ms max p95 round trip. This reproduced the earlier three-edge result
while keeping strict all-target preflight fail-closed.

Read the ready-target proxy report:
[AIWire Proxy Ready-Targets Run](docs/perf/aiwire_proxy_ready_targets_2026-07-07.md).

Current local benchmark-profile smoke on 2026-07-05 uses the Python AIWire path,
level 3, seed 1729, and synthetic public-safe `corpus_metadata` on every
message. This is a reproducible codec/corpus check, not a LAN throughput claim:

| Profile | Corpus | Messages | Raw bytes | AIWire bytes | Ratio | Saved | Avg raw frame |
|---|---|---:|---:|---:|---:|---:|---:|
| small | structured | 128 | 75,937 | 10,560 | 7.19x | 86.1% | 593.3 B |
| small | delta | 128 | 87,741 | 6,462 | 13.58x | 92.6% | 685.5 B |
| medium | structured | 1,024 | 605,634 | 79,146 | 7.65x | 86.9% | 591.4 B |
| medium | delta | 1,024 | 703,911 | 44,427 | 15.84x | 93.7% | 687.4 B |
| bursty | structured | 256 | 203,163 | 25,021 | 8.12x | 87.7% | 793.6 B |
| bursty | delta | 256 | 225,531 | 15,022 | 15.01x | 93.3% | 881.0 B |

The delta corpus is where the idea is most visible: once session/task/template
shape is stable, repeated structure collapses and mostly changed values cross
the wire.

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

## Explicit Sidecar Proxy

`aura-proxy` is the first runnable service shape for AIWire. It is an explicit
TCP sidecar pair, not transparent OS interception:

```text
local agent -> ingress sidecar -> AIWire tunnel -> egress sidecar -> upstream agent
```

Local client and upstream sockets keep using uint32 length-prefixed raw payload
bytes. The sidecar-to-sidecar hop performs a fail-closed AIWire handshake,
keeps control frames separately inspectable, and moves semantic frames through
the AIWire session stream.

Egress side, next to the upstream service:

```bash
aura-proxy egress \
  --listen-host 0.0.0.0 \
  --listen-port 9102 \
  --upstream-host 127.0.0.1 \
  --upstream-port 8765 \
  --backend native \
  --metrics-output /tmp/aura-egress.metrics.json
```

Ingress side, next to the client:

```bash
aura-proxy ingress \
  --listen-host 127.0.0.1 \
  --listen-port 9101 \
  --egress-host <egress-host-or-z6> \
  --egress-port 9102 \
  --backend native \
  --metrics-output /tmp/aura-ingress.metrics.json \
  --replay-log-output /tmp/aura-ingress.replay.jsonl
```

Use `--backend python` for portable tests, `--backend native` after
`tools/check_aiwire_native_backend.py --build --require-native` passes on both
machines, and `--once` for single-connection smoke runs.

Benchmark the full local proxy path with the public fixture corpus:

```bash
aura-proxy-benchmark \
  --seconds 60 \
  --connections 1 \
  --backend native \
  --modeled-link-mbps 10 \
  --output /tmp/aura-proxy-benchmark.json \
  --replay-log-output /tmp/aura-proxy-benchmark.jsonl
```

For real network runs, start the fixture responder and egress sidecar on each
edge host, then drive the ingress/client side from the coordinator. The helper
below builds that SSH plan and writes per-target artifacts without storing
private host details in the repo:

```bash
python tools/run_aiwire_proxy_cluster.py \
  --target edge-1=<edge-ssh-host> \
  --target edge-2=<edge-ssh-host>,remote_root=/home/<user>/AURA \
  --ssh-bootstrap \
  --ssh-public-key ~/.ssh/id_ed25519.pub \
  --output /tmp/aura-proxy-bootstrap.json \
  --summary-output /tmp/aura-proxy-bootstrap.md

python tools/run_aiwire_proxy_cluster.py \
  --target edge-1=<edge-ssh-host> \
  --target edge-2=<edge-ssh-host>,remote_root=/home/<user>/AURA \
  --preflight \
  --seconds 60 \
  --connections 1 \
  --backend native \
  --fixture-variation-profile cluster \
  --output /tmp/aura-proxy-cluster.json \
  --summary-output /tmp/aura-proxy-cluster.md

# Execute the same plan after preflight passes and the commands look right.
python tools/run_aiwire_proxy_cluster.py \
  --target edge-1=<edge-ssh-host> \
  --target edge-2=<edge-ssh-host>,remote_root=/home/<user>/AURA \
  --preflight \
  --seconds 60 \
  --connections 1 \
  --backend native \
  --fixture-variation-profile cluster \
  --run
```

Use `--ssh-bootstrap` only to generate the safe key-install report when targets
are network-reachable but batch SSH auth fails. It emits `ssh-copy-id`, target
console, and post-check commands; it does not modify hosts.

Target lines can include `proxy_host`, `egress_port`, `upstream_port`, and
`remote_root` overrides. The global `--remote-root` still defaults to `~/AURA`;
use per-target `remote_root=/home/<user>/AURA` when different edge machines use
different SSH users or checkout paths. For bootstrap reports, target lines can
also include `ssh_public_key=/path/to/key.pub` so labs with dedicated per-target
keys do not accidentally emit the same authorized-key command for every edge.
For larger labs, start from the public-safe target file example at
`deploy/aura-proxy/proxy-cluster.targets.example` and keep the real filled-in
copy untracked.
Use `--connections N` to run N parallel client/ingress/egress/fixture sessions
per target. The default is `1`, matching the original single-session proxy
measurements. Use `--connections-sweep 1,2,4,8,16,32,64` to run a repeatable
sequential scaling sweep with one JSON artifact and one markdown summary; add
`128` only when deliberately probing saturation.

Latest LAN validation: after the single-session ready-target run, 60-second
native proxy runs with `--connections 2`, `4`, and `8` across three ready edge
targets verified 8,150, 16,283, and 32,450 exchanges. Group rate scaled from
67.9 ex/s at one connection per target to 540.3 ex/s at eight connections per
target, a 7.96x gain, while AIWire stayed near 366.8 semantic bytes per
exchange, 84.4% semantic-byte savings, and 48.16 ms max p95.

A follow-up `--connections-sweep 16,32` saturation pass on the same ready edge
shape verified 64,914 and 128,739 exchanges across 48 and 96 total sessions.
Group rate reached 1,080.6 and 2,142.2 ex/s, about 15.9x and 31.6x the
single-connection baseline, while AIWire stayed near 366.6 semantic bytes per
exchange, 84.4% semantic-byte savings, 6.40x modeled capacity gain, and
48.61 ms max p95.

A later `--connections-sweep 64,128` pass found the practical knee. The 64x
run verified 229,223 exchanges across 192 sessions at 3,802.8 ex/s, 84.4%
savings, and 59.81 ms max p95. The 128x run still verified, but throughput
dropped to 2,562.6 ex/s and max p95 rose to 223.18 ms, so this LAN sidecar
shape is useful through about 64 connections per target before scheduler,
socket, or sidecar contention dominates.

The proxy runner can also apply deterministic tunnel impairment to the
inter-sidecar AIWire hop with `--tunnel-bandwidth-mbps`,
`--tunnel-one-way-delay-ms`, `--tunnel-jitter-ms`, and tail-pause flags. An
edge-mesh pass using 6 Mbps, 12 ms one-way delay, 8 ms jitter, and 2.5% tail
pauses up to 120 ms verified 82,414 exchanges at 32 connections per target and
164,435 at 64. The 64x impaired run sustained 2,730.3 ex/s with 84.4% byte
savings and 86.14 ms max p95; that is about 51.3 Mbps of raw-JSON-equivalent
movement carried in about 8.0 Mbps of AIWire semantic tunnel bytes across the
three target groups.

The same impaired 64-connection sidecar shape was then rerun with
`--tunnel-codec-sweep raw,zlib,aiwire` so raw, stateless zlib, and AIWire used
the same sidecar envelope and delay model:

| Tunnel codec | Exchanges | Group ex/s | vs raw | Tunnel B/ex | Saved | p95 max | Tunnel Mbps |
|---|---:|---:|---:|---:|---:|---:|---:|
| raw | 114,681 | 1,905.9 | 1.00x | 2,349.8 | -0.1% | 118.85 ms | 35.82 |
| zlib | 165,463 | 2,750.3 | 1.44x | 1,218.1 | 48.1% | 88.54 ms | 26.80 |
| aiwire | 164,436 | 2,731.3 | 1.43x | 367.1 | 84.4% | 86.39 ms | 8.02 |

That result is the clearest current sidecar comparison. AIWire and zlib moved
roughly the same verified exchange rate at this concurrency, so the next
bottleneck is sidecar/runtime work rather than AIWire bytes. But AIWire carried
that rate in about one third of zlib's tunnel bytes and about one sixth of raw's,
leaving much more room for control, verification, telemetry, and retries.

A 20-second-per-codec profiling follow-up on the same 192-session shape added
sidecar stage timing. Stage totals are summed across concurrent sessions, so the
mean milliseconds per call is the useful per-exchange reading:

| Tunnel codec | Group ex/s | Tunnel B/ex | Saved | p95 max | Ingress write mean | Egress write mean | Egress encode mean |
|---|---:|---:|---:|---:|---:|---:|---:|
| raw | 1,890.0 | 2,350.0 | -0.1% | 123.05 ms | 51.09 ms | 48.54 ms | 0.003 ms |
| zlib | 2,741.5 | 1,217.9 | 48.1% | 89.13 ms | 17.28 ms | 16.34 ms | 0.216 ms |
| aiwire | 2,712.8 | 369.2 | 84.3% | 87.20 ms | 15.99 ms | 14.33 ms | 0.302 ms |

The profile says the byte savings are real, but after frames shrink the current
sidecar run is dominated by response-path waits and fixed per-frame latency, not
AIWire encode/decode cost. AIWire encode/decode stayed sub-millisecond per
exchange while consuming far less tunnel bandwidth than zlib.

Preflight checks SSH alias resolution, SSH TCP reachability, batch-mode
authentication, remote AURA importability, fixture corpus presence, and native
backend readiness before any remote sidecars are launched.
Use `--ready-targets-output /tmp/aura-ready-targets.txt` with `--preflight`
when you want a generated targets file containing only machines that passed
readiness.

Editable service templates live under `deploy/aura-proxy/` for systemd and
launchd.

Details:
[AIWire Explicit Sidecar Proxy](docs/aiwire_proxy.md)
and
[AIWire Proxy Edge Readiness Runbook](docs/aiwire_proxy_edge_readiness.md)
include the runbook details. The impaired cross-machine result is captured in
[AIWire Proxy Edge-Mesh Impairment Run](docs/perf/aiwire_proxy_edge_mesh_impairment_2026-07-07.md).
The raw/zlib/AIWire sidecar comparison is captured in
[AIWire Proxy Codec Sweep](docs/perf/aiwire_proxy_codec_sweep_2026-07-07.md).

## Benchmarking AIWire

For a fast local benchmark with stable corpus metrics:

```bash
PYTHONPATH=src python -m aura_compression.cli.benchmark \
  --profile small \
  --corpus delta

PYTHONPATH=src python -m aura_compression.cli.benchmark \
  --profile bursty \
  --corpus structured

PYTHONPATH=src python -m aura_compression.cli.benchmark \
  --profile medium \
  --corpus delta \
  --backend native \
  --sustained-session \
  --peers 4
```

Profiles are `small`, `medium`, and `bursty`; `--messages` can override the
profile count for focused smoke tests. Corpora are `structured` and `delta`.
Benchmark messages include `corpus_metadata` marking them synthetic and
public-safe. Backends are `python`, `native`, and `auto`; the benchmark JSON
reports both the requested backend and the actual encode/decode backend so
Python-vs-native comparisons are explicit. Use `--sustained-session` to model
the main AIWire case: peers handshake once, update shared session templates,
then keep sending only steady-state deltas. `--peers N` scales the setup model
to an n-party session before amortizing setup bytes over the delta stream.

Before running native Python-vs-native comparisons on a workstation or edge
target, build and verify the optional C++ backend on that machine:

```bash
python tools/check_aiwire_native_backend.py --build --require-native --messages 32
```

The same check also has a Make target:

```bash
make -C native/aiwire check
```

The report confirms the loaded `libaura_aiwire` path/version, dictionary
identity, native AIWire round trips, Python/native frame interop, and native
AIToken plus AIToken+AIWire support. GitHub Actions runs the native check on
Linux and macOS.

After native readiness passes, create a repeatable Python-vs-native comparison
artifact from the same sustained-session corpus and fixture-backed network
model:

```bash
PYTHONPATH=src python tools/compare_aiwire_backends.py \
  --backends python,native \
  --messages 128 \
  --fixture-profiles lan_10m \
  --codecs raw,zlib,aiwire,aitoken_aiwire \
  --agent-counts 1,64 \
  --output /tmp/aura_aiwire_backend_compare.json \
  --markdown-output /tmp/aura_aiwire_backend_compare.md
```

The JSON keeps full sustained-session and fixture-saturation results for audit;
the Markdown summarizes backend deltas, byte movement, codec CPU, and whether
the native path actually handled encode/decode. Use `--allow-missing-native`
only for portable smoke tests where skipping native is acceptable.

To identify where the current Python hot path is spending CPU on a workstation
or edge target, generate a cProfile-backed report:

```bash
PYTHONPATH=src python tools/profile_aiwire_hot_path.py \
  --mode both \
  --backend native \
  --messages 128 \
  --codecs raw,zlib,aiwire,aitoken_aiwire \
  --output /tmp/aura_aiwire_hot_path_profile.json \
  --markdown-output /tmp/aura_aiwire_hot_path_profile.md
```

Run the same command with `--backend python` and `--backend native` on each
machine. The report records platform details, native availability, payload
byte/cpu summaries, and the top cumulative/self-time functions for the
sustained-session setup path and fixture codec path.

To compare the coordinator path itself before running the Z6/Nano lab, run the
same local n-ary fixture replay through both coordinator modes:

```bash
PYTHONPATH=src python tools/compare_aiwire_coordinators.py \
  --coordinators threaded,asyncio \
  --target-count 2 \
  --exchanges 12 \
  --codecs raw,aiwire \
  --backend python \
  --agent-count 4 \
  --pipeline-window 2 \
  --link-mbps 10 \
  --output /tmp/aura_aiwire_coordinator_compare.json \
  --markdown-output /tmp/aura_aiwire_coordinator_compare.md
```

The report keeps the full `nary-client` payload for each coordinator and
summarizes completed exchanges, exchange rate, framed bytes per exchange, p95
latency, and utilization deltas by codec. Use `--backend native` after the
native readiness gate passes.

The LAN benchmark harness can run a server on one machine and a client on
another. The live harness also accepts `--backend python|native|auto` on both
server and client paths; keep both sides on the same requested backend when
comparing Python and native AIWire. Client and n-ary client modes also accept
`--coordinator threaded|asyncio`. `threaded` is the historical default;
`asyncio` uses one event loop for peer probes and replay-session fan-out so
coordinator-side network concurrency is measured without client thread-pool
contention.

```bash
# Target machine
PYTHONPATH=src python tools/stress_ai_wire_roundtrip_z6.py server \
  --host 0.0.0.0 \
  --port 8765 \
  --runs 5 \
  --backend python \
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
  --coordinator asyncio \
  --backend python \
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
For native/asyncio measurement after the native readiness gate passes, add
`--backend native --coordinator asyncio`. With fixture replay, add
`--fixture-variation-profile cluster` to vary the public corpus by profile while
preserving SHA-256 response verification.

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
  --backend python \
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
  --coordinator asyncio \
  --backend python \
  --fixture-corpus fixtures/aiwire_sessions/public_session_corpus_v1.json \
  --fixture-session-templates updated \
  --force-session-templates \
  --output /tmp/aura_live_fixture_replay.json
```

In fixture mode, the client and server compare request/response corpus digests
during the handshake and the client verifies each replayed fixture response by
SHA-256.

To coordinate multiple peers under one fail-closed AIWire n-ary contract, start
each target server with one extra run for the handshake probe, then use
`nary-client` from the coordinator. If `--session-shards` is greater than 1,
each target opens multiple independent replay sessions and each session receives
an equal share of that target's modeled `--link-mbps` budget.

```bash
# Each target. runs = 1 probe + codec_count * session_shards.
# For thread-sharded runs, set connection-workers >= session_shards.
# For POSIX forked server workers, use connection-processes instead.
PYTHONPATH=src python tools/stress_ai_wire_roundtrip_z6.py server \
  --host 0.0.0.0 \
  --port 8910 \
  --runs 4 \
  --connection-workers 1 \
  --connection-processes 0 \
  --backend python \
  --fixture-corpus fixtures/aiwire_sessions/public_session_corpus_v1.json \
  --fixture-session-templates updated \
  --link-mbps 10

# Coordinator/client.
PYTHONPATH=src python tools/stress_ai_wire_roundtrip_z6.py nary-client \
  --target edge-1=<target-1>:8910 \
  --target edge-2=<target-2>:8910 \
  --target edge-3=<target-3>:8910 \
  --target edge-4=<target-4>:8910 \
  --seconds 60 \
  --agent-count 64 \
  --pipeline-window 1 \
  --session-shards 1 \
  --link-mbps 10 \
  --codecs raw,zlib,aiwire \
  --coordinator asyncio \
  --backend python \
  --fixture-corpus fixtures/aiwire_sessions/public_session_corpus_v1.json \
  --fixture-session-templates updated \
  --fixture-variation-profile cluster \
  --force-session-templates \
  --target-parallelism 4 \
  --output /tmp/aura_nary_fixture_replay.json
```

## Transport Examples

AIWire frames are ordinary bytes after the session handshake. The repo includes
small examples for common transport boundaries. Each example now carries both
semantic frames and compact routine-control LUT frames so route/status control
stays inspectable without decompressing the semantic stream:

- [Length-prefixed TCP](examples/aiwire_tcp_transport.py)
- [WebSocket binary messages](examples/aiwire_websocket_transport.py)
- [HTTP POST with Server-Sent Events](examples/aiwire_http_streaming_transport.py)
- [Local broker/topic queue](examples/aiwire_local_broker.py)
- [Replay-log JSONL audit format](docs/aiwire_replay_log.md)

Run them from the repo root with `PYTHONPATH=src`. The WebSocket example uses
the optional `websocket` extra. TCP uses an explicit length prefix; WebSocket,
SSE, and broker examples rely on their native message/event boundaries. All
examples keep mission-critical control out of the compact LUT path.

Convert any stress or network-suite JSON artifact into a deterministic replay
log with payload hashes:

```bash
PYTHONPATH=src python tools/write_aiwire_replay_log.py \
  /tmp/aura_nary_fixture_replay.json \
  --output /tmp/aura_nary_fixture_replay.jsonl
```

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
- [AIWire Z6-to-Nano relay benchmark](docs/perf/z6_to_nano_aiwire_2026-07-05.md)
- [AIWire n-ary Z6-to-Nano benchmark](docs/perf/aiwire_nary_z6_to_nano_2026-07-05.md)
- [AIWire proxy codec sweep](docs/perf/aiwire_proxy_codec_sweep_2026-07-07.md)
- [AIWire fixture saturation benchmark](docs/perf/aiwire_fixture_saturation_2026-07-04.md)
- [Transport examples](examples/README.md)
- [Large-file and API notes](docs/api/compressor.md)

## Tests

```bash
PYTHONPATH=src pytest tests/test_ai_wire.py tests/test_ai_wire_token.py \
  tests/test_aiwire_benchmark_smoke.py tests/test_aiwire_session_fixtures.py \
  tests/test_aiwire_bandwidth_extrapolation.py \
  tests/test_aiwire_fixture_saturation.py tests/test_aiwire_backend_comparison.py \
  tests/test_aiwire_hot_path_profile.py tests/test_aiwire_stress_fixture_replay.py \
  tests/test_aiwire_coordinator_comparison.py \
  tests/test_aiwire_network_profiles.py -q
pytest -q
```

Formatting checks used in this repo:

```bash
uvx black --check src/aura_compression tests tools
uvx isort --check-only src/aura_compression tests tools
```

## Roadmap Summary

Current phase state:

- Phase 1 Public Baseline: complete and maintained.
- Phase 2 AIWire v1 Hardening: complete and maintained by the fast AIWire gate.
- Phase 3 Better Message Corpora: complete and maintained with deterministic
  corpora, local benchmark profiles, corpus summaries, public-safe metadata, and
  CI smoke thresholds.
- Phase 4 Native and Edge Performance: next active performance track.
- Phase 5 Transport Examples: implemented for TCP, WebSocket, HTTP streaming,
  and local broker; replay-log polish remains.
- Phase 6 Dictionary Evolution: planned.
- Phase 7 General AURA Cleanup: planned.

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
