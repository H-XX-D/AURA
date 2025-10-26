#!/usr/bin/env python3
"""Optional metadata sidechain storage for fast-path retrieval."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional


_DEF_DB_PATH = "./sidechain/sidechain.db"
_DEF_BLOB_DIR = "./sidechain/blobs"
_DEF_COLD_DIR = "./sidechain/cold"


def _iso_utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _stringify(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except TypeError:
        return str(value)


@dataclass
class SidechainConfig:
    """Runtime configuration for the sidechain service."""

    enabled: bool = False
    db_path: str = _DEF_DB_PATH
    blob_dir: str = _DEF_BLOB_DIR
    inline_threshold: int = 4096
    blob_threshold: int = 65536
    cold_storage_dir: Optional[str] = _DEF_COLD_DIR

    @classmethod
    def from_overrides(cls, overrides: Optional[Dict[str, Any]] = None, *, enabled: bool = True) -> "SidechainConfig":
        base = {
            "enabled": enabled,
            "db_path": os.getenv("AURA_SIDECHAIN_DB_PATH", _DEF_DB_PATH),
            "blob_dir": os.getenv("AURA_SIDECHAIN_BLOB_DIR", _DEF_BLOB_DIR),
            "inline_threshold": int(os.getenv("AURA_SIDECHAIN_INLINE_THRESHOLD", "4096")),
            "blob_threshold": int(os.getenv("AURA_SIDECHAIN_BLOB_THRESHOLD", "65536")),
            "cold_storage_dir": os.getenv("AURA_SIDECHAIN_COLD_DIR", _DEF_COLD_DIR) or None,
        }
        if overrides:
            base.update(overrides)
        return cls(**base)


class NoOpSidechainService:
    """Disabled sidechain implementation."""

    @property
    def is_enabled(self) -> bool:
        return False

    def store_entry(self, payload: bytes, metadata: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Optional[str]:
        return None

    def fetch_recent(self, limit: int = 10) -> List[Dict[str, Any]]:
        return []

    def close(self) -> None:
        return None


class SidechainService:
    """SQLite-backed sidechain metadata store with blob spillover."""

    def __init__(self, config: SidechainConfig):
        self._config = config
        self._enabled = config.enabled
        self._cold_dir = Path(config.cold_storage_dir) if config.cold_storage_dir else None
        if not self._enabled:
            self._conn = None
            self._lock = threading.Lock()
            self._blob_dir = Path(config.blob_dir)
            return

        self._db_path = Path(config.db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._blob_dir = Path(config.blob_dir)
        self._blob_dir.mkdir(parents=True, exist_ok=True)
        if self._cold_dir:
            self._cold_dir.mkdir(parents=True, exist_ok=True)

        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    def _init_schema(self) -> None:
        if not self._conn:
            return
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS sidechain_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    message_hash TEXT NOT NULL,
                    compression_method TEXT,
                    original_size INTEGER,
                    compressed_size INTEGER,
                    storage_kind TEXT NOT NULL,
                    blob_ref TEXT,
                    metadata TEXT,
                    session_id TEXT,
                    user_id TEXT,
                    payload BLOB
                )
                """
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_sidechain_hash ON sidechain_messages(message_hash)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_sidechain_created ON sidechain_messages(created_at)"
            )
            self._conn.commit()

    def store_entry(
        self,
        payload: bytes,
        metadata: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        if not self.is_enabled or payload is None:
            return None

        context = context or {}

        compressed_size = len(payload)
        original_size = metadata.get("original_size")
        method = metadata.get("method")
        message_hash = hashlib.sha256(payload).hexdigest()

        storage_kind = "inline"
        blob_ref: Optional[str] = None
        inline_payload: Optional[bytes] = payload

        if compressed_size > self._config.inline_threshold:
            inline_payload = None
            if compressed_size <= self._config.blob_threshold:
                storage_kind = "blob"
                blob_ref = self._write_blob(message_hash, payload)
            else:
                if self._cold_dir is not None:
                    storage_kind = "cold"
                    blob_ref = self._write_cold_blob(message_hash, payload)
                else:
                    storage_kind = "external"
                    blob_ref = "external:audit"

        # Ensure metadata is JSON-safe
        safe_metadata = json.dumps(metadata, default=_stringify, separators=(",", ":"))

        created_at = _iso_utc_now()
        session_id = context.get("session_id")
        user_id = context.get("user_id")

        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute(
                """
                INSERT INTO sidechain_messages (
                    created_at,
                    message_hash,
                    compression_method,
                    original_size,
                    compressed_size,
                    storage_kind,
                    blob_ref,
                    metadata,
                    session_id,
                    user_id,
                    payload
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    created_at,
                    message_hash,
                    method,
                    original_size,
                    compressed_size,
                    storage_kind,
                    blob_ref,
                    safe_metadata,
                    session_id,
                    user_id,
                    inline_payload,
                ),
            )
            self._conn.commit()
            record_id = cursor.lastrowid

        if storage_kind == "inline":
            return f"inline:{record_id}"
        return blob_ref

    def fetch_recent(self, limit: int = 10) -> List[Dict[str, Any]]:
        if not self.is_enabled:
            return []
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute(
                "SELECT * FROM sidechain_messages ORDER BY id DESC LIMIT ?",
                (int(limit),),
            )
            rows = cursor.fetchall()
        results: List[Dict[str, Any]] = []
        for row in rows:
            entry = dict(row)
            try:
                entry["metadata"] = json.loads(entry["metadata"] or "{}")
            except json.JSONDecodeError:
                entry["metadata"] = {}
            results.append(entry)
        return results

    def close(self) -> None:
        if self._conn is not None:
            with self._lock:
                self._conn.close()
                self._conn = None

    def _write_blob(self, message_hash: str, payload: bytes) -> str:
        """Persist payload to blob directory using the hash as filename."""
        blob_path = self._blob_dir / f"{message_hash}.bin"
        if blob_path.exists():
            return str(blob_path)
        tmp_path = blob_path.with_suffix(".tmp")
        with open(tmp_path, "wb") as handle:
            handle.write(payload)
        os.replace(tmp_path, blob_path)
        return str(blob_path)

    def _write_cold_blob(self, message_hash: str, payload: bytes) -> str:
        if self._cold_dir is None:
            raise RuntimeError("Cold storage directory is not configured")
        cold_path = self._cold_dir / f"{message_hash}.cold"
        if cold_path.exists():
            return str(cold_path)
        tmp_path = cold_path.with_suffix(".tmp")
        with open(tmp_path, "wb") as handle:
            handle.write(payload)
        os.replace(tmp_path, cold_path)
        return str(cold_path)

    def __del__(self) -> None:  # pragma: no cover - best effort cleanup
        try:
            self.close()
        except Exception:
            pass


__all__ = [
    "SidechainConfig",
    "SidechainService",
    "NoOpSidechainService",
]
