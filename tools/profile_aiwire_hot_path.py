#!/usr/bin/env python3
"""Profile AIWire benchmark hot paths with cProfile."""

from __future__ import annotations

import argparse
import cProfile
import json
import platform
import pstats
import sys
import time
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
TOOLS = ROOT / "tools"
for candidate in (SRC, TOOLS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from benchmark_aiwire_fixture_saturation import (  # noqa: E402
    DEFAULT_FIXTURE_PATH,
    SUPPORTED_CODECS,
    measure_fixture_codecs,
)

from aura_compression.ai_wire import (  # noqa: E402
    AI_WIRE_DEFAULT_LEVEL,
    AIWireNativeError,
    aiwire_native_status,
)
from aura_compression.ai_wire_fixtures import (  # noqa: E402
    load_aiwire_session_fixture_corpus,
)
from aura_compression.cli.benchmark import (  # noqa: E402
    BENCHMARK_BACKENDS,
    BENCHMARK_PROFILES,
    run_benchmark,
)

SCHEMA = "aura.aiwire.hot_path_profile.v1"
PROFILE_MODES = ("sustained", "fixture", "both")
DEFAULT_CODECS = ("raw", "zlib", "aiwire", "aitoken_aiwire")


def _split_csv(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split(",") if part.strip())


def _platform_info() -> dict[str, str]:
    return {
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python": platform.python_version(),
        "python_implementation": platform.python_implementation(),
    }


def _relative_file(filename: str) -> str:
    try:
        return str(Path(filename).resolve().relative_to(ROOT))
    except ValueError:
        return filename


def _stat_rows(
    stats: pstats.Stats,
    *,
    sort_index: int,
    top_limit: int,
    elapsed_ms: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    sorted_stats = sorted(
        stats.stats.items(),
        key=lambda item: item[1][sort_index],
        reverse=True,
    )
    for (filename, line, function), stat in sorted_stats[:top_limit]:
        (
            primitive_calls,
            total_calls,
            self_seconds,
            cumulative_seconds,
            _callers,
        ) = stat
        cumulative_ms = cumulative_seconds * 1000.0
        self_ms = self_seconds * 1000.0
        self_percent = self_ms / elapsed_ms * 100.0 if elapsed_ms else 0.0
        self_us_per_call = 0.0
        if total_calls:
            self_us_per_call = self_seconds * 1_000_000.0 / total_calls
        rows.append(
            {
                "file": _relative_file(filename),
                "line": line,
                "function": function,
                "primitive_calls": primitive_calls,
                "total_calls": total_calls,
                "self_ms": self_ms,
                "cumulative_ms": cumulative_ms,
                "cumulative_percent_of_elapsed": (
                    cumulative_ms / elapsed_ms * 100.0 if elapsed_ms else 0.0
                ),
                "self_percent_of_elapsed": self_percent,
                "self_us_per_call": self_us_per_call,
            }
        )
    return rows


def _profile_call(
    name: str,
    work: Callable[[], dict[str, Any]],
    *,
    top_limit: int,
) -> dict[str, Any]:
    profiler = cProfile.Profile()
    started = time.perf_counter()
    profiler.enable()
    payload = work()
    profiler.disable()
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    stats = pstats.Stats(profiler)
    primitive_calls = sum(row[0] for row in stats.stats.values())
    total_calls = sum(row[1] for row in stats.stats.values())
    return {
        "name": name,
        "elapsed_ms": elapsed_ms,
        "primitive_calls": primitive_calls,
        "total_calls": total_calls,
        "payload": payload,
        "top_cumulative": _stat_rows(
            stats,
            sort_index=3,
            top_limit=top_limit,
            elapsed_ms=elapsed_ms,
        ),
        "top_self_time": _stat_rows(
            stats,
            sort_index=2,
            top_limit=top_limit,
            elapsed_ms=elapsed_ms,
        ),
    }


def _saved_percent(raw_bytes: float, wire_bytes: float) -> float:
    return (1.0 - wire_bytes / raw_bytes) * 100.0 if raw_bytes else 0.0


def _sustained_summary(result: Mapping[str, Any]) -> dict[str, Any]:
    session_model = result.get("session_model", {})
    raw_bytes = float(result["bytes_in"])
    wire_bytes = float(result["bytes_out"])
    amortized_wire_bpm = session_model.get("amortized_wire_bytes_per_message")
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
        "steady_state_wire_bytes_per_message": session_model.get(
            "steady_state_wire_bytes_per_message"
        ),
        "amortized_wire_bytes_per_message": amortized_wire_bpm,
    }


def _fixture_summary(
    rows: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for row in rows:
        cpu_ceiling = row["cpu_ceiling_exchanges_per_second"]
        summary.append(
            {
                "codec": row["codec"],
                "backend": row["backend"],
                "exchanges": row["exchanges"],
                "raw_bytes": row["raw_bytes"],
                "framed_wire_bytes": row["framed_wire_bytes"],
                "framed_bytes_per_exchange": row["framed_bytes_per_exchange"],
                "framed_ratio": row["framed_ratio"],
                "framed_wire_saved_percent": row["framed_wire_saved_percent"],
                "codec_cpu_us_per_exchange": row["codec_cpu_us_per_exchange"],
                "cpu_ceiling_exchanges_per_second": cpu_ceiling,
            }
        )
    return summary


def _validate_inputs(
    *,
    mode: str,
    backend: str,
    profile: str,
    corpus: str,
    messages: int,
    peers: int,
    codecs: Iterable[str],
    top_limit: int,
) -> tuple[str, ...]:
    if mode not in PROFILE_MODES:
        mode_choices = ", ".join(PROFILE_MODES)
        message = f"unsupported mode {mode!r}"
        raise ValueError(f"{message}; choices: {mode_choices}")
    if backend not in BENCHMARK_BACKENDS:
        backend_choices = ", ".join(BENCHMARK_BACKENDS)
        message = f"unsupported backend {backend!r}"
        raise ValueError(f"{message}; choices: {backend_choices}")
    if profile not in BENCHMARK_PROFILES:
        profile_choices = ", ".join(BENCHMARK_PROFILES)
        message = f"unsupported profile {profile!r}"
        raise ValueError(f"{message}; choices: {profile_choices}")
    if corpus != "delta":
        message = "hot-path sustained profiling requires corpus='delta'"
        raise ValueError(message)
    if messages <= 0:
        raise ValueError("messages must be positive")
    if peers < 2:
        raise ValueError("peers must be at least 2")
    if top_limit <= 0:
        raise ValueError("top_limit must be positive")

    codec_list = tuple(codecs)
    invalid_codecs = []
    for codec in codec_list:
        if codec not in SUPPORTED_CODECS:
            invalid_codecs.append(codec)
    if invalid_codecs:
        codec_choices = ", ".join(SUPPORTED_CODECS)
        message = f"unsupported codec(s): {invalid_codecs}"
        raise ValueError(f"{message}; choices: {codec_choices}")
    return codec_list


def profile_aiwire_hot_path(
    *,
    mode: str = "both",
    backend: str = "python",
    profile: str = "small",
    corpus: str = "delta",
    messages: int = 128,
    seed: int = 1729,
    level: int = AI_WIRE_DEFAULT_LEVEL,
    peers: int = 4,
    fixture_path: Path = DEFAULT_FIXTURE_PATH,
    codecs: Iterable[str] = DEFAULT_CODECS,
    top_limit: int = 20,
    allow_missing_native: bool = False,
) -> dict[str, Any]:
    """Profile sustained-session and fixture hot paths with stable JSON."""

    codec_list = _validate_inputs(
        mode=mode,
        backend=backend,
        profile=profile,
        corpus=corpus,
        messages=messages,
        peers=peers,
        codecs=codecs,
        top_limit=top_limit,
    )
    native_status = aiwire_native_status()
    if backend == "native" and not native_status.available:
        reason = native_status.error
        if reason is None:
            reason = "native AIWire backend is not available"
        errors = []
        if not allow_missing_native:
            errors.append({"backend": backend, "error": reason})
        report = {
            "schema": SCHEMA,
            "ok": allow_missing_native,
            "skipped": allow_missing_native,
            "errors": errors,
            "reason": reason,
            "settings": {
                "mode": mode,
                "backend": backend,
                "allow_missing_native": allow_missing_native,
            },
            "platform": _platform_info(),
            "native_status": native_status.as_dict(),
            "profiles": [],
        }
        return report

    profiles: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    if mode in {"sustained", "both"}:

        def sustained_work() -> dict[str, Any]:
            result = run_benchmark(
                profile=profile,
                corpus=corpus,
                messages=messages,
                seed=seed,
                level=level,
                backend=backend,
                sustained_session=True,
                peers=peers,
            )
            return {
                "kind": "sustained_session",
                "summary": _sustained_summary(result),
            }

        try:
            profiles.append(
                _profile_call(
                    "sustained_session",
                    sustained_work,
                    top_limit=top_limit,
                )
            )
        except AIWireNativeError as exc:
            errors.append({"profile": "sustained_session", "error": str(exc)})

    if mode in {"fixture", "both"}:
        fixture_corpus = load_aiwire_session_fixture_corpus(fixture_path)

        def fixture_work() -> dict[str, Any]:
            measured = measure_fixture_codecs(
                fixture_corpus,
                codecs=codec_list,
                backend=backend,
                level=level,
            )
            return {
                "kind": "fixture_codecs",
                "fixture_corpus": str(fixture_path),
                "summary": _fixture_summary(measured),
            }

        try:
            profiles.append(
                _profile_call(
                    "fixture_codecs",
                    fixture_work,
                    top_limit=top_limit,
                )
            )
        except AIWireNativeError as exc:
            errors.append({"profile": "fixture_codecs", "error": str(exc)})

    return {
        "schema": SCHEMA,
        "ok": not errors,
        "skipped": False,
        "errors": errors,
        "settings": {
            "mode": mode,
            "backend": backend,
            "profile": profile,
            "corpus": corpus,
            "messages": messages,
            "seed": seed,
            "aiwire_level": level,
            "peers": peers,
            "fixture_corpus": str(fixture_path),
            "codecs": list(codec_list),
            "top_limit": top_limit,
            "allow_missing_native": allow_missing_native,
        },
        "platform": _platform_info(),
        "native_status": native_status.as_dict(),
        "profiles": profiles,
    }


def _fmt(value: Any, digits: int = 2) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, int):
        return f"{value:,}"
    return f"{float(value):,.{digits}f}"


def _render_payload_summary(profiled: Mapping[str, Any]) -> list[str]:
    payload = profiled["payload"]
    if payload["kind"] == "sustained_session":
        summary = payload["summary"]
        header = " ".join(
            [
                "| Backend | Actual | Messages | Raw B |",
                "Wire B | Ratio | Saved | Enc ms | Dec ms |",
            ]
        )
        encode_backend = summary["encode_backend"]
        decode_backend = summary["decode_backend"]
        actual_backend = f"{encode_backend}/{decode_backend}"
        return [
            header,
            "|---|---|---:|---:|---:|---:|---:|---:|---:|",
            "| {backend} | {actual} | {messages} | {raw} | {wire} | "
            "{ratio}x | "
            "{saved}% | {enc} | {dec} |".format(
                backend=summary["requested_backend"],
                actual=actual_backend,
                messages=_fmt(summary["messages"], 0),
                raw=_fmt(summary["raw_bytes"], 0),
                wire=_fmt(summary["wire_bytes"], 0),
                ratio=_fmt(summary["ratio"], 2),
                saved=_fmt(summary["saved_percent"], 1),
                enc=_fmt(summary["encode_ms"], 2),
                dec=_fmt(summary["decode_ms"], 2),
            ),
        ]

    lines = [
        "| Codec | Actual | Framed B/ex | Ratio | Saved | " "CPU us/ex |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in payload["summary"]:
        lines.append(
            "| {codec} | {backend} | {bpe} | {ratio}x | {saved}% | "
            "{cpu} |".format(
                codec=row["codec"],
                backend=row["backend"],
                bpe=_fmt(row["framed_bytes_per_exchange"], 1),
                ratio=_fmt(row["framed_ratio"], 2),
                saved=_fmt(row["framed_wire_saved_percent"], 1),
                cpu=_fmt(row["codec_cpu_us_per_exchange"], 1),
            )
        )
    return lines


def _render_stat_rows(rows: Iterable[Mapping[str, Any]]) -> list[str]:
    lines = [
        "| Function | Calls | Self ms | Cum ms | Cum % |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in rows:
        label = f"{row['file']}:{row['line']} {row['function']}"
        lines.append(
            "| `{label}` | {calls} | {self_ms} | {cum_ms} | "
            "{cum_pct}% |".format(
                label=label,
                calls=_fmt(row["total_calls"], 0),
                self_ms=_fmt(row["self_ms"], 2),
                cum_ms=_fmt(row["cumulative_ms"], 2),
                cum_pct=_fmt(row["cumulative_percent_of_elapsed"], 1),
            )
        )
    return lines


def render_markdown(report: Mapping[str, Any]) -> str:
    """Render a compact hot-path profile report."""

    settings = report["settings"]
    native_status = report["native_status"]
    system = report["platform"]["system"]
    machine = report["platform"]["machine"]
    platform_line = f"- Platform: `{system} {machine}`"
    lines = [
        "# AIWire Hot Path Profile",
        "",
        "This report uses Python cProfile to identify CPU-heavy "
        "functions in the "
        "sustained-session and fixture codec paths.",
        "",
        f"- Status: `{'ok' if report['ok'] else 'failed'}`",
        f"- Mode: `{settings['mode']}`",
        f"- Backend: `{settings['backend']}`",
        platform_line,
        f"- Native available: `{native_status['available']}`",
        "",
    ]
    if report.get("skipped"):
        lines.extend([f"Skipped: {report.get('reason')}", ""])
        return "\n".join(lines)

    for profiled in report["profiles"]:
        lines.extend(
            [
                f"## {profiled['name']}",
                "",
                f"- Elapsed: `{_fmt(profiled['elapsed_ms'], 2)} ms`",
                f"- Calls: `{_fmt(profiled['total_calls'], 0)}`",
                "",
                "### Payload",
                "",
                *_render_payload_summary(profiled),
                "",
                "### Top Cumulative Time",
                "",
                *_render_stat_rows(profiled["top_cumulative"]),
                "",
                "### Top Self Time",
                "",
                *_render_stat_rows(profiled["top_self_time"]),
                "",
            ]
        )
    if report["errors"]:
        error_lines = []
        for error in report["errors"]:
            error_lines.append(f"- `{error['profile']}`: {error['error']}")
        lines.extend(
            [
                "## Errors",
                "",
                *error_lines,
                "",
            ]
        )
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    allow_missing_help = " ".join(
        [
            "Return ok=true and mark native skipped when",
            "libaura_aiwire is absent.",
        ]
    )
    parser.add_argument("--mode", choices=PROFILE_MODES, default="both")
    parser.add_argument(
        "--backend",
        choices=BENCHMARK_BACKENDS,
        default="python",
    )
    parser.add_argument(
        "--profile",
        choices=tuple(BENCHMARK_PROFILES),
        default="small",
        help="Benchmark size profile. --messages overrides the profile count.",
    )
    parser.add_argument("--corpus", choices=("delta",), default="delta")
    parser.add_argument("--messages", type=int, default=128)
    parser.add_argument("--seed", type=int, default=1729)
    parser.add_argument(
        "--aiwire-level",
        type=int,
        default=AI_WIRE_DEFAULT_LEVEL,
    )
    parser.add_argument("--peers", type=int, default=4)
    parser.add_argument(
        "--fixture-corpus",
        type=Path,
        default=DEFAULT_FIXTURE_PATH,
    )
    parser.add_argument("--codecs", default="raw,zlib,aiwire,aitoken_aiwire")
    parser.add_argument(
        "--top",
        type=int,
        default=20,
        help="number of cProfile rows to keep",
    )
    parser.add_argument(
        "--allow-missing-native",
        action="store_true",
        help=allow_missing_help,
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="json",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = profile_aiwire_hot_path(
            mode=args.mode,
            backend=args.backend,
            profile=args.profile,
            corpus=args.corpus,
            messages=args.messages,
            seed=args.seed,
            level=args.aiwire_level,
            peers=args.peers,
            fixture_path=args.fixture_corpus,
            codecs=_split_csv(args.codecs),
            top_limit=args.top,
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
