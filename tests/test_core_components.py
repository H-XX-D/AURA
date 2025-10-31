#!/usr/bin/env python3
"""Smoke tests for core compression components."""

from __future__ import annotations

from pathlib import Path

from aura_compression.compressor_refactored import ProductionHybridCompressor
from aura_compression.templates import TemplateLibrary


def _build_compressor(tmp_path: Path) -> ProductionHybridCompressor:
    """Create a compressor configured for unit testing."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    compressor = ProductionHybridCompressor(
        enable_aura=False,  # avoid spawning discovery worker
        enable_fast_path=True,
        enable_audit_logging=False,
        template_cache_dir=str(cache_dir),
        template_sync_interval_seconds=None,
    )
    return compressor


def test_production_compressor_round_trip(tmp_path: Path):
    compressor = _build_compressor(tmp_path)
    message = "API REQUEST user=1001 action=login latency=45ms region=us-east device=ios"

    payload, method, metadata = compressor.compress(message)
    restored = compressor.decompress(payload)

    assert restored == message
    assert method.name
    assert metadata["compressed_size"] > 0

    compressor.template_library.shutdown()


def test_template_library_default_match():
    library = TemplateLibrary()
    custom_id = 20000
    pattern = "Order {0}: status={1}"
    library.add(custom_id, pattern)

    sample = "Order 42: status=ready"
    match = library.match(sample)

    assert match is not None
    assert match.template_id == custom_id
    assert match.slots == ["42", "ready"]
