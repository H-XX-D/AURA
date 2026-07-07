"""Persistent AIWire session-resume cache.

The cache stores peer dictionary state hashes and their template shapes so a
later connection can offer a resume hello without relearning recurring session
structure. Authentication material is intentionally supplied only at handshake
time and is never persisted here.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from .ai_wire import (
    AI_WIRE_DELTA_VERSION,
    AI_WIRE_DICTIONARY_SHA256,
    AIWireHandshakeError,
    AIWireSessionResumeHello,
    AIWireSessionResumeResponse,
    AIWireSessionTemplates,
    aiwire_session_dictionary_state_sha256,
    build_aiwire_session_resume_hello,
    negotiate_aiwire_session_resume,
    normalize_aiwire_session_templates,
    verify_aiwire_session_resume_response,
)

AI_WIRE_RESUME_CACHE_SCHEMA = "aura.aiwire.resume_cache.v1"
AI_WIRE_RESUME_CACHE_ENTRY_SCHEMA = "aura.aiwire.resume_cache.entry.v1"
AI_WIRE_RESUME_CACHE_ENV = "AURA_AIWIRE_RESUME_CACHE"


def default_aiwire_resume_cache_path() -> Path:
    """Return the default local resume-cache path."""

    configured = os.getenv(AI_WIRE_RESUME_CACHE_ENV)
    if configured:
        return Path(configured).expanduser()

    xdg_cache_home = os.getenv("XDG_CACHE_HOME")
    if xdg_cache_home:
        return Path(xdg_cache_home).expanduser() / "aura" / "aiwire_resume_cache.json"

    return Path.home() / ".cache" / "aura" / "aiwire_resume_cache.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _validate_sha256_hex(value: str, field_name: str) -> None:
    if len(value) != 64:
        raise AIWireHandshakeError(f"{field_name} must be a SHA-256 hex digest")
    try:
        bytes.fromhex(value)
    except ValueError as exc:
        raise AIWireHandshakeError(f"{field_name} must be hex") from exc


def _validate_non_empty(value: str, field_name: str) -> str:
    normalized = str(value)
    if not normalized:
        raise AIWireHandshakeError(f"{field_name} must not be empty")
    return normalized


@dataclass(frozen=True)
class AIWireResumeCacheEntry:
    """Known peer/session dictionary state that can be offered for resume."""

    peer_id: str
    app_namespace: str
    state_hash: str
    session_templates: tuple[tuple[int, str], ...]
    epoch: int
    static_dictionary_sha256: str = AI_WIRE_DICTIONARY_SHA256
    delta_version: int = AI_WIRE_DELTA_VERSION
    updated_at_utc: str = ""
    label: str | None = None

    def __post_init__(self) -> None:
        _validate_non_empty(self.peer_id, "peer_id")
        _validate_non_empty(self.app_namespace, "app_namespace")
        _validate_sha256_hex(self.state_hash, "state_hash")
        _validate_sha256_hex(self.static_dictionary_sha256, "static_dictionary_sha256")
        if self.epoch < 0:
            raise AIWireHandshakeError("epoch must be non-negative")
        if self.delta_version <= 0:
            raise AIWireHandshakeError("delta_version must be positive")
        normalize_aiwire_session_templates(self.session_templates)

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "schema": AI_WIRE_RESUME_CACHE_ENTRY_SCHEMA,
            "peer_id": self.peer_id,
            "app_namespace": self.app_namespace,
            "state_hash": self.state_hash,
            "session_templates": [
                {"template_id": template_id, "pattern": pattern}
                for template_id, pattern in self.session_templates
            ],
            "epoch": self.epoch,
            "static_dictionary_sha256": self.static_dictionary_sha256,
            "delta_version": self.delta_version,
            "updated_at_utc": self.updated_at_utc,
            "label": self.label,
        }
        return payload

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "AIWireResumeCacheEntry":
        if value.get("schema") != AI_WIRE_RESUME_CACHE_ENTRY_SCHEMA:
            raise AIWireHandshakeError("unsupported AIWire resume-cache entry schema")
        try:
            return cls(
                peer_id=str(value["peer_id"]),
                app_namespace=str(value.get("app_namespace", "default")),
                state_hash=str(value["state_hash"]),
                session_templates=normalize_aiwire_session_templates(
                    value.get("session_templates", ())
                ),
                epoch=int(value["epoch"]),
                static_dictionary_sha256=str(
                    value.get("static_dictionary_sha256", AI_WIRE_DICTIONARY_SHA256)
                ),
                delta_version=int(value.get("delta_version", AI_WIRE_DELTA_VERSION)),
                updated_at_utc=str(value.get("updated_at_utc", "")),
                label=(str(value["label"]) if value.get("label") is not None else None),
            )
        except (KeyError, TypeError, ValueError, AIWireHandshakeError) as exc:
            raise AIWireHandshakeError(f"malformed AIWire resume-cache entry: {exc}") from exc


class AIWireResumeCache:
    """JSON-backed cache for AIWire future-connection resume state."""

    def __init__(self, path: str | os.PathLike[str] | None = None, *, autoload: bool = True):
        self.path = (
            Path(path).expanduser() if path is not None else default_aiwire_resume_cache_path()
        )
        self._entries: dict[tuple[str, str, str], AIWireResumeCacheEntry] = {}
        if autoload:
            self.load()

    @property
    def entries(self) -> tuple[AIWireResumeCacheEntry, ...]:
        return tuple(
            sorted(
                self._entries.values(),
                key=lambda entry: (
                    entry.peer_id,
                    entry.app_namespace,
                    entry.updated_at_utc,
                    entry.state_hash,
                ),
                reverse=True,
            )
        )

    def load(self) -> "AIWireResumeCache":
        if not self.path.exists():
            self._entries = {}
            return self

        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(payload, Mapping):
            raise AIWireHandshakeError("AIWire resume cache must be a JSON object")
        if payload.get("schema") != AI_WIRE_RESUME_CACHE_SCHEMA:
            raise AIWireHandshakeError("unsupported AIWire resume-cache schema")

        entries: dict[tuple[str, str, str], AIWireResumeCacheEntry] = {}
        raw_entries = payload.get("entries", ())
        if not isinstance(raw_entries, Iterable) or isinstance(raw_entries, (str, bytes)):
            raise AIWireHandshakeError("AIWire resume-cache entries must be a list")
        for raw_entry in raw_entries:
            if not isinstance(raw_entry, Mapping):
                raise AIWireHandshakeError("AIWire resume-cache entry must be an object")
            entry = AIWireResumeCacheEntry.from_dict(raw_entry)
            entries[(entry.peer_id, entry.app_namespace, entry.state_hash)] = entry
        self._entries = entries
        return self

    def save(self) -> None:
        if not self.path.parent.exists():
            self.path.parent.mkdir(parents=True, mode=0o700)
        else:
            self.path.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "schema": AI_WIRE_RESUME_CACHE_SCHEMA,
            "updated_at_utc": _utc_now(),
            "entries": [entry.to_dict() for entry in self.entries],
        }
        rendered = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"

        fd, temp_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.",
            suffix=".tmp",
            dir=str(self.path.parent),
            text=True,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as temp_file:
                temp_file.write(rendered)
            os.chmod(temp_name, 0o600)
            os.replace(temp_name, self.path)
        finally:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass

    def put_state(
        self,
        *,
        peer_id: str,
        session_templates: AIWireSessionTemplates | None,
        epoch: int,
        app_namespace: str = "default",
        label: str | None = None,
        static_dictionary_sha256: str = AI_WIRE_DICTIONARY_SHA256,
        delta_version: int = AI_WIRE_DELTA_VERSION,
        save: bool = True,
    ) -> AIWireResumeCacheEntry:
        if delta_version != AI_WIRE_DELTA_VERSION:
            raise AIWireHandshakeError(f"unsupported AIWire delta version: {delta_version}")
        peer = _validate_non_empty(peer_id, "peer_id")
        namespace = _validate_non_empty(app_namespace, "app_namespace")
        templates = normalize_aiwire_session_templates(session_templates)
        state_hash = aiwire_session_dictionary_state_sha256(
            templates,
            epoch=epoch,
            static_dictionary_sha256=static_dictionary_sha256,
        )
        entry = AIWireResumeCacheEntry(
            peer_id=peer,
            app_namespace=namespace,
            state_hash=state_hash,
            session_templates=templates,
            epoch=epoch,
            static_dictionary_sha256=static_dictionary_sha256,
            delta_version=delta_version,
            updated_at_utc=_utc_now(),
            label=label,
        )
        self._entries[(entry.peer_id, entry.app_namespace, entry.state_hash)] = entry
        if save:
            self.save()
        return entry

    def entries_for(
        self,
        peer_id: str,
        app_namespace: str = "default",
        *,
        static_dictionary_sha256: str = AI_WIRE_DICTIONARY_SHA256,
        delta_version: int = AI_WIRE_DELTA_VERSION,
    ) -> tuple[AIWireResumeCacheEntry, ...]:
        peer = _validate_non_empty(peer_id, "peer_id")
        namespace = _validate_non_empty(app_namespace, "app_namespace")
        return tuple(
            entry
            for entry in self.entries
            if entry.peer_id == peer
            and entry.app_namespace == namespace
            and entry.static_dictionary_sha256 == static_dictionary_sha256
            and entry.delta_version == delta_version
        )

    def cached_state_hashes(
        self,
        peer_id: str,
        app_namespace: str = "default",
        *,
        static_dictionary_sha256: str = AI_WIRE_DICTIONARY_SHA256,
        delta_version: int = AI_WIRE_DELTA_VERSION,
    ) -> tuple[str, ...]:
        return tuple(
            entry.state_hash
            for entry in self.entries_for(
                peer_id,
                app_namespace,
                static_dictionary_sha256=static_dictionary_sha256,
                delta_version=delta_version,
            )
        )

    def get_state(
        self,
        state_hash: str,
        *,
        peer_id: str | None = None,
        app_namespace: str | None = None,
    ) -> AIWireResumeCacheEntry:
        _validate_sha256_hex(state_hash, "state_hash")
        matches = [
            entry
            for entry in self._entries.values()
            if entry.state_hash == state_hash
            and (peer_id is None or entry.peer_id == peer_id)
            and (app_namespace is None or entry.app_namespace == app_namespace)
        ]
        if not matches:
            raise AIWireHandshakeError("unknown AIWire resume-cache state hash")
        if len(matches) > 1:
            raise AIWireHandshakeError("ambiguous AIWire resume-cache state hash")
        return matches[0]

    def build_resume_hello(
        self,
        *,
        peer_id: str,
        app_namespace: str = "default",
        auth_key: bytes | bytearray | memoryview | str | None = None,
        nonce: str | None = None,
    ) -> AIWireSessionResumeHello:
        return build_aiwire_session_resume_hello(
            peer_id=peer_id,
            app_namespace=app_namespace,
            cached_state_hashes=self.cached_state_hashes(peer_id, app_namespace),
            auth_key=auth_key,
            nonce=nonce,
        )

    def negotiate_resume(
        self,
        hello: AIWireSessionResumeHello | dict[str, object],
        *,
        auth_key: bytes | bytearray | memoryview | str | None = None,
        nonce: str | None = None,
    ) -> AIWireSessionResumeResponse:
        parsed = (
            hello
            if isinstance(hello, AIWireSessionResumeHello)
            else AIWireSessionResumeHello.from_dict(hello)
        )
        available_hashes = self.cached_state_hashes(
            parsed.peer_id,
            parsed.app_namespace,
            static_dictionary_sha256=parsed.static_dictionary_sha256,
        )
        return negotiate_aiwire_session_resume(
            parsed,
            available_state_hashes=available_hashes,
            static_dictionary_sha256=AI_WIRE_DICTIONARY_SHA256,
            auth_key=auth_key,
            nonce=nonce,
        )

    def verify_resume_response(
        self,
        hello: AIWireSessionResumeHello | dict[str, object],
        response: AIWireSessionResumeResponse | dict[str, object],
        *,
        auth_key: bytes | bytearray | memoryview | str | None = None,
    ) -> AIWireResumeCacheEntry:
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
        verify_aiwire_session_resume_response(parsed_hello, parsed_response, auth_key=auth_key)
        if parsed_response.resume_state_hash is None:
            raise AIWireHandshakeError("session resume response did not select a state hash")
        entry = self.get_state(
            parsed_response.resume_state_hash,
            peer_id=parsed_hello.peer_id,
            app_namespace=parsed_hello.app_namespace,
        )
        if entry.static_dictionary_sha256 != parsed_response.static_dictionary_sha256:
            raise AIWireHandshakeError("session resume cached static dictionary mismatch")
        if entry.delta_version != parsed_response.selected_delta_version:
            raise AIWireHandshakeError("session resume cached delta version mismatch")
        return entry
