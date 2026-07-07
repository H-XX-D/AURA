#!/usr/bin/env python3
"""Compare AIWire threaded and asyncio coordinators on one n-ary fixture workload."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"

SCHEMA = "aura.aiwire.coordinator_comparison.v1"
DEFAULT_COORDINATORS = ("threaded", "asyncio")
DEFAULT_FIXTURE_CORPUS = ROOT / "fixtures" / "aiwire_sessions" / "public_session_corpus_v1.json"


def _split_csv(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split(",") if part.strip())


def _codec_count(codecs: Iterable[str]) -> int:
    return len(list(codecs))


def _percent_delta(baseline: float, candidate: float) -> float | None:
    if baseline == 0:
        return None
    return (candidate - baseline) / baseline * 100.0


def _target_specs(target_count: int, port_base: int, host: str) -> list[dict[str, Any]]:
    return [
        {
            "index": index,
            "label": f"local-{index}",
            "host": host,
            "port": port_base + index - 1,
        }
        for index in range(1, target_count + 1)
    ]


def _collect_servers(
    servers: Iterable[subprocess.Popen[str]],
    *,
    force_terminate: bool = False,
) -> list[dict[str, Any]]:
    outputs = []
    if force_terminate:
        for server in servers:
            if server.poll() is None:
                server.terminate()
    for server in servers:
        try:
            stdout, stderr = server.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            if server.poll() is None:
                server.terminate()
            try:
                stdout, stderr = server.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
                stdout, stderr = server.communicate()
        outputs.append(
            {
                "returncode": server.returncode,
                "stdout": stdout,
                "stderr": stderr,
            }
        )
    return outputs


def _start_servers(
    *,
    coordinator: str,
    target_specs: list[dict[str, Any]],
    args: argparse.Namespace,
    codecs: tuple[str, ...],
) -> list[subprocess.Popen[str]]:
    stress_tool = TOOLS / "stress_ai_wire_roundtrip_z6.py"
    runs = 1 + _codec_count(codecs) * max(1, args.session_shards)
    servers = []
    for target in target_specs:
        server_cmd = [
            sys.executable,
            str(stress_tool),
            "server",
            "--host",
            str(target["host"]),
            "--port",
            str(target["port"]),
            "--runs",
            str(runs),
            "--connection-workers",
            str(max(1, args.server_connection_workers)),
            "--backend",
            args.backend,
            "--link-mbps",
            str(args.link_mbps),
            "--one-way-delay-ms",
            str(args.one_way_delay_ms),
            "--jitter-ms",
            str(args.jitter_ms),
            "--tail-pause-probability",
            str(args.tail_pause_probability),
            "--tail-pause-ms",
            str(args.tail_pause_ms),
            "--impairment-seed",
            str(args.impairment_seed),
            "--fixture-corpus",
            str(args.fixture_corpus),
            "--fixture-session-templates",
            args.fixture_session_templates,
        ]
        server = subprocess.Popen(
            server_cmd,
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        servers.append(server)
    startup_delay = max(
        float(args.server_start_delay),
        2.0 if sys.platform == "win32" else 0.0,
    )
    time.sleep(startup_delay)
    return servers


def _looks_like_startup_refusal(stderr: str | None) -> bool:
    text = stderr or ""
    return "ConnectionRefusedError" in text or "ECONNREFUSED" in text or "WinError 1225" in text


def _run_nary_client(
    *,
    coordinator: str,
    target_specs: list[dict[str, Any]],
    args: argparse.Namespace,
    codecs: tuple[str, ...],
) -> dict[str, Any]:
    stress_tool = TOOLS / "stress_ai_wire_roundtrip_z6.py"
    client_cmd = [
        sys.executable,
        str(stress_tool),
        "nary-client",
        "--seconds",
        str(args.seconds),
        "--exchanges",
        str(args.exchanges),
        "--codecs",
        ",".join(codecs),
        "--coordinator",
        coordinator,
        "--backend",
        args.backend,
        "--link-mbps",
        str(args.link_mbps),
        "--one-way-delay-ms",
        str(args.one_way_delay_ms),
        "--jitter-ms",
        str(args.jitter_ms),
        "--tail-pause-probability",
        str(args.tail_pause_probability),
        "--tail-pause-ms",
        str(args.tail_pause_ms),
        "--impairment-seed",
        str(args.impairment_seed),
        "--agent-count",
        str(args.agent_count),
        "--pipeline-window",
        str(args.pipeline_window),
        "--session-shards",
        str(args.session_shards),
        "--target-parallelism",
        str(args.target_parallelism),
        "--timeout",
        str(args.timeout),
        "--fixture-corpus",
        str(args.fixture_corpus),
        "--fixture-session-templates",
        args.fixture_session_templates,
        "--fixture-variation-profile",
        args.fixture_variation_profile,
        "--force-session-templates",
    ]
    for target in target_specs:
        label = str(target["label"])
        endpoint = f"{target['host']}:{target['port']}"
        client_cmd.extend(["--target", f"{label}={endpoint}"])
    max_attempts = 4 if sys.platform == "win32" else 2
    completed: subprocess.CompletedProcess[str] | None = None
    for attempt in range(max_attempts):
        try:
            completed = subprocess.run(
                client_cmd,
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
                timeout=args.timeout + args.seconds * max(2, _codec_count(codecs)) + 30,
            )
            break
        except subprocess.CalledProcessError as exc:
            if attempt + 1 < max_attempts and _looks_like_startup_refusal(exc.stderr):
                time.sleep(max(0.25, float(args.server_start_delay)) * (attempt + 1))
                continue
            raise RuntimeError(
                "n-ary client failed for coordinator "
                f"{coordinator!r} with exit code {exc.returncode}\n"
                f"stdout:\n{exc.stdout or ''}\n"
                f"stderr:\n{exc.stderr or ''}"
            ) from exc
    if completed is None:
        raise RuntimeError(f"n-ary client did not run for coordinator {coordinator!r}")
    payload = json.loads(completed.stdout)
    if not isinstance(payload, dict):
        raise RuntimeError(
            f"n-ary client returned JSON that is not an object for coordinator {coordinator!r}"
        )
    return dict(payload)


def _summary_for_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    aggregate = []
    observed_eps_by_codec: dict[str, float] = {}
    for row in payload.get("results", []):
        codec = str(row["codec"])
        observed_eps_by_codec[codec] = observed_eps_by_codec.get(codec, 0.0) + float(
            row["exchanges_per_second"]
        )
    for row in payload.get("aggregate", []):
        codec = str(row["codec"])
        deadline_eps = float(row["deadline_exchanges_per_second"])
        aggregate.append(
            {
                "codec": codec,
                "deadline_completed_exchanges": row["deadline_completed_exchanges"],
                "deadline_exchanges_per_second": row["deadline_exchanges_per_second"],
                "observed_exchanges_per_second": (
                    deadline_eps if deadline_eps else observed_eps_by_codec.get(codec, 0.0)
                ),
                "framed_bytes_per_exchange": row["framed_bytes_per_exchange"],
                "framed_wire_saved_percent": row["framed_wire_saved_percent"],
                "roundtrip_ms_p95_avg": row["roundtrip_ms_p95_avg"],
                "roundtrip_ms_p95_max": row["roundtrip_ms_p95_max"],
                "bandwidth_utilization_percent": row["bandwidth_utilization_percent"],
                "verified": row["verified"],
            }
        )
    return {
        "coordinator": payload["coordinator"],
        "participant_count": payload["participant_count"],
        "remote_peer_count": payload["remote_peer_count"],
        "session_shards_per_target": payload["session_shards_per_target"],
        "total_replay_sessions": payload["total_replay_sessions"],
        "requested_backend": payload["requested_backend"],
        "nary_negotiation_accepted": payload["nary_negotiation"]["accepted"],
        "aggregate": aggregate,
        "verified": all(bool(row.get("verified")) for row in payload.get("results", [])),
    }


def _aggregate_by_codec(summary: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {str(row["codec"]): row for row in summary["aggregate"]}


def _delta_rows(summaries: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    if len(summaries) < 2:
        return []
    baseline = summaries[0]
    baseline_by_codec = _aggregate_by_codec(baseline)
    deltas: list[dict[str, Any]] = []
    for candidate in summaries[1:]:
        candidate_by_codec = _aggregate_by_codec(candidate)
        for codec, base_row in baseline_by_codec.items():
            candidate_row = candidate_by_codec.get(codec)
            if candidate_row is None:
                continue
            deltas.append(
                {
                    "baseline_coordinator": baseline["coordinator"],
                    "candidate_coordinator": candidate["coordinator"],
                    "codec": codec,
                    "completed_delta_percent": _percent_delta(
                        float(base_row["deadline_completed_exchanges"]),
                        float(candidate_row["deadline_completed_exchanges"]),
                    ),
                    "eps_delta_percent": _percent_delta(
                        float(base_row["observed_exchanges_per_second"]),
                        float(candidate_row["observed_exchanges_per_second"]),
                    ),
                    "p95_avg_delta_percent": _percent_delta(
                        float(base_row["roundtrip_ms_p95_avg"]),
                        float(candidate_row["roundtrip_ms_p95_avg"]),
                    ),
                    "framed_bytes_delta_percent": _percent_delta(
                        float(base_row["framed_bytes_per_exchange"]),
                        float(candidate_row["framed_bytes_per_exchange"]),
                    ),
                    "utilization_delta_points": float(
                        candidate_row["bandwidth_utilization_percent"]
                    )
                    - float(base_row["bandwidth_utilization_percent"]),
                }
            )
    return deltas


def run_coordinator_comparison(args: argparse.Namespace) -> dict[str, Any]:
    coordinators = _split_csv(args.coordinators)
    codecs = _split_csv(args.codecs)
    if not coordinators:
        raise ValueError("at least one coordinator is required")
    if not codecs:
        raise ValueError("at least one codec is required")
    if args.target_count < 1:
        raise ValueError("target-count must be at least 1")
    targets = _target_specs(args.target_count, args.port_base, args.host)
    runs = []
    summaries = []
    for index, coordinator in enumerate(coordinators):
        shifted_targets = [
            {
                **target,
                "port": int(target["port"]) + index * max(1, args.target_count),
            }
            for target in targets
        ]
        print(
            f"[coordinator] {coordinator} on ports "
            f"{','.join(str(target['port']) for target in shifted_targets)}",
            file=sys.stderr,
        )
        servers = _start_servers(
            coordinator=coordinator,
            target_specs=shifted_targets,
            args=args,
            codecs=codecs,
        )
        try:
            payload = _run_nary_client(
                coordinator=coordinator,
                target_specs=shifted_targets,
                args=args,
                codecs=codecs,
            )
            server_outputs = _collect_servers(servers)
        except BaseException:
            server_outputs = _collect_servers(servers, force_terminate=True)
            raise
        failed_servers = [output for output in server_outputs if output["returncode"] != 0]
        if failed_servers:
            raise RuntimeError(f"{coordinator} server failed: {failed_servers!r}")
        summary = _summary_for_payload(payload)
        runs.append(
            {
                "coordinator": coordinator,
                "targets": shifted_targets,
                "summary": summary,
                "payload": payload,
            }
        )
        summaries.append(summary)

    return {
        "schema": SCHEMA,
        "ok": all(bool(summary["verified"]) for summary in summaries),
        "settings": {
            "coordinators": list(coordinators),
            "host": args.host,
            "port_base": args.port_base,
            "target_count": args.target_count,
            "seconds": args.seconds,
            "exchanges": args.exchanges,
            "codecs": list(codecs),
            "backend": args.backend,
            "agent_count": args.agent_count,
            "pipeline_window": args.pipeline_window,
            "session_shards": args.session_shards,
            "target_parallelism": args.target_parallelism,
            "link_mbps": args.link_mbps,
            "one_way_delay_ms": args.one_way_delay_ms,
            "jitter_ms": args.jitter_ms,
            "tail_pause_probability": args.tail_pause_probability,
            "tail_pause_ms": args.tail_pause_ms,
            "fixture_corpus": str(args.fixture_corpus),
            "fixture_session_templates": args.fixture_session_templates,
            "fixture_variation_profile": args.fixture_variation_profile,
        },
        "summaries": summaries,
        "deltas": _delta_rows(summaries),
        "runs": runs,
    }


def _fmt(value: Any, digits: int = 2) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# AIWire Coordinator Comparison",
        "",
        "This report runs the same local n-ary fixture replay workload with each "
        "coordinator mode and compares aggregate codec results.",
        "",
        "## Settings",
        "",
        f"- Backend: `{report['settings']['backend']}`",
        f"- Coordinators: `{', '.join(report['settings']['coordinators'])}`",
        f"- Targets: `{report['settings']['target_count']}`",
        f"- Codecs: `{', '.join(report['settings']['codecs'])}`",
        f"- Fixture: `{report['settings']['fixture_corpus']}`",
        "",
        "## Aggregate Results",
        "",
        "| Coordinator | Codec | Completed | Ex/s | Framed B/ex | p95 avg ms | Util % | Verified |",
        "|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for summary in report["summaries"]:
        for row in summary["aggregate"]:
            lines.append(
                "| "
                f"{summary['coordinator']} | "
                f"{row['codec']} | "
                f"{_fmt(row['deadline_completed_exchanges'], 0)} | "
                f"{_fmt(row['observed_exchanges_per_second'])} | "
                f"{_fmt(row['framed_bytes_per_exchange'])} | "
                f"{_fmt(row['roundtrip_ms_p95_avg'])} | "
                f"{_fmt(row['bandwidth_utilization_percent'])} | "
                f"{row['verified']} |"
            )
    lines.extend(
        [
            "",
            "## Deltas",
            "",
            "| Baseline | Candidate | Codec | Completed % | Ex/s % | p95 avg % | Framed B/ex % | Util pts |",
            "|---|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in report["deltas"]:
        lines.append(
            "| "
            f"{row['baseline_coordinator']} | "
            f"{row['candidate_coordinator']} | "
            f"{row['codec']} | "
            f"{_fmt(row['completed_delta_percent'])} | "
            f"{_fmt(row['eps_delta_percent'])} | "
            f"{_fmt(row['p95_avg_delta_percent'])} | "
            f"{_fmt(row['framed_bytes_delta_percent'])} | "
            f"{_fmt(row['utilization_delta_points'])} |"
        )
    lines.append("")
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coordinators", default="threaded,asyncio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port-base", type=int, default=9300)
    parser.add_argument("--target-count", type=int, default=2)
    parser.add_argument("--seconds", type=float, default=0.0)
    parser.add_argument("--exchanges", type=int, default=12)
    parser.add_argument("--codecs", default="raw,aiwire")
    parser.add_argument("--backend", choices=("python", "native", "auto"), default="python")
    parser.add_argument("--agent-count", type=int, default=4)
    parser.add_argument("--pipeline-window", type=int, default=2)
    parser.add_argument("--session-shards", type=int, default=1)
    parser.add_argument("--target-parallelism", type=int, default=4)
    parser.add_argument("--server-connection-workers", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--server-start-delay", type=float, default=0.35)
    parser.add_argument("--link-mbps", type=float, default=10.0)
    parser.add_argument("--one-way-delay-ms", type=float, default=0.0)
    parser.add_argument("--jitter-ms", type=float, default=0.0)
    parser.add_argument("--tail-pause-probability", type=float, default=0.0)
    parser.add_argument("--tail-pause-ms", type=float, default=0.0)
    parser.add_argument("--impairment-seed", type=int, default=1729)
    parser.add_argument("--fixture-corpus", type=Path, default=DEFAULT_FIXTURE_CORPUS)
    parser.add_argument(
        "--fixture-session-templates",
        choices=("none", "initial", "updated"),
        default="updated",
    )
    parser.add_argument(
        "--fixture-variation-profile",
        choices=("none", "cluster"),
        default="cluster",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = run_coordinator_comparison(args)
    rendered_json = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered_json)
    if args.markdown_output:
        args.markdown_output.write_text(render_markdown(report) + "\n")
    if args.format == "markdown":
        print(render_markdown(report))
    else:
        print(rendered_json, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
