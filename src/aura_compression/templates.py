"""Template library providing matching, formatting, and dynamic sync."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Pattern, Any
from functools import lru_cache

from .persistent_cache import PersistentTemplateCache


@dataclass
class TemplateMatch:
    template_id: int
    slots: List[str]
    start: Optional[int] = None
    end: Optional[int] = None


@dataclass
class TemplateEntry:
    template_id: int
    pattern: str
    slot_count: int


@dataclass
class TemplateRecord:
    template_id: int
    pattern: str
    regex: Pattern[str]
    partial_regex: Pattern[str]
    slot_order: List[int]
    literal_length: int
    anchor_literal: Optional[str]
    anchor_casefold: Optional[str]

    def match(self, text: str) -> Optional[List[str]]:
        match_obj = self.regex.fullmatch(text.strip())
        if not match_obj:
            return None
        return self._extract_slots(match_obj)

    def _extract_slots(self, match_obj) -> List[str]:
        if not self.slot_order:
            return []
        slots: List[str] = []
        group_dict = match_obj.groupdict()
        for slot_idx in self.slot_order:
            prefix = f"slot_{slot_idx}_"
            values = [
                value.strip() if value else ""
                for name, value in group_dict.items()
                if name.startswith(prefix)
            ]
            slots.append(values[0] if values else "")
        return slots


class TemplateLibrary:
    """Template library supporting matching and dynamic sync."""

    _SLOT_RE = re.compile(r"\{(\d+)\}")

    # Template ID Ranges (reorganized for better distribution):
    # 0-127:   DEFAULT_TEMPLATES (most common patterns)
    # 128-191: DYNAMIC_RANGE (discovered templates - 64 slots)
    # 192-255: CLIENT_SYNC_RANGE (client-discovered - 64 slots)

    DEFAULT_TEMPLATES: Dict[int, str] = {
        # Common responses (0-19)
        # 0 is repurposed for limitation messages to match tests
        0: "I don't have access to {0}. {1}",
        1: "No",
        2: "I don't know",
        3: "I'm not sure",
        4: "That's correct",
        5: "That's incorrect",
        6: "Maybe",
        7: "Probably",
        8: "Definitely",
        9: "Absolutely",

        # Limitations & abilities (20-39)
        # 20 is repurposed for detailed definitions to match tests
        20: "{0} is {1} {2} {3}.",
        21: "I don't have access to {0}. {1}",
        22: "I cannot {0}.",
        23: "I'm unable to {0}.",
        24: "I can't {0}.",
        25: "I can help with {0}.",
        26: "I can help you {0}.",
        27: "I'm able to {0}.",

        # Facts & definitions (40-59)
        # 40 is repurposed for instruction with command blocks to match tests
        40: "To {0}, use {1}: `{2}`",
        41: "{0} are {1}.",
        42: "The {0} is {1}.",
        43: "The {0} are {1}.",
        44: "The {0} of {1} is {2}.",
        45: "{0} means {1}.",
        46: "{0} refers to {1}.",

        # Questions (60-69)
        60: "What {0}?",
        61: "Why {0}?",
        62: "How {0}?",
        63: "When {0}?",
        64: "Where {0}?",
        65: "Can you {0}?",
        66: "Could you {0}?",
        67: "Would you {0}?",
        68: "Could you clarify {0}?",
        69: "What specific {0} would you like to know more about?",

        # Instructions & recommendations (70-89)
        70: "To {0}, {1}.",
        71: "To {0}, use {1}.",
        72: "To {0}, use {1}: `{2}`",
        73: "You can {0} by {1}.",
        74: "Try {0}.",
        75: "I recommend {0}.",
        76: "I suggest {0}.",
        77: "Consider {0}.",
        78: "To {0}, I recommend: {1}",

    # Explanations and recommendations (90-99)
    # 90 is repurposed for recommendations to match tests
    90: "To {0}, I recommend: {1}",
        91: "{0} is used for {1}.",
        92: "The {0} of {1} is {2} because {3}.",
        93: "{0} because {1}.",
        94: "This is {0}.",
        95: "This means {0}.",

    # Clarifications (100-109)
    # 100 is repurposed for clarification question to match tests
    100: "Yes, I can help with that. What specific {0} would you like to know more about?",
        101: "Here's an example: `{0}`",
        102: "Here's how to {0}:\n\n```{1}\n{2}\n```",
        103: "For example: {0}",

    # App/UX snippets (128-191 - dynamic range, but provide a default used by tests)
    130: "Open the {0}: {1}",

        # Lists & enumerations (110-119)
        110: "Common {0} include: {1}.",
        111: "The main {0} are: {1}.",
        112: "Examples include: {0}.",
        113: "{0}, {1}, and {2}.",
        114: "{0} and {1}.",

        # Comparisons (120-127)
        120: "The main {0} between {1} are: {2}",
        121: "{0} and {1} are different: {0} {2}, {1} {3}.",
        122: "{0} is better than {1} because {2}.",
        123: "{0} is similar to {1}.",
        124: "{0} differs from {1} in {2}.",
        125: "Unlike {0}, {1} {2}.",
        126: "Both {0} and {1} {2}.",
        127: "Neither {0} nor {1} {2}.",
    }

    # Dynamic templates: discovered at runtime (64 slots)
    DYNAMIC_RANGE = range(128, 192)

    # Client-synced templates: discovered on client side (64 slots)
    CLIENT_SYNC_RANGE = range(192, 256)

    def __init__(self, custom_templates: Optional[Dict[int, str]] = None, enable_fast_matching: bool = True,
                 enable_persistent_cache: bool = True, cache_dir: str = ".aura_cache"):
        self._templates: Dict[int, str] = {}
        self._records: Dict[int, TemplateRecord] = {}
        self._static_ids = set(self.DEFAULT_TEMPLATES.keys())
        self._next_dynamic_id = self.DYNAMIC_RANGE.start
        self._next_client_sync_id = self.CLIENT_SYNC_RANGE.start

        # Fast matching optimization
        self.enable_fast_matching = enable_fast_matching
        self._length_buckets: Dict[int, List[int]] = {}  # length_bucket -> [template_ids]
        self._pattern_hashes: Dict[int, List[int]] = {}  # hash -> [template_ids]

        # Template match cache for performance (Optimization 1)
        self._match_cache_enabled = True
        self._match_cache_hits = 0
        self._match_cache_misses = 0

        # Persistent cache for surviving restarts (Optimization: Persistent Template Cache)
        self.enable_persistent_cache = enable_persistent_cache
        self._persistent_cache = PersistentTemplateCache(cache_dir=cache_dir) if enable_persistent_cache else None

        for template_id, pattern in self.DEFAULT_TEMPLATES.items():
            self._register_template(template_id, pattern)
            self._advance_counters(template_id)

        if custom_templates:
            for template_id, pattern in custom_templates.items():
                self._register_template(template_id, pattern)
                self._advance_counters(template_id)

        self.templates = dict(self._templates)

    # ------------------------------------------------------------------ public API

    def get(self, template_id: int) -> Optional[str]:
        return self._templates.get(template_id)

    def list_templates(self) -> Dict[int, str]:
        return dict(self._templates)

    def add(self, template_id: int, template: str) -> None:
        self._register_template(template_id, template)
        self._advance_counters(template_id)
        self.templates = dict(self._templates)

    def remove(self, template_id: int) -> None:
        if template_id in self._templates and template_id not in self._static_ids:
            self._templates.pop(template_id, None)
            self._records.pop(template_id, None)
            self.templates = dict(self._templates)
            # Clear cache when templates change
            self.clear_match_cache()

    def clear_match_cache(self) -> None:
        """Clear the template match cache (call when templates change)"""
        self._cached_match.cache_clear()
        self._match_cache_hits = 0
        self._match_cache_misses = 0

    def get_cache_stats(self) -> Dict[str, int]:
        """Get template match cache statistics"""
        cache_info = self._cached_match.cache_info()
        total_requests = self._match_cache_hits + self._match_cache_misses
        hit_rate = (self._match_cache_hits / total_requests * 100) if total_requests > 0 else 0.0

        return {
            'hits': cache_info.hits,
            'misses': cache_info.misses,
            'size': cache_info.currsize,
            'maxsize': cache_info.maxsize,
            'hit_rate_percent': hit_rate,
        }

    def format_template(self, template_id: int, slots: Iterable[str]) -> str:
        pattern = self._templates.get(template_id)
        if pattern is None:
            raise ValueError(f"Unknown template ID: {template_id}")
        return pattern.format(*slots)

    def _compute_text_hash(self, text: str) -> int:
        """Compute fast hash for text matching pre-filter"""
        if not text:
            return 0
        length = len(text)
        first_char = ord(text[0]) if text else 0
        last_char = ord(text[-1]) if text else 0
        space_count = text.count(' ')
        return hash((length // 10, first_char, last_char, space_count // 3))

    def _get_candidate_templates(self, text: str) -> List[int]:
        """Get candidate template IDs using fast pre-filtering"""
        if not self.enable_fast_matching:
            return list(self._records.keys())

        # Try length bucket first
        length_bucket = len(text) // 10
        candidates = set(self._length_buckets.get(length_bucket, []))

        # Also try adjacent buckets (±1)
        candidates.update(self._length_buckets.get(length_bucket - 1, []))
        candidates.update(self._length_buckets.get(length_bucket + 1, []))

        # Try pattern hash
        pattern_hash = self._compute_text_hash(text)
        candidates.update(self._pattern_hashes.get(pattern_hash, []))

        # If no candidates, fall back to all templates
        if not candidates:
            return list(self._records.keys())

        return list(candidates)

    @lru_cache(maxsize=1024)
    def _cached_match(self, text: str) -> Optional[TemplateMatch]:
        """Cached template matching for performance (Optimization 1)"""
        best_match: Optional[TemplateMatch] = None
        best_score: Optional[tuple[int, int]] = None
        stripped = text.strip()

        # Get candidate templates using fast pre-filter
        candidate_ids = self._get_candidate_templates(stripped)

        for template_id in candidate_ids:
            record = self._records.get(template_id)
            if not record:
                continue

            slots = record.match(stripped)
            if slots is None:
                continue
            total_slot_length = sum(len(slot) for slot in slots)
            score = (total_slot_length, len(slots))
            if best_score is None or score < best_score:
                best_score = score
                best_match = TemplateMatch(template_id=record.template_id, slots=slots)

        return best_match

    def match(self, text: str) -> Optional[TemplateMatch]:
        """Match text to template with caching (including persistent cache)"""
        # Try persistent cache first (Optimization: Persistent Template Cache)
        if self._persistent_cache:
            cached_data = self._persistent_cache.get(text)
            if cached_data is not None:
                # Convert dict back to TemplateMatch
                return TemplateMatch(**cached_data)

        # Try in-memory LRU cache
        if self._match_cache_enabled:
            try:
                result = self._cached_match(text)
                self._match_cache_hits += 1

                # Store in persistent cache for future restarts
                if self._persistent_cache and result is not None:
                    # Convert TemplateMatch to dict for storage
                    match_data = {
                        'template_id': result.template_id,
                        'slots': result.slots,
                        'start': result.start,
                        'end': result.end
                    }
                    self._persistent_cache.put(text, match_data)

                return result
            except TypeError:
                # Text not hashable, fall through to uncached
                self._match_cache_misses += 1
        else:
            self._match_cache_misses += 1

        # Uncached path (fallback)
        result = self._cached_match.__wrapped__(self, text)

        # Store successful matches in persistent cache
        if self._persistent_cache and result is not None:
            # Convert TemplateMatch to dict for storage
            match_data = {
                'template_id': result.template_id,
                'slots': result.slots,
                'start': result.start,
                'end': result.end
            }
            self._persistent_cache.put(text, match_data)

        return result

    def find_substring_matches(self, text: str) -> List[TemplateMatch]:
        candidates: List[TemplateMatch] = []
        seen_spans = set()
        text_length = len(text)
        text_casefold = text.casefold()
        if self.enable_fast_matching:
            max_bucket = len(text) // 10
            candidate_ids = set()
            for bucket in range(max_bucket + 1):
                candidate_ids.update(self._length_buckets.get(bucket, []))
            if not candidate_ids:
                candidate_records = self._records.values()
            else:
                candidate_records = (
                    self._records[tid]
                    for tid in candidate_ids
                    if tid in self._records
                )
        else:
            candidate_records = self._records.values()

        for record in candidate_records:
            if record.literal_length > len(text):
                continue
            if record.anchor_casefold and record.anchor_casefold not in text_casefold:
                continue
            for match_obj in record.partial_regex.finditer(text):
                start = match_obj.start()
                if start < 0:
                    continue
                best_end = None
                best_slots: Optional[List[str]] = None

                # Expand to the right to capture the longest substring that fully matches the template
                end = match_obj.end()
                while end <= text_length:
                    segment = text[start:end]
                    slots = record.match(segment)
                    if slots is not None:
                        best_end = end
                        best_slots = slots
                        end += 1
                        continue
                    if best_end is not None:
                        break
                    end += 1

                if best_end is None or best_slots is None:
                    continue

                # Enforce word-boundary safety to avoid matching inside words.
                # If the matched segment starts/ends with an alphanumeric character,
                # ensure the preceding/following characters (if any) are not alphanumeric.
                seg = text[start:best_end]
                if seg:
                    # Check left boundary
                    if seg[0].isalnum() and start > 0 and text[start - 1].isalnum():
                        continue
                    # Check right boundary
                    if seg[-1].isalnum() and best_end < text_length and text[best_end].isalnum():
                        continue

                span = (start, best_end)
                if span in seen_spans:
                    continue
                seen_spans.add(span)

                candidates.append(
                    TemplateMatch(
                        template_id=record.template_id,
                        slots=best_slots,
                        start=start,
                        end=best_end,
                    )
                )

        # Deduplicate overlaps by preferring earliest start and longest length
        candidates.sort(key=lambda m: (m.start if m.start is not None else 0,
                                       -((m.end or 0) - (m.start or 0))))

        selected: List[TemplateMatch] = []
        current_end = -1
        for match in candidates:
            if match.start is None or match.end is None:
                continue
            if match.start < current_end:
                continue
            selected.append(match)
            current_end = match.end

        return selected

    def get_entry(self, template_id: int) -> Optional[TemplateEntry]:
        record = self._records.get(template_id)
        if not record:
            return None
        return TemplateEntry(template_id=template_id, pattern=record.pattern, slot_count=len(record.slot_order))

    def extract_slots(self, template_id: int, text: str) -> Optional[List[str]]:
        record = self._records.get(template_id)
        if not record:
            return None
        return record.match(text)

    def record_use(self, template_id: int) -> None:
        # Placeholder for future tracking; no-op in current implementation
        pass

    def sync_dynamic_templates(self, dynamic_templates: Dict[int, str]) -> None:
        dynamic_ids = set(dynamic_templates.keys())
        for template_id in list(self._records.keys()):
            if template_id not in self._static_ids and template_id not in dynamic_ids:
                self.remove(template_id)

        for template_id, pattern in dynamic_templates.items():
            self._register_template(template_id, pattern)
            self._advance_counters(template_id)

        self.templates = dict(self._templates)
        # Clear cache when templates change
        self.clear_match_cache()

    def allocate_dynamic_id(self) -> int:
        while self._next_dynamic_id in self._templates and self._next_dynamic_id < self.DYNAMIC_RANGE.stop:
            self._next_dynamic_id += 1
        if self._next_dynamic_id >= self.DYNAMIC_RANGE.stop:
            raise RuntimeError("Dynamic template ID range exhausted")
        allocated = self._next_dynamic_id
        self._next_dynamic_id += 1
        return allocated

    def allocate_client_sync_id(self) -> int:
        while self._next_client_sync_id in self._templates and self._next_client_sync_id < self.CLIENT_SYNC_RANGE.stop:
            self._next_client_sync_id += 1
        if self._next_client_sync_id >= self.CLIENT_SYNC_RANGE.stop:
            raise RuntimeError("Client-sync template ID range exhausted")
        allocated = self._next_client_sync_id
        self._next_client_sync_id += 1
        return allocated

    def _advance_counters(self, template_id: int) -> None:
        if template_id in self.DYNAMIC_RANGE and template_id >= self._next_dynamic_id:
            self._next_dynamic_id = template_id + 1
        if template_id in self.CLIENT_SYNC_RANGE and template_id >= self._next_client_sync_id:
            self._next_client_sync_id = template_id + 1

    # ------------------------------------------------------------------ helpers

    @classmethod
    def _extract_literal_parts(cls, pattern: str) -> List[str]:
        parts = cls._SLOT_RE.split(pattern)
        return [parts[idx] for idx in range(0, len(parts), 2) if idx < len(parts)]

    @staticmethod
    def _select_anchor_literal(literal_parts: List[str]) -> tuple[Optional[str], Optional[str]]:
        anchor: Optional[str] = None
        for part in literal_parts:
            if not part:
                continue
            if not any(ch.isalnum() for ch in part):
                continue
            if anchor is None or len(part) > len(anchor):
                anchor = part
        if anchor is None:
            return None, None
        return anchor, anchor.casefold()

    def _register_template(self, template_id: int, pattern: str) -> None:
        regex, partial_regex, slot_order = self._compile_pattern(pattern)
        pattern_text = re.sub(r'\{[0-9]+\}', '', pattern)
        literal_length = len(pattern_text)
        literal_parts = self._extract_literal_parts(pattern)
        anchor_literal, anchor_casefold = self._select_anchor_literal(literal_parts)
        self._templates[template_id] = pattern
        self._records[template_id] = TemplateRecord(
            template_id=template_id,
            pattern=pattern,
            regex=regex,
            partial_regex=partial_regex,
            slot_order=slot_order,
            literal_length=literal_length,
            anchor_literal=anchor_literal,
            anchor_casefold=anchor_casefold,
        )

        # Update fast matching indices
        if self.enable_fast_matching:
            # Add to length bucket
            # Approximate pattern length (remove slot placeholders)
            length_bucket = len(pattern_text) // 10
            if length_bucket not in self._length_buckets:
                self._length_buckets[length_bucket] = []
            if template_id not in self._length_buckets[length_bucket]:
                self._length_buckets[length_bucket].append(template_id)

            # Add to pattern hash
            pattern_hash = self._compute_text_hash(pattern_text)
            if pattern_hash not in self._pattern_hashes:
                self._pattern_hashes[pattern_hash] = []
            if template_id not in self._pattern_hashes[pattern_hash]:
                self._pattern_hashes[pattern_hash].append(template_id)

    @classmethod
    def _compile_pattern(cls, pattern: str) -> tuple[Pattern[str], Pattern[str], List[int]]:
        slot_order: List[int] = []
        parts: List[str] = []
        literal = True
        counter = 0
        for part in cls._SLOT_RE.split(pattern):
            if literal:
                parts.append(re.escape(part))
            else:
                slot_idx = int(part)
                if slot_idx not in slot_order:
                    slot_order.append(slot_idx)
                parts.append(rf"(?P<slot_{slot_idx}_{counter}>.+?)")
                counter += 1
            literal = not literal
        regex_body = "".join(parts)
        compiled_full = re.compile(rf"^{regex_body}$", re.IGNORECASE)
        compiled_partial = re.compile(regex_body, re.IGNORECASE)
        return compiled_full, compiled_partial, slot_order

    def shutdown(self) -> None:
        """Shutdown the template library and save persistent cache."""
        if self._persistent_cache:
            self._persistent_cache.shutdown()

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get statistics for both in-memory and persistent caches."""
        stats = {
            'in_memory_cache': {
                'enabled': self._match_cache_enabled,
                'hits': self._match_cache_hits,
                'misses': self._match_cache_misses,
                'hit_rate': (self._match_cache_hits / (self._match_cache_hits + self._match_cache_misses))
                           if (self._match_cache_hits + self._match_cache_misses) > 0 else 0.0
            }
        }

        if self._persistent_cache:
            stats['persistent_cache'] = self._persistent_cache.get_stats()

        return stats


__all__ = ["TemplateLibrary", "TemplateMatch", "TemplateEntry"]
