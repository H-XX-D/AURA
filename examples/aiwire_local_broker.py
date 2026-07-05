#!/usr/bin/env python3
"""In-process broker example for AIWire-framed local agent messages."""

from __future__ import annotations

import queue
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


class LocalBroker:
    """Tiny topic broker that stores already-encoded AIWire carrier frames."""

    def __init__(self) -> None:
        self._topics: dict[str, "queue.Queue[bytes]"] = {}

    def publish(self, topic: str, frame: TransportCarrierFrame) -> None:
        self._topics.setdefault(topic, queue.Queue()).put(frame.to_bytes())

    def consume(self, topic: str, timeout: float = 1.0) -> TransportCarrierFrame:
        return TransportCarrierFrame.from_bytes(
            self._topics.setdefault(topic, queue.Queue()).get(timeout=timeout)
        )


def run_demo(count: int = 8, seed: int = 4303) -> TransportDemoResult:
    messages = demo_messages(count, seed)
    broker = LocalBroker()
    inbound = "agents.worker.inbox"
    outbound = "agents.client.replies"
    wire_bytes = 0
    received: list[dict[str, Any]] = []
    worker_control_received = 0
    worker_control_sent = 0

    def worker() -> None:
        nonlocal worker_control_received, worker_control_sent
        decoder = AIWireSessionDecoder()
        encoder = AIWireSessionEncoder(level=3)
        for index in range(count):
            control_frame = broker.consume(inbound)
            if control_frame.lane != CONTROL_LANE:
                raise ValueError("expected control frame before semantic frame")
            decode_demo_control_frame(control_frame.payload)
            worker_control_received += 1

            semantic_frame = broker.consume(inbound)
            if semantic_frame.lane != SEMANTIC_LANE:
                raise ValueError("expected semantic frame after control frame")
            message = decoder.decompress_message(semantic_frame.payload)
            received.append(message)
            control_payload = route_status_payload(
                transport="local-broker",
                sequence=index,
                direction="worker_to_client",
                status="accepted",
                trace_id=message.get("trace_id"),
            )
            broker.publish(
                outbound,
                TransportCarrierFrame(
                    CONTROL_LANE,
                    encode_route_status_control(control_payload),
                ),
            )
            worker_control_sent += 1
            reply: dict[str, Any] = {
                "protocol": "local.agent",
                "schema": "local.agent.transport.ack.v1",
                "transport": "local-broker",
                "sequence": index,
                "trace_id": message.get("trace_id"),
                "accepted": True,
            }
            broker.publish(
                outbound,
                TransportCarrierFrame(SEMANTIC_LANE, encoder.compress_message(reply)),
            )

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    encoder = AIWireSessionEncoder(level=3)
    decoder = AIWireSessionDecoder()
    replies = 0
    control_sent = 0
    control_received = 0
    for index, message in enumerate(messages):
        control_payload = route_status_payload(
            transport="local-broker",
            sequence=index,
            direction="client_to_worker",
            status="ready",
            trace_id=message.get("trace_id"),
        )
        control_frame = TransportCarrierFrame(
            CONTROL_LANE,
            encode_route_status_control(control_payload),
        )
        wire_bytes += len(control_frame.to_bytes())
        broker.publish(inbound, control_frame)
        control_sent += 1

        frame = encoder.compress_message(message)
        semantic_frame = TransportCarrierFrame(SEMANTIC_LANE, frame)
        wire_bytes += len(semantic_frame.to_bytes())
        broker.publish(inbound, semantic_frame)

        reply_control = broker.consume(outbound)
        if reply_control.lane != CONTROL_LANE:
            raise ValueError("expected control reply before semantic reply")
        decode_demo_control_frame(reply_control.payload)
        wire_bytes += len(reply_control.to_bytes())
        control_received += 1

        reply_frame = broker.consume(outbound)
        if reply_frame.lane != SEMANTIC_LANE:
            raise ValueError("expected semantic reply after control reply")
        wire_bytes += len(reply_frame.to_bytes())
        decoder.decompress_message(reply_frame.payload)
        replies += 1

    thread.join(timeout=5)
    if thread.is_alive():
        raise TimeoutError("broker worker did not finish")

    return TransportDemoResult(
        transport="local-broker",
        messages_sent=len(messages),
        messages_received=len(received),
        replies_received=replies,
        control_frames_sent=control_sent + worker_control_sent,
        control_frames_received=control_received + worker_control_received,
        raw_bytes=raw_size(messages),
        wire_bytes=wire_bytes,
    )


if __name__ == "__main__":
    print_result(run_demo())
