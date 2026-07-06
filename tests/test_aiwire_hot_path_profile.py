from __future__ import annotations

import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from profile_aiwire_hot_path import (  # noqa: E402
    SCHEMA,
    profile_aiwire_hot_path,
    render_markdown,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "aiwire_sessions"
    / "public_session_corpus_v1.json"
)


def test_hot_path_profile_reports_sustained_and_fixture_sections() -> None:
    report = profile_aiwire_hot_path(
        mode="both",
        backend="python",
        messages=8,
        fixture_path=FIXTURE_PATH,
        codecs=("raw", "aiwire"),
        top_limit=5,
        allow_missing_native=True,
    )

    assert report["schema"] == SCHEMA
    assert report["ok"] is True
    assert report["settings"]["mode"] == "both"
    assert report["settings"]["backend"] == "python"
    assert "machine" in report["platform"]
    assert [profile["name"] for profile in report["profiles"]] == [
        "sustained_session",
        "fixture_codecs",
    ]

    sustained = report["profiles"][0]
    fixture = report["profiles"][1]
    sustained_summary = sustained["payload"]["summary"]
    fixture_summary = fixture["payload"]["summary"]

    assert sustained["elapsed_ms"] > 0
    assert sustained["total_calls"] > 0
    assert sustained["top_cumulative"]
    assert sustained["top_self_time"]
    assert sustained_summary["wire_bytes"] < sustained_summary["raw_bytes"]
    assert {row["codec"] for row in fixture_summary} == {"raw", "aiwire"}
    assert fixture["top_cumulative"]
    assert fixture["top_self_time"]


def test_hot_path_profile_markdown_renders_tables() -> None:
    report = profile_aiwire_hot_path(
        mode="fixture",
        backend="python",
        messages=4,
        fixture_path=FIXTURE_PATH,
        codecs=("raw", "aiwire"),
        top_limit=3,
        allow_missing_native=True,
    )
    markdown = render_markdown(report)

    assert "AIWire Hot Path Profile" in markdown
    assert "fixture_codecs" in markdown
    assert "Top Cumulative Time" in markdown
    assert "| raw | raw |" in markdown
    assert "| aiwire | python |" in markdown


def test_hot_path_profile_allows_missing_native_backend() -> None:
    report = profile_aiwire_hot_path(
        mode="fixture",
        backend="native",
        messages=4,
        fixture_path=FIXTURE_PATH,
        codecs=("raw", "aiwire"),
        top_limit=3,
        allow_missing_native=True,
    )

    assert report["schema"] == SCHEMA
    if report["skipped"]:
        assert report["ok"] is True
        assert report["profiles"] == []
        assert report["reason"]
    else:
        assert report["ok"] is True
        assert report["profiles"][0]["name"] == "fixture_codecs"
