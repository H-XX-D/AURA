# AI-to-AI Messaging Field Survey

Research date: 2026-07-04

This note summarizes what the broader field is already doing around
AI-to-AI, agent-to-tool, and agent-to-UI messaging, with emphasis on wire
format, transport, compression, and where AURA/AIWire is differentiated.

## Short Version

The field is converging on interoperable JSON event and JSON-RPC protocols:
MCP for model-to-tool/context servers, A2A for agent-to-agent task exchange,
AG-UI for agent-to-frontend event streams, and WebSocket/WebRTC/SSE transports
for realtime behavior. These protocols optimize for compatibility, security,
streaming, and debuggability.

They mostly do not solve bandwidth-proportional AI message movement. Existing
byte-efficiency work is generic: HTTP/2 HPACK and HTTP/3 QPACK compress headers,
gRPC can compress individual messages, Protobuf/CBOR/Avro provide binary
serialization, and zstd supports dictionaries. The gap AURA can target is a
handshaked structure side channel for repetitive AI message streams: peers agree
on protocol structure, session templates, and template updates, then send
changes against that shared state instead of repeatedly moving whole frames.

## What Existing Agent Protocols Are Doing

| Area | What the field is doing | Wire/transport shape | AURA implication |
|---|---|---|---|
| MCP | Standardizes LLM app to tool/resource/prompt server communication. | JSON-RPC, UTF-8, stdio or Streamable HTTP; HTTP can use SSE. | AIWire should not replace MCP semantics. It can carry a structural side channel beside a high-volume MCP stream. |
| A2A | Standardizes agent-to-agent discovery, capability negotiation, tasks, streaming, async/push, and enterprise security patterns. | HTTP, JSON-RPC 2.0, SSE. | AURA can preserve A2A at boundaries while trusted peers exchange structure/templates and send deltas internally. |
| AG-UI | Standardizes event streams between agents and user-facing apps. | Typed streaming events, usually JSON event streams. | Same repeated-event shape as agent traffic; useful corpus for template/delta measurement, but not the core AI-to-AI target. |
| OpenAI Realtime / agent SDK patterns | Uses WebSocket for server-to-server realtime and WebRTC for lower-latency browser/mobile realtime; agent SDKs emphasize handoffs, tools, guardrails, tracing. | WebSocket/WebRTC/events; orchestration frameworks above transport. | AURA is lower-level: it can optimize server-to-server event movement, not orchestration semantics. |

## What Existing Wire Efficiency Work Is Doing

| Area | Established approach | Limitation for AI-to-AI streams | AURA direction |
|---|---|---|---|
| Protobuf / gRPC | Typed schema, binary encoding, generated bindings; gRPC supports compression. | Best when schemas are stable. Agent payloads are often evolving, opaque, tool-specific JSON. | Use as a comparison point. Do not force all agent protocols into static schemas. |
| CBOR / MessagePack / Avro | Compact binary serialization for structured data. | Reduces syntax overhead, but does not automatically exploit repeated session-specific agent vocabulary across many frames. | AIToken is in this family, but tuned to AI protocol keys and reversible JSON compatibility. |
| HTTP/2 / HTTP/3 | Header compression and multiplexing. HPACK/QPACK compress HTTP fields. | Helps headers, not repetitive JSON body content. | AIWire is analogous in spirit, but for AI message structure and value deltas. |
| gRPC compression | Per-call or per-message compression to reduce bandwidth. | Usually message-local, not optimized for thousands of tiny repetitive AI events with shared context. | Session dictionaries/templates, template-update signals, and deltas are the differentiator. |
| zstd dictionaries | Well-established dictionary compression, including raw content dictionaries. | Generic; still needs training, dictionary distribution, and protocol-specific handshakes. | AIWire session templates are aligned with this pattern. A zstd backend is worth benchmarking under the same delta model. |
| QUIC/WebRTC | Better realtime transport properties, multiplexed streams, path migration, lower-latency media paths. | Transport choice does not shrink payloads by itself. | AIWire can ride over TCP, QUIC streams, or WebRTC data channels if framed cleanly. |

## Where AURA Is Actually Different

AURA should not claim to invent agent interoperability. MCP, A2A, AG-UI, gRPC,
and WebRTC already cover large parts of that landscape.

AURA's useful claim is narrower and stronger:

> Given repetitive structured AI message streams, AURA handshakes the structure
> once and then moves changes. Fewer delta bytes per semantic exchange means
> more exchanges can fit through the same constrained link.

The current benchmark demonstrates that distinction:

- Raw JSON is bandwidth-bound: about 1,756 bandwidth-capacity exchanges/s on
  the modeled 10 Mbps bidirectional link.
- `aiwire` has about 11,017 bandwidth-capacity exchanges/s, 6.28x raw.
- `aitoken_aiwire` has about 12,948 bandwidth-capacity exchanges/s, 7.38x raw.
- The observed runtime uses only 19.6% of `aitoken_aiwire` capacity, so after
  compression the bottleneck moves to CPU/runtime/harness overhead.

This is a good result, but it also defines the next work: optimize native
runtime and concurrency until observed exchanges approach the new bandwidth
capacity.

## Product Positioning

The clean positioning is:

1. Preserve existing agent protocol semantics at boundaries.
2. Add AIWire as an explicit side channel for structure negotiation,
   session-template updates, and delta/resync behavior inside trusted
   high-volume links.
3. Measure semantic exchanges per second, p95/p99 latency, framed bytes per
   exchange, bandwidth-capacity exchanges per second, and codec CPU per exchange.
4. Treat compression ratio as a supporting metric, not the headline.

This avoids fighting MCP/A2A/AG-UI. AURA becomes the efficient data plane those
protocols can use when messages are numerous, repetitive, and network-bound,
while whole JSON-shaped frames remain the boundary and fallback representation.

## Near-Term Engineering Implications

- Add an MCP Streamable HTTP adapter experiment: preserve JSON-RPC externally,
  but negotiate AIWire structure/templates for the internal trusted link and
  move deltas after the handshake.
- Add an A2A proxy experiment: agent cards/tasks remain standard A2A; trusted
  peer links negotiate AIWire side-channel state.
- Benchmark native zstd dictionary mode against current native deflate.
- Add concurrency/native harness work so observed exchange rate can approach
  bandwidth-proportional capacity.
- Keep C ABI boundaries stable so C++, Python, Rust, Go, and local bridge code
  can share the same native codec.

## Sources

- MCP transports specification:
  https://modelcontextprotocol.io/specification/2025-11-25/basic/transports
- A2A protocol specification:
  https://github.com/a2aproject/A2A/blob/main/docs/specification.md
- AG-UI event architecture:
  https://docs.ag-ui.com/concepts/events
- OpenAI Realtime WebSocket:
  https://developers.openai.com/api/docs/guides/realtime-websocket
- OpenAI Realtime WebRTC:
  https://developers.openai.com/api/docs/guides/realtime-webrtc
- OpenAI Agents SDK:
  https://openai.github.io/openai-agents-python/
- gRPC compression:
  https://grpc.io/docs/guides/compression/
- Protocol Buffers overview:
  https://protobuf.dev/overview/
- RFC 8949, CBOR:
  https://www.rfc-editor.org/info/rfc8949/
- RFC 8878, Zstandard:
  https://www.rfc-editor.org/info/rfc8878/
- zstd dictionary format:
  https://github.com/facebook/zstd/blob/dev/doc/zstd_compression_format.md
- RFC 9113, HTTP/2:
  https://datatracker.ietf.org/doc/html/rfc9113
- RFC 9204, QPACK:
  https://www.rfc-editor.org/info/rfc9204/
- RFC 9000, QUIC:
  https://datatracker.ietf.org/doc/rfc9000/
- RFC 6349, TCP throughput testing:
  https://datatracker.ietf.org/doc/html/rfc6349
- RFC 5166, congestion-control evaluation metrics:
  https://www.rfc-editor.org/info/rfc5166/
