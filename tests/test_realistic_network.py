#!/usr/bin/env python3
"""
Realistic network workload tests for AURA compression.

These tests exercise binary semantic compression with known conversational
patterns and validate that template discovery promotes new API-style patterns
into the SQLite-backed cache. They intentionally enable template discovery and
binary semantics to mirror production settings.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, Tuple

import pytest

from aura_compression.background_workers import TemplateDiscoveryWorker
from aura_compression.compressor_refactored import ProductionHybridCompressor
from aura_compression.enums import CompressionMethod

NETWORK_MESSAGES: Tuple[str, ...] = (
    "API REQUEST user=1001 action=login latency=45ms region=us-east device=ios",
    "API REQUEST user=1044 action=login latency=47ms region=us-west device=android",
    "API REQUEST user=1089 action=login latency=52ms region=eu-west device=ios",
    "API REQUEST user=1120 action=login latency=50ms region=ap-south device=browser",
    "API REQUEST user=1205 action=login latency=43ms region=us-east device=android",
    "API REQUEST user=1350 action=login latency=46ms region=eu-west device=browser",
)


def _build_compressor(audit_dir: Path, cache_dir: Path) -> ProductionHybridCompressor:
    """Helper to build a compressor with discovery enabled and isolated paths."""
    audit_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)
    compressor = ProductionHybridCompressor(
        enable_aura=True,
        enable_audit_logging=True,
        audit_log_directory=str(audit_dir),
        template_cache_dir=str(cache_dir),
        template_cache_size=256,
        template_sync_interval_seconds=None,
        enable_scorer=True,
        enable_fast_path=True,
    )
    return compressor


@pytest.fixture
def compression_env(tmp_path: Path) -> Iterable[Dict[str, object]]:
    """Yield an initialized compressor and its working directories."""
    audit_dir = tmp_path / "audit"
    cache_dir = tmp_path / "cache"
    compressor = _build_compressor(audit_dir, cache_dir)

    try:
        yield {
            "compressor": compressor,
            "audit_dir": audit_dir,
            "cache_dir": cache_dir,
        }
    finally:
        worker = compressor._template_service.discovery_worker  # type: ignore[attr-defined]
        if worker:
            worker.stop()
        compressor.template_library.shutdown()


def test_binary_semantic_round_trip_for_conversational_template(
    compression_env: Dict[str, object],
) -> None:
    """Ensure conversational prompts hit the binary semantic fast path."""
    compressor: ProductionHybridCompressor = compression_env["compressor"]  # type: ignore[assignment]

    message = "Hello Alice, how are you today?"
    payload, method, metadata = compressor.compress(message)

    assert method == CompressionMethod.BINARY_SEMANTIC
    assert payload[0] == CompressionMethod.BINARY_SEMANTIC.value
    assert metadata.get("template_id") is not None

    restored = compressor.decompress(payload)
    assert restored == message


def test_template_discovery_promotes_network_pattern(tmp_path: Path) -> None:
    """
    Compress a stream of API-style messages, run discovery, and confirm the
    promoted template can drive binary semantic compression via SQLite cache.
    """
    audit_dir = tmp_path / "audit_logs"
    cache_dir = tmp_path / "cache"

    # Phase 1: capture realistic traffic with discovery enabled so audit logs are written.
    compressor = _build_compressor(audit_dir, cache_dir)
    try:
        for message in NETWORK_MESSAGES:
            compressor.compress(message)
    finally:
        worker = compressor._template_service.discovery_worker  # type: ignore[attr-defined]
        if worker:
            worker.stop()
        compressor.template_library.shutdown()

    # Phase 2: run discovery manually with low thresholds for the test environment.
    discovery_worker = TemplateDiscoveryWorker(
        audit_log_directory=str(audit_dir),
        cache_dir=str(cache_dir),
        discovery_interval_seconds=3600,
        min_messages_for_discovery=4,
        min_frequency=3,
        compression_threshold=1.01,
    )
    try:
        promoted = discovery_worker.run_discovery()
        templates = discovery_worker.get_discovered_templates()

        assert promoted >= 1
        assert templates, "Expected at least one discovered template"
    finally:
        discovery_worker.stop()

    # Phase 3: instantiate a fresh compressor that should load the SQLite-backed template.
    followup_compressor = _build_compressor(audit_dir, cache_dir)
    try:
        # Stop the background worker immediately; the template should already be in the cache.
        followup_worker = followup_compressor._template_service.discovery_worker  # type: ignore[attr-defined]
        if followup_worker:
            followup_worker.stop()

        followup_compressor._template_service.sync_template_store()

        payload, method, metadata = followup_compressor.compress(NETWORK_MESSAGES[0])
        assert method == CompressionMethod.BINARY_SEMANTIC
        assert metadata.get("template_id") is not None

        template_id = metadata["template_id"]
        assert isinstance(template_id, int)
        assert template_id >= 149  # Platform discovery allocation range starts at 149.

        restored = followup_compressor.decompress(payload)
        assert restored == NETWORK_MESSAGES[0]
    finally:
        followup_compressor.template_library.shutdown()


def test_mixed_network_payloads_preserve_content(compression_env: Dict[str, object]) -> None:
    """Validate round-trip integrity across varied network-style payloads."""
    compressor: ProductionHybridCompressor = compression_env["compressor"]  # type: ignore[assignment]

    samples = [
        (
            '{"method": "POST", "endpoint": "/api/orders", "body": {"order_id": "ORD-4451", "amount": 149.50}}',
            "JSON API request",
        ),
        (
            "[2025-03-22T02:15:01Z] WARN: Rate limit exceeded for IP 192.168.1.8, user 2048",
            "Structured log line",
        ),
        (
            "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8",
            "Binary sidechannel wrapper",
        ),
    ]

    for payload, description in samples:
        compressed, method, metadata = compressor.compress(payload)
        round_trip = compressor.decompress(compressed)

        assert round_trip == payload, f"{description} failed round-trip"
        assert metadata.get("ratio") is not None
        assert method in {
            CompressionMethod.BINARY_SEMANTIC,
            CompressionMethod.AURALITE,
            CompressionMethod.PATTERN_SEMANTIC,
            CompressionMethod.BRIO,
            CompressionMethod.UNCOMPRESSED,
        }, f"Unexpected method for {description}"
