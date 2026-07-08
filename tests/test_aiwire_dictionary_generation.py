from __future__ import annotations

import json
from pathlib import Path

from aura_compression.ai_wire import AI_WIRE_DICTIONARY_SHA256
from aura_compression.aiwire_dictionary_generation import (
    AIWIRE_DICTIONARY_CANDIDATES_SCHEMA,
    build_aiwire_candidate_dictionary_bytes,
    build_aiwire_dictionary_candidate_report,
    discover_aiwire_dictionary_candidates,
    write_aiwire_candidate_dictionary,
    write_aiwire_dictionary_candidate_report,
)
from aura_compression.cli.aiwire_dictionary_generate import main as dictionary_generate_main

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "aiwire_sessions"
    / "public_session_corpus_v1.json"
)


def _candidate_terms(report: dict[str, object]) -> set[str]:
    return {
        str(candidate["term"])
        for candidate in report["candidate_terms"]  # type: ignore[index]
        if isinstance(candidate, dict)
    }


def test_dictionary_candidate_report_is_deterministic() -> None:
    first = build_aiwire_dictionary_candidate_report(
        fixture_corpus=FIXTURE_PATH,
        max_entries=24,
    )
    second = build_aiwire_dictionary_candidate_report(
        fixture_corpus=FIXTURE_PATH,
        max_entries=24,
    )

    assert first == second
    assert first["schema"] == AIWIRE_DICTIONARY_CANDIDATES_SCHEMA
    baseline = first["baseline_static_dictionary"]  # type: ignore[index]
    assert baseline["sha256"] == AI_WIRE_DICTIONARY_SHA256
    assert first["source"]["message_count"] == 72  # type: ignore[index]
    assert first["candidate_count"] == 24
    assert first["candidate_dictionary"]["bytes"] > 0  # type: ignore[index]
    assert len(str(first["candidate_dictionary"]["sha256"])) == 64  # type: ignore[index]


def test_dictionary_candidates_include_protocol_and_fixture_terms() -> None:
    report = build_aiwire_dictionary_candidate_report(
        fixture_corpus=FIXTURE_PATH,
        max_entries=128,
    )
    terms = _candidate_terms(report)

    assert '"protocol":' in terms
    assert '"fixture_metadata":' in terms
    assert '"protocol":"openai.responses"' in terms
    assert any(term.startswith('"schema":"local.agent.') for term in terms)

    first_candidate = report["candidate_terms"][0]  # type: ignore[index]
    assert first_candidate["estimated_saved_bytes"] > 0
    assert first_candidate["occurrences"] >= 2
    assert isinstance(first_candidate["in_static_dictionary"], bool)


def test_candidate_dictionary_bytes_are_stable_and_bounded() -> None:
    candidates = discover_aiwire_dictionary_candidates(
        [
            {"protocol": "mcp", "method": "tools/call", "params": {"name": "shell"}},
            {"protocol": "mcp", "method": "tools/call", "params": {"name": "read"}},
        ],
        max_entries=8,
    )

    dictionary = build_aiwire_candidate_dictionary_bytes(candidates, max_bytes=64)

    assert 0 < len(dictionary) <= 64
    assert dictionary == build_aiwire_candidate_dictionary_bytes(candidates, max_bytes=64)
    assert b'"protocol":"mcp"' in dictionary


def test_dictionary_candidate_report_and_dictionary_writers(tmp_path: Path) -> None:
    report = build_aiwire_dictionary_candidate_report(
        fixture_corpus=FIXTURE_PATH,
        max_entries=16,
    )
    report_path = tmp_path / "report.json"
    dictionary_path = tmp_path / "candidate.dict"

    write_aiwire_dictionary_candidate_report(report_path, report)
    write_aiwire_candidate_dictionary(dictionary_path, report)

    saved = json.loads(report_path.read_text(encoding="utf-8"))
    assert saved == report
    assert dictionary_path.stat().st_size == report["candidate_dictionary"]["bytes"]


def test_package_cli_aiwire_dictionary_generate(tmp_path: Path) -> None:
    report_path = tmp_path / "dictionary-candidates.json"
    dictionary_path = tmp_path / "candidate.dict"

    assert (
        dictionary_generate_main(
            [
                "--fixture-corpus",
                str(FIXTURE_PATH),
                "--max-entries",
                "12",
                "--output",
                str(report_path),
                "--dictionary-output",
                str(dictionary_path),
            ]
        )
        == 0
    )

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["schema"] == AIWIRE_DICTIONARY_CANDIDATES_SCHEMA
    assert payload["candidate_count"] == 12
    assert payload["dictionary_output"] == str(dictionary_path)
    assert dictionary_path.stat().st_size == payload["candidate_dictionary"]["bytes"]
