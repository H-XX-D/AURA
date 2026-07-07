# AIWire Explicit Proxy Three-Edge Run

Date: 2026-07-06

This run extended the explicit AIWire sidecar proxy to three reachable Jetson
Orin Nano-class edge targets on the same LAN. The coordinator ran the
ingress/client half from the Mac. Each edge target ran the fixture responder and
egress sidecar from its own `AURA` checkout with the native AIWire backend built
locally.

The path for each target was:

```text
coordinator client -> coordinator ingress -> LAN -> edge egress -> edge fixture upstream
```

## Readiness

All three edge targets passed:

- SSH config resolution
- SSH TCP reachability
- batch-mode SSH authentication
- remote AURA import
- fixture corpus presence
- native AIWire backend readiness

One additional configured edge target was reachable on SSH but did not accept
the configured public key. Another configured edge target did not answer on the
LAN. Those targets were excluded from this measured run; dry-run bootstrap
reports were generated locally for the key-auth cases.

Native backend status on all included targets:

| Field | Value |
|---|---:|
| Platform | Linux aarch64 |
| Python | 3.10.12 |
| Native backend | `aura-aiwire-native-cpp/3` |
| Dictionary bytes | 32,768 |
| Dictionary checksum | `94dd21718372952e` |
| Dictionary matched Python | true |

## 60-Second Result

Run settings:

- backend: `native`
- fixture variation profile: `cluster`
- duration: 60 seconds
- modeled link: 10 Mbps per target
- target parallelism: 3
- fixture/egress connections: 1 per target

Aggregate result:

| Targets | Exchanges | Group ex/s | Raw B/ex | AIWire B/ex | Saved | Capacity gain | p95 max | p99 max | Verified |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 3 | 4,075 | 67.9 | 2,311.8 | 363.6 | 84.3% | 6.36x | 47.98 ms | 48.33 ms | 3/3 |

Per-target result:

| Target | Exchanges | Ex/s | Raw B/ex | AIWire B/ex | Saved | p50 | p95 | p99 | Verified |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| edge A | 1,357 | 22.6 | 2,314.5 | 363.1 | 84.3% | 44.01 ms | 47.66 ms | 48.30 ms | true |
| edge B | 1,364 | 22.7 | 2,290.6 | 362.4 | 84.2% | 43.99 ms | 44.48 ms | 45.01 ms | true |
| edge C | 1,354 | 22.6 | 2,330.4 | 365.4 | 84.3% | 44.01 ms | 47.98 ms | 48.33 ms | true |

Aggregate modeled bandwidth:

| Metric | Value |
|---|---:|
| Raw framed bytes | 9,420,445 |
| AIWire semantic framed bytes | 1,481,770 |
| Control framed bytes | 4,344 |
| Semantic bandwidth capacity gain | 6.36x |

The important result is linearity of the current sidecar shape. The one-edge,
two-edge, and three-edge explicit proxy runs all land at roughly 22.6 completed
exchanges/second per target with about 84% fewer semantic bytes than raw framed
JSON. Adding the third edge target increased group throughput to 67.9
exchanges/second while preserving the same sustained-handshake byte movement.

This still does not fill the modeled 10 Mbps links. The bottleneck remains the
single-connection request/response loop and Python sidecar orchestration, not
semantic bytes on the wire.

## Smoke Result

Before the 60-second run, a three-target 32-exchange-per-target smoke passed:

| Targets | Exchanges | Group ex/s | Raw B/ex | AIWire B/ex | Saved | p95 max | Verified |
|---:|---:|---:|---:|---:|---:|---:|---|
| 3 | 96 | 68.8 | 2,315.2 | 402.1 | 82.6% | 48.45 ms | 3/3 |

## Cleanup

After the run, all included edge targets had no remaining proxy fixture
processes and no listeners on the benchmark egress or upstream ports.

## Artifacts

Local run artifacts:

- `/tmp/three-nano-proxy-preflight-20260706T235746Z.md`
- `/tmp/three-nano-proxy-smoke-20260706T235756Z.md`
- `/tmp/three-nano-proxy-60s-20260706T235807Z.md`
- `/tmp/three-nano-proxy-60s-20260706T235807Z.json`

These artifacts are machine-local and are not committed because they include
deployment-specific labels, addresses, and paths.
