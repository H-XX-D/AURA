#!/usr/bin/env python3
"""Summarize AIWire stress output in AI-to-AI messaging terms."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _float(value: Any) -> float:
    return float(value or 0.0)


def _int(value: Any) -> int:
    return int(value or 0)


def _fmt_float(value: float, digits: int = 1) -> str:
    return f"{value:.{digits}f}"


def _metrics(row: dict[str, Any]) -> dict[str, Any]:
    exchanges = max(1, _int(row.get("exchanges")))
    stress_seconds = max(_float(row.get("stress_ms")) / 1000.0, 1e-9)
    framed_bytes = _float(row.get("framed_wire_bytes"))
    raw_bytes = _float(row.get("raw_bytes"))
    framed_request_bytes = _float(row.get("framed_request_wire_bytes"))
    framed_response_bytes = _float(row.get("framed_response_wire_bytes"))
    request_framed_bytes_per_exchange = framed_request_bytes / exchanges
    response_framed_bytes_per_exchange = framed_response_bytes / exchanges
    client_link_bytes_per_second = _float(row.get("client_link_mbps")) * 1_000_000.0 / 8.0
    server_link_bytes_per_second = _float(row.get("server_link_mbps")) * 1_000_000.0 / 8.0
    request_capacity = (
        client_link_bytes_per_second / request_framed_bytes_per_exchange
        if client_link_bytes_per_second and request_framed_bytes_per_exchange
        else 0.0
    )
    response_capacity = (
        server_link_bytes_per_second / response_framed_bytes_per_exchange
        if server_link_bytes_per_second and response_framed_bytes_per_exchange
        else 0.0
    )
    if request_capacity and response_capacity:
        bandwidth_capacity = min(request_capacity, response_capacity)
        bottleneck_direction = "request" if request_capacity <= response_capacity else "response"
    else:
        bandwidth_capacity = 0.0
        bottleneck_direction = ""
    client_codec_ms = _float(row.get("client_compress_ms")) + _float(
        row.get("client_decompress_ms")
    )
    server_codec_ms = _float(row.get("server_compress_ms")) + _float(
        row.get("server_decompress_ms")
    )
    p50 = _float(row.get("roundtrip_ms_p50"))
    p95 = _float(row.get("roundtrip_ms_p95"))
    p99 = _float(row.get("roundtrip_ms_p99"))

    return {
        "network_profile": row.get("network_profile", ""),
        "network_description": row.get("network_description", ""),
        "profile_rtt_ms": _float(row.get("profile_rtt_ms")),
        "profile_pipeline_window": _int(row.get("profile_pipeline_window")),
        "codec": row.get("codec", ""),
        "backend": row.get("backend", ""),
        "completed": _int(row.get("deadline_completed_exchanges")),
        "completed_per_second": _float(row.get("deadline_exchanges_per_second")),
        "framed_bytes_per_exchange": framed_bytes / exchanges,
        "request_framed_bytes_per_exchange": request_framed_bytes_per_exchange,
        "response_framed_bytes_per_exchange": response_framed_bytes_per_exchange,
        "raw_bytes_per_exchange": raw_bytes / exchanges,
        "framed_saved_percent": _float(row.get("framed_wire_saved_percent")),
        "framed_ratio": _float(row.get("framed_ratio")),
        "bandwidth_capacity_exchanges_per_second": bandwidth_capacity,
        "request_capacity_exchanges_per_second": request_capacity,
        "response_capacity_exchanges_per_second": response_capacity,
        "bandwidth_capacity_completed": bandwidth_capacity * _float(row.get("target_seconds")),
        "bandwidth_utilization_percent": (
            _float(row.get("deadline_exchanges_per_second")) / bandwidth_capacity * 100.0
            if bandwidth_capacity
            else 0.0
        ),
        "bandwidth_bottleneck_direction": bottleneck_direction,
        "wire_mbps": framed_bytes * 8.0 / stress_seconds / 1_000_000.0,
        "semantic_mbps": raw_bytes * 8.0 / stress_seconds / 1_000_000.0,
        "codec_cpu_us_per_exchange": (client_codec_ms + server_codec_ms) * 1000.0 / exchanges,
        "client_codec_us_per_exchange": client_codec_ms * 1000.0 / exchanges,
        "server_codec_us_per_exchange": server_codec_ms * 1000.0 / exchanges,
        "p50_ms": p50,
        "p95_ms": p95,
        "p99_ms": p99,
        "p95_tail_tax_ms": p95 - p50,
        "p99_tail_tax_ms": p99 - p50,
        "verified": bool(row.get("verified")),
    }


def _load(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text())
    rows = payload.get("results")
    if not isinstance(rows, list):
        raise ValueError(f"{path} does not contain a results list")
    return [_metrics(row) for row in rows]


def _markdown(rows: list[dict[str, Any]], source: Path) -> str:
    include_profile = any(row["network_profile"] for row in rows)
    raw_capacity_by_profile: dict[str, float] = {}
    for row in rows:
        if row["codec"] == "raw":
            raw_capacity_by_profile[row["network_profile"]] = row[
                "bandwidth_capacity_exchanges_per_second"
            ]
    default_raw_capacity = next(iter(raw_capacity_by_profile.values()), 0.0)
    table_header = (
        "| Profile | Codec | Backend | Completed | Ex/s | Framed B/ex | BW cap ex/s | "
        "BW gain | Obs/BW cap | Saved | p95 ms | Codec CPU us/ex | Link Mbps |"
        if include_profile
        else "| Codec | Backend | Completed | Ex/s | Framed B/ex | BW cap ex/s | BW gain | "
        "Obs/BW cap | Saved | p95 ms | Codec CPU us/ex | Link Mbps |"
    )
    table_rule = (
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"
        if include_profile
        else "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"
    )
    lines = [
        f"# AI-to-AI Messaging Metrics: {source}",
        "",
        "These metrics treat each request/response pair as a semantic exchange. "
        "Framed bytes include TCP frame length prefixes, so the table reflects "
        "bytes the link actually has to carry for this harness.",
        "",
        table_header,
        table_rule,
    ]
    for row in rows:
        capacity = row["bandwidth_capacity_exchanges_per_second"]
        raw_capacity = raw_capacity_by_profile.get(row["network_profile"], default_raw_capacity)
        gain = capacity / raw_capacity if raw_capacity else 0.0
        if include_profile:
            lines.append(
                "| {profile} | {codec} | {backend} | {completed} | {eps} | {bpx} | "
                "{capacity} | {gain}x | {util}% | {saved}% | {p95} | {cpu} | "
                "{wire_mbps} |".format(
                    profile=row["network_profile"],
                    codec=row["codec"],
                    backend=row["backend"],
                    completed=row["completed"],
                    eps=_fmt_float(row["completed_per_second"], 1),
                    bpx=_fmt_float(row["framed_bytes_per_exchange"], 1),
                    capacity=_fmt_float(capacity, 1),
                    gain=_fmt_float(gain, 2),
                    util=_fmt_float(row["bandwidth_utilization_percent"], 1),
                    saved=_fmt_float(row["framed_saved_percent"], 1),
                    p95=_fmt_float(row["p95_ms"], 1),
                    cpu=_fmt_float(row["codec_cpu_us_per_exchange"], 1),
                    wire_mbps=_fmt_float(row["wire_mbps"], 2),
                )
            )
            continue
        lines.append(
            "| {codec} | {backend} | {completed} | {eps} | {bpx} | {capacity} | "
            "{gain}x | {util}% | {saved}% | {p95} | {cpu} | {wire_mbps} |".format(
                codec=row["codec"],
                backend=row["backend"],
                completed=row["completed"],
                eps=_fmt_float(row["completed_per_second"], 1),
                bpx=_fmt_float(row["framed_bytes_per_exchange"], 1),
                capacity=_fmt_float(capacity, 1),
                gain=_fmt_float(gain, 2),
                util=_fmt_float(row["bandwidth_utilization_percent"], 1),
                saved=_fmt_float(row["framed_saved_percent"], 1),
                p95=_fmt_float(row["p95_ms"], 1),
                cpu=_fmt_float(row["codec_cpu_us_per_exchange"], 1),
                wire_mbps=_fmt_float(row["wire_mbps"], 2),
            )
        )

    best_bandwidth = max(rows, key=lambda row: row["framed_saved_percent"])
    best_capacity = max(rows, key=lambda row: row["bandwidth_capacity_exchanges_per_second"])
    best_completed = max(rows, key=lambda row: row["completed_per_second"])
    best_tail = min(rows, key=lambda row: row["p95_ms"])
    best_cpu = min(
        (row for row in rows if row["codec"] != "raw"),
        key=lambda row: row["codec_cpu_us_per_exchange"],
    )

    lines.extend(
        [
            "",
            "## Readout",
            "",
            f"- Best bandwidth reduction: `{best_bandwidth['codec']}` "
            f"({best_bandwidth['framed_saved_percent']:.1f}% framed bytes saved).",
            f"- Highest bandwidth-proportional capacity: `{best_capacity['codec']}` "
            f"({best_capacity['bandwidth_capacity_exchanges_per_second']:.1f} ex/s).",
            f"- Highest completed exchange rate: `{best_completed['codec']}` "
            f"({best_completed['completed_per_second']:.1f} ex/s).",
            f"- Lowest p95 roundtrip: `{best_tail['codec']}` ({best_tail['p95_ms']:.1f} ms).",
            f"- Lowest non-raw codec CPU: `{best_cpu['codec']}` "
            f"({best_cpu['codec_cpu_us_per_exchange']:.1f} us/ex).",
            "",
            "For AI-to-AI messaging, the useful result is not just compression ratio. "
            "Bandwidth-proportional capacity is the exchange rate predicted from "
            "link bytes per second divided by framed bytes per exchange. A codec wins "
            "when it can turn that extra capacity into verified semantic exchanges "
            "without letting p95/p99 latency or codec CPU become the next bottleneck.",
            "",
        ]
    )
    return "\n".join(lines)


def _json(rows: list[dict[str, Any]]) -> str:
    return json.dumps({"metrics": rows}, indent=2, sort_keys=True) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("benchmark_json", type=Path)
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows = _load(args.benchmark_json)
    rendered = _json(rows) if args.format == "json" else _markdown(rows, args.benchmark_json)
    if args.output:
        args.output.write_text(rendered)
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
