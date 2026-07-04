# AURA

AURA is an experimental compression toolkit for structured AI-to-AI traffic.
Its strongest current path is **AIWire**: a negotiated structure side channel
for high-volume agent messages moving over ordinary TCP, HTTP, WebSocket, or LAN
links.

AIWire is not just "compress each JSON frame." Peers handshake the structure
first: protocol identity, static dictionary, session templates, and optional
session-local structure updates. After that, agents should send compact changes
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
| AIWire structural side channel | Working Python path, optional native backend loader |
| Structured message helpers | Working canonical JSON encode/decode helpers |
| AI-to-AI benchmark harness | Working LAN roundtrip benchmark tooling |
| General AURA compressor | Alpha research path |
| Large-file CLI | Experimental but usable for local tests |
| Production readiness | Not production-ready; use for prototyping and measurement |

The package targets CPython 3.10+.

## Benchmark Snapshot

On 2026-07-04, AIWire was benchmarked from a Mac client to a workstation-class
Z6 target and four Jetson Nano-class edge targets on a local LAN. The benchmark
modeled a 10 Mbps egress link per direction and used 5 second request/response
windows.

| Target group | raw | zlib | AIWire |
|---|---:|---:|---:|
| Z6 target, completed exchanges in 5s | 8,777 | 14,952 | 55,337 |
| Z6 target, vs raw | 1.00x | 1.70x | 6.30x |
| Nano average, completed exchanges in 5s | 8,752 | 14,951 | 20,887 |
| Nano average, vs raw | 1.00x | 1.71x | 2.39x |

Read the full report:
[AI-to-AI LAN Benchmark](docs/perf/ai_to_ai_lan_benchmark_2026-07-04.md)

The benchmark also showed that the generic `ProductionHybridCompressor` path is
not the right fit for this small-message workload yet. AIWire is the intended
AURA path for high-volume structured AI message streams.

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
PYTHONPATH=src python tools/stress_ai_wire_roundtrip_z6.py server --host 0.0.0.0 --port 8765

# Client machine
PYTHONPATH=src python tools/stress_ai_wire_roundtrip_z6.py client \
  --host <target-host> \
  --port 8765 \
  --seconds 5 \
  --agent-count 16 \
  --pipeline-window 1 \
  --link-mbps 10 \
  --codecs raw,zlib,aura,aiwire
```

Codec meanings:

- `raw`: canonical structured JSON frames
- `zlib`: stateless zlib per frame
- `aura`: generic `ProductionHybridCompressor` per frame
- `aiwire`: stateful AURA AIWire structure side channel and delta stream

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
- [AI-to-AI LAN benchmark](docs/perf/ai_to_ai_lan_benchmark_2026-07-04.md)
- [Large-file and API notes](docs/api/compressor.md)

## Tests

```bash
PYTHONPATH=src pytest tests/test_ai_wire.py -q
pytest -q
```

Formatting checks used in this repo:

```bash
uvx black --check src/aura_compression tests tools/stress_ai_wire_roundtrip_z6.py
uvx isort --check-only src/aura_compression tests tools/stress_ai_wire_roundtrip_z6.py
```

## Roadmap Summary

The near-term roadmap is to harden AIWire first:

- Stabilize the AIWire v1 frame and handshake contract
- Define the session-template update signal and delta/resync behavior
- Keep benchmark reports reproducible and public-safe
- Add more realistic MCP, A2A, OpenAI, and local agent message corpora
- Improve ARM64/native backend performance for edge targets
- Add transport examples for TCP, WebSocket, HTTP streaming, and local broker use
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
