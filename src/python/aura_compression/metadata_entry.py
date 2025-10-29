#!/usr/bin/env python3
"""
AURA 6-Byte Metadata Entry Structure

Implements Claim 22: 6-byte metadata entry format for inline metadata encoding.

Metadata Entry Format (6 bytes):
[0] Kind (1 byte) - Template/LZ77/Semantic/Literal/Fallback
[1-5] Payload (5 bytes) - Kind-specific data

Copyright (c) 2025 Todd James Hendricks
Licensed under Apache License 2.0
Patent Pending - Application No. 19/366,538
"""

from typing import List, Optional, Tuple
from enum import IntEnum
from dataclasses import dataclass


class MetadataKind(IntEnum):
    """Metadata entry kind (Claim 22)"""
    TEMPLATE = 0  # Template substitution
    LZ77 = 1  # LZ77 backreference
    SEMANTIC = 2  # Semantic compression
    LITERAL = 3  # Literal data
    FALLBACK = 4  # Fallback indicator


@dataclass
class MetadataEntry:
    """
    6-byte metadata entry (Claim 22)

    Structure:
    - Byte 0: Kind (template/LZ77/semantic/literal/fallback)
    - Bytes 1-5: Kind-specific payload (5 bytes)

    Kind-Specific Payloads:
    - TEMPLATE: template_id (uint16) + reserved (3 bytes)
    - LZ77: offset (uint24) + length (uint16)
    - SEMANTIC: token_count (uint32) + reserved (1 byte)
    - LITERAL: payload_size (uint32) + reserved (1 byte)
    - FALLBACK: fallback_reason (uint32) + reserved (1 byte)
    """
    kind: MetadataKind

    # TEMPLATE payload
    template_id: Optional[int] = None  # uint16 (0-65535)

    # LZ77 payload
    lz77_offset: Optional[int] = None  # uint24 (0-16777215)
    lz77_length: Optional[int] = None  # uint16 (0-65535)

    # SEMANTIC payload
    token_count: Optional[int] = None  # uint32 (0-4294967295)

    # LITERAL payload
    payload_size: Optional[int] = None  # uint32 (0-4294967295)

    # FALLBACK payload
    fallback_reason: Optional[int] = None  # uint32 reason code

    def to_bytes(self) -> bytes:
        """
        Encode metadata entry to 6-byte format (Claim 22)

        Returns:
            6-byte metadata entry
        """
        entry = bytearray(6)

        # Byte 0: Kind
        entry[0] = self.kind

        # Bytes 1-5: Kind-specific payload
        if self.kind == MetadataKind.TEMPLATE:
            # Template ID (uint16, big-endian)
            if self.template_id is not None:
                entry[1:3] = self.template_id.to_bytes(2, 'big')
            # Bytes 3-5: Reserved (zeros)

        elif self.kind == MetadataKind.LZ77:
            # Offset (uint24, big-endian)
            if self.lz77_offset is not None:
                entry[1:4] = self.lz77_offset.to_bytes(3, 'big')
            # Length (uint16, big-endian)
            if self.lz77_length is not None:
                entry[4:6] = self.lz77_length.to_bytes(2, 'big')

        elif self.kind == MetadataKind.SEMANTIC:
            # Token count (uint32, big-endian)
            if self.token_count is not None:
                entry[1:5] = self.token_count.to_bytes(4, 'big')
            # Byte 5: Reserved

        elif self.kind == MetadataKind.LITERAL:
            # Payload size (uint32, big-endian)
            if self.payload_size is not None:
                entry[1:5] = self.payload_size.to_bytes(4, 'big')
            # Byte 5: Reserved

        elif self.kind == MetadataKind.FALLBACK:
            # Fallback reason code (uint32, big-endian)
            if self.fallback_reason is not None:
                entry[1:5] = self.fallback_reason.to_bytes(4, 'big')
            # Byte 5: Reserved

        return bytes(entry)

    @staticmethod
    def from_bytes(data: bytes) -> 'MetadataEntry':
        """
        Decode 6-byte metadata entry (Claim 22)

        Args:
            data: 6-byte metadata entry

        Returns:
            MetadataEntry object
        """
        if len(data) != 6:
            raise ValueError(f"Metadata entry must be 6 bytes, got {len(data)}")

        # Byte 0: Kind
        kind = MetadataKind(data[0])

        # Parse kind-specific payload
        if kind == MetadataKind.TEMPLATE:
            template_id = int.from_bytes(data[1:3], 'big')
            return MetadataEntry(
                kind=kind,
                template_id=template_id
            )

        elif kind == MetadataKind.LZ77:
            offset = int.from_bytes(data[1:4], 'big')
            length = int.from_bytes(data[4:6], 'big')
            return MetadataEntry(
                kind=kind,
                lz77_offset=offset,
                lz77_length=length
            )

        elif kind == MetadataKind.SEMANTIC:
            token_count = int.from_bytes(data[1:5], 'big')
            return MetadataEntry(
                kind=kind,
                token_count=token_count
            )

        elif kind == MetadataKind.LITERAL:
            payload_size = int.from_bytes(data[1:5], 'big')
            return MetadataEntry(
                kind=kind,
                payload_size=payload_size
            )

        elif kind == MetadataKind.FALLBACK:
            fallback_reason = int.from_bytes(data[1:5], 'big')
            return MetadataEntry(
                kind=kind,
                fallback_reason=fallback_reason
            )

        else:
            raise ValueError(f"Unknown metadata kind: {kind}")


class MetadataStream:
    """
    Stream of 6-byte metadata entries (Claim 22)

    Manages encoding/decoding of multiple metadata entries.
    """

    def __init__(self):
        self.entries: List[MetadataEntry] = []

    def add_entry(self, entry: MetadataEntry):
        """Add metadata entry to stream"""
        self.entries.append(entry)

    def add_template(self, template_id: int):
        """Add template metadata entry"""
        entry = MetadataEntry(
            kind=MetadataKind.TEMPLATE,
            template_id=template_id
        )
        self.add_entry(entry)

    def add_lz77(self, offset: int, length: int):
        """Add LZ77 backreference metadata entry"""
        entry = MetadataEntry(
            kind=MetadataKind.LZ77,
            lz77_offset=offset,
            lz77_length=length
        )
        self.add_entry(entry)

    def add_semantic(self, token_count: int):
        """Add semantic compression metadata entry"""
        entry = MetadataEntry(
            kind=MetadataKind.SEMANTIC,
            token_count=token_count
        )
        self.add_entry(entry)

    def add_literal(self, payload_size: int):
        """Add literal data metadata entry"""
        entry = MetadataEntry(
            kind=MetadataKind.LITERAL,
            payload_size=payload_size
        )
        self.add_entry(entry)

    def add_fallback(self, reason_code: int):
        """Add fallback indicator metadata entry"""
        entry = MetadataEntry(
            kind=MetadataKind.FALLBACK,
            fallback_reason=reason_code
        )
        self.add_entry(entry)

    def to_bytes(self) -> bytes:
        """
        Encode all metadata entries to bytes

        Format:
        [entry_count:2][entry1:6][entry2:6]...[entryN:6]

        Returns:
            Encoded metadata stream
        """
        # Entry count (2 bytes, big-endian)
        count = len(self.entries)
        data = bytearray(count.to_bytes(2, 'big'))

        # Encode each entry (6 bytes each)
        for entry in self.entries:
            data.extend(entry.to_bytes())

        return bytes(data)

    @staticmethod
    def from_bytes(data: bytes) -> 'MetadataStream':
        """
        Decode metadata stream from bytes

        Args:
            data: Encoded metadata stream

        Returns:
            MetadataStream object
        """
        if len(data) < 2:
            raise ValueError("Metadata stream too short")

        # Parse entry count
        count = int.from_bytes(data[0:2], 'big')

        # Validate size
        expected_size = 2 + (count * 6)
        if len(data) != expected_size:
            raise ValueError(f"Expected {expected_size} bytes for {count} entries, got {len(data)}")

        # Parse entries
        stream = MetadataStream()
        offset = 2

        for i in range(count):
            entry_data = data[offset:offset + 6]
            entry = MetadataEntry.from_bytes(entry_data)
            stream.add_entry(entry)
            offset += 6

        return stream

    def get_entry_count(self) -> int:
        """Get number of metadata entries"""
        return len(self.entries)

    def get_template_ids(self) -> List[int]:
        """Get all template IDs from metadata"""
        template_ids = []
        for entry in self.entries:
            if entry.kind == MetadataKind.TEMPLATE and entry.template_id is not None:
                template_ids.append(entry.template_id)
        return template_ids

    def get_lz77_references(self) -> List[Tuple[int, int]]:
        """Get all LZ77 backreferences (offset, length)"""
        refs = []
        for entry in self.entries:
            if entry.kind == MetadataKind.LZ77:
                if entry.lz77_offset is not None and entry.lz77_length is not None:
                    refs.append((entry.lz77_offset, entry.lz77_length))
        return refs

    def has_fallback(self) -> bool:
        """Check if metadata contains fallback indicator"""
        for entry in self.entries:
            if entry.kind == MetadataKind.FALLBACK:
                return True
        return False

    def get_total_size_bytes(self) -> int:
        """Get total size of metadata stream in bytes"""
        return 2 + (len(self.entries) * 6)
