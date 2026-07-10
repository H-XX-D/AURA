"""Shared helpers for the AIWire transport examples."""

from __future__ import annotations

import base64
import binascii
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, cast

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from aura_compression import (
    AIWireCompatibilityManifest,
    AIWireControlLUTEntry,
    AIWireHandshakeError,
    aiwire_compatibility_manifest_sha256,
    build_aiwire_compatibility_manifest,
    build_structured_ai_messages,
    decode_aiwire_control_lut_frame,
    encode_ai_wire_message,
    encode_aiwire_control_lut_frame,
    verify_aiwire_compatibility_manifest,
)

SEMANTIC_LANE = "semantic"
CONTROL_LANE = "control"
TRANSPORT_COMPATIBILITY_SCHEMA = "aura.aiwire.transport_compatibility.v1"
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
    compatibility_checks: int
    compatibility_codec: str

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
            "compatibility_checks": self.compatibility_checks,
            "compatibility_codec": self.compatibility_codec,
            "ratio": round(self.ratio, 3),
        }


def demo_messages(count: int, seed: int) -> list[dict[str, Any]]:
    return cast(list[dict[str, Any]], build_structured_ai_messages(count=count, seed=seed))


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
    return cast(
        bytes,
        encode_aiwire_control_lut_frame(
            DEMO_CONTROL_LUT,
            meaning="route_status",
            payload=payload,
        ),
    )


def decode_demo_control_frame(frame: bytes) -> dict[str, object]:
    return cast(
        dict[str, object], decode_aiwire_control_lut_frame(DEMO_CONTROL_LUT, frame).to_dict()
    )


def _compatibility_manifest_payload(
    manifest: AIWireCompatibilityManifest | Mapping[str, Any],
) -> dict[str, object]:
    if isinstance(manifest, AIWireCompatibilityManifest):
        return manifest.to_dict()
    return AIWireCompatibilityManifest.from_dict(manifest).to_dict()


def encode_transport_compatibility_control(
    role: str,
    *,
    manifest: AIWireCompatibilityManifest | Mapping[str, Any] | None = None,
) -> bytes:
    resolved_manifest = (
        manifest
        if manifest is not None
        else build_aiwire_compatibility_manifest(fallback_codecs=())
    )
    manifest_payload = _compatibility_manifest_payload(resolved_manifest)
    payload = {
        "schema": TRANSPORT_COMPATIBILITY_SCHEMA,
        "role": role,
        "manifest": manifest_payload,
        "manifest_sha256": aiwire_compatibility_manifest_sha256(manifest_payload),
    }
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


def verify_transport_compatibility_control(
    frame: bytes,
    *,
    expected_role: str,
    local_manifest: AIWireCompatibilityManifest | Mapping[str, Any] | None = None,
) -> dict[str, object]:
    try:
        payload = json.loads(frame.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("transport compatibility control must be JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("transport compatibility control must be an object")
    if payload.get("schema") != TRANSPORT_COMPATIBILITY_SCHEMA:
        raise ValueError("unsupported transport compatibility control schema")
    if payload.get("role") != expected_role:
        raise ValueError(
            f"expected compatibility role {expected_role!r}, got {payload.get('role')!r}"
        )
    manifest = payload.get("manifest")
    if not isinstance(manifest, Mapping):
        raise ValueError("transport compatibility control is missing manifest")
    actual_hash = aiwire_compatibility_manifest_sha256(manifest)
    if payload.get("manifest_sha256") != actual_hash:
        raise ValueError("transport compatibility manifest hash mismatch")
    try:
        check = verify_aiwire_compatibility_manifest(
            manifest,
            local_manifest=(
                local_manifest
                if local_manifest is not None
                else build_aiwire_compatibility_manifest(fallback_codecs=())
            ),
            allow_fallback=False,
        )
    except AIWireHandshakeError as exc:
        raise ValueError(str(exc)) from exc
    if not check.accepted or check.codec != "aiwire":
        raise ValueError(check.reason or "transport compatibility rejected")
    return cast(dict[str, object], check.to_dict())


def b64(payload: bytes) -> str:
    return base64.b64encode(payload).decode("ascii")


def unb64(payload: str) -> bytes:
    try:
        return base64.b64decode(payload.encode("ascii"), validate=True)
    except (UnicodeEncodeError, binascii.Error) as exc:
        raise ValueError("transport payload must be valid base64") from exc


def print_result(result: TransportDemoResult) -> None:
    print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
