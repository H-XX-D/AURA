#!/usr/bin/env python3
"""
Template Manager - Handles template matching and management
Extracted from the monolithic ProductionHybridCompressor
"""

import json
import os
import re
import struct
from collections import Counter
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from aura_compression.enums import (
    _SEMANTIC_PREVIEW_LIMIT,
    _SEMANTIC_TOKEN_LIMIT,
    _SEMANTIC_TOKEN_PATTERN,
    TEMPLATE_METADATA_KIND,
    CompressionMethod,
)
from aura_compression.templates import TemplateLibrary, TemplateMatch


class TemplateManager:
    """
    Manages template matching and template library operations
    """

    def __init__(self, template_library: TemplateLibrary):
        """
        Initialize template manager
        """
        self.template_library = template_library
        self._template_cache: Dict[str, Optional[TemplateMatch]] = {}
        self._cache_max_size = 1000

    def find_template_match(self, text: str) -> Optional[TemplateMatch]:
        """
        Find the best template match for the given text
        """
        # Check cache first
        if text in self._template_cache:
            cached_match = self._template_cache[text]
            if cached_match is None:
                return None
            if self.validate_template_match(text, cached_match):
                return cached_match
            # Stale cached entry - invalidate and fall through to fresh lookup
            self.invalidate_text(text)
            self.template_library.invalidate_text_cache(text)

        # Find best match
        best_match = self.template_library.match(text)

        if best_match and not self.validate_template_match(text, best_match):
            # Cached persistent entry may be stale; invalidate and retry once
            self.template_library.invalidate_text_cache(text)
            best_match = self.template_library.match(text)
            if best_match and not self.validate_template_match(text, best_match):
                best_match = None

        # Cache result
        self._add_to_cache(text, best_match)

        return best_match

    def _add_to_cache(self, text: str, match: Optional[TemplateMatch]):
        """
        Add template match to cache
        """
        if len(self._template_cache) >= self._cache_max_size:
            # Simple LRU: remove oldest entry
            oldest_key = next(iter(self._template_cache))
            del self._template_cache[oldest_key]

        self._template_cache[text] = match

    def invalidate_text(self, text: str) -> None:
        """Remove a cached match for specific text."""
        self._template_cache.pop(text, None)

    def clear_cache(self):
        """
        Clear the template match cache
        """
        self._template_cache.clear()

    def get_template_stats(self) -> dict:
        """
        Get statistics about template usage
        """
        cache_hits = sum(1 for match in self._template_cache.values() if match is not None)
        cache_misses = sum(1 for match in self._template_cache.values() if match is None)
        total_cache_entries = len(self._template_cache)

        return {
            "cache_size": total_cache_entries,
            "cache_hit_rate": cache_hits / total_cache_entries if total_cache_entries > 0 else 0.0,
            "template_library_size": (
                len(self.template_library.templates)
                if hasattr(self.template_library, "templates")
                else 0
            ),
        }

    def validate_template_match(self, text: str, template_match: TemplateMatch) -> bool:
        """
        Validate that a template match correctly reconstructs the original text
        """
        try:
            reconstructed = self.template_library.format_template(
                template_match.template_id, template_match.slots
            )
            return reconstructed == text
        except Exception:
            return False

    def get_semantic_preview(self, text: str, limit: int = _SEMANTIC_PREVIEW_LIMIT) -> str:
        """
        Get a semantic preview of the text for template matching
        """
        if len(text) <= limit:
            return text

        # Extract semantic tokens
        tokens = re.findall(_SEMANTIC_TOKEN_PATTERN, text)
        if len(tokens) <= _SEMANTIC_TOKEN_LIMIT:
            return text

        # Create preview from first few tokens
        preview_tokens = tokens[:_SEMANTIC_TOKEN_LIMIT]
        preview = " ".join(preview_tokens)

        # Add length indicator if truncated
        if len(preview) < len(text):
            preview += f" ... ({len(text)} chars total)"

        return preview

    def extract_template_slots(self, text: str, template_pattern: str) -> Optional[List[str]]:
        """
        Extract slot values from text using a template pattern
        """
        try:
            # Convert template pattern to regex
            # This is a simplified implementation - real implementation would be more sophisticated
            regex_pattern = re.escape(template_pattern)
            # Replace slot placeholders with capture groups
            regex_pattern = regex_pattern.replace(r"\{\}", r"(.+?)")

            match = re.match(regex_pattern, text, re.DOTALL)
            if match:
                return list(match.groups())
            return None
        except Exception:
            return None

    def update_template_usage_stats(self, template_id: int, success: bool = True):
        """
        Update usage statistics for a template
        """
        # This would update some internal statistics
        # For now, just pass
        pass

    def get_template_metadata(self, template_id: int) -> Optional[dict]:
        """
        Get metadata for a specific template
        """
        try:
            entry = self.template_library.get_entry(template_id)
            if entry:
                return {
                    "id": template_id,
                    "slot_count": entry.slot_count,
                    "pattern": getattr(entry, "pattern", None),
                    "category": getattr(entry, "category", None),
                }
            return None
        except Exception:
            return None
