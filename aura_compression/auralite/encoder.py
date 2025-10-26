"""Aura-Lite encoder implementation."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import List, Optional, cast, Dict

from aura_compression.brio_full.dictionary import DICTIONARY
from aura_compression.templates import TemplateMatch, TemplateLibrary


@dataclass
class AuraLiteEncoded:
    payload: bytes
    template_ids: List[int]


class AuraLiteEncoder:
    """Lightweight encoder using template tokens + dictionary + literal runs."""

    TEMPLATE_KIND = 0x00
    DICTIONARY_KIND = 0x01
    LITERAL_KIND = 0x03

    def __init__(self, template_library: Optional[TemplateLibrary] = None, use_compact_header: bool = True, enable_fast_path: bool = True) -> None:
        # Filter dictionary to only entries with ID <= 255 (fits in 1 byte)
        # The current format uses 1 byte for dictionary token IDs, so IDs > 255 cannot be encoded
        filtered_dict = [entry for entry in DICTIONARY if entry.token_id <= 255]
        self._dictionary_entries = sorted(filtered_dict, key=lambda entry: len(entry.phrase), reverse=True)
        self._id_to_entry = {entry.token_id: entry for entry in filtered_dict}
        self._template_library = template_library or TemplateLibrary()
        self._use_compact_header = use_compact_header
        self._enable_fast_path = enable_fast_path

        # Fast path cache for AURA-Lite compression
        self._cache_enabled = enable_fast_path
        self._cache_hits = 0
        self._cache_misses = 0

    @lru_cache(maxsize=1024)
    def _cached_encode(self, text: str) -> AuraLiteEncoded:
        """Cached encoding for fast path (text-only, no template hints)"""
        token_bytes, template_ids = self._tokenise(text)

        if self._use_compact_header and len(token_bytes) <= 255:
            header = bytearray()
            header.append(0xAA)  # Binary magic byte
            header.append(0x10)  # version 1, flags 0
            header.append(len(token_bytes) & 0xFF)
            payload = bytes(header + token_bytes)
            return AuraLiteEncoded(payload=payload, template_ids=template_ids)

        # Full header fallback
        header = bytearray()
        header += b"AUL1"
        header.append(1)  # version
        header.append(0)  # flags
        header += len(token_bytes).to_bytes(4, "big")
        header.append(0)  # metadata count
        payload = bytes(header + token_bytes)
        return AuraLiteEncoded(payload=payload, template_ids=template_ids)

    def encode(
        self,
        text: str,
        template_match: Optional[TemplateMatch] = None,
        template_spans: Optional[List[TemplateMatch]] = None,
    ) -> AuraLiteEncoded:
        # FAST PATH: Use cache for simple text-only encoding
        if self._enable_fast_path and template_match is None and (template_spans is None or len(template_spans) == 0):
            try:
                result = self._cached_encode(text)
                self._cache_hits += 1
                return result
            except TypeError:
                # Unhashable type, fall through to normal path
                self._cache_misses += 1
        else:
            self._cache_misses += 1

        # Normal path
        if template_match:
            token_bytes = self._encode_template(template_match)
            template_ids = [template_match.template_id]
        else:
            span_list = [
                match for match in (template_spans or [])
                if match.start is not None and match.end is not None
            ]
            span_list.sort(key=lambda m: cast(int, m.start))
            token_bytes, template_ids = self._encode_with_spans(text, span_list)

        if self._use_compact_header:
            # Compact binary header (3 bytes total):
            # - 1 byte: magic 0xAL (170 decimal) for AURA-Lite compact
            # - 1 byte: version (4 bits) + flags (4 bits)
            # - 1 byte: token length (0-255, for larger use full header)
            # This saves 8 bytes vs full header (11 bytes)

            if len(token_bytes) <= 255:
                header = bytearray()
                header.append(0xAA)  # Binary magic byte (170 decimal, AA hex)
                header.append(0x10)  # version 1, flags 0
                header.append(len(token_bytes) & 0xFF)
                payload = bytes(header + token_bytes)
                return AuraLiteEncoded(payload=payload, template_ids=template_ids)

        # Fall back to full header if compact doesn't fit or disabled
        header = bytearray()
        header += b"AUL1"
        header.append(1)  # version
        header.append(0)  # flags
        header += len(token_bytes).to_bytes(4, "big")
        header.append(0)  # metadata count (server retains audit data only)

        payload = bytes(header + token_bytes)
        return AuraLiteEncoded(payload=payload, template_ids=template_ids)

    # ------------------------------------------------------------------ internals

    def _encode_template(self, match: TemplateMatch) -> bytearray:
        slots = list(match.slots)
        token = bytearray()
        token.append(self.TEMPLATE_KIND)
        token.append(match.template_id & 0xFF)
        token.append(len(slots) & 0xFF)
        for slot in slots:
            slot_bytes = slot.encode("utf-8")
            token += len(slot_bytes).to_bytes(2, "big")
            token += slot_bytes
        return token

    def _encode_with_spans(self, text: str, spans: List[TemplateMatch]) -> tuple[bytearray, List[int]]:
        if not spans:
            return self._tokenise(text)

        token_bytes = bytearray()
        template_ids: List[int] = []
        cursor = 0

        for match in spans:
            if match.start is None or match.end is None:
                continue
            start = cast(int, match.start)
            end = cast(int, match.end)
            if start < cursor:
                continue

            # Encode text before this template
            if start > cursor:
                prefix_tokens, _ = self._tokenise(text[cursor:start])
                token_bytes.extend(prefix_tokens)

            # Reconstruct the template to find actual template length
            reconstructed = self._template_library.format_template(match.template_id, match.slots)
            template_len = len(reconstructed)

            # Encode the template itself
            token_bytes.extend(self._encode_template(match))
            template_ids.append(match.template_id)

            # Move cursor to just after the reconstructed template text
            # (not to end of span, which may include extra whitespace captured by regex)
            cursor = start + template_len

            # If there's trailing whitespace between reconstructed template end and span end,
            # encode it as literals
            if cursor < end:
                trailing_ws = text[cursor:end]
                ws_tokens, _ = self._tokenise(trailing_ws)
                token_bytes.extend(ws_tokens)
                cursor = end

        if cursor < len(text):
            suffix_tokens, _ = self._tokenise(text[cursor:])
            token_bytes.extend(suffix_tokens)

        return token_bytes, template_ids

    def _tokenise(self, text: str) -> tuple[bytearray, List[int]]:
        token_bytes = bytearray()
        template_ids: List[int] = []

        i = 0
        while i < len(text):
            entry = self._longest_dictionary_match(text, i)
            if entry:
                token_bytes.append(self.DICTIONARY_KIND)
                token_bytes.append(entry.token_id & 0xFF)
                i += len(entry.phrase)
                continue

            # literal run
            start = i
            i += 1
            while i < len(text) and (i - start) < 255:
                if self._longest_dictionary_match(text, i):
                    break
                i += 1
            literal_bytes = text[start:i].encode("utf-8")
            token_bytes.append(self.LITERAL_KIND)
            token_bytes.append(len(literal_bytes) & 0xFF)
            token_bytes.extend(literal_bytes)

        return token_bytes, template_ids

    def _longest_dictionary_match(self, text: str, pos: int):
        for entry in self._dictionary_entries:
            if text.startswith(entry.phrase, pos):
                return entry
        return None

    def clear_cache(self) -> None:
        """Clear the encoding cache"""
        self._cached_encode.cache_clear()
        self._cache_hits = 0
        self._cache_misses = 0

    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics"""
        cache_info = self._cached_encode.cache_info()
        total_requests = self._cache_hits + self._cache_misses
        hit_rate = (self._cache_hits / total_requests * 100) if total_requests > 0 else 0.0

        return {
            'hits': cache_info.hits,
            'misses': cache_info.misses,
            'size': cache_info.currsize,
            'maxsize': cache_info.maxsize,
            'hit_rate_percent': hit_rate,
        }
