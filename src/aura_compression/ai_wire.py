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
import os
import sys
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

AI_WIRE_VERSION = 1
AI_WIRE_SUPPORTED_VERSIONS = (AI_WIRE_VERSION,)
AI_WIRE_PROTOCOL = "aura.aiwire"
AI_WIRE_HANDSHAKE_SCHEMA = "aura.aiwire.handshake.v1"
AI_WIRE_NEGOTIATION_SCHEMA = "aura.aiwire.negotiation.v1"
AI_WIRE_WBITS = -15
AI_WIRE_MEM_LEVEL = 8
AI_WIRE_DEFAULT_LEVEL = 3
AI_WIRE_FLUSH_MODE = "z_sync_flush"


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
    # MCP shaped traffic.
    '"protocol":"mcp"',
    '"method":"tools/call"',
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
    '"message":',
    '"messageId":',
    '"contextId":',
    '"status":',
    '"state":"working"',
    '"state":"completed"',
    '"artifacts":',
    '"artifactId":',
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


def _fnv1a64(data: bytes) -> int:
    value = 14695981039346656037
    for byte in data:
        value ^= byte
        value = (value * 1099511628211) & 0xFFFFFFFFFFFFFFFF
    return value


AI_WIRE_DICTIONARY_FNV1A64 = _fnv1a64(AI_WIRE_STATIC_DICTIONARY)


class AIWireNativeError(RuntimeError):
    """Raised when the native C++ AIWire backend reports an error."""


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

    def as_dict(self) -> dict[str, object]:
        return {
            "available": self.available,
            "library_path": self.library_path,
            "version": self.version,
            "error": self.error,
            "dictionary_size": self.dictionary_size,
            "dictionary_checksum": self.dictionary_checksum,
            "dictionary_matches_python": self.dictionary_matches_python,
        }


class _NativeAIWireLibrary:
    """ctypes loader for ``libaura_aiwire``."""

    def __init__(self) -> None:
        self.library_path: str | None = None
        self.error: str | None = None
        self.lib: ctypes.CDLL | None = None
        self.version: str | None = None
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
                self._configure_signatures(lib)
                raw_version = lib.aura_aiwire_backend_version()
                self.version = (
                    raw_version.decode("utf-8", errors="replace") if raw_version else None
                )
                return
            except (OSError, AttributeError) as exc:
                errors.append(f"{library_path}: {exc}")
        self.error = "; ".join(errors) if errors else "libaura_aiwire not found"

    @staticmethod
    def _configure_signatures(lib: ctypes.CDLL) -> None:
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

    def to_dict(self) -> dict[str, object]:
        return {
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
        }

    @classmethod
    def from_dict(cls, value: dict[str, object]) -> "AIWireHandshake":
        if value.get("schema") != AI_WIRE_HANDSHAKE_SCHEMA:
            raise AIWireHandshakeError("unsupported AIWire handshake schema")
        if value.get("protocol") != AI_WIRE_PROTOCOL:
            raise AIWireHandshakeError("unsupported AIWire protocol")

        try:
            versions = tuple(int(version) for version in value["versions"])  # type: ignore[index]
            fallback_codecs = tuple(str(codec) for codec in value.get("fallback_codecs", ()))
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
            )
        except (KeyError, TypeError, ValueError) as exc:
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
    fallback_codecs: Iterable[str] = ("zlib", "raw"),
) -> AIWireHandshake:
    if not 0 <= level <= 9:
        raise ValueError(f"zlib level must be in [0, 9], got {level}")

    native_status = aiwire_native_status()
    backend = "native" if _native_enabled(use_native) and native_status.available else "python"

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
        fallback_codecs=tuple(fallback_codecs),
    )


def negotiate_aiwire_handshake(
    peer_handshake: dict[str, object] | AIWireHandshake,
    *,
    level: int = AI_WIRE_DEFAULT_LEVEL,
    use_static_dictionary: bool = True,
    use_native: bool | None = None,
    fallback_codecs: Iterable[str] = ("zlib", "raw"),
    allow_fallback: bool = True,
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
    )

    common_versions = sorted(set(peer.versions).intersection(local.versions), reverse=True)
    reason = None
    if not common_versions:
        reason = "no_common_aiwire_version"
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
        local_fallbacks = tuple(fallback_codecs)
        peer_fallbacks = set(peer.fallback_codecs)
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
    def __init__(self, *, level: int, use_static_dictionary: bool) -> None:
        self._handle = None
        self._lib = _get_native_library()
        if self._lib.lib is None:
            raise AIWireNativeError(self._lib.error or "native AIWire library not loaded")

        self._handle = self._lib.lib.aura_aiwire_encoder_create(
            int(level),
            1 if use_static_dictionary else 0,
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
    def __init__(self, *, use_static_dictionary: bool) -> None:
        self._handle = None
        self._lib = _get_native_library()
        if self._lib.lib is None:
            raise AIWireNativeError(self._lib.error or "native AIWire library not loaded")

        self._handle = self._lib.lib.aura_aiwire_decoder_create(
            1 if use_static_dictionary else 0,
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


class AIWireSessionEncoder:
    """Stateful encoder for ordered AI-to-AI message frames."""

    def __init__(
        self,
        *,
        level: int = AI_WIRE_DEFAULT_LEVEL,
        use_static_dictionary: bool = True,
        use_native: bool | None = None,
    ) -> None:
        if not 0 <= level <= 9:
            raise ValueError(f"zlib level must be in [0, 9], got {level}")

        self.level = level
        self.use_static_dictionary = use_static_dictionary
        self.backend = "python"
        self._native: _NativeAIWireEncoder | None = None
        self._compressor: zlib.compressobj | None = None
        self._frames = 0
        self._bytes_in = 0
        self._bytes_out = 0

        if _native_enabled(use_native):
            try:
                self._native = _NativeAIWireEncoder(
                    level=level,
                    use_static_dictionary=use_static_dictionary,
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
        if use_static_dictionary:
            kwargs["zdict"] = AI_WIRE_STATIC_DICTIONARY
        self._compressor = zlib.compressobj(**kwargs)

    @property
    def stats(self) -> AIWireStats:
        return AIWireStats(
            frames=self._frames,
            bytes_in=self._bytes_in,
            bytes_out=self._bytes_out,
        )

    def compress_frame(self, payload: bytes | str) -> bytes:
        raw = payload.encode("utf-8") if isinstance(payload, str) else bytes(payload)
        if self._native is not None:
            compressed = self._native.compress_frame(raw)
        else:
            assert self._compressor is not None
            compressed = self._compressor.compress(raw) + self._compressor.flush(zlib.Z_SYNC_FLUSH)
        self._frames += 1
        self._bytes_in += len(raw)
        self._bytes_out += len(compressed)
        return compressed

    def compress_frames(self, frames: Iterable[bytes | str]) -> list[bytes]:
        return [self.compress_frame(frame) for frame in frames]

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
        use_native: bool | None = None,
    ) -> None:
        self.use_static_dictionary = use_static_dictionary
        self.backend = "python"
        self._native: _NativeAIWireDecoder | None = None
        self._decompressor: zlib.decompressobj | None = None
        self._frames = 0
        self._bytes_in = 0
        self._bytes_out = 0

        if _native_enabled(use_native):
            try:
                self._native = _NativeAIWireDecoder(
                    use_static_dictionary=use_static_dictionary,
                )
                self.backend = "native"
                return
            except AIWireNativeError:
                if use_native is True:
                    raise

        kwargs = {"wbits": AI_WIRE_WBITS}
        if use_static_dictionary:
            kwargs["zdict"] = AI_WIRE_STATIC_DICTIONARY
        self._decompressor = zlib.decompressobj(**kwargs)

    @property
    def stats(self) -> AIWireStats:
        return AIWireStats(
            frames=self._frames,
            bytes_in=self._bytes_in,
            bytes_out=self._bytes_out,
        )

    def decompress_frame(self, payload: bytes) -> bytes:
        if self._native is not None:
            restored = self._native.decompress_frame(payload)
        else:
            assert self._decompressor is not None
            restored = self._decompressor.decompress(payload)
        if self._decompressor is not None and self._decompressor.unused_data:
            raise ValueError("AI wire frame contains unused compressed data")
        self._frames += 1
        self._bytes_in += len(payload)
        self._bytes_out += len(restored)
        return restored

    def decompress_frames(self, frames: Iterable[bytes]) -> list[bytes]:
        return [self.decompress_frame(frame) for frame in frames]

    def close(self) -> None:
        if self._native is not None:
            self._native.close()
            self._native = None


def compress_ai_wire_frames(
    frames: Iterable[bytes | str],
    *,
    level: int = AI_WIRE_DEFAULT_LEVEL,
    use_static_dictionary: bool = True,
    use_native: bool | None = None,
) -> tuple[list[bytes], AIWireStats]:
    encoder = AIWireSessionEncoder(
        level=level,
        use_static_dictionary=use_static_dictionary,
        use_native=use_native,
    )
    compressed = encoder.compress_frames(frames)
    return compressed, encoder.stats


def decompress_ai_wire_frames(
    frames: Iterable[bytes],
    *,
    use_static_dictionary: bool = True,
    use_native: bool | None = None,
) -> tuple[list[bytes], AIWireStats]:
    decoder = AIWireSessionDecoder(
        use_static_dictionary=use_static_dictionary,
        use_native=use_native,
    )
    restored = decoder.decompress_frames(frames)
    return restored, decoder.stats
