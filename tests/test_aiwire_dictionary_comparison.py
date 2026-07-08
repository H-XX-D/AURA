from __future__ import annotations

import json
import sys
from pathlib import Path

from aura_compression.ai_wire import AI_WIRE_DICTIONARY_SHA256
from aura_compression.aiwire_dictionary_comparison import (
    AIWIRE_DICTIONARY_COMPARISON_SCHEMA,
    build_aiwire_dictionary_comparison_report,
    render_aiwire_dictionary_comparison_markdown,
    write_aiwire_dictionary_comparison_markdown,
    write_aiwire_dictionary_comparison_report,
)

TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from compare_aiwire_dictionaries import main as compare_dictionaries_main  # noqa: E402

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "aiwire_sessions"
    / "public_session_corpus_v1.json"
)


def test_dictionary_comparison_report_is_deterministic() -> None:
    first = build_aiwire_dictionary_comparison_report(
        fixture_corpus=FIXTURE_PATH,
        max_entries=32,
    )
    second = build_aiwire_dictionary_comparison_report(
        fixture_corpus=FIXTURE_PATH,
        max_entries=32,
    )

    assert first == second
    assert first["schema"] == AIWIRE_DICTIONARY_COMPARISON_SCHEMA
    assert first["source"]["message_count"] == 72  # type: ignore[index]
    assert first["candidate_report"]["candidate_count"] == 32  # type: ignore[index]

    dictionaries = {row["name"]: row for row in first["dictionaries"]}  # type: ignore[index]
    assert dictionaries["aiwire_v1_static"]["sha256"] == AI_WIRE_DICTIONARY_SHA256
    assert "generated_combined" in dictionaries
    assert any(
        row["kind"] == "generated_protocol_specific"
        for row in first["dictionaries"]  # type: ignore[index]
    )


def test_dictionary_comparison_measurements_round_trip() -> None:
    report = build_aiwire_dictionary_comparison_report(
        fixture_corpus=FIXTURE_PATH,
        max_entries=24,
    )

    measurements = report["measurements"]
    assert measurements
    assert all(row["round_trip_verified"] is True for row in measurements)
    all_scope = [row for row in measurements if row["message_scope"] == "all"]
    assert {row["dictionary"] for row in all_scope} == {
        "no_dictionary",
        "aiwire_v1_static",
        "generated_combined",
    }
    assert all(row["wire_bytes"] > 0 for row in measurements)


def test_dictionary_comparison_markdown_and_writers(tmp_path: Path) -> None:
    report = build_aiwire_dictionary_comparison_report(
        fixture_corpus=FIXTURE_PATH,
        max_entries=16,
    )
    markdown = render_aiwire_dictionary_comparison_markdown(report)

    assert "AIWire Dictionary Comparison Matrix" in markdown
    assert "generated_combined" in markdown
    assert "current_compatible" in markdown

    json_path = tmp_path / "dictionary-comparison.json"
    markdown_path = tmp_path / "dictionary-comparison.md"
    write_aiwire_dictionary_comparison_report(json_path, report)
    write_aiwire_dictionary_comparison_markdown(markdown_path, report)

    assert json.loads(json_path.read_text(encoding="utf-8")) == report
    assert markdown_path.read_text(encoding="utf-8") == markdown


def test_compare_aiwire_dictionaries_tool_writes_outputs(tmp_path: Path) -> None:
    json_path = tmp_path / "report.json"
    markdown_path = tmp_path / "report.md"

    assert (
        compare_dictionaries_main(
            [
                "--fixture-corpus",
                str(FIXTURE_PATH),
                "--max-entries",
                "12",
                "--json-output",
                str(json_path),
                "--markdown-output",
                str(markdown_path),
            ]
        )
        == 0
    )

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["schema"] == AIWIRE_DICTIONARY_COMPARISON_SCHEMA
    assert payload["candidate_report"]["candidate_count"] == 12
    assert "AIWire Dictionary Comparison Matrix" in markdown_path.read_text(encoding="utf-8")
