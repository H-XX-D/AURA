#!/usr/bin/env python3
"""Length-prefixed TCP transport example for AIWire frames."""

from __future__ import annotations

import queue
import socket
import struct
import threading
from typing import Any

try:
    from .aiwire_transport_common import (
        CONTROL_LANE,
        SEMANTIC_LANE,
        TransportCarrierFrame,
        TransportDemoResult,
        decode_demo_control_frame,
        demo_messages,
        encode_route_status_control,
        encode_transport_compatibility_control,
        print_result,
        raw_size,
        route_status_payload,
        verify_transport_compatibility_control,
    )
except ImportError:  # pragma: no cover - direct script execution.
    from aiwire_transport_common import (
        CONTROL_LANE,
        SEMANTIC_LANE,
        TransportCarrierFrame,
        TransportDemoResult,
        decode_demo_control_frame,
        demo_messages,
        encode_route_status_control,
        encode_transport_compatibility_control,
        print_result,
        raw_size,
        route_status_payload,
        verify_transport_compatibility_control,
    )

from aura_compression import AIWireSessionDecoder, AIWireSessionEncoder

U32 = struct.Struct("!I")


def _write_frame(sock: socket.socket, frame: TransportCarrierFrame) -> int:
    payload = frame.to_bytes()
    sock.sendall(U32.pack(len(payload)))
    sock.sendall(payload)
    return U32.size + len(payload)


def _read_exact(sock: socket.socket, size: int) -> bytes:
    data = bytearray()
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            raise EOFError("socket closed while reading frame")
        data.extend(chunk)
    return bytes(data)


def _read_frame(sock: socket.socket) -> TransportCarrierFrame:
    size = U32.unpack(_read_exact(sock, U32.size))[0]
    return TransportCarrierFrame.from_bytes(_read_exact(sock, size))


def run_demo(count: int = 8, seed: int = 4101) -> TransportDemoResult:
    messages = demo_messages(count, seed)
    received: "queue.Queue[tuple[list[dict[str, Any]], int, int, int] | BaseException]" = (
        queue.Queue()
    )

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
                    control_received = 0
                    control_sent = 0
                    compatibility_checks = 0

                    compatibility_frame = _read_frame(conn)
                    if compatibility_frame.lane != CONTROL_LANE:
                        raise ValueError("expected compatibility control before data frames")
                    verify_transport_compatibility_control(
                        compatibility_frame.payload,
                        expected_role="client",
                    )
                    compatibility_checks += 1
                    control_received += 1
                    _write_frame(
                        conn,
                        TransportCarrierFrame(
                            CONTROL_LANE,
                            encode_transport_compatibility_control("server"),
                        ),
                    )
                    control_sent += 1
                    for index in range(count):
                        control_frame = _read_frame(conn)
                        if control_frame.lane != CONTROL_LANE:
                            raise ValueError("expected control frame before semantic frame")
                        decode_demo_control_frame(control_frame.payload)
                        control_received += 1

                        semantic_frame = _read_frame(conn)
                        if semantic_frame.lane != SEMANTIC_LANE:
                            raise ValueError("expected semantic frame after control frame")
                        message = decoder.decompress_message(semantic_frame.payload)
                        server_messages.append(message)

                        control_payload = route_status_payload(
                            transport="tcp",
                            sequence=index,
                            direction="server_to_client",
                            status="accepted",
                            trace_id=message.get("trace_id"),
                        )
                        _write_frame(
                            conn,
                            TransportCarrierFrame(
                                CONTROL_LANE,
                                encode_route_status_control(control_payload),
                            ),
                        )
                        control_sent += 1
                        reply = {
                            "protocol": "local.agent",
                            "schema": "local.agent.transport.ack.v1",
                            "transport": "tcp",
                            "sequence": index,
                            "trace_id": message.get("trace_id"),
                            "accepted": True,
                        }
                        _write_frame(
                            conn,
                            TransportCarrierFrame(
                                SEMANTIC_LANE,
                                encoder.compress_message(reply),
                            ),
                        )
                    received.put(
                        (
                            server_messages,
                            control_received,
                            control_sent,
                            compatibility_checks,
                        )
                    )
            except BaseException as exc:  # pragma: no cover - surfaced through queue.
                received.put(exc)

        thread = threading.Thread(target=server, daemon=True)
        thread.start()
        wire_bytes = 0
        replies = 0
        with socket.create_connection((host, port), timeout=5) as sock:
            encoder = AIWireSessionEncoder(level=3)
            decoder = AIWireSessionDecoder()
            control_sent = 0
            control_received = 0
            compatibility_checks = 0
            compatibility_frame = TransportCarrierFrame(
                CONTROL_LANE,
                encode_transport_compatibility_control("client"),
            )
            wire_bytes += _write_frame(sock, compatibility_frame)
            control_sent += 1
            reply_compatibility = _read_frame(sock)
            if reply_compatibility.lane != CONTROL_LANE:
                raise ValueError("expected compatibility control reply")
            wire_bytes += U32.size + len(reply_compatibility.to_bytes())
            verify_transport_compatibility_control(
                reply_compatibility.payload,
                expected_role="server",
            )
            compatibility_checks += 1
            control_received += 1
            for index, message in enumerate(messages):
                control_payload = route_status_payload(
                    transport="tcp",
                    sequence=index,
                    direction="client_to_server",
                    status="ready",
                    trace_id=message.get("trace_id"),
                )
                wire_bytes += _write_frame(
                    sock,
                    TransportCarrierFrame(
                        CONTROL_LANE,
                        encode_route_status_control(control_payload),
                    ),
                )
                control_sent += 1
                frame = encoder.compress_message(message)
                wire_bytes += _write_frame(sock, TransportCarrierFrame(SEMANTIC_LANE, frame))

                reply_control = _read_frame(sock)
                if reply_control.lane != CONTROL_LANE:
                    raise ValueError("expected control reply before semantic reply")
                decode_demo_control_frame(reply_control.payload)
                wire_bytes += U32.size + len(reply_control.to_bytes())
                control_received += 1

                reply_frame = _read_frame(sock)
                if reply_frame.lane != SEMANTIC_LANE:
                    raise ValueError("expected semantic reply after control reply")
                wire_bytes += U32.size + len(reply_frame.to_bytes())
                decoder.decompress_message(reply_frame.payload)
                replies += 1

        thread.join(timeout=5)
        if thread.is_alive():
            raise TimeoutError("TCP demo server did not finish")
        server_result = received.get_nowait()
        if isinstance(server_result, BaseException):
            raise RuntimeError("TCP demo server failed") from server_result

    (
        server_messages,
        server_control_received,
        server_control_sent,
        server_compatibility_checks,
    ) = server_result

    return TransportDemoResult(
        transport="tcp",
        messages_sent=len(messages),
        messages_received=len(server_messages),
        replies_received=replies,
        control_frames_sent=control_sent + server_control_sent,
        control_frames_received=control_received + server_control_received,
        raw_bytes=raw_size(messages),
        wire_bytes=wire_bytes,
        compatibility_checks=compatibility_checks + server_compatibility_checks,
        compatibility_codec="aiwire",
    )


if __name__ == "__main__":
    print_result(run_demo())
