"""Decoder counterpart for the Brio prototype."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from .constants import MAGIC, VERSION, WINDOW_SIZE
from .tokens import (
    DictionaryToken,
    LiteralToken,
    MatchToken,
    TemplateToken,
    MetadataEntry,
    Token,
)
from . import dictionary


@dataclass
class BrioDecompressed:
    text: str
    tokens: List[Token]
    metadata: List[MetadataEntry]


@dataclass
class BrioDecoder:
    def __init__(self, template_library=None):
        self.template_library = template_library
    def decompress(self, payload: bytes) -> BrioDecompressed:
        view = memoryview(payload)
        # Check for new "BR" magic (TCP-optimized)
        if view[:2].tobytes() == b"BR":
            if view[2] != VERSION:
                raise ValueError("Unsupported Brio payload version")

            # Variable-length decode payload_len
            offset = 3
            first_byte = view[offset]
            if first_byte < 0x80:
                # 1-byte length
                payload_len = first_byte
                offset += 1
            elif first_byte < 0xC0:
                # 2-byte length
                payload_len = ((first_byte & 0x3F) << 8) | view[offset + 1]
                offset += 2
            else:
                # 3-byte length
                payload_len = ((first_byte & 0x3F) << 16) | (view[offset + 1] << 8) | view[offset + 2]
                offset += 3

            # Variable-length decode metadata_count
            first_byte = view[offset]
            if first_byte < 0x80:
                # 1-byte count
                metadata_count = first_byte
                offset += 1
            else:
                # 2-byte count
                metadata_count = ((first_byte & 0x7F) << 8) | view[offset + 1]
                offset += 2

            metadata_start = offset
            metadata_end = metadata_start + metadata_count * 5
            payload_start = metadata_end
            payload_end = payload_start + payload_len
        elif view[:4].tobytes() == b"AURA":
            # Legacy format
            if view[4] != VERSION:
                raise ValueError("Unsupported Brio payload version")

            payload_len = int.from_bytes(view[5:9], "big")
            metadata_count = int.from_bytes(view[9:11], "big")

            metadata_start = 11
            metadata_end = metadata_start + metadata_count * 5
            payload_start = metadata_end
            payload_end = payload_start + payload_len
        else:
            raise ValueError("Invalid Brio payload: missing magic")

        metadata: List[MetadataEntry] = []
        meta_bytes = view[metadata_start:metadata_end].tobytes()
        for i in range(0, len(meta_bytes), 5):
            token_index = int.from_bytes(meta_bytes[i : i + 2], "big")
            kind = meta_bytes[i + 2]
            value = int.from_bytes(meta_bytes[i + 3 : i + 5], "big")
            metadata.append(MetadataEntry(token_index, kind, value))

        payload_slice = view[payload_start:payload_end].tobytes()
        payload_bytes = list(payload_slice)
        tokens = self._deserialise_tokens(payload_bytes)
        text = self._reconstruct(tokens).decode("utf-8")
        return BrioDecompressed(text=text, tokens=tokens, metadata=metadata)

    # -- helper utilities -----------------------------------------

    def _deserialise_tokens(self, payload: List[int]) -> List[Token]:
        tokens: List[Token] = []
        i = 0
        size = len(payload)
        while i < size:
            tag = payload[i]
            i += 1
            if tag == 0x00:
                tokens.append(LiteralToken(payload[i]))
                i += 1
            elif tag == 0x01:
                tokens.append(DictionaryToken(payload[i]))
                i += 1
            elif tag == 0x02:
                distance = (payload[i] << 8) | payload[i + 1]
                length = payload[i + 2]
                tokens.append(MatchToken(distance, length))
                i += 3
            elif tag == 0x03:
                # Template token (inline semantic binary)
                template_id = payload[i]
                i += 1
                slot_count = payload[i]
                i += 1
                slots: List[str] = []
                for _ in range(slot_count):
                    if i + 2 > size:
                        raise ValueError("Malformed template slot header")
                    slot_len = (payload[i] << 8) | payload[i + 1]
                    i += 2
                    if i + slot_len > size:
                        raise ValueError("Malformed template slot payload")
                    slot_bytes = bytes(payload[i : i + slot_len])
                    slots.append(slot_bytes.decode("utf-8"))
                    i += slot_len
                tokens.append(TemplateToken(template_id, slots))
            else:
                raise ValueError(f"Unknown token tag: {tag:#x}")
        return tokens

    def _reconstruct(self, tokens: List[Token]) -> bytearray:
        window = bytearray()
        output = bytearray()

        for token in tokens:
            if isinstance(token, LiteralToken):
                output.append(token.value)
                window.append(token.value)
            elif isinstance(token, DictionaryToken):
                entry = dictionary.by_id(token.entry_id)
                output.extend(entry.phrase_bytes)
                window.extend(entry.phrase_bytes)
            elif isinstance(token, MatchToken):
                start = len(window) - token.distance
                if start < 0:
                    raise ValueError("Invalid match token distance")
                match_bytes = [window[start + i] for i in range(token.length)]
                output.extend(match_bytes)
                window.extend(match_bytes)
            elif isinstance(token, TemplateToken):
                # Reconstruct template from semantic binary
                if not self.template_library:
                    raise ValueError("Template token encountered without a template library")
                rendered = self.template_library.format_template(token.template_id, token.slots)
                rendered_bytes = rendered.encode("utf-8")
                output.extend(rendered_bytes)
                window.extend(rendered_bytes)
            else:  # pragma: no cover
                raise ValueError(f"Unexpected token type: {token!r}")

            if len(window) > WINDOW_SIZE:
                del window[:-WINDOW_SIZE]

        return output


__all__ = ["BrioDecoder", "BrioDecompressed"]
