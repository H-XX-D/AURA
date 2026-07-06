from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from aura_compression.aiwire_replay_log import (
    AIWIRE_REPLAY_LOG_SCHEMA,
    build_replay_records,
    dumps_replay_log,
    loads_replay_log,
    sha256_hex,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_CORPUS = "fixtures/aiwire_sessions/public_session_corpus_v1.json"


def _network_suite_payload() -> dict[str, object]:
    return {
        "suite": "aura-aiwire-realistic-network",
        "seconds": 5.0,
        "exchanges": 20,
        "agent_count": 4,
        "codecs": ["raw", "aiwire"],
        "requested_backend": "native",
        "coordinator": "asyncio",
        "fixture_corpus": FIXTURE_CORPUS,
        "fixture_session_templates": "updated",
        "fixture_variation_profile": "cluster",
        "profiles": [{"name": "lan_10m", "rtt_ms": 4.0}],
        "results": [
            {
                "network_profile": "lan_10m",
                "codec": "raw",
                "backend": "raw",
                "verified": True,
                "exchanges": 20,
                "deadline_completed_exchanges": 20,
                "deadline_exchanges_per_second": 10.0,
                "framed_wire_bytes": 40000,
                "framed_bytes_per_exchange": 2000.0,
                "roundtrip_ms_p95": 12.0,
            },
            {
                "network_profile": "lan_10m",
                "codec": "aiwire",
                "backend": "native",
                "verified": True,
                "exchanges": 20,
                "deadline_completed_exchanges": 20,
                "deadline_exchanges_per_second": 30.0,
                "framed_wire_bytes": 8000,
                "framed_bytes_per_exchange": 400.0,
                "roundtrip_ms_p95": 4.0,
            },
        ],
    }


def _nary_payload() -> dict[str, object]:
    return {
        "mode": "nary_client",
        "coordinator": "asyncio",
        "participant_count": 3,
        "remote_peer_count": 2,
        "session_shards_per_target": 1,
        "total_replay_sessions": 2,
        "requested_backend": "native",
        "targets": [
            {"index": 1, "label": "nano-a"},
            {"index": 2, "label": "nano-b"},
        ],
        "fixture_replay": {
            "fixture_schema": "aura.aiwire.session_fixture.v1",
            "fixture_session_template_count": 8,
            "fixture_request_sha256": "a" * 64,
            "fixture_response_sha256": "b" * 64,
        },
        "nary_negotiation": {
            "accepted": True,
            "codec": "aiwire",
            "version": 1,
        },
        "nary_peer_probes": [
            {"target_label": "nano-a", "verified": True},
            {"target_label": "nano-b", "verified": True},
        ],
        "aggregate": [
            {
                "codec": "aiwire",
                "deadline_completed_exchanges": 40,
                "deadline_exchanges_per_second": 20.0,
                "verified": True,
            }
        ],
        "results": [
            {
                "target_label": "nano-a",
                "target_index": 1,
                "codec": "aiwire",
                "backend": "native",
                "verified": True,
                "deadline_completed_exchanges": 20,
            },
            {
                "target_label": "nano-b",
                "target_index": 2,
                "codec": "aiwire",
                "backend": "native",
                "verified": True,
                "deadline_completed_exchanges": 20,
            },
        ],
    }


def test_replay_log_records_network_suite_results() -> None:
    source_bytes = json.dumps(
        _network_suite_payload(),
        sort_keys=True,
    ).encode()
    records = build_replay_records(
        _network_suite_payload(),
        source="/tmp/aura_network.json",
        source_sha256=sha256_hex(source_bytes),
    )

    assert [record["record_type"] for record in records] == [
        "header",
        "result",
        "result",
    ]
    assert records[0]["schema"] == AIWIRE_REPLAY_LOG_SCHEMA
    assert records[0]["payload"]["input_kind"] == "network_suite"
    assert records[0]["payload"]["settings"]["profiles"] == ["lan_10m"]
    assert records[1]["payload"]["summary"]["codec"] == "raw"
    assert records[2]["payload"]["summary"]["backend"] == "native"

    rendered = dumps_replay_log(_network_suite_payload())
    loaded = loads_replay_log(rendered)
    expected = build_replay_records(_network_suite_payload())
    assert loaded == expected


def test_replay_log_records_nary_handshake_and_targets() -> None:
    records = build_replay_records(_nary_payload())
    record_types = [record["record_type"] for record in records]

    assert record_types == [
        "header",
        "fixture_replay",
        "nary_negotiation",
        "target",
        "target",
        "peer_probe",
        "peer_probe",
        "aggregate_result",
        "result",
        "result",
    ]
    assert records[0]["payload"]["input_kind"] == "nary_client"
    assert records[2]["payload"]["accepted"] is True
    assert records[3]["payload"]["label"] == "nano-a"
    assert records[7]["payload"]["codec"] == "aiwire"


def test_replay_log_loader_rejects_payload_hash_mismatch() -> None:
    rendered = dumps_replay_log(_network_suite_payload())
    first, *rest = rendered.splitlines()
    record = json.loads(first)
    record["payload"]["counts"]["results"] = 99
    corrupted = "\n".join([json.dumps(record, sort_keys=True), *rest]) + "\n"

    try:
        loads_replay_log(corrupted)
    except ValueError as exc:
        assert "payload hash mismatch" in str(exc)
    else:  # pragma: no cover - defensive assertion.
        raise AssertionError("corrupted replay log was accepted")


def test_replay_log_loader_ignores_blank_lines() -> None:
    rendered = "\n" + dumps_replay_log(_network_suite_payload()) + "\n"

    loaded = loads_replay_log(rendered)
    expected = build_replay_records(_network_suite_payload())
    assert loaded == expected


def test_replay_log_cli_writes_jsonl(tmp_path: Path) -> None:
    input_path = tmp_path / "benchmark.json"
    output_path = tmp_path / "benchmark.jsonl"
    input_path.write_text(json.dumps(_network_suite_payload(), sort_keys=True))

    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "write_aiwire_replay_log.py"),
            str(input_path),
            "--output",
            str(output_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert output_path.read_text() == completed.stdout
    records = loads_replay_log(output_path.read_text())
    assert records[0]["payload"]["source"] == str(input_path)
    source_sha256 = sha256_hex(input_path.read_bytes())
    assert records[0]["payload"]["source_sha256"] == source_sha256
