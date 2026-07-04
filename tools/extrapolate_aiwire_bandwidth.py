#!/usr/bin/env python3
"""Extrapolate AIWire semantic data movement from measured framed bytes."""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any


def _float(value: Any) -> float:
    return float(value or 0.0)


def _int(value: Any) -> int:
    return int(value or 0)


def _fmt(value: float, digits: int = 1) -> str:
    return f"{value:.{digits}f}"


def _split_mbps(value: str) -> tuple[float, ...]:
    return tuple(float(part.strip()) for part in value.split(",") if part.strip())


def _split_ints(value: str) -> tuple[int, ...]:
    return tuple(int(part.strip()) for part in value.split(",") if part.strip())


def _profile(row: dict[str, Any]) -> str:
    return str(row.get("network_profile") or "default")


def _measured(row: dict[str, Any]) -> dict[str, Any]:
    exchanges = max(1, _int(row.get("exchanges")))
    framed_request = _float(row.get("framed_request_wire_bytes"))
    framed_response = _float(row.get("framed_response_wire_bytes"))
    raw_bytes = _float(row.get("raw_bytes"))
    return {
        "profile": _profile(row),
        "codec": str(row.get("codec") or ""),
        "backend": str(row.get("backend") or ""),
        "exchanges": exchanges,
        "request_bpe": _float(row.get("request_framed_bytes_per_exchange"))
        or framed_request / exchanges,
        "response_bpe": _float(row.get("response_framed_bytes_per_exchange"))
        or framed_response / exchanges,
        "framed_bpe": _float(row.get("framed_bytes_per_exchange"))
        or (framed_request + framed_response) / exchanges,
        "raw_bpe": raw_bytes / exchanges,
        "p95_ms": _float(row.get("roundtrip_ms_p95")),
        "profile_rtt_ms": _float(row.get("profile_rtt_ms")),
        "profile_pipeline_window": _int(
            row.get("profile_pipeline_window") or row.get("pipeline_window")
        ),
        "measured_uplink_mbps": _float(row.get("client_link_mbps")),
        "measured_downlink_mbps": _float(row.get("server_link_mbps")),
        "codec_cpu_us_per_exchange": (
            (
                _float(row.get("client_compress_ms"))
                + _float(row.get("client_decompress_ms"))
                + _float(row.get("server_compress_ms"))
                + _float(row.get("server_decompress_ms"))
            )
            * 1000.0
            / exchanges
        ),
    }


def _serialization_ms(byte_count: float, mbps: float) -> float:
    if byte_count <= 0 or mbps <= 0:
        return 0.0
    return byte_count * 8.0 / (mbps * 1000.0)


def _latency_residual_ms(row: dict[str, Any]) -> float:
    """Estimate non-serialization p95 latency from the measured run."""

    measured_serialization = _serialization_ms(
        row["request_bpe"],
        row["measured_uplink_mbps"],
    ) + _serialization_ms(
        row["response_bpe"],
        row["measured_downlink_mbps"],
    )
    return max(0.0, row["p95_ms"] - row["profile_rtt_ms"] - measured_serialization)


def _projected_p95_ms(row: dict[str, Any], *, uplink_mbps: float, downlink_mbps: float) -> float:
    return (
        row["profile_rtt_ms"]
        + _latency_residual_ms(row)
        + _serialization_ms(row["request_bpe"], uplink_mbps)
        + _serialization_ms(row["response_bpe"], downlink_mbps)
    )


def _window_capacity(inflight_window: int, projected_p95_ms: float) -> float:
    if not inflight_window or not projected_p95_ms:
        return 0.0
    return inflight_window / (projected_p95_ms / 1000.0)


def _capacity(
    row: dict[str, Any],
    *,
    uplink_mbps: float,
    downlink_mbps: float,
) -> tuple[float, str]:
    uplink_bytes_per_second = uplink_mbps * 1_000_000.0 / 8.0
    downlink_bytes_per_second = downlink_mbps * 1_000_000.0 / 8.0
    request_capacity = uplink_bytes_per_second / row["request_bpe"] if row["request_bpe"] else 0.0
    response_capacity = (
        downlink_bytes_per_second / row["response_bpe"] if row["response_bpe"] else 0.0
    )
    if request_capacity <= response_capacity:
        return request_capacity, "uplink"
    return response_capacity, "downlink"


def extrapolate_rows(
    benchmark: dict[str, Any],
    *,
    bandwidth_mbps: tuple[float, ...],
    downlink_multiplier: float = 1.0,
    agent_counts: tuple[int, ...] | None = None,
    per_agent_window: int | None = None,
) -> list[dict[str, Any]]:
    """Return bandwidth-proportional projections from measured benchmark rows."""

    measured = [_measured(row) for row in benchmark.get("results", [])]
    raw_by_profile = {row["profile"]: row for row in measured if row["codec"] == "raw"}
    projections: list[dict[str, Any]] = []
    for row in measured:
        raw_row = raw_by_profile.get(row["profile"])
        for uplink_mbps in bandwidth_mbps:
            downlink_mbps = uplink_mbps * downlink_multiplier
            capacity, bottleneck = _capacity(
                row,
                uplink_mbps=uplink_mbps,
                downlink_mbps=downlink_mbps,
            )
            semantic_bytes_per_second = row["raw_bpe"] * capacity
            wire_bytes_per_second = row["framed_bpe"] * capacity
            request_serialization_ms = _serialization_ms(row["request_bpe"], uplink_mbps)
            response_serialization_ms = _serialization_ms(row["response_bpe"], downlink_mbps)
            projected_p95_ms = _projected_p95_ms(
                row,
                uplink_mbps=uplink_mbps,
                downlink_mbps=downlink_mbps,
            )
            if agent_counts is None:
                concurrency_options = (
                    (
                        1,
                        max(1, row["profile_pipeline_window"]),
                        max(1, row["profile_pipeline_window"]),
                    ),
                )
            else:
                window_per_agent = max(1, int(per_agent_window or 1))
                concurrency_options = tuple(
                    (max(1, agent_count), window_per_agent, max(1, agent_count) * window_per_agent)
                    for agent_count in agent_counts
                )

            raw_capacity = 0.0
            raw_projected_p95_ms = 0.0
            raw_required_total_mbps = 0.0
            if raw_row is not None:
                raw_capacity, _raw_bottleneck = _capacity(
                    raw_row,
                    uplink_mbps=uplink_mbps,
                    downlink_mbps=downlink_mbps,
                )
                raw_projected_p95_ms = _projected_p95_ms(
                    raw_row,
                    uplink_mbps=uplink_mbps,
                    downlink_mbps=downlink_mbps,
                )
                raw_required_total_mbps = raw_row["framed_bpe"] * capacity * 8.0 / 1_000_000.0

            required_inflight_window = (
                math.ceil(capacity * (projected_p95_ms / 1000.0))
                if capacity and projected_p95_ms
                else 0
            )
            for agent_count, window_per_agent, inflight_window in concurrency_options:
                latency_window_capacity = _window_capacity(inflight_window, projected_p95_ms)
                effective_capacity = (
                    min(capacity, latency_window_capacity) if latency_window_capacity else capacity
                )
                required_agent_count = (
                    math.ceil(required_inflight_window / window_per_agent)
                    if required_inflight_window
                    else 0
                )
                raw_effective_capacity = 0.0
                if raw_row is not None:
                    raw_latency_capacity = _window_capacity(inflight_window, raw_projected_p95_ms)
                    raw_effective_capacity = (
                        min(raw_capacity, raw_latency_capacity)
                        if raw_latency_capacity
                        else raw_capacity
                    )
                effective_semantic_bytes_per_second = row["raw_bpe"] * effective_capacity
                effective_wire_bytes_per_second = row["framed_bpe"] * effective_capacity
                effective_raw_required_total_mbps = (
                    raw_row["framed_bpe"] * effective_capacity * 8.0 / 1_000_000.0
                    if raw_row is not None
                    else 0.0
                )
                projections.append(
                    {
                        "profile": row["profile"],
                        "codec": row["codec"],
                        "backend": row["backend"],
                        "uplink_mbps": uplink_mbps,
                        "downlink_mbps": downlink_mbps,
                        "agent_count": agent_count,
                        "per_agent_window": window_per_agent,
                        "aggregate_inflight_window": inflight_window,
                        "required_inflight_window": required_inflight_window,
                        "required_agent_count": required_agent_count,
                        "bandwidth_fill_percent": (
                            effective_capacity / capacity * 100.0 if capacity else 0.0
                        ),
                        "capacity_exchanges_per_second": capacity,
                        "capacity_exchanges_per_minute": capacity * 60.0,
                        "capacity_exchanges_per_hour": capacity * 3600.0,
                        "effective_capacity_exchanges_per_second": effective_capacity,
                        "effective_capacity_exchanges_per_minute": effective_capacity * 60.0,
                        "effective_capacity_exchanges_per_hour": effective_capacity * 3600.0,
                        "latency_window_capacity_exchanges_per_second": latency_window_capacity,
                        "capacity_gain_vs_raw": capacity / raw_capacity if raw_capacity else 0.0,
                        "effective_gain_vs_raw": (
                            effective_capacity / raw_effective_capacity
                            if raw_effective_capacity
                            else 0.0
                        ),
                        "semantic_mib_per_second": semantic_bytes_per_second / 1024.0 / 1024.0,
                        "semantic_gib_per_hour": semantic_bytes_per_second
                        * 3600.0
                        / 1024.0
                        / 1024.0
                        / 1024.0,
                        "wire_mib_per_second": wire_bytes_per_second / 1024.0 / 1024.0,
                        "wire_gib_per_hour": wire_bytes_per_second
                        * 3600.0
                        / 1024.0
                        / 1024.0
                        / 1024.0,
                        "effective_semantic_mib_per_second": effective_semantic_bytes_per_second
                        / 1024.0
                        / 1024.0,
                        "effective_semantic_gib_per_hour": effective_semantic_bytes_per_second
                        * 3600.0
                        / 1024.0
                        / 1024.0
                        / 1024.0,
                        "effective_wire_mib_per_second": effective_wire_bytes_per_second
                        / 1024.0
                        / 1024.0,
                        "effective_wire_gib_per_hour": effective_wire_bytes_per_second
                        * 3600.0
                        / 1024.0
                        / 1024.0
                        / 1024.0,
                        "wire_total_mbps": wire_bytes_per_second * 8.0 / 1_000_000.0,
                        "effective_wire_total_mbps": effective_wire_bytes_per_second
                        * 8.0
                        / 1_000_000.0,
                        "raw_required_total_mbps": raw_required_total_mbps,
                        "effective_raw_required_total_mbps": effective_raw_required_total_mbps,
                        "framed_bytes_per_exchange": row["framed_bpe"],
                        "raw_bytes_per_exchange": row["raw_bpe"],
                        "bottleneck_direction": bottleneck,
                        "projected_p95_ms": projected_p95_ms,
                        "projected_request_serialization_ms": request_serialization_ms,
                        "projected_response_serialization_ms": response_serialization_ms,
                        "latency_residual_ms": _latency_residual_ms(row),
                        "profile_rtt_ms": row["profile_rtt_ms"],
                        "profile_pipeline_window": row["profile_pipeline_window"],
                        "measured_p95_ms": row["p95_ms"],
                        "measured_codec_cpu_us_per_exchange": row["codec_cpu_us_per_exchange"],
                    }
                )
    return projections


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    if not isinstance(payload.get("results"), list):
        raise ValueError(f"{path} does not contain a results list")
    return payload


def _markdown(rows: list[dict[str, Any]], source: Path) -> str:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["profile"]].append(row)

    lines = [
        f"# AIWire Bandwidth-Proportional Extrapolation: {source}",
        "",
        "This table projects semantic exchange capacity from measured framed bytes per "
        "exchange. It assumes the same message shape and codec cost measured by the "
        "benchmark, then scales the link budget linearly by bandwidth.",
        "",
        "| Profile | Mbps up/down | Agents | Win/agent | In-flight | Codec | BW ex/s | "
        "Eff ex/s | Fill | Need agents | p95 ms | vs raw | Eff semantic MiB/s | "
        "Eff wire MiB/s | Raw Mbps needed | Bottleneck |",
        "|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for profile in sorted(grouped):
        rows_for_profile = sorted(
            grouped[profile],
            key=lambda row: (row["uplink_mbps"], row["agent_count"], row["codec"]),
        )
        for row in rows_for_profile:
            lines.append(
                "| {profile} | {up}/{down} | {agents} | {win_agent} | {inflight} | "
                "{codec} | {bw_eps} | {eff_eps} | {fill}% | {need_agents} | "
                "{p95} | {gain}x | {sem_mib} | {wire_mib} | "
                "{raw_mbps} | {bottleneck} |".format(
                    profile=profile,
                    up=_fmt(row["uplink_mbps"], 1),
                    down=_fmt(row["downlink_mbps"], 1),
                    agents=row["agent_count"],
                    win_agent=row["per_agent_window"],
                    inflight=row["aggregate_inflight_window"],
                    codec=row["codec"],
                    bw_eps=_fmt(row["capacity_exchanges_per_second"], 1),
                    eff_eps=_fmt(row["effective_capacity_exchanges_per_second"], 1),
                    fill=_fmt(row["bandwidth_fill_percent"], 1),
                    need_agents=row["required_agent_count"],
                    p95=_fmt(row["projected_p95_ms"], 1),
                    gain=_fmt(row["effective_gain_vs_raw"], 2),
                    sem_mib=_fmt(row["effective_semantic_mib_per_second"], 2),
                    wire_mib=_fmt(row["effective_wire_mib_per_second"], 2),
                    raw_mbps=_fmt(row["effective_raw_required_total_mbps"], 2),
                    bottleneck=row["bottleneck_direction"],
                )
            )
    lines.extend(
        [
            "",
            "Readout: if framed bytes per exchange stay constant, exchange capacity "
            "scales directly with available bandwidth. AURA's advantage is the lower "
            "bytes-per-exchange term, so the same Mbps carries more semantic exchanges. "
            "Effective capacity is additionally capped by the projected p95 latency and "
            "aggregate in-flight window. The required agent count is computed as "
            "`ceil(bandwidth_capacity * projected_p95_seconds / window_per_agent)`.",
            "",
        ]
    )
    return "\n".join(lines)


def _json(rows: list[dict[str, Any]]) -> str:
    return json.dumps({"extrapolations": rows}, indent=2, sort_keys=True) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("benchmark_json", type=Path)
    parser.add_argument(
        "--bandwidth-mbps",
        default="1,5,10,50,100",
        help="comma-separated uplink Mbps values to project",
    )
    parser.add_argument(
        "--downlink-multiplier",
        type=float,
        default=1.0,
        help="downlink Mbps as a multiplier of each uplink Mbps value",
    )
    parser.add_argument(
        "--agent-counts",
        default="1,2,4,8,16,32",
        help=(
            "comma-separated logical agent counts to project; each agent contributes "
            "--per-agent-window in-flight exchanges"
        ),
    )
    parser.add_argument(
        "--per-agent-window",
        type=int,
        default=1,
        help="in-flight exchanges each projected logical agent can keep outstanding",
    )
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows = extrapolate_rows(
        _load(args.benchmark_json),
        bandwidth_mbps=_split_mbps(args.bandwidth_mbps),
        downlink_multiplier=args.downlink_multiplier,
        agent_counts=_split_ints(args.agent_counts) if args.agent_counts else None,
        per_agent_window=args.per_agent_window,
    )
    rendered = _json(rows) if args.format == "json" else _markdown(rows, args.benchmark_json)
    if args.output:
        args.output.write_text(rendered)
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
