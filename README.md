# AURA

AURA is an experimental compression and structure-negotiation toolkit for
AI-to-AI traffic. Its strongest current path is **AIWire**: a negotiated
structure side channel for high-volume agent messages moving over ordinary TCP,
HTTP, WebSocket, or LAN links.

AIWire is not just "compress each JSON frame." Peers handshake the structure
first: protocol identity, static dictionary, session templates, and optional
session-local structure updates. After that, agents send compact changes
against the handshaked structure instead of repeatedly moving whole JSON-shaped
frames.

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
- Structured logs, traces, and operational events with repeated fields

AURA is not a drop-in replacement for gzip, zstd, brotli, TLS, or a message
broker. It is a protocol-aware structural side channel for controlled
environments.

The main metric is not compression ratio by itself. The question is how many
verified semantic exchanges fit through the link once bandwidth, p95 latency,
codec CPU, and enough in-flight agent work are all accounted for.

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

## Install

```bash
git clone https://github.com/H-XX-D/AURA.git
cd AURA
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

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
    build_structured_ai_messages,
    compress_ai_wire_frames,
    decompress_ai_wire_frames,
)

messages = build_structured_ai_messages(1024)
compressed, encode_stats = compress_ai_wire_frames(messages)
restored, decode_stats = decompress_ai_wire_frames(compressed)

assert len(restored) == len(messages)
print(encode_stats.as_dict())
```

## Benchmarking AIWire

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

## Transport Examples

AIWire frames are ordinary bytes after the session handshake. The repo includes
small examples for common transport boundaries:

- [Length-prefixed TCP](examples/aiwire_tcp_transport.py)
- [WebSocket binary messages](examples/aiwire_websocket_transport.py)
- [HTTP POST with Server-Sent Events](examples/aiwire_http_streaming_transport.py)
- [Local broker/topic queue](examples/aiwire_local_broker.py)

Run them from the repo root with `PYTHONPATH=src`. The WebSocket example uses
the optional `websocket` extra.

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
- [AIWire session dictionary safety](docs/aiwire_session_dictionary.md)
- [Realistic network benchmarks](docs/perf/realistic_network_benchmarks.md)
- [AI-to-AI messaging metrics](docs/perf/ai_to_ai_messaging_metrics_2026-07-04.md)
- [AI-to-AI LAN benchmark](docs/perf/ai_to_ai_lan_benchmark_2026-07-04.md)
- [Transport examples](examples/README.md)
- [Large-file and API notes](docs/api/compressor.md)

## Tests

```bash
PYTHONPATH=src pytest tests/test_ai_wire.py tests/test_ai_wire_token.py \
  tests/test_aiwire_bandwidth_extrapolation.py tests/test_aiwire_network_profiles.py -q
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
- Publish the AIWire v1 side-channel and delta-frame spec
- Define the session-template update signal and delta/resync behavior
- Keep benchmark reports reproducible and public-safe
- Keep improving realistic MCP, A2A, OpenAI, and local agent message corpora
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
