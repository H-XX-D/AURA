#!/usr/bin/env python3
"""Focused tests around the large-file CLI utilities."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aura_compression.cli.aiwire_compatibility import main as compatibility_main
from aura_compression.cli.aiwire_resume_cache import main as resume_cache_main
from aura_compression.cli.benchmark import main as benchmark_main
from aura_compression.cli.compress import main as cli_compress_main
from aura_compression.cli.decompress import main as cli_decompress_main
from aura_compression.cli.proxy import _resume_config
from aura_compression.cli.proxy import build_parser as proxy_build_parser
from aura_compression.cli.server import main as server_main
from tools.compress_large_file import (
    _output_stats,
    _parse_chunk_size,
    _render_stats,
    _resolve_progress_mode,
    compress_path,
    inspect_container,
)


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
    assert output["benchmark_profile"] == "custom"
    assert output["corpus"] == "structured"
    assert output["requested_backend"] == "python"
    assert output["encode_backend"] == "python"
    assert output["decode_backend"] == "python"
    assert output["ratio"] > 0
    assert output["encode_stats"]["frames"] == 8
    assert output["encode_stats"]["bytes_in"] == output["bytes_in"]
    assert output["encode_stats"]["bytes_out"] == output["bytes_out"]
    assert output["encode_stats"]["ratio"] == output["ratio"]
    assert output["decode_stats"]["frames"] == 8
    assert output["decode_stats"]["bytes_out"] == output["decode_bytes_out"]
    assert output["corpus_summary"]["message_count"] == 8
    assert output["corpus_summary"]["total_bytes"] == output["bytes_in"]
    assert output["corpus_summary"]["protocol_mix"]
    assert output["corpus_summary"]["top_level_key_counts"]["corpus_metadata"] == 8
    assert len(output["corpus_summary"]["corpus_sha256"]) == 64


def test_package_cli_benchmark_supports_delta_profile(capsys):
    assert benchmark_main(["--profile", "small", "--corpus", "delta"]) == 0
    output = json.loads(capsys.readouterr().out)

    assert output["benchmark_profile"] == "small"
    assert output["corpus"] == "delta"
    assert output["messages"] == 128
    assert output["corpus_summary"]["message_count"] == 128
    assert output["corpus_summary"]["delta_changed_value_mix"]["status"] > 0


def test_package_cli_benchmark_supports_sustained_session_mode(capsys):
    assert (
        benchmark_main(
            [
                "--profile",
                "small",
                "--corpus",
                "delta",
                "--messages",
                "16",
                "--sustained-session",
                "--peers",
                "3",
            ]
        )
        == 0
    )
    output = json.loads(capsys.readouterr().out)

    assert output["benchmark_mode"] == "sustained_session"
    assert output["session_model"]["participant_count"] == 3
    assert output["session_model"]["setup_frame_count"] == 4
    assert output["session_model"]["steady_state_messages"] == 16


def test_package_cli_benchmark_supports_bursty_profile(capsys):
    assert benchmark_main(["--profile", "bursty", "--messages", "32"]) == 0
    output = json.loads(capsys.readouterr().out)
    summary = output["corpus_summary"]

    assert output["benchmark_profile"] == "bursty"
    assert output["messages"] == 32
    assert summary["top_level_key_counts"]["benchmark_profile"] == 32
    assert summary["top_level_key_counts"]["burst_payload"] > 0
    assert summary["max_frame_bytes"] > summary["min_frame_bytes"] * 3


def test_package_cli_aiwire_compatibility_manifest_and_check(tmp_path: Path):
    templates = tmp_path / "templates.json"
    dictionary_extension = tmp_path / "tenant-alpha.dict"
    manifest = tmp_path / "manifest.json"
    check = tmp_path / "check.json"
    templates.write_text(json.dumps({"128": "agent {0} calls tool {1}"}), encoding="utf-8")
    dictionary_extension.write_bytes(b'"tenant_private_route":"alpha"')

    assert (
        compatibility_main(
            [
                "--session-templates",
                str(templates),
                "--session-template-epoch",
                "1",
                "--dictionary-extension",
                str(dictionary_extension),
                "--output",
                str(manifest),
            ]
        )
        == 0
    )
    manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert manifest_payload["schema"] == "aura.aiwire.compatibility_manifest.v1"
    assert len(manifest_payload["manifest_sha256"]) == 64
    assert manifest_payload["dictionary_extension_count"] == 1
    assert manifest_payload["dictionary_extensions"][0]["name"] == "tenant-alpha.dict"
    assert "tenant_private_route" not in manifest.read_text(encoding="utf-8")

    assert (
        compatibility_main(
            [
                "--session-templates",
                str(templates),
                "--session-template-epoch",
                "1",
                "--dictionary-extension",
                str(dictionary_extension),
                "--peer-manifest",
                str(manifest),
                "--output",
                str(check),
            ]
        )
        == 0
    )
    check_payload = json.loads(check.read_text(encoding="utf-8"))
    assert check_payload["accepted"] is True
    assert check_payload["codec"] == "aiwire"
    assert check_payload["reason"] is None


def test_package_cli_aiwire_resume_cache_round_trip(tmp_path: Path):
    cache = tmp_path / "resume-cache.json"
    templates = tmp_path / "templates.json"
    listed = tmp_path / "list.json"
    hello = tmp_path / "hello.json"
    response = tmp_path / "response.json"
    verified = tmp_path / "verified.json"
    templates.write_text(
        json.dumps({"128": "agent {0} calls tool {1}", "129": "task {0} status {1}"}),
        encoding="utf-8",
    )

    assert (
        resume_cache_main(
            [
                "--cache",
                str(cache),
                "put",
                "--peer-id",
                "nano-engineer",
                "--app-namespace",
                "aura-cluster",
                "--session-templates",
                str(templates),
                "--epoch",
                "2",
                "--label",
                "z6-nano",
            ]
        )
        == 0
    )
    assert (
        resume_cache_main(
            ["--cache", str(cache), "list", "--peer-id", "nano-engineer", "--output", str(listed)]
        )
        == 0
    )
    list_payload = json.loads(listed.read_text(encoding="utf-8"))
    assert list_payload["entries"][0]["session_template_count"] == 2

    assert (
        resume_cache_main(
            [
                "--cache",
                str(cache),
                "hello",
                "--peer-id",
                "nano-engineer",
                "--app-namespace",
                "aura-cluster",
                "--nonce",
                "1" * 32,
                "--output",
                str(hello),
            ]
        )
        == 0
    )
    assert (
        resume_cache_main(
            [
                "--cache",
                str(cache),
                "negotiate",
                "--hello",
                str(hello),
                "--nonce",
                "2" * 32,
                "--output",
                str(response),
            ]
        )
        == 0
    )
    assert (
        resume_cache_main(
            [
                "--cache",
                str(cache),
                "verify",
                "--hello",
                str(hello),
                "--response",
                str(response),
                "--output",
                str(verified),
            ]
        )
        == 0
    )
    verify_payload = json.loads(verified.read_text(encoding="utf-8"))
    assert verify_payload["accepted"] is True
    assert verify_payload["entry"]["peer_id"] == "nano-engineer"


def test_package_cli_proxy_resume_flags_parse(tmp_path: Path):
    cache = tmp_path / "proxy-resume.json"
    auth_key = tmp_path / "resume.key"
    auth_key.write_text("shared-proxy-resume-key\n", encoding="utf-8")
    parser = proxy_build_parser()
    args = parser.parse_args(
        [
            "ingress",
            "--listen-port",
            "9101",
            "--egress-host",
            "127.0.0.1",
            "--egress-port",
            "9102",
            "--backend",
            "python",
            "--resume-cache",
            str(cache),
            "--resume-peer-id",
            "z6-to-nano",
            "--resume-app-namespace",
            "aura-cluster",
            "--resume-auth-key-file",
            str(auth_key),
            "--require-resume",
        ]
    )
    config = _resume_config(args, parser)

    assert config is not None
    assert config.cache_path == cache
    assert config.peer_id == "z6-to-nano"
    assert config.app_namespace == "aura-cluster"
    assert config.require_resume is True
    assert config.auth_key == b"shared-proxy-resume-key"


def test_package_cli_server_guidance(capsys):
    assert server_main([]) == 0
    assert "transport examples" in capsys.readouterr().out
