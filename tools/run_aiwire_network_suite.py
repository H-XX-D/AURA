#!/usr/bin/env python3
"""Run AIWire stress benchmarks across realistic network profiles."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from aiwire_network_profiles import profiles_as_dicts, resolve_network_profiles


def _codec_count(codecs: str) -> int:
    return len([codec for codec in codecs.split(",") if codec.strip()])


def _run_profile(profile, args: argparse.Namespace, port: int) -> list[dict[str, Any]]:
    stress_tool = TOOLS / "stress_ai_wire_roundtrip_z6.py"
    server_cmd = [
        sys.executable,
        str(stress_tool),
        "server",
        "--host",
        args.host,
        "--port",
        str(port),
        "--runs",
        str(_codec_count(args.codecs)),
        "--backend",
        args.backend,
        "--link-mbps",
        str(profile.server_link_mbps),
        "--one-way-delay-ms",
        str(profile.server_one_way_delay_ms),
        "--jitter-ms",
        str(profile.server_jitter_ms),
        "--tail-pause-probability",
        str(profile.server_tail_pause_probability),
        "--tail-pause-ms",
        str(profile.server_tail_pause_ms),
        "--impairment-seed",
        str(args.impairment_seed),
    ]
    client_cmd = [
        sys.executable,
        str(stress_tool),
        "client",
        "--host",
        args.host,
        "--port",
        str(port),
        "--seconds",
        str(args.seconds),
        "--exchanges",
        str(args.exchanges),
        "--codecs",
        args.codecs,
        "--backend",
        args.backend,
        "--coordinator",
        args.coordinator,
        "--pipeline-window",
        str(profile.pipeline_window),
        "--agent-count",
        str(args.agent_count),
        "--link-mbps",
        str(profile.client_link_mbps),
        "--one-way-delay-ms",
        str(profile.client_one_way_delay_ms),
        "--jitter-ms",
        str(profile.client_jitter_ms),
        "--tail-pause-probability",
        str(profile.client_tail_pause_probability),
        "--tail-pause-ms",
        str(profile.client_tail_pause_ms),
        "--impairment-seed",
        str(args.impairment_seed),
        "--timeout",
        str(args.timeout),
    ]
    if args.discover_session_templates:
        client_cmd.append("--discover-session-templates")
    if args.force_session_templates:
        client_cmd.append("--force-session-templates")
    if args.allow_aiwire_fallback:
        client_cmd.append("--allow-aiwire-fallback")
    if args.fixture_corpus:
        fixture_args = [
            "--fixture-corpus",
            str(args.fixture_corpus),
            "--fixture-session-templates",
            args.fixture_session_templates,
        ]
        server_cmd.extend(fixture_args)
        client_cmd.extend(fixture_args)
        client_cmd.extend(
            [
                "--fixture-variation-profile",
                args.fixture_variation_profile,
            ]
        )
        if args.fixture_variation_profile != "none":
            client_cmd.extend(["--fixture-peer-label", profile.name])

    server = subprocess.Popen(
        server_cmd,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    time.sleep(args.server_start_delay)
    try:
        completed = subprocess.run(
            client_cmd,
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=args.timeout + args.seconds * max(2, _codec_count(args.codecs)) + 30,
        )
    except BaseException:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
        raise

    try:
        server_stdout, server_stderr = server.communicate(timeout=10)
    except subprocess.TimeoutExpired:
        server.kill()
        server_stdout, server_stderr = server.communicate()
        raise RuntimeError(
            f"server did not exit for profile {profile.name}; stderr:\n{server_stderr}"
        )
    if server.returncode != 0:
        raise RuntimeError(
            f"server failed for profile {profile.name} with {server.returncode}\n"
            f"stdout:\n{server_stdout}\nstderr:\n{server_stderr}"
        )

    payload = json.loads(completed.stdout)
    rows = payload.get("results", [])
    if not isinstance(rows, list):
        raise RuntimeError(f"client output for {profile.name} did not contain results")
    for row in rows:
        row["network_profile"] = profile.name
        row["network_description"] = profile.description
        row["profile_rtt_ms"] = profile.rtt_ms
        row["profile_pipeline_window"] = row.get("pipeline_window") or profile.pipeline_window
        row["profile_per_agent_pipeline_window"] = (
            row.get("per_agent_pipeline_window") or profile.pipeline_window
        )
    return rows


def run_suite(args: argparse.Namespace) -> dict[str, Any]:
    profiles = resolve_network_profiles(args.profiles)
    all_results: list[dict[str, Any]] = []
    for index, profile in enumerate(profiles):
        port = args.port_base + index
        print(f"[profile] {profile.name} on port {port}", file=sys.stderr)
        all_results.extend(_run_profile(profile, args, port))
    return {
        "suite": "aura-aiwire-realistic-network",
        "seconds": args.seconds,
        "exchanges": args.exchanges,
        "agent_count": args.agent_count,
        "codecs": [codec.strip() for codec in args.codecs.split(",") if codec.strip()],
        "requested_backend": args.backend,
        "coordinator": args.coordinator,
        "fixture_corpus": str(args.fixture_corpus) if args.fixture_corpus else "",
        "fixture_session_templates": (
            args.fixture_session_templates if args.fixture_corpus else ""
        ),
        "fixture_variation_profile": (
            args.fixture_variation_profile if args.fixture_corpus else ""
        ),
        "profiles": profiles_as_dicts(profiles),
        "results": all_results,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profiles",
        default="lan_10m,wifi_busy,lte_good,edge_mesh",
        help="comma-separated profile names, 'default', or 'all'",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port-base", type=int, default=9100)
    parser.add_argument("--seconds", type=float, default=5.0)
    parser.add_argument("--exchanges", type=int, default=20000)
    parser.add_argument("--codecs", default="raw,zlib,aiwire,aitoken_aiwire")
    parser.add_argument(
        "--backend",
        choices=("python", "native", "auto"),
        default="python",
        help=(
            "AIWire encode/decode backend for negotiated AIWire codecs. "
            "python is the reproducible default; native requires libaura_aiwire; "
            "auto uses native when available."
        ),
    )
    parser.add_argument(
        "--coordinator",
        choices=("threaded", "asyncio"),
        default="threaded",
        help=(
            "client-side stress coordinator. threaded preserves the historical "
            "path; asyncio uses one event loop for peer/frame fan-out."
        ),
    )
    parser.add_argument(
        "--agent-count",
        type=int,
        default=1,
        help="logical agents sharing each client session",
    )
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--server-start-delay", type=float, default=0.25)
    parser.add_argument("--impairment-seed", type=int, default=1729)
    parser.add_argument("--discover-session-templates", action="store_true")
    parser.add_argument("--force-session-templates", action="store_true")
    parser.add_argument("--allow-aiwire-fallback", action="store_true")
    parser.add_argument(
        "--fixture-corpus",
        type=Path,
        help="public AIWire fixture corpus to replay through every live TCP profile",
    )
    parser.add_argument(
        "--fixture-session-templates",
        choices=("none", "initial", "updated"),
        default="updated",
        help="fixture session-template set to advertise during AIWire handshakes",
    )
    parser.add_argument(
        "--fixture-variation-profile",
        choices=("none", "cluster"),
        default="none",
        help=(
            "deterministically vary fixture frames per profile to mimic working " "cluster traffic"
        ),
    )
    parser.add_argument("--output", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = run_suite(args)
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered)
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
