"""Token codec for structured AIWire messages.

This is an experimental structural codec for AI-to-AI JSON frames.  It is not
an entropy compressor.  It encodes JSON structure directly, replaces common
agent protocol keys/values with compact tokens, and keeps a small session string
table for repeated values that are not in the static tables.
"""

from __future__ import annotations

import ctypes
import json
import math
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from .ai_wire import (
    AI_WIRE_DEFAULT_LEVEL,
    AIWireNativeError,
    AIWireSessionDecoder,
    AIWireSessionEncoder,
    AIWireSessionTemplates,
    _build_session_dictionary,
    _bytes_from_native_call,
    _get_native_library,
    _native_enabled,
    normalize_aiwire_session_templates,
)
from .ai_wire_messages import AIWireFrame, encode_ai_wire_message

AI_WIRE_TOKEN_MAGIC = b"AWT1"
AI_WIRE_TOKEN_VERSION = 1

_FRAME_RAW_BYTES = 0x01
_FRAME_JSON_VALUE = 0x02

_NULL = 0x10
_FALSE = 0x11
_TRUE = 0x12
_INT = 0x13
_FLOAT = 0x14
_STRING_RAW = 0x15
_STRING_INTERN = 0x16
_STRING_REF = 0x17
_KEY_TOKEN = 0x18
_VALUE_TOKEN = 0x19
_ARRAY = 0x1A
_OBJECT = 0x1B

_COMMON_KEYS: tuple[str, ...] = (
    "protocol",
    "jsonrpc",
    "id",
    "method",
    "params",
    "result",
    "error",
    "name",
    "arguments",
    "metadata",
    "trace_id",
    "task_id",
    "session_id",
    "call_id",
    "tool_call_id",
    "content",
    "structuredContent",
    "isError",
    "type",
    "kind",
    "text",
    "role",
    "model",
    "input",
    "tools",
    "parameters",
    "properties",
    "required",
    "description",
    "uri",
    "line_start",
    "line_end",
    "matches",
    "file",
    "line",
    "score",
    "message",
    "messageId",
    "contextId",
    "status",
    "state",
    "artifacts",
    "artifactId",
    "event",
    "agent",
    "from",
    "to",
    "handoff",
    "working_memory",
    "facts",
    "open_questions",
    "requested_output_schema",
    "objective",
    "constraints",
    "subgoals",
    "evidence",
    "confidence",
    "verdict",
    "comments",
    "severity",
    "answer",
    "summary",
    "actions",
    "item",
    "repository",
    "path",
    "query",
    "limit",
    "tenant",
    "priority",
    "operation",
    "task",
    "parts",
    "service",
    "output",
    "rows",
    "timestamp",
    "level",
    "sequence",
    "sha256",
    "request",
    "transport",
    "exchange",
    "request_bytes",
    "tool_results",
    "next_actions",
    "ok",
    "elapsed_ms",
    "schema",
    "topic",
    "partition",
    "offset",
    "headers",
    "route",
    "body",
    "delta",
    "op",
    "value",
    "previous",
    "clock",
    "lamport",
    "source",
    "response",
    "response_id",
    "item_id",
    "output_index",
    "content_index",
    "annotations",
    "configuration",
    "historyLength",
    "acceptedOutputModes",
    "taskId",
    "append",
    "lastChunk",
    "artifact",
    "history",
    "hash_modifiers",
    "control",
    "_meta",
    "protocolVersion",
    "capabilities",
    "clientInfo",
    "clientCapabilities",
    "inputSchema",
    "outputSchema",
    "resultType",
    "ttlMs",
    "cacheScope",
    "contents",
    "mimeType",
    "messages",
    "maxTokens",
    "includeContext",
)

_COMMON_VALUES: tuple[str, ...] = (
    "2.0",
    "openai.responses",
    "responses.create",
    "response.output_item.done",
    "function",
    "function_call",
    "mcp",
    "tools/call",
    "a2a",
    "message/send",
    "agent.trace",
    "agent.handoff",
    "agent.review",
    "agent.final",
    "agent.response",
    "plan.created",
    "text",
    "object",
    "string",
    "integer",
    "user",
    "agent",
    "assistant",
    "system",
    "working",
    "completed",
    "accepted",
    "needs_review",
    "ready",
    "queued",
    "planner",
    "researcher",
    "coder",
    "reviewer",
    "executor",
    "summarizer",
    "observer",
    "web_search",
    "read_file",
    "write_patch",
    "run_shell",
    "vector_lookup",
    "search_logs",
    "policy_check",
    "memory_route",
    "continue",
    "record_latency",
    "diagnostic-summary",
    "aura.aiwire.stress",
    "response.completed",
    "response.output_text.delta",
    "response.web_search_call.completed",
    "function_call_output",
    "web_search_call",
    "output_json",
    "json_schema",
    "initialize",
    "tools/list",
    "resources/read",
    "prompts/get",
    "sampling/createMessage",
    "notifications/tools/list_changed",
    "complete",
    "public",
    "message/stream",
    "tasks/get",
    "TaskStatusUpdateEvent",
    "TaskArtifactUpdateEvent",
    "submitted",
    "input_required",
    "local.agent",
    "local.agent.broker.envelope.v1",
    "local.agent.session.handshake.v1",
    "local.agent.delta.status.v1",
    "local.agent.delta.tool_result.v1",
    "local.agent.route_hint.v1",
    "replace",
    "append",
    "command",
    "continue_task",
    "session_template_update",
)

_KEY_TO_TOKEN = {value: index for index, value in enumerate(_COMMON_KEYS)}
_TOKEN_TO_KEY = {index: value for index, value in enumerate(_COMMON_KEYS)}
_VALUE_TO_TOKEN = {value: index for index, value in enumerate(_COMMON_VALUES)}
_TOKEN_TO_VALUE = {index: value for index, value in enumerate(_COMMON_VALUES)}


class AIWireTokenError(ValueError):
    """Raised when token encoding or decoding fails."""


@dataclass(frozen=True)
class AIWireTokenStats:
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


@dataclass(frozen=True)
class AIWireTokenAIWireStats:
    """Byte counters for the tokenized AIWire pipeline.

    ``bytes_in`` is the canonical source frame size, ``token_bytes`` is the
    intermediate AIToken size, and ``bytes_out`` is the final AIWire frame size.
    """

    frames: int
    bytes_in: int
    token_bytes: int
    bytes_out: int

    @property
    def ratio(self) -> float:
        return self.bytes_in / self.bytes_out if self.bytes_out else 0.0

    @property
    def token_ratio(self) -> float:
        return self.bytes_in / self.token_bytes if self.token_bytes else 0.0

    @property
    def wire_ratio(self) -> float:
        return self.token_bytes / self.bytes_out if self.bytes_out else 0.0

    @property
    def average_bytes_in(self) -> float:
        return self.bytes_in / self.frames if self.frames else 0.0

    @property
    def average_token_bytes(self) -> float:
        return self.token_bytes / self.frames if self.frames else 0.0

    @property
    def average_bytes_out(self) -> float:
        return self.bytes_out / self.frames if self.frames else 0.0


def _write_varint(value: int, output: bytearray) -> None:
    if value < 0:
        raise AIWireTokenError("varint cannot encode negative values")
    while value >= 0x80:
        output.append((value & 0x7F) | 0x80)
        value >>= 7
    output.append(value)


def _read_varint(data: bytes, offset: int) -> tuple[int, int]:
    shift = 0
    value = 0
    while True:
        if offset >= len(data):
            raise AIWireTokenError("truncated varint")
        byte = data[offset]
        offset += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, offset
        shift += 7
        if shift > 63:
            raise AIWireTokenError("varint is too large")


def _zigzag_encode(value: int) -> int:
    return (value << 1) ^ (value >> 63)


def _zigzag_decode(value: int) -> int:
    return (value >> 1) ^ -(value & 1)


def _json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


class _StringTable:
    def __init__(self, max_entries: int) -> None:
        self.max_entries = max_entries
        self.values: list[str] = []
        self.index: dict[str, int] = {}

    def get(self, value: str) -> int | None:
        return self.index.get(value)

    def add(self, value: str) -> int | None:
        if value in self.index:
            return self.index[value]
        if len(self.values) >= self.max_entries:
            return None
        token = len(self.values)
        self.values.append(value)
        self.index[value] = token
        return token

    def at(self, token: int) -> str:
        try:
            return self.values[token]
        except IndexError as exc:
            raise AIWireTokenError(f"unknown session string token: {token}") from exc


class _NativeAIWireTokenEncoder:
    def __init__(self, *, max_session_strings: int, intern_min_length: int) -> None:
        self._handle = None
        self._lib = _get_native_library()
        if self._lib.lib is None:
            raise AIWireNativeError(self._lib.error or "native AIWire library not loaded")
        if not self._lib.supports_token_codec:
            raise AIWireNativeError("native AIWire backend lacks token codec support")
        self._handle = self._lib.lib.aura_aiwire_token_encoder_create(
            int(max_session_strings),
            int(intern_min_length),
        )
        if not self._handle:
            raise AIWireNativeError(self._lib.last_error())

    @property
    def stats(self) -> AIWireTokenStats:
        assert self._lib.lib is not None
        return AIWireTokenStats(
            frames=int(self._lib.lib.aura_aiwire_token_encoder_frames(self._handle)),
            bytes_in=int(self._lib.lib.aura_aiwire_token_encoder_bytes_in(self._handle)),
            bytes_out=int(self._lib.lib.aura_aiwire_token_encoder_bytes_out(self._handle)),
        )

    def encode_frame(self, payload: bytes) -> bytes:
        if not self._handle or self._lib.lib is None:
            raise AIWireNativeError("native AIWire token encoder is closed")
        return _bytes_from_native_call(
            self._lib,
            self._lib.lib.aura_aiwire_token_encoder_encode,
            self._handle,
            payload,
        )

    def close(self) -> None:
        if self._handle and self._lib.lib is not None:
            self._lib.lib.aura_aiwire_token_encoder_destroy(self._handle)
            self._handle = None

    def __del__(self) -> None:
        self.close()


class _NativeAIWireTokenDecoder:
    def __init__(self, *, max_session_strings: int) -> None:
        self._handle = None
        self._lib = _get_native_library()
        if self._lib.lib is None:
            raise AIWireNativeError(self._lib.error or "native AIWire library not loaded")
        if not self._lib.supports_token_codec:
            raise AIWireNativeError("native AIWire backend lacks token codec support")
        self._handle = self._lib.lib.aura_aiwire_token_decoder_create(int(max_session_strings))
        if not self._handle:
            raise AIWireNativeError(self._lib.last_error())

    @property
    def stats(self) -> AIWireTokenStats:
        assert self._lib.lib is not None
        return AIWireTokenStats(
            frames=int(self._lib.lib.aura_aiwire_token_decoder_frames(self._handle)),
            bytes_in=int(self._lib.lib.aura_aiwire_token_decoder_bytes_in(self._handle)),
            bytes_out=int(self._lib.lib.aura_aiwire_token_decoder_bytes_out(self._handle)),
        )

    def decode_frame(self, payload: bytes) -> bytes:
        if not self._handle or self._lib.lib is None:
            raise AIWireNativeError("native AIWire token decoder is closed")
        return _bytes_from_native_call(
            self._lib,
            self._lib.lib.aura_aiwire_token_decoder_decode,
            self._handle,
            payload,
        )

    def close(self) -> None:
        if self._handle and self._lib.lib is not None:
            self._lib.lib.aura_aiwire_token_decoder_destroy(self._handle)
            self._handle = None

    def __del__(self) -> None:
        self.close()


class _NativeAIWireTokenAIWireEncoder:
    def __init__(
        self,
        *,
        level: int,
        use_static_dictionary: bool,
        session_templates: AIWireSessionTemplates | None = None,
    ) -> None:
        self._handle = None
        self._lib = _get_native_library()
        if self._lib.lib is None:
            raise AIWireNativeError(self._lib.error or "native AIWire library not loaded")
        if not self._lib.supports_token_aiwire:
            raise AIWireNativeError("native AIWire backend lacks token+AIWire support")

        normalized_templates = normalize_aiwire_session_templates(session_templates)
        dictionary = _build_session_dictionary(
            use_static_dictionary=use_static_dictionary,
            session_templates=normalized_templates,
        )
        if dictionary is None:
            self._handle = self._lib.lib.aura_aiwire_token_aiwire_encoder_create(
                int(level),
                1 if use_static_dictionary else 0,
            )
        else:
            dictionary_ptr = ctypes.c_char_p(dictionary) if dictionary else None
            self._handle = self._lib.lib.aura_aiwire_token_aiwire_encoder_create_with_dictionary(
                int(level),
                dictionary_ptr,
                len(dictionary),
            )
        if not self._handle:
            raise AIWireNativeError(self._lib.last_error())

    @property
    def stats(self) -> AIWireTokenAIWireStats:
        assert self._lib.lib is not None
        return AIWireTokenAIWireStats(
            frames=int(self._lib.lib.aura_aiwire_token_aiwire_encoder_frames(self._handle)),
            bytes_in=int(self._lib.lib.aura_aiwire_token_aiwire_encoder_bytes_in(self._handle)),
            token_bytes=int(
                self._lib.lib.aura_aiwire_token_aiwire_encoder_token_bytes(self._handle)
            ),
            bytes_out=int(self._lib.lib.aura_aiwire_token_aiwire_encoder_bytes_out(self._handle)),
        )

    def encode_frame(self, payload: bytes) -> bytes:
        if not self._handle or self._lib.lib is None:
            raise AIWireNativeError("native AIWire token+AIWire encoder is closed")
        return _bytes_from_native_call(
            self._lib,
            self._lib.lib.aura_aiwire_token_aiwire_encoder_encode,
            self._handle,
            payload,
        )

    def close(self) -> None:
        if self._handle and self._lib.lib is not None:
            self._lib.lib.aura_aiwire_token_aiwire_encoder_destroy(self._handle)
            self._handle = None

    def __del__(self) -> None:
        self.close()


class _NativeAIWireTokenAIWireDecoder:
    def __init__(
        self,
        *,
        use_static_dictionary: bool,
        session_templates: AIWireSessionTemplates | None = None,
    ) -> None:
        self._handle = None
        self._lib = _get_native_library()
        if self._lib.lib is None:
            raise AIWireNativeError(self._lib.error or "native AIWire library not loaded")
        if not self._lib.supports_token_aiwire:
            raise AIWireNativeError("native AIWire backend lacks token+AIWire support")

        normalized_templates = normalize_aiwire_session_templates(session_templates)
        dictionary = _build_session_dictionary(
            use_static_dictionary=use_static_dictionary,
            session_templates=normalized_templates,
        )
        if dictionary is None:
            self._handle = self._lib.lib.aura_aiwire_token_aiwire_decoder_create(
                1 if use_static_dictionary else 0
            )
        else:
            dictionary_ptr = ctypes.c_char_p(dictionary) if dictionary else None
            self._handle = self._lib.lib.aura_aiwire_token_aiwire_decoder_create_with_dictionary(
                dictionary_ptr,
                len(dictionary),
            )
        if not self._handle:
            raise AIWireNativeError(self._lib.last_error())

    @property
    def stats(self) -> AIWireTokenAIWireStats:
        assert self._lib.lib is not None
        return AIWireTokenAIWireStats(
            frames=int(self._lib.lib.aura_aiwire_token_aiwire_decoder_frames(self._handle)),
            bytes_in=int(self._lib.lib.aura_aiwire_token_aiwire_decoder_bytes_in(self._handle)),
            token_bytes=int(
                self._lib.lib.aura_aiwire_token_aiwire_decoder_token_bytes(self._handle)
            ),
            bytes_out=int(self._lib.lib.aura_aiwire_token_aiwire_decoder_bytes_out(self._handle)),
        )

    def decode_frame(self, payload: bytes) -> bytes:
        if not self._handle or self._lib.lib is None:
            raise AIWireNativeError("native AIWire token+AIWire decoder is closed")
        return _bytes_from_native_call(
            self._lib,
            self._lib.lib.aura_aiwire_token_aiwire_decoder_decode,
            self._handle,
            payload,
        )

    def close(self) -> None:
        if self._handle and self._lib.lib is not None:
            self._lib.lib.aura_aiwire_token_aiwire_decoder_destroy(self._handle)
            self._handle = None

    def __del__(self) -> None:
        self.close()


class AIWireTokenSessionEncoder:
    """Encode structured AIWire messages into compact binary token frames."""

    def __init__(
        self,
        *,
        max_session_strings: int = 4096,
        intern_min_length: int = 6,
        use_native: bool | None = None,
    ) -> None:
        self._strings = _StringTable(max_session_strings)
        self.intern_min_length = intern_min_length
        self.backend = "python"
        self._native: _NativeAIWireTokenEncoder | None = None
        self._frames = 0
        self._bytes_in = 0
        self._bytes_out = 0

        if _native_enabled(use_native):
            try:
                self._native = _NativeAIWireTokenEncoder(
                    max_session_strings=max_session_strings,
                    intern_min_length=intern_min_length,
                )
                self.backend = "native"
                return
            except AIWireNativeError:
                if use_native is True:
                    raise

    @property
    def stats(self) -> AIWireTokenStats:
        if self._native is not None:
            return self._native.stats
        return AIWireTokenStats(self._frames, self._bytes_in, self._bytes_out)

    def encode_frame(self, message: AIWireFrame) -> bytes:
        raw = encode_ai_wire_message(message)
        if self._native is not None:
            return self._native.encode_frame(raw)

        output = bytearray(AI_WIRE_TOKEN_MAGIC)
        output.append(AI_WIRE_TOKEN_VERSION)

        try:
            value = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError):
            output.append(_FRAME_RAW_BYTES)
            _write_varint(len(raw), output)
            output.extend(raw)
        else:
            output.append(_FRAME_JSON_VALUE)
            self._encode_value(value, output)

        encoded = bytes(output)
        self._frames += 1
        self._bytes_in += len(raw)
        self._bytes_out += len(encoded)
        return encoded

    def encode_message(self, message: AIWireFrame) -> bytes:
        return self.encode_frame(message)

    def close(self) -> None:
        if self._native is not None:
            self._native.close()
            self._native = None

    def _encode_value(self, value: Any, output: bytearray) -> None:
        if value is None:
            output.append(_NULL)
        elif value is False:
            output.append(_FALSE)
        elif value is True:
            output.append(_TRUE)
        elif isinstance(value, int) and not isinstance(value, bool):
            output.append(_INT)
            _write_varint(_zigzag_encode(value), output)
        elif isinstance(value, float):
            if not math.isfinite(value):
                raise AIWireTokenError("non-finite floats are not supported")
            output.append(_FLOAT)
            raw = repr(value).encode("ascii")
            _write_varint(len(raw), output)
            output.extend(raw)
        elif isinstance(value, str):
            self._encode_string(value, output, is_key=False)
        elif isinstance(value, list):
            output.append(_ARRAY)
            _write_varint(len(value), output)
            for item in value:
                self._encode_value(item, output)
        elif isinstance(value, dict):
            output.append(_OBJECT)
            items = sorted(value.items(), key=lambda item: str(item[0]))
            _write_varint(len(items), output)
            for key, item in items:
                self._encode_string(str(key), output, is_key=True)
                self._encode_value(item, output)
        else:
            raise AIWireTokenError(f"unsupported JSON value type: {type(value).__name__}")

    def _encode_string(self, value: str, output: bytearray, *, is_key: bool) -> None:
        if is_key and value in _KEY_TO_TOKEN:
            output.append(_KEY_TOKEN)
            _write_varint(_KEY_TO_TOKEN[value], output)
            return
        if not is_key and value in _VALUE_TO_TOKEN:
            output.append(_VALUE_TOKEN)
            _write_varint(_VALUE_TO_TOKEN[value], output)
            return

        token = self._strings.get(value)
        if token is not None:
            output.append(_STRING_REF)
            _write_varint(token, output)
            return

        raw = value.encode("utf-8")
        if len(value) >= self.intern_min_length:
            token = self._strings.add(value)
            if token is not None:
                output.append(_STRING_INTERN)
                _write_varint(token, output)
                _write_varint(len(raw), output)
                output.extend(raw)
                return

        output.append(_STRING_RAW)
        _write_varint(len(raw), output)
        output.extend(raw)


class AIWireTokenSessionDecoder:
    """Decode frames emitted by :class:`AIWireTokenSessionEncoder`."""

    def __init__(
        self,
        *,
        max_session_strings: int = 4096,
        use_native: bool | None = None,
    ) -> None:
        self._strings = _StringTable(max_session_strings)
        self.backend = "python"
        self._native: _NativeAIWireTokenDecoder | None = None
        self._frames = 0
        self._bytes_in = 0
        self._bytes_out = 0

        if _native_enabled(use_native):
            try:
                self._native = _NativeAIWireTokenDecoder(
                    max_session_strings=max_session_strings,
                )
                self.backend = "native"
                return
            except AIWireNativeError:
                if use_native is True:
                    raise

    @property
    def stats(self) -> AIWireTokenStats:
        if self._native is not None:
            return self._native.stats
        return AIWireTokenStats(self._frames, self._bytes_in, self._bytes_out)

    def decode_frame(self, frame: bytes | bytearray | memoryview) -> bytes:
        data = bytes(frame)
        if self._native is not None:
            return self._native.decode_frame(data)

        if not data.startswith(AI_WIRE_TOKEN_MAGIC):
            raise AIWireTokenError("invalid AIWire token frame magic")
        offset = len(AI_WIRE_TOKEN_MAGIC)
        if offset >= len(data) or data[offset] != AI_WIRE_TOKEN_VERSION:
            raise AIWireTokenError("unsupported AIWire token frame version")
        offset += 1
        if offset >= len(data):
            raise AIWireTokenError("truncated AIWire token frame")

        frame_type = data[offset]
        offset += 1
        if frame_type == _FRAME_RAW_BYTES:
            size, offset = _read_varint(data, offset)
            end = offset + size
            if end != len(data):
                raise AIWireTokenError("raw token frame length mismatch")
            restored = data[offset:end]
        elif frame_type == _FRAME_JSON_VALUE:
            value, offset = self._decode_value(data, offset)
            if offset != len(data):
                raise AIWireTokenError("trailing bytes in token frame")
            restored = _json_bytes(value)
        else:
            raise AIWireTokenError(f"unknown AIWire token frame type: {frame_type}")

        self._frames += 1
        self._bytes_in += len(data)
        self._bytes_out += len(restored)
        return restored

    def decode_message(self, frame: bytes | bytearray | memoryview) -> Any:
        return json.loads(self.decode_frame(frame))

    def close(self) -> None:
        if self._native is not None:
            self._native.close()
            self._native = None

    def _decode_value(self, data: bytes, offset: int) -> tuple[Any, int]:
        if offset >= len(data):
            raise AIWireTokenError("truncated JSON token")
        tag = data[offset]
        offset += 1

        if tag == _NULL:
            return None, offset
        if tag == _FALSE:
            return False, offset
        if tag == _TRUE:
            return True, offset
        if tag == _INT:
            encoded, offset = _read_varint(data, offset)
            return _zigzag_decode(encoded), offset
        if tag == _FLOAT:
            raw, offset = self._read_raw_string_bytes(data, offset)
            return float(raw.decode("ascii")), offset
        if tag in {_STRING_RAW, _STRING_INTERN, _STRING_REF, _KEY_TOKEN, _VALUE_TOKEN}:
            return self._decode_string_at(data, offset, tag=tag)
        if tag == _ARRAY:
            size, offset = _read_varint(data, offset)
            items = []
            for _ in range(size):
                item, offset = self._decode_value(data, offset)
                items.append(item)
            return items, offset
        if tag == _OBJECT:
            size, offset = _read_varint(data, offset)
            result: dict[str, Any] = {}
            for _ in range(size):
                if offset >= len(data):
                    raise AIWireTokenError("truncated object key")
                key_tag = data[offset]
                offset += 1
                key, offset = self._decode_string_at(data, offset, tag=key_tag)
                item, offset = self._decode_value(data, offset)
                result[key] = item
            return result, offset
        raise AIWireTokenError(f"unknown JSON token tag: {tag}")

    def _decode_string_at(self, data: bytes, offset: int, *, tag: int) -> tuple[str, int]:
        if tag == _KEY_TOKEN:
            token, offset = _read_varint(data, offset)
            if token not in _TOKEN_TO_KEY:
                raise AIWireTokenError(f"unknown key token: {token}")
            return _TOKEN_TO_KEY[token], offset
        if tag == _VALUE_TOKEN:
            token, offset = _read_varint(data, offset)
            if token not in _TOKEN_TO_VALUE:
                raise AIWireTokenError(f"unknown value token: {token}")
            return _TOKEN_TO_VALUE[token], offset
        if tag == _STRING_REF:
            token, offset = _read_varint(data, offset)
            return self._strings.at(token), offset
        if tag == _STRING_RAW:
            raw, offset = self._read_raw_string_bytes(data, offset)
            return raw.decode("utf-8"), offset
        if tag == _STRING_INTERN:
            token, offset = _read_varint(data, offset)
            raw, offset = self._read_raw_string_bytes(data, offset)
            value = raw.decode("utf-8")
            expected = self._strings.add(value)
            if expected is not None and expected != token:
                raise AIWireTokenError("session string token mismatch")
            return value, offset
        raise AIWireTokenError(f"expected string token, got {tag}")

    @staticmethod
    def _read_raw_string_bytes(data: bytes, offset: int) -> tuple[bytes, int]:
        size, offset = _read_varint(data, offset)
        end = offset + size
        if end > len(data):
            raise AIWireTokenError("truncated string bytes")
        return data[offset:end], end


class AIWireTokenAIWireSessionEncoder:
    """Encode AI messages as AIToken frames, then compress them with AIWire."""

    def __init__(
        self,
        *,
        level: int = AI_WIRE_DEFAULT_LEVEL,
        use_static_dictionary: bool = True,
        session_templates: AIWireSessionTemplates | None = None,
        use_native: bool | None = None,
        max_session_strings: int = 4096,
        intern_min_length: int = 6,
    ) -> None:
        self._native: _NativeAIWireTokenAIWireEncoder | None = None
        if max_session_strings == 4096 and intern_min_length == 6 and _native_enabled(use_native):
            try:
                self._native = _NativeAIWireTokenAIWireEncoder(
                    level=level,
                    use_static_dictionary=use_static_dictionary,
                    session_templates=session_templates,
                )
                self.token_encoder = None
                self.wire_encoder = None
                self.backend = "aitoken+native"
                return
            except AIWireNativeError:
                if use_native is True:
                    raise

        self.token_encoder = AIWireTokenSessionEncoder(
            max_session_strings=max_session_strings,
            intern_min_length=intern_min_length,
            use_native=use_native,
        )
        self.wire_encoder = AIWireSessionEncoder(
            level=level,
            use_static_dictionary=use_static_dictionary,
            session_templates=session_templates,
            use_native=use_native,
        )
        self.backend = f"aitoken+{self.wire_encoder.backend}"

    @property
    def stats(self) -> AIWireTokenAIWireStats:
        if self._native is not None:
            return self._native.stats
        assert self.token_encoder is not None
        assert self.wire_encoder is not None
        token_stats = self.token_encoder.stats
        wire_stats = self.wire_encoder.stats
        return AIWireTokenAIWireStats(
            frames=token_stats.frames,
            bytes_in=token_stats.bytes_in,
            token_bytes=token_stats.bytes_out,
            bytes_out=wire_stats.bytes_out,
        )

    def __enter__(self) -> "AIWireTokenAIWireSessionEncoder":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def encode_frame(self, message: AIWireFrame) -> bytes:
        raw = encode_ai_wire_message(message)
        if self._native is not None:
            return self._native.encode_frame(raw)
        assert self.token_encoder is not None
        assert self.wire_encoder is not None
        token_frame = self.token_encoder.encode_frame(raw)
        return self.wire_encoder.compress_frame(token_frame)

    def encode_frames(self, frames: Iterable[AIWireFrame]) -> list[bytes]:
        return [self.encode_frame(frame) for frame in frames]

    def encode_message(self, message: AIWireFrame) -> bytes:
        return self.encode_frame(message)

    def encode_messages(self, messages: Iterable[AIWireFrame]) -> list[bytes]:
        return self.encode_frames(messages)

    def close(self) -> None:
        if self._native is not None:
            self._native.close()
            self._native = None
            return
        if self.token_encoder is not None:
            self.token_encoder.close()
        if self.wire_encoder is not None:
            self.wire_encoder.close()


class AIWireTokenAIWireSessionDecoder:
    """Decode AIWire-compressed AIToken frames back to canonical message bytes."""

    def __init__(
        self,
        *,
        use_static_dictionary: bool = True,
        session_templates: AIWireSessionTemplates | None = None,
        use_native: bool | None = None,
        max_session_strings: int = 4096,
    ) -> None:
        self._native: _NativeAIWireTokenAIWireDecoder | None = None
        if max_session_strings == 4096 and _native_enabled(use_native):
            try:
                self._native = _NativeAIWireTokenAIWireDecoder(
                    use_static_dictionary=use_static_dictionary,
                    session_templates=session_templates,
                )
                self.wire_decoder = None
                self.token_decoder = None
                self.backend = "aitoken+native"
                return
            except AIWireNativeError:
                if use_native is True:
                    raise

        self.wire_decoder = AIWireSessionDecoder(
            use_static_dictionary=use_static_dictionary,
            session_templates=session_templates,
            use_native=use_native,
        )
        self.token_decoder = AIWireTokenSessionDecoder(
            max_session_strings=max_session_strings,
            use_native=use_native,
        )
        self.backend = f"aitoken+{self.wire_decoder.backend}"

    @property
    def stats(self) -> AIWireTokenAIWireStats:
        if self._native is not None:
            return self._native.stats
        assert self.wire_decoder is not None
        assert self.token_decoder is not None
        wire_stats = self.wire_decoder.stats
        token_stats = self.token_decoder.stats
        return AIWireTokenAIWireStats(
            frames=token_stats.frames,
            bytes_in=token_stats.bytes_out,
            token_bytes=token_stats.bytes_in,
            bytes_out=wire_stats.bytes_in,
        )

    def __enter__(self) -> "AIWireTokenAIWireSessionDecoder":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def decode_frame(self, payload: bytes | bytearray | memoryview) -> bytes:
        data = bytes(payload)
        if self._native is not None:
            return self._native.decode_frame(data)
        assert self.wire_decoder is not None
        assert self.token_decoder is not None
        token_frame = self.wire_decoder.decompress_frame(data)
        return self.token_decoder.decode_frame(token_frame)

    def decode_frames(self, frames: Iterable[bytes]) -> list[bytes]:
        return [self.decode_frame(frame) for frame in frames]

    def decode_message(self, payload: bytes | bytearray | memoryview) -> Any:
        return json.loads(self.decode_frame(payload))

    def decode_messages(self, frames: Iterable[bytes]) -> list[Any]:
        return [self.decode_message(frame) for frame in frames]

    def close(self) -> None:
        if self._native is not None:
            self._native.close()
            self._native = None
            return
        if self.token_decoder is not None:
            self.token_decoder.close()
        if self.wire_decoder is not None:
            self.wire_decoder.close()


def encode_ai_wire_token_frames(
    frames: list[AIWireFrame],
) -> tuple[list[bytes], AIWireTokenStats]:
    encoder = AIWireTokenSessionEncoder()
    encoded = [encoder.encode_frame(frame) for frame in frames]
    return encoded, encoder.stats


def decode_ai_wire_token_frames(
    frames: list[bytes],
) -> tuple[list[bytes], AIWireTokenStats]:
    decoder = AIWireTokenSessionDecoder()
    decoded = [decoder.decode_frame(frame) for frame in frames]
    return decoded, decoder.stats


def encode_ai_wire_token_aiwire_frames(
    frames: Iterable[AIWireFrame],
    *,
    level: int = AI_WIRE_DEFAULT_LEVEL,
    use_static_dictionary: bool = True,
    session_templates: AIWireSessionTemplates | None = None,
    use_native: bool | None = None,
) -> tuple[list[bytes], AIWireTokenAIWireStats]:
    encoder = AIWireTokenAIWireSessionEncoder(
        level=level,
        use_static_dictionary=use_static_dictionary,
        session_templates=session_templates,
        use_native=use_native,
    )
    try:
        encoded = encoder.encode_frames(frames)
        return encoded, encoder.stats
    finally:
        encoder.close()


def decode_ai_wire_token_aiwire_frames(
    frames: Iterable[bytes],
    *,
    use_static_dictionary: bool = True,
    session_templates: AIWireSessionTemplates | None = None,
    use_native: bool | None = None,
) -> tuple[list[bytes], AIWireTokenAIWireStats]:
    decoder = AIWireTokenAIWireSessionDecoder(
        use_static_dictionary=use_static_dictionary,
        session_templates=session_templates,
        use_native=use_native,
    )
    try:
        decoded = decoder.decode_frames(frames)
        return decoded, decoder.stats
    finally:
        decoder.close()
