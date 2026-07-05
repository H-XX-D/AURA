# AIWire N-ary Z6-to-Nano Cluster Benchmark

Date: 2026-07-05

## Setup

This run extended the Z6-to-Nano relay test from independent one-target
sessions to one coordinator-mediated n-ary session contract. The Z6 acted as
the coordinator and client. Four ARM64 Jetson Orin Nano-class edge targets ran
the benchmark server.

Host-specific LAN addresses, usernames, and private machine names are omitted
from this public report. Targets are labeled `edge-1` through `edge-4`.

The run used:

- Fixture: `fixtures/aiwire_sessions/public_session_corpus_v1.json`
- Tool: `tools/stress_ai_wire_roundtrip_z6.py nary-client`
- Topology: one Z6 coordinator/client to four edge servers
- Codecs: `raw`, `zlib`, `aiwire`
- Duration: 5 seconds per codec
- Link model: 10 Mbps in each direction per target
- Aggregate modeled server egress: 40 Mbps across four targets
- Logical agents: 64 per target
- Per-agent pipeline window: 1
- Fixture response verification: SHA-256
- Fixture variation profile: `cluster`
- AIWire backend: Python

The `cluster` variation profile keeps the public fixture corpus as the base
semantic workload, then deterministically varies each peer's frames with
different roles, routes, workloads, epochs, queue depths, token windows,
backpressure flags, and telemetry. Client and server derive the same varied
request/response bytes independently, so SHA-256 verification still checks the
actual bytes moved during the run.

Before replay, the coordinator performed one handshake probe per peer, collected
each peer's AIWire server handshake, and ran fail-closed n-ary negotiation with
fallback disabled. The n-ary negotiation accepted all four peers:

- Shared codec: `aiwire`
- Shared version: `1`
- Remote peer count: `4`
- Participant count including coordinator: `5`
- Session-template count: `8`
- Session-template SHA-256:
  `1797e19dc003b6c9b7b5d7549a99b45a7ccb5911927387a4215d24a0aea020d6`

Command shape:

```bash
# Each edge target, launched from the Z6 relay.
# Runs = one n-ary probe + one replay per codec.
PYTHONPATH=src python3 tools/stress_ai_wire_roundtrip_z6.py server \
  --host 0.0.0.0 \
  --port 8910 \
  --runs 4 \
  --fixture-corpus fixtures/aiwire_sessions/public_session_corpus_v1.json \
  --fixture-session-templates updated \
  --link-mbps 10

# Z6 coordinator/client.
PYTHONPATH=src python3 tools/stress_ai_wire_roundtrip_z6.py nary-client \
  --target edge-1=<edge-target-1>:8910 \
  --target edge-2=<edge-target-2>:8910 \
  --target edge-3=<edge-target-3>:8910 \
  --target edge-4=<edge-target-4>:8910 \
  --seconds 5 \
  --agent-count 64 \
  --pipeline-window 1 \
  --link-mbps 10 \
  --codecs raw,zlib,aiwire \
  --fixture-corpus fixtures/aiwire_sessions/public_session_corpus_v1.json \
  --fixture-session-templates updated \
  --fixture-variation-profile cluster \
  --force-session-templates \
  --target-parallelism 4
```

## Aggregate Results

`Completed 5s group` is the sum of verified request/response exchanges across
the four targets during the 5 second codec window. `BW cap ex/s` is the modeled
aggregate bandwidth capacity implied by the measured framed bytes per exchange.

| Codec | Completed 5s group | Ex/s group | vs raw | Framed B/ex | Saved | p95 avg | p95 max | BW cap ex/s | Util |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| raw | 21,710 | 4,342.0 | 1.00x | 2,305.3 | -0.3% | 67.82 | 69.06 | 4,331.6 | 100.2% |
| zlib | 23,011 | 4,602.2 | 1.06x | 1,214.3 | 47.1% | 60.94 | 62.08 | 8,222.2 | 56.0% |
| aiwire | 23,009 | 4,601.8 | 1.06x | 367.7 | 84.0% | 60.49 | 60.93 | 26,784.9 | 17.2% |

## Per-target Results

| Target | Codec | Completed 5s | Ex/s | Framed B/ex | Saved | p95 ms | BW cap ex/s | Util |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| edge-1 | raw | 5,401 | 1,080.2 | 2,311.2 | -0.3% | 67.64 | 1,080.1 | 100.0% |
| edge-2 | raw | 5,439 | 1,087.8 | 2,303.3 | -0.3% | 66.09 | 1,083.8 | 100.4% |
| edge-3 | raw | 5,426 | 1,085.2 | 2,303.2 | -0.3% | 68.49 | 1,083.8 | 100.1% |
| edge-4 | raw | 5,444 | 1,088.8 | 2,303.3 | -0.3% | 69.06 | 1,083.9 | 100.5% |
| edge-1 | zlib | 5,880 | 1,176.0 | 1,217.3 | 47.2% | 60.32 | 2,050.3 | 57.4% |
| edge-2 | zlib | 5,597 | 1,119.4 | 1,213.2 | 47.1% | 61.93 | 2,057.2 | 54.4% |
| edge-3 | zlib | 5,876 | 1,175.2 | 1,213.5 | 47.1% | 59.41 | 2,057.0 | 57.1% |
| edge-4 | zlib | 5,658 | 1,131.6 | 1,213.1 | 47.2% | 62.08 | 2,057.8 | 55.0% |
| edge-1 | aiwire | 5,688 | 1,137.6 | 366.4 | 84.1% | 60.54 | 6,751.1 | 16.9% |
| edge-2 | aiwire | 5,753 | 1,150.6 | 368.1 | 84.0% | 60.28 | 6,681.9 | 17.2% |
| edge-3 | aiwire | 5,755 | 1,151.0 | 368.0 | 84.0% | 60.93 | 6,679.2 | 17.2% |
| edge-4 | aiwire | 5,813 | 1,162.6 | 368.4 | 84.0% | 60.21 | 6,672.8 | 17.4% |

## Readout

The n-ary contract worked: all four peers agreed on the same AIWire version,
static dictionary identity, session-template hash, and required session-template
state before any replay traffic was counted. Every fixture response was
verified by SHA-256.

The aggregate throughput result is deliberately conservative and more realistic
than replaying the same exact frame sequence on every peer. The cluster
variation roughly doubled the raw framed exchange size compared with the clean
fixture run. Raw JSON filled the four modeled 10 Mbps links almost exactly.
zlib reduced bytes enough that link utilization dropped to 56.0%. AIWire
reduced each verified varied exchange to about 367.7 framed bytes, so modeled
bandwidth capacity rose to about 26,785 exchanges per second across the four
targets. The measured Python coordinator used 17.2% of that capacity.

That means the bottleneck moved. On this four-target n-ary run, AIWire's main
benefit was not fully expressed as more completed exchanges because the Z6
Python coordinator, per-frame encode/decode work, and one in-flight request per
logical agent limited the run first. The important signal is still useful for
edge networking: even with varied working-cluster traffic, after the sustained
handshake AIWire leaves most of the modeled link free for more agents, wider
windows, safety checks, retries, control traffic, or other payload lanes.
