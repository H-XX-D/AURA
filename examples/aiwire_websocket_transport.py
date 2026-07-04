#!/usr/bin/env python3
"""WebSocket transport example for AIWire frames.

Install the optional dependency first:

    pip install -e ".[websocket]"
"""

from __future__ import annotations

import asyncio
from typing import Any

try:
    from .aiwire_transport_common import TransportDemoResult, demo_messages, print_result, raw_size
except ImportError:  # pragma: no cover - direct script execution.
    from aiwire_transport_common import TransportDemoResult, demo_messages, print_result, raw_size

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

    async def handler(websocket: Any) -> None:
        decoder = AIWireSessionDecoder()
        encoder = AIWireSessionEncoder(level=3)
        for index in range(count):
            frame = await websocket.recv()
            if isinstance(frame, str):
                frame = frame.encode("latin1")
            message = decoder.decompress_message(frame)
            received.append(message)
            reply = {
                "protocol": "local.agent",
                "schema": "local.agent.transport.ack.v1",
                "transport": "websocket",
                "sequence": index,
                "trace_id": message.get("trace_id"),
                "accepted": True,
            }
            await websocket.send(encoder.compress_message(reply))

    server = await websockets.serve(handler, "127.0.0.1", 0)
    try:
        port = server.sockets[0].getsockname()[1]
        encoder = AIWireSessionEncoder(level=3)
        decoder = AIWireSessionDecoder()
        replies = 0
        wire_bytes = 0
        async with websockets.connect(f"ws://127.0.0.1:{port}") as websocket:
            for message in messages:
                frame = encoder.compress_message(message)
                wire_bytes += len(frame)
                await websocket.send(frame)
                reply_frame = await websocket.recv()
                if isinstance(reply_frame, str):
                    reply_frame = reply_frame.encode("latin1")
                wire_bytes += len(reply_frame)
                decoder.decompress_message(reply_frame)
                replies += 1
    finally:
        server.close()
        await server.wait_closed()

    return TransportDemoResult(
        transport="websocket",
        messages_sent=len(messages),
        messages_received=len(received),
        replies_received=replies,
        raw_bytes=raw_size(messages),
        wire_bytes=wire_bytes,
    )


def run_demo(count: int = 8, seed: int = 4404) -> TransportDemoResult:
    return asyncio.run(run_async_demo(count=count, seed=seed))


if __name__ == "__main__":
    print_result(run_demo())
