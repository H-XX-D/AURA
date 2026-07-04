# Realistic AIWire Network Benchmarks

This benchmark suite measures AURA/AIWire under network conditions that look
closer to real agent deployments than a single clean LAN run.

## What The Suite Models

Each profile has separate client-to-server and server-to-client settings:

- Egress bandwidth in Mbps.
- One-way propagation delay.
- Per-frame jitter.
- Occasional tail pauses to approximate queue spikes or TCP retransmit recovery.
- Pipeline depth, because high-RTT links need more in-flight exchanges.
- Concurrent logical agents, because each agent contributes to the aggregate
  in-flight window needed to fill a bandwidth-delay product.

The harness still uses TCP and does not drop application frames. Lossy networks
are modeled as latency tails, not as corrupted or missing messages.

## Profile Set

Profiles live in [`tools/aiwire_network_profiles.py`](../../tools/aiwire_network_profiles.py).

| Profile | Purpose |
|---|---|
| `loopback_cpu` | CPU ceiling with no modeled link bottleneck. |
| `lan_1g` | Clean wired gigabit-class LAN. |
| `lan_10m` | Constrained local lab link for bandwidth-proportional tests. |
| `wifi_good` | Good Wi-Fi with moderate jitter and asymmetric throughput. |
| `wifi_busy` | Congested Wi-Fi with queue spikes. |
| `wan_regional` | Regional cloud or office WAN. |
| `lte_good` | Healthy mobile uplink/downlink asymmetry. |
| `lte_poor` | Weak cellular with low uplink and frequent stalls. |
| `satellite` | High-latency satellite-style path. |
| `edge_mesh` | Small edge mesh or Nano-class LAN under contention. |

## Run A Local Suite

```bash
PYTHONPATH=src python tools/run_aiwire_network_suite.py \
  --profiles lan_10m,wifi_busy,lte_good,edge_mesh \
  --seconds 5 \
  --exchanges 20000 \
  --agent-count 8 \
  --codecs raw,zlib,aiwire,aitoken_aiwire \
  --discover-session-templates \
  --output /tmp/aura_aiwire_network_suite.json
```

Generate the report:

```bash
python tools/analyze_ai_wire_benchmark.py \
  /tmp/aura_aiwire_network_suite.json \
  --output /tmp/aura_aiwire_network_suite.md
```

Extrapolate exchange and data movement at other bandwidths from the measured
bytes-per-exchange:

```bash
python tools/extrapolate_aiwire_bandwidth.py \
  /tmp/aura_aiwire_network_suite.json \
  --bandwidth-mbps 1,5,10,50,100,1000 \
  --agent-counts 1,2,4,8,16,32 \
  --per-agent-window 1 \
  --output /tmp/aura_aiwire_bandwidth_extrapolation.md
```

The extrapolation includes latency limits. It reports pure bandwidth capacity
and effective capacity, where effective capacity is capped by:

```text
aggregate_inflight_window / projected_p95_roundtrip_seconds
```

Projected p95 keeps the measured non-serialization tail from the benchmark and
recomputes request/response serialization delay at the requested Mbps. This
keeps high-RTT profiles honest: saving bytes creates capacity, but the stream
needs enough in-flight exchanges to fill that capacity. Required agents are
estimated as:

```text
ceil(bandwidth_capacity_exchanges_per_second * projected_p95_seconds / per_agent_window)
```

## Run The Fixture Saturation Model

For a fast, reproducible pass that does not open sockets, run the fixture-backed
saturation benchmark:

```bash
PYTHONPATH=src python tools/benchmark_aiwire_fixture_saturation.py \
  --fixture-corpus fixtures/aiwire_sessions/public_session_corpus_v1.json \
  --profiles lan_10m,wifi_busy,lte_good,edge_mesh \
  --codecs raw,zlib,aitoken,aiwire,aitoken_aiwire \
  --agent-counts 1,8,64 \
  --backend python \
  --markdown-output docs/perf/aiwire_fixture_saturation_2026-07-04.md \
  --output /tmp/aura_aiwire_fixture_saturation_2026-07-04.json \
  --format markdown
```

This model measures codec bytes on the committed public AIWire session fixture,
then projects saturation using the same realistic profile definitions. It is
useful for CI and documentation because the traffic corpus is stable and
public-safe. It complements the live TCP harness; it does not replace real
round-trip tests across machines.

Current snapshot:
[AIWire Fixture Bandwidth Saturation](aiwire_fixture_saturation_2026-07-04.md)

## Replay The Public Fixture Over Live TCP

The stress harness can replay the committed public fixture corpus over a real
length-prefixed TCP connection. In this mode, the client declares fixture
request/response digests during the handshake, the server rejects mismatched
corpora, and the client verifies replayed responses by SHA-256.

```bash
PYTHONPATH=src python tools/run_aiwire_network_suite.py \
  --profiles lan_10m,wifi_busy,lte_good,edge_mesh \
  --seconds 5 \
  --exchanges 36 \
  --agent-count 64 \
  --codecs raw,zlib,aiwire,aitoken_aiwire \
  --fixture-corpus fixtures/aiwire_sessions/public_session_corpus_v1.json \
  --fixture-session-templates updated \
  --force-session-templates \
  --output /tmp/aura_aiwire_fixture_tcp_suite.json
```

For a single manual profile, add the same fixture flags to both the server and
client commands.

## Run One Manual Profile Across Machines

Start the server using the server-side profile values:

```bash
PYTHONPATH=src python tools/stress_ai_wire_roundtrip_z6.py server \
  --host 0.0.0.0 \
  --port 8910 \
  --runs 4 \
  --link-mbps 8 \
  --one-way-delay-ms 65 \
  --jitter-ms 35 \
  --tail-pause-probability 0.04 \
  --tail-pause-ms 300
```

Run the client using the client-side profile values:

```bash
PYTHONPATH=src python tools/stress_ai_wire_roundtrip_z6.py client \
  --host <target-host> \
  --port 8910 \
  --seconds 5 \
  --exchanges 20000 \
  --codecs raw,zlib,aiwire,aitoken_aiwire \
  --agent-count 32 \
  --pipeline-window 1 \
  --link-mbps 1.5 \
  --one-way-delay-ms 65 \
  --jitter-ms 35 \
  --tail-pause-probability 0.06 \
  --tail-pause-ms 350 \
  --output /tmp/aura_lte_poor.json
```

## Metrics That Matter

- Completed verified request/response exchanges per second.
- Framed bytes per exchange.
- Bandwidth-proportional exchange capacity per profile.
- Observed utilization of that bandwidth capacity.
- Concurrent logical agents needed to fill the latency window.
- p95/p99 roundtrip latency and tail tax.
- Codec CPU per exchange.
- Request/response bottleneck direction for asymmetric links.
- Extrapolated semantic MiB/s and GiB/hour at chosen bandwidths.
- Projected p95 latency and latency-window exchange capacity.

Compression ratio is useful, but it is not the headline. The headline is how
many verified semantic exchanges fit through the constrained link without
turning CPU or tail latency into the next bottleneck.
