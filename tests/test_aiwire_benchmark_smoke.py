"""CI-friendly AIWire benchmark smoke tests."""

from __future__ import annotations

import pytest

from aura_compression.cli.benchmark import run_benchmark


@pytest.mark.parametrize(
    "profile,corpus,messages,min_ratio,required_protocol",
    [
        ("small", "structured", None, 5.0, "mcp"),
        ("small", "delta", None, 8.0, "local.agent"),
        ("bursty", "structured", 64, 3.0, "openai.responses"),
    ],
)
def test_aiwire_benchmark_profiles_stay_above_regression_thresholds(
    profile: str,
    corpus: str,
    messages: int | None,
    min_ratio: float,
    required_protocol: str,
) -> None:
    result = run_benchmark(
        profile=profile,
        corpus=corpus,
        messages=messages,
        seed=1729,
        level=3,
    )
    summary = result["corpus_summary"]

    assert result["ratio"] >= min_ratio
    assert result["bytes_out"] < result["bytes_in"]
    assert result["decode_bytes_out"] == result["bytes_in"]
    assert result["encode_stats"]["frames"] == result["messages"]
    assert result["decode_stats"]["frames"] == result["messages"]
    assert result["encode_stats"]["bytes_in"] == summary["total_bytes"] == result["bytes_in"]
    assert summary["message_count"] == result["messages"]
    assert summary["json_message_count"] == result["messages"]
    assert summary["non_json_message_count"] == 0
    assert summary["protocol_mix"][required_protocol] > 0
    assert summary["top_level_key_counts"]["corpus_metadata"] == result["messages"]
    assert summary["nested_key_counts"]["public_safe"] == result["messages"]
    assert len(summary["corpus_sha256"]) == 64

    if profile == "bursty":
        assert summary["top_level_key_counts"]["burst_payload"] > 0
        assert summary["max_frame_bytes"] > summary["min_frame_bytes"] * 3

    if corpus == "delta":
        assert summary["delta_changed_value_mix"]["status"] > 0
        assert summary["delta_changed_value_mix"]["token"] > 0


def test_aiwire_benchmark_rejects_invalid_message_count() -> None:
    with pytest.raises(ValueError, match="messages must be positive"):
        run_benchmark(messages=0)
