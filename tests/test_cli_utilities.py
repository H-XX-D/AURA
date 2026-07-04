#!/usr/bin/env python3
"""Focused tests around the large-file CLI utilities."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.compress_large_file import (
    _output_stats,
    _parse_chunk_size,
    _render_stats,
    _resolve_progress_mode,
    compress_path,
    inspect_container,
)
from aura_compression.cli.benchmark import main as benchmark_main
from aura_compression.cli.compress import main as cli_compress_main
from aura_compression.cli.decompress import main as cli_decompress_main
from aura_compression.cli.server import main as server_main


@pytest.mark.parametrize(
    "value,expected",
    [
        ("64K", 64 * 1024),
        ("1M", 1024 * 1024),
        ("2m", 2 * 1024 * 1024),
        ("3G", 3 * 1024 * 1024 * 1024),
        ("65536", 65536),
        (131072, 131072),
    ],
)
def test_parse_chunk_size_valid(value, expected):
    assert _parse_chunk_size(value) == expected


@pytest.mark.parametrize("value", ["0", "-1", "abc", "10XB"])
def test_parse_chunk_size_invalid(value):
    with pytest.raises(Exception):
        _parse_chunk_size(value)


def test_resolve_progress_mode_auto(monkeypatch):
    assert _resolve_progress_mode("auto", True) == "bar"
    assert _resolve_progress_mode("auto", False) == "none"
    assert _resolve_progress_mode("percent", False) == "percent"
    with pytest.raises(ValueError):
        _resolve_progress_mode("verbose", True)


def test_render_and_output_stats(tmp_path: Path):
    stats = {"input_size": 1024, "compression_ratio": 3.5}
    rendered = _render_stats(stats, fmt="table")
    assert "input_size" in rendered
    stats_file = tmp_path / "stats.txt"
    _output_stats(stats, "json", stats_file)
    data = json.loads(stats_file.read_text())
    assert data["input_size"] == 1024


def test_inspect_container_reports_metadata(tmp_path: Path):
    source = tmp_path / "sample.log"
    source.write_text("request=123 status=200\n" * 400, encoding="utf-8")
    compressed = tmp_path / "sample.aura"
    stats = compress_path(
        source,
        compressed,
        chunk_size=_parse_chunk_size("16K"),
        cache_dir=tmp_path / "cache",
        audit_dir=tmp_path / "audit",
        sync_every=1,
        show_progress=False,
        progress_mode="none",
    )
    assert stats["chunks"] > 0

    info = inspect_container(compressed, max_chunks=2)
    assert info["path"].endswith("sample.aura")
    assert info["chunk_count"] == stats["chunks"]
    assert info["method_counts"]
    assert isinstance(info["sample_chunks"], list)
    assert info["sample_chunks"][0]["index"] == 0


def test_package_cli_round_trip(tmp_path: Path):
    source = tmp_path / "message.json"
    frame = tmp_path / "message.aiwire"
    restored = tmp_path / "restored.json"
    payload = b'{"jsonrpc":"2.0","method":"tools/call","protocol":"mcp"}'
    source.write_bytes(payload)

    assert cli_compress_main([str(source), "--output", str(frame)]) == 0
    assert frame.stat().st_size > 0
    assert cli_decompress_main([str(frame), "--output", str(restored)]) == 0
    assert restored.read_bytes() == payload


def test_package_cli_benchmark_smoke(capsys):
    assert benchmark_main(["--messages", "8"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["messages"] == 8
    assert output["ratio"] > 0


def test_package_cli_server_guidance(capsys):
    assert server_main([]) == 0
    assert "transport examples" in capsys.readouterr().out
