# AIWire Proxy Multi-Connection Scaling Run

This is the public-safe follow-up to the ready-target proxy benchmark. It uses
the same explicit sidecar shape, public fixture corpus, cluster variation
profile, native backend, and 10 Mbps modeled-link reporting, but sweeps the
proxy sessions from one to one hundred twenty-eight per ready target.

Run shape:

- Coordinator: local Z6-class machine
- Edge shape: 3 ready LAN targets
- Backend: `native`
- Fixture variation profile: `cluster`
- Duration: 60 seconds
- Connections per target: 1, 2, 4, 8, 16, 32, 64, and 128
- Total proxy sessions: 3, 6, 12, 24, 48, 96, 192, and 384

Aggregate sweep:

| Connections per target | Total sessions | Exchanges | Group ex/s | vs 1x | Raw B/ex | AIWire B/ex | Saved | Capacity gain | p95 max |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 3 | 4,076 | 67.9 | 1.00x | 2,311.7 | 363.6 | 84.3% | 6.36x | 47.92 ms |
| 2 | 6 | 8,150 | 135.8 | 2.00x | 2,348.0 | 366.7 | 84.4% | 6.40x | 47.92 ms |
| 4 | 12 | 16,283 | 271.2 | 3.99x | 2,348.1 | 366.7 | 84.4% | 6.40x | 47.92 ms |
| 8 | 24 | 32,450 | 540.3 | 7.96x | 2,347.5 | 366.8 | 84.4% | 6.40x | 48.16 ms |
| 16 | 48 | 64,914 | 1,080.6 | 15.91x | 2,347.6 | 366.8 | 84.4% | 6.40x | 48.13 ms |
| 32 | 96 | 128,739 | 2,142.2 | 31.55x | 2,347.3 | 366.6 | 84.4% | 6.40x | 48.61 ms |
| 64 | 192 | 229,223 | 3,802.8 | 56.01x | 2,347.5 | 366.8 | 84.4% | 6.40x | 59.81 ms |
| 128 | 384 | 161,648 | 2,562.6 | 37.74x | 2,347.3 | 368.1 | 84.3% | 6.38x | 223.18 ms |

Interpretation:

- Connection sharding scaled useful message movement almost linearly through
  thirty-two sessions per target for this LAN sidecar shape, and continued
  improving through sixty-four sessions per target with a modest tail-latency
  increase.
- One hundred twenty-eight sessions per target is past the useful knee for this
  setup. The run still verified, and per-exchange bytes stayed stable, but
  throughput fell below the 64x run and p95 climbed to 223.18 ms.
- The per-exchange byte profile stayed stable, which is what AURA wants from a
  bandwidth-proportional tunnel: more lanes move more deltas without inflating
  each exchange.
- The p95 latency ceiling stayed effectively flat through 96 total proxy
  sessions, rose modestly at 192 sessions, and broke at 384 sessions. That
  points to scheduler, socket, or sidecar contention rather than AIWire byte
  inflation as the first visible limit in this test shape.

The 16x and 32x measurements were produced with `--connections-sweep 16,32`,
which runs multiple connection levels sequentially and emits one combined JSON
report plus one markdown summary. The 64x and 128x measurements used the same
runner path with `--connections-sweep 64,128`.

This run still uses public fixture traffic and a modeled 10 Mbps capacity view.
It is not a production workload replay or a throttled WAN test.
