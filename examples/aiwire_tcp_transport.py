#!/usr/bin/env python3
"""Length-prefixed TCP transport example for AIWire frames."""

from __future__ import annotations

import queue
import socket
import struct
import threading
from typing import Any

try:
    from .aiwire_transport_common import TransportDemoResult, demo_messages, print_result, raw_size
except ImportError:  # pragma: no cover - direct script execution.
    from aiwire_transport_common import TransportDemoResult, demo_messages, print_result, raw_size

from aura_compression import AIWireSessionDecoder, AIWireSessionEncoder

U32 = struct.Struct("!I")


def _write_frame(sock: socket.socket, payload: bytes) -> None:
    sock.sendall(U32.pack(len(payload)))
    sock.sendall(payload)


def _read_exact(sock: socket.socket, size: int) -> bytes:
    data = bytearray()
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            raise EOFError("socket closed while reading frame")
        data.extend(chunk)
    return bytes(data)


def _read_frame(sock: socket.socket) -> bytes:
    size = U32.unpack(_read_exact(sock, U32.size))[0]
    return _read_exact(sock, size)


def run_demo(count: int = 8, seed: int = 4101) -> TransportDemoResult:
    messages = demo_messages(count, seed)
    received: "queue.Queue[list[dict[str, Any]] | BaseException]" = queue.Queue()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        host, port = listener.getsockname()

        def server() -> None:
            try:
                with listener.accept()[0] as conn:
                    decoder = AIWireSessionDecoder()
                    encoder = AIWireSessionEncoder(level=3)
                    server_messages: list[dict[str, Any]] = []
                    for index in range(count):
                        message = decoder.decompress_message(_read_frame(conn))
                        server_messages.append(message)
                        reply = {
                            "protocol": "local.agent",
                            "schema": "local.agent.transport.ack.v1",
                            "transport": "tcp",
                            "sequence": index,
                            "trace_id": message.get("trace_id"),
                            "accepted": True,
                        }
                        _write_frame(conn, encoder.compress_message(reply))
                    received.put(server_messages)
            except BaseException as exc:  # pragma: no cover - surfaced through queue.
                received.put(exc)

        thread = threading.Thread(target=server, daemon=True)
        thread.start()
        wire_bytes = 0
        replies = 0
        with socket.create_connection((host, port), timeout=5) as sock:
            encoder = AIWireSessionEncoder(level=3)
            decoder = AIWireSessionDecoder()
            for message in messages:
                frame = encoder.compress_message(message)
                wire_bytes += U32.size + len(frame)
                _write_frame(sock, frame)
                reply_frame = _read_frame(sock)
                wire_bytes += U32.size + len(reply_frame)
                decoder.decompress_message(reply_frame)
                replies += 1

        thread.join(timeout=5)
        if thread.is_alive():
            raise TimeoutError("TCP demo server did not finish")
        server_result = received.get_nowait()
        if isinstance(server_result, BaseException):
            raise RuntimeError("TCP demo server failed") from server_result

    return TransportDemoResult(
        transport="tcp",
        messages_sent=len(messages),
        messages_received=len(server_result),
        replies_received=replies,
        raw_bytes=raw_size(messages),
        wire_bytes=wire_bytes,
    )


if __name__ == "__main__":
    print_result(run_demo())
