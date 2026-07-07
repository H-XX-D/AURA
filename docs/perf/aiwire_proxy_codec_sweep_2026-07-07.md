# AIWire Proxy Codec Sweep

This run compares `raw`, `zlib`, and `aiwire` inside the same explicit sidecar
proxy shape. The local applications still exchange raw length-prefixed agent
frames. Only the semantic payload inside the inter-sidecar tunnel changes codec,
so the result isolates payload codec behavior from sidecar framing, connection
count, fixture shape, and deterministic tunnel impairment.

Run shape:

- Coordinator: local Z6-class machine
- Edge shape: 3 ready LAN targets
- Backend: `native`
- Fixture variation profile: `cluster`
- Duration: 60 seconds per codec
- Connections per target: 64
- Total proxy sessions: 192
- Tunnel codecs: `raw`, `zlib`, `aiwire`
- Tunnel impairment per target direction: 6 Mbps, 12 ms one-way delay, 8 ms
  jitter, 2.5% tail pauses up to 120 ms
- Run ID: `edge-mesh-codec-64-60s-20260706-225504`

Command shape:

```bash
python tools/run_aiwire_proxy_cluster.py \
  --targets-file /tmp/aura-ready-targets.txt \
  --preflight --run --seconds 60 \
  --connections 64 \
  --tunnel-codec-sweep raw,zlib,aiwire \
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

| Codec | Total sessions | Verified | Exchanges | Group ex/s | vs raw | Raw B/ex | Tunnel B/ex | Saved | Capacity gain | p95 max | Raw-equivalent Mbps | Tunnel Mbps |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `raw` | 192 | 3/3 | 114,681 | 1,905.9 | 1.00x | 2,347.8 | 2,349.8 | -0.1% | 1.00x | 118.85 ms | 35.79 | 35.82 |
| `zlib` | 192 | 3/3 | 165,463 | 2,750.3 | 1.44x | 2,347.7 | 1,218.1 | 48.1% | 1.93x | 88.54 ms | 51.65 | 26.80 |
| `aiwire` | 192 | 3/3 | 164,436 | 2,731.3 | 1.43x | 2,348.0 | 367.1 | 84.4% | 6.40x | 86.39 ms | 51.31 | 8.02 |

Interpretation:

- Raw is the control: it verified correctly, but the sidecar tunnel moved the
  whole JSON-shaped frame plus the proxy lane tag, so it used slightly more
  tunnel bytes than raw application framing and had the worst p95 tail.
- zlib cut tunnel bytes by 48.1% and raised verified exchange rate by 1.44x
  over raw in this sidecar shape.
- AIWire matched zlib's useful exchange rate within this run's sidecar and CPU
  limits, but moved only 367.1 tunnel bytes per exchange instead of 1,218.1 for
  zlib. That is 3.32x less tunnel traffic than zlib and 6.40x less than raw.
- The current bottleneck at 64 connections per target is no longer AIWire wire
  bytes. The next limiter is sidecar/runtime scheduling, socket work, fixture
  verification, or native/Python boundary overhead.
- The practical benefit remains bandwidth headroom. At the same useful
  raw-equivalent movement of about 51 Mbps across the three target groups,
  AIWire consumed about 8 Mbps of semantic tunnel traffic while zlib consumed
  about 26.8 Mbps.

This is a benchmark harness, not production traffic shaping. The impairment is
applied in the sidecar write path so the comparison is deterministic and does
not need privileged network configuration.

## Stage Profile Follow-up

After the sweep above, the proxy metrics were extended with per-stage timing and
impairment wait accounting. A shorter 20-second-per-codec follow-up used the
same three ready edge targets, native backend, 64 connections per target, and
the same 6 Mbps plus latency/jitter/tail impairment model.

- Run ID: `edge-mesh-profile-64-20s-20260706-231342`
- Commit: `1b3b84a`
- Duration: 20 seconds per codec
- Total proxy sessions: 192
- Verified targets: 3/3 for every codec

Aggregate result:

| Codec | Total sessions | Verified | Exchanges | Group ex/s | vs raw | Raw B/ex | Tunnel B/ex | Saved | Capacity gain | p95 max |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `raw` | 192 | 3/3 | 38,156 | 1,890.0 | 1.00x | 2,348.0 | 2,350.0 | -0.1% | 1.00x | 123.05 ms |
| `zlib` | 192 | 3/3 | 55,301 | 2,741.5 | 1.45x | 2,347.3 | 1,217.9 | 48.1% | 1.93x | 89.13 ms |
| `aiwire` | 192 | 3/3 | 54,912 | 2,712.8 | 1.44x | 2,348.0 | 369.2 | 84.3% | 6.36x | 87.20 ms |

Top stage means:

| Codec | Role | Stage | Calls | Total s | Mean ms |
|---|---|---|---:|---:|---:|
| `raw` | ingress | `tunnel_request_write` | 38,156 | 1,949.254 | 51.086 |
| `raw` | egress | `tunnel_response_write` | 38,156 | 1,852.015 | 48.538 |
| `zlib` | ingress | `tunnel_request_write` | 55,301 | 955.483 | 17.278 |
| `zlib` | egress | `tunnel_response_write` | 55,301 | 903.587 | 16.339 |
| `zlib` | egress | `response_encode` | 55,301 | 11.968 | 0.216 |
| `aiwire` | ingress | `tunnel_request_write` | 54,912 | 877.776 | 15.985 |
| `aiwire` | egress | `tunnel_response_write` | 54,912 | 786.707 | 14.327 |
| `aiwire` | egress | `response_encode` | 54,912 | 16.592 | 0.302 |

Stage totals are summed across concurrent sessions, so they can exceed wall
clock time. The mean milliseconds per call are the per-exchange signal.

Interpretation:

- AIWire's semantic tunnel bytes stayed about 3.30x smaller than zlib and 6.36x
  smaller than raw in the same sidecar path.
- AIWire write-stage means were lower than zlib's, but not 3.30x lower because
  the impairment model includes fixed per-frame latency, jitter, and tail pause
  components in addition to serialization time.
- AIWire encode/decode cost was not the bottleneck in this run: egress response
  encode averaged 0.302 ms per exchange and ingress response decode averaged
  0.039 ms per exchange.
- The dominant remaining stages after compression were response-path waits:
  ingress `tunnel_response_read` and egress `upstream_response_read`. That points
  the next optimization at proxy scheduling, fixture/upstream response handling,
  and concurrent socket coordination rather than the AIWire codec itself.

Follow-up: the inline fixture isolation run removed the benchmark fixture TCP hop
and raised the same 192-session impaired AIWire shape from 2,731.5 to 3,909.9
exchanges/s while preserving 84.4% semantic-byte savings. See
[AIWire Proxy Inline Fixture Isolation](aiwire_proxy_inline_fixture_2026-07-07.md).
