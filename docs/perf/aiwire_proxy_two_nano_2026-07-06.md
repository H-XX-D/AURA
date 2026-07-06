# AIWire Explicit Proxy Two-Edge Run

Date: 2026-07-06

This run extended the explicit AIWire sidecar proxy from one Jetson Orin
Nano-class edge target to two reachable Nano-class edge targets on the same LAN.
The coordinator ran the ingress/client half from the Mac. Each edge target ran
the fixture responder and egress sidecar from its own `AURA` checkout with the
native AIWire backend built locally.

The path for each target was:

```text
coordinator client -> coordinator ingress -> LAN -> edge egress -> edge fixture upstream
```

The two-edge run also validates the SSH orchestrator's per-target
`remote_root` option. The real lab used different SSH users and checkout paths,
so the runner had to support target-local roots instead of assuming every edge
machine used the same home directory.

## Readiness

Both edge targets passed:

- SSH config resolution
- SSH TCP reachability
- batch-mode SSH authentication
- remote AURA import
- fixture corpus presence
- native AIWire backend readiness

Native backend status on both targets:

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
- target parallelism: 2
- fixture/egress connections: 1 per target

Aggregate result:

| Targets | Exchanges | Group ex/s | Raw B/ex | AIWire B/ex | Saved | p95 max | p99 max | Verified |
|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 2 | 2,709 | 45.1 | 2,322.4 | 364.2 | 84.3% | 47.98 ms | 48.26 ms | 2/2 |

Per-target result:

| Target | Exchanges | Ex/s | Raw B/ex | AIWire B/ex | Saved | p50 | p95 | p99 | Verified |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| edge A | 1,355 | 22.6 | 2,314.5 | 363.0 | 84.3% | 44.01 ms | 47.97 ms | 48.21 ms | true |
| edge B | 1,354 | 22.6 | 2,330.4 | 365.4 | 84.3% | 44.01 ms | 47.98 ms | 48.26 ms | true |

Aggregate modeled bandwidth:

| Metric | Value |
|---|---:|
| Raw framed bytes | 6,291,462 |
| AIWire semantic framed bytes | 986,612 |
| Control framed bytes | 2,896 |
| Semantic bandwidth capacity gain | 6.38x |

The important result is that adding a second edge target scaled the current
single-connection sidecar path almost linearly at the completed-exchange level:
about 22.6 exchanges/second per target and 45.1 exchanges/second as a group.
The byte result stayed stable as well: sustained handshaked AIWire deltas moved
about 84% fewer semantic bytes than raw framed JSON on both targets.

This still does not fill the modeled 10 Mbps links. The run confirms the
sidecar proxy preserves bandwidth-proportional byte movement across multiple
edge targets, while the current request/response loop remains the throughput
limit.

## Smoke Result

Before the 60-second run, a two-target 32-exchange-per-target smoke passed:

| Targets | Exchanges | Group ex/s | Raw B/ex | AIWire B/ex | Saved | p95 max | Verified |
|---:|---:|---:|---:|---:|---:|---:|---|
| 2 | 64 | 45.2 | 2,325.8 | 402.9 | 82.7% | 48.09 ms | 2/2 |

## Cleanup

After the run, both edge targets had no remaining proxy fixture processes and no
listeners on the benchmark egress or upstream ports.

## Artifacts

Local run artifacts:

- `/tmp/two-nano-proxy-preflight-20260706T212827Z.md`
- `/tmp/two-nano-proxy-smoke-20260706T212836Z.md`
- `/tmp/two-nano-proxy-60s-20260706T212848Z.md`
- `/tmp/two-nano-proxy-60s-20260706T212848Z.json`

These artifacts are machine-local and are not committed because they include
deployment-specific labels, addresses, and paths.
