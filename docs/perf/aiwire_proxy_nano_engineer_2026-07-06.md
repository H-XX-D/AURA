# AIWire Explicit Proxy Nano Edge Run

Date: 2026-07-06

This run exercised the explicit AIWire sidecar proxy over a real LAN hop to one
Jetson Orin Nano-class edge target. The coordinator ran the ingress/client half
from the Mac. The edge target ran the fixture responder and egress sidecar from
a fresh `~/AURA` checkout with the native AIWire backend built locally.

The path was:

```text
coordinator client -> coordinator ingress -> LAN -> edge egress -> edge fixture upstream
```

## Readiness

The edge target passed:

- SSH config resolution
- SSH TCP reachability
- batch-mode SSH authentication
- remote AURA import
- fixture corpus presence
- native AIWire backend readiness

Native backend check on the edge target:

| Field | Value |
|---|---:|
| Platform | Linux aarch64 |
| Python | 3.10.12 |
| Native backend | `aura-aiwire-native-cpp/3` |
| Dictionary bytes | 32,768 |
| Dictionary checksum | `94dd21718372952e` |
| Native roundtrip frames | 64 |
| Native roundtrip ratio | 5.01x |

## 60-Second Result

Run settings:

- backend: `native`
- fixture variation profile: `cluster`
- duration: 60 seconds
- modeled link: 10 Mbps
- target parallelism: 1
- fixture/egress connections: 1

| Target | Exchanges | Ex/s | Raw B/ex | AIWire B/ex | Saved | p50 | p95 | p99 | Verified |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| one Nano-class edge | 1,358 | 22.6 | 2,345.4 | 367.0 | 84.4% | 44.01 ms | 46.29 ms | 48.21 ms | true |

Aggregate modeled bandwidth:

| Metric | Value |
|---|---:|
| Raw framed bytes | 3,185,007 |
| AIWire semantic framed bytes | 498,387 |
| Control framed bytes | 1,448 |
| Semantic bandwidth capacity gain | 6.39x |
| Modeled raw capacity | 533.0 ex/s |
| Modeled AIWire capacity | 3,406.0 ex/s |

The important result is byte movement. The live sidecar path preserved the same
direction seen in local proxy tests: sustained handshaked AIWire deltas moved
about one-sixth of the semantic bytes that raw frames would have moved. The
completed exchange rate was limited by the current single-connection
request/response loop and LAN/edge runtime path, not by modeled 10 Mbps link
capacity.

## Smoke Result

Before the 60-second run, a 32-exchange smoke passed:

| Exchanges | Ex/s | Raw B/ex | AIWire B/ex | Saved | p95 | Verified |
|---:|---:|---:|---:|---:|---:|---|
| 32 | 22.7 | 2,348.7 | 405.4 | 82.7% | 47.93 ms | true |

## Artifacts

Local run artifacts:

- `/tmp/nano-engineer-proxy-preflight-20260706T211744Z.md`
- `/tmp/nano-engineer-proxy-smoke-20260706T211954Z.md`
- `/tmp/nano-engineer-proxy-60s-20260706T212015Z.md`
- `/tmp/nano-engineer-proxy-60s-20260706T212015Z.json`

These artifacts are machine-local and are not committed because they include
deployment-specific host labels and paths.
