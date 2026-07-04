#!/usr/bin/env python3
"""In-process broker example for AIWire-framed local agent messages."""

from __future__ import annotations

import queue
import threading
from typing import Any

try:
    from .aiwire_transport_common import TransportDemoResult, demo_messages, print_result, raw_size
except ImportError:  # pragma: no cover - direct script execution.
    from aiwire_transport_common import TransportDemoResult, demo_messages, print_result, raw_size

from aura_compression import AIWireSessionDecoder, AIWireSessionEncoder


class LocalBroker:
    """Tiny topic broker that stores already-encoded AIWire frames."""

    def __init__(self) -> None:
        self._topics: dict[str, "queue.Queue[bytes]"] = {}

    def publish(self, topic: str, frame: bytes) -> None:
        self._topics.setdefault(topic, queue.Queue()).put(frame)

    def consume(self, topic: str, timeout: float = 1.0) -> bytes:
        return self._topics.setdefault(topic, queue.Queue()).get(timeout=timeout)


def run_demo(count: int = 8, seed: int = 4303) -> TransportDemoResult:
    messages = demo_messages(count, seed)
    broker = LocalBroker()
    inbound = "agents.worker.inbox"
    outbound = "agents.client.replies"
    wire_bytes = 0
    received: list[dict[str, Any]] = []

    def worker() -> None:
        decoder = AIWireSessionDecoder()
        encoder = AIWireSessionEncoder(level=3)
        for index in range(count):
            message = decoder.decompress_message(broker.consume(inbound))
            received.append(message)
            reply: dict[str, Any] = {
                "protocol": "local.agent",
                "schema": "local.agent.transport.ack.v1",
                "transport": "local-broker",
                "sequence": index,
                "trace_id": message.get("trace_id"),
                "accepted": True,
            }
            broker.publish(outbound, encoder.compress_message(reply))

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    encoder = AIWireSessionEncoder(level=3)
    decoder = AIWireSessionDecoder()
    replies = 0
    for message in messages:
        frame = encoder.compress_message(message)
        wire_bytes += len(frame)
        broker.publish(inbound, frame)
        reply_frame = broker.consume(outbound)
        wire_bytes += len(reply_frame)
        decoder.decompress_message(reply_frame)
        replies += 1

    thread.join(timeout=5)
    if thread.is_alive():
        raise TimeoutError("broker worker did not finish")

    return TransportDemoResult(
        transport="local-broker",
        messages_sent=len(messages),
        messages_received=len(received),
        replies_received=replies,
        raw_bytes=raw_size(messages),
        wire_bytes=wire_bytes,
    )


if __name__ == "__main__":
    print_result(run_demo())
