#!/usr/bin/env python3
"""Tests for template cache self-healing logic."""

import sqlite3
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aura_compression.templates import TemplateLibrary, TemplateMatch
from aura_compression.compressor_refactored import ProductionHybridCompressor
from aura_compression.enums import CompressionMethod


def _create_template_library(cache_dir: Path) -> TemplateLibrary:
    return TemplateLibrary(enable_persistent_cache=True, cache_dir=str(cache_dir))


def test_template_library_invalidates_stale_persistent(tmp_path):
    """Persistent cache entries referencing missing templates should be dropped."""
    library = _create_template_library(tmp_path)
    text = "stale template payload"

    library._persistent_cache.put(text, {
        'template_id': 999,
        'slots': [],
        'start': None,
        'end': None,
    })

    match = library.match(text)
    assert match is None
    assert library._persistent_cache.get(text) is None

    cache_file = Path(library._persistent_cache.cache_file)
    assert cache_file.exists(), "SQLite cache should be created on disk"
    with sqlite3.connect(cache_file) as conn:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='template_cache'"
        )
        assert cursor.fetchone() is not None


def test_compressor_self_heals_stale_cache(tmp_path):
    """ProductionHybridCompressor should recover from stale template cache entries."""
    cache_dir = tmp_path / "cache"
    audit_dir = tmp_path / "audit"
    store_path = tmp_path / "templates_store.json"

    compressor = ProductionHybridCompressor(
        enable_aura=False,
        enable_audit_logging=False,
        enable_sidechain=True,
        template_store_path=str(store_path),
        audit_log_directory=str(audit_dir),
        template_cache_dir=str(cache_dir),
        template_sync_interval_seconds=None,
    )

    text = "this text should fall back to auralite"
    compressor.template_library._persistent_cache.put(text, {
        'template_id': 250,
        'slots': [],
        'start': None,
        'end': None,
    })
    compressor._template_manager._template_cache[text] = TemplateMatch(250, [])

    _, method, _ = compressor.compress(text)
    assert method != CompressionMethod.BINARY_SEMANTIC
    assert compressor.template_library._persistent_cache.get(text) is None

    cache_file = Path(compressor.template_library._persistent_cache.cache_file)
    assert cache_file.exists(), "SQLite cache should persist to disk"
    with sqlite3.connect(cache_file) as conn:
        cursor = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='template_cache'"
        )
        assert cursor.fetchone()[0] == 1
