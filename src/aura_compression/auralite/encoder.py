"""Aura-Lite encoder implementation."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Callable, Dict, FrozenSet, List, Optional, Union, cast

from aura_compression.brio_full.dictionary import DICTIONARY, DictionaryEntry
from aura_compression.brio_full.trie import DictionaryTrie
from aura_compression.templates import TemplateLibrary, TemplateMatch


@dataclass(frozen=True)
class _DictionaryResources:
    entries: tuple[DictionaryEntry, ...]
    id_to_entry: Dict[int, DictionaryEntry]
    trie: DictionaryTrie
    prefix_chars: FrozenSet[str]


def _build_dictionary_resources() -> _DictionaryResources:
    filtered_entries = tuple(entry for entry in DICTIONARY if entry.token_id <= 255)
    trie = DictionaryTrie()
    prefix_chars = set()
    for entry in filtered_entries:
        trie.insert(entry.phrase, entry.token_id)
        if entry.phrase:
            prefix_chars.add(entry.phrase[0])

    return _DictionaryResources(
        entries=filtered_entries,
        id_to_entry={entry.token_id: entry for entry in filtered_entries},
        trie=trie,
        prefix_chars=frozenset(prefix_chars),
    )


_DICTIONARY_RESOURCES = _build_dictionary_resources()


@dataclass
class AuraLiteEncoded:
    payload: bytes
    template_ids: List[int]


class AuraLiteEncoder:
    """Lightweight encoder using template tokens + dictionary + literal runs."""

    TEMPLATE_KIND = 0x00
    DICTIONARY_KIND = 0x01
    LITERAL_KIND = 0x03

    def __init__(
        self,
        template_library: Optional[TemplateLibrary] = None,
        use_compact_header: bool = True,
        enable_fast_path: bool = True,
        fast_path_cache_size: int = 4096,
    ) -> None:
        resources = _DICTIONARY_RESOURCES
        self._id_to_entry = resources.id_to_entry
        self._dictionary_trie = resources.trie
        self._dictionary_prefix_chars = resources.prefix_chars
        self._template_library = template_library or TemplateLibrary()
        self._use_compact_header = use_compact_header

        # Fast path configuration
        self._cache_enabled = enable_fast_path
        self._fast_path_cache_size = max(0, fast_path_cache_size)
        self._effective_cache_size = 0
        self._fast_path_encoder: Callable[[str], AuraLiteEncoded] = self._build_fast_path_encoder(
            self._fast_path_cache_size
        )

    def _encode_text_only(self, text: str) -> AuraLiteEncoded:
        """Encode text-only payloads without template hints."""
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

    def _build_fast_path_encoder(self, desired_maxsize: int) -> Callable[[str], AuraLiteEncoded]:
        """Create (or rebuild) the fast path encoder with the requested cache size."""
        effective_size = desired_maxsize if self._cache_enabled and desired_maxsize > 0 else 0
        self._effective_cache_size = effective_size

        if effective_size <= 0:
            return self._encode_text_only

        return lru_cache(maxsize=effective_size)(self._encode_text_only)

    def configure_fast_path_cache(
        self, *, enabled: Optional[bool] = None, maxsize: Optional[int] = None
    ) -> None:
        """Allow callers to tune or disable the fast path cache at runtime."""
        if enabled is not None:
            self._cache_enabled = enabled
        if maxsize is not None:
            self._fast_path_cache_size = max(0, int(maxsize))

        self._fast_path_encoder = self._build_fast_path_encoder(self._fast_path_cache_size)

    def encode(
        self,
        text: str,
        template_match: Optional[TemplateMatch] = None,
        template_spans: Optional[List[TemplateMatch]] = None,
    ) -> AuraLiteEncoded:
        # FAST PATH: Use cache for simple text-only encoding
        use_fast_path = (
            self._cache_enabled
            and template_match is None
            and (template_spans is None or len(template_spans) == 0)
        )

        if use_fast_path:
            try:
                return self._fast_path_encoder(text)
            except TypeError:
                # Unhashable type, fall through to normal path
                pass

        # Normal path
        if template_match:
            token_bytes = self._encode_template(template_match)
            template_ids = [template_match.template_id]
        else:
            span_list = [
                match
                for match in (template_spans or [])
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

    def _encode_with_spans(
        self, text: str, spans: List[TemplateMatch]
    ) -> tuple[bytearray, List[int]]:
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

        length = len(text)
        prefix_chars = self._dictionary_prefix_chars
        i = 0

        while i < length:
            entry = None
            if text[i] in prefix_chars:
                entry = self._longest_dictionary_match(text, i)

            if entry:
                token_bytes.append(self.DICTIONARY_KIND)
                token_bytes.append(entry.token_id & 0xFF)
                i += len(entry.phrase)
                continue

            start = i
            i += 1
            while i < length:
                if (i - start) >= 255:
                    break
                char = text[i]
                if char in prefix_chars:
                    entry = self._longest_dictionary_match(text, i)
                    if entry:
                        break
                i += 1

            literal_bytes = text[start:i].encode("utf-8")
            token_bytes.append(self.LITERAL_KIND)
            token_bytes.append(len(literal_bytes) & 0xFF)
            token_bytes.extend(literal_bytes)

        return token_bytes, template_ids

    def _longest_dictionary_match(self, text: str, pos: int):
        match = self._dictionary_trie.longest_prefix_match(text, pos)
        if match is None:
            return None
        _, token_id = match
        entry = self._id_to_entry.get(token_id)
        return entry

    def clear_cache(self) -> None:
        """Clear the encoding cache."""
        cache_clear = getattr(self._fast_path_encoder, "cache_clear", None)
        if callable(cache_clear):
            cache_clear()

    def get_cache_stats(self) -> Dict[str, Union[float, int, bool]]:
        """Get cache statistics for observability and tuning."""
        cache_info_fn = getattr(self._fast_path_encoder, "cache_info", None)
        if cache_info_fn is None:
            return {
                "enabled": False,
                "hits": 0,
                "misses": 0,
                "size": 0,
                "maxsize": 0,
                "hit_rate_percent": 0.0,
            }

        cache_info = cache_info_fn()
        total_requests = cache_info.hits + cache_info.misses
        hit_rate = (cache_info.hits / total_requests * 100.0) if total_requests > 0 else 0.0

        return {
            "enabled": self._effective_cache_size > 0,
            "hits": cache_info.hits,
            "misses": cache_info.misses,
            "size": cache_info.currsize,
            "maxsize": cache_info.maxsize,
            "hit_rate_percent": hit_rate,
        }
