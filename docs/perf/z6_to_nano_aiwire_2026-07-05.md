# AIWire Z6-to-Nano Relay Benchmark

Date: 2026-07-05

## Setup

This run tested the path the edge machines actually use: the local workstation
reached a Z6 relay over SSH, then the Z6 launched the benchmark client and
reached four ARM64 Jetson Orin Nano-class targets on the local network.

Host-specific LAN addresses, usernames, and private machine names are omitted
from this public report. The benchmark code was staged to temporary directories
on the relay and edge targets.

The run used the committed public fixture corpus with updated session templates:

- Fixture: `fixtures/aiwire_sessions/public_session_corpus_v1.json`
- Tool: `tools/stress_ai_wire_roundtrip_z6.py`
- Topology: Z6 client to one Nano server at a time
- Codecs: `raw`, `zlib`, `aiwire`
- Duration: 5 seconds per codec
- Link model: 10 Mbps in each direction
- Logical agents: 64
- Per-agent pipeline window: 1
- Fixture response verification: SHA-256
- AIWire backend: Python

Command shape:

```bash
# Edge target, launched from the Z6 relay
PYTHONPATH=src python3 tools/stress_ai_wire_roundtrip_z6.py server \
  --host 0.0.0.0 \
  --port 8765 \
  --runs 3 \
  --fixture-corpus fixtures/aiwire_sessions/public_session_corpus_v1.json \
  --fixture-session-templates updated \
  --link-mbps 10

# Z6 relay
PYTHONPATH=src python3 tools/stress_ai_wire_roundtrip_z6.py client \
  --host <edge-target> \
  --port 8765 \
  --seconds 5 \
  --agent-count 64 \
  --pipeline-window 1 \
  --link-mbps 10 \
  --codecs raw,zlib,aiwire \
  --fixture-corpus fixtures/aiwire_sessions/public_session_corpus_v1.json \
  --fixture-session-templates updated \
  --force-session-templates
```

## Results

`Completed 5s` is verified request/response exchanges completed before the 5
second deadline. `Framed B/ex` includes the benchmark's frame overhead.
`BW cap ex/s` is the modeled 10 Mbps bandwidth capacity implied by the measured
framed bytes per exchange. `Util` compares observed throughput with that
modeled bandwidth capacity.

| Target | Codec | Completed 5s | Ex/s | Framed B/ex | Saved | p95 ms | BW cap ex/s | Util |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Nano edge 1 | raw | 11,274 | 2,254.8 | 1,105.4 | -0.7% | 28.90 | 2,254.4 | 100.0% |
| Nano edge 1 | zlib | 19,328 | 3,865.6 | 643.2 | 41.4% | 16.90 | 3,865.2 | 100.0% |
| Nano edge 1 | aiwire | 33,160 | 6,632.0 | 45.6 | 95.8% | 13.55 | 54,279.3 | 12.2% |
| Nano edge 2 | raw | 11,274 | 2,254.8 | 1,105.4 | -0.7% | 28.87 | 2,254.4 | 100.0% |
| Nano edge 2 | zlib | 19,328 | 3,865.6 | 643.2 | 41.4% | 16.86 | 3,865.2 | 100.0% |
| Nano edge 2 | aiwire | 39,698 | 7,939.6 | 45.5 | 95.9% | 12.03 | 54,333.9 | 14.6% |
| Nano edge 3 | raw | 11,264 | 2,252.8 | 1,105.4 | -0.7% | 28.89 | 2,254.3 | 99.9% |
| Nano edge 3 | zlib | 19,327 | 3,865.4 | 643.2 | 41.4% | 16.82 | 3,865.3 | 100.0% |
| Nano edge 3 | aiwire | 36,478 | 7,295.6 | 45.5 | 95.9% | 12.60 | 54,309.2 | 13.4% |
| Nano edge 4 | raw | 11,276 | 2,255.2 | 1,105.3 | -0.7% | 28.90 | 2,254.4 | 100.0% |
| Nano edge 4 | zlib | 19,330 | 3,866.0 | 643.2 | 41.4% | 17.22 | 3,865.2 | 100.0% |
| Nano edge 4 | aiwire | 36,622 | 7,324.4 | 45.5 | 95.9% | 13.32 | 54,310.4 | 13.5% |

## Nano Average

| Codec | Completed 5s | Ex/s | vs raw | Framed B/ex | Saved | p95 ms | BW cap ex/s | Util |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| raw | 11,272.0 | 2,254.4 | 1.00x | 1,105.4 | -0.7% | 28.89 | 2,254.3 | 100.0% |
| zlib | 19,328.3 | 3,865.7 | 1.71x | 643.2 | 41.4% | 16.95 | 3,865.2 | 100.0% |
| aiwire | 36,489.5 | 7,297.9 | 3.24x | 45.5 | 95.9% | 12.88 | 54,308.2 | 13.4% |

AIWire averaged `1.89x` the completed exchanges of zlib and `3.24x` raw on
the same 5 second edge-target windows.

## Readout

This is the strongest machine-to-machine result so far because it keeps the
workload fixture-backed and moves the client onto the Z6 relay rather than the
Mac. Raw JSON and stateless zlib both filled the modeled 10 Mbps link. AIWire
did not fill the link: it reduced each verified fixture exchange to roughly
45.5 framed bytes, so the measured run was limited by runtime scheduling,
agent concurrency, and one in-flight request per logical agent instead of link
bandwidth.

That is the bandwidth-proportional result AURA is aiming for. Once peers have a
sustained handshake and shared session templates, repeated structure stops
moving as whole JSON frames. The wire carries compact deltas, leaving headroom
for more agents, more checks, control traffic, retries, or unrelated payloads
on the same constrained edge link.
