from __future__ import annotations

import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from compare_aiwire_backends import (  # noqa: E402
    SCHEMA,
    render_markdown,
    run_backend_comparison,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "aiwire_sessions"
    / "public_session_corpus_v1.json"
)


def test_backend_comparison_runs_python_backend_on_shared_inputs() -> None:
    report = run_backend_comparison(
        backends=("python",),
        messages=8,
        fixture_path=FIXTURE_PATH,
        fixture_profiles="lan_10m",
        codecs=("raw", "aiwire"),
        agent_counts=(1,),
        allow_missing_native=True,
    )

    assert report["schema"] == SCHEMA
    assert report["ok"] is True
    assert report["completed_backend_count"] == 1
    assert report["settings"]["backends"] == ["python"]
    assert report["deltas"] == []

    backend_result = report["backend_results"][0]
    sustained = backend_result["sustained_summary"]
    fixture = backend_result["fixture_summary"]

    assert backend_result["backend"] == "python"
    assert backend_result["skipped"] is False
    assert sustained["requested_backend"] == "python"
    assert sustained["encode_backend"] == "python"
    assert sustained["decode_backend"] == "python"
    assert sustained["messages"] == 8
    assert sustained["wire_bytes"] < sustained["raw_bytes"]
    assert fixture["codecs"] == ["raw", "aiwire"]
    assert fixture["max_agent_count"] == 1
    assert {row["codec"] for row in fixture["codec_measurements"]} == {
        "raw",
        "aiwire",
    }
    assert backend_result["fixture_saturation"]["suite"] == "aura-aiwire-fixture-saturation"


def test_backend_comparison_allows_missing_native_backend() -> None:
    report = run_backend_comparison(
        backends=("native",),
        messages=4,
        fixture_path=FIXTURE_PATH,
        fixture_profiles="lan_10m",
        codecs=("raw", "aiwire"),
        agent_counts=(1,),
        allow_missing_native=True,
    )

    assert report["schema"] == SCHEMA
    assert report["ok"] is True
    assert len(report["backend_results"]) == 1

    backend_result = report["backend_results"][0]
    assert backend_result["backend"] == "native"
    if backend_result["skipped"]:
        assert backend_result["available"] is False
        assert backend_result["reason"]
        assert report["completed_backend_count"] == 0
    else:
        assert backend_result["available"] is True
        assert backend_result["sustained_summary"]["requested_backend"] == "native"
        assert report["completed_backend_count"] == 1


def test_backend_comparison_markdown_has_summary_tables() -> None:
    report = run_backend_comparison(
        backends=("python",),
        messages=8,
        fixture_path=FIXTURE_PATH,
        fixture_profiles="lan_10m",
        codecs=("raw", "aiwire"),
        agent_counts=(1,),
        allow_missing_native=True,
    )
    markdown = render_markdown(report)

    assert "AIWire Backend Comparison" in markdown
    assert "Sustained Session" in markdown
    assert "Fixture Codec Summary" in markdown
    assert "| python | python/python |" in markdown
    assert "| python | aiwire | python |" in markdown
