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
        TransportDemoResult,
        b64,
        demo_messages,
        print_result,
        raw_size,
        unb64,
    )
except ImportError:  # pragma: no cover - direct script execution.
    from aiwire_transport_common import (
        TransportDemoResult,
        b64,
        demo_messages,
        print_result,
        raw_size,
        unb64,
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

        self.send_response(200)
        self.send_header("content-type", "text/event-stream")
        self.send_header("cache-control", "no-cache")
        self.end_headers()

        for index, frame_text in enumerate(payload["frames"]):
            message = decoder.decompress_message(unb64(frame_text))
            received.append(message)
            reply = {
                "protocol": "local.agent",
                "schema": "local.agent.transport.ack.v1",
                "transport": "http-sse",
                "sequence": index,
                "trace_id": message.get("trace_id"),
                "accepted": True,
            }
            event = f"event: aiwire\ndata: {b64(encoder.compress_message(reply))}\n\n"
            self.wfile.write(event.encode("utf-8"))
            self.wfile.flush()

        self.server.received_messages = received  # type: ignore[attr-defined]


def run_demo(count: int = 8, seed: int = 4202) -> TransportDemoResult:
    messages = demo_messages(count, seed)
    encoder = AIWireSessionEncoder(level=3)
    frames = [encoder.compress_message(message) for message in messages]
    request_body = json.dumps({"frames": [b64(frame) for frame in frames]}).encode("utf-8")
    wire_bytes = len(request_body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), _SseHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        request = Request(
            f"http://{host}:{port}/aiwire",
            data=request_body,
            headers={"accept": "text/event-stream", "content-type": "application/json"},
            method="POST",
        )
        decoder = AIWireSessionDecoder()
        replies = 0
        with urlopen(request, timeout=5) as response:  # noqa: S310 - local demo URL.
            for raw_line in response:
                line = raw_line.decode("utf-8").strip()
                if not line.startswith("data: "):
                    continue
                reply_frame = unb64(line.removeprefix("data: "))
                wire_bytes += len(raw_line)
                decoder.decompress_message(reply_frame)
                replies += 1
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()

    received = getattr(server, "received_messages", [])
    return TransportDemoResult(
        transport="http-sse",
        messages_sent=len(messages),
        messages_received=len(received),
        replies_received=replies,
        raw_bytes=raw_size(messages),
        wire_bytes=wire_bytes,
    )


if __name__ == "__main__":
    print_result(run_demo())
