# AIWire Proxy Upstream Agent Profile

This run adds deterministic benchmark-only upstream work to the explicit
AIWire proxy benchmark. The goal is to test the sustained-handshake path when
the upstream is no longer an instant fixture responder.

The `edge-mixed` profile sleeps before each fixture response with a small
per-exchange delay plus deterministic tail pauses. It is not a protocol change:
normal `aura-proxy egress --upstream-host ...` forwarding is unchanged.

## Run Shape

- Date: 2026-07-07
- Targets: 3 ready edge targets
- Sessions: 64 connections per target, 192 total proxy sessions
- Duration: 60 seconds per pass
- Backend: native
- Tunnel codec: AIWire
- Fixture variation: cluster
- Upstream agent profile: `edge-mixed`
- Upstream agent seed: 99
- Tunnel impairment per sidecar: 6 Mbps, 12 ms one-way delay, 8 ms jitter,
  2.5% tail pauses up to 120 ms, seed 1729

Baseline command shape:

```bash
python tools/run_aiwire_proxy_cluster.py \
  --targets-file /tmp/aura-ready-targets.txt \
  --run --seconds 60 --connections 64 \
  --tunnel-codec aiwire --backend native \
  --fixture-variation-profile cluster \
  --upstream-agent-profile edge-mixed \
  --upstream-agent-seed 99 \
  --target-parallelism 3 \
  --modeled-link-mbps 6 \
  --tunnel-bandwidth-mbps 6 \
  --tunnel-one-way-delay-ms 12 \
  --tunnel-jitter-ms 8 \
  --tunnel-tail-pause-probability 0.025 \
  --tunnel-tail-pause-ms 120 \
  --impairment-seed 1729
```

The isolation pass added:

```bash
--inline-upstream-fixture
```

## Results

| Upstream mode | Verified | Exchanges | Group ex/s | Raw B/ex | Tunnel B/ex | Saved | Raw-equivalent Mbps | Tunnel Mbps | p95 max |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Remote TCP fixture + `edge-mixed` | 3/3 | 155,577 | 2,583.3 | 2,347.7 | 367.2 | 84.4% | 48.70 | 7.62 | 98.22 ms |
| Inline fixture + `edge-mixed` | 3/3 | 256,567 | 4,259.6 | 2,347.6 | 366.7 | 84.4% | 80.31 | 12.54 | 70.49 ms |

The inline run moved 64.9% more verified exchanges per second and lowered max
p95 by 28.2%, while byte shape stayed the same. The sustained-handshake
benefit held: about 80.3 Mbps of raw-JSON-equivalent movement was represented
by about 12.5 Mbps of AIWire semantic tunnel bytes across the three target
groups.

## Stage Profile

| Upstream mode | Stage | Mean ms |
|---|---|---:|
| Remote TCP fixture + `edge-mixed` | egress `upstream_response_read` | 42.744 |
| Remote TCP fixture + `edge-mixed` | egress `response_encode` | 0.307 |
| Remote TCP fixture + `edge-mixed` | egress `tunnel_response_write` | 14.227 |
| Remote TCP fixture + `edge-mixed` | ingress `tunnel_response_read` | 58.137 |
| Inline fixture + `edge-mixed` | egress `upstream_response_inline` | 3.921 |
| Inline fixture + `edge-mixed` | egress `response_encode` | 0.171 |
| Inline fixture + `edge-mixed` | egress `tunnel_response_write` | 14.036 |
| Inline fixture + `edge-mixed` | ingress `tunnel_response_read` | 20.195 |

`edge-mixed` makes the upstream work visible: inline egress spent about 3.9 ms
per response inside `upstream_response_inline`. The TCP fixture path still
spends much more time in `upstream_response_read`, which includes both the
simulated work and the extra upstream socket scheduling.

## Interpretation

This profile makes the benchmark closer to a real local-agent service without
changing the production proxy path. The result supports the same conclusion as
the inline fixture isolation run, but under less ideal conditions: AIWire's
bytes stay small, and once whole-frame movement is removed from the constrained
hop, the next bottlenecks are application response behavior and sidecar socket
scheduling.

One important wrinkle: the inline `edge-mixed` run was faster than the earlier
instant inline fixture pass. That can happen because small deterministic
upstream waits reduce burst contention across 192 concurrent sessions. Treat
this as a scheduling signal, not a codec speedup claim.
