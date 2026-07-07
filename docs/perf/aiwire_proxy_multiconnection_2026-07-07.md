# AIWire Proxy Multi-Connection Run

This is the public-safe follow-up to the ready-target proxy benchmark. It uses
the same explicit sidecar shape, public fixture corpus, cluster variation
profile, native backend, and 10 Mbps modeled-link reporting, but increases the
proxy sessions from one to two per ready target.

Run shape:

- Coordinator: local Z6-class machine
- Edge shape: 3 ready LAN targets
- Backend: `native`
- Fixture variation profile: `cluster`
- Duration: 60 seconds
- Connections per target: 2
- Total proxy sessions: 6

Aggregate result:

| Targets | Connections | Exchanges | Group ex/s | Raw B/ex | AIWire B/ex | Saved | p95 max |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 3/3 | 6 | 8,150 | 135.8 | 2,348.0 | 366.7 | 84.4% | 47.92 ms |

Comparison with the prior single-connection ready-target run:

| Run | Connections | Exchanges | Group ex/s | Raw B/ex | AIWire B/ex | Saved | p95 max |
|---|---:|---:|---:|---:|---:|---:|---:|
| Ready targets, single connection | 3 | 4,076 | 67.9 | 2,311.7 | 363.6 | 84.3% | 47.92 ms |
| Ready targets, two connections | 6 | 8,150 | 135.8 | 2,348.0 | 366.7 | 84.4% | 47.92 ms |

Interpretation:

- Connection sharding doubled useful message movement for this LAN sidecar
  shape while preserving semantic-byte savings.
- The per-exchange byte profile stayed stable, which is what AURA wants from a
  bandwidth-proportional tunnel: more lanes move more deltas without inflating
  each exchange.
- The p95 latency ceiling did not move in this run, so the extra sessions
  improved throughput without an obvious tail-latency penalty at this scale.

This run still uses public fixture traffic and a modeled 10 Mbps capacity view.
It is not a production workload replay or a throttled WAN test.
