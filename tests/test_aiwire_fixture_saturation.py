from __future__ import annotations

import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from aiwire_network_profiles import resolve_network_profiles  # noqa: E402
from benchmark_aiwire_fixture_saturation import (  # noqa: E402
    build_fixture_saturation_report,
    measure_fixture_codecs,
    render_markdown,
    saturation_rows,
)

from aura_compression.ai_wire_fixtures import load_aiwire_session_fixture_corpus  # noqa: E402

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "aiwire_sessions"
    / "public_session_corpus_v1.json"
)


def test_fixture_saturation_measures_codec_bytes_against_saved_corpus() -> None:
    corpus = load_aiwire_session_fixture_corpus(FIXTURE_PATH)
    rows = measure_fixture_codecs(
        corpus,
        codecs=("raw", "zlib", "aiwire", "aitoken_aiwire"),
        backend="python",
    )
    by_codec = {row["codec"]: row for row in rows}

    assert by_codec["raw"]["exchanges"] == 36
    assert by_codec["aiwire"]["verified"] is True
    assert by_codec["aitoken_aiwire"]["verified"] is True
    assert (
        by_codec["zlib"]["framed_bytes_per_exchange"] < by_codec["raw"]["framed_bytes_per_exchange"]
    )
    assert (
        by_codec["aiwire"]["framed_bytes_per_exchange"]
        < by_codec["zlib"]["framed_bytes_per_exchange"]
    )
    assert (
        by_codec["aitoken_aiwire"]["framed_bytes_per_exchange"]
        < by_codec["zlib"]["framed_bytes_per_exchange"]
    )
    assert by_codec["aiwire"]["side_channel_framed_bytes"] > 0
    assert by_codec["raw"]["side_channel_framed_bytes"] == 0


def test_fixture_saturation_projects_agents_needed_to_fill_bandwidth() -> None:
    corpus = load_aiwire_session_fixture_corpus(FIXTURE_PATH)
    measurements = measure_fixture_codecs(
        corpus,
        codecs=("raw", "aiwire"),
        backend="python",
    )
    rows = saturation_rows(
        measurements,
        profiles=resolve_network_profiles("lan_10m"),
        agent_counts=(1, 64),
        per_agent_window=1,
    )

    raw_64 = next(row for row in rows if row["codec"] == "raw" and row["agent_count"] == 64)
    aiwire_1 = next(row for row in rows if row["codec"] == "aiwire" and row["agent_count"] == 1)
    aiwire_64 = next(row for row in rows if row["codec"] == "aiwire" and row["agent_count"] == 64)

    assert aiwire_1["limiting_factor"] == "latency_window"
    assert aiwire_1["bandwidth_fill_percent"] < 10.0
    assert aiwire_64["limiting_factor"] != "latency_window"
    assert aiwire_64["bandwidth_fill_percent"] > aiwire_1["bandwidth_fill_percent"]
    assert aiwire_64["bandwidth_fill_percent"] >= 80.0
    assert aiwire_64["required_agent_count"] > raw_64["required_agent_count"]
    assert (
        aiwire_64["effective_capacity_exchanges_per_second"]
        > raw_64["effective_capacity_exchanges_per_second"]
    )
    assert aiwire_64["effective_messages_per_second"] == (
        aiwire_64["effective_capacity_exchanges_per_second"] * 2
    )


def test_fixture_saturation_report_and_markdown_are_consistent() -> None:
    report = build_fixture_saturation_report(
        fixture_path=FIXTURE_PATH,
        profiles="lan_10m",
        codecs=("raw", "aiwire"),
        agent_counts=(1, 64),
        per_agent_window=1,
        backend="python",
    )
    markdown = render_markdown(report)

    assert report["suite"] == "aura-aiwire-fixture-saturation"
    assert report["exchanges"] == 36
    assert len(report["results"]) == 4
    assert "AIWire Fixture Bandwidth Saturation" in markdown
    assert "Need agents" in markdown
    assert "Raw Mbps equiv" in markdown
