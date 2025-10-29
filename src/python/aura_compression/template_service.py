#!/usr/bin/env python3
"""
Template Service - Extracted template management functionality from ProductionHybridCompressor
Handles template library, normalization, store synchronization, and compression operations
"""
import json
import os
import struct
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple, Protocol

from .templates import TemplateLibrary, TemplateMatch
from .normalizer import TemplateNormalizer, get_standard_normalizer


class TemplateServiceInterface(Protocol):
    """Protocol for template service implementations"""

    def compress_with_template(self, template_id: int, slots: List[str]) -> bytes:
        """Compress data using a template"""
        ...

    def find_template_match(self, text: str) -> Optional[TemplateMatch]:
        """Find a template match for the given text"""
        ...

    def record_template_use(self, template_id: int) -> None:
        """Record usage of a template"""
        ...

    def normalize_text(self, text: str) -> Tuple[str, Dict[str, Any]]:
        """Normalize text for template matching"""
        ...

    def sync_template_store(self, force: bool = False) -> None:
        """Synchronize templates from store file"""
        ...

    def ensure_template_loaded(self, template_id: int) -> None:
        """Ensure a template is loaded"""
        ...


class TemplateService(TemplateServiceInterface):
    """
    Service for managing templates, normalization, and template-based compression
    """

    def __init__(
        self,
        template_store_path: Optional[str] = None,
        template_cache_size: int = 128,
        enable_normalization: bool = True,
    ):
        """
        Initialize template service

        Args:
            template_store_path: Path to template store JSON file
            template_cache_size: Maximum active dynamic templates
            enable_normalization: Whether to enable text normalization
        """
        # Template library
        self.template_library = TemplateLibrary()

        # Template normalization
        self.enable_normalization = enable_normalization
        self._normalizer: Optional[TemplateNormalizer] = None
        if enable_normalization:
            self._normalizer = get_standard_normalizer()

        # Template store management
        self.template_cache_size = template_cache_size
        self._template_store_path: Optional[Path] = None
        self._template_store_mtime: Optional[float] = None

        # Resolve template store path
        resolved_store = template_store_path or os.getenv("AURA_TEMPLATE_STORE")
        if resolved_store is None:
            default_store = Path("./template_store.json")
            if default_store.exists():
                resolved_store = str(default_store)

        if resolved_store:
            self._template_store_path = Path(resolved_store)
            self.sync_template_store(force=True)

    def compress_with_template(self, template_id: int, slots: List[str]) -> bytes:
        """
        Binary semantic compression using templates

        Optimized format:
        - Zero-slot templates: [template_id:1] (1 byte total)
        - Non-zero slots: [template_id:1][slot_count:1][slot0_len:2][slot0_data]...
        """
        if template_id < 0 or template_id > 255:
            raise ValueError(f"Template ID must be between 0 and 255 (got {template_id})")

        self.ensure_template_loaded(template_id)

        entry = self.template_library.get_entry(template_id)
        if entry is None:
            raise ValueError(f"Unknown template ID: {template_id}")

        if len(slots) > 255:
            raise ValueError(f"Too many slots: {len(slots)} (max 255)")
        if entry.slot_count != len(slots):
            raise ValueError(
                f"Template {template_id} expects {entry.slot_count} slots, got {len(slots)}"
            )

        result = bytearray()
        result.append(template_id & 0xFF)

        # Optimize: zero-slot templates are just 1 byte (template_id only)
        if len(slots) == 0:
            return bytes(result)

        result.append(len(slots) & 0xFF)

        for slot in slots:
            slot_bytes = slot.encode('utf-8')
            if len(slot_bytes) > 65535:
                raise ValueError(f"Slot too long: {len(slot_bytes)} bytes (max 65535)")
            result.extend(struct.pack('>H', len(slot_bytes)))
            result.extend(slot_bytes)

        return bytes(result)

    def find_template_match(self, text: str) -> Optional[TemplateMatch]:
        """
        Find a template match for the given text
        This is a placeholder - actual implementation would use ML/template matching
        """
        # For now, return None - template matching logic would be implemented here
        # This could involve ML models, pattern matching, etc.
        return None

    def record_template_use(self, template_id: int) -> None:
        """Record usage of a template for analytics"""
        self.template_library.record_use(template_id)

    def normalize_text(self, text: str) -> Tuple[str, Dict[str, Any]]:
        """
        Normalize text for template matching

        Returns:
            Tuple of (normalized_text, normalization_metadata)
        """
        if not self.enable_normalization or self._normalizer is None:
            return text, {}

        result = self._normalizer.normalize(text)
        return result.normalized_text, {
            'replacements': result.replacements,
            'normalization_count': result.normalization_count
        }

    def sync_template_store(self, force: bool = False) -> None:
        """
        Synchronize templates from store file
        """
        if self._template_store_path is None:
            return

        if not self._template_store_path.exists():
            if self._template_store_mtime is not None:
                self.template_library.sync_dynamic_templates({})
                self._template_store_mtime = None
            return

        mtime = self._template_store_path.stat().st_mtime
        if not force and self._template_store_mtime is not None:
            if mtime <= self._template_store_mtime:
                return

        try:
            data = json.loads(self._template_store_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return

        raw_templates = data.get("templates")
        if raw_templates is None or not raw_templates:
            raw_templates = data.get("platform_templates", {})
        if raw_templates is None:
            raw_templates = {}
        dynamic_templates: Dict[int, str] = {}

        for tid, info in raw_templates.items():
            try:
                template_id = int(tid)
            except (TypeError, ValueError):
                continue

            if not (0 <= template_id <= 255):
                continue

            pattern = info.get("pattern")
            if not isinstance(pattern, str) or not pattern.strip():
                continue

            dynamic_templates[template_id] = pattern

        self.template_library.sync_dynamic_templates(dynamic_templates)
        self._template_store_mtime = mtime

    def ensure_template_loaded(self, template_id: int) -> None:
        """
        Ensure a template is loaded from store if available
        """
        if self.template_library.get_entry(template_id):
            return

        if self._template_store_path is None:
            env_store = os.getenv("AURA_TEMPLATE_STORE")
            if env_store and Path(env_store).exists():
                self._template_store_path = Path(env_store)
            else:
                default_store = Path("./template_store.json")
                if default_store.exists():
                    self._template_store_path = default_store

        self.sync_template_store(force=True)

    def get_template_library(self) -> TemplateLibrary:
        """Get the underlying template library"""
        return self.template_library

    def get_normalizer(self) -> Optional[TemplateNormalizer]:
        """Get the text normalizer"""
        return self._normalizer


class NoOpTemplateService(TemplateServiceInterface):
    """
    No-operation template service for minimal functionality
    """

    def compress_with_template(self, template_id: int, slots: List[str]) -> bytes:
        """No-op implementation - should not be called"""
        raise NotImplementedError("Template compression not available")

    def find_template_match(self, text: str) -> Optional[TemplateMatch]:
        """No-op implementation"""
        return None

    def record_template_use(self, template_id: int) -> None:
        """No-op implementation"""
        pass

    def normalize_text(self, text: str) -> Tuple[str, Dict[str, Any]]:
        """No-op implementation"""
        return text, {}

    def sync_template_store(self, force: bool = False) -> None:
        """No-op implementation"""
        pass

    def ensure_template_loaded(self, template_id: int) -> None:
        """No-op implementation"""
        pass


def create_template_service(
    template_store_path: Optional[str] = None,
    template_cache_size: int = 128,
    enable_normalization: bool = True,
) -> TemplateServiceInterface:
    """
    Factory function to create template service

    Args:
        template_store_path: Path to template store JSON file
        template_cache_size: Maximum active dynamic templates
        enable_normalization: Whether to enable text normalization

    Returns:
        TemplateServiceInterface implementation
    """
    return TemplateService(
        template_store_path=template_store_path,
        template_cache_size=template_cache_size,
        enable_normalization=enable_normalization,
    )