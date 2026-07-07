# AIWire Transport Examples

These examples show how AIWire frames can ride over ordinary transports. They
first exchange an AIWire compatibility manifest on the control lane, then carry
semantic/message frames and compact routine-control LUT frames so the control
side channel stays visible without inflating the semantic stream. They are
intentionally small and local-only; production deployments should add their own
authentication, authorization, peer identity, retries, backpressure, and
observability.

Run from the repository root:

```bash
PYTHONPATH=src python examples/aiwire_tcp_transport.py
PYTHONPATH=src python examples/aiwire_http_streaming_transport.py
PYTHONPATH=src python examples/aiwire_local_broker.py
```

The WebSocket example uses the optional dependency:

```bash
pip install -e ".[websocket]"
PYTHONPATH=src python examples/aiwire_websocket_transport.py
```

## What Each Example Shows

- `aiwire_tcp_transport.py`: length-prefixed AIWire frames over a raw TCP
  socket. Every carrier frame is `uint32_be length` plus a one-byte lane tag and
  the AIWire payload.
- `aiwire_websocket_transport.py`: one binary WebSocket message per AIWire
  carrier frame.
- `aiwire_http_streaming_transport.py`: ordered request carrier frames sent in
  an HTTP POST, with routine control streamed back as `aiwire-control` SSE
  events before semantic `aiwire` reply events.
- `aiwire_local_broker.py`: an in-process topic broker carrying already-encoded
  AIWire carrier frames between local agents.

The same pattern applies to other transports: perform the compatibility
manifest exchange and AIWire handshake/session setup at the application
boundary, then carry compressed semantic frames and routine-control frames as
opaque bytes in the transport that already fits your system. The transport must
preserve frame boundaries and ordering inside each live AIWire compression
epoch. Mission-critical control still belongs in explicit system-control
messages, not the compact LUT path.
