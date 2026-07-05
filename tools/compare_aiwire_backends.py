#!/usr/bin/env python3
"""Compare AIWire Python and native backends on the same benchmark inputs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
TOOLS = ROOT / "tools"
for candidate in (SRC, TOOLS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from benchmark_aiwire_fixture_saturation import (  # noqa: E402
    DEFAULT_FIXTURE_PATH,
    build_fixture_saturation_report,
)

from aura_compression.ai_wire import (  # noqa: E402
    AI_WIRE_DEFAULT_LEVEL,
    AIWireNativeError,
    aiwire_native_status,
)
from aura_compression.cli.benchmark import (  # noqa: E402
    BENCHMARK_BACKENDS,
    BENCHMARK_PROFILES,
    run_benchmark,
)

SCHEMA = "aura.aiwire.backend_comparison.v1"
DEFAULT_BACKENDS = ("python", "native")
DEFAULT_CODECS = ("raw", "zlib", "aiwire", "aitoken_aiwire")
DEFAULT_AGENT_COUNTS = (1, 64)


def _split_csv(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split(",") if part.strip())


def _split_ints(value: str) -> tuple[int, ...]:
    return tuple(int(part.strip()) for part in value.split(",") if part.strip())


def _saved_percent(raw_bytes: float, wire_bytes: float) -> float:
    return (1.0 - wire_bytes / raw_bytes) * 100.0 if raw_bytes else 0.0


def _percent_delta(baseline: float, candidate: float) -> float | None:
    if baseline == 0:
        return None
    return (candidate - baseline) / baseline * 100.0


def _speedup(baseline_seconds: float, candidate_seconds: float) -> float | None:
    if candidate_seconds <= 0:
        return None
    return baseline_seconds / candidate_seconds


def _sustained_summary(result: Mapping[str, Any]) -> dict[str, Any]:
    session_model = result.get("session_model", {})
    raw_bytes = float(result["bytes_in"])
    wire_bytes = float(result["bytes_out"])
    return {
        "requested_backend": result["requested_backend"],
        "encode_backend": result["encode_backend"],
        "decode_backend": result["decode_backend"],
        "messages": result["messages"],
        "raw_bytes": result["bytes_in"],
        "wire_bytes": result["bytes_out"],
        "ratio": result["ratio"],
        "saved_percent": _saved_percent(raw_bytes, wire_bytes),
        "encode_ms": float(result["encode_seconds"]) * 1000.0,
        "decode_ms": float(result["decode_seconds"]) * 1000.0,
        "setup_framed_bytes": session_model.get("setup_framed_bytes"),
        "setup_share_percent": session_model.get("setup_share_percent"),
        "steady_state_wire_bytes_per_message": session_model.get(
            "steady_state_wire_bytes_per_message"
        ),
        "amortized_wire_bytes_per_message": session_model.get("amortized_wire_bytes_per_message"),
        "amortized_saved_percent": session_model.get("amortized_saved_percent"),
    }


def _fixture_summary(report: Mapping[str, Any]) -> dict[str, Any]:
    agent_counts = [int(value) for value in report["agent_counts"]]
    max_agents = max(agent_counts) if agent_counts else 1
    codec_measurements = []
    for measured in report["codec_measurements"]:
        codec_measurements.append(
            {
                "codec": measured["codec"],
                "backend": measured["backend"],
                "raw_bytes": measured["raw_bytes"],
                "framed_wire_bytes": measured["framed_wire_bytes"],
                "framed_bytes_per_exchange": measured["framed_bytes_per_exchange"],
                "ratio": measured["framed_ratio"],
                "saved_percent": measured["framed_wire_saved_percent"],
                "codec_cpu_us_per_exchange": measured["codec_cpu_us_per_exchange"],
                "cpu_ceiling_exchanges_per_second": measured["cpu_ceiling_exchanges_per_second"],
            }
        )

    saturation_at_max_agents = []
    for row in report["results"]:
        if int(row["agent_count"]) != max_agents:
            continue
        saturation_at_max_agents.append(
            {
                "network_profile": row["network_profile"],
                "codec": row["codec"],
                "agent_count": row["agent_count"],
                "framed_bytes_per_exchange": row["framed_bytes_per_exchange"],
                "bandwidth_capacity_exchanges_per_second": row[
                    "bandwidth_capacity_exchanges_per_second"
                ],
                "effective_capacity_exchanges_per_second": row[
                    "effective_capacity_exchanges_per_second"
                ],
                "effective_messages_per_second": row["effective_messages_per_second"],
                "bandwidth_fill_percent": row["bandwidth_fill_percent"],
                "effective_gain_vs_raw": row["effective_gain_vs_raw"],
                "wire_saved_vs_raw_percent": row["wire_saved_vs_raw_percent"],
                "projected_p95_ms": row["projected_p95_ms"],
                "limiting_factor": row["limiting_factor"],
            }
        )

    return {
        "backend_mode": report["backend_mode"],
        "profiles": [profile["name"] for profile in report["profiles"]],
        "agent_counts": agent_counts,
        "max_agent_count": max_agents,
        "codecs": report["codecs"],
        "codec_measurements": codec_measurements,
        "saturation_at_max_agents": saturation_at_max_agents,
    }


def _backend_result(
    *,
    backend: str,
    profile: str,
    corpus: str,
    messages: int,
    seed: int,
    level: int,
    peers: int,
    fixture_path: Path,
    fixture_profiles: str,
    codecs: Iterable[str],
    agent_counts: Iterable[int],
    per_agent_window: int,
) -> dict[str, Any]:
    sustained = run_benchmark(
        profile=profile,
        corpus=corpus,
        messages=messages,
        seed=seed,
        level=level,
        backend=backend,
        sustained_session=True,
        peers=peers,
    )
    fixture = build_fixture_saturation_report(
        fixture_path=fixture_path,
        profiles=fixture_profiles,
        codecs=codecs,
        agent_counts=agent_counts,
        per_agent_window=per_agent_window,
        backend=backend,
        level=level,
    )
    return {
        "backend": backend,
        "available": True,
        "skipped": False,
        "sustained_session": sustained,
        "sustained_summary": _sustained_summary(sustained),
        "fixture_saturation": fixture,
        "fixture_summary": _fixture_summary(fixture),
    }


def _missing_native_result(backend: str, reason: str, *, skipped: bool) -> dict[str, Any]:
    result: dict[str, Any] = {
        "backend": backend,
        "available": False,
        "skipped": skipped,
        "reason": reason,
    }
    if not skipped:
        result["error"] = reason
    return result


def _completed_results(results: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [result for result in results if not result.get("skipped") and result.get("available")]


def _fixture_measurement_by_codec(result: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {row["codec"]: row for row in result["fixture_summary"]["codec_measurements"]}


def _delta_rows(results: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    completed = _completed_results(results)
    if len(completed) < 2:
        return []

    baseline = completed[0]
    baseline_summary = baseline["sustained_summary"]
    baseline_fixture = _fixture_measurement_by_codec(baseline)
    deltas: list[dict[str, Any]] = []
    for candidate in completed[1:]:
        candidate_summary = candidate["sustained_summary"]
        candidate_fixture = _fixture_measurement_by_codec(candidate)
        fixture_codec_deltas = []
        for codec in sorted(set(baseline_fixture) & set(candidate_fixture)):
            base_codec = baseline_fixture[codec]
            candidate_codec = candidate_fixture[codec]
            fixture_codec_deltas.append(
                {
                    "codec": codec,
                    "framed_bytes_delta_percent": _percent_delta(
                        float(base_codec["framed_wire_bytes"]),
                        float(candidate_codec["framed_wire_bytes"]),
                    ),
                    "cpu_speedup": _speedup(
                        float(base_codec["codec_cpu_us_per_exchange"]),
                        float(candidate_codec["codec_cpu_us_per_exchange"]),
                    ),
                    "baseline_backend": base_codec["backend"],
                    "candidate_backend": candidate_codec["backend"],
                }
            )

        deltas.append(
            {
                "from_backend": baseline["backend"],
                "to_backend": candidate["backend"],
                "encode_speedup": _speedup(
                    float(baseline_summary["encode_ms"]),
                    float(candidate_summary["encode_ms"]),
                ),
                "decode_speedup": _speedup(
                    float(baseline_summary["decode_ms"]),
                    float(candidate_summary["decode_ms"]),
                ),
                "wire_bytes_delta_percent": _percent_delta(
                    float(baseline_summary["wire_bytes"]),
                    float(candidate_summary["wire_bytes"]),
                ),
                "ratio_delta_percent": _percent_delta(
                    float(baseline_summary["ratio"]),
                    float(candidate_summary["ratio"]),
                ),
                "fixture_codec_deltas": fixture_codec_deltas,
            }
        )
    return deltas


def run_backend_comparison(
    *,
    backends: Iterable[str] = DEFAULT_BACKENDS,
    profile: str = "small",
    corpus: str = "delta",
    messages: int = 128,
    seed: int = 1729,
    level: int = AI_WIRE_DEFAULT_LEVEL,
    peers: int = 4,
    fixture_path: Path = DEFAULT_FIXTURE_PATH,
    fixture_profiles: str = "lan_10m",
    codecs: Iterable[str] = DEFAULT_CODECS,
    agent_counts: Iterable[int] = DEFAULT_AGENT_COUNTS,
    per_agent_window: int = 1,
    allow_missing_native: bool = False,
) -> dict[str, Any]:
    """Run a Python/native AIWire comparison and return stable JSON."""

    backend_list = tuple(backends)
    codec_list = tuple(codecs)
    agent_count_list = tuple(int(value) for value in agent_counts)
    invalid_backends = [backend for backend in backend_list if backend not in BENCHMARK_BACKENDS]
    if invalid_backends:
        choices = ", ".join(BENCHMARK_BACKENDS)
        raise ValueError(f"unsupported backend(s): {invalid_backends}; choices: {choices}")
    if messages <= 0:
        raise ValueError("messages must be positive")
    if peers < 2:
        raise ValueError("peers must be at least 2")
    if corpus != "delta":
        raise ValueError("backend comparison uses sustained sessions and requires corpus='delta'")

    native_status = aiwire_native_status()
    results: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for backend in backend_list:
        if backend == "native" and not native_status.available:
            reason = native_status.error or "native AIWire backend is not available"
            skipped = allow_missing_native
            results.append(_missing_native_result(backend, reason, skipped=skipped))
            if not skipped:
                errors.append({"backend": backend, "error": reason})
            continue

        try:
            results.append(
                _backend_result(
                    backend=backend,
                    profile=profile,
                    corpus=corpus,
                    messages=messages,
                    seed=seed,
                    level=level,
                    peers=peers,
                    fixture_path=fixture_path,
                    fixture_profiles=fixture_profiles,
                    codecs=codec_list,
                    agent_counts=agent_count_list,
                    per_agent_window=per_agent_window,
                )
            )
        except AIWireNativeError as exc:
            if backend == "native" and allow_missing_native:
                results.append(_missing_native_result(backend, str(exc), skipped=True))
            else:
                results.append(_missing_native_result(backend, str(exc), skipped=False))
                errors.append({"backend": backend, "error": str(exc)})

    report: dict[str, Any] = {
        "schema": SCHEMA,
        "ok": not errors,
        "errors": errors,
        "native_status": native_status.as_dict(),
        "settings": {
            "backends": list(backend_list),
            "profile": profile,
            "corpus": corpus,
            "messages": messages,
            "seed": seed,
            "aiwire_level": level,
            "peers": peers,
            "fixture_corpus": str(fixture_path),
            "fixture_profiles": fixture_profiles,
            "codecs": list(codec_list),
            "agent_counts": list(agent_count_list),
            "per_agent_window": per_agent_window,
            "allow_missing_native": allow_missing_native,
        },
        "backend_results": results,
        "deltas": _delta_rows(results),
    }
    report["completed_backend_count"] = len(_completed_results(results))
    return report


def _fmt(value: Any, digits: int = 2) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, int):
        return f"{value:,}"
    return f"{float(value):,.{digits}f}"


def _markdown_sustained_rows(report: Mapping[str, Any]) -> list[str]:
    lines = [
        "| Backend | Actual | Messages | Raw B | Wire B | Ratio | Saved | Enc ms | Dec ms | Steady B/msg | Amort B/msg | Setup B |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for result in report["backend_results"]:
        if result.get("skipped") or not result.get("available"):
            lines.append(
                "| {backend} | skipped | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |".format(
                    backend=result["backend"]
                )
            )
            continue
        summary = result["sustained_summary"]
        lines.append(
            "| {backend} | {actual} | {messages} | {raw} | {wire} | {ratio}x | "
            "{saved}% | {enc} | {dec} | {steady} | {amort} | {setup} |".format(
                backend=result["backend"],
                actual=f"{summary['encode_backend']}/{summary['decode_backend']}",
                messages=_fmt(summary["messages"], 0),
                raw=_fmt(summary["raw_bytes"], 0),
                wire=_fmt(summary["wire_bytes"], 0),
                ratio=_fmt(summary["ratio"], 2),
                saved=_fmt(summary["saved_percent"], 1),
                enc=_fmt(summary["encode_ms"], 2),
                dec=_fmt(summary["decode_ms"], 2),
                steady=_fmt(summary["steady_state_wire_bytes_per_message"], 1),
                amort=_fmt(summary["amortized_wire_bytes_per_message"], 1),
                setup=_fmt(summary["setup_framed_bytes"], 0),
            )
        )
    return lines


def _markdown_fixture_rows(report: Mapping[str, Any]) -> list[str]:
    lines = [
        "| Backend | Codec | Actual | Framed B/ex | Ratio | Saved | CPU us/ex |",
        "|---|---|---|---:|---:|---:|---:|",
    ]
    for result in report["backend_results"]:
        if result.get("skipped") or not result.get("available"):
            continue
        for row in result["fixture_summary"]["codec_measurements"]:
            lines.append(
                "| {backend} | {codec} | {actual} | {bpe} | {ratio}x | {saved}% | {cpu} |".format(
                    backend=result["backend"],
                    codec=row["codec"],
                    actual=row["backend"],
                    bpe=_fmt(row["framed_bytes_per_exchange"], 1),
                    ratio=_fmt(row["ratio"], 2),
                    saved=_fmt(row["saved_percent"], 1),
                    cpu=_fmt(row["codec_cpu_us_per_exchange"], 1),
                )
            )
    return lines


def _markdown_delta_rows(report: Mapping[str, Any]) -> list[str]:
    if not report["deltas"]:
        return ["No backend deltas were computed."]
    lines = [
        "| From | To | Encode speedup | Decode speedup | Wire delta | Ratio delta |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in report["deltas"]:
        lines.append(
            "| {from_backend} | {to_backend} | {enc}x | {dec}x | {wire}% | {ratio}% |".format(
                from_backend=row["from_backend"],
                to_backend=row["to_backend"],
                enc=_fmt(row["encode_speedup"], 2),
                dec=_fmt(row["decode_speedup"], 2),
                wire=_fmt(row["wire_bytes_delta_percent"], 2),
                ratio=_fmt(row["ratio_delta_percent"], 2),
            )
        )
    return lines


def render_markdown(report: Mapping[str, Any]) -> str:
    """Render a concise human-readable backend comparison report."""

    settings = report["settings"]
    native_status = report["native_status"]
    lines = [
        "# AIWire Backend Comparison",
        "",
        "This report runs the same sustained-session delta corpus and fixture-backed "
        "network saturation model through each requested AIWire backend.",
        "",
        f"- Status: `{'ok' if report['ok'] else 'failed'}`",
        f"- Backends: `{','.join(settings['backends'])}`",
        f"- Sustained corpus: `{settings['profile']}/{settings['corpus']}` with "
        f"`{settings['messages']}` messages and `{settings['peers']}` peers",
        f"- Fixture profiles: `{settings['fixture_profiles']}`",
        f"- Fixture codecs: `{','.join(settings['codecs'])}`",
        f"- Native available: `{native_status['available']}`",
        "",
        "## Sustained Session",
        "",
        *_markdown_sustained_rows(report),
        "",
        "## Fixture Codec Summary",
        "",
        *_markdown_fixture_rows(report),
        "",
        "## Backend Deltas",
        "",
        *_markdown_delta_rows(report),
        "",
    ]
    if report["errors"]:
        lines.extend(
            [
                "## Errors",
                "",
                *[f"- `{error['backend']}`: {error['error']}" for error in report["errors"]],
                "",
            ]
        )
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backends", default="python,native")
    parser.add_argument(
        "--profile",
        choices=tuple(BENCHMARK_PROFILES),
        default="small",
        help="Benchmark size profile. --messages overrides the profile count.",
    )
    parser.add_argument(
        "--corpus",
        choices=("delta",),
        default="delta",
        help="Sustained-session backend comparison currently requires delta corpus.",
    )
    parser.add_argument("--messages", type=int, default=128)
    parser.add_argument("--seed", type=int, default=1729)
    parser.add_argument("--aiwire-level", type=int, default=AI_WIRE_DEFAULT_LEVEL)
    parser.add_argument("--peers", type=int, default=4)
    parser.add_argument("--fixture-corpus", type=Path, default=DEFAULT_FIXTURE_PATH)
    parser.add_argument("--fixture-profiles", default="lan_10m")
    parser.add_argument("--codecs", default="raw,zlib,aiwire,aitoken_aiwire")
    parser.add_argument("--agent-counts", default="1,64")
    parser.add_argument("--per-agent-window", type=int, default=1)
    parser.add_argument(
        "--allow-missing-native",
        action="store_true",
        help="Return ok=true and mark native skipped when libaura_aiwire is absent.",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = run_backend_comparison(
            backends=_split_csv(args.backends),
            profile=args.profile,
            corpus=args.corpus,
            messages=args.messages,
            seed=args.seed,
            level=args.aiwire_level,
            peers=args.peers,
            fixture_path=args.fixture_corpus,
            fixture_profiles=args.fixture_profiles,
            codecs=_split_csv(args.codecs),
            agent_counts=_split_ints(args.agent_counts),
            per_agent_window=args.per_agent_window,
            allow_missing_native=args.allow_missing_native,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    json_payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    markdown = render_markdown(report) + "\n"
    if args.output:
        args.output.write_text(json_payload, encoding="utf-8")
    if args.markdown_output:
        args.markdown_output.write_text(markdown, encoding="utf-8")
    print(markdown if args.format == "markdown" else json_payload, end="")
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
