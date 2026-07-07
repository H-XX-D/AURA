# AIWire Proxy Multi-Connection Scaling Run

This is the public-safe follow-up to the ready-target proxy benchmark. It uses
the same explicit sidecar shape, public fixture corpus, cluster variation
profile, native backend, and 10 Mbps modeled-link reporting, but sweeps the
proxy sessions from one to eight per ready target.

Run shape:

- Coordinator: local Z6-class machine
- Edge shape: 3 ready LAN targets
- Backend: `native`
- Fixture variation profile: `cluster`
- Duration: 60 seconds
- Connections per target: 1, 2, 4, and 8
- Total proxy sessions: 3, 6, 12, and 24

Aggregate sweep:

| Connections per target | Total sessions | Exchanges | Group ex/s | vs 1x | Raw B/ex | AIWire B/ex | Saved | Capacity gain | p95 max |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 3 | 4,076 | 67.9 | 1.00x | 2,311.7 | 363.6 | 84.3% | 6.36x | 47.92 ms |
| 2 | 6 | 8,150 | 135.8 | 2.00x | 2,348.0 | 366.7 | 84.4% | 6.40x | 47.92 ms |
| 4 | 12 | 16,283 | 271.2 | 3.99x | 2,348.1 | 366.7 | 84.4% | 6.40x | 47.92 ms |
| 8 | 24 | 32,450 | 540.3 | 7.96x | 2,347.5 | 366.8 | 84.4% | 6.40x | 48.16 ms |

Interpretation:

- Connection sharding scaled useful message movement almost linearly through
  eight sessions per target for this LAN sidecar shape.
- The per-exchange byte profile stayed stable, which is what AURA wants from a
  bandwidth-proportional tunnel: more lanes move more deltas without inflating
  each exchange.
- The p95 latency ceiling stayed effectively flat through 24 total proxy
  sessions, so the extra sessions improved throughput without an obvious
  tail-latency penalty at this scale.

This run still uses public fixture traffic and a modeled 10 Mbps capacity view.
It is not a production workload replay or a throttled WAN test.
