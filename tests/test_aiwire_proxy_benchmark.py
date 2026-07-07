from __future__ import annotations

import json
import plistlib
import queue
import socket
import threading
from pathlib import Path
from typing import TypeVar

from aura_compression.ai_wire_fixtures import load_aiwire_session_fixture_corpus
from aura_compression.aiwire_proxy import run_egress_proxy
from aura_compression.aiwire_proxy_benchmark import (
    AIWIRE_PROXY_BENCHMARK_SCHEMA,
    AIWIRE_PROXY_FIXTURE_SERVER_SCHEMA,
    DEFAULT_PROXY_FIXTURE_PATH,
    build_proxy_fixture_pairs,
    run_proxy_benchmark,
    run_proxy_fixture_server,
    run_proxy_ingress_benchmark,
)
from aura_compression.aiwire_replay_log import loads_replay_log
from aura_compression.cli.proxy_benchmark import main as proxy_benchmark_main
from aura_compression.cli.proxy_fixture_server import build_parser as build_fixture_server_parser

ROOT = Path(__file__).resolve().parents[1]
HOST = "127.0.0.1"
T = TypeVar("T")


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((HOST, 0))
        return int(sock.getsockname()[1])


def _run_background(fn):
    results: "queue.Queue[T | BaseException]" = queue.Queue()

    def target() -> None:
        try:
            results.put(fn())
        except BaseException as exc:  # pragma: no cover - surfaced by caller.
            results.put(exc)

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    return thread, results


def _get_background_result(thread: threading.Thread, results: "queue.Queue[T | BaseException]"):
    thread.join(timeout=10)
    assert not thread.is_alive(), "background worker did not finish"
    result = results.get_nowait()
    if isinstance(result, BaseException):
        raise result
    return result


def test_proxy_fixture_pairs_are_extracted_from_public_corpus() -> None:
    corpus = load_aiwire_session_fixture_corpus(DEFAULT_PROXY_FIXTURE_PATH)
    pairs = build_proxy_fixture_pairs(corpus)

    assert len(pairs) == 36
    assert pairs[0].request
    assert pairs[0].response
    assert pairs[0].session_id.startswith("fixture-session-")


def test_proxy_fixture_pairs_support_cluster_variation() -> None:
    corpus = load_aiwire_session_fixture_corpus(DEFAULT_PROXY_FIXTURE_PATH)
    plain = build_proxy_fixture_pairs(corpus)
    varied = build_proxy_fixture_pairs(
        corpus,
        fixture_variation_profile="cluster",
        fixture_peer_label="edge-1",
    )

    assert len(varied) == len(plain)
    assert varied[0].request != plain[0].request
    assert b'"cluster_context"' in varied[0].request
    assert b'"cluster_peer":"edge-1"' in varied[0].request


def test_proxy_benchmark_round_trips_fixture_pairs(tmp_path: Path) -> None:
    output = tmp_path / "proxy-benchmark.json"
    replay_log = tmp_path / "proxy-benchmark.jsonl"

    result = run_proxy_benchmark(
        seconds=0,
        max_exchanges=6,
        connections=2,
        backend="python",
        output=output,
        replay_log_output=replay_log,
    )

    assert result["schema"] == AIWIRE_PROXY_BENCHMARK_SCHEMA
    assert result["verified"] is True
    assert result["requested_connections"] == 2
    assert result["connections"] == 2
    assert result["exchanges"] == 6
    assert result["tunnel_codec"] == "aiwire"
    assert result["actual_backend"] == "python"
    assert result["fixture_corpus_source"] == "file"
    assert result["raw_framed_bytes"] > result["tunnel_semantic_framed_bytes"]
    assert result["tunnel_saved_percent"] > 0
    assert result["modeled_tunnel_gain_vs_raw"] > 1
    assert result["ingress_metrics"]["negotiation_codec"] == "aiwire"
    assert result["ingress_metrics"]["accepted_connections"] == 2
    assert result["egress_metrics"]["accepted_connections"] == 2
    assert result["upstream"]["accepted_connections"] == 2
    ingress_counts = result["ingress_metrics"]["stage_call_count"]
    egress_counts = result["egress_metrics"]["stage_call_count"]
    assert ingress_counts["request_encode"] == 6
    assert ingress_counts["tunnel_response_read"] == 6
    assert egress_counts["request_decode"] == 6
    assert egress_counts["tunnel_response_write"] == 6
    assert result["ingress_metrics"]["stage_mean_ms"]["request_encode"] >= 0.0
    assert json.loads(output.read_text())["exchanges"] == 6

    records = loads_replay_log(replay_log.read_text())
    assert [record["record_type"] for record in records] == ["header", "result"]
    assert records[1]["payload"]["row"]["exchanges"] == 6
    assert records[1]["payload"]["row"]["codec"] == "aiwire"


def test_proxy_benchmark_supports_inline_fixture_upstream() -> None:
    result = run_proxy_benchmark(
        seconds=0,
        max_exchanges=6,
        connections=2,
        backend="python",
        inline_upstream_fixture=True,
    )

    assert result["verified"] is True
    assert result["inline_upstream_fixture"] is True
    assert result["upstream_mode"] == "inline_fixture"
    assert result["upstream"]["mode"] == "inline_fixture"
    assert result["upstream"]["accepted_connections"] == 2
    assert result["upstream"]["exchanges"] == 6
    assert result["exchanges"] == 6
    egress_counts = result["egress_metrics"]["stage_call_count"]
    assert egress_counts["upstream_response_inline"] == 6
    assert "connect_upstream" not in egress_counts
    assert "upstream_request_write" not in egress_counts
    assert "upstream_response_read" not in egress_counts


def test_proxy_benchmark_supports_raw_and_zlib_tunnel_codecs() -> None:
    for codec in ("raw", "zlib"):
        result = run_proxy_benchmark(
            seconds=0,
            max_exchanges=4,
            connections=2,
            backend="python",
            tunnel_codec=codec,
        )

        assert result["verified"] is True
        assert result["tunnel_codec"] == codec
        assert result["actual_backend"] == codec
        assert result["exchanges"] == 4
        assert result["ingress_metrics"]["negotiation_codec"] == codec
        assert result["egress_metrics"]["negotiation_codec"] == codec
        assert result["ingress_metrics"]["tunnel_codec"] == codec
        assert result["egress_metrics"]["tunnel_codec"] == codec
        assert result["raw_framed_bytes"] > 0
        assert result["tunnel_semantic_framed_bytes"] > 0


def test_proxy_benchmark_records_tunnel_impairment() -> None:
    result = run_proxy_benchmark(
        seconds=0,
        max_exchanges=2,
        connections=1,
        backend="python",
        tunnel_bandwidth_mbps=1000.0,
        tunnel_one_way_delay_ms=0.1,
        tunnel_jitter_ms=0.0,
        impairment_seed=99,
    )

    assert result["verified"] is True
    assert result["exchanges"] == 2
    assert result["tunnel_impairment"] == {
        "bandwidth_mbps": 1000.0,
        "one_way_delay_ms": 0.1,
        "jitter_ms": 0.0,
        "tail_pause_probability": 0.0,
        "tail_pause_ms": 0.0,
        "seed": 99,
    }
    assert result["ingress_metrics"]["tunnel_impairment"] == result["tunnel_impairment"]
    assert result["ingress_metrics"]["tunnel_impairment_wait_seconds"] > 0.0
    assert result["egress_metrics"]["tunnel_impairment_wait_seconds"] > 0.0


def test_proxy_ingress_benchmark_round_trips_remote_egress_shape(tmp_path: Path) -> None:
    upstream_port = _free_port()
    egress_port = _free_port()
    fixture_metrics = tmp_path / "fixture.metrics.json"
    egress_metrics = tmp_path / "egress.metrics.json"
    ingress_metrics = tmp_path / "ingress.metrics.json"

    fixture_ready = threading.Event()
    fixture_thread, fixture_results = _run_background(
        lambda: run_proxy_fixture_server(
            listen_host=HOST,
            listen_port=upstream_port,
            fixture_variation_profile="cluster",
            fixture_peer_label="edge-1",
            max_connections=2,
            metrics_output=fixture_metrics,
            ready_callback=lambda _port: fixture_ready.set(),
        )
    )
    assert fixture_ready.wait(timeout=5)

    egress_ready = threading.Event()
    egress_thread, egress_results = _run_background(
        lambda: run_egress_proxy(
            listen_host=HOST,
            listen_port=egress_port,
            upstream_host=HOST,
            upstream_port=upstream_port,
            backend="python",
            max_connections=2,
            metrics_output=egress_metrics,
            ready_callback=lambda _port: egress_ready.set(),
        )
    )
    assert egress_ready.wait(timeout=5)

    result = run_proxy_ingress_benchmark(
        egress_host=HOST,
        egress_port=egress_port,
        seconds=0,
        max_exchanges=6,
        connections=2,
        backend="python",
        fixture_variation_profile="cluster",
        fixture_peer_label="edge-1",
        ingress_metrics_output=ingress_metrics,
    )

    egress = _get_background_result(egress_thread, egress_results)
    fixture = _get_background_result(fixture_thread, fixture_results)

    assert result["mode"] == "ingress_client"
    assert result["verified"] is True
    assert result["requested_connections"] == 2
    assert result["connections"] == 2
    assert result["exchanges"] == 6
    assert result["fixture_variation_profile"] == "cluster"
    assert result["fixture_peer_label"] == "edge-1"
    assert egress.accepted_connections == 2
    assert egress.exchanges == 6
    assert fixture.accepted_connections == 2
    assert fixture.exchanges == 6
    assert json.loads(fixture_metrics.read_text())["schema"] == AIWIRE_PROXY_FIXTURE_SERVER_SCHEMA
    assert json.loads(ingress_metrics.read_text())["exchanges"] == 6


def test_proxy_benchmark_cli_outputs_json(capsys) -> None:
    assert (
        proxy_benchmark_main(["--seconds", "0", "--max-exchanges", "4", "--connections", "2"]) == 0
    )
    result = json.loads(capsys.readouterr().out)

    assert result["schema"] == AIWIRE_PROXY_BENCHMARK_SCHEMA
    assert result["connections"] == 2
    assert result["exchanges"] == 4
    assert result["verified"] is True


def test_proxy_benchmark_cli_supports_inline_upstream_fixture(capsys) -> None:
    assert (
        proxy_benchmark_main(
            [
                "--seconds",
                "0",
                "--max-exchanges",
                "4",
                "--connections",
                "2",
                "--inline-upstream-fixture",
            ]
        )
        == 0
    )
    result = json.loads(capsys.readouterr().out)

    assert result["inline_upstream_fixture"] is True
    assert result["upstream_mode"] == "inline_fixture"
    assert result["exchanges"] == 4


def test_proxy_fixture_server_cli_parser_accepts_cluster_variation() -> None:
    args = build_fixture_server_parser().parse_args(
        [
            "--fixture-variation-profile",
            "cluster",
            "--fixture-peer-label",
            "edge-1",
        ]
    )

    assert args.fixture_variation_profile == "cluster"
    assert args.fixture_peer_label == "edge-1"


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
