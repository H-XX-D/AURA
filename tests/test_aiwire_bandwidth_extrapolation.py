from __future__ import annotations

import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from extrapolate_aiwire_bandwidth import extrapolate_rows  # noqa: E402


def _benchmark() -> dict[str, object]:
    return {
        "results": [
            {
                "network_profile": "lab",
                "codec": "raw",
                "backend": "raw",
                "exchanges": 100,
                "framed_request_wire_bytes": 40000,
                "framed_response_wire_bytes": 60000,
                "framed_bytes_per_exchange": 1000.0,
                "raw_bytes": 100000,
                "roundtrip_ms_p95": 30.0,
                "client_link_mbps": 1.0,
                "server_link_mbps": 1.0,
                "profile_rtt_ms": 10.0,
                "profile_pipeline_window": 4,
            },
            {
                "network_profile": "lab",
                "codec": "aiwire",
                "backend": "native",
                "exchanges": 100,
                "framed_request_wire_bytes": 10000,
                "framed_response_wire_bytes": 15000,
                "framed_bytes_per_exchange": 250.0,
                "raw_bytes": 100000,
                "roundtrip_ms_p95": 20.0,
                "client_link_mbps": 1.0,
                "server_link_mbps": 1.0,
                "profile_rtt_ms": 10.0,
                "profile_pipeline_window": 4,
            },
        ]
    }


def test_extrapolate_rows_scales_capacity_with_bandwidth() -> None:
    rows = extrapolate_rows(_benchmark(), bandwidth_mbps=(1.0, 10.0))
    raw_1 = next(row for row in rows if row["codec"] == "raw" and row["uplink_mbps"] == 1.0)
    raw_10 = next(row for row in rows if row["codec"] == "raw" and row["uplink_mbps"] == 10.0)
    aiwire_1 = next(row for row in rows if row["codec"] == "aiwire" and row["uplink_mbps"] == 1.0)

    assert raw_10["capacity_exchanges_per_second"] == raw_1["capacity_exchanges_per_second"] * 10
    assert aiwire_1["capacity_gain_vs_raw"] == 4.0
    assert aiwire_1["semantic_mib_per_second"] > raw_1["semantic_mib_per_second"]
    assert aiwire_1["raw_required_total_mbps"] > raw_1["raw_required_total_mbps"]


def test_extrapolate_rows_projects_latency_and_effective_capacity() -> None:
    rows = extrapolate_rows(_benchmark(), bandwidth_mbps=(1.0, 10.0))
    raw_1 = next(row for row in rows if row["codec"] == "raw" and row["uplink_mbps"] == 1.0)
    raw_10 = next(row for row in rows if row["codec"] == "raw" and row["uplink_mbps"] == 10.0)

    assert raw_10["projected_p95_ms"] < raw_1["projected_p95_ms"]
    assert raw_1["effective_capacity_exchanges_per_second"] < raw_1["capacity_exchanges_per_second"]
    assert raw_1["effective_semantic_mib_per_second"] < raw_1["semantic_mib_per_second"]


def test_extrapolate_rows_projects_concurrent_agents_to_fill_bandwidth() -> None:
    rows = extrapolate_rows(
        _benchmark(),
        bandwidth_mbps=(10.0,),
        agent_counts=(1, 4, 32),
        per_agent_window=1,
    )
    aiwire_1 = next(row for row in rows if row["codec"] == "aiwire" and row["agent_count"] == 1)
    aiwire_32 = next(row for row in rows if row["codec"] == "aiwire" and row["agent_count"] == 32)

    assert (
        aiwire_32["effective_capacity_exchanges_per_second"]
        > aiwire_1["effective_capacity_exchanges_per_second"]
    )
    assert aiwire_32["bandwidth_fill_percent"] > aiwire_1["bandwidth_fill_percent"]
    assert aiwire_1["required_inflight_window"] > aiwire_1["aggregate_inflight_window"]
    assert aiwire_1["required_agent_count"] == aiwire_1["required_inflight_window"]


def test_extrapolate_rows_uses_asymmetric_downlink_multiplier() -> None:
    rows = extrapolate_rows(_benchmark(), bandwidth_mbps=(1.0,), downlink_multiplier=4.0)
    raw = next(row for row in rows if row["codec"] == "raw")

    assert raw["downlink_mbps"] == 4.0
    assert raw["bottleneck_direction"] == "uplink"
