# AIWire Proxy Edge-Mesh Impairment Run

This run applies an explicit tunnel impairment to the sidecar hop instead of
only reporting a modeled link budget. The local raw client and remote raw
fixture service stay local to their sidecars; bandwidth, propagation delay,
jitter, and tail pauses are applied to the inter-sidecar AIWire tunnel writes.

Run shape:

- Coordinator: local Z6-class machine
- Edge shape: 3 ready LAN targets
- Backend: `native`
- Fixture variation profile: `cluster`
- Duration: 60 seconds
- Connections per target: 32 and 64
- Total proxy sessions: 96 and 192
- Tunnel impairment per target direction: 6 Mbps, 12 ms one-way delay, 8 ms
  jitter, 2.5% tail pauses up to 120 ms

Command shape:

```bash
python tools/run_aiwire_proxy_cluster.py \
  --targets-file /tmp/aura-ready-targets.txt \
  --preflight --run --seconds 60 \
  --connections-sweep 32,64 \
  --backend native \
  --fixture-variation-profile cluster \
  --target-parallelism 3 \
  --modeled-link-mbps 6 \
  --tunnel-bandwidth-mbps 6 \
  --tunnel-one-way-delay-ms 12 \
  --tunnel-jitter-ms 8 \
  --tunnel-tail-pause-probability 0.025 \
  --tunnel-tail-pause-ms 120 \
  --impairment-seed 1729
```

Aggregate sweep:

| Connections per target | Total sessions | Exchanges | Group ex/s | Raw B/ex | AIWire B/ex | Saved | Capacity gain | p95 max | Raw-equivalent Mbps | AIWire wire Mbps |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 32 | 96 | 82,414 | 1,370.9 | 2,347.9 | 367.1 | 84.4% | 6.40x | 86.03 ms | 25.75 | 4.03 |
| 64 | 192 | 164,435 | 2,730.3 | 2,348.1 | 367.1 | 84.4% | 6.40x | 86.14 ms | 51.29 | 8.02 |

Interpretation:

- The impaired tunnel preserved the byte profile: each verified exchange still
  moved about 367 AIWire semantic bytes instead of about 2,348 raw framed bytes.
- 64 connections per target still nearly doubled 32 connections per target under
  edge-mesh delay, jitter, and tail pauses.
- Tail latency stayed stable between 32 and 64 connections per target, with p95
  around 86 ms in both levels.
- At 64 connections per target, the useful raw-JSON-equivalent movement was
  about 51.3 Mbps across the three target groups while AIWire semantic tunnel
  bytes used about 8.0 Mbps. That is the bandwidth-proportional result AURA is
  trying to expose: the application gets more verified JSON exchanges than raw
  framing could fit through the same kind of constrained tunnel.

This is still a benchmark harness, not production `tc/netem` shaping. The
impairment is applied in the sidecar write path so it is deterministic,
portable, and can run without privileged network configuration.

The same 64-connection impaired sidecar shape was rerun with raw, zlib, and
AIWire tunnel payload codecs. That comparison is documented in
[AIWire Proxy Codec Sweep](aiwire_proxy_codec_sweep_2026-07-07.md).
