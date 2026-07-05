"""CI-friendly AIWire benchmark smoke tests."""

from __future__ import annotations

import pytest

from aura_compression.ai_wire import aiwire_native_status
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


def test_aiwire_benchmark_sustained_session_reports_delta_steady_state() -> None:
    result = run_benchmark(
        profile="small",
        corpus="delta",
        messages=64,
        seed=1729,
        level=3,
        sustained_session=True,
        peers=4,
    )
    session_model = result["session_model"]

    assert result["benchmark_mode"] == "sustained_session"
    assert session_model["mode"] == "sustained_delta_after_handshake"
    assert session_model["participant_count"] == 4
    assert session_model["remote_peer_count"] == 3
    assert session_model["setup_frame_count"] == 5
    assert session_model["template_count"] > 0
    assert len(session_model["session_template_sha256"]) == 64
    assert session_model["steady_state_messages"] == 64
    assert session_model["steady_state_raw_delta_bytes"] == result["bytes_in"]
    assert session_model["steady_state_wire_delta_bytes"] == result["bytes_out"]
    assert session_model["total_wire_bytes_with_setup"] > result["bytes_out"]
    assert session_model["steady_state_ratio"] == result["ratio"]
    assert session_model["amortized_wire_bytes_per_message"] > (
        session_model["steady_state_wire_bytes_per_message"]
    )
    assert session_model["setup_share_percent"] > 0


def test_aiwire_benchmark_sustained_session_requires_delta_corpus() -> None:
    with pytest.raises(ValueError, match="requires corpus='delta'"):
        run_benchmark(corpus="structured", sustained_session=True)


def test_aiwire_benchmark_rejects_invalid_peer_count() -> None:
    with pytest.raises(ValueError, match="peers must be at least 2"):
        run_benchmark(corpus="delta", sustained_session=True, peers=1)


def test_aiwire_benchmark_reports_python_backend_by_default() -> None:
    result = run_benchmark(messages=8)

    assert result["requested_backend"] == "python"
    assert result["encode_backend"] == "python"
    assert result["decode_backend"] == "python"
    assert "available" in result["native_status"]
    assert "library_path" not in result["native_status"]


def test_aiwire_benchmark_rejects_invalid_backend() -> None:
    with pytest.raises(ValueError, match="unsupported benchmark backend"):
        run_benchmark(messages=1, backend="gpu")  # type: ignore[arg-type]


def test_aiwire_benchmark_native_backend_when_available() -> None:
    status = aiwire_native_status()
    if not status.available:
        pytest.skip(status.error or "native AIWire backend is not built")

    result = run_benchmark(
        profile="small",
        corpus="delta",
        messages=32,
        seed=1729,
        level=3,
        backend="native",
    )

    assert result["requested_backend"] == "native"
    assert result["encode_backend"] == "native"
    assert result["decode_backend"] == "native"
    assert result["native_status"]["dictionary_matches_python"] is True
    assert result["ratio"] > 8.0
