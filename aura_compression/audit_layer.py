#!/usr/bin/env python3
"""AURA Compression Server-Side Audit Layer (simplified)."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class AuditLevel(Enum):
    """Audit log levels."""

    INFO = 1
    WARNING = 2
    ERROR = 3
    SECURITY = 4


class CompressionEvent(Enum):
    """Compression events that are audited."""

    COMPRESS_START = "compress_start"
    COMPRESS_SUCCESS = "compress_success"
    COMPRESS_FAILURE = "compress_failure"
    DECOMPRESS_START = "decompress_start"
    DECOMPRESS_SUCCESS = "decompress_success"
    DECOMPRESS_FAILURE = "decompress_failure"
    METHOD_SELECTION = "method_selection"
    DICTIONARY_BUILD = "dictionary_build"
    PATTERN_DISCOVERY = "pattern_discovery"
    FILE_UPLOAD = "file_upload"
    FILE_DOWNLOAD = "file_download"


@dataclass
class AuditEntry:
    """Single audit log entry."""

    timestamp: str
    event_id: str
    level: str
    event_type: str
    user_id: Optional[str]
    session_id: Optional[str]
    source_ip: Optional[str]
    method: Optional[str]
    original_size: int
    compressed_size: int
    compression_ratio: float
    latency_ms: float
    data_hash: Optional[str]
    result_hash: Optional[str]
    metadata: Dict[str, Any]
    previous_hash: Optional[str]
    entry_hash: Optional[str]


# ---------------------------------------------------------------------------
# Metadata alias helpers (shared with audit logger)


_METADATA_ALIASES: Dict[str, str] = {}
_REVERSE_ALIASES: Dict[str, str] = {}


def register_metadata_aliases(alias_map: Dict[str, str]) -> None:
    for key, alias in alias_map.items():
        _METADATA_ALIASES[key] = alias
        _REVERSE_ALIASES.setdefault(alias, key)


register_metadata_aliases(
    {
        "original_size": "os",
        "compressed_size": "cs",
        "compression_ratio": "cr",
        "latency_ms": "l",
        "method": "m",
        "fast_path_candidate": "fpc",
        "fast_path_used": "fpu",
        "reason": "r",
        "template_ids": "tids",
        "template_id": "tid",
        "template_count": "tc",
        "normalization_count": "nc",
        "attempted_methods": "am",
        "ratio": "cr",
    }
)


def compact_metadata(metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not metadata:
        return {}
    compact: Dict[str, Any] = {}
    for key, value in metadata.items():
        if value in (None, [], {}):
            continue
        alias = _METADATA_ALIASES.get(key, key)
        compact[alias] = value
    if compact:
        compact.setdefault("mv", 1)
    return compact


def expand_metadata(metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not metadata:
        return {}
    expanded: Dict[str, Any] = {}
    for key, value in metadata.items():
        if key == "mv":
            continue
        expanded[_REVERSE_ALIASES.get(key, key)] = value
    return expanded


def _iso_utc_now() -> str:
    """Return an ISO-8601 UTC timestamp with trailing Z."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# SQLite-backed audit log storage


class AuditDatabase:
    """Thin SQLite wrapper used by the compression auditor."""

    def __init__(self, db_path: str = "audit/compression_audit.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.lock = threading.Lock()
        self._init_schema()

    def _init_schema(self) -> None:
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    event_id TEXT UNIQUE NOT NULL,
                    level TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    user_id TEXT,
                    session_id TEXT,
                    source_ip TEXT,
                    method TEXT,
                    original_size INTEGER,
                    compressed_size INTEGER,
                    compression_ratio REAL,
                    latency_ms REAL,
                    data_hash TEXT,
                    result_hash TEXT,
                    metadata TEXT,
                    previous_hash TEXT,
                    entry_hash TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS security_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    user_id TEXT,
                    source_ip TEXT,
                    description TEXT,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_event ON audit_log(event_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_session ON audit_log(session_id)")
            self.conn.commit()

    def insert(self, entry: AuditEntry) -> int:
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                INSERT INTO audit_log (
                    timestamp, event_id, level, event_type, user_id, session_id, source_ip,
                    method, original_size, compressed_size, compression_ratio, latency_ms,
                    data_hash, result_hash, metadata, previous_hash, entry_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.timestamp,
                    entry.event_id,
                    entry.level,
                    entry.event_type,
                    entry.user_id,
                    entry.session_id,
                    entry.source_ip,
                    entry.method,
                    entry.original_size,
                    entry.compressed_size,
                    entry.compression_ratio,
                    entry.latency_ms,
                    entry.data_hash,
                    entry.result_hash,
                    json.dumps(entry.metadata, separators=(",", ":")),
                    entry.previous_hash,
                    entry.entry_hash,
                ),
            )
            self.conn.commit()
            return cursor.lastrowid

    def query(self, filters: Dict[str, Any], limit: int = 100) -> List[Dict[str, Any]]:
        where: List[str] = []
        params: List[Any] = []
        if "start_time" in filters:
            where.append("timestamp >= ?")
            params.append(filters["start_time"])
        if "end_time" in filters:
            where.append("timestamp <= ?")
            params.append(filters["end_time"])
        if "event_type" in filters:
            where.append("event_type = ?")
            params.append(filters["event_type"])
        if "user_id" in filters:
            where.append("user_id = ?")
            params.append(filters["user_id"])
        if "session_id" in filters:
            where.append("session_id = ?")
            params.append(filters["session_id"])

        where_sql = " AND ".join(where) if where else "1=1"
        query_sql = f"SELECT * FROM audit_log WHERE {where_sql} ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute(query_sql, params)
            columns = [col[0] for col in cursor.description]
            rows = []
            for row in cursor.fetchall():
                entry = dict(zip(columns, row))
                metadata_blob = entry.get("metadata")
                entry["metadata"] = expand_metadata(json.loads(metadata_blob)) if metadata_blob else {}
                rows.append(entry)
            return rows

    def aggregate_metrics(self, start_time: str, end_time: str) -> Dict[str, Any]:
        query_sql = (
            """
            SELECT method,
                   COUNT(*) as operations,
                   SUM(original_size) as total_in,
                   SUM(compressed_size) as total_out,
                   AVG(compression_ratio) as avg_ratio,
                   AVG(latency_ms) as avg_latency,
                   MIN(latency_ms) as min_latency,
                   MAX(latency_ms) as max_latency
            FROM audit_log
            WHERE timestamp >= ? AND timestamp <= ?
              AND event_type IN ('compress_success', 'decompress_success')
            GROUP BY method
            """
        )
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute(query_sql, (start_time, end_time))
            metrics: Dict[str, Any] = {}
            for row in cursor.fetchall():
                method = row[0] or "unknown"
                metrics[method] = {
                    "operations": row[1],
                    "total_bytes_in": row[2],
                    "total_bytes_out": row[3],
                    "avg_ratio": row[4],
                    "avg_latency_ms": row[5],
                    "min_latency_ms": row[6],
                    "max_latency_ms": row[7],
                }
            return metrics

    def insert_security_event(
        self,
        timestamp: str,
        event_type: str,
        severity: str,
        user_id: Optional[str],
        source_ip: Optional[str],
        description: str,
        metadata: Dict[str, Any],
    ) -> None:
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                INSERT INTO security_events (
                    timestamp, event_type, severity, user_id, source_ip, description, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (timestamp, event_type, severity, user_id, source_ip, description, json.dumps(metadata)),
            )
            self.conn.commit()

    def close(self) -> None:
        self.conn.close()


# ---------------------------------------------------------------------------
# Compression auditor facade


class CompressionAuditor:
    """High-level facade that records compression operations."""

    def __init__(self, db_path: str = "audit/compression_audit.db", enable_chain: bool = True) -> None:
        self.db = AuditDatabase(db_path)
        self.enable_chain = enable_chain
        self.last_hash: Optional[str] = None
        self._load_last_hash()

    def _load_last_hash(self) -> None:
        records = self.db.query({}, limit=1)
        if records:
            self.last_hash = records[0].get("entry_hash")

    def _compute_hash(self, entry: AuditEntry) -> str:
        payload = (
            f"{entry.timestamp}|{entry.event_id}|{entry.event_type}|"
            f"{entry.original_size}|{entry.compressed_size}|{entry.data_hash}|"
            f"{entry.previous_hash}"
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def log_compression(
        self,
        event_type: CompressionEvent,
        method: str,
        original_size: int,
        compressed_size: int,
        latency_ms: float,
        data: Optional[bytes] = None,
        result: Optional[bytes] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        source_ip: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        timestamp = _iso_utc_now()
        event_id = hashlib.sha256(f"{timestamp}|{session_id}|{time.time()}".encode("utf-8")).hexdigest()[:16]

        data_hash = hashlib.sha256(data).hexdigest() if data else None
        result_hash = hashlib.sha256(result).hexdigest() if result else None

        if "failure" in event_type.value:
            level = AuditLevel.ERROR
        elif compressed_size > original_size:
            level = AuditLevel.WARNING
        else:
            level = AuditLevel.INFO

        ratio = original_size / compressed_size if compressed_size > 0 else 1.0
        metadata_payload = compact_metadata(metadata)

        entry = AuditEntry(
            timestamp=timestamp,
            event_id=event_id,
            level=level.name,
            event_type=event_type.value,
            user_id=user_id,
            session_id=session_id,
            source_ip=source_ip,
            method=method,
            original_size=original_size,
            compressed_size=compressed_size,
            compression_ratio=ratio,
            latency_ms=latency_ms,
            data_hash=data_hash,
            result_hash=result_hash,
            metadata=metadata_payload,
            previous_hash=self.last_hash,
            entry_hash=None,
        )
        entry.entry_hash = self._compute_hash(entry)
        self.db.insert(entry)
        if self.enable_chain:
            self.last_hash = entry.entry_hash
        return event_id

    def log_security_event(
        self,
        event_type: str,
        severity: AuditLevel,
        description: str,
        user_id: Optional[str] = None,
        source_ip: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        timestamp = _iso_utc_now()
        self.db.insert_security_event(
            timestamp=timestamp,
            event_type=event_type,
            severity=severity.name,
            user_id=user_id,
            source_ip=source_ip,
            description=description,
            metadata=metadata or {},
        )

    def verify_chain(self, start_id: int, end_id: int) -> Tuple[bool, List[str]]:
        if not self.enable_chain:
            return True, []

        query_sql = (
            """
            SELECT id, timestamp, event_id, event_type, original_size, compressed_size,
                   data_hash, previous_hash, entry_hash
            FROM audit_log
            WHERE id >= ? AND id <= ?
            ORDER BY id ASC
            """
        )

        errors: List[str] = []
        prev_hash: Optional[str] = None
        with self.db.lock:
            cursor = self.db.conn.cursor()
            cursor.execute(query_sql, (start_id, end_id))
            for row in cursor.fetchall():
                _, timestamp, event_id, event_type, original_size, compressed_size, data_hash, previous_hash, entry_hash = row
                if prev_hash is not None and previous_hash != prev_hash:
                    errors.append(f"Previous hash mismatch for event {event_id}")
                dummy_entry = AuditEntry(
                    timestamp=timestamp,
                    event_id=event_id,
                    level="",
                    event_type=event_type,
                    user_id=None,
                    session_id=None,
                    source_ip=None,
                    method=None,
                    original_size=original_size or 0,
                    compressed_size=compressed_size or 0,
                    compression_ratio=1.0,
                    latency_ms=0.0,
                    data_hash=data_hash,
                    result_hash=None,
                    metadata={},
                    previous_hash=previous_hash,
                    entry_hash=entry_hash,
                )
                if self._compute_hash(dummy_entry) != entry_hash:
                    errors.append(f"Hash mismatch for event {event_id}")
                prev_hash = entry_hash
        return len(errors) == 0, errors

    def aggregate_metrics(self, hours: int = 1) -> Dict[str, Any]:
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=hours)
        return self.db.aggregate_metrics(
            start_time.isoformat().replace("+00:00", "Z"),
            end_time.isoformat().replace("+00:00", "Z"),
        )

    def query(self, filters: Dict[str, Any], limit: int = 100) -> List[Dict[str, Any]]:
        return self.db.query(filters, limit)

    def close(self) -> None:
        self.db.close()


__all__ = [
    "AuditLevel",
    "CompressionEvent",
    "AuditEntry",
    "AuditDatabase",
    "CompressionAuditor",
    "compact_metadata",
    "expand_metadata",
    "register_metadata_aliases",
]
