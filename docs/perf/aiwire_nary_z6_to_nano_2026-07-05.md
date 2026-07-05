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
- Duration: 60 seconds per codec
- Link model: 10 Mbps in each direction per target
- Aggregate modeled server egress: 40 Mbps across four targets
- Logical agents: 64 per target
- Per-agent pipeline window: 1 baseline, with AIWire-only follow-up at 2, 4,
  and 8
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
  --seconds 60 \
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

`Completed 60s group` is the sum of verified request/response exchanges across
the four targets during the 60 second codec window. `BW cap ex/s` is the modeled
aggregate bandwidth capacity implied by the measured framed bytes per exchange.

| Codec | Completed 60s group | Ex/s group | vs raw | Framed B/ex | Saved | p95 avg | p95 max | BW cap ex/s | Util |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| raw | 259,065 | 4,317.8 | 1.00x | 2,313.0 | -0.3% | 68.75 | 69.31 | 4,317.0 | 100.0% |
| zlib | 287,744 | 4,795.7 | 1.11x | 1,219.3 | 47.1% | 60.77 | 61.44 | 8,187.8 | 58.6% |
| aiwire | 279,904 | 4,665.1 | 1.08x | 368.1 | 84.0% | 62.68 | 64.00 | 26,734.6 | 17.4% |

## AIWire Pipeline-Window Sweep

After the baseline run, the same Z6-to-four-edge n-ary workload was repeated
for AIWire only while widening the per-agent pipeline window. This isolates the
question of whether one Python stream can consume the bandwidth headroom AIWire
creates.

Command shape:

```bash
PYTHONPATH=src python3 tools/stress_ai_wire_roundtrip_z6.py nary-client \
  --target edge-1=<edge-target-1>:8910 \
  --target edge-2=<edge-target-2>:8910 \
  --target edge-3=<edge-target-3>:8910 \
  --target edge-4=<edge-target-4>:8910 \
  --seconds 60 \
  --agent-count 64 \
  --pipeline-window <1|2|4|8> \
  --link-mbps 10 \
  --codecs aiwire \
  --fixture-corpus fixtures/aiwire_sessions/public_session_corpus_v1.json \
  --fixture-session-templates updated \
  --fixture-variation-profile cluster \
  --force-session-templates \
  --target-parallelism 4
```

| Pipeline window | Aggregate window/target | Completed 60s group | Ex/s group | vs window 1 | Framed B/ex | Saved | p95 avg | p95 max | BW cap ex/s | Util |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 64 | 279,904 | 4,665.1 | 1.00x | 368.1 | 84.0% | 62.68 | 64.00 | 26,734.6 | 17.4% |
| 2 | 128 | 269,437 | 4,490.6 | 0.96x | 368.1 | 84.0% | 125.34 | 129.71 | 26,735.5 | 16.8% |
| 4 | 256 | 276,090 | 4,601.5 | 0.99x | 368.1 | 84.0% | 251.51 | 253.50 | 26,735.5 | 17.2% |
| 8 | 512 | 237,916 | 3,965.3 | 0.85x | 368.1 | 84.0% | 739.82 | 926.68 | 26,737.9 | 14.8% |

The extra queue depth did not increase sustained throughput. Window 4 stayed
near the baseline exchange rate but quadrupled p95 latency, and window 8 reduced
throughput while pushing p95 into the high hundreds of milliseconds. That means
the current limiter is not only the number of outstanding frames; it is the
single Python stream/server execution path. To consume AIWire's bandwidth
headroom, the next benchmark should add multiple sessions or connections per
target, or move the coordinator/server hot path to native/concurrent execution.

## Per-target Results

| Target | Codec | Completed 60s | Ex/s | Framed B/ex | Saved | p95 ms | BW cap ex/s | Util |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| edge-1 | raw | 64,590 | 1,076.5 | 2,319.0 | -0.3% | 68.89 | 1,076.5 | 100.0% |
| edge-2 | raw | 64,818 | 1,080.3 | 2,311.0 | -0.3% | 67.61 | 1,080.2 | 100.0% |
| edge-3 | raw | 64,833 | 1,080.5 | 2,311.0 | -0.3% | 69.31 | 1,080.2 | 100.0% |
| edge-4 | raw | 64,824 | 1,080.4 | 2,311.0 | -0.3% | 69.20 | 1,080.2 | 100.0% |
| edge-1 | zlib | 70,536 | 1,175.6 | 1,222.2 | 47.1% | 61.18 | 2,041.7 | 57.6% |
| edge-2 | zlib | 71,768 | 1,196.1 | 1,218.3 | 47.1% | 61.13 | 2,048.4 | 58.4% |
| edge-3 | zlib | 74,380 | 1,239.7 | 1,218.6 | 47.1% | 59.32 | 2,048.4 | 60.5% |
| edge-4 | zlib | 71,060 | 1,184.3 | 1,218.1 | 47.1% | 61.44 | 2,049.2 | 57.8% |
| edge-1 | aiwire | 71,475 | 1,191.2 | 366.6 | 84.1% | 60.47 | 6,741.6 | 17.7% |
| edge-2 | aiwire | 69,105 | 1,151.8 | 368.5 | 84.0% | 64.00 | 6,665.0 | 17.3% |
| edge-3 | aiwire | 69,851 | 1,164.2 | 368.5 | 84.0% | 62.42 | 6,666.1 | 17.5% |
| edge-4 | aiwire | 69,473 | 1,157.9 | 368.9 | 84.0% | 63.85 | 6,661.8 | 17.4% |

## Readout

The n-ary contract worked: all four peers agreed on the same AIWire version,
static dictionary identity, session-template hash, and required session-template
state before any replay traffic was counted. Every fixture response was
verified by SHA-256.

The aggregate throughput result is deliberately conservative and more realistic
than replaying the same exact frame sequence on every peer. The cluster
variation roughly doubled the raw framed exchange size compared with the clean
fixture run. Raw JSON filled the four modeled 10 Mbps links almost exactly.
zlib reduced bytes enough that link utilization dropped to 58.6%. AIWire
reduced each verified varied exchange to about 368.1 framed bytes, so modeled
bandwidth capacity rose to about 26,735 exchanges per second across the four
targets. The measured Python coordinator used 17.4% of that capacity.

That means the bottleneck moved. On this four-target n-ary run, AIWire's main
benefit was not fully expressed as more completed exchanges because the Z6
Python coordinator, per-frame encode/decode work, and one in-flight request per
logical agent limited the run first. The important signal is still useful for
edge networking: even with varied working-cluster traffic, after the sustained
handshake AIWire leaves most of the modeled link free for more agents, wider
windows, safety checks, retries, control traffic, or other payload lanes.
