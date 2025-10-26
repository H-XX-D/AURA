#!/usr/bin/env python3
"""Utilities for working with AURA Tablet (``.auratab``) archives.

An AURA Tablet is a binary artifact that captures the memory of a completed
feature, bug fix, or investigation. Tablets are meant to complement the
``.auractx`` capsule format by preserving historical context that can be
shared across projects, branches, or even different AI assistants.

The binary layout (big-endian) is intentionally simple:

```
+-----------+----------------------+--------------------------------------------------+
| Offset    | Field                | Description                                      |
+===========+======================+==================================================+
| 0         | magic (8 bytes)      | ASCII ``AURATAB1`` identifier                    |
| 8         | version (uint16)     | Format version (currently ``1``)                 |
| 10        | created_at (uint64)  | Epoch milliseconds (UTC)                         |
| 18        | metadata (len+blob)  | ``uint32`` length + UTF-8 JSON payload           |
| 22+       | entry_count (uint32) | Number of tablet entries that follow             |
| ...       | entries              | Repeated blocks, one per entry                   |
+-----------+----------------------+--------------------------------------------------+

Each entry block is encoded as three length-prefixed UTF-8 strings:

```
+-----------+----------------------+--------------------------------------------------+
| Field     | Type                 | Contents                                         |
+===========+======================+==================================================+
| path      | uint32 + bytes       | Repository-relative file path                    |
| diff      | uint32 + bytes       | Unified diff, patch, or serialized content       |
| notes     | uint32 + bytes       | Optional commentary or learnings                 |
+-----------+----------------------+--------------------------------------------------+
```

All numeric fields are encoded using big-endian byte order to ease inspection
with common hex editors. Strings are stored as UTF-8; zero-length strings are
allowed. The metadata JSON mirrors :class:`TabletMetadata.to_dict`.
"""

from __future__ import annotations

import json
import struct
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Sequence

__all__ = [
    "TABLET_MAGIC",
    "TABLET_VERSION",
    "TabletEntry",
    "TabletMetadata",
    "Tablet",
    "load_tablet",
    "save_tablet",
]

TABLET_MAGIC = b"AURATAB1"
TABLET_VERSION = 1


def _ensure_timezone(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _encode_string(value: str) -> bytes:
    data = value.encode("utf-8")
    length = len(data)
    if length > 0xFFFFFFFF:
        raise ValueError("String payload exceeds 4 GiB limit")
    return struct.pack(">I", length) + data


def _decode_string(buffer: memoryview, cursor: int) -> tuple[str, int]:
    if cursor + 4 > len(buffer):
        raise ValueError("Unexpected EOF while reading string length")
    (length,) = struct.unpack_from(">I", buffer, cursor)
    cursor += 4
    end = cursor + length
    if end > len(buffer):
        raise ValueError("Unexpected EOF while reading string payload")
    data = bytes(buffer[cursor:end]).decode("utf-8")
    return data, end


@dataclass(slots=True)
class TabletEntry:
    """Represents a single file contribution captured by the tablet."""

    path: str
    diff: str
    notes: str = ""

    def to_dict(self) -> Dict[str, str]:
        return {"path": self.path, "diff": self.diff, "notes": self.notes}

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "TabletEntry":
        return cls(
            path=payload["path"],
            diff=payload.get("diff", ""),
            notes=payload.get("notes", ""),
        )


@dataclass(slots=True)
class TabletMetadata:
    """Descriptive metadata stored alongside the tablet entries."""

    title: str
    summary: str
    author: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    tags: List[str] = field(default_factory=list)
    revision: str | None = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "summary": self.summary,
            "author": self.author,
            "created_at": _ensure_timezone(self.created_at).isoformat(),
            "tags": list(self.tags),
            "revision": self.revision,
            "extra": self.extra,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "TabletMetadata":
        created_raw = payload.get("created_at")
        if created_raw:
            created_at = datetime.fromisoformat(created_raw)
            created_at = _ensure_timezone(created_at)
        else:
            created_at = datetime.now(timezone.utc)
        return cls(
            title=payload.get("title", "Untitled Tablet"),
            summary=payload.get("summary", ""),
            author=payload.get("author"),
            created_at=created_at,
            tags=list(payload.get("tags", [])),
            revision=payload.get("revision"),
            extra=dict(payload.get("extra", {})),
        )


@dataclass(slots=True)
class Tablet:
    """In-memory representation of an AURA Tablet."""

    metadata: TabletMetadata
    entries: List[TabletEntry] = field(default_factory=list)

    def to_bytes(self) -> bytes:
        created_at = int(_ensure_timezone(self.metadata.created_at).timestamp() * 1000)
        metadata_blob = json.dumps(self.metadata.to_dict(), ensure_ascii=False, sort_keys=True)

        buffer = bytearray()
        buffer.extend(TABLET_MAGIC)
        buffer.extend(struct.pack(">H", TABLET_VERSION))
        buffer.extend(struct.pack(">Q", created_at))
        buffer.extend(_encode_string(metadata_blob))
        buffer.extend(struct.pack(">I", len(self.entries)))

        for entry in self.entries:
            buffer.extend(_encode_string(entry.path))
            buffer.extend(_encode_string(entry.diff))
            buffer.extend(_encode_string(entry.notes))

        return bytes(buffer)

    def write(self, path: Path | str) -> Path:
        path = Path(path)
        path.write_bytes(self.to_bytes())
        return path

    @classmethod
    def from_bytes(cls, payload: bytes) -> "Tablet":
        buffer = memoryview(payload)
        cursor = 0

        if len(buffer) < len(TABLET_MAGIC):
            raise ValueError("Payload too small to be a valid tablet")
        magic = bytes(buffer[cursor:cursor + len(TABLET_MAGIC)])
        cursor += len(TABLET_MAGIC)
        if magic != TABLET_MAGIC:
            raise ValueError("Invalid tablet magic header")

        if cursor + 2 > len(buffer):
            raise ValueError("Corrupt tablet: missing version")
        (version,) = struct.unpack_from(">H", buffer, cursor)
        cursor += 2
        if version != TABLET_VERSION:
            raise ValueError(f"Unsupported tablet version {version}")

        if cursor + 8 > len(buffer):
            raise ValueError("Corrupt tablet: missing timestamp")
        (created_ms,) = struct.unpack_from(">Q", buffer, cursor)
        cursor += 8
        created_at = datetime.fromtimestamp(created_ms / 1000, tz=timezone.utc)

        metadata_json, cursor = _decode_string(buffer, cursor)
        metadata = TabletMetadata.from_dict(json.loads(metadata_json))
        metadata.created_at = created_at

        if cursor + 4 > len(buffer):
            raise ValueError("Corrupt tablet: missing entry count")
        (entry_count,) = struct.unpack_from(">I", buffer, cursor)
        cursor += 4

        entries: List[TabletEntry] = []
        for _ in range(entry_count):
            path, cursor = _decode_string(buffer, cursor)
            diff, cursor = _decode_string(buffer, cursor)
            notes, cursor = _decode_string(buffer, cursor)
            entries.append(TabletEntry(path=path, diff=diff, notes=notes))

        return cls(metadata=metadata, entries=entries)

    @classmethod
    def read(cls, path: Path | str) -> "Tablet":
        return cls.from_bytes(Path(path).read_bytes())

    def add_entry(self, *, path: str, diff: str, notes: str = "") -> None:
        self.entries.append(TabletEntry(path=path, diff=diff, notes=notes))

    def iter_entries(self) -> Iterator[TabletEntry]:
        return iter(self.entries)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metadata": self.metadata.to_dict(),
            "entries": [entry.to_dict() for entry in self.entries],
        }


def load_tablet(path: Path | str) -> Tablet:
    """Convenience wrapper around :meth:`Tablet.read`."""

    return Tablet.read(path)


def save_tablet(path: Path | str, metadata: TabletMetadata, entries: Sequence[TabletEntry]) -> Path:
    """Persist a tablet to disk from metadata and entries."""

    tablet = Tablet(metadata=metadata, entries=list(entries))
    return tablet.write(path)
