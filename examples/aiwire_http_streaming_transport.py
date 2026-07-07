#!/usr/bin/env python3
"""HTTP POST plus Server-Sent Events example for AIWire frames."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.request import Request, urlopen

try:
    from .aiwire_transport_common import (
        CONTROL_LANE,
        SEMANTIC_LANE,
        TransportCarrierFrame,
        TransportDemoResult,
        b64,
        decode_demo_control_frame,
        demo_messages,
        encode_route_status_control,
        encode_transport_compatibility_control,
        print_result,
        raw_size,
        route_status_payload,
        unb64,
        verify_transport_compatibility_control,
    )
except ImportError:  # pragma: no cover - direct script execution.
    from aiwire_transport_common import (
        CONTROL_LANE,
        SEMANTIC_LANE,
        TransportCarrierFrame,
        TransportDemoResult,
        b64,
        decode_demo_control_frame,
        demo_messages,
        encode_route_status_control,
        encode_transport_compatibility_control,
        print_result,
        raw_size,
        route_status_payload,
        unb64,
        verify_transport_compatibility_control,
    )

from aura_compression import AIWireSessionDecoder, AIWireSessionEncoder


class _SseHandler(BaseHTTPRequestHandler):
    server_version = "AURAHTTPDemo/1.0"

    def log_message(self, _format: str, *_args: Any) -> None:
        return

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler hook.
        length = int(self.headers.get("content-length", "0"))
        payload = json.loads(self.rfile.read(length))
        decoder = AIWireSessionDecoder()
        encoder = AIWireSessionEncoder(level=3)
        received: list[dict[str, Any]] = []
        control_received = 0
        control_sent = 0
        pending_control: dict[str, object] | None = None

        self.send_response(200)
        self.send_header("content-type", "text/event-stream")
        self.send_header("cache-control", "no-cache")
        self.end_headers()

        frames = list(payload["frames"])
        if not frames:
            raise ValueError("HTTP AIWire request is missing compatibility frame")
        compatibility_carrier = TransportCarrierFrame.from_bytes(unb64(frames[0]))
        if compatibility_carrier.lane != CONTROL_LANE:
            raise ValueError("expected compatibility control before data frames")
        verify_transport_compatibility_control(
            compatibility_carrier.payload,
            expected_role="client",
        )
        control_received += 1
        compatibility_reply = TransportCarrierFrame(
            CONTROL_LANE,
            encode_transport_compatibility_control("server"),
        ).to_bytes()
        compatibility_event = "event: aiwire-control\n" f"data: {b64(compatibility_reply)}\n\n"
        self.wfile.write(compatibility_event.encode("utf-8"))
        self.wfile.flush()
        control_sent += 1

        for frame_text in frames[1:]:
            carrier = TransportCarrierFrame.from_bytes(unb64(frame_text))
            if carrier.lane == CONTROL_LANE:
                pending_control = decode_demo_control_frame(carrier.payload)
                control_received += 1
                continue
            if carrier.lane != SEMANTIC_LANE:
                raise ValueError(f"unexpected AIWire carrier lane: {carrier.lane}")
            if pending_control is None:
                raise ValueError("semantic frame arrived without preceding control frame")
            message = decoder.decompress_message(carrier.payload)
            received.append(message)
            sequence = int(pending_control["payload"]["sequence"])  # type: ignore[index]
            reply = {
                "protocol": "local.agent",
                "schema": "local.agent.transport.ack.v1",
                "transport": "http-sse",
                "sequence": sequence,
                "trace_id": message.get("trace_id"),
                "accepted": True,
            }
            control_payload = route_status_payload(
                transport="http-sse",
                sequence=sequence,
                direction="server_to_client",
                status="accepted",
                trace_id=message.get("trace_id"),
            )
            control_carrier = TransportCarrierFrame(
                CONTROL_LANE,
                encode_route_status_control(control_payload),
            ).to_bytes()
            semantic_carrier = TransportCarrierFrame(
                SEMANTIC_LANE,
                encoder.compress_message(reply),
            ).to_bytes()
            control_event = "event: aiwire-control\n" f"data: {b64(control_carrier)}\n\n"
            semantic_event = "event: aiwire\n" f"data: {b64(semantic_carrier)}\n\n"
            self.wfile.write(control_event.encode("utf-8"))
            self.wfile.write(semantic_event.encode("utf-8"))
            self.wfile.flush()
            control_sent += 1
            pending_control = None

        self.server.received_messages = received  # type: ignore[attr-defined]
        self.server.control_frames_received = control_received  # type: ignore[attr-defined]
        self.server.control_frames_sent = control_sent  # type: ignore[attr-defined]


def run_demo(count: int = 8, seed: int = 4202) -> TransportDemoResult:
    messages = demo_messages(count, seed)
    encoder = AIWireSessionEncoder(level=3)
    carrier_frames: list[TransportCarrierFrame] = [
        TransportCarrierFrame(CONTROL_LANE, encode_transport_compatibility_control("client"))
    ]
    for index, message in enumerate(messages):
        control_payload = route_status_payload(
            transport="http-sse",
            sequence=index,
            direction="client_to_server",
            status="ready",
            trace_id=message.get("trace_id"),
        )
        carrier_frames.append(
            TransportCarrierFrame(CONTROL_LANE, encode_route_status_control(control_payload))
        )
        carrier_frames.append(
            TransportCarrierFrame(SEMANTIC_LANE, encoder.compress_message(message))
        )
    request_body = json.dumps(
        {"frames": [b64(frame.to_bytes()) for frame in carrier_frames]},
        separators=(",", ":"),
    ).encode("utf-8")
    wire_bytes = len(request_body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), _SseHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host = str(server.server_address[0])
        port = int(server.server_address[1])
        request = Request(
            f"http://{host}:{port}/aiwire",
            data=request_body,
            headers={"accept": "text/event-stream", "content-type": "application/json"},
            method="POST",
        )
        decoder = AIWireSessionDecoder()
        replies = 0
        control_received = 0
        control_sent = len(messages) + 1
        compatibility_checks = 0
        with urlopen(request, timeout=5) as response:  # noqa: S310 - local demo URL.
            for raw_line in response:
                line = raw_line.decode("utf-8").strip()
                if not line.startswith("data: "):
                    continue
                carrier = TransportCarrierFrame.from_bytes(unb64(line.removeprefix("data: ")))
                wire_bytes += len(raw_line)
                if carrier.lane == CONTROL_LANE:
                    if not compatibility_checks:
                        verify_transport_compatibility_control(
                            carrier.payload,
                            expected_role="server",
                        )
                        compatibility_checks += 1
                    else:
                        decode_demo_control_frame(carrier.payload)
                    control_received += 1
                    continue
                if carrier.lane != SEMANTIC_LANE:
                    raise ValueError(f"unexpected AIWire carrier lane: {carrier.lane}")
                decoder.decompress_message(carrier.payload)
                replies += 1
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()

    received = getattr(server, "received_messages", [])
    server_control_received = getattr(server, "control_frames_received", 0)
    server_control_sent = getattr(server, "control_frames_sent", 0)
    return TransportDemoResult(
        transport="http-sse",
        messages_sent=len(messages),
        messages_received=len(received),
        replies_received=replies,
        control_frames_sent=control_sent + server_control_sent,
        control_frames_received=control_received + server_control_received,
        raw_bytes=raw_size(messages),
        wire_bytes=wire_bytes,
        compatibility_checks=compatibility_checks + 1,
        compatibility_codec="aiwire",
    )


if __name__ == "__main__":
    print_result(run_demo())
