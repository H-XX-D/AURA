# AIWire Proxy Inline Fixture Isolation

This run isolates the explicit AIWire sidecar tunnel from the benchmark's raw
fixture TCP hop. The normal production `aura-proxy egress --upstream-host ...`
path still forwards to a real upstream socket. The new inline mode is
benchmark-only and lets the egress sidecar answer from the same public fixture
corpus in process.

## Run Shape

- Date: 2026-07-07
- Targets: 3 ready edge targets
- Sessions: 64 connections per target, 192 total proxy sessions
- Duration: 60 seconds per pass
- Backend: native
- Tunnel codec: AIWire
- Fixture variation: cluster
- Tunnel impairment per sidecar: 6 Mbps, 12 ms one-way delay, 8 ms jitter,
  2.5% tail pauses up to 120 ms, seed 1729

The baseline pass used the existing remote raw fixture server:

```bash
python tools/run_aiwire_proxy_cluster.py \
  --targets-file /tmp/aura-ready-targets.txt \
  --run --seconds 60 --connections 64 \
  --tunnel-codec aiwire --backend native \
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

The isolation pass added:

```bash
--inline-upstream-fixture
```

## Results

| Upstream mode | Verified | Exchanges | Group ex/s | Raw B/ex | Tunnel B/ex | Saved | Raw-equivalent Mbps | Tunnel Mbps | p95 max |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Remote TCP fixture | 3/3 | 164,416 | 2,731.5 | 2,348.1 | 367.1 | 84.4% | 51.47 | 8.05 | 86.27 ms |
| Inline fixture | 3/3 | 235,705 | 3,909.9 | 2,347.7 | 366.8 | 84.4% | 73.78 | 11.53 | 71.39 ms |

Inline fixture mode moved 43.1% more verified exchanges per second and reduced
max p95 by 17.3% while keeping the per-exchange byte shape effectively
unchanged. That means the prior 64-connection AIWire sidecar ceiling was
substantially affected by the local raw fixture TCP hop, not by AIWire's
semantic encoder.

## Stage Profile

| Upstream mode | Stage | Mean ms |
|---|---|---:|
| Remote TCP fixture | egress `upstream_response_read` | 38.643 |
| Remote TCP fixture | egress `response_encode` | 0.311 |
| Remote TCP fixture | egress `tunnel_response_write` | 14.227 |
| Remote TCP fixture | ingress `tunnel_response_read` | 54.147 |
| Inline fixture | egress `upstream_response_inline` | 0.004 |
| Inline fixture | egress `response_encode` | 0.158 |
| Inline fixture | egress `tunnel_response_write` | 14.021 |
| Inline fixture | ingress `tunnel_response_read` | 17.551 |

The inline pass removes the egress `connect_upstream`,
`upstream_request_write`, and `upstream_response_read` stages from the hot path.
The AIWire response encode stage remained sub-millisecond. The dominant
remaining time is tunnel scheduling, modeled impairment wait, and concurrent
client-side socket coordination.

## Interpretation

This is useful for AURA because the value proposition is sustained handshakes
where agents exchange deltas, control metadata, and recurring structures by
address instead of repeatedly moving whole JSON frames. With inline fixture
isolation, the same 84.4% tunnel-byte reduction supported about 73.8 Mbps of
raw-JSON-equivalent movement in about 11.5 Mbps of AIWire semantic tunnel bytes
across the three target groups.

The next measurement target should be a real local-agent upstream, not the
fixture harness. The fixture isolation result says AIWire has more headroom than
the previous sidecar fixture benchmark exposed; the next bottleneck to measure
is application upstream behavior and sidecar socket scheduling under realistic
agent work.
