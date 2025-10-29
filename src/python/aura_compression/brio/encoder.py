"""High-level encoder for the Brio prototype."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from . import dictionary
from .constants import MAX_MATCH, WINDOW_SIZE
from . import lz77
from .tokens import (
    DictionaryToken,
    LiteralToken,
    MatchToken,
    TemplateToken,
    MetadataEntry,
    Token,
)

_LITERAL_KIND = 0
_DICT_KIND = 1
_MATCH_KIND = 2
_TEMPLATE_KIND = 0x01  # Template metadata kind

_TEMPLATE_TAG = 0x03  # Template token tag
_WINDOW_TRIM_SLACK = 1024


@dataclass
class BrioCompressed:
    payload: bytes
    tokens: List[Token]
    metadata: List[MetadataEntry]


@dataclass
class BrioEncoder:
    def compress(self, text: str) -> BrioCompressed:
        """Compress text by tokenizing it first"""
        tokens, metadata = self._tokenise(text)
        return self.compress_tokens(tokens, metadata)

    def compress_tokens(self, tokens: List[Token], metadata: List[MetadataEntry]) -> BrioCompressed:
        """Compress pre-tokenized input (allows inline semantic binaries)"""
        payload = self._serialise_tokens(tokens)

        header = bytearray()
        # Compact header: 2-byte magic + 1-byte version/flags + var-length payload_len + var-length metadata_count
        header += b"BR"  # 2-byte magic for "Brio"
        header.append(1)  # Version 1

        # Variable-length encode payload length (1-4 bytes)
        payload_len = len(payload)
        if payload_len < 128:
            header.append(payload_len)
        elif payload_len < 16384:
            header.append(0x80 | (payload_len >> 8))
            header.append(payload_len & 0xFF)
        else:
            header.append(0xC0 | (payload_len >> 16))
            header.append((payload_len >> 8) & 0xFF)
            header.append(payload_len & 0xFF)

        # Variable-length encode metadata count (1-2 bytes)
        metadata_count = len(metadata)
        if metadata_count < 128:
            header.append(metadata_count)
        else:
            header.append(0x80 | (metadata_count >> 8))
            header.append(metadata_count & 0xFF)

        for entry in metadata:
            header += entry.token_index.to_bytes(2, "big")
            header.append(entry.kind & 0xFF)
            header += entry.value.to_bytes(2, "big")

        wire = bytes(header) + payload
        return BrioCompressed(wire, tokens, metadata)

    # -- internals -------------------------------------------------

    def _tokenise(self, text: str) -> Tuple[List[Token], List[MetadataEntry]]:
        data = text.encode("utf-8")
        tokens: List[Token] = []
        metadata: List[MetadataEntry] = []
        window = bytearray()
        pos = 0
        size = len(data)

        while pos < size:
            entry = dictionary.longest_prefix_match_bytes(data, pos)
            if entry and len(entry.phrase_bytes) >= MAX_MATCH:
                entry = None

            if entry and len(entry.phrase_bytes) >= 6:
                tokens.append(DictionaryToken(entry.token_id))
                metadata.append(MetadataEntry(len(tokens) - 1, _DICT_KIND, entry.token_id))
                window.extend(entry.phrase_bytes)
                if len(window) > WINDOW_SIZE + _WINDOW_TRIM_SLACK:
                    del window[: len(window) - WINDOW_SIZE]
                pos += len(entry.phrase_bytes)
                continue

            chunk_start = pos
            pos += 1
            while pos < size:
                if dictionary.longest_prefix_match_bytes(data, pos) is not None:
                    break
                if pos - chunk_start >= 64:
                    break
                pos += 1

            chunk = data[chunk_start:pos]
            lz_tokens = lz77.tokenize(chunk, window)
            self._extend_with_lz_tokens(tokens, metadata, lz_tokens, window)

        return tokens, metadata

    def _extend_with_lz_tokens(
        self,
        output: List[Token],
        metadata: List[MetadataEntry],
        lz_tokens: List[lz77.Token],
        window: bytearray,
    ) -> None:
        for lz_token in lz_tokens:
            if isinstance(lz_token, lz77.LZLiteral):
                output.append(LiteralToken(lz_token.value))
                metadata.append(MetadataEntry(len(output) - 1, _LITERAL_KIND, lz_token.value))
                window.append(lz_token.value)
                if len(window) > WINDOW_SIZE + _WINDOW_TRIM_SLACK:
                    del window[: len(window) - WINDOW_SIZE]
            else:
                output.append(MatchToken(lz_token.distance, lz_token.length))
                metadata.append(
                    MetadataEntry(len(output) - 1, _MATCH_KIND, min(lz_token.distance, 0xFFFF))
                )
                start = len(window) - lz_token.distance
                match_bytes = [window[start + i] for i in range(lz_token.length)]
                window.extend(match_bytes)
                if len(window) > WINDOW_SIZE + _WINDOW_TRIM_SLACK:
                    del window[: len(window) - WINDOW_SIZE]

    def _serialise_tokens(self, tokens: List[Token]) -> bytes:
        buf = bytearray()
        for token in tokens:
            if isinstance(token, LiteralToken):
                buf.append(0x00)
                buf.append(token.value & 0xFF)
            elif isinstance(token, DictionaryToken):
                buf.append(0x01)
                buf.append(token.entry_id & 0xFF)
            elif isinstance(token, MatchToken):
                buf.append(0x02)
                buf += token.distance.to_bytes(2, "big")
                buf.append(token.length & 0xFF)
            elif isinstance(token, TemplateToken):
                # Inline semantic binary format
                buf.append(_TEMPLATE_TAG)  # 0x03
                buf.append(token.template_id & 0xFF)
                buf.append(len(token.slots) & 0xFF)
                for slot in token.slots:
                    slot_bytes = slot.encode("utf-8")
                    if len(slot_bytes) > 65535:
                        raise ValueError(f"Template slot exceeds maximum length: {len(slot_bytes)}")
                    buf.extend(len(slot_bytes).to_bytes(2, "big"))
                    buf.extend(slot_bytes)
            else:  # pragma: no cover
                raise ValueError(f"Unknown token: {token!r}")
        return bytes(buf)


__all__ = ["BrioEncoder", "BrioCompressed"]
