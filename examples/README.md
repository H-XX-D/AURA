# AIWire Transport Examples

These examples show how AIWire frames can ride over ordinary transports. They
are intentionally small and local-only; production deployments should add their
own authentication, authorization, peer identity, retries, backpressure, and
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
  socket.
- `aiwire_websocket_transport.py`: binary AIWire frames over WebSocket messages.
- `aiwire_http_streaming_transport.py`: compressed request frames sent in an
  HTTP POST, with AIWire replies streamed back as Server-Sent Events.
- `aiwire_local_broker.py`: an in-process topic broker carrying already-encoded
  AIWire frames between local agents.

The same pattern applies to other transports: perform the AIWire
handshake/session setup at the application boundary, then carry compressed
AIWire frames as opaque bytes in the transport that already fits your system.
