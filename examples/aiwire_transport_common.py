"""Shared helpers for the AIWire transport examples."""

from __future__ import annotations

import base64
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from aura_compression import (
    AIWireControlLUTEntry,
    build_structured_ai_messages,
    decode_aiwire_control_lut_frame,
    encode_ai_wire_message,
    encode_aiwire_control_lut_frame,
)

SEMANTIC_LANE = "semantic"
CONTROL_LANE = "control"
_LANE_TO_TAG = {SEMANTIC_LANE: 0x01, CONTROL_LANE: 0x02}
_TAG_TO_LANE = {value: key for key, value in _LANE_TO_TAG.items()}

DEMO_CONTROL_LUT = (
    AIWireControlLUTEntry(0x0010, "heartbeat", "aura.aiwire.heartbeat.v1"),
    AIWireControlLUTEntry(0x0011, "route_status", "aura.aiwire.route_status.v1"),
)


@dataclass(frozen=True)
class TransportCarrierFrame:
    """Small transport envelope used by the examples.

    AIWire data frames do not self-identify their lane, so each example adds a
    one-byte carrier tag before the transport's own frame boundary.
    """

    lane: str
    payload: bytes

    def to_bytes(self) -> bytes:
        try:
            tag = _LANE_TO_TAG[self.lane]
        except KeyError as exc:
            raise ValueError(f"unsupported AIWire transport lane: {self.lane}") from exc
        return bytes((tag,)) + self.payload

    @classmethod
    def from_bytes(cls, frame: bytes) -> "TransportCarrierFrame":
        if len(frame) < 1:
            raise ValueError("transport carrier frame is empty")
        try:
            lane = _TAG_TO_LANE[frame[0]]
        except KeyError as exc:
            raise ValueError(f"unknown AIWire transport lane tag: {frame[0]}") from exc
        return cls(lane=lane, payload=frame[1:])


@dataclass(frozen=True)
class TransportDemoResult:
    transport: str
    messages_sent: int
    messages_received: int
    replies_received: int
    control_frames_sent: int
    control_frames_received: int
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
            "control_frames_sent": self.control_frames_sent,
            "control_frames_received": self.control_frames_received,
            "raw_bytes": self.raw_bytes,
            "wire_bytes": self.wire_bytes,
            "ratio": round(self.ratio, 3),
        }


def demo_messages(count: int, seed: int) -> list[dict[str, Any]]:
    return build_structured_ai_messages(count=count, seed=seed)


def raw_size(messages: list[dict[str, Any]]) -> int:
    return sum(len(encode_ai_wire_message(message)) for message in messages)


def route_status_payload(
    *,
    transport: str,
    sequence: int,
    direction: str,
    status: str,
    trace_id: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "direction": direction,
        "sequence": sequence,
        "status": status,
        "transport": transport,
    }
    if trace_id is not None:
        payload["trace_id"] = str(trace_id)
    return payload


def encode_route_status_control(payload: Mapping[str, Any]) -> bytes:
    return encode_aiwire_control_lut_frame(
        DEMO_CONTROL_LUT,
        meaning="route_status",
        payload=payload,
    )


def decode_demo_control_frame(frame: bytes) -> dict[str, object]:
    return decode_aiwire_control_lut_frame(DEMO_CONTROL_LUT, frame).to_dict()


def b64(payload: bytes) -> str:
    return base64.b64encode(payload).decode("ascii")


def unb64(payload: str) -> bytes:
    return base64.b64decode(payload.encode("ascii"))


def print_result(result: TransportDemoResult) -> None:
    print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
