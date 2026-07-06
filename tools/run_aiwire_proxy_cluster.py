#!/usr/bin/env python3
"""Run cross-machine AIWire proxy benchmarks through SSH-managed edge sidecars."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import math
import shlex
import socket
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from aura_compression.ai_wire import AI_WIRE_DEFAULT_LEVEL
from aura_compression.aiwire_proxy_benchmark import (
    FIXTURE_VARIATION_PROFILES,
    run_proxy_ingress_benchmark,
)

DEFAULT_FIXTURE_CORPUS = "fixtures/aiwire_sessions/public_session_corpus_v1.json"
PROXY_CLUSTER_SCHEMA = "aura.aiwire.proxy_cluster_benchmark.v1"
SSH_PUBLIC_KEY_PREFIXES = (
    "ssh-ed25519",
    "ssh-rsa",
    "ecdsa-sha2-",
    "sk-ecdsa-sha2-",
    "sk-ssh-ed25519",
)


@dataclass(frozen=True)
class ProxyClusterTarget:
    """One remote edge host used by the proxy cluster runner."""

    label: str
    ssh_host: str
    proxy_host: str
    egress_port: int
    upstream_port: int
    ssh_port: int | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _quote(value: str | Path) -> str:
    return shlex.quote(str(value))


def _shell_command(parts: list[str]) -> str:
    return shlex.join(parts)


def _quote_remote_path(value: str | Path) -> str:
    text = str(value)
    if text == "~":
        return "$HOME"
    if text.startswith("~/"):
        suffix = text[2:]
        return "$HOME" if not suffix else f"$HOME/{_quote(suffix)}"
    return _quote(text)


def _proxy_host_from_ssh_host(ssh_host: str) -> str:
    host = ssh_host.rsplit("@", 1)[-1]
    if host.count(":") == 1:
        host = host.rsplit(":", 1)[0]
    return host


def parse_target(
    spec: str,
    *,
    index: int = 0,
    default_egress_port: int = 9200,
    default_upstream_port: int = 9300,
) -> ProxyClusterTarget:
    """Parse label=ssh-host[,proxy_host=host,egress_port=N,upstream_port=N]."""

    fields = [field.strip() for field in spec.split(",") if field.strip()]
    if not fields:
        raise ValueError("empty target specification")
    head = fields[0]
    if "=" in head:
        label, ssh_host = head.split("=", 1)
        label = label.strip()
        ssh_host = ssh_host.strip()
    else:
        ssh_host = head
        label = f"edge-{index + 1}"
    if not label or not ssh_host:
        raise ValueError(f"invalid target specification: {spec!r}")

    options: dict[str, str] = {}
    for field in fields[1:]:
        if "=" not in field:
            raise ValueError(f"target option must be key=value: {field!r}")
        key, value = field.split("=", 1)
        options[key.strip()] = value.strip()

    proxy_host = (
        options.get("proxy_host") or options.get("host") or _proxy_host_from_ssh_host(ssh_host)
    )
    ssh_port = int(options["ssh_port"]) if "ssh_port" in options else None
    egress_port = int(options.get("egress_port", default_egress_port + index))
    upstream_port = int(options.get("upstream_port", default_upstream_port + index))
    return ProxyClusterTarget(
        label=label,
        ssh_host=ssh_host,
        proxy_host=proxy_host,
        egress_port=egress_port,
        upstream_port=upstream_port,
        ssh_port=ssh_port,
    )


def _read_targets_file(path: str | Path) -> list[str]:
    specs = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            specs.append(stripped)
    return specs


def collect_targets(args: argparse.Namespace) -> list[ProxyClusterTarget]:
    specs = list(args.target or [])
    if args.targets_file:
        specs.extend(_read_targets_file(args.targets_file))
    if not specs:
        raise ValueError("provide at least one --target or --targets-file entry")
    return [
        parse_target(
            spec,
            index=index,
            default_egress_port=args.egress_port_base,
            default_upstream_port=args.upstream_port_base,
        )
        for index, spec in enumerate(specs)
    ]


def _remote_module_command(
    *,
    remote_root: str,
    remote_python: str,
    module: str,
    args: list[str],
) -> str:
    command = shlex.join([remote_python, "-m", module, *args])
    return f"cd {_quote_remote_path(remote_root)} && PYTHONPATH=src {command}"


def _background_command(*, run_dir: str, name: str, inner: str) -> str:
    stdout = f"{run_dir}/{name}.stdout"
    stderr = f"{run_dir}/{name}.stderr"
    pid = f"{run_dir}/{name}.pid"
    return (
        f"mkdir -p {_quote(run_dir)} && "
        f"(nohup sh -lc {_quote(inner)} > {_quote(stdout)} 2> {_quote(stderr)} "
        f"< /dev/null & echo $! > {_quote(pid)})"
    )


def _fetch_json_command(path: str) -> str:
    quoted = _quote(path)
    return f"for i in $(seq 1 100); do [ -s {quoted} ] && break; sleep 0.2; done; cat {quoted}"


def _cleanup_command(run_dir: str) -> str:
    return (
        "for name in egress fixture; do "
        f"pidfile={_quote(run_dir)}/$name.pid; "
        'if [ -f "$pidfile" ]; then kill "$(cat "$pidfile")" 2>/dev/null || true; fi; '
        "done"
    )


def build_target_plan(
    target: ProxyClusterTarget,
    args: argparse.Namespace,
    *,
    run_id: str,
    output_dir: Path,
) -> dict[str, Any]:
    remote_run_dir = f"{args.remote_run_dir.rstrip('/')}/{run_id}/{target.label}"
    local_dir = output_dir / target.label
    local_ingress_metrics = local_dir / "ingress.metrics.json"
    local_benchmark = local_dir / "benchmark.json"
    local_replay = local_dir / "ingress.replay.jsonl"
    remote_fixture_metrics = f"{remote_run_dir}/fixture.metrics.json"
    remote_egress_metrics = f"{remote_run_dir}/egress.metrics.json"

    fixture_args = [
        "--listen-host",
        "127.0.0.1",
        "--listen-port",
        str(target.upstream_port),
        "--fixture-corpus",
        args.fixture_corpus,
        "--fixture-variation-profile",
        args.fixture_variation_profile,
        "--fixture-peer-label",
        target.label,
        "--connections",
        "1",
        "--metrics-output",
        remote_fixture_metrics,
    ]
    egress_args = [
        "egress",
        "--listen-host",
        "0.0.0.0",
        "--listen-port",
        str(target.egress_port),
        "--upstream-host",
        "127.0.0.1",
        "--upstream-port",
        str(target.upstream_port),
        "--backend",
        args.backend,
        "--level",
        str(args.level),
        "--connections",
        "1",
        "--metrics-output",
        remote_egress_metrics,
    ]
    fixture_inner = _remote_module_command(
        remote_root=args.remote_root,
        remote_python=args.remote_python,
        module="aura_compression.cli.proxy_fixture_server",
        args=fixture_args,
    )
    egress_inner = _remote_module_command(
        remote_root=args.remote_root,
        remote_python=args.remote_python,
        module="aura_compression.cli.proxy",
        args=egress_args,
    )
    return {
        "target": asdict(target),
        "remote_run_dir": remote_run_dir,
        "local_dir": str(local_dir),
        "artifacts": {
            "local_benchmark": str(local_benchmark),
            "local_ingress_metrics": str(local_ingress_metrics),
            "local_replay_log": str(local_replay),
            "remote_fixture_metrics": remote_fixture_metrics,
            "remote_egress_metrics": remote_egress_metrics,
        },
        "commands": {
            "start_fixture": _background_command(
                run_dir=remote_run_dir,
                name="fixture",
                inner=fixture_inner,
            ),
            "start_egress": _background_command(
                run_dir=remote_run_dir,
                name="egress",
                inner=egress_inner,
            ),
            "fetch_fixture_metrics": _fetch_json_command(remote_fixture_metrics),
            "fetch_egress_metrics": _fetch_json_command(remote_egress_metrics),
            "cleanup": _cleanup_command(remote_run_dir),
        },
    }


def build_plan(args: argparse.Namespace, targets: list[ProxyClusterTarget]) -> dict[str, Any]:
    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = Path(args.output_dir or f"/tmp/aura-proxy-cluster-{run_id}")
    return {
        "schema": PROXY_CLUSTER_SCHEMA,
        "mode": "plan",
        "dry_run": not args.run,
        "run_id": run_id,
        "created_at_utc": _utc_now(),
        "coordinator_label": args.coordinator_label,
        "seconds": args.seconds,
        "max_exchanges": args.max_exchanges,
        "backend": args.backend,
        "level": args.level,
        "modeled_link_mbps": args.modeled_link_mbps,
        "fixture_corpus": args.fixture_corpus,
        "fixture_variation_profile": args.fixture_variation_profile,
        "target_parallelism": args.target_parallelism,
        "output_dir": str(output_dir),
        "targets": [
            build_target_plan(target, args, run_id=run_id, output_dir=output_dir)
            for target in targets
        ],
    }


def _ssh_connect_timeout_value(args: argparse.Namespace) -> str:
    return str(max(1, math.ceil(float(args.ssh_connect_timeout))))


def _ssh_command_prefix(target: ProxyClusterTarget, args: argparse.Namespace) -> list[str]:
    command = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        f"ConnectTimeout={_ssh_connect_timeout_value(args)}",
    ]
    if target.ssh_port is not None:
        command.extend(["-p", str(target.ssh_port)])
    command.append(target.ssh_host)
    return command


def _ssh_config_command(target: ProxyClusterTarget, args: argparse.Namespace) -> list[str]:
    command = [
        "ssh",
        "-G",
        "-o",
        "BatchMode=yes",
        "-o",
        f"ConnectTimeout={_ssh_connect_timeout_value(args)}",
    ]
    if target.ssh_port is not None:
        command.extend(["-p", str(target.ssh_port)])
    command.append(target.ssh_host)
    return command


def _run_capture(
    command: list[str], *, timeout: float, check: bool = False
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=check,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _tail(value: str, *, limit: int = 1200) -> str:
    return value[-limit:] if len(value) > limit else value


def _parse_ssh_g_output(output: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for line in output.splitlines():
        if not line.strip() or " " not in line:
            continue
        key, value = line.split(None, 1)
        if key in {"hostname", "port", "user"}:
            parsed[key] = value.strip()
    return parsed


def _ssh_config_probe(target: ProxyClusterTarget, args: argparse.Namespace) -> dict[str, Any]:
    try:
        completed = _run_capture(
            _ssh_config_command(target, args),
            timeout=args.ssh_connect_timeout,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "command": exc.cmd,
            "error": f"ssh -G timed out after {args.ssh_connect_timeout}s",
        }

    result: dict[str, Any] = {
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
    }
    if completed.returncode == 0:
        parsed = _parse_ssh_g_output(completed.stdout)
        result.update(
            {
                "hostname": parsed.get("hostname", _proxy_host_from_ssh_host(target.ssh_host)),
                "port": int(parsed.get("port", target.ssh_port or 22)),
                "user": parsed.get("user"),
            }
        )
    else:
        result["stderr"] = _tail(completed.stderr)
    return result


def _tcp_probe(host: str, port: int, timeout: float) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            pass
    except OSError as exc:
        return {
            "ok": False,
            "host": host,
            "port": port,
            "elapsed_ms": (time.perf_counter() - started) * 1000,
            "error": str(exc),
        }
    return {
        "ok": True,
        "host": host,
        "port": port,
        "elapsed_ms": (time.perf_counter() - started) * 1000,
    }


def _ssh_auth_probe(target: ProxyClusterTarget, args: argparse.Namespace) -> dict[str, Any]:
    try:
        completed = _run_capture(
            [*_ssh_command_prefix(target, args), "printf AURA_PROXY_PREFLIGHT_OK"],
            timeout=args.ssh_timeout,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "command": exc.cmd,
            "error": f"ssh auth probe timed out after {args.ssh_timeout}s",
        }

    stdout = completed.stdout.strip()
    return {
        "ok": completed.returncode == 0 and stdout == "AURA_PROXY_PREFLIGHT_OK",
        "returncode": completed.returncode,
        "stdout": stdout,
        "stderr": _tail(completed.stderr),
    }


def _remote_preflight_command(args: argparse.Namespace) -> str:
    code = """
import json
import pathlib
import platform
import sys

fixture_corpus = pathlib.Path(__AURA_FIXTURE_CORPUS__)
if not fixture_corpus.is_absolute():
    fixture_corpus = pathlib.Path.cwd() / fixture_corpus

result = {
    "python": platform.python_version(),
    "cwd": str(pathlib.Path.cwd()),
    "fixture_corpus": str(fixture_corpus),
    "fixture_exists": fixture_corpus.exists(),
    "aura_import_ok": False,
    "native_status": None,
    "errors": [],
}

try:
    import aura_compression  # noqa: F401
    from aura_compression.ai_wire import aiwire_native_status

    result["aura_import_ok"] = True
    result["native_status"] = aiwire_native_status().as_dict()
except Exception as exc:
    result["errors"].append(f"aura import/native status failed: {exc}")

if not result["fixture_exists"]:
    result["errors"].append("fixture corpus not found")

if __AURA_BACKEND__ == "native":
    native_status = result.get("native_status") or {}
    if not native_status.get("available"):
        result["errors"].append("native AIWire backend is not available")
    if native_status.get("dictionary_matches_python") is not True:
        result["errors"].append("native AIWire dictionary does not match Python dictionary")

result["ok"] = not result["errors"]
print(json.dumps(result, sort_keys=True))
""".replace("__AURA_FIXTURE_CORPUS__", repr(args.fixture_corpus)).replace(
        "__AURA_BACKEND__", repr(args.backend)
    )
    command = shlex.join([args.remote_python, "-c", code])
    return f"cd {_quote_remote_path(args.remote_root)} && PYTHONPATH=src {command}"


def _remote_environment_probe(
    target: ProxyClusterTarget, args: argparse.Namespace
) -> dict[str, Any]:
    try:
        completed = _run_capture(
            [*_ssh_command_prefix(target, args), _remote_preflight_command(args)],
            timeout=args.ssh_timeout,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "command": exc.cmd,
            "error": f"remote environment probe timed out after {args.ssh_timeout}s",
        }

    result: dict[str, Any] = {
        "ok": False,
        "returncode": completed.returncode,
        "stderr": _tail(completed.stderr),
    }
    if completed.returncode != 0:
        result["stdout"] = _tail(completed.stdout)
        return result
    try:
        parsed = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        result["stdout"] = _tail(completed.stdout)
        result["error"] = f"remote preflight returned invalid JSON: {exc}"
        return result
    return parsed


def _preflight_target(target_plan: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    target = ProxyClusterTarget(**target_plan["target"])
    errors: list[str] = []
    ssh_config = _ssh_config_probe(target, args)
    ssh_host = str(ssh_config.get("hostname") or _proxy_host_from_ssh_host(target.ssh_host))
    ssh_port = int(ssh_config.get("port") or target.ssh_port or 22)
    if not ssh_config.get("ok"):
        errors.append("ssh config could not be resolved")

    tcp = _tcp_probe(ssh_host, ssh_port, args.ssh_connect_timeout)
    if not tcp.get("ok"):
        errors.append("ssh tcp port is not reachable")

    auth = {"ok": False, "skipped": "ssh tcp port is not reachable"}
    remote = {"ok": False, "skipped": "ssh auth did not pass"}
    if tcp.get("ok"):
        auth = _ssh_auth_probe(target, args)
        if not auth.get("ok"):
            errors.append("ssh batch authentication failed")
        else:
            remote = _remote_environment_probe(target, args)
            if not remote.get("ok"):
                errors.append("remote AURA environment check failed")

    return {
        "target": asdict(target),
        "ok": not errors,
        "errors": errors,
        "ssh_config": ssh_config,
        "tcp": tcp,
        "ssh_auth": auth,
        "remote_environment": remote,
    }


def run_preflight(plan: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.target_parallelism) as executor:
        futures = [
            executor.submit(_preflight_target, target_plan, args) for target_plan in plan["targets"]
        ]
        targets = [future.result() for future in concurrent.futures.as_completed(futures)]
    targets.sort(key=lambda row: row["target"]["label"])
    return {
        "ok": all(row["ok"] for row in targets),
        "checked_at_utc": _utc_now(),
        "targets": targets,
    }


def _read_public_key(path: str | Path) -> tuple[Path, str]:
    public_key_path = Path(path).expanduser()
    key = public_key_path.read_text(encoding="utf-8").strip()
    if "\n" in key or "\r" in key:
        raise ValueError(f"public key must be one line: {public_key_path}")
    if "PRIVATE" in key:
        raise ValueError(f"refusing to use a private key file: {public_key_path}")
    if not key.startswith(SSH_PUBLIC_KEY_PREFIXES):
        raise ValueError(f"unsupported or invalid SSH public key: {public_key_path}")
    return public_key_path, key


def _ssh_copy_id_command(target: ProxyClusterTarget, public_key_path: Path) -> str:
    command = ["ssh-copy-id", "-i", str(public_key_path)]
    if target.ssh_port is not None:
        command.extend(["-p", str(target.ssh_port)])
    command.append(target.ssh_host)
    return _shell_command(command)


def _authorized_keys_console_command(public_key: str) -> str:
    quoted_key = _quote(public_key)
    return (
        'umask 077; mkdir -p "$HOME/.ssh"; touch "$HOME/.ssh/authorized_keys"; '
        f'grep -qxF {quoted_key} "$HOME/.ssh/authorized_keys" || '
        f"printf '%s\\n' {quoted_key} >> \"$HOME/.ssh/authorized_keys\"; "
        'chmod 700 "$HOME/.ssh"; chmod 600 "$HOME/.ssh/authorized_keys"'
    )


def build_ssh_bootstrap(plan: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    public_key_path, public_key = _read_public_key(args.ssh_public_key)
    public_key_sha256 = hashlib.sha256(public_key.encode("utf-8")).hexdigest()
    return {
        "schema": "aura.aiwire.proxy_cluster_ssh_bootstrap.v1",
        "public_key_path": str(public_key_path),
        "public_key_sha256": public_key_sha256,
        "created_at_utc": _utc_now(),
        "dry_run": True,
        "targets": [
            {
                "target": item["target"],
                "ssh_copy_id_command": _ssh_copy_id_command(
                    ProxyClusterTarget(**item["target"]),
                    public_key_path,
                ),
                "console_authorized_keys_command": _authorized_keys_console_command(public_key),
                "post_check_command": _shell_command(
                    [
                        *_ssh_command_prefix(ProxyClusterTarget(**item["target"]), args),
                        "printf AURA_PROXY_PREFLIGHT_OK",
                    ]
                ),
            }
            for item in plan["targets"]
        ],
    }


def _ssh_capture(
    target: ProxyClusterTarget,
    args: argparse.Namespace,
    command: str,
    *,
    timeout: float,
) -> str:
    completed = subprocess.run(
        [*_ssh_command_prefix(target, args), command],
        check=True,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return completed.stdout


def _ssh_run(
    target: ProxyClusterTarget,
    args: argparse.Namespace,
    command: str,
    *,
    timeout: float,
) -> None:
    subprocess.run(
        [*_ssh_command_prefix(target, args), command],
        check=True,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _local_fixture_path(path: str) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else ROOT / candidate


def run_target(
    target_plan: dict[str, Any],
    args: argparse.Namespace,
) -> dict[str, Any]:
    target = ProxyClusterTarget(**target_plan["target"])
    commands = target_plan["commands"]
    local_dir = Path(target_plan["local_dir"])
    local_dir.mkdir(parents=True, exist_ok=True)
    artifacts = target_plan["artifacts"]
    started_at = _utc_now()
    try:
        _ssh_run(target, args, commands["start_fixture"], timeout=args.ssh_timeout)
        _ssh_run(target, args, commands["start_egress"], timeout=args.ssh_timeout)
        time.sleep(args.server_start_delay)
        benchmark = run_proxy_ingress_benchmark(
            egress_host=target.proxy_host,
            egress_port=target.egress_port,
            fixture_corpus_path=_local_fixture_path(args.fixture_corpus),
            fixture_variation_profile=args.fixture_variation_profile,
            fixture_peer_label=target.label,
            seconds=args.seconds,
            max_exchanges=args.max_exchanges,
            backend=args.backend,
            level=args.level,
            modeled_link_mbps=args.modeled_link_mbps,
            output=artifacts["local_benchmark"],
            replay_log_output=artifacts["local_replay_log"],
            ingress_metrics_output=artifacts["local_ingress_metrics"],
        )
        fixture_metrics = json.loads(
            _ssh_capture(
                target,
                args,
                commands["fetch_fixture_metrics"],
                timeout=args.ssh_timeout,
            )
        )
        egress_metrics = json.loads(
            _ssh_capture(
                target,
                args,
                commands["fetch_egress_metrics"],
                timeout=args.ssh_timeout,
            )
        )
    except BaseException:
        try:
            _ssh_run(target, args, commands["cleanup"], timeout=args.ssh_timeout)
        finally:
            raise

    return {
        "target": asdict(target),
        "started_at_utc": started_at,
        "ended_at_utc": _utc_now(),
        "verified": bool(benchmark.get("verified"))
        and fixture_metrics.get("exchanges") == benchmark.get("exchanges")
        and egress_metrics.get("exchanges") == benchmark.get("exchanges"),
        "benchmark": benchmark,
        "remote_fixture_metrics": fixture_metrics,
        "remote_egress_metrics": egress_metrics,
        "artifacts": artifacts,
    }


def _aggregate_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    exchanges = sum(int(row["benchmark"]["exchanges"]) for row in results)
    raw_framed = sum(int(row["benchmark"]["raw_framed_bytes"]) for row in results)
    tunnel_semantic = sum(int(row["benchmark"]["tunnel_semantic_framed_bytes"]) for row in results)
    tunnel_control = sum(int(row["benchmark"]["tunnel_control_framed_bytes"]) for row in results)
    ex_per_second = sum(float(row["benchmark"]["exchanges_per_second"]) for row in results)
    return {
        "targets": len(results),
        "verified_targets": sum(1 for row in results if row["verified"]),
        "exchanges": exchanges,
        "exchanges_per_second_group": ex_per_second,
        "raw_framed_bytes": raw_framed,
        "tunnel_semantic_framed_bytes": tunnel_semantic,
        "tunnel_control_framed_bytes": tunnel_control,
        "raw_framed_bytes_per_exchange": raw_framed / exchanges if exchanges else 0.0,
        "tunnel_semantic_framed_bytes_per_exchange": (
            tunnel_semantic / exchanges if exchanges else 0.0
        ),
        "tunnel_saved_percent": (
            100.0 * (1.0 - tunnel_semantic / raw_framed) if raw_framed else 0.0
        ),
        "bandwidth_capacity_gain": raw_framed / tunnel_semantic if tunnel_semantic else 0.0,
        "roundtrip_ms_p95_max": max(
            (float(row["benchmark"]["roundtrip_ms_p95"]) for row in results),
            default=0.0,
        ),
        "roundtrip_ms_p99_max": max(
            (float(row["benchmark"]["roundtrip_ms_p99"]) for row in results),
            default=0.0,
        ),
    }


def run_plan(plan: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    started_at = _utc_now()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.target_parallelism) as executor:
        futures = [
            executor.submit(run_target, target_plan, args) for target_plan in plan["targets"]
        ]
        results = [future.result() for future in concurrent.futures.as_completed(futures)]
    results.sort(key=lambda row: row["target"]["label"])
    return {
        **plan,
        "mode": "run",
        "dry_run": False,
        "started_at_utc": started_at,
        "ended_at_utc": _utc_now(),
        "results": results,
        "aggregate": _aggregate_results(results),
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# AIWire Proxy Cluster Benchmark",
        "",
        f"Run ID: `{report['run_id']}`",
        f"Fixture variation: `{report['fixture_variation_profile']}`",
        f"Backend: `{report['backend']}`",
        f"Seconds: `{report['seconds']}`",
        "",
    ]
    if report.get("dry_run"):
        ssh_bootstrap = report.get("ssh_bootstrap")
        if ssh_bootstrap:
            lines.extend(
                [
                    "## SSH Bootstrap",
                    "",
                    f"Public key path: `{ssh_bootstrap['public_key_path']}`",
                    f"Public key SHA256: `{ssh_bootstrap['public_key_sha256']}`",
                    "",
                    (
                        "Use `ssh-copy-id` when password SSH is available. "
                        "Use the console command from a local shell on the target "
                        "when SSH auth is not available yet."
                    ),
                    "",
                ]
            )
            for item in ssh_bootstrap["targets"]:
                target = item["target"]
                lines.extend(
                    [
                        f"### {target['label']}",
                        "",
                        "Password SSH path:",
                        "",
                        "```bash",
                        item["ssh_copy_id_command"],
                        "```",
                        "",
                        "Target console path:",
                        "",
                        "```bash",
                        item["console_authorized_keys_command"],
                        "```",
                        "",
                        "Post-check from the coordinator:",
                        "",
                        "```bash",
                        item["post_check_command"],
                        "```",
                        "",
                    ]
                )

        preflight = report.get("preflight")
        if preflight:
            lines.extend(
                [
                    "## Preflight",
                    "",
                    "| Target | SSH TCP | SSH auth | Remote env | Status |",
                    "|---|---|---|---|---|",
                ]
            )
            for item in preflight["targets"]:
                target = item["target"]
                lines.append(
                    f"| {target['label']} | {item['tcp'].get('ok')} | "
                    f"{item['ssh_auth'].get('ok')} | "
                    f"{item['remote_environment'].get('ok')} | "
                    f"{'ready' if item['ok'] else '; '.join(item['errors'])} |"
                )
            lines.extend(
                [
                    "",
                    (
                        "All targets are ready for `--run`."
                        if preflight["ok"]
                        else "Fix failed preflight checks before running sidecars."
                    ),
                    "",
                ]
            )
        lines.extend(
            [
                "## Plan",
                "",
                "| Target | SSH host | Proxy host | Egress | Upstream |",
                "|---|---|---|---:|---:|",
            ]
        )
        for item in report["targets"]:
            target = item["target"]
            lines.append(
                f"| {target['label']} | `{target['ssh_host']}` | `{target['proxy_host']}` | "
                f"{target['egress_port']} | {target['upstream_port']} |"
            )
        lines.append("")
        lines.append("Run again with `--run` to start remote fixture and egress sidecars.")
        return "\n".join(lines) + "\n"

    aggregate = report["aggregate"]
    lines.extend(
        [
            "## Aggregate",
            "",
            "| Targets | Exchanges | Group ex/s | Raw B/ex | AIWire B/ex | Saved | p95 max |",
            "|---:|---:|---:|---:|---:|---:|---:|",
            (
                f"| {aggregate['verified_targets']}/{aggregate['targets']} | "
                f"{aggregate['exchanges']:,} | "
                f"{aggregate['exchanges_per_second_group']:,.1f} | "
                f"{aggregate['raw_framed_bytes_per_exchange']:,.1f} | "
                f"{aggregate['tunnel_semantic_framed_bytes_per_exchange']:,.1f} | "
                f"{aggregate['tunnel_saved_percent']:.1f}% | "
                f"{aggregate['roundtrip_ms_p95_max']:.2f} ms |"
            ),
            "",
            "## Targets",
            "",
            "| Target | Exchanges | Ex/s | Raw B/ex | AIWire B/ex | Saved | p95 | Verified |",
            "|---|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for item in report["results"]:
        target = item["target"]
        benchmark = item["benchmark"]
        lines.append(
            f"| {target['label']} | {benchmark['exchanges']:,} | "
            f"{benchmark['exchanges_per_second']:,.1f} | "
            f"{benchmark['raw_framed_bytes_per_exchange']:,.1f} | "
            f"{benchmark['tunnel_semantic_framed_bytes_per_exchange']:,.1f} | "
            f"{benchmark['tunnel_saved_percent']:.1f}% | "
            f"{benchmark['roundtrip_ms_p95']:.2f} ms | {item['verified']} |"
        )
    return "\n".join(lines) + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        action="append",
        help=(
            "target as label=ssh-host[,proxy_host=host,egress_port=N,upstream_port=N]; "
            "repeat for each edge"
        ),
    )
    parser.add_argument("--targets-file")
    parser.add_argument("--run", action="store_true", help="execute the SSH plan")
    parser.add_argument(
        "--ssh-bootstrap",
        action="store_true",
        help="include dry-run SSH authorized_keys bootstrap commands in the report",
    )
    parser.add_argument(
        "--ssh-public-key",
        default="~/.ssh/id_ed25519.pub",
        help="public key used by --ssh-bootstrap",
    )
    parser.add_argument(
        "--preflight",
        action="store_true",
        help=(
            "check SSH config, TCP reachability, batch auth, remote AURA import, "
            "fixture corpus, and native backend readiness"
        ),
    )
    parser.add_argument("--run-id")
    parser.add_argument("--coordinator-label", default="z6")
    parser.add_argument("--remote-root", default="~/AURA")
    parser.add_argument("--remote-python", default="python3")
    parser.add_argument("--remote-run-dir", default="/tmp/aura-proxy-cluster")
    parser.add_argument("--output-dir")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--summary-output", type=Path)
    parser.add_argument("--fixture-corpus", default=DEFAULT_FIXTURE_CORPUS)
    parser.add_argument(
        "--fixture-variation-profile",
        choices=FIXTURE_VARIATION_PROFILES,
        default="cluster",
    )
    parser.add_argument("--seconds", type=float, default=60.0)
    parser.add_argument("--max-exchanges", type=int)
    parser.add_argument("--backend", choices=("python", "native", "auto"), default="native")
    parser.add_argument("--level", type=int, default=AI_WIRE_DEFAULT_LEVEL)
    parser.add_argument("--modeled-link-mbps", type=float, default=10.0)
    parser.add_argument("--egress-port-base", type=int, default=9200)
    parser.add_argument("--upstream-port-base", type=int, default=9300)
    parser.add_argument("--target-parallelism", type=int, default=4)
    parser.add_argument("--server-start-delay", type=float, default=1.0)
    parser.add_argument("--ssh-connect-timeout", type=float, default=5.0)
    parser.add_argument("--ssh-timeout", type=float, default=30.0)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    targets = collect_targets(args)
    plan = build_plan(args, targets)
    if args.ssh_bootstrap:
        plan = {**plan, "mode": "ssh_bootstrap", "ssh_bootstrap": build_ssh_bootstrap(plan, args)}
    if args.preflight:
        plan = {**plan, "mode": "preflight", "preflight": run_preflight(plan, args)}
        if args.run and not plan["preflight"]["ok"]:
            report = {**plan, "dry_run": True}
            exit_code = 2
        else:
            report = run_plan(plan, args) if args.run else plan
            exit_code = 0
    else:
        report = run_plan(plan, args) if args.run else plan
        exit_code = 0

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    if args.summary_output:
        args.summary_output.parent.mkdir(parents=True, exist_ok=True)
        args.summary_output.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
