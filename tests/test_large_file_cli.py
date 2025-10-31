#!/usr/bin/env python3
"""Regression tests for the large-file compressor CLI."""

from __future__ import annotations

from pathlib import Path

from tools.compress_large_file import (
    compress_path,
    decompress_path,
    inspect_container,
    verify_container,
)


def test_round_trip_large_file_cli(tmp_path: Path) -> None:
    """Ensure compress + decompress preserves payload and metadata."""
    sample_data = (
        "API REQUEST user=1001 action=login latency=45ms region=us-east device=ios\n"
        "API REQUEST user=1044 action=login latency=47ms region=us-west device=android\n"
    ) * 256

    source = tmp_path / "sample.txt"
    source.write_bytes(sample_data.encode("utf-8"))

    compressed = tmp_path / "sample.aura"
    restored = tmp_path / "restored.txt"
    cache_dir = tmp_path / "cache"
    audit_dir = tmp_path / "audit"

    compress_stats = compress_path(
        source,
        compressed,
        chunk_size=8192,
        cache_dir=cache_dir,
        audit_dir=audit_dir,
        sync_every=2,
        show_progress=False,
        progress_mode="none",
    )
    assert compress_stats["chunks"] > 0
    assert compress_stats["input_size"] == source.stat().st_size

    decompress_stats = decompress_path(
        compressed,
        restored,
        cache_dir=cache_dir,
        audit_dir=audit_dir,
        show_progress=False,
        progress_mode="none",
    )
    assert decompress_stats["chunks"] == compress_stats["chunks"]
    assert restored.read_bytes() == sample_data.encode("utf-8")

    info = inspect_container(compressed, max_chunks=2)
    assert info["chunk_count"] == compress_stats["chunks"]
    assert info["path"].endswith("sample.aura")

    verify_stats = verify_container(
        compressed,
        cache_dir=cache_dir / "verify",
        audit_dir=audit_dir / "verify",
        show_progress=False,
        progress_mode="none",
    )
    assert verify_stats["verified"] is True
    assert verify_stats["output_path"] is None
    assert verify_stats["restored_size"] == compress_stats["input_size"]
