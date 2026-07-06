from __future__ import annotations

import json
import plistlib
from pathlib import Path

from aura_compression.ai_wire_fixtures import load_aiwire_session_fixture_corpus
from aura_compression.aiwire_proxy_benchmark import (
    AIWIRE_PROXY_BENCHMARK_SCHEMA,
    DEFAULT_PROXY_FIXTURE_PATH,
    build_proxy_fixture_pairs,
    run_proxy_benchmark,
)
from aura_compression.aiwire_replay_log import loads_replay_log
from aura_compression.cli.proxy_benchmark import main as proxy_benchmark_main

ROOT = Path(__file__).resolve().parents[1]


def test_proxy_fixture_pairs_are_extracted_from_public_corpus() -> None:
    corpus = load_aiwire_session_fixture_corpus(DEFAULT_PROXY_FIXTURE_PATH)
    pairs = build_proxy_fixture_pairs(corpus)

    assert len(pairs) == 36
    assert pairs[0].request
    assert pairs[0].response
    assert pairs[0].session_id.startswith("fixture-session-")


def test_proxy_benchmark_round_trips_fixture_pairs(tmp_path: Path) -> None:
    output = tmp_path / "proxy-benchmark.json"
    replay_log = tmp_path / "proxy-benchmark.jsonl"

    result = run_proxy_benchmark(
        seconds=0,
        max_exchanges=6,
        backend="python",
        output=output,
        replay_log_output=replay_log,
    )

    assert result["schema"] == AIWIRE_PROXY_BENCHMARK_SCHEMA
    assert result["verified"] is True
    assert result["exchanges"] == 6
    assert result["actual_backend"] == "python"
    assert result["fixture_corpus_source"] == "file"
    assert result["raw_framed_bytes"] > result["tunnel_semantic_framed_bytes"]
    assert result["tunnel_saved_percent"] > 0
    assert result["modeled_tunnel_gain_vs_raw"] > 1
    assert result["ingress_metrics"]["negotiation_codec"] == "aiwire"
    assert json.loads(output.read_text())["exchanges"] == 6

    records = loads_replay_log(replay_log.read_text())
    assert [record["record_type"] for record in records] == ["header", "result"]
    assert records[1]["payload"]["row"]["exchanges"] == 6


def test_proxy_benchmark_cli_outputs_json(capsys) -> None:
    assert proxy_benchmark_main(["--seconds", "0", "--max-exchanges", "3"]) == 0
    result = json.loads(capsys.readouterr().out)

    assert result["schema"] == AIWIRE_PROXY_BENCHMARK_SCHEMA
    assert result["exchanges"] == 3
    assert result["verified"] is True


def test_proxy_service_templates_reference_explicit_sidecar() -> None:
    systemd_ingress = ROOT / "deploy" / "aura-proxy" / "systemd" / "aura-proxy-ingress.service"
    systemd_egress = ROOT / "deploy" / "aura-proxy" / "systemd" / "aura-proxy-egress.service"
    launchd_ingress = ROOT / "deploy" / "aura-proxy" / "launchd" / "org.aura.proxy.ingress.plist"
    launchd_egress = ROOT / "deploy" / "aura-proxy" / "launchd" / "org.aura.proxy.egress.plist"

    for path in (systemd_ingress, systemd_egress):
        text = path.read_text()
        assert "aura-proxy" in text
        assert "--metrics-output" in text
        assert "transparent" not in text.lower()

    for path in (launchd_ingress, launchd_egress):
        payload = plistlib.loads(path.read_bytes())
        args = payload["ProgramArguments"]
        assert "aura-proxy" in args
        assert "--metrics-output" in args
        assert payload["KeepAlive"] is True
