"""Aura-Lite decoder implementation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from aura_compression.brio_full.dictionary import by_id
from aura_compression.templates import TemplateLibrary


@dataclass
class AuraLiteDecoded:
    text: str
    template_ids: List[int]


class AuraLiteDecoder:
    TEMPLATE_KIND = 0x00
    DICTIONARY_KIND = 0x01
    LITERAL_KIND = 0x03

    def __init__(self, template_library: TemplateLibrary) -> None:
        self.template_library = template_library

    def decode(self, payload: bytes) -> AuraLiteDecoded:
        # Check for compact binary header (3 bytes: magic + version_flags + token_length)
        if len(payload) >= 3 and payload[0] == 0xAA:  # 170 decimal (AA hex)
            # Compact binary header format
            version_flags = payload[1]
            version = (version_flags >> 4) & 0x0F
            # flags = version_flags & 0x0F  # unused for now
            token_length = payload[2]
            tokens_bytes = payload[3:3 + token_length]
        elif len(payload) >= 11 and payload[:4] == b"AUL1":
            # Full header format (backward compatibility)
            token_len = int.from_bytes(payload[6:10], "big")
            # metadata_count = payload[10]  # intentionally ignored (sanitized)
            tokens_bytes = payload[11:11 + token_len]
        else:
            raise ValueError("Invalid AURA-Lite payload")

        pos = 0
        template_ids: List[int] = []
        parts: List[str] = []

        while pos < len(tokens_bytes):
            kind = tokens_bytes[pos]
            pos += 1

            if kind == self.TEMPLATE_KIND:
                template_id = tokens_bytes[pos]
                pos += 1
                slot_count = tokens_bytes[pos]
                pos += 1
                slots: List[str] = []
                for _ in range(slot_count):
                    slot_len = int.from_bytes(tokens_bytes[pos:pos + 2], "big")
                    pos += 2
                    slot_bytes = tokens_bytes[pos:pos + slot_len]
                    pos += slot_len
                    slots.append(slot_bytes.decode("utf-8"))
                template_ids.append(template_id)
                parts.append(self.template_library.format_template(template_id, slots))

            elif kind == self.DICTIONARY_KIND:
                entry_id = tokens_bytes[pos]
                pos += 1
                entry = by_id(entry_id)
                parts.append(entry.phrase)

            elif kind == self.LITERAL_KIND:
                length = tokens_bytes[pos]
                pos += 1
                chunk = tokens_bytes[pos:pos + length]
                pos += length
                parts.append(chunk.decode("utf-8"))

            else:
                raise ValueError(f"Unknown token kind: {kind:#02x}")

        text = "".join(parts)
        return AuraLiteDecoded(text=text, template_ids=template_ids)
