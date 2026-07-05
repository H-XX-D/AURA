#!/usr/bin/env python3
"""AURA AI-to-AI wire codec.

This module provides a session-oriented codec for agent messaging streams.  It
uses Python's zlib bindings as the native deflate backend, but keeps an AURA
protocol-specific static dictionary and a live compressor history across frames.
That combination is a much better fit for small JSON agent messages than
compressing each message independently.
"""

from __future__ import annotations

import ctypes
import hashlib
import hmac
import json
import os
import secrets
import sys
import zlib
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import Any, Iterable, Mapping

from .ai_wire_messages import (
    AIWireFrame,
    build_ai_wire_messages,
    build_delta_structured_ai_messages,
    build_structured_ai_messages,
    decode_ai_wire_message,
    discover_ai_wire_session_templates,
    encode_ai_wire_message,
)

AI_WIRE_VERSION = 1
AI_WIRE_SUPPORTED_VERSIONS = (AI_WIRE_VERSION,)
AI_WIRE_PROTOCOL = "aura.aiwire"
AI_WIRE_HANDSHAKE_SCHEMA = "aura.aiwire.handshake.v1"
AI_WIRE_NEGOTIATION_SCHEMA = "aura.aiwire.negotiation.v1"
AI_WIRE_CONTROL_LUT_SCHEMA = "aura.aiwire.control_lut.v1"
AI_WIRE_SYSTEM_CONTROL_SCHEMA = "aura.aiwire.system_control.v1"
AI_WIRE_SESSION_TEMPLATE_UPDATE_SCHEMA = "aura.aiwire.session_templates.update.v1"
AI_WIRE_SESSION_DICTIONARY_STATE_SCHEMA = "aura.aiwire.session_dictionary.state.v1"
AI_WIRE_SESSION_DICTIONARY_DIFF_SCHEMA = "aura.aiwire.session_dictionary.diff.v1"
AI_WIRE_SESSION_DICTIONARY_ACK_SCHEMA = "aura.aiwire.session_dictionary.ack.v1"
AI_WIRE_SESSION_RESUME_HELLO_SCHEMA = "aura.aiwire.session_resume.hello.v1"
AI_WIRE_SESSION_RESUME_RESPONSE_SCHEMA = "aura.aiwire.session_resume.response.v1"
AI_WIRE_WBITS = -15
AI_WIRE_MEM_LEVEL = 8
AI_WIRE_DEFAULT_LEVEL = 3
AI_WIRE_FLUSH_MODE = "z_sync_flush"
AI_WIRE_SYNC_FLUSH_SUFFIX = b"\x00\x00\xff\xff"
AI_WIRE_FALLBACK_CODECS = ("zlib", "raw")
AI_WIRE_DELTA_VERSION = 1
AI_WIRE_MAX_SESSION_TEMPLATES = 4096
AI_WIRE_MAX_SESSION_DICTIONARY_DIFF_ADDITIONS = 128
AI_WIRE_MAX_SESSION_TEMPLATE_BYTES = 4096
AI_WIRE_MAX_SESSION_DICTIONARY_BYTES = 262144
AI_WIRE_MAX_CONTROL_LUT_ENTRIES = 1024
AI_WIRE_NONCE_BYTES = 16
AI_WIRE_MISSION_CRITICAL = "mission_critical"
AI_WIRE_ROUTINE_CONTROL_CRITICALITIES = ("routine", "important")
AI_WIRE_MISSION_CRITICAL_CONTROL_TYPES = frozenset(
    {
        "handshake_accept",
        "handshake_reject",
        "dictionary_update",
        "epoch_reset",
        "resync_required",
        "auth_failure",
        "safety_policy",
        "key_rotation",
        "emergency_stop",
        "critical_route_authority",
        "critical_verification_failure",
    }
)


_COMMON_AI_JSON_TERMS: tuple[str, ...] = (
    # Generic JSON-RPC / tool-call scaffolding.
    '"jsonrpc":"2.0"',
    '"id":',
    '"method":',
    '"params":',
    '"result":',
    '"error":',
    '"name":',
    '"arguments":',
    '"metadata":',
    '"trace_id":',
    '"task_id":',
    '"session_id":',
    '"call_id":',
    '"tool_call_id":',
    '"content":',
    '"structuredContent":',
    '"isError":false',
    '"type":"text"',
    '"kind":"text"',
    '"text":',
    '"role":"user"',
    '"role":"agent"',
    '"role":"assistant"',
    '"role":"system"',
    '"parts":[{"kind":"text","text":',
    # OpenAI Responses / function-calling shaped traffic.
    '"protocol":"openai.responses"',
    '"operation":"responses.create"',
    '"model":',
    '"input":',
    '"tools":',
    '"type":"function"',
    '"type":"function_call"',
    '"response.output_item.done"',
    '"parameters":',
    '"properties":',
    '"required":',
    '"description":',
    '"additionalProperties":false',
    '"text":{"format":{"type":"json_schema"',
    '"type":"json_schema"',
    '"strict":true',
    '"output_json"',
    # MCP shaped traffic.
    '"protocol":"mcp"',
    '"method":"initialize"',
    '"method":"tools/list"',
    '"method":"tools/call"',
    '"method":"resources/read"',
    '"method":"prompts/get"',
    '"method":"sampling/createMessage"',
    '"notifications/tools/list_changed"',
    '"io.modelcontextprotocol/protocolVersion"',
    '"io.modelcontextprotocol/clientInfo"',
    '"io.modelcontextprotocol/clientCapabilities"',
    '"resultType":"complete"',
    '"tools":',
    '"inputSchema":',
    '"ttlMs":300000',
    '"cacheScope":"public"',
    '"resources/read"',
    '"prompts/get"',
    '"sampling/createMessage"',
    '"uri":',
    '"line_start":',
    '"line_end":',
    '"matches":',
    '"file":',
    '"line":',
    '"score":',
    # A2A shaped traffic.
    '"protocol":"a2a"',
    '"method":"message/send"',
    '"method":"message/stream"',
    '"method":"tasks/get"',
    '"event":"TaskStatusUpdateEvent"',
    '"event":"TaskArtifactUpdateEvent"',
    '"message":',
    '"messageId":',
    '"contextId":',
    '"taskId":',
    '"status":',
    '"state":"submitted"',
    '"state":"working"',
    '"state":"input_required"',
    '"state":"completed"',
    '"artifacts":',
    '"artifactId":',
    '"historyLength":',
    '"acceptedOutputModes":',
    '"lastChunk":',
    '"append":true',
    # Local agent runtime / broker-shaped traffic.
    '"protocol":"local.agent"',
    '"schema":"local.agent.broker.envelope.v1"',
    '"schema":"local.agent.session.handshake.v1"',
    '"schema":"local.agent.delta.status.v1"',
    '"schema":"local.agent.delta.tool_result.v1"',
    '"schema":"local.agent.route_hint.v1"',
    '"partition":',
    '"offset":',
    '"headers":',
    '"route":',
    '"codec":"aura.aiwire"',
    '"delta":',
    '"op":"replace"',
    '"op":"append"',
    '"clock":',
    '"lamport":',
    '"route_before_decompress":true',
    '"requires_decompression":false',
    '"hash_modifiers":',
    '"session_template_update"',
    # Agent runtime traces and handoffs.
    '"protocol":"agent.trace"',
    '"protocol":"agent.handoff"',
    '"protocol":"agent.review"',
    '"protocol":"agent.final"',
    '"event":"plan.created"',
    '"agent":',
    '"from":',
    '"to":',
    '"handoff":',
    '"working_memory":',
    '"facts":',
    '"open_questions":',
    '"requested_output_schema":',
    '"objective":',
    '"constraints":',
    '"subgoals":',
    '"evidence":',
    '"confidence":',
    '"verdict":',
    '"comments":',
    '"severity":',
    '"answer":',
    '"summary":',
    '"actions":',
    # Common operational vocabulary in AI-to-AI engineering messages.
    "latency regression",
    "tail latency",
    "retry budget",
    "retry fanout",
    "patch validation",
    "verified evidence",
    "session template",
    "recurring message shape",
    "bandwidth",
    "structured output",
    "function_call_output",
    "deployment",
    "repository",
    "service",
    "trace",
    "planner",
    "researcher",
    "coder",
    "reviewer",
    "executor",
    "summarizer",
)


def _build_static_dictionary() -> bytes:
    """Build a zlib dictionary with high-value substrings near the end."""

    generic_json = (
        "{}[],:"
        '"protocol":'
        '"operation":'
        '"tenant":'
        '"priority":'
        '"repository":'
        '"path":'
        '"query":'
        '"limit":'
        '"output":'
        '"rows":'
        '"timestamp":'
        '"level":'
        '"message":'
    )
    ordered_terms = [generic_json, *_COMMON_AI_JSON_TERMS]
    dictionary = "\n".join(ordered_terms)

    # Repeat the terms so short fragments also appear in the final 32 KiB zlib
    # dictionary window.  zlib gives more weight to terms at the end.
    repeated = (dictionary + "\n") * 12
    return repeated.encode("utf-8")[-32768:]


AI_WIRE_STATIC_DICTIONARY = _build_static_dictionary()
AI_WIRE_DICTIONARY_SHA256 = hashlib.sha256(AI_WIRE_STATIC_DICTIONARY).hexdigest()

AIWireSessionTemplates = Mapping[int, str] | Iterable[tuple[int, str] | Mapping[str, Any]]
AIWireControlLUTEntries = Iterable[Any]
AIWireAuthKey = bytes | bytearray | memoryview | str | None


def normalize_aiwire_session_templates(
    session_templates: AIWireSessionTemplates | None = None,
) -> tuple[tuple[int, str], ...]:
    """Return a deterministic ``(template_id, pattern)`` tuple for session use."""

    if session_templates is None:
        return ()

    items: Iterable[Any]
    if isinstance(session_templates, Mapping):
        items = session_templates.items()
    else:
        items = session_templates

    normalized: list[tuple[int, str]] = []
    seen: set[int] = set()
    for item in items:
        if isinstance(item, Mapping):
            template_id = int(item.get("template_id", item.get("id")))  # type: ignore[arg-type]
            pattern = str(item.get("pattern", item.get("template", "")))
        else:
            template_id = int(item[0])
            pattern = str(item[1])

        if template_id in seen:
            raise ValueError(f"duplicate AIWire session template id: {template_id}")
        if not 0 <= template_id <= 65535:
            raise ValueError(f"AIWire session template id out of uint16 range: {template_id}")
        if not pattern:
            raise ValueError(f"AIWire session template {template_id} has an empty pattern")
        seen.add(template_id)
        normalized.append((template_id, pattern))

    return tuple(sorted(normalized, key=lambda entry: entry[0]))


def aiwire_session_templates_sha256(
    session_templates: AIWireSessionTemplates | None = None,
) -> str:
    """Hash session templates in canonical order for handshake comparison."""

    normalized = normalize_aiwire_session_templates(session_templates)
    if not normalized:
        return ""
    payload = json.dumps(
        [{"template_id": template_id, "pattern": pattern} for template_id, pattern in normalized],
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _validate_sha256_hex(value: str, field_name: str) -> None:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise AIWireHandshakeError(f"{field_name} must be a lowercase sha256 hex digest")


def _auth_key_bytes(auth_key: AIWireAuthKey) -> bytes | None:
    if auth_key is None:
        return None
    if isinstance(auth_key, str):
        return auth_key.encode("utf-8")
    if isinstance(auth_key, (bytes, bytearray, memoryview)):
        return bytes(auth_key)
    raise TypeError(f"unsupported AIWire auth key type: {type(auth_key).__name__}")


def _sign_aiwire_payload(payload: Mapping[str, Any], auth_key: AIWireAuthKey) -> str:
    key = _auth_key_bytes(auth_key)
    if key is None:
        return ""
    return hmac.new(key, _canonical_json_bytes(payload), hashlib.sha256).hexdigest()


def _verify_aiwire_payload_auth(
    payload: Mapping[str, Any],
    auth_tag: str,
    auth_key: AIWireAuthKey,
    context: str,
) -> None:
    key = _auth_key_bytes(auth_key)
    if key is None:
        return
    expected = hmac.new(key, _canonical_json_bytes(payload), hashlib.sha256).hexdigest()
    if not auth_tag or not hmac.compare_digest(expected, auth_tag):
        raise AIWireHandshakeError(f"{context} auth tag mismatch")


def _make_aiwire_nonce() -> str:
    return secrets.token_hex(AI_WIRE_NONCE_BYTES)


def _validate_aiwire_nonce(value: str, field_name: str = "nonce") -> None:
    expected_length = AI_WIRE_NONCE_BYTES * 2
    if len(value) != expected_length or any(char not in "0123456789abcdef" for char in value):
        raise AIWireHandshakeError(
            f"{field_name} must be {expected_length} lowercase hex characters"
        )


def _parse_lut_code(value: int | str) -> int:
    if isinstance(value, str):
        text = value.lower()
        code = int(text, 16) if text.startswith("0x") else int(text)
    else:
        code = int(value)
    if not 0 <= code <= 65535:
        raise AIWireHandshakeError(f"control LUT code out of uint16 range: {code}")
    return code


def _format_lut_code(code: int) -> str:
    return f"0x{code:04x}"


@dataclass(frozen=True)
class AIWireControlLUTEntry:
    """Handshake-pinned compact representation for noncritical control messages."""

    code: int
    meaning: str
    payload_schema: str = ""
    criticality: str = "routine"

    def __post_init__(self) -> None:
        _parse_lut_code(self.code)
        if not self.meaning:
            raise AIWireHandshakeError("control LUT meaning must be non-empty")
        if self.criticality == AI_WIRE_MISSION_CRITICAL:
            raise AIWireHandshakeError(
                "mission-critical control messages must use system control messages"
            )
        if self.criticality not in AI_WIRE_ROUTINE_CONTROL_CRITICALITIES:
            raise AIWireHandshakeError(f"unsupported control LUT criticality: {self.criticality}")

    def to_dict(self) -> dict[str, object]:
        return {
            "code": _format_lut_code(self.code),
            "meaning": self.meaning,
            "payload_schema": self.payload_schema,
            "criticality": self.criticality,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "AIWireControlLUTEntry":
        try:
            return cls(
                code=_parse_lut_code(value["code"]),
                meaning=str(value["meaning"]),
                payload_schema=str(value.get("payload_schema", "")),
                criticality=str(value.get("criticality", "routine")),
            )
        except (KeyError, TypeError, ValueError, AIWireHandshakeError) as exc:
            raise AIWireHandshakeError(f"malformed AIWire control LUT entry: {exc}") from exc


@dataclass(frozen=True)
class AIWireControlLUTFrame:
    """Decoded routine-control LUT frame.

    The wire form is compact by design: two big-endian bytes for the LUT code
    followed by an optional canonical JSON payload mapping.
    """

    code: int
    meaning: str
    payload: Mapping[str, Any]
    payload_schema: str = ""
    criticality: str = "routine"

    def to_dict(self) -> dict[str, object]:
        return {
            "code": _format_lut_code(self.code),
            "meaning": self.meaning,
            "payload": dict(self.payload),
            "payload_schema": self.payload_schema,
            "criticality": self.criticality,
        }


def normalize_aiwire_control_lut(
    entries: AIWireControlLUTEntries | None = None,
) -> tuple[AIWireControlLUTEntry, ...]:
    """Return a deterministic routine-control LUT for handshake hashing."""

    if entries is None:
        return ()

    normalized: list[AIWireControlLUTEntry] = []
    seen_codes: set[int] = set()
    seen_meanings: set[str] = set()
    for item in entries:
        if isinstance(item, AIWireControlLUTEntry):
            entry = item
        elif isinstance(item, Mapping):
            entry = AIWireControlLUTEntry.from_dict(item)
        else:
            entry = AIWireControlLUTEntry(code=_parse_lut_code(item[0]), meaning=str(item[1]))

        if entry.code in seen_codes:
            raise AIWireHandshakeError(f"duplicate control LUT code: {_format_lut_code(entry.code)}")
        if entry.meaning in seen_meanings:
            raise AIWireHandshakeError(f"duplicate control LUT meaning: {entry.meaning}")
        seen_codes.add(entry.code)
        seen_meanings.add(entry.meaning)
        normalized.append(entry)

    if len(normalized) > AI_WIRE_MAX_CONTROL_LUT_ENTRIES:
        raise AIWireHandshakeError("control LUT entry limit exceeded")
    return tuple(sorted(normalized, key=lambda entry: entry.code))


def aiwire_control_lut_sha256(entries: AIWireControlLUTEntries | None = None) -> str:
    """Hash a routine-control LUT in canonical order for handshake comparison."""

    normalized = normalize_aiwire_control_lut(entries)
    if not normalized:
        return ""
    payload = {
        "schema": AI_WIRE_CONTROL_LUT_SCHEMA,
        "protocol": AI_WIRE_PROTOCOL,
        "entries": [entry.to_dict() for entry in normalized],
    }
    return _sha256_hex(_canonical_json_bytes(payload))


def _control_lut_entry_by_code(
    entries: AIWireControlLUTEntries,
    code: int,
) -> AIWireControlLUTEntry:
    normalized = normalize_aiwire_control_lut(entries)
    for entry in normalized:
        if entry.code == code:
            return entry
    raise AIWireHandshakeError(f"unknown control LUT code: {_format_lut_code(code)}")


def _control_lut_entry_by_meaning(
    entries: AIWireControlLUTEntries,
    meaning: str,
) -> AIWireControlLUTEntry:
    normalized = normalize_aiwire_control_lut(entries)
    for entry in normalized:
        if entry.meaning == meaning:
            return entry
    raise AIWireHandshakeError(f"unknown control LUT meaning: {meaning}")


def _control_frame_bytes(frame: bytes | bytearray | memoryview | str) -> bytes:
    if isinstance(frame, str):
        text = frame.strip().lower()
        if text.startswith("0x"):
            text = text[2:]
        text = "".join(char for char in text if not char.isspace() and char not in ":-_")
        try:
            return bytes.fromhex(text)
        except ValueError as exc:
            raise AIWireHandshakeError(f"malformed control LUT frame hex: {exc}") from exc
    if isinstance(frame, (bytes, bytearray, memoryview)):
        return bytes(frame)
    raise TypeError(f"unsupported control LUT frame type: {type(frame).__name__}")


def encode_aiwire_control_lut_frame(
    entries: AIWireControlLUTEntries,
    *,
    meaning: str | None = None,
    code: int | str | None = None,
    payload: Mapping[str, Any] | None = None,
) -> bytes:
    """Encode a routine-control LUT frame as compact bytes.

    ``entries`` must be the same routine-control LUT proven during handshake.
    Mission-critical controls are not valid LUT entries and must use
    ``AIWireSystemControlMessage`` instead.
    """

    if (meaning is None) == (code is None):
        raise AIWireHandshakeError("provide exactly one of meaning or code")
    entry = (
        _control_lut_entry_by_meaning(entries, meaning)
        if meaning is not None
        else _control_lut_entry_by_code(entries, _parse_lut_code(code))  # type: ignore[arg-type]
    )
    if entry.criticality == AI_WIRE_MISSION_CRITICAL:
        raise AIWireHandshakeError("mission-critical control must use system control messages")
    if payload is not None and not isinstance(payload, Mapping):
        raise AIWireHandshakeError("control LUT payload must be a mapping")

    payload_bytes = b"" if not payload else _canonical_json_bytes(payload)
    return entry.code.to_bytes(2, "big") + payload_bytes


def aiwire_control_lut_frame_hex(frame: bytes | bytearray | memoryview | str) -> str:
    """Return a display-safe hexadecimal control LUT frame string."""

    return "0x" + _control_frame_bytes(frame).hex()


def decode_aiwire_control_lut_frame(
    entries: AIWireControlLUTEntries,
    frame: bytes | bytearray | memoryview | str,
) -> AIWireControlLUTFrame:
    """Decode a compact routine-control LUT frame using the handshaked LUT."""

    raw = _control_frame_bytes(frame)
    if len(raw) < 2:
        raise AIWireHandshakeError("control LUT frame is too short")
    code = int.from_bytes(raw[:2], "big")
    entry = _control_lut_entry_by_code(entries, code)
    payload_bytes = raw[2:]
    if payload_bytes:
        try:
            payload = json.loads(payload_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AIWireHandshakeError(f"malformed control LUT payload: {exc}") from exc
        if not isinstance(payload, Mapping):
            raise AIWireHandshakeError("control LUT payload must decode to a mapping")
        payload = dict(payload)
    else:
        payload = {}
    return AIWireControlLUTFrame(
        code=entry.code,
        meaning=entry.meaning,
        payload=payload,
        payload_schema=entry.payload_schema,
        criticality=entry.criticality,
    )


@dataclass(frozen=True)
class AIWireSystemControlMessage:
    """Self-describing mission-critical control message.

    These messages intentionally do not depend on the mutable session template
    dictionary or compact control LUT. Unknown mission-critical messages fail
    closed at parse time.
    """

    control_type: str
    session_id: str
    epoch: int
    sequence: int
    payload: Mapping[str, Any]
    nonce: str
    state_hash: str | None = None
    auth_tag: str = ""

    def to_unsigned_dict(self) -> dict[str, object]:
        return {
            "schema": AI_WIRE_SYSTEM_CONTROL_SCHEMA,
            "protocol": AI_WIRE_PROTOCOL,
            "lane": "control",
            "criticality": AI_WIRE_MISSION_CRITICAL,
            "control_type": self.control_type,
            "session_id": self.session_id,
            "epoch": self.epoch,
            "sequence": self.sequence,
            "nonce": self.nonce,
            "state_hash": self.state_hash,
            "payload": dict(self.payload),
        }

    def to_dict(self) -> dict[str, object]:
        payload = self.to_unsigned_dict()
        payload["auth_tag"] = self.auth_tag
        return payload

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "AIWireSystemControlMessage":
        if value.get("schema") != AI_WIRE_SYSTEM_CONTROL_SCHEMA:
            raise AIWireHandshakeError("unsupported AIWire system control schema")
        if value.get("protocol") != AI_WIRE_PROTOCOL:
            raise AIWireHandshakeError("unsupported AIWire protocol")
        if value.get("lane") != "control":
            raise AIWireHandshakeError("AIWire system control lane must be control")
        if value.get("criticality") != AI_WIRE_MISSION_CRITICAL:
            raise AIWireHandshakeError("AIWire system control must be mission critical")

        try:
            control_type = str(value["control_type"])
            if control_type not in AI_WIRE_MISSION_CRITICAL_CONTROL_TYPES:
                raise AIWireHandshakeError(f"unknown mission-critical control type: {control_type}")
            nonce = str(value["nonce"])
            _validate_aiwire_nonce(nonce)
            state_hash = str(value["state_hash"]) if value.get("state_hash") is not None else None
            if state_hash is not None:
                _validate_sha256_hex(state_hash, "state_hash")
            payload = value.get("payload", {})
            if not isinstance(payload, Mapping):
                raise AIWireHandshakeError("system control payload must be a mapping")
            epoch = int(value["epoch"])
            sequence = int(value["sequence"])
            if epoch < 0:
                raise AIWireHandshakeError("system control epoch must be non-negative")
            if sequence < 0:
                raise AIWireHandshakeError("system control sequence must be non-negative")
            return cls(
                control_type=control_type,
                session_id=str(value["session_id"]),
                epoch=epoch,
                sequence=sequence,
                payload=dict(payload),
                nonce=nonce,
                state_hash=state_hash,
                auth_tag=str(value.get("auth_tag", "")),
            )
        except (KeyError, TypeError, ValueError, AIWireHandshakeError) as exc:
            raise AIWireHandshakeError(f"malformed AIWire system control message: {exc}") from exc


def build_aiwire_system_control_message(
    *,
    control_type: str,
    session_id: str,
    epoch: int,
    sequence: int,
    payload: Mapping[str, Any] | None = None,
    state_hash: str | None = None,
    auth_key: AIWireAuthKey = None,
    nonce: str | None = None,
) -> AIWireSystemControlMessage:
    """Build and optionally authenticate a mission-critical system control message."""

    message = AIWireSystemControlMessage(
        control_type=control_type,
        session_id=session_id,
        epoch=epoch,
        sequence=sequence,
        payload=dict(payload or {}),
        nonce=nonce or _make_aiwire_nonce(),
        state_hash=state_hash,
    )
    parsed = AIWireSystemControlMessage.from_dict(message.to_dict())
    auth_tag = _sign_aiwire_payload(parsed.to_unsigned_dict(), auth_key)
    return AIWireSystemControlMessage(
        control_type=parsed.control_type,
        session_id=parsed.session_id,
        epoch=parsed.epoch,
        sequence=parsed.sequence,
        payload=parsed.payload,
        nonce=parsed.nonce,
        state_hash=parsed.state_hash,
        auth_tag=auth_tag,
    )


def verify_aiwire_system_control_message(
    message: Mapping[str, Any] | AIWireSystemControlMessage,
    *,
    auth_key: AIWireAuthKey = None,
) -> AIWireSystemControlMessage:
    """Parse and verify a mission-critical system control message."""

    parsed = (
        message
        if isinstance(message, AIWireSystemControlMessage)
        else AIWireSystemControlMessage.from_dict(message)
    )
    _verify_aiwire_payload_auth(
        parsed.to_unsigned_dict(),
        parsed.auth_tag,
        auth_key,
        "AIWire system control",
    )
    return parsed


def _template_pattern_sha256(pattern: str) -> str:
    return _sha256_hex(pattern.encode("utf-8"))


def _validate_session_dictionary_bounds(
    session_templates: tuple[tuple[int, str], ...],
    *,
    max_templates: int = AI_WIRE_MAX_SESSION_TEMPLATES,
    max_template_bytes: int = AI_WIRE_MAX_SESSION_TEMPLATE_BYTES,
    max_total_bytes: int = AI_WIRE_MAX_SESSION_DICTIONARY_BYTES,
) -> None:
    if len(session_templates) > max_templates:
        raise AIWireHandshakeError("session dictionary template limit exceeded")

    total_bytes = 0
    for template_id, pattern in session_templates:
        pattern_size = len(pattern.encode("utf-8"))
        if pattern_size > max_template_bytes:
            raise AIWireHandshakeError(
                f"session dictionary template {template_id} exceeds byte limit"
            )
        total_bytes += pattern_size

    if total_bytes > max_total_bytes:
        raise AIWireHandshakeError("session dictionary total byte limit exceeded")


def _session_dictionary_state_payload(
    session_templates: AIWireSessionTemplates | None,
    *,
    epoch: int,
    static_dictionary_sha256: str = AI_WIRE_DICTIONARY_SHA256,
) -> dict[str, object]:
    if epoch < 0:
        raise AIWireHandshakeError("session dictionary epoch must be non-negative")
    _validate_sha256_hex(static_dictionary_sha256, "static_dictionary_sha256")
    normalized = normalize_aiwire_session_templates(session_templates)
    _validate_session_dictionary_bounds(normalized)
    return {
        "schema": AI_WIRE_SESSION_DICTIONARY_STATE_SCHEMA,
        "protocol": AI_WIRE_PROTOCOL,
        "version": AI_WIRE_VERSION,
        "delta_version": AI_WIRE_DELTA_VERSION,
        "static_dictionary_sha256": static_dictionary_sha256,
        "epoch": epoch,
        "templates": [
            {
                "template_id": template_id,
                "pattern": pattern,
                "pattern_sha256": _template_pattern_sha256(pattern),
            }
            for template_id, pattern in normalized
        ],
    }


def aiwire_session_dictionary_state_sha256(
    session_templates: AIWireSessionTemplates | None = None,
    *,
    epoch: int = 0,
    static_dictionary_sha256: str = AI_WIRE_DICTIONARY_SHA256,
) -> str:
    """Hash the authenticated session dictionary state for delta safety."""

    return _sha256_hex(
        _canonical_json_bytes(
            _session_dictionary_state_payload(
                session_templates,
                epoch=epoch,
                static_dictionary_sha256=static_dictionary_sha256,
            )
        )
    )


@dataclass(frozen=True)
class AIWireSessionTemplateUpdate:
    """Delta signal for synchronizing session templates between AIWire epochs.

    zlib dictionaries are fixed when a stream starts.  Applying this update
    changes the session-template map for the next negotiated compression epoch;
    callers must reset/recreate encoders and decoders before relying on the new
    templates for compression.
    """

    previous_sha256: str
    next_sha256: str
    previous_count: int
    next_count: int
    add_or_update: tuple[tuple[int, str], ...]
    remove: tuple[int, ...]
    epoch: int
    requires_session_reset: bool = True

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": AI_WIRE_SESSION_TEMPLATE_UPDATE_SCHEMA,
            "protocol": AI_WIRE_PROTOCOL,
            "previous_sha256": self.previous_sha256,
            "next_sha256": self.next_sha256,
            "previous_count": self.previous_count,
            "next_count": self.next_count,
            "add_or_update": [
                {"template_id": template_id, "pattern": pattern}
                for template_id, pattern in self.add_or_update
            ],
            "remove": list(self.remove),
            "epoch": self.epoch,
            "requires_session_reset": self.requires_session_reset,
        }

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> "AIWireSessionTemplateUpdate":
        if value.get("schema") != AI_WIRE_SESSION_TEMPLATE_UPDATE_SCHEMA:
            raise AIWireHandshakeError("unsupported AIWire session template update schema")
        if value.get("protocol") != AI_WIRE_PROTOCOL:
            raise AIWireHandshakeError("unsupported AIWire protocol")

        try:
            add_or_update = normalize_aiwire_session_templates(value.get("add_or_update", ()))
            remove = tuple(sorted(int(template_id) for template_id in value.get("remove", ())))
            return cls(
                previous_sha256=str(value["previous_sha256"]),
                next_sha256=str(value["next_sha256"]),
                previous_count=int(value["previous_count"]),
                next_count=int(value["next_count"]),
                add_or_update=add_or_update,
                remove=remove,
                epoch=int(value.get("epoch", 0)),
                requires_session_reset=bool(value.get("requires_session_reset", True)),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise AIWireHandshakeError(f"malformed AIWire session template update: {exc}") from exc


def build_aiwire_session_template_update(
    current_templates: AIWireSessionTemplates | None,
    next_templates: AIWireSessionTemplates | None,
    *,
    epoch: int = 0,
) -> AIWireSessionTemplateUpdate:
    """Build a delta signal from one session-template map to another."""

    current = dict(normalize_aiwire_session_templates(current_templates))
    desired = dict(normalize_aiwire_session_templates(next_templates))
    add_or_update = tuple(
        sorted(
            (
                (template_id, pattern)
                for template_id, pattern in desired.items()
                if current.get(template_id) != pattern
            ),
            key=lambda entry: entry[0],
        )
    )
    remove = tuple(sorted(template_id for template_id in current if template_id not in desired))
    return AIWireSessionTemplateUpdate(
        previous_sha256=aiwire_session_templates_sha256(current),
        next_sha256=aiwire_session_templates_sha256(desired),
        previous_count=len(current),
        next_count=len(desired),
        add_or_update=add_or_update,
        remove=remove,
        epoch=epoch,
        requires_session_reset=True,
    )


def apply_aiwire_session_template_update(
    current_templates: AIWireSessionTemplates | None,
    update: AIWireSessionTemplateUpdate | dict[str, object],
) -> tuple[tuple[int, str], ...]:
    """Apply and verify a session-template delta signal."""

    parsed = (
        update
        if isinstance(update, AIWireSessionTemplateUpdate)
        else AIWireSessionTemplateUpdate.from_dict(update)
    )
    current = dict(normalize_aiwire_session_templates(current_templates))
    if aiwire_session_templates_sha256(current) != parsed.previous_sha256:
        raise AIWireHandshakeError("session template update previous hash mismatch")
    if len(current) != parsed.previous_count:
        raise AIWireHandshakeError("session template update previous count mismatch")

    for template_id in parsed.remove:
        current.pop(template_id, None)
    for template_id, pattern in parsed.add_or_update:
        current[template_id] = pattern

    normalized = normalize_aiwire_session_templates(current)
    if aiwire_session_templates_sha256(normalized) != parsed.next_sha256:
        raise AIWireHandshakeError("session template update next hash mismatch")
    if len(normalized) != parsed.next_count:
        raise AIWireHandshakeError("session template update next count mismatch")
    return normalized


def _dictionary_diff_id_payload(value: Mapping[str, Any]) -> dict[str, object]:
    payload = dict(value)
    payload.pop("auth_tag", None)
    payload.pop("diff_id", None)
    return payload


def _dictionary_diff_id(value: Mapping[str, Any]) -> str:
    return _sha256_hex(_canonical_json_bytes(_dictionary_diff_id_payload(value)))


def _verify_session_dictionary_diff_identity(diff: "AIWireSessionDictionaryDiff") -> None:
    if diff.diff_id != _dictionary_diff_id(diff.to_dict()):
        raise AIWireHandshakeError("session dictionary diff_id mismatch")


@dataclass(frozen=True)
class AIWireSessionDictionaryDiff:
    """Authenticated append-only session dictionary update proposal.

    A diff is only a proposal until the receiver validates it and returns a
    matching ACK.  Senders must not encode deltas against ``next_state_hash``
    until that ACK has been verified.
    """

    session_id: str
    epoch: int
    previous_state_hash: str
    next_state_hash: str
    previous_count: int
    next_count: int
    additions: tuple[tuple[int, str], ...]
    nonce: str
    diff_id: str
    auth_tag: str = ""

    def to_unsigned_dict(self) -> dict[str, object]:
        return {
            "schema": AI_WIRE_SESSION_DICTIONARY_DIFF_SCHEMA,
            "protocol": AI_WIRE_PROTOCOL,
            "session_id": self.session_id,
            "epoch": self.epoch,
            "previous_state_hash": self.previous_state_hash,
            "next_state_hash": self.next_state_hash,
            "previous_count": self.previous_count,
            "next_count": self.next_count,
            "additions": [
                {
                    "template_id": template_id,
                    "pattern": pattern,
                    "pattern_sha256": _template_pattern_sha256(pattern),
                }
                for template_id, pattern in self.additions
            ],
            "nonce": self.nonce,
            "diff_id": self.diff_id,
            "delta_version": AI_WIRE_DELTA_VERSION,
        }

    def to_dict(self) -> dict[str, object]:
        payload = self.to_unsigned_dict()
        payload["auth_tag"] = self.auth_tag
        return payload

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> "AIWireSessionDictionaryDiff":
        if value.get("schema") != AI_WIRE_SESSION_DICTIONARY_DIFF_SCHEMA:
            raise AIWireHandshakeError("unsupported AIWire session dictionary diff schema")
        if value.get("protocol") != AI_WIRE_PROTOCOL:
            raise AIWireHandshakeError("unsupported AIWire protocol")
        if int(value.get("delta_version", 0)) != AI_WIRE_DELTA_VERSION:
            raise AIWireHandshakeError("unsupported AIWire delta version")

        try:
            additions = normalize_aiwire_session_templates(value.get("additions", ()))
            _validate_session_dictionary_bounds(additions)
            for template_id, pattern in additions:
                pattern_hash = next(
                    item.get("pattern_sha256")
                    for item in value.get("additions", ())  # type: ignore[union-attr]
                    if int(item.get("template_id")) == template_id  # type: ignore[union-attr,arg-type]
                )
                if str(pattern_hash) != _template_pattern_sha256(pattern):
                    raise AIWireHandshakeError("session dictionary addition hash mismatch")

            previous_state_hash = str(value["previous_state_hash"])
            next_state_hash = str(value["next_state_hash"])
            diff_id = str(value["diff_id"])
            _validate_sha256_hex(previous_state_hash, "previous_state_hash")
            _validate_sha256_hex(next_state_hash, "next_state_hash")
            _validate_sha256_hex(diff_id, "diff_id")
            expected_diff_id = _dictionary_diff_id(value)
            if diff_id != expected_diff_id:
                raise AIWireHandshakeError("session dictionary diff_id mismatch")

            return cls(
                session_id=str(value["session_id"]),
                epoch=int(value["epoch"]),
                previous_state_hash=previous_state_hash,
                next_state_hash=next_state_hash,
                previous_count=int(value["previous_count"]),
                next_count=int(value["next_count"]),
                additions=additions,
                nonce=str(value["nonce"]),
                diff_id=diff_id,
                auth_tag=str(value.get("auth_tag", "")),
            )
        except (KeyError, TypeError, ValueError, StopIteration, AIWireHandshakeError) as exc:
            raise AIWireHandshakeError(f"malformed AIWire session dictionary diff: {exc}") from exc


@dataclass(frozen=True)
class AIWireSessionDictionaryAck:
    """Receiver ACK/NACK for a session dictionary diff."""

    session_id: str
    epoch: int
    accepted: bool
    diff_id: str
    previous_state_hash: str
    state_hash: str
    reason: str | None
    nonce: str
    auth_tag: str = ""

    def to_unsigned_dict(self) -> dict[str, object]:
        return {
            "schema": AI_WIRE_SESSION_DICTIONARY_ACK_SCHEMA,
            "protocol": AI_WIRE_PROTOCOL,
            "session_id": self.session_id,
            "epoch": self.epoch,
            "accepted": self.accepted,
            "diff_id": self.diff_id,
            "previous_state_hash": self.previous_state_hash,
            "state_hash": self.state_hash,
            "reason": self.reason,
            "nonce": self.nonce,
            "delta_version": AI_WIRE_DELTA_VERSION,
        }

    def to_dict(self) -> dict[str, object]:
        payload = self.to_unsigned_dict()
        payload["auth_tag"] = self.auth_tag
        return payload

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> "AIWireSessionDictionaryAck":
        if value.get("schema") != AI_WIRE_SESSION_DICTIONARY_ACK_SCHEMA:
            raise AIWireHandshakeError("unsupported AIWire session dictionary ACK schema")
        if value.get("protocol") != AI_WIRE_PROTOCOL:
            raise AIWireHandshakeError("unsupported AIWire protocol")
        if int(value.get("delta_version", 0)) != AI_WIRE_DELTA_VERSION:
            raise AIWireHandshakeError("unsupported AIWire delta version")

        try:
            diff_id = str(value["diff_id"])
            previous_state_hash = str(value["previous_state_hash"])
            state_hash = str(value["state_hash"])
            _validate_sha256_hex(diff_id, "diff_id")
            _validate_sha256_hex(previous_state_hash, "previous_state_hash")
            _validate_sha256_hex(state_hash, "state_hash")
            return cls(
                session_id=str(value["session_id"]),
                epoch=int(value["epoch"]),
                accepted=bool(value["accepted"]),
                diff_id=diff_id,
                previous_state_hash=previous_state_hash,
                state_hash=state_hash,
                reason=(str(value["reason"]) if value.get("reason") is not None else None),
                nonce=str(value["nonce"]),
                auth_tag=str(value.get("auth_tag", "")),
            )
        except (KeyError, TypeError, ValueError, AIWireHandshakeError) as exc:
            raise AIWireHandshakeError(f"malformed AIWire session dictionary ACK: {exc}") from exc


@dataclass(frozen=True)
class AIWireSessionResumeHello:
    """Future-connection proof that a peer has cached session dictionary state."""

    peer_id: str
    app_namespace: str
    static_dictionary_sha256: str
    cached_state_hashes: tuple[str, ...]
    supported_delta_versions: tuple[int, ...]
    nonce: str
    auth_tag: str = ""

    def to_unsigned_dict(self) -> dict[str, object]:
        return {
            "schema": AI_WIRE_SESSION_RESUME_HELLO_SCHEMA,
            "protocol": AI_WIRE_PROTOCOL,
            "peer_id": self.peer_id,
            "app_namespace": self.app_namespace,
            "static_dictionary_sha256": self.static_dictionary_sha256,
            "cached_state_hashes": list(self.cached_state_hashes),
            "supported_delta_versions": list(self.supported_delta_versions),
            "nonce": self.nonce,
        }

    def to_dict(self) -> dict[str, object]:
        payload = self.to_unsigned_dict()
        payload["auth_tag"] = self.auth_tag
        return payload

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> "AIWireSessionResumeHello":
        if value.get("schema") != AI_WIRE_SESSION_RESUME_HELLO_SCHEMA:
            raise AIWireHandshakeError("unsupported AIWire session resume hello schema")
        if value.get("protocol") != AI_WIRE_PROTOCOL:
            raise AIWireHandshakeError("unsupported AIWire protocol")

        try:
            static_dictionary_sha256 = str(value["static_dictionary_sha256"])
            _validate_sha256_hex(static_dictionary_sha256, "static_dictionary_sha256")
            cached_state_hashes = tuple(str(item) for item in value.get("cached_state_hashes", ()))
            for cached_hash in cached_state_hashes:
                _validate_sha256_hex(cached_hash, "cached_state_hash")
            supported_delta_versions = tuple(
                int(version) for version in value.get("supported_delta_versions", ())
            )
            return cls(
                peer_id=str(value["peer_id"]),
                app_namespace=str(value.get("app_namespace", "default")),
                static_dictionary_sha256=static_dictionary_sha256,
                cached_state_hashes=cached_state_hashes,
                supported_delta_versions=supported_delta_versions,
                nonce=str(value["nonce"]),
                auth_tag=str(value.get("auth_tag", "")),
            )
        except (KeyError, TypeError, ValueError, AIWireHandshakeError) as exc:
            raise AIWireHandshakeError(f"malformed AIWire session resume hello: {exc}") from exc


@dataclass(frozen=True)
class AIWireSessionResumeResponse:
    """Resume decision for a future agent connection."""

    accepted: bool
    reason: str | None
    resume_state_hash: str | None
    static_dictionary_sha256: str
    selected_delta_version: int | None
    hello_nonce: str
    nonce: str
    auth_tag: str = ""

    def to_unsigned_dict(self) -> dict[str, object]:
        return {
            "schema": AI_WIRE_SESSION_RESUME_RESPONSE_SCHEMA,
            "protocol": AI_WIRE_PROTOCOL,
            "accepted": self.accepted,
            "reason": self.reason,
            "resume_state_hash": self.resume_state_hash,
            "static_dictionary_sha256": self.static_dictionary_sha256,
            "selected_delta_version": self.selected_delta_version,
            "hello_nonce": self.hello_nonce,
            "nonce": self.nonce,
        }

    def to_dict(self) -> dict[str, object]:
        payload = self.to_unsigned_dict()
        payload["auth_tag"] = self.auth_tag
        return payload

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> "AIWireSessionResumeResponse":
        if value.get("schema") != AI_WIRE_SESSION_RESUME_RESPONSE_SCHEMA:
            raise AIWireHandshakeError("unsupported AIWire session resume response schema")
        if value.get("protocol") != AI_WIRE_PROTOCOL:
            raise AIWireHandshakeError("unsupported AIWire protocol")

        try:
            static_dictionary_sha256 = str(value["static_dictionary_sha256"])
            _validate_sha256_hex(static_dictionary_sha256, "static_dictionary_sha256")
            resume_state_hash = (
                str(value["resume_state_hash"])
                if value.get("resume_state_hash") is not None
                else None
            )
            if resume_state_hash is not None:
                _validate_sha256_hex(resume_state_hash, "resume_state_hash")
            selected_delta_version = (
                int(value["selected_delta_version"])
                if value.get("selected_delta_version") is not None
                else None
            )
            return cls(
                accepted=bool(value["accepted"]),
                reason=(str(value["reason"]) if value.get("reason") is not None else None),
                resume_state_hash=resume_state_hash,
                static_dictionary_sha256=static_dictionary_sha256,
                selected_delta_version=selected_delta_version,
                hello_nonce=str(value["hello_nonce"]),
                nonce=str(value["nonce"]),
                auth_tag=str(value.get("auth_tag", "")),
            )
        except (KeyError, TypeError, ValueError, AIWireHandshakeError) as exc:
            raise AIWireHandshakeError(f"malformed AIWire session resume response: {exc}") from exc


def build_aiwire_session_dictionary_diff(
    current_templates: AIWireSessionTemplates | None,
    discovered_templates: AIWireSessionTemplates,
    *,
    session_id: str,
    epoch: int = 0,
    auth_key: AIWireAuthKey = None,
    nonce: str | None = None,
) -> AIWireSessionDictionaryDiff:
    """Build a safe append-only dictionary diff from discovered templates.

    Existing IDs may be repeated only when the pattern is identical.  A changed
    shape must receive a new template ID so old deltas keep a stable meaning.
    """

    current = dict(normalize_aiwire_session_templates(current_templates))
    discovered = dict(normalize_aiwire_session_templates(discovered_templates))
    _validate_session_dictionary_bounds(normalize_aiwire_session_templates(current))
    _validate_session_dictionary_bounds(normalize_aiwire_session_templates(discovered))

    additions: list[tuple[int, str]] = []
    for template_id, pattern in sorted(discovered.items()):
        existing = current.get(template_id)
        if existing == pattern:
            continue
        if existing is not None:
            raise AIWireHandshakeError(
                f"session dictionary template {template_id} already has a different shape"
            )
        additions.append((template_id, pattern))

    if not additions:
        raise AIWireHandshakeError("session dictionary diff has no additions")
    if len(additions) > AI_WIRE_MAX_SESSION_DICTIONARY_DIFF_ADDITIONS:
        raise AIWireHandshakeError("session dictionary diff addition limit exceeded")

    next_templates = normalize_aiwire_session_templates({**current, **dict(additions)})
    _validate_session_dictionary_bounds(next_templates)
    next_epoch = epoch + 1
    previous_state_hash = aiwire_session_dictionary_state_sha256(current, epoch=epoch)
    next_state_hash = aiwire_session_dictionary_state_sha256(next_templates, epoch=next_epoch)
    nonce_value = nonce or _make_aiwire_nonce()
    unsigned_without_id: dict[str, object] = {
        "schema": AI_WIRE_SESSION_DICTIONARY_DIFF_SCHEMA,
        "protocol": AI_WIRE_PROTOCOL,
        "session_id": session_id,
        "epoch": next_epoch,
        "previous_state_hash": previous_state_hash,
        "next_state_hash": next_state_hash,
        "previous_count": len(current),
        "next_count": len(next_templates),
        "additions": [
            {
                "template_id": template_id,
                "pattern": pattern,
                "pattern_sha256": _template_pattern_sha256(pattern),
            }
            for template_id, pattern in additions
        ],
        "nonce": nonce_value,
        "delta_version": AI_WIRE_DELTA_VERSION,
    }
    diff_id = _sha256_hex(_canonical_json_bytes(unsigned_without_id))
    unsigned = {**unsigned_without_id, "diff_id": diff_id}
    return AIWireSessionDictionaryDiff(
        session_id=session_id,
        epoch=next_epoch,
        previous_state_hash=previous_state_hash,
        next_state_hash=next_state_hash,
        previous_count=len(current),
        next_count=len(next_templates),
        additions=tuple(additions),
        nonce=nonce_value,
        diff_id=diff_id,
        auth_tag=_sign_aiwire_payload(unsigned, auth_key),
    )


def _build_session_dictionary_ack(
    diff: AIWireSessionDictionaryDiff,
    *,
    accepted: bool,
    state_hash: str,
    reason: str | None,
    auth_key: AIWireAuthKey,
    nonce: str | None = None,
) -> AIWireSessionDictionaryAck:
    ack_without_auth = AIWireSessionDictionaryAck(
        session_id=diff.session_id,
        epoch=diff.epoch,
        accepted=accepted,
        diff_id=diff.diff_id,
        previous_state_hash=diff.previous_state_hash,
        state_hash=state_hash,
        reason=reason,
        nonce=nonce or _make_aiwire_nonce(),
        auth_tag="",
    )
    return AIWireSessionDictionaryAck(
        **{
            **ack_without_auth.__dict__,
            "auth_tag": _sign_aiwire_payload(ack_without_auth.to_unsigned_dict(), auth_key),
        }
    )


def apply_aiwire_session_dictionary_diff(
    current_templates: AIWireSessionTemplates | None,
    diff: AIWireSessionDictionaryDiff | dict[str, object],
    *,
    current_epoch: int = 0,
    auth_key: AIWireAuthKey = None,
    replay_cache: set[str] | None = None,
    ack_nonce: str | None = None,
) -> tuple[tuple[int, str], AIWireSessionDictionaryAck]:
    """Validate, apply, and ACK a session dictionary diff proposal."""

    parsed = (
        diff
        if isinstance(diff, AIWireSessionDictionaryDiff)
        else AIWireSessionDictionaryDiff.from_dict(diff)
    )
    _verify_session_dictionary_diff_identity(parsed)
    _verify_aiwire_payload_auth(
        parsed.to_unsigned_dict(),
        parsed.auth_tag,
        auth_key,
        "session dictionary diff",
    )
    if replay_cache is not None and (
        parsed.diff_id in replay_cache or parsed.nonce in replay_cache
    ):
        raise AIWireHandshakeError("session dictionary diff replay detected")

    current = dict(normalize_aiwire_session_templates(current_templates))
    current_normalized = normalize_aiwire_session_templates(current)
    if parsed.previous_state_hash != aiwire_session_dictionary_state_sha256(
        current_normalized,
        epoch=current_epoch,
    ):
        raise AIWireHandshakeError("session dictionary previous state hash mismatch")
    if parsed.previous_count != len(current):
        raise AIWireHandshakeError("session dictionary previous count mismatch")
    if parsed.epoch != current_epoch + 1:
        raise AIWireHandshakeError("session dictionary epoch must increment by one")
    if not parsed.additions:
        raise AIWireHandshakeError("session dictionary diff has no additions")
    if len(parsed.additions) > AI_WIRE_MAX_SESSION_DICTIONARY_DIFF_ADDITIONS:
        raise AIWireHandshakeError("session dictionary diff addition limit exceeded")

    for template_id, pattern in parsed.additions:
        if template_id in current:
            if current[template_id] == pattern:
                raise AIWireHandshakeError(
                    "session dictionary diff repeats an already accepted template"
                )
            raise AIWireHandshakeError("session dictionary template id overwrite rejected")
        current[template_id] = pattern

    next_templates = normalize_aiwire_session_templates(current)
    _validate_session_dictionary_bounds(next_templates)
    next_state_hash = aiwire_session_dictionary_state_sha256(
        next_templates,
        epoch=parsed.epoch,
    )
    if parsed.next_state_hash != next_state_hash:
        raise AIWireHandshakeError("session dictionary next state hash mismatch")
    if parsed.next_count != len(next_templates):
        raise AIWireHandshakeError("session dictionary next count mismatch")

    if replay_cache is not None:
        replay_cache.add(parsed.diff_id)
        replay_cache.add(parsed.nonce)

    return next_templates, _build_session_dictionary_ack(
        parsed,
        accepted=True,
        state_hash=next_state_hash,
        reason=None,
        auth_key=auth_key,
        nonce=ack_nonce,
    )


def verify_aiwire_session_dictionary_ack(
    diff: AIWireSessionDictionaryDiff | dict[str, object],
    ack: AIWireSessionDictionaryAck | dict[str, object],
    *,
    auth_key: AIWireAuthKey = None,
) -> None:
    """Verify that a receiver ACK authorizes use of a proposed dictionary diff."""

    parsed_diff = (
        diff
        if isinstance(diff, AIWireSessionDictionaryDiff)
        else AIWireSessionDictionaryDiff.from_dict(diff)
    )
    _verify_session_dictionary_diff_identity(parsed_diff)
    parsed_ack = (
        ack
        if isinstance(ack, AIWireSessionDictionaryAck)
        else AIWireSessionDictionaryAck.from_dict(ack)
    )
    _verify_aiwire_payload_auth(
        parsed_ack.to_unsigned_dict(),
        parsed_ack.auth_tag,
        auth_key,
        "session dictionary ACK",
    )
    if not parsed_ack.accepted:
        raise AIWireHandshakeError(parsed_ack.reason or "session dictionary diff rejected")
    if parsed_ack.session_id != parsed_diff.session_id:
        raise AIWireHandshakeError("session dictionary ACK session mismatch")
    if parsed_ack.epoch != parsed_diff.epoch:
        raise AIWireHandshakeError("session dictionary ACK epoch mismatch")
    if parsed_ack.diff_id != parsed_diff.diff_id:
        raise AIWireHandshakeError("session dictionary ACK diff mismatch")
    if parsed_ack.previous_state_hash != parsed_diff.previous_state_hash:
        raise AIWireHandshakeError("session dictionary ACK previous state mismatch")
    if parsed_ack.state_hash != parsed_diff.next_state_hash:
        raise AIWireHandshakeError("session dictionary ACK next state mismatch")


def build_aiwire_session_resume_hello(
    *,
    peer_id: str,
    cached_state_hashes: Iterable[str],
    app_namespace: str = "default",
    static_dictionary_sha256: str = AI_WIRE_DICTIONARY_SHA256,
    supported_delta_versions: Iterable[int] = (AI_WIRE_DELTA_VERSION,),
    auth_key: AIWireAuthKey = None,
    nonce: str | None = None,
) -> AIWireSessionResumeHello:
    """Build a future-connection resume hello with explicit cached state hashes."""

    _validate_sha256_hex(static_dictionary_sha256, "static_dictionary_sha256")
    cached = tuple(cached_state_hashes)
    for cached_hash in cached:
        _validate_sha256_hex(cached_hash, "cached_state_hash")
    versions = tuple(int(version) for version in supported_delta_versions)
    hello_without_auth = AIWireSessionResumeHello(
        peer_id=peer_id,
        app_namespace=app_namespace,
        static_dictionary_sha256=static_dictionary_sha256,
        cached_state_hashes=cached,
        supported_delta_versions=versions,
        nonce=nonce or _make_aiwire_nonce(),
        auth_tag="",
    )
    return AIWireSessionResumeHello(
        **{
            **hello_without_auth.__dict__,
            "auth_tag": _sign_aiwire_payload(hello_without_auth.to_unsigned_dict(), auth_key),
        }
    )


def negotiate_aiwire_session_resume(
    hello: AIWireSessionResumeHello | dict[str, object],
    *,
    available_state_hashes: Iterable[str],
    static_dictionary_sha256: str = AI_WIRE_DICTIONARY_SHA256,
    auth_key: AIWireAuthKey = None,
    nonce: str | None = None,
) -> AIWireSessionResumeResponse:
    """Negotiate reuse of a cached session dictionary on a future connection."""

    parsed = (
        hello
        if isinstance(hello, AIWireSessionResumeHello)
        else AIWireSessionResumeHello.from_dict(hello)
    )
    _verify_aiwire_payload_auth(
        parsed.to_unsigned_dict(),
        parsed.auth_tag,
        auth_key,
        "session resume hello",
    )
    _validate_sha256_hex(static_dictionary_sha256, "static_dictionary_sha256")
    available = set(available_state_hashes)
    for state_hash in available:
        _validate_sha256_hex(state_hash, "available_state_hash")

    accepted = False
    reason: str | None = None
    selected_hash: str | None = None
    selected_delta_version: int | None = None
    if parsed.static_dictionary_sha256 != static_dictionary_sha256:
        reason = "static_dictionary_sha256_mismatch"
    elif AI_WIRE_DELTA_VERSION not in parsed.supported_delta_versions:
        reason = "no_common_delta_version"
    else:
        for cached_hash in parsed.cached_state_hashes:
            if cached_hash in available:
                accepted = True
                selected_hash = cached_hash
                selected_delta_version = AI_WIRE_DELTA_VERSION
                break
        if not accepted:
            reason = "no_shared_session_dictionary"

    response_without_auth = AIWireSessionResumeResponse(
        accepted=accepted,
        reason=reason,
        resume_state_hash=selected_hash,
        static_dictionary_sha256=static_dictionary_sha256,
        selected_delta_version=selected_delta_version,
        hello_nonce=parsed.nonce,
        nonce=nonce or _make_aiwire_nonce(),
        auth_tag="",
    )
    return AIWireSessionResumeResponse(
        **{
            **response_without_auth.__dict__,
            "auth_tag": _sign_aiwire_payload(
                response_without_auth.to_unsigned_dict(),
                auth_key,
            ),
        }
    )


def verify_aiwire_session_resume_response(
    hello: AIWireSessionResumeHello | dict[str, object],
    response: AIWireSessionResumeResponse | dict[str, object],
    *,
    auth_key: AIWireAuthKey = None,
) -> None:
    """Verify a resume response before reusing cached dictionary state."""

    parsed_hello = (
        hello
        if isinstance(hello, AIWireSessionResumeHello)
        else AIWireSessionResumeHello.from_dict(hello)
    )
    parsed_response = (
        response
        if isinstance(response, AIWireSessionResumeResponse)
        else AIWireSessionResumeResponse.from_dict(response)
    )
    _verify_aiwire_payload_auth(
        parsed_response.to_unsigned_dict(),
        parsed_response.auth_tag,
        auth_key,
        "session resume response",
    )
    if parsed_response.hello_nonce != parsed_hello.nonce:
        raise AIWireHandshakeError("session resume response nonce mismatch")
    if parsed_response.static_dictionary_sha256 != parsed_hello.static_dictionary_sha256:
        raise AIWireHandshakeError("session resume static dictionary mismatch")
    if not parsed_response.accepted:
        raise AIWireHandshakeError(parsed_response.reason or "session resume rejected")
    if parsed_response.selected_delta_version not in parsed_hello.supported_delta_versions:
        raise AIWireHandshakeError("session resume delta version mismatch")
    if parsed_response.resume_state_hash not in parsed_hello.cached_state_hashes:
        raise AIWireHandshakeError("session resume state hash was not offered")


def _build_session_dictionary(
    *,
    use_static_dictionary: bool,
    session_templates: tuple[tuple[int, str], ...],
) -> bytes | None:
    dictionary = AI_WIRE_STATIC_DICTIONARY if use_static_dictionary else b""
    if session_templates:
        template_terms = "\n".join(
            f"{template_id}:{pattern}" for template_id, pattern in session_templates
        )
        # Keep session terms near the end of the zlib window because they are
        # workload-specific and should have the highest match priority.
        dictionary += (("\n" + template_terms) * 12).encode("utf-8")
    return dictionary[-32768:] if dictionary else None


def _fnv1a64(data: bytes) -> int:
    value = 14695981039346656037
    for byte in data:
        value ^= byte
        value = (value * 1099511628211) & 0xFFFFFFFFFFFFFFFF
    return value


AI_WIRE_DICTIONARY_FNV1A64 = _fnv1a64(AI_WIRE_STATIC_DICTIONARY)


class AIWireNativeError(RuntimeError):
    """Raised when the native C++ AIWire backend reports an error."""


class AIWireFrameError(ValueError):
    """Raised when an AIWire data frame cannot be safely decoded."""


class AIWireFallbackError(ValueError):
    """Raised when an AIWire negotiated fallback frame is invalid."""


class AIWireHandshakeError(ValueError):
    """Raised when an AIWire protocol handshake cannot be negotiated."""


@dataclass(frozen=True)
class AIWireNativeStatus:
    """Runtime status for the optional native AIWire backend."""

    available: bool
    library_path: str | None
    version: str | None = None
    error: str | None = None
    dictionary_size: int | None = None
    dictionary_checksum: str | None = None
    dictionary_matches_python: bool | None = None
    supports_custom_dictionary: bool = False
    supports_token_codec: bool = False
    supports_token_aiwire: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "available": self.available,
            "library_path": self.library_path,
            "version": self.version,
            "error": self.error,
            "dictionary_size": self.dictionary_size,
            "dictionary_checksum": self.dictionary_checksum,
            "dictionary_matches_python": self.dictionary_matches_python,
            "supports_custom_dictionary": self.supports_custom_dictionary,
            "supports_token_codec": self.supports_token_codec,
            "supports_token_aiwire": self.supports_token_aiwire,
        }


class _NativeAIWireLibrary:
    """ctypes loader for ``libaura_aiwire``."""

    def __init__(self) -> None:
        self.library_path: str | None = None
        self.error: str | None = None
        self.lib: ctypes.CDLL | None = None
        self.version: str | None = None
        self.supports_custom_dictionary = False
        self.supports_token_codec = False
        self.supports_token_aiwire = False
        self._load()

    @property
    def available(self) -> bool:
        return self.lib is not None

    @staticmethod
    def _library_names() -> tuple[str, ...]:
        if sys.platform == "darwin":
            return ("libaura_aiwire.dylib", "libaura_aiwire.so")
        if os.name == "nt":
            return ("aura_aiwire.dll", "libaura_aiwire.dll")
        return ("libaura_aiwire.so",)

    @classmethod
    def _candidate_paths(cls) -> Iterable[Path]:
        env_path = os.getenv("AURA_AIWIRE_LIBRARY")
        if env_path:
            yield Path(env_path).expanduser()

        package_dir = Path(__file__).resolve().parent
        repo_root = package_dir.parents[1] if len(package_dir.parents) > 1 else package_dir
        for name in cls._library_names():
            yield package_dir / "native" / name
            yield repo_root / "native" / "aiwire" / "build" / name

        for name in cls._library_names():
            yield Path(name)

    def _load(self) -> None:
        errors: list[str] = []
        for path in self._candidate_paths():
            library_path = str(path)
            if path.is_absolute() and not path.exists():
                continue
            try:
                lib = ctypes.CDLL(library_path)
                self.lib = lib
                self.library_path = library_path
                (
                    self.supports_custom_dictionary,
                    self.supports_token_codec,
                    self.supports_token_aiwire,
                ) = self._configure_signatures(lib)
                raw_version = lib.aura_aiwire_backend_version()
                self.version = (
                    raw_version.decode("utf-8", errors="replace") if raw_version else None
                )
                return
            except (OSError, AttributeError) as exc:
                errors.append(f"{library_path}: {exc}")
        self.error = "; ".join(errors) if errors else "libaura_aiwire not found"

    @staticmethod
    def _configure_signatures(lib: ctypes.CDLL) -> tuple[bool, bool, bool]:
        lib.aura_aiwire_last_error.argtypes = []
        lib.aura_aiwire_last_error.restype = ctypes.c_char_p

        lib.aura_aiwire_backend_version.argtypes = []
        lib.aura_aiwire_backend_version.restype = ctypes.c_char_p

        lib.aura_aiwire_static_dictionary_size.argtypes = []
        lib.aura_aiwire_static_dictionary_size.restype = ctypes.c_size_t

        lib.aura_aiwire_static_dictionary_checksum.argtypes = []
        lib.aura_aiwire_static_dictionary_checksum.restype = ctypes.c_uint64

        lib.aura_aiwire_free.argtypes = [ctypes.c_void_p]
        lib.aura_aiwire_free.restype = None

        lib.aura_aiwire_encoder_create.argtypes = [ctypes.c_int, ctypes.c_int]
        lib.aura_aiwire_encoder_create.restype = ctypes.c_void_p
        supports_custom_dictionary = hasattr(
            lib, "aura_aiwire_encoder_create_with_dictionary"
        ) and hasattr(lib, "aura_aiwire_decoder_create_with_dictionary")
        if supports_custom_dictionary:
            lib.aura_aiwire_encoder_create_with_dictionary.argtypes = [
                ctypes.c_int,
                ctypes.c_void_p,
                ctypes.c_size_t,
            ]
            lib.aura_aiwire_encoder_create_with_dictionary.restype = ctypes.c_void_p
        lib.aura_aiwire_encoder_destroy.argtypes = [ctypes.c_void_p]
        lib.aura_aiwire_encoder_destroy.restype = None
        lib.aura_aiwire_encoder_compress.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(ctypes.c_size_t),
        ]
        lib.aura_aiwire_encoder_compress.restype = ctypes.c_int
        lib.aura_aiwire_encoder_frames.argtypes = [ctypes.c_void_p]
        lib.aura_aiwire_encoder_frames.restype = ctypes.c_uint64
        lib.aura_aiwire_encoder_bytes_in.argtypes = [ctypes.c_void_p]
        lib.aura_aiwire_encoder_bytes_in.restype = ctypes.c_uint64
        lib.aura_aiwire_encoder_bytes_out.argtypes = [ctypes.c_void_p]
        lib.aura_aiwire_encoder_bytes_out.restype = ctypes.c_uint64

        lib.aura_aiwire_decoder_create.argtypes = [ctypes.c_int]
        lib.aura_aiwire_decoder_create.restype = ctypes.c_void_p
        if supports_custom_dictionary:
            lib.aura_aiwire_decoder_create_with_dictionary.argtypes = [
                ctypes.c_void_p,
                ctypes.c_size_t,
            ]
            lib.aura_aiwire_decoder_create_with_dictionary.restype = ctypes.c_void_p
        lib.aura_aiwire_decoder_destroy.argtypes = [ctypes.c_void_p]
        lib.aura_aiwire_decoder_destroy.restype = None
        lib.aura_aiwire_decoder_decompress.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(ctypes.c_size_t),
        ]
        lib.aura_aiwire_decoder_decompress.restype = ctypes.c_int
        lib.aura_aiwire_decoder_frames.argtypes = [ctypes.c_void_p]
        lib.aura_aiwire_decoder_frames.restype = ctypes.c_uint64
        lib.aura_aiwire_decoder_bytes_in.argtypes = [ctypes.c_void_p]
        lib.aura_aiwire_decoder_bytes_in.restype = ctypes.c_uint64
        lib.aura_aiwire_decoder_bytes_out.argtypes = [ctypes.c_void_p]
        lib.aura_aiwire_decoder_bytes_out.restype = ctypes.c_uint64

        supports_token_codec = hasattr(lib, "aura_aiwire_token_encoder_create") and hasattr(
            lib, "aura_aiwire_token_decoder_create"
        )
        if supports_token_codec:
            lib.aura_aiwire_token_encoder_create.argtypes = [
                ctypes.c_size_t,
                ctypes.c_size_t,
            ]
            lib.aura_aiwire_token_encoder_create.restype = ctypes.c_void_p
            lib.aura_aiwire_token_encoder_destroy.argtypes = [ctypes.c_void_p]
            lib.aura_aiwire_token_encoder_destroy.restype = None
            lib.aura_aiwire_token_encoder_encode.argtypes = [
                ctypes.c_void_p,
                ctypes.c_void_p,
                ctypes.c_size_t,
                ctypes.POINTER(ctypes.c_void_p),
                ctypes.POINTER(ctypes.c_size_t),
            ]
            lib.aura_aiwire_token_encoder_encode.restype = ctypes.c_int
            lib.aura_aiwire_token_encoder_frames.argtypes = [ctypes.c_void_p]
            lib.aura_aiwire_token_encoder_frames.restype = ctypes.c_uint64
            lib.aura_aiwire_token_encoder_bytes_in.argtypes = [ctypes.c_void_p]
            lib.aura_aiwire_token_encoder_bytes_in.restype = ctypes.c_uint64
            lib.aura_aiwire_token_encoder_bytes_out.argtypes = [ctypes.c_void_p]
            lib.aura_aiwire_token_encoder_bytes_out.restype = ctypes.c_uint64

            lib.aura_aiwire_token_decoder_create.argtypes = [ctypes.c_size_t]
            lib.aura_aiwire_token_decoder_create.restype = ctypes.c_void_p
            lib.aura_aiwire_token_decoder_destroy.argtypes = [ctypes.c_void_p]
            lib.aura_aiwire_token_decoder_destroy.restype = None
            lib.aura_aiwire_token_decoder_decode.argtypes = [
                ctypes.c_void_p,
                ctypes.c_void_p,
                ctypes.c_size_t,
                ctypes.POINTER(ctypes.c_void_p),
                ctypes.POINTER(ctypes.c_size_t),
            ]
            lib.aura_aiwire_token_decoder_decode.restype = ctypes.c_int
            lib.aura_aiwire_token_decoder_frames.argtypes = [ctypes.c_void_p]
            lib.aura_aiwire_token_decoder_frames.restype = ctypes.c_uint64
            lib.aura_aiwire_token_decoder_bytes_in.argtypes = [ctypes.c_void_p]
            lib.aura_aiwire_token_decoder_bytes_in.restype = ctypes.c_uint64
            lib.aura_aiwire_token_decoder_bytes_out.argtypes = [ctypes.c_void_p]
            lib.aura_aiwire_token_decoder_bytes_out.restype = ctypes.c_uint64

        supports_token_aiwire = hasattr(
            lib, "aura_aiwire_token_aiwire_encoder_create_with_dictionary"
        ) and hasattr(lib, "aura_aiwire_token_aiwire_decoder_create_with_dictionary")
        if supports_token_aiwire:
            lib.aura_aiwire_token_aiwire_encoder_create.argtypes = [
                ctypes.c_int,
                ctypes.c_int,
            ]
            lib.aura_aiwire_token_aiwire_encoder_create.restype = ctypes.c_void_p
            lib.aura_aiwire_token_aiwire_encoder_create_with_dictionary.argtypes = [
                ctypes.c_int,
                ctypes.c_void_p,
                ctypes.c_size_t,
            ]
            lib.aura_aiwire_token_aiwire_encoder_create_with_dictionary.restype = ctypes.c_void_p
            lib.aura_aiwire_token_aiwire_encoder_destroy.argtypes = [ctypes.c_void_p]
            lib.aura_aiwire_token_aiwire_encoder_destroy.restype = None
            lib.aura_aiwire_token_aiwire_encoder_encode.argtypes = [
                ctypes.c_void_p,
                ctypes.c_void_p,
                ctypes.c_size_t,
                ctypes.POINTER(ctypes.c_void_p),
                ctypes.POINTER(ctypes.c_size_t),
            ]
            lib.aura_aiwire_token_aiwire_encoder_encode.restype = ctypes.c_int
            lib.aura_aiwire_token_aiwire_encoder_frames.argtypes = [ctypes.c_void_p]
            lib.aura_aiwire_token_aiwire_encoder_frames.restype = ctypes.c_uint64
            lib.aura_aiwire_token_aiwire_encoder_bytes_in.argtypes = [ctypes.c_void_p]
            lib.aura_aiwire_token_aiwire_encoder_bytes_in.restype = ctypes.c_uint64
            lib.aura_aiwire_token_aiwire_encoder_token_bytes.argtypes = [ctypes.c_void_p]
            lib.aura_aiwire_token_aiwire_encoder_token_bytes.restype = ctypes.c_uint64
            lib.aura_aiwire_token_aiwire_encoder_bytes_out.argtypes = [ctypes.c_void_p]
            lib.aura_aiwire_token_aiwire_encoder_bytes_out.restype = ctypes.c_uint64

            lib.aura_aiwire_token_aiwire_decoder_create.argtypes = [ctypes.c_int]
            lib.aura_aiwire_token_aiwire_decoder_create.restype = ctypes.c_void_p
            lib.aura_aiwire_token_aiwire_decoder_create_with_dictionary.argtypes = [
                ctypes.c_void_p,
                ctypes.c_size_t,
            ]
            lib.aura_aiwire_token_aiwire_decoder_create_with_dictionary.restype = ctypes.c_void_p
            lib.aura_aiwire_token_aiwire_decoder_destroy.argtypes = [ctypes.c_void_p]
            lib.aura_aiwire_token_aiwire_decoder_destroy.restype = None
            lib.aura_aiwire_token_aiwire_decoder_decode.argtypes = [
                ctypes.c_void_p,
                ctypes.c_void_p,
                ctypes.c_size_t,
                ctypes.POINTER(ctypes.c_void_p),
                ctypes.POINTER(ctypes.c_size_t),
            ]
            lib.aura_aiwire_token_aiwire_decoder_decode.restype = ctypes.c_int
            lib.aura_aiwire_token_aiwire_decoder_frames.argtypes = [ctypes.c_void_p]
            lib.aura_aiwire_token_aiwire_decoder_frames.restype = ctypes.c_uint64
            lib.aura_aiwire_token_aiwire_decoder_bytes_in.argtypes = [ctypes.c_void_p]
            lib.aura_aiwire_token_aiwire_decoder_bytes_in.restype = ctypes.c_uint64
            lib.aura_aiwire_token_aiwire_decoder_token_bytes.argtypes = [ctypes.c_void_p]
            lib.aura_aiwire_token_aiwire_decoder_token_bytes.restype = ctypes.c_uint64
            lib.aura_aiwire_token_aiwire_decoder_bytes_out.argtypes = [ctypes.c_void_p]
            lib.aura_aiwire_token_aiwire_decoder_bytes_out.restype = ctypes.c_uint64

        return supports_custom_dictionary, supports_token_codec, supports_token_aiwire

    def last_error(self) -> str:
        if self.lib is None:
            return self.error or "native AIWire library not loaded"
        raw = self.lib.aura_aiwire_last_error()
        return raw.decode("utf-8", errors="replace") if raw else "unknown native AIWire error"


_NATIVE_LIBRARY: _NativeAIWireLibrary | None = None


def _get_native_library() -> _NativeAIWireLibrary:
    global _NATIVE_LIBRARY
    if _NATIVE_LIBRARY is None:
        _NATIVE_LIBRARY = _NativeAIWireLibrary()
    return _NATIVE_LIBRARY


def aiwire_native_status() -> AIWireNativeStatus:
    lib = _get_native_library()
    dictionary_size = None
    dictionary_checksum = None
    dictionary_matches_python = None
    if lib.lib is not None:
        try:
            dictionary_size = int(lib.lib.aura_aiwire_static_dictionary_size())
            native_checksum = int(lib.lib.aura_aiwire_static_dictionary_checksum())
            dictionary_checksum = f"{native_checksum:016x}"
            dictionary_matches_python = (
                dictionary_size == len(AI_WIRE_STATIC_DICTIONARY)
                and native_checksum == AI_WIRE_DICTIONARY_FNV1A64
            )
        except (AttributeError, OSError, TypeError):
            dictionary_matches_python = False

    return AIWireNativeStatus(
        available=lib.available,
        library_path=lib.library_path,
        version=lib.version,
        error=lib.error,
        dictionary_size=dictionary_size,
        dictionary_checksum=dictionary_checksum,
        dictionary_matches_python=dictionary_matches_python,
        supports_custom_dictionary=lib.supports_custom_dictionary,
        supports_token_codec=lib.supports_token_codec,
        supports_token_aiwire=lib.supports_token_aiwire,
    )


@dataclass(frozen=True)
class AIWireHandshake:
    """Compatibility contract sent before an AIWire session starts."""

    versions: tuple[int, ...]
    preferred_version: int
    dictionary_sha256: str
    dictionary_size: int
    wbits: int
    mem_level: int
    flush_mode: str
    level: int
    use_static_dictionary: bool
    backend: str
    native_version: str | None
    fallback_codecs: tuple[str, ...]
    session_templates: tuple[tuple[int, str], ...]
    session_template_sha256: str
    session_template_count: int
    session_template_epoch: int
    require_session_templates: bool
    control_lut: tuple[AIWireControlLUTEntry, ...]
    control_lut_sha256: str
    control_lut_count: int
    control_lut_epoch: int
    require_control_lut: bool

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "schema": AI_WIRE_HANDSHAKE_SCHEMA,
            "protocol": AI_WIRE_PROTOCOL,
            "versions": list(self.versions),
            "preferred_version": self.preferred_version,
            "dictionary_sha256": self.dictionary_sha256,
            "dictionary_size": self.dictionary_size,
            "wbits": self.wbits,
            "mem_level": self.mem_level,
            "flush_mode": self.flush_mode,
            "level": self.level,
            "use_static_dictionary": self.use_static_dictionary,
            "backend": self.backend,
            "native_version": self.native_version,
            "fallback_codecs": list(self.fallback_codecs),
            "session_templates": [
                {"template_id": template_id, "pattern": pattern}
                for template_id, pattern in self.session_templates
            ],
            "session_template_sha256": self.session_template_sha256,
            "session_template_count": self.session_template_count,
            "session_template_epoch": self.session_template_epoch,
            "require_session_templates": self.require_session_templates,
        }
        if self.control_lut_count or self.control_lut_epoch or self.require_control_lut:
            payload.update(
                {
                    "control_lut": [entry.to_dict() for entry in self.control_lut],
                    "control_lut_sha256": self.control_lut_sha256,
                    "control_lut_count": self.control_lut_count,
                    "control_lut_epoch": self.control_lut_epoch,
                    "require_control_lut": self.require_control_lut,
                }
            )
        return payload

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> "AIWireHandshake":
        if value.get("schema") != AI_WIRE_HANDSHAKE_SCHEMA:
            raise AIWireHandshakeError("unsupported AIWire handshake schema")
        if value.get("protocol") != AI_WIRE_PROTOCOL:
            raise AIWireHandshakeError("unsupported AIWire protocol")

        try:
            versions = tuple(int(version) for version in value["versions"])  # type: ignore[index]
            fallback_codecs = tuple(str(codec) for codec in value.get("fallback_codecs", ()))
            session_templates = normalize_aiwire_session_templates(
                value.get("session_templates", ())
            )
            control_lut = normalize_aiwire_control_lut(value.get("control_lut", ()))
            session_template_sha256 = str(
                value.get(
                    "session_template_sha256",
                    aiwire_session_templates_sha256(session_templates),
                )
            )
            if session_template_sha256 != aiwire_session_templates_sha256(session_templates):
                raise AIWireHandshakeError("session template hash does not match payload")
            session_template_count = int(
                value.get("session_template_count", len(session_templates))
            )
            if session_template_count != len(session_templates):
                raise AIWireHandshakeError("session template count does not match payload")
            control_lut_sha256 = str(
                value.get("control_lut_sha256", aiwire_control_lut_sha256(control_lut))
            )
            if control_lut_sha256 != aiwire_control_lut_sha256(control_lut):
                raise AIWireHandshakeError("control LUT hash does not match payload")
            control_lut_count = int(value.get("control_lut_count", len(control_lut)))
            if control_lut_count != len(control_lut):
                raise AIWireHandshakeError("control LUT count does not match payload")
            return cls(
                versions=versions,
                preferred_version=int(value["preferred_version"]),
                dictionary_sha256=str(value["dictionary_sha256"]),
                dictionary_size=int(value["dictionary_size"]),
                wbits=int(value["wbits"]),
                mem_level=int(value["mem_level"]),
                flush_mode=str(value["flush_mode"]),
                level=int(value["level"]),
                use_static_dictionary=bool(value["use_static_dictionary"]),
                backend=str(value.get("backend", "unknown")),
                native_version=(
                    str(value["native_version"])
                    if value.get("native_version") is not None
                    else None
                ),
                fallback_codecs=fallback_codecs,
                session_templates=session_templates,
                session_template_sha256=session_template_sha256,
                session_template_count=session_template_count,
                session_template_epoch=int(value.get("session_template_epoch", 0)),
                require_session_templates=bool(value.get("require_session_templates", False)),
                control_lut=control_lut,
                control_lut_sha256=control_lut_sha256,
                control_lut_count=control_lut_count,
                control_lut_epoch=int(value.get("control_lut_epoch", 0)),
                require_control_lut=bool(value.get("require_control_lut", False)),
            )
        except (KeyError, TypeError, ValueError, AIWireHandshakeError) as exc:
            raise AIWireHandshakeError(f"malformed AIWire handshake: {exc}") from exc


@dataclass(frozen=True)
class AIWireNegotiation:
    """Server response to an AIWire handshake."""

    accepted: bool
    codec: str
    version: int | None
    reason: str | None
    server_handshake: AIWireHandshake

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": AI_WIRE_NEGOTIATION_SCHEMA,
            "accepted": self.accepted,
            "codec": self.codec,
            "version": self.version,
            "reason": self.reason,
            "server": self.server_handshake.to_dict(),
        }


def build_aiwire_handshake(
    *,
    level: int = AI_WIRE_DEFAULT_LEVEL,
    use_static_dictionary: bool = True,
    use_native: bool | None = None,
    fallback_codecs: Iterable[str] = AI_WIRE_FALLBACK_CODECS,
    session_templates: AIWireSessionTemplates | None = None,
    session_template_epoch: int = 0,
    require_session_templates: bool = False,
    control_lut: AIWireControlLUTEntries | None = None,
    control_lut_epoch: int = 0,
    require_control_lut: bool = False,
) -> AIWireHandshake:
    if not 0 <= level <= 9:
        raise ValueError(f"zlib level must be in [0, 9], got {level}")

    normalized_templates = normalize_aiwire_session_templates(session_templates)
    normalized_control_lut = normalize_aiwire_control_lut(control_lut)
    normalized_fallback_codecs = tuple(
        _normalize_aiwire_fallback_codec(codec) for codec in fallback_codecs
    )
    native_status = aiwire_native_status()
    backend = (
        "native"
        if _native_enabled(use_native)
        and native_status.available
        and (not normalized_templates or native_status.supports_custom_dictionary)
        else "python"
    )

    return AIWireHandshake(
        versions=AI_WIRE_SUPPORTED_VERSIONS,
        preferred_version=AI_WIRE_VERSION,
        dictionary_sha256=AI_WIRE_DICTIONARY_SHA256 if use_static_dictionary else "",
        dictionary_size=len(AI_WIRE_STATIC_DICTIONARY) if use_static_dictionary else 0,
        wbits=AI_WIRE_WBITS,
        mem_level=AI_WIRE_MEM_LEVEL,
        flush_mode=AI_WIRE_FLUSH_MODE,
        level=level,
        use_static_dictionary=use_static_dictionary,
        backend=backend,
        native_version=native_status.version if backend == "native" else None,
        fallback_codecs=normalized_fallback_codecs,
        session_templates=normalized_templates,
        session_template_sha256=aiwire_session_templates_sha256(normalized_templates),
        session_template_count=len(normalized_templates),
        session_template_epoch=session_template_epoch,
        require_session_templates=require_session_templates,
        control_lut=normalized_control_lut,
        control_lut_sha256=aiwire_control_lut_sha256(normalized_control_lut),
        control_lut_count=len(normalized_control_lut),
        control_lut_epoch=control_lut_epoch,
        require_control_lut=require_control_lut,
    )


def negotiate_aiwire_handshake(
    peer_handshake: dict[str, object] | AIWireHandshake,
    *,
    level: int = AI_WIRE_DEFAULT_LEVEL,
    use_static_dictionary: bool = True,
    use_native: bool | None = None,
    fallback_codecs: Iterable[str] = AI_WIRE_FALLBACK_CODECS,
    allow_fallback: bool = True,
    session_templates: AIWireSessionTemplates | None = None,
    session_template_epoch: int = 0,
    require_session_templates: bool = False,
    control_lut: AIWireControlLUTEntries | None = None,
    control_lut_epoch: int = 0,
    require_control_lut: bool = False,
) -> AIWireNegotiation:
    peer = (
        peer_handshake
        if isinstance(peer_handshake, AIWireHandshake)
        else AIWireHandshake.from_dict(peer_handshake)
    )
    local = build_aiwire_handshake(
        level=level,
        use_static_dictionary=use_static_dictionary,
        use_native=use_native,
        fallback_codecs=fallback_codecs,
        session_templates=session_templates,
        session_template_epoch=session_template_epoch,
        require_session_templates=require_session_templates,
        control_lut=control_lut,
        control_lut_epoch=control_lut_epoch,
        require_control_lut=require_control_lut,
    )

    common_versions = sorted(set(peer.versions).intersection(local.versions), reverse=True)
    templates_are_required = (
        peer.require_session_templates
        or local.require_session_templates
        or bool(peer.session_template_count)
        or bool(local.session_template_count)
    )
    control_lut_is_required = (
        peer.require_control_lut
        or local.require_control_lut
        or bool(peer.control_lut_count)
        or bool(local.control_lut_count)
    )
    reason = None
    if not common_versions:
        reason = "no_common_aiwire_version"
    elif templates_are_required and peer.session_template_count != local.session_template_count:
        reason = "session_template_count_mismatch"
    elif templates_are_required and peer.session_template_sha256 != local.session_template_sha256:
        reason = "session_template_sha256_mismatch"
    elif (
        peer.require_session_templates or local.require_session_templates
    ) and not local.session_template_count:
        reason = "session_templates_required"
    elif control_lut_is_required and peer.control_lut_count != local.control_lut_count:
        reason = "control_lut_count_mismatch"
    elif control_lut_is_required and peer.control_lut_sha256 != local.control_lut_sha256:
        reason = "control_lut_sha256_mismatch"
    elif (peer.require_control_lut or local.require_control_lut) and not local.control_lut_count:
        reason = "control_lut_required"
    elif peer.use_static_dictionary != local.use_static_dictionary:
        reason = "static_dictionary_mode_mismatch"
    elif peer.use_static_dictionary and peer.dictionary_sha256 != local.dictionary_sha256:
        reason = "dictionary_sha256_mismatch"
    elif peer.use_static_dictionary and peer.dictionary_size != local.dictionary_size:
        reason = "dictionary_size_mismatch"
    elif peer.wbits != local.wbits:
        reason = "zlib_window_mismatch"
    elif peer.flush_mode != local.flush_mode:
        reason = "flush_mode_mismatch"
    elif peer.mem_level != local.mem_level:
        reason = "mem_level_mismatch"

    if reason is None:
        return AIWireNegotiation(
            accepted=True,
            codec="aiwire",
            version=common_versions[0],
            reason=None,
            server_handshake=local,
        )

    fallback = None
    if allow_fallback:
        local_fallbacks = local.fallback_codecs
        peer_fallbacks = {str(codec).lower() for codec in peer.fallback_codecs}
        for codec in local_fallbacks:
            if codec in peer_fallbacks:
                fallback = codec
                break

    if fallback is not None:
        return AIWireNegotiation(
            accepted=True,
            codec=fallback,
            version=None,
            reason=reason,
            server_handshake=local,
        )

    return AIWireNegotiation(
        accepted=False,
        codec="",
        version=None,
        reason=reason,
        server_handshake=local,
    )


def _normalize_aiwire_fallback_codec(codec: str) -> str:
    normalized = str(codec).lower()
    if normalized not in AI_WIRE_FALLBACK_CODECS:
        raise AIWireFallbackError(f"unsupported AIWire fallback codec: {codec}")
    return normalized


def encode_aiwire_fallback_frame(
    codec: str,
    payload: AIWireFrame,
    *,
    level: int = AI_WIRE_DEFAULT_LEVEL,
) -> bytes:
    """Encode one stateless fallback frame after AIWire negotiation.

    Fallback frames intentionally do not use the live AIWire compression stream.
    ``raw`` is canonical AIWire message bytes. ``zlib`` is a standalone zlib
    frame over those canonical bytes.
    """

    normalized = _normalize_aiwire_fallback_codec(codec)
    raw = encode_ai_wire_message(payload)
    if normalized == "raw":
        return raw
    if not 0 <= level <= 9:
        raise AIWireFallbackError(f"zlib fallback level must be in [0, 9], got {level}")
    return zlib.compress(raw, level)


def decode_aiwire_fallback_frame(codec: str, payload: bytes | bytearray | memoryview) -> bytes:
    """Decode one stateless fallback frame after AIWire negotiation."""

    normalized = _normalize_aiwire_fallback_codec(codec)
    frame = bytes(payload)
    if normalized == "raw":
        return frame
    try:
        decompressor = zlib.decompressobj()
        restored = decompressor.decompress(frame) + decompressor.flush()
    except zlib.error as exc:
        raise AIWireFallbackError(f"AIWire zlib fallback frame decompression failed: {exc}") from exc
    if decompressor.unused_data:
        raise AIWireFallbackError("AIWire zlib fallback frame contains unused compressed data")
    return restored


def _native_enabled(use_native: bool | None) -> bool:
    if use_native is not None:
        return use_native
    value = os.getenv("AURA_AIWIRE_NATIVE", "auto").lower()
    return value not in {"0", "false", "off", "no", "python"}


def _bytes_from_native_call(
    lib: _NativeAIWireLibrary,
    func,
    handle: ctypes.c_void_p,
    payload: bytes,
) -> bytes:
    assert lib.lib is not None
    output = ctypes.c_void_p()
    output_size = ctypes.c_size_t()
    input_ptr = ctypes.c_char_p(payload) if payload else None

    rc = func(
        handle,
        input_ptr,
        len(payload),
        ctypes.byref(output),
        ctypes.byref(output_size),
    )
    if rc != 0:
        raise AIWireNativeError(lib.last_error())

    try:
        return ctypes.string_at(output, output_size.value) if output_size.value else b""
    finally:
        if output:
            lib.lib.aura_aiwire_free(output)


class _NativeAIWireEncoder:
    def __init__(
        self,
        *,
        level: int,
        use_static_dictionary: bool,
        dictionary: bytes | None = None,
    ) -> None:
        self._handle = None
        self._lib = _get_native_library()
        if self._lib.lib is None:
            raise AIWireNativeError(self._lib.error or "native AIWire library not loaded")

        if dictionary is None:
            self._handle = self._lib.lib.aura_aiwire_encoder_create(
                int(level),
                1 if use_static_dictionary else 0,
            )
        else:
            if not self._lib.supports_custom_dictionary:
                raise AIWireNativeError("native AIWire backend lacks custom dictionary support")
            dictionary_ptr = ctypes.c_char_p(dictionary) if dictionary else None
            self._handle = self._lib.lib.aura_aiwire_encoder_create_with_dictionary(
                int(level),
                dictionary_ptr,
                len(dictionary),
            )
        if not self._handle:
            raise AIWireNativeError(self._lib.last_error())

    def close(self) -> None:
        if self._handle and self._lib.lib is not None:
            self._lib.lib.aura_aiwire_encoder_destroy(self._handle)
            self._handle = None

    def __del__(self) -> None:
        self.close()

    def compress_frame(self, payload: bytes) -> bytes:
        if not self._handle or self._lib.lib is None:
            raise AIWireNativeError("native AIWire encoder is closed")
        return _bytes_from_native_call(
            self._lib,
            self._lib.lib.aura_aiwire_encoder_compress,
            self._handle,
            payload,
        )


class _NativeAIWireDecoder:
    def __init__(
        self,
        *,
        use_static_dictionary: bool,
        dictionary: bytes | None = None,
    ) -> None:
        self._handle = None
        self._lib = _get_native_library()
        if self._lib.lib is None:
            raise AIWireNativeError(self._lib.error or "native AIWire library not loaded")

        if dictionary is None:
            self._handle = self._lib.lib.aura_aiwire_decoder_create(
                1 if use_static_dictionary else 0,
            )
        else:
            if not self._lib.supports_custom_dictionary:
                raise AIWireNativeError("native AIWire backend lacks custom dictionary support")
            dictionary_ptr = ctypes.c_char_p(dictionary) if dictionary else None
            self._handle = self._lib.lib.aura_aiwire_decoder_create_with_dictionary(
                dictionary_ptr,
                len(dictionary),
            )
        if not self._handle:
            raise AIWireNativeError(self._lib.last_error())

    def close(self) -> None:
        if self._handle and self._lib.lib is not None:
            self._lib.lib.aura_aiwire_decoder_destroy(self._handle)
            self._handle = None

    def __del__(self) -> None:
        self.close()

    def decompress_frame(self, payload: bytes) -> bytes:
        if not self._handle or self._lib.lib is None:
            raise AIWireNativeError("native AIWire decoder is closed")
        return _bytes_from_native_call(
            self._lib,
            self._lib.lib.aura_aiwire_decoder_decompress,
            self._handle,
            payload,
        )


@dataclass(frozen=True)
class AIWireStats:
    """Simple byte/frame counters for one wire-codec session."""

    frames: int
    bytes_in: int
    bytes_out: int

    @property
    def ratio(self) -> float:
        return self.bytes_in / self.bytes_out if self.bytes_out else 0.0

    @property
    def average_bytes_in(self) -> float:
        return self.bytes_in / self.frames if self.frames else 0.0

    @property
    def average_bytes_out(self) -> float:
        return self.bytes_out / self.frames if self.frames else 0.0

    def as_dict(self) -> dict[str, int | float]:
        """Return the stable benchmark serialization for AIWire counters."""

        return {
            "frames": self.frames,
            "bytes_in": self.bytes_in,
            "bytes_out": self.bytes_out,
            "ratio": self.ratio,
            "average_bytes_in": self.average_bytes_in,
            "average_bytes_out": self.average_bytes_out,
        }


class AIWireSessionEncoder:
    """Stateful encoder for ordered AI-to-AI message frames."""

    def __init__(
        self,
        *,
        level: int = AI_WIRE_DEFAULT_LEVEL,
        use_static_dictionary: bool = True,
        session_templates: AIWireSessionTemplates | None = None,
        use_native: bool | None = None,
    ) -> None:
        if not 0 <= level <= 9:
            raise ValueError(f"zlib level must be in [0, 9], got {level}")

        self.level = level
        self.use_static_dictionary = use_static_dictionary
        self.session_templates = normalize_aiwire_session_templates(session_templates)
        self.backend = "python"
        self._native: _NativeAIWireEncoder | None = None
        self._compressor: zlib.compressobj | None = None
        self._frames = 0
        self._bytes_in = 0
        self._bytes_out = 0

        dictionary = _build_session_dictionary(
            use_static_dictionary=use_static_dictionary,
            session_templates=self.session_templates,
        )

        if _native_enabled(use_native):
            try:
                self._native = _NativeAIWireEncoder(
                    level=level,
                    use_static_dictionary=use_static_dictionary,
                    dictionary=dictionary if self.session_templates else None,
                )
                self.backend = "native"
                return
            except AIWireNativeError:
                if use_native is True:
                    raise

        kwargs = {
            "level": level,
            "method": zlib.DEFLATED,
            "wbits": AI_WIRE_WBITS,
            "memLevel": AI_WIRE_MEM_LEVEL,
            "strategy": zlib.Z_DEFAULT_STRATEGY,
        }
        if dictionary:
            kwargs["zdict"] = dictionary
        self._compressor = zlib.compressobj(**kwargs)

    @property
    def stats(self) -> AIWireStats:
        return AIWireStats(
            frames=self._frames,
            bytes_in=self._bytes_in,
            bytes_out=self._bytes_out,
        )

    def __enter__(self) -> "AIWireSessionEncoder":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def compress_frame(self, payload: AIWireFrame) -> bytes:
        raw = encode_ai_wire_message(payload)
        if self._native is not None:
            compressed = self._native.compress_frame(raw)
        else:
            assert self._compressor is not None
            compressed = self._compressor.compress(raw) + self._compressor.flush(zlib.Z_SYNC_FLUSH)
        self._frames += 1
        self._bytes_in += len(raw)
        self._bytes_out += len(compressed)
        return compressed

    def compress_frames(self, frames: Iterable[AIWireFrame]) -> list[bytes]:
        return [self.compress_frame(frame) for frame in frames]

    def compress_message(self, message: AIWireFrame) -> bytes:
        return self.compress_frame(message)

    def compress_messages(self, messages: Iterable[AIWireFrame]) -> list[bytes]:
        return self.compress_frames(messages)

    def close(self) -> None:
        if self._native is not None:
            self._native.close()
            self._native = None


class AIWireSessionDecoder:
    """Stateful decoder for frames emitted by :class:`AIWireSessionEncoder`."""

    def __init__(
        self,
        *,
        use_static_dictionary: bool = True,
        session_templates: AIWireSessionTemplates | None = None,
        use_native: bool | None = None,
    ) -> None:
        self.use_static_dictionary = use_static_dictionary
        self.session_templates = normalize_aiwire_session_templates(session_templates)
        self.backend = "python"
        self._native: _NativeAIWireDecoder | None = None
        self._decompressor: zlib.decompressobj | None = None
        self._frames = 0
        self._bytes_in = 0
        self._bytes_out = 0
        self._failed_reason: str | None = None

        dictionary = _build_session_dictionary(
            use_static_dictionary=use_static_dictionary,
            session_templates=self.session_templates,
        )

        if _native_enabled(use_native):
            try:
                self._native = _NativeAIWireDecoder(
                    use_static_dictionary=use_static_dictionary,
                    dictionary=dictionary if self.session_templates else None,
                )
                self.backend = "native"
                return
            except AIWireNativeError:
                if use_native is True:
                    raise

        kwargs = {"wbits": AI_WIRE_WBITS}
        if dictionary:
            kwargs["zdict"] = dictionary
        self._decompressor = zlib.decompressobj(**kwargs)

    @property
    def stats(self) -> AIWireStats:
        return AIWireStats(
            frames=self._frames,
            bytes_in=self._bytes_in,
            bytes_out=self._bytes_out,
        )

    @property
    def interrupted(self) -> bool:
        """Whether this live decoder stream has hit a non-recoverable frame error."""

        return self._failed_reason is not None

    @property
    def failed_reason(self) -> str | None:
        """Return the first frame error that interrupted this decoder stream."""

        return self._failed_reason

    def __enter__(self) -> "AIWireSessionDecoder":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def _raise_frame_error(self, message: str, exc: BaseException | None = None) -> None:
        if self._failed_reason is None:
            self._failed_reason = message
            if self._native is not None:
                self._native.close()
        if exc is not None:
            raise AIWireFrameError(message) from exc
        raise AIWireFrameError(message)

    def decompress_frame(self, payload: bytes) -> bytes:
        if self._failed_reason is not None:
            raise AIWireFrameError(
                "AIWire decoder stream is interrupted; fresh handshake required: "
                f"{self._failed_reason}"
            )
        frame = bytes(payload)
        if not frame.endswith(AI_WIRE_SYNC_FLUSH_SUFFIX):
            self._raise_frame_error("AIWire frame is truncated or missing Z_SYNC_FLUSH marker")

        if self._native is not None:
            try:
                restored = self._native.decompress_frame(frame)
            except AIWireNativeError as exc:
                self._raise_frame_error(f"AIWire frame decompression failed: {exc}", exc)
        else:
            assert self._decompressor is not None
            try:
                restored = self._decompressor.decompress(frame)
            except zlib.error as exc:
                self._raise_frame_error(f"AIWire frame decompression failed: {exc}", exc)
        if self._decompressor is not None and self._decompressor.unused_data:
            self._raise_frame_error("AIWire frame contains unused compressed data")
        self._frames += 1
        self._bytes_in += len(frame)
        self._bytes_out += len(restored)
        return restored

    def decompress_frames(self, frames: Iterable[bytes]) -> list[bytes]:
        return [self.decompress_frame(frame) for frame in frames]

    def decompress_message(self, payload: bytes) -> Any:
        return decode_ai_wire_message(self.decompress_frame(payload))

    def decompress_messages(self, frames: Iterable[bytes]) -> list[Any]:
        return [self.decompress_message(frame) for frame in frames]

    def close(self) -> None:
        if self._native is not None:
            self._native.close()
            self._native = None


def compress_ai_wire_frames(
    frames: Iterable[AIWireFrame],
    *,
    level: int = AI_WIRE_DEFAULT_LEVEL,
    use_static_dictionary: bool = True,
    session_templates: AIWireSessionTemplates | None = None,
    use_native: bool | None = None,
) -> tuple[list[bytes], AIWireStats]:
    encoder = AIWireSessionEncoder(
        level=level,
        use_static_dictionary=use_static_dictionary,
        session_templates=session_templates,
        use_native=use_native,
    )
    try:
        compressed = encoder.compress_frames(frames)
        return compressed, encoder.stats
    finally:
        encoder.close()


def decompress_ai_wire_frames(
    frames: Iterable[bytes],
    *,
    use_static_dictionary: bool = True,
    session_templates: AIWireSessionTemplates | None = None,
    use_native: bool | None = None,
) -> tuple[list[bytes], AIWireStats]:
    decoder = AIWireSessionDecoder(
        use_static_dictionary=use_static_dictionary,
        session_templates=session_templates,
        use_native=use_native,
    )
    try:
        restored = decoder.decompress_frames(frames)
        return restored, decoder.stats
    finally:
        decoder.close()
