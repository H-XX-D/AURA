"""Shared helpers for the AIWire transport examples."""

from __future__ import annotations

import base64
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from aura_compression import build_structured_ai_messages, encode_ai_wire_message


@dataclass(frozen=True)
class TransportDemoResult:
    transport: str
    messages_sent: int
    messages_received: int
    replies_received: int
    raw_bytes: int
    wire_bytes: int

    @property
    def ratio(self) -> float:
        return self.raw_bytes / self.wire_bytes if self.wire_bytes else 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "transport": self.transport,
            "messages_sent": self.messages_sent,
            "messages_received": self.messages_received,
            "replies_received": self.replies_received,
            "raw_bytes": self.raw_bytes,
            "wire_bytes": self.wire_bytes,
            "ratio": round(self.ratio, 3),
        }


def demo_messages(count: int, seed: int) -> list[dict[str, Any]]:
    return build_structured_ai_messages(count=count, seed=seed)


def raw_size(messages: list[dict[str, Any]]) -> int:
    return sum(len(encode_ai_wire_message(message)) for message in messages)


def b64(payload: bytes) -> str:
    return base64.b64encode(payload).decode("ascii")


def unb64(payload: str) -> bytes:
    return base64.b64decode(payload.encode("ascii"))


def print_result(result: TransportDemoResult) -> None:
    print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
