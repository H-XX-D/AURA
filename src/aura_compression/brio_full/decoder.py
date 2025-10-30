"""Decoder counterpart for the template-aware Brio prototype."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from aura_compression.templates import TemplateLibrary

from .constants import MAGIC, VERSION, WINDOW_SIZE
from .tokens import (
    DictionaryToken,
    LiteralToken,
    MatchToken,
    MetadataEntry,
    TemplateToken,
    Token,
)
from . import dictionary
from . import rans

_TEMPLATE_KIND = 0x01


@dataclass
class BrioDecompressed:
    text: str
    tokens: List[Token]
    metadata: List[MetadataEntry]


class BrioDecoder:
    def __init__(self, template_library: Optional[TemplateLibrary] = None):
        self.template_library = template_library

    def decompress(self, payload: bytes) -> BrioDecompressed:
        view = memoryview(payload)
        if view[:4].tobytes() != MAGIC:
            raise ValueError("Invalid Brio payload: missing magic")
        if view[4] != VERSION:
            raise ValueError("Unsupported Brio payload version")

        plain_token_len = int.from_bytes(view[5:9], "big")
        rans_payload_len = int.from_bytes(view[9:13], "big")
        metadata_count = int.from_bytes(view[13:15], "big")

        freq_start = 15
        freq_end = freq_start + 256 * 2
        freqs = [
            int.from_bytes(view[freq_start + i * 2 : freq_start + i * 2 + 2], "big")
            for i in range(256)
        ]

        metadata_start = freq_end
        metadata_end = metadata_start + metadata_count * 6
        metadata: List[MetadataEntry] = []
        meta_bytes = view[metadata_start:metadata_end].tobytes()
        for i in range(0, len(meta_bytes), 6):
            token_index = int.from_bytes(meta_bytes[i : i + 2], "big")
            kind = meta_bytes[i + 2]
            value = int.from_bytes(meta_bytes[i + 3 : i + 5], "big")
            flags = meta_bytes[i + 5]
            metadata.append(MetadataEntry(token_index, kind, value, flags))

        rans_start = metadata_end
        rans_end = rans_start + rans_payload_len
        rans_bitstream = view[rans_start:rans_end].tobytes()

        cumfreq = rans.cumulative(freqs)
        lookup = rans.build_symbol_lookup(freqs, cumfreq)
        payload_bytes = rans.decode(rans_bitstream, plain_token_len, freqs, cumfreq, lookup)

        tokens = self._deserialise_tokens(payload_bytes)
        text = self._reconstruct(tokens)
        return BrioDecompressed(text=text, tokens=tokens, metadata=metadata)

    # ------------------------------------------------------------------ internals

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
                if i >= size:
                    raise ValueError("Malformed template token")
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
            else:  # pragma: no cover
                raise ValueError(f"Unknown token tag: {tag:#x}")
        return tokens

    def _reconstruct(self, tokens: List[Token]) -> str:
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
                if not self.template_library:
                    raise ValueError("Template token encountered without a template library")
                rendered = self.template_library.format_template(token.template_id, token.slots)
                rendered_bytes = rendered.encode("utf-8")
                output.extend(rendered_bytes)
                window.extend(rendered_bytes)
                self.template_library.record_use(token.template_id)
            else:  # pragma: no cover
                raise ValueError(f"Unexpected token type: {token!r}")

            if len(window) > WINDOW_SIZE:
                del window[:-WINDOW_SIZE]

        return output.decode("utf-8")


__all__ = ["BrioDecoder", "BrioDecompressed"]
