#!/usr/bin/env python3
"""WebSocket transport example for AIWire frames.

Install the optional dependency first:

    pip install -e ".[websocket]"
"""

from __future__ import annotations

import asyncio
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
        print_result,
        raw_size,
        route_status_payload,
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
        print_result,
        raw_size,
        route_status_payload,
    )

from aura_compression import AIWireSessionDecoder, AIWireSessionEncoder


async def run_async_demo(count: int = 8, seed: int = 4404) -> TransportDemoResult:
    try:
        import websockets
    except ImportError as exc:  # pragma: no cover - depends on optional extra.
        raise RuntimeError(
            'install the optional websocket extra: pip install -e ".[websocket]"'
        ) from exc

    messages = demo_messages(count, seed)
    received: list[dict[str, Any]] = []
    server_control_received = 0
    server_control_sent = 0

    async def handler(websocket: Any) -> None:
        nonlocal server_control_received, server_control_sent
        decoder = AIWireSessionDecoder()
        encoder = AIWireSessionEncoder(level=3)
        for index in range(count):
            raw_control = await websocket.recv()
            if isinstance(raw_control, str):
                raw_control = raw_control.encode("latin1")
            control_frame = TransportCarrierFrame.from_bytes(raw_control)
            if control_frame.lane != CONTROL_LANE:
                raise ValueError("expected control frame before semantic frame")
            decode_demo_control_frame(control_frame.payload)
            server_control_received += 1

            raw_semantic = await websocket.recv()
            if isinstance(raw_semantic, str):
                raw_semantic = raw_semantic.encode("latin1")
            semantic_frame = TransportCarrierFrame.from_bytes(raw_semantic)
            if semantic_frame.lane != SEMANTIC_LANE:
                raise ValueError("expected semantic frame after control frame")
            message = decoder.decompress_message(semantic_frame.payload)
            received.append(message)
            control_payload = route_status_payload(
                transport="websocket",
                sequence=index,
                direction="server_to_client",
                status="accepted",
                trace_id=message.get("trace_id"),
            )
            await websocket.send(
                TransportCarrierFrame(
                    CONTROL_LANE,
                    encode_route_status_control(control_payload),
                ).to_bytes()
            )
            server_control_sent += 1
            reply = {
                "protocol": "local.agent",
                "schema": "local.agent.transport.ack.v1",
                "transport": "websocket",
                "sequence": index,
                "trace_id": message.get("trace_id"),
                "accepted": True,
            }
            await websocket.send(
                TransportCarrierFrame(
                    SEMANTIC_LANE,
                    encoder.compress_message(reply),
                ).to_bytes()
            )

    server = await websockets.serve(handler, "127.0.0.1", 0)
    try:
        port = server.sockets[0].getsockname()[1]
        encoder = AIWireSessionEncoder(level=3)
        decoder = AIWireSessionDecoder()
        replies = 0
        wire_bytes = 0
        control_sent = 0
        control_received = 0
        async with websockets.connect(f"ws://127.0.0.1:{port}") as websocket:
            for message in messages:
                control_payload = route_status_payload(
                    transport="websocket",
                    sequence=control_sent,
                    direction="client_to_server",
                    status="ready",
                    trace_id=message.get("trace_id"),
                )
                control_frame = TransportCarrierFrame(
                    CONTROL_LANE,
                    encode_route_status_control(control_payload),
                ).to_bytes()
                wire_bytes += len(control_frame)
                await websocket.send(control_frame)
                control_sent += 1

                frame = encoder.compress_message(message)
                semantic_frame = TransportCarrierFrame(SEMANTIC_LANE, frame).to_bytes()
                wire_bytes += len(semantic_frame)
                await websocket.send(semantic_frame)

                reply_control = await websocket.recv()
                if isinstance(reply_control, str):
                    reply_control = reply_control.encode("latin1")
                reply_control_frame = TransportCarrierFrame.from_bytes(reply_control)
                if reply_control_frame.lane != CONTROL_LANE:
                    raise ValueError("expected control reply before semantic reply")
                decode_demo_control_frame(reply_control_frame.payload)
                wire_bytes += len(reply_control)
                control_received += 1

                reply_frame = await websocket.recv()
                if isinstance(reply_frame, str):
                    reply_frame = reply_frame.encode("latin1")
                reply_carrier = TransportCarrierFrame.from_bytes(reply_frame)
                if reply_carrier.lane != SEMANTIC_LANE:
                    raise ValueError("expected semantic reply after control reply")
                wire_bytes += len(reply_frame)
                decoder.decompress_message(reply_carrier.payload)
                replies += 1
    finally:
        server.close()
        await server.wait_closed()

    return TransportDemoResult(
        transport="websocket",
        messages_sent=len(messages),
        messages_received=len(received),
        replies_received=replies,
        control_frames_sent=control_sent + server_control_sent,
        control_frames_received=control_received + server_control_received,
        raw_bytes=raw_size(messages),
        wire_bytes=wire_bytes,
    )


def run_demo(count: int = 8, seed: int = 4404) -> TransportDemoResult:
    return asyncio.run(run_async_demo(count=count, seed=seed))


if __name__ == "__main__":
    print_result(run_demo())
