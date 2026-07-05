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

- Keep the AIWire v1 handshake, side-channel, and delta-frame spec aligned with
  implementation and tests.
- Define handshake fields, template update signals, accepted fallback behavior,
  resync behavior, and failure modes.
- Keep cross-version dictionary compatibility tests in the fast AIWire gate.
- Keep corrupted-frame and truncated-frame tests in the fast AIWire gate.
- Keep TCP partial-frame read/write tests and interrupted delta-state tests in
  the fast AIWire gate.
- Keep negotiated fallback tests for `raw` and `zlib` in the fast AIWire gate.
- Make stats stable enough for benchmark comparison over time.

Definition of done:

- AIWire v1 can be implemented by another language/runtime from the spec and
  interoperate with the Python tests.

## Phase 3: Better Message Corpora

Goal: benchmark against realistic protocol-shaped data.

- Expand the generated corpus for MCP requests, MCP responses, A2A tasks,
  OpenAI tool calls, structured outputs, traces, reviews, and memory writes.
- Add delta-shaped corpora where the task/session/template is stable and only
  status, token, argument, artifact, or trace values change.
- Keep current corpus variants aligned with public protocol shapes and mark
  synthetic fields clearly.
- Keep saved fixture corpora deterministic, public-safe, and side-channel
  complete. The first AIWire session fixture is
  [`fixtures/aiwire_sessions/public_session_corpus_v1.json`](../fixtures/aiwire_sessions/public_session_corpus_v1.json).
- Track corpus size, average frame size, key distribution, and protocol mix.
- Benchmark with small, medium, and bursty message sizes.
- Add CI-friendly benchmark smoke tests that detect major regressions without
  requiring a full LAN lab.
- Keep the fixture-backed saturation benchmark current so bandwidth, latency,
  CPU ceiling, and concurrent-agent requirements are measured on the same
  public corpus.

Definition of done:

- Benchmark numbers can be compared across commits and across machines with a
  known corpus.

## Phase 4: Native and Edge Performance

Goal: make AIWire fast on workstation and ARM64 edge targets.

- Make native backend builds reproducible on macOS, Linux x86_64, and Linux
  ARM64.
- Verify Python/native interoperability in CI where possible.
- Profile Jetson Nano-class CPUs and remove avoidable Python overhead.
- Add a native server mode to the benchmark harness when the backend is
  available.
- Compare Python AIWire, native AIWire, stateless zlib, and raw JSON under the
  same link model.

Definition of done:

- ARM64 edge targets get a measurable AIWire throughput improvement over the
  Python path while preserving byte-for-byte round trips.

## Phase 5: Transport Examples

Goal: show how AIWire fits into normal network stacks.

- Raw TCP example with length-prefixed frames.
- WebSocket example for browser/service use.
- HTTP streaming or SSE example for server-pushed agent updates.
- Local broker adapter example.
- Replay log format for offline benchmark capture.

Definition of done:

- Users can place AIWire as an explicit structural side channel beside or below
  their message protocol without changing their protocol semantics.

## Phase 6: Dictionary Evolution

Goal: improve compression without breaking deployed peers.

- Version static dictionaries and session-template catalogs explicitly.
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
