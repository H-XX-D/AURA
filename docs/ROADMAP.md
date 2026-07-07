# AURA Roadmap

This roadmap prioritizes the path that currently has the clearest evidence:
AIWire for handshaked structure and delta movement in high-volume AI-to-AI
messages.

## North Star

AURA should make structured agent traffic cheaper to move across normal
networks without requiring a special transport. Peers handshake the stable
structure first, then move changes against that shared session state instead of
whole frames whenever possible.

The practical target is:

```text
more AI messages per second
less bandwidth per conversation
lower tail latency under bandwidth pressure
reproducible round trips
clear fallback when peers cannot negotiate AIWire
clean resync when peers lose structural state
```

## Phase 1: Public Baseline

Goal: make the repo understandable and reproducible from a fresh clone.

Status: complete and maintained.

- Keep `README.md`, `docs/architecture.md`, and this roadmap aligned around
  the AI-to-AI use case.
- Keep benchmark reports public-safe and free of host-specific private details.
- Document the exact benchmark commands for local LAN reproduction.
- Keep `tests/test_ai_wire.py` as the fast correctness gate.
- Add small examples for raw TCP and WebSocket frame transport.
- Publish a clear "what this is good for / not good for" section.

Definition of done:

- A new developer can install the repo, run the AIWire tests, and run a local
  client/server benchmark without reading private notes.

## Phase 2: AIWire v1 Hardening

Goal: freeze the minimum protocol contract.

Status: complete and maintained by the fast AIWire gate.

- Keep the AIWire v1 handshake, side-channel, and delta-frame spec aligned with
  implementation and tests.
- Define handshake fields, template update signals, accepted fallback behavior,
  resync behavior, and failure modes.
- Keep cross-version dictionary compatibility tests in the fast AIWire gate.
- Keep corrupted-frame and truncated-frame tests in the fast AIWire gate.
- Keep TCP partial-frame read/write tests and interrupted delta-state tests in
  the fast AIWire gate.
- Keep negotiated fallback tests for `raw` and `zlib` in the fast AIWire gate.
- Keep stable stats serialization in the fast AIWire gate for benchmark
  comparison over time.
- Keep n-ary handshake negotiation fail-closed so multi-agent sessions share
  one codec, dictionary, template, and control-LUT contract.

Definition of done:

- AIWire v1 can be implemented by another language/runtime from the spec and
  interoperate with the Python tests.

## Phase 3: Better Message Corpora

Goal: benchmark against realistic protocol-shaped data.

Status: complete and maintained with deterministic corpora, local benchmark
profiles, corpus summaries, public-safe metadata, and CI smoke thresholds.

- Expand the generated corpus for MCP requests, MCP responses, A2A tasks,
  OpenAI tool calls, structured outputs, traces, reviews, and memory writes.
- Keep generated delta-shaped corpora where the task/session/template is stable
  and only status, token, argument, artifact, route, or trace values change.
- Keep current corpus variants aligned with public protocol shapes and mark
  benchmark traffic with synthetic, public-safe corpus metadata.
- Keep saved fixture corpora deterministic, public-safe, and side-channel
  complete. The first AIWire session fixture is
  [`fixtures/aiwire_sessions/public_session_corpus_v1.json`](../fixtures/aiwire_sessions/public_session_corpus_v1.json).
- Keep stable corpus summaries for size, average frame size, key distribution,
  protocol mix, and delta value mix.
- Keep local benchmark profiles for small, medium, and bursty message sizes.
- Keep CI-friendly benchmark smoke tests that detect major regressions without
  requiring a full LAN lab.
- Keep sustained-session benchmark mode separate from one-shot frame tests:
  setup and template handshakes are counted once, while steady-state delta bytes
  are measured over time.
- Keep the fixture-backed saturation benchmark current so bandwidth, latency,
  CPU ceiling, and concurrent-agent requirements are measured on the same
  public corpus.

Definition of done:

- Benchmark numbers can be compared across commits and across machines with a
  known corpus.

## Phase 4: Native and Edge Performance

Goal: make AIWire fast on workstation and ARM64 edge targets.

Status: active. The package benchmark CLI and live TCP/n-ary stress harness now
expose `--backend python|native|auto`, so Python/native comparisons can use the
same corpus, link model, and result schema. A native AIWire build/check utility
now verifies `libaura_aiwire` dictionary identity, Python/native interop, and
native token paths on each machine before cluster runs.

- Make native backend builds reproducible on macOS, Linux x86_64, and Linux
  ARM64. `tools/check_aiwire_native_backend.py --build --require-native` is the
  shared gate for workstations and edge targets.
- Verify Python/native interoperability in CI where possible. Linux and macOS
  Actions now build the C++ native backend and run the native check utility.
- Keep the package benchmark CLI wired to `--backend python|native|auto` so
  Python/native comparisons use the same corpus and output schema.
- Use `tools/compare_aiwire_backends.py` to produce one repeatable
  Python-vs-native artifact across the sustained-session benchmark and
  fixture-backed saturation model before running LAN or n-ary cluster tests.
- Keep the live TCP and n-ary stress harness wired to
  `--backend python|native|auto` so cross-machine cluster tests report both the
  requested backend and the actual encode/decode backend.
- Profile Jetson Nano-class CPUs and remove avoidable Python overhead.
  `tools/profile_aiwire_hot_path.py` now emits JSON/Markdown cProfile artifacts
  for the sustained-session setup path and fixture codec path so Z6/Jetson runs
  can identify whether time is in template discovery, JSON encoding, zlib, or
  native boundary work before async/native rewrites.
- Keep session/connection sharding in the n-ary benchmark harness as a
  measurement tool. Corrected thread and forked-process server sharding both
  regressed throughput and tail latency, so they are diagnostics rather than
  the performance path.
- Keep the opt-in asyncio coordinator loop in the live TCP/n-ary stress harness
  (`--coordinator asyncio`) as the next measurement path for occupying AIWire's
  saved-bandwidth headroom without client thread-pool contention.
  `tools/compare_aiwire_coordinators.py` now produces JSON/Markdown artifacts
  for threaded-vs-asyncio n-ary fixture replay on the same link model.
- Use the asyncio coordinator with the native backend on Z6/Jetson runs before
  committing to a deeper native coordinator/server rewrite.
- Keep `tools/run_aiwire_network_suite.py` wired to `--backend` and
  `--coordinator` so realistic-profile sweeps can exercise native AIWire and
  the asyncio coordinator without hand-written stress commands.
- The 2026-07-06 local native/asyncio realistic-profile run shows native AIWire
  saturating the modeled links at 95.7-99.9% utilization and 6.19-6.40x raw
  exchange rate. AIToken+AIWire reaches 7.43-14.97x raw and 95.3% byte savings
  but still leaves bandwidth headroom at 64 agents.
- Keep raw, stateless zlib, and native AIWire sidecar codec sweeps under the
  same link model. The 2026-07-07 impaired proxy sweep shows AIWire matching
  zlib's useful exchange rate in the current sidecar shape while using 367.1
  tunnel bytes per exchange versus zlib's 1,218.1.
- Keep sidecar stage profiling in the proxy benchmark output. The follow-up
  profile shows AIWire encode/decode staying sub-millisecond per exchange while
  response-path waits and fixed per-frame latency dominate at 64 connections per
  target. The inline-fixture isolation run then removed the benchmark's raw
  fixture TCP hop and raised the same impaired 192-session AIWire pass from
  2,731.5 to 3,909.9 exchanges/s with byte savings unchanged at 84.4%, so the
  next sidecar target is realistic upstream-agent behavior and socket scheduling
  rather than the codec hot path. The first `edge-mixed` upstream-agent profile
  pass kept AIWire at 84.4% byte savings; TCP fixture mode moved 2,583.3
  exchanges/s and inline fixture mode moved 4,259.6 exchanges/s, confirming the
  constrained-hop byte advantage persists when responses are not instant.

Definition of done:

- ARM64 edge targets get a measurable AIWire throughput improvement over the
  Python path while preserving byte-for-byte round trips.

## Phase 5: Transport Examples

Goal: show how AIWire fits into normal network stacks.

Status: complete and maintained. Transport examples exist for TCP, WebSocket,
HTTP streaming, local broker use, deterministic replay-log audit capture, and
an explicit TCP sidecar proxy for raw length-prefixed agent frames over an
AIWire tunnel. The sidecar path now has an end-to-end local benchmark harness
and an SSH-managed cross-machine benchmark runner, cluster-varied fixture replay,
editable systemd/launchd templates, and fail-closed compatibility-manifest
startup checks.

- Raw TCP example with length-prefixed frames and manifest preflight.
- WebSocket example for browser/service use with manifest preflight.
- HTTP streaming or SSE example for server-pushed agent updates with manifest
  preflight.
- Local broker adapter example with manifest preflight.
- Replay log format for offline benchmark capture.
- Explicit `aura-proxy` ingress/egress sidecar for controlled TCP links.
- `aura-proxy-benchmark` for sustained local sidecar byte-movement checks.
- `tools/run_aiwire_proxy_cluster.py` for 60-second coordinator-to-edge proxy
  runs with remote fixture servers, remote egress sidecars, local ingress
  clients, per-target JSON artifacts, markdown summaries, and opt-in
  multi-connection sessions per target.
- Service-manager templates for systemd and launchd.

Definition of done:

- Users can place AIWire as an explicit structural side channel beside or below
  their message protocol without changing their protocol semantics.

## Phase 6: Dictionary Evolution

Goal: improve compression without breaking deployed peers.

Status: active. The first compatibility gate is implemented: AIWire can now
emit and compare a manifest that pins protocol version, static dictionary hash
and size, zlib parameters, delta version, session dictionary state, routine
control-LUT state, fallback codecs, and safety limits before a peer/release is
trusted. The explicit proxy now uses that manifest as part of session startup
before it accepts semantic AIWire frames. Persistent session resume cache
support is also implemented so repeat peer connections can offer known
dictionary state hashes and fail closed if the selected state cannot be resolved
locally.

- Version static dictionaries and session-template catalogs explicitly.
- Keep `aura-aiwire-compatibility` available as the release/deployment preflight
  for dictionary, template, delta-version, and LUT compatibility.
- Keep runtime startup paths, including `aura-proxy` and transport examples,
  fail-closed on compatibility-manifest mismatch before data frames move.
- Keep `aura-aiwire-resume-cache` available as the local peer-state store for
  future-connection resume handshakes.
- Add corpus-driven dictionary generation tooling.
- Keep a compatibility matrix for dictionary hash, protocol version, and
  template hash, delta version, and fallback codec.
- Measure whether protocol-specific dictionaries outperform one combined
  dictionary.
- Add application-provided dictionary extensions for private deployments without
  putting private terms into the public repo.

Definition of done:

- Dictionary upgrades are benchmarked, reversible, and negotiated safely.

## Phase 7: General AURA Cleanup

Goal: make the broader compression toolkit easier to trust.

Status: planned.

- Separate production-facing AIWire modules from research modules in docs.
- Reduce duplicate compressor entry points where possible.
- Add focused tests around template discovery and metadata sidechannel behavior.
- Document which APIs are stable, experimental, or legacy.
- Remove or archive stale claims that are not supported by current tests.

Definition of done:

- The repo no longer looks like one unfinished universal compressor; it clearly
  presents a proven AIWire path plus experimental research areas.

## Open Research Questions

- How much does canonical JSON ordering help compared with schema-aware binary
  encoding?
- When should batching beat streaming for latency-sensitive agent traffic?
- Can AURA metadata sidechannels route messages before decompression without
  creating security or privacy hazards?
- What is the best split between static dictionaries, session templates, and
  per-session learned structure for MCP, A2A, OpenAI, local traces, and
  application-specific terms?
- Does QUIC add value for this workload, or is TCP/WebSocket enough for normal
  LAN and service deployments?
