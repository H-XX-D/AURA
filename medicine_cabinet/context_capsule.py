#!/usr/bin/env python3
"""Context capsule (``.auractx``) utilities.

Capsules capture the current working state for a project. They are intended
to stay local, complementing the portable ``.auratab`` tablets that preserve
long-term memories.

Binary layout (big-endian):

```
+-----------+----------------------+-----------------------------------------+
| Offset    | Field                | Description                             |
+===========+======================+=========================================+
| 0         | magic (8 bytes)      | ASCII ``AURACTX1`` identifier           |
| 8         | version (uint16)     | Format version (``1``)                  |
| 10        | created_at (uint64)  | Epoch milliseconds (UTC)                |
| 18        | metadata (len+blob)  | ``uint32`` + UTF-8 JSON metadata        |
| 22+       | section_count        | ``uint32``                              |
| ...       | sections             | Repeated blocks, see below              |
+-----------+----------------------+-----------------------------------------+
```

Each section is encoded as: name (length-prefixed UTF-8), kind (uint8), and
payload (length-prefixed bytes). ``kind`` maps to :class:`SectionKind`.
"""

from __future__ import annotations

import json
import struct
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import IntEnum
from pathlib import Path
from typing import Any, Dict, Iterator, List, Sequence

__all__ = [
	"CAPSULE_MAGIC",
	"CAPSULE_VERSION",
	"SectionKind",
	"CapsuleSection",
	"CapsuleMetadata",
	"ContextCapsule",
	"load_capsule",
	"save_capsule",
]

CAPSULE_MAGIC = b"AURACTX1"
CAPSULE_VERSION = 1


def _ensure_timezone(dt: datetime) -> datetime:
	if dt.tzinfo is None:
		return dt.replace(tzinfo=timezone.utc)
	return dt.astimezone(timezone.utc)


def _encode_string(value: str) -> bytes:
	data = value.encode("utf-8")
	if len(data) > 0xFFFFFFFF:
		raise ValueError("String exceeds 4 GiB limit")
	return struct.pack(">I", len(data)) + data


def _decode_string(payload: memoryview, cursor: int) -> tuple[str, int]:
	if cursor + 4 > len(payload):
		raise ValueError("Unexpected EOF while reading string length")
	(length,) = struct.unpack_from(">I", payload, cursor)
	cursor += 4
	end = cursor + length
	if end > len(payload):
		raise ValueError("Unexpected EOF while reading string payload")
	return bytes(payload[cursor:end]).decode("utf-8"), end


class SectionKind(IntEnum):
	TEXT = 1
	JSON = 2
	BINARY = 3


@dataclass(slots=True)
class CapsuleSection:
	name: str
	kind: SectionKind
	payload: bytes

	@classmethod
	def text(cls, name: str, content: str) -> "CapsuleSection":
		return cls(name=name, kind=SectionKind.TEXT, payload=content.encode("utf-8"))

	@classmethod
	def json(cls, name: str, data: Any) -> "CapsuleSection":
		blob = json.dumps(data, ensure_ascii=False, sort_keys=True).encode("utf-8")
		return cls(name=name, kind=SectionKind.JSON, payload=blob)

	@classmethod
	def binary(cls, name: str, data: bytes) -> "CapsuleSection":
		return cls(name=name, kind=SectionKind.BINARY, payload=bytes(data))

	def as_text(self) -> str:
		return self.payload.decode("utf-8")

	def as_json(self) -> Any:
		return json.loads(self.as_text())


@dataclass(slots=True)
class CapsuleMetadata:
	project: str
	summary: str
	author: str | None = None
	created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
	branch: str | None = None
	revision: str | None = None
	extra: Dict[str, Any] = field(default_factory=dict)

	def to_dict(self) -> Dict[str, Any]:
		return {
			"project": self.project,
			"summary": self.summary,
			"author": self.author,
			"created_at": _ensure_timezone(self.created_at).isoformat(),
			"branch": self.branch,
			"revision": self.revision,
			"extra": self.extra,
		}

	@classmethod
	def from_dict(cls, data: Dict[str, Any]) -> "CapsuleMetadata":
		created_raw = data.get("created_at")
		if created_raw:
			created_at = _ensure_timezone(datetime.fromisoformat(created_raw))
		else:
			created_at = datetime.now(timezone.utc)
		return cls(
			project=data.get("project", "Unnamed Project"),
			summary=data.get("summary", ""),
			author=data.get("author"),
			created_at=created_at,
			branch=data.get("branch"),
			revision=data.get("revision"),
			extra=dict(data.get("extra", {})),
		)


@dataclass(slots=True)
class ContextCapsule:
	metadata: CapsuleMetadata
	sections: List[CapsuleSection] = field(default_factory=list)

	def to_bytes(self) -> bytes:
		created_ms = int(_ensure_timezone(self.metadata.created_at).timestamp() * 1000)
		metadata_blob = json.dumps(self.metadata.to_dict(), ensure_ascii=False, sort_keys=True)

		buffer = bytearray()
		buffer.extend(CAPSULE_MAGIC)
		buffer.extend(struct.pack(">H", CAPSULE_VERSION))
		buffer.extend(struct.pack(">Q", created_ms))
		buffer.extend(_encode_string(metadata_blob))
		buffer.extend(struct.pack(">I", len(self.sections)))

		for section in self.sections:
			buffer.extend(_encode_string(section.name))
			buffer.append(section.kind.value)
			if len(section.payload) > 0xFFFFFFFF:
				raise ValueError("Section payload exceeds 4 GiB limit")
			buffer.extend(struct.pack(">I", len(section.payload)))
			buffer.extend(section.payload)

		return bytes(buffer)

	def write(self, path: Path | str) -> Path:
		path = Path(path)
		path.write_bytes(self.to_bytes())
		return path

	def add_section(self, section: CapsuleSection) -> None:
		self.sections.append(section)

	def iter_sections(self) -> Iterator[CapsuleSection]:
		return iter(self.sections)

	def to_dict(self) -> Dict[str, Any]:
		return {
			"metadata": self.metadata.to_dict(),
			"sections": [
				{
					"name": section.name,
					"kind": section.kind.name,
					"payload": section.payload.hex() if section.kind is SectionKind.BINARY else section.as_text(),
				}
				for section in self.sections
			],
		}

	# --- Semantic Helpers for AI Context ---

	def get_section(self, name: str) -> CapsuleSection | None:
		"""Finds a section by name, returning the first match."""
		for section in self.sections:
			if section.name == name:
				return section
		return None

	def set_section(self, section: CapsuleSection, overwrite: bool = True):
		"""Adds or updates a section.

		If a section with the same name already exists and overwrite is True,
		it is replaced. Otherwise, a new section is appended.
		"""
		if overwrite:
			# Filter out existing sections with the same name
			self.sections = [s for s in self.sections if s.name != section.name]
		self.sections.append(section)

	def set_task_objective(self, objective: str):
		"""Sets the AI's current task objective."""
		self.set_section(CapsuleSection.text("task_objective", objective))

	def get_task_objective(self) -> str | None:
		"""Gets the AI's current task objective."""
		section = self.get_section("task_objective")
		return section.as_text() if section else None

	def set_relevant_files(self, files: List[str]):
		"""Sets the list of files relevant to the current task."""
		self.set_section(CapsuleSection.json("relevant_files", files))

	def get_relevant_files(self) -> List[str] | None:
		"""Gets the list of relevant files."""
		section = self.get_section("relevant_files")
		return section.as_json() if section else None

	def set_working_plan(self, plan: Any):
		"""Sets the AI's working plan (e.g., a list of steps)."""
		self.set_section(CapsuleSection.json("working_plan", plan))

	def get_working_plan(self) -> Any | None:
		"""Gets the AI's working plan."""
		section = self.get_section("working_plan")
		return section.as_json() if section else None

	def set_error_state(self, error_output: str):
		"""Records the last known error state."""
		self.set_section(CapsuleSection.text("error_state", error_output))

	def get_error_state(self) -> str | None:
		"""Gets the last known error state."""
		section = self.get_section("error_state")
		return section.as_text() if section else None

	def set_symbols_of_interest(self, symbols: List[str]):
		"""Sets a list of code symbols (functions, classes) of interest."""
		self.set_section(CapsuleSection.json("code_symbols_of_interest", symbols))

	def get_symbols_of_interest(self) -> List[str] | None:
		"""Gets the list of code symbols of interest."""
		section = self.get_section("code_symbols_of_interest")
		return section.as_json() if section else None

	# --- End Semantic Helpers ---


	@classmethod
	def from_bytes(cls, payload: bytes) -> "ContextCapsule":
		buffer = memoryview(payload)
		cursor = 0

		if len(buffer) < len(CAPSULE_MAGIC):
			raise ValueError("Payload too small to be a capsule")
		magic = bytes(buffer[:len(CAPSULE_MAGIC)])
		cursor += len(CAPSULE_MAGIC)
		if magic != CAPSULE_MAGIC:
			raise ValueError("Invalid capsule magic header")

		if cursor + 2 > len(buffer):
			raise ValueError("Capsule missing version field")
		(version,) = struct.unpack_from(">H", buffer, cursor)
		cursor += 2
		if version != CAPSULE_VERSION:
			raise ValueError(f"Unsupported capsule version {version}")

		if cursor + 8 > len(buffer):
			raise ValueError("Capsule missing creation timestamp")
		(created_ms,) = struct.unpack_from(">Q", buffer, cursor)
		cursor += 8
		created_at = datetime.fromtimestamp(created_ms / 1000, tz=timezone.utc)

		metadata_json, cursor = _decode_string(buffer, cursor)
		metadata = CapsuleMetadata.from_dict(json.loads(metadata_json))
		metadata.created_at = created_at

		if cursor + 4 > len(buffer):
			raise ValueError("Capsule missing section count")
		(section_count,) = struct.unpack_from(">I", buffer, cursor)
		cursor += 4

		sections: List[CapsuleSection] = []
		for _ in range(section_count):
			name, cursor = _decode_string(buffer, cursor)
			if cursor >= len(buffer):
				raise ValueError("Capsule truncated before section kind")
			kind_value = buffer[cursor]
			cursor += 1
			try:
				kind = SectionKind(kind_value)
			except ValueError as exc:
				raise ValueError(f"Unknown section kind {kind_value}") from exc

			if cursor + 4 > len(buffer):
				raise ValueError("Capsule truncated before payload length")
			(length,) = struct.unpack_from(">I", buffer, cursor)
			cursor += 4
			end = cursor + length
			if end > len(buffer):
				raise ValueError("Capsule truncated during payload read")
			payload_bytes = bytes(buffer[cursor:end])
			cursor = end

			sections.append(CapsuleSection(name=name, kind=kind, payload=payload_bytes))

		return cls(metadata=metadata, sections=sections)

	@classmethod
	def read(cls, path: Path | str) -> "ContextCapsule":
		return cls.from_bytes(Path(path).read_bytes())


def load_capsule(path: Path | str) -> ContextCapsule:
	return ContextCapsule.read(path)


def save_capsule(path: Path | str, metadata: CapsuleMetadata, sections: Sequence[CapsuleSection]) -> Path:
	capsule = ContextCapsule(metadata=metadata, sections=list(sections))
	return capsule.write(path)
