"""High-level encoder for the Brio prototype with template awareness."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

from aura_compression.templates import TemplateLibrary, TemplateMatch

from . import dictionary
from .constants import MAX_MATCH, WINDOW_SIZE
from . import lz77
from . import rans
from .tokens import (
    DictionaryToken,
    LiteralToken,
    MatchToken,
    MetadataEntry,
    TemplateToken,
    Token,
)

_LITERAL_KIND = 0
_DICT_KIND = 1
_MATCH_KIND = 2
_TEMPLATE_KIND = 0x01

_DICT_TAG = 0x01
_MATCH_TAG = 0x02
_TEMPLATE_TAG = 0x03

SERVER_ONLY_FLAG = 0x80


@dataclass
class BrioCompressed:
    payload: bytes
    tokens: List[Token]
    metadata: List[MetadataEntry]


class BrioEncoder:
    def __init__(self, template_library: Optional[TemplateLibrary] = None):
        self.template_library = template_library

    def compress(
        self,
        text: str,
        template_match: Optional[TemplateMatch] = None,
    ) -> BrioCompressed:
        if template_match and self.template_library:
            tokens = [TemplateToken(template_match.template_id, list(template_match.slots))]
            slot_count = len(template_match.slots)
            metadata = [
                MetadataEntry(
                    token_index=0,
                    kind=_TEMPLATE_KIND,
                    value=template_match.template_id,
                    flags=min((slot_count or 1), 0x7F),
                )
            ]
        else:
            tokens, metadata = self._tokenise(text)

        plain_bytes = list(self._serialise_tokens(tokens))
        raw_freqs = rans.build_frequencies(plain_bytes)
        freqs = rans.normalise_frequencies(raw_freqs)
        cumfreq = rans.cumulative(freqs)
        rans_payload = rans.encode(plain_bytes, freqs, cumfreq)

        header = bytearray()
        header += b"AURA"
        header.append(1)
        header += len(plain_bytes).to_bytes(4, "big")
        header += len(rans_payload).to_bytes(4, "big")
        header += len(metadata).to_bytes(2, "big")

        for f in freqs:
            header += f.to_bytes(2, "big")

        for entry in metadata:
            header += entry.token_index.to_bytes(2, "big")
            header.append(entry.kind & 0xFF)
            header += entry.value.to_bytes(2, "big")
            header.append(entry.flags & 0xFF)

        payload = bytes(header) + rans_payload
        return BrioCompressed(payload=payload, tokens=tokens, metadata=metadata)

    # ------------------------------------------------------------------ internals

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
                metadata.append(
                    MetadataEntry(
                        len(tokens) - 1,
                        _DICT_KIND,
                        entry.token_id,
                        flags=SERVER_ONLY_FLAG,
                    )
                )
                window.extend(entry.phrase_bytes)
                if len(window) > WINDOW_SIZE:
                    del window[:-WINDOW_SIZE]
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
                metadata.append(
                    MetadataEntry(
                        len(output) - 1,
                        _LITERAL_KIND,
                        lz_token.value,
                        flags=SERVER_ONLY_FLAG,
                    )
                )
                window.append(lz_token.value)
                if len(window) > WINDOW_SIZE:
                    del window[:-WINDOW_SIZE]
            else:
                output.append(MatchToken(lz_token.distance, lz_token.length))
                metadata.append(
                    MetadataEntry(
                        len(output) - 1,
                        _MATCH_KIND,
                        min(lz_token.distance, 0xFFFF),
                        flags=SERVER_ONLY_FLAG,
                    )
                )
                start = len(window) - lz_token.distance
                match_bytes = [window[start + i] for i in range(lz_token.length)]
                window.extend(match_bytes)
                if len(window) > WINDOW_SIZE:
                    del window[:-WINDOW_SIZE]

    def _serialise_tokens(self, tokens: List[Token]) -> bytes:
        buf = bytearray()
        for token in tokens:
            if isinstance(token, LiteralToken):
                buf.append(0x00)
                buf.append(token.value & 0xFF)
            elif isinstance(token, DictionaryToken):
                buf.append(_DICT_TAG)
                buf.append(token.entry_id & 0xFF)
            elif isinstance(token, MatchToken):
                buf.append(_MATCH_TAG)
                buf += token.distance.to_bytes(2, "big")
                buf.append(token.length & 0xFF)
            elif isinstance(token, TemplateToken):
                buf.append(_TEMPLATE_TAG)
                buf.append(token.template_id & 0xFF)
                buf.append(len(token.slots) & 0xFF)
                for slot in token.slots:
                    slot_bytes = slot.encode("utf-8")
                    if len(slot_bytes) > 65535:
                        raise ValueError(
                            f"Template slot exceeds maximum length (65535 bytes): {len(slot_bytes)}"
                        )
                    buf.extend(len(slot_bytes).to_bytes(2, "big"))
                    buf.extend(slot_bytes)
            else:  # pragma: no cover
                raise ValueError(f"Unknown token: {token!r}")
        return bytes(buf)


__all__ = ["BrioEncoder", "BrioCompressed"]
