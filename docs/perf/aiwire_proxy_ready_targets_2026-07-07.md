# AIWire Proxy Ready-Targets Run

Date: 2026-07-07

This run validated the mixed-lab readiness workflow for the explicit AIWire
sidecar proxy. The coordinator started from a configured six-target lab shape,
ran fail-closed preflight across all targets, wrote a generated ready-only
targets file, then ran the sustained proxy benchmark against only the machines
that passed readiness.

The path for each included target remained:

```text
coordinator client -> coordinator ingress -> LAN -> edge egress -> edge fixture upstream
```

## Readiness Split

The mixed preflight checked six configured edge targets:

| Status | Count | Meaning |
|---|---:|---|
| Ready | 3 | SSH config, SSH TCP, batch auth, remote import, fixture corpus, and native backend all passed |
| SSH auth blocked | 2 | SSH port was reachable, but batch key authentication failed |
| SSH TCP blocked | 1 | SSH endpoint did not answer from the coordinator |

The generated ready-only targets file contained 3 of 6 targets. The strict
all-target preflight still failed closed; the ready-only file made the runnable
subset explicit for smoke and sustained benchmark runs.

## 60-Second Result

Run settings:

- backend: `native`
- fixture variation profile: `cluster`
- duration: 60 seconds
- modeled link: 10 Mbps per target
- target parallelism: 4
- fixture/egress connections: 1 per target
- source target set: generated ready-only targets file from mixed preflight

Aggregate result:

| Targets | Exchanges | Group ex/s | Raw B/ex | AIWire B/ex | Saved | Capacity gain | p95 max | p99 max | Verified |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 3 | 4,076 | 67.9 | 2,311.7 | 363.6 | 84.3% | 6.36x | 47.92 ms | 48.27 ms | 3/3 |

Per-target result:

| Target | Exchanges | Ex/s | Raw B/ex | AIWire B/ex | Saved | p50 | p95 | p99 | Verified |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| edge A | 1,355 | 22.6 | 2,314.5 | 363.0 | 84.3% | 44.02 ms | 47.92 ms | 48.26 ms | true |
| edge B | 1,364 | 22.7 | 2,290.6 | 362.4 | 84.2% | 44.00 ms | 44.38 ms | 44.77 ms | true |
| edge C | 1,357 | 22.6 | 2,330.2 | 365.5 | 84.3% | 44.01 ms | 47.74 ms | 48.27 ms | true |

Aggregate modeled bandwidth:

| Metric | Value |
|---|---:|
| Raw framed bytes | 9,422,559 |
| AIWire semantic framed bytes | 1,482,236 |
| Control framed bytes | 4,344 |
| Semantic bandwidth capacity gain | 6.36x |

## Interpretation

The useful result is operational rather than a new throughput ceiling. The
ready-only run reproduced the earlier three-edge sidecar shape: roughly 22.6
completed exchanges/second per target, about 84% fewer semantic bytes than raw
framed JSON, and stable p95 latency under 48 ms.

That means the readiness workflow can keep a larger desired cluster visible
without blocking progress on machines that are already prepared. Strict
all-target runs still fail if any configured target is not ready; generated
ready-only runs are an explicit, auditable subset.

The remaining performance limit is unchanged. The current sidecar benchmark
uses one request/response connection per edge target, so it does not fill the
modeled 10 Mbps links after AIWire reduces frame size. More useful next work is
multi-connection sidecar concurrency or a native coordinator/server loop, not
more dictionary tuning.

## Cleanup

After the run, all included edge targets had no remaining proxy fixture
processes from the benchmark.

## Artifacts

Local run artifacts:

- `/tmp/aura-mixed-readiness-20260707T010201Z.md`
- `/tmp/aura-mixed-readiness-20260707T010201Z.json`
- `/tmp/aura-ready-targets-20260707T010201Z.txt`
- `/tmp/aura-ready-60s-20260707T010217Z.md`
- `/tmp/aura-ready-60s-20260707T010217Z.json`

These artifacts are machine-local and are not committed because they include
deployment-specific labels, addresses, users, and paths.
