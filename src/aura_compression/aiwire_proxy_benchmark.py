"""Local benchmark harness for the explicit AIWire sidecar proxy."""

from __future__ import annotations

import json
import queue
import socket
import statistics
import tempfile
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypeVar

from .ai_wire import AI_WIRE_DEFAULT_LEVEL, encode_ai_wire_message
from .ai_wire_fixtures import (
    build_aiwire_session_fixture_corpus,
    load_aiwire_session_fixture_corpus,
)
from .aiwire_proxy import (
    DEFAULT_MAX_FRAME_BYTES,
    BackendName,
    read_length_prefixed,
    run_egress_proxy,
    run_ingress_proxy,
    write_length_prefixed,
)
from .aiwire_replay_log import dumps_replay_log

AIWIRE_PROXY_BENCHMARK_SCHEMA = "aura.aiwire.proxy_benchmark.v1"
AIWIRE_PROXY_FIXTURE_SERVER_SCHEMA = "aura.aiwire.proxy_fixture_server.v1"
DEFAULT_PROXY_FIXTURE_PATH = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "aiwire_sessions"
    / "public_session_corpus_v1.json"
)
HOST = "127.0.0.1"
FIXTURE_VARIATION_PROFILES = ("none", "cluster")
T = TypeVar("T")


@dataclass(frozen=True)
class ProxyFixturePair:
    """One request/response pair replayed through the proxy."""

    session_id: str
    exchange_index: int
    request: bytes
    response: bytes


@dataclass(frozen=True)
class ProxyFixtureServerMetrics:
    """Metrics emitted by the raw upstream fixture responder."""

    schema: str
    started_at_utc: str
    ended_at_utc: str
    listen_host: str
    listen_port: int
    fixture_corpus: str
    fixture_corpus_source: str
    fixture_pair_count: int
    fixture_variation_profile: str
    fixture_peer_label: str
    max_connections: int | None
    accepted_connections: int
    exchanges: int
    raw_request_payload_bytes: int
    raw_response_payload_bytes: int


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _bound_listener(host: str = HOST, port: int = 0) -> tuple[socket.socket, int]:
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind((host, port))
    listener.listen()
    return listener, int(listener.getsockname()[1])


def _run_background(
    fn: Callable[[], T],
) -> tuple[threading.Thread, "queue.Queue[T | BaseException]"]:
    results: "queue.Queue[T | BaseException]" = queue.Queue()

    def target() -> None:
        try:
            results.put(fn())
        except BaseException as exc:  # pragma: no cover - surfaced by caller.
            results.put(exc)

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    return thread, results


def _background_result(
    thread: threading.Thread,
    results: "queue.Queue[T | BaseException]",
    *,
    timeout: float = 15.0,
) -> T:
    thread.join(timeout=timeout)
    if thread.is_alive():
        raise TimeoutError("background worker did not finish")
    result = results.get_nowait()
    if isinstance(result, BaseException):
        raise result
    return result


def _percentile(values: Sequence[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * percentile
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    weight = rank - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _fixture_peer_seed(peer_label: str) -> int:
    import hashlib

    digest = hashlib.sha256(peer_label.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def _cluster_variation_frame(
    frame: bytes,
    *,
    direction: str,
    peer_label: str,
    exchange_index: int,
) -> bytes:
    message = json.loads(frame)
    if not isinstance(message, dict):
        return frame

    roles = (
        "coordinator",
        "router",
        "planner",
        "tool-runner",
        "retriever",
        "critic",
        "memory-writer",
        "monitor",
    )
    workloads = (
        "mcp_tool_call",
        "a2a_task_delta",
        "openai_response_stream",
        "local_agent_trace",
        "handoff_review",
        "memory_commit",
        "artifact_update",
        "health_check",
    )
    zones = ("lab-a", "lab-b", "edge-mesh", "desk-lan")
    peer_seed = _fixture_peer_seed(peer_label)
    role = roles[(peer_seed + exchange_index) % len(roles)]
    workload = workloads[(peer_seed // 3 + exchange_index * 2) % len(workloads)]
    zone = zones[(peer_seed // 7 + exchange_index) % len(zones)]
    epoch = exchange_index // 36
    shard = (peer_seed + exchange_index * 7) % 17
    queue_depth = (peer_seed + exchange_index * 5) % 64
    token_window = 2048 + ((peer_seed + exchange_index * 97) % 14) * 512
    gpu_load = 18 + ((peer_seed + exchange_index * 11) % 79)
    memory_pressure = 21 + ((peer_seed + exchange_index * 13) % 67)
    route_from = peer_label if direction == "server_to_client" else "z6-coordinator"
    route_to = "z6-coordinator" if direction == "server_to_client" else peer_label

    message["cluster_context"] = {
        "schema": "aura.cluster.fixture_variation.v1",
        "profile": "working_cluster",
        "peer": peer_label,
        "role": role,
        "zone": zone,
        "workload": workload,
        "direction": direction,
        "route": {
            "from": route_from,
            "to": route_to,
            "lane": "semantic",
            "shard": shard,
        },
        "epoch": epoch,
        "sequence": exchange_index,
        "telemetry": {
            "queue_depth": queue_depth,
            "inflight_agents": 4 + ((peer_seed + exchange_index) % 29),
            "gpu_load_percent": gpu_load,
            "memory_pressure_percent": memory_pressure,
            "token_window": token_window,
            "retry_budget": 1 + ((peer_seed + exchange_index) % 4),
            "backpressure": queue_depth > 48 or memory_pressure > 78,
        },
    }
    metadata = message.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    metadata.update(
        {
            "cluster_peer": peer_label,
            "cluster_role": role,
            "cluster_epoch": epoch,
            "cluster_workload": workload,
        }
    )
    message["metadata"] = metadata

    if isinstance(message.get("trace_id"), str):
        message["trace_id"] = f"{message['trace_id']}:{peer_label}:e{epoch}:x{exchange_index % 997}"
    if "id" in message and isinstance(message["id"], (int, str)):
        message["id"] = f"{peer_label}-{message['id']}-{exchange_index % 997}"

    return _canonical_json_bytes(message)


def _vary_fixture_frame(
    frame: bytes,
    *,
    direction: str,
    fixture_variation_profile: str,
    fixture_peer_label: str,
    exchange_index: int,
) -> bytes:
    if fixture_variation_profile == "none":
        return frame
    if fixture_variation_profile == "cluster":
        return _cluster_variation_frame(
            frame,
            direction=direction,
            peer_label=fixture_peer_label,
            exchange_index=exchange_index,
        )
    raise ValueError(
        "fixture_variation_profile must be one of: " + ", ".join(FIXTURE_VARIATION_PROFILES)
    )


def build_proxy_fixture_pairs(
    corpus: Mapping[str, Any],
    *,
    fixture_variation_profile: str = "none",
    fixture_peer_label: str = "proxy-fixture",
) -> list[ProxyFixturePair]:
    """Extract ordered request/response replay pairs from an AIWire fixture corpus."""

    pairs: list[ProxyFixturePair] = []
    sessions = corpus.get("sessions")
    if not isinstance(sessions, list):
        raise ValueError("fixture corpus is missing sessions")

    for session in sessions:
        if not isinstance(session, Mapping):
            continue
        session_id = str(session.get("session_id", "fixture-session"))
        events = session.get("events")
        if not isinstance(events, list):
            continue

        requests: dict[int, Mapping[str, Any]] = {}
        responses: dict[int, Mapping[str, Any]] = {}
        for event in events:
            if not isinstance(event, Mapping) or event.get("kind") != "message":
                continue
            exchange_index = int(event["exchange_index"])
            if event.get("direction") == "client_to_server":
                requests[exchange_index] = event
            elif event.get("direction") == "server_to_client":
                responses[exchange_index] = event

        for exchange_index in sorted(set(requests).intersection(responses)):
            variation_index = len(pairs)
            request_message = requests[exchange_index].get("message")
            response_message = responses[exchange_index].get("message")
            request = _vary_fixture_frame(
                encode_ai_wire_message(request_message),
                direction="client_to_server",
                fixture_variation_profile=fixture_variation_profile,
                fixture_peer_label=fixture_peer_label,
                exchange_index=variation_index,
            )
            response = _vary_fixture_frame(
                encode_ai_wire_message(response_message),
                direction="server_to_client",
                fixture_variation_profile=fixture_variation_profile,
                fixture_peer_label=fixture_peer_label,
                exchange_index=variation_index,
            )
            pairs.append(
                ProxyFixturePair(
                    session_id=session_id,
                    exchange_index=exchange_index,
                    request=request,
                    response=response,
                )
            )

    if not pairs:
        raise ValueError("fixture corpus did not contain request/response pairs")
    return pairs


def _load_fixture_corpus(path: Path) -> tuple[dict[str, Any], str]:
    if path.exists():
        return load_aiwire_session_fixture_corpus(path), "file"
    if path == DEFAULT_PROXY_FIXTURE_PATH:
        return build_aiwire_session_fixture_corpus(), "generated"
    raise FileNotFoundError(path)


def _fixture_responder(
    listener: socket.socket,
    *,
    pairs: Sequence[ProxyFixturePair],
    max_connections: int | None = 1,
    max_frame_bytes: int = DEFAULT_MAX_FRAME_BYTES,
) -> dict[str, Any]:
    accepted_connections = 0
    exchanges = 0
    raw_request_payload_bytes = 0
    raw_response_payload_bytes = 0
    with listener:
        while max_connections is None or accepted_connections < max_connections:
            conn, _addr = listener.accept()
            accepted_connections += 1
            with conn:
                while True:
                    try:
                        request = read_length_prefixed(
                            conn,
                            max_frame_bytes=max_frame_bytes,
                        )
                    except EOFError:
                        break
                    pair = pairs[exchanges % len(pairs)]
                    if request != pair.request:
                        raise AssertionError(
                            f"request payload mismatch at exchange {exchanges}; "
                            f"fixture={pair.session_id}:{pair.exchange_index}"
                        )
                    raw_request_payload_bytes += len(request)
                    raw_response_payload_bytes += len(pair.response)
                    write_length_prefixed(conn, pair.response)
                    exchanges += 1

    return {
        "accepted_connections": accepted_connections,
        "exchanges": exchanges,
        "raw_request_payload_bytes": raw_request_payload_bytes,
        "raw_response_payload_bytes": raw_response_payload_bytes,
    }


def run_proxy_fixture_server(
    *,
    listen_host: str = HOST,
    listen_port: int = 8765,
    fixture_corpus_path: str | Path = DEFAULT_PROXY_FIXTURE_PATH,
    fixture_variation_profile: str = "none",
    fixture_peer_label: str = "proxy-fixture",
    max_connections: int | None = 1,
    max_frame_bytes: int = DEFAULT_MAX_FRAME_BYTES,
    metrics_output: str | Path | None = None,
    ready_callback: Callable[[int], None] | None = None,
) -> ProxyFixtureServerMetrics:
    """Run a raw length-prefixed upstream responder for proxy benchmarks."""

    if max_connections is not None and max_connections <= 0:
        raise ValueError("max_connections must be positive when provided")
    started_at_utc = _utc_now()
    fixture_path = Path(fixture_corpus_path)
    corpus, fixture_corpus_source = _load_fixture_corpus(fixture_path)
    pairs = build_proxy_fixture_pairs(
        corpus,
        fixture_variation_profile=fixture_variation_profile,
        fixture_peer_label=fixture_peer_label,
    )
    listener, bound_port = _bound_listener(listen_host, listen_port)
    if ready_callback is not None:
        ready_callback(bound_port)
    responder = _fixture_responder(
        listener,
        pairs=pairs,
        max_connections=max_connections,
        max_frame_bytes=max_frame_bytes,
    )
    metrics = ProxyFixtureServerMetrics(
        schema=AIWIRE_PROXY_FIXTURE_SERVER_SCHEMA,
        started_at_utc=started_at_utc,
        ended_at_utc=_utc_now(),
        listen_host=listen_host,
        listen_port=bound_port,
        fixture_corpus=str(fixture_path),
        fixture_corpus_source=fixture_corpus_source,
        fixture_pair_count=len(pairs),
        fixture_variation_profile=fixture_variation_profile,
        fixture_peer_label=fixture_peer_label,
        max_connections=max_connections,
        accepted_connections=int(responder["accepted_connections"]),
        exchanges=int(responder["exchanges"]),
        raw_request_payload_bytes=int(responder["raw_request_payload_bytes"]),
        raw_response_payload_bytes=int(responder["raw_response_payload_bytes"]),
    )
    if metrics_output:
        Path(metrics_output).write_text(
            json.dumps(asdict(metrics), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return metrics


def _capacity_eps(link_mbps: float, bytes_per_exchange: float) -> float:
    if link_mbps <= 0 or bytes_per_exchange <= 0:
        return 0.0
    return link_mbps * 1_000_000.0 / 8.0 / bytes_per_exchange


def _benchmark_result_row(result: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "codec": "aiwire",
        "backend": result["actual_backend"],
        "verified": result["verified"],
        "exchanges": result["exchanges"],
        "deadline_completed_exchanges": result["exchanges"],
        "deadline_exchanges_per_second": result["exchanges_per_second"],
        "framed_wire_bytes": result["tunnel_semantic_framed_bytes"],
        "framed_bytes_per_exchange": result["tunnel_semantic_framed_bytes_per_exchange"],
        "framed_wire_saved_percent": result["tunnel_saved_percent"],
        "raw_framed_bytes": result["raw_framed_bytes"],
        "tunnel_control_framed_bytes": result["tunnel_control_framed_bytes"],
        "roundtrip_ms_p50": result["roundtrip_ms_p50"],
        "roundtrip_ms_p95": result["roundtrip_ms_p95"],
        "roundtrip_ms_p99": result["roundtrip_ms_p99"],
        "modeled_link_mbps": result["modeled_link_mbps"],
        "modeled_raw_capacity_exchanges_per_second": result[
            "modeled_raw_capacity_exchanges_per_second"
        ],
        "modeled_tunnel_capacity_exchanges_per_second": result[
            "modeled_tunnel_capacity_exchanges_per_second"
        ],
        "bandwidth_capacity_gain": result["bandwidth_capacity_gain"],
    }


def _run_fixture_client(
    *,
    ingress_host: str,
    ingress_port: int,
    pairs: Sequence[ProxyFixturePair],
    seconds: float,
    max_exchanges: int | None,
) -> dict[str, Any]:
    started_at_utc = _utc_now()
    started = time.perf_counter()
    deadline = started + seconds if seconds > 0 else None
    exchanges = 0
    client_raw_framed_bytes = 0
    latencies_ms: list[float] = []
    with socket.create_connection((ingress_host, ingress_port), timeout=5) as client:
        while max_exchanges is None or exchanges < max_exchanges:
            if deadline is not None and exchanges > 0 and time.perf_counter() >= deadline:
                break
            pair = pairs[exchanges % len(pairs)]
            roundtrip_started = time.perf_counter()
            client_raw_framed_bytes += write_length_prefixed(client, pair.request)
            response = read_length_prefixed(client)
            client_raw_framed_bytes += 4 + len(response)
            latencies_ms.append((time.perf_counter() - roundtrip_started) * 1000.0)
            if response != pair.response:
                raise AssertionError(f"response payload mismatch at exchange {exchanges}")
            exchanges += 1

    return {
        "started_at_utc": started_at_utc,
        "elapsed_seconds": max(time.perf_counter() - started, 0.000001),
        "exchanges": exchanges,
        "client_raw_framed_bytes": client_raw_framed_bytes,
        "latencies_ms": latencies_ms,
    }


def _result_from_ingress_metrics(
    *,
    mode: str,
    client_run: Mapping[str, Any],
    fixture_path: Path,
    fixture_corpus_source: str,
    fixture_pair_count: int,
    fixture_variation_profile: str,
    fixture_peer_label: str,
    seconds: float,
    max_exchanges: int | None,
    backend: BackendName,
    level: int,
    modeled_link_mbps: float,
    ingress_payload: Mapping[str, Any],
    egress_payload: Mapping[str, Any] | None = None,
    upstream: Mapping[str, Any] | None = None,
    egress_host: str | None = None,
    egress_port: int | None = None,
) -> dict[str, Any]:
    exchanges = int(client_run["exchanges"])
    elapsed = float(client_run["elapsed_seconds"])
    latencies_ms = list(client_run["latencies_ms"])
    raw_framed_bytes = int(ingress_payload["raw_framed_bytes"])
    tunnel_semantic_framed_bytes = int(ingress_payload["tunnel_semantic_framed_bytes"])
    tunnel_control_framed_bytes = int(ingress_payload["tunnel_control_framed_bytes"])
    tunnel_total_framed_bytes = int(ingress_payload["tunnel_total_framed_bytes"])
    raw_bpe = raw_framed_bytes / exchanges if exchanges else 0.0
    tunnel_semantic_bpe = tunnel_semantic_framed_bytes / exchanges if exchanges else 0.0
    tunnel_total_bpe = tunnel_total_framed_bytes / exchanges if exchanges else 0.0
    raw_capacity = _capacity_eps(modeled_link_mbps, raw_bpe)
    tunnel_capacity = _capacity_eps(modeled_link_mbps, tunnel_semantic_bpe)
    tunnel_total_capacity = _capacity_eps(modeled_link_mbps, tunnel_total_bpe)
    actual_backend = str(ingress_payload["encoder_backend"])
    result: dict[str, Any] = {
        "schema": AIWIRE_PROXY_BENCHMARK_SCHEMA,
        "mode": mode,
        "started_at_utc": client_run["started_at_utc"],
        "ended_at_utc": _utc_now(),
        "fixture_corpus": str(fixture_path),
        "fixture_corpus_source": fixture_corpus_source,
        "fixture_pair_count": fixture_pair_count,
        "fixture_variation_profile": fixture_variation_profile,
        "fixture_peer_label": fixture_peer_label,
        "seconds": seconds,
        "max_exchanges": max_exchanges,
        "elapsed_seconds": elapsed,
        "requested_backend": backend,
        "actual_backend": actual_backend,
        "level": level,
        "verified": True,
        "exchanges": exchanges,
        "exchanges_per_second": exchanges / elapsed,
        "client_raw_framed_bytes": client_run["client_raw_framed_bytes"],
        "raw_framed_bytes": raw_framed_bytes,
        "raw_request_payload_bytes": ingress_payload["raw_request_payload_bytes"],
        "raw_response_payload_bytes": ingress_payload["raw_response_payload_bytes"],
        "raw_framed_bytes_per_exchange": raw_bpe,
        "tunnel_semantic_framed_bytes": tunnel_semantic_framed_bytes,
        "tunnel_control_framed_bytes": tunnel_control_framed_bytes,
        "tunnel_total_framed_bytes": tunnel_total_framed_bytes,
        "tunnel_semantic_framed_bytes_per_exchange": tunnel_semantic_bpe,
        "tunnel_total_framed_bytes_per_exchange": tunnel_total_bpe,
        "tunnel_saved_percent": ingress_payload["tunnel_saved_percent"],
        "bandwidth_capacity_gain": ingress_payload["bandwidth_capacity_gain"],
        "modeled_link_mbps": modeled_link_mbps,
        "modeled_raw_capacity_exchanges_per_second": raw_capacity,
        "modeled_tunnel_capacity_exchanges_per_second": tunnel_capacity,
        "modeled_tunnel_total_capacity_exchanges_per_second": tunnel_total_capacity,
        "modeled_tunnel_gain_vs_raw": tunnel_capacity / raw_capacity if raw_capacity else 0.0,
        "roundtrip_ms_min": min(latencies_ms) if latencies_ms else 0.0,
        "roundtrip_ms_mean": statistics.fmean(latencies_ms) if latencies_ms else 0.0,
        "roundtrip_ms_p50": _percentile(latencies_ms, 0.50),
        "roundtrip_ms_p95": _percentile(latencies_ms, 0.95),
        "roundtrip_ms_p99": _percentile(latencies_ms, 0.99),
        "roundtrip_ms_max": max(latencies_ms) if latencies_ms else 0.0,
        "upstream": dict(upstream or {}),
        "ingress_metrics": dict(ingress_payload),
        "egress_metrics": dict(egress_payload or {}),
    }
    if egress_host is not None:
        result["egress_host"] = egress_host
    if egress_port is not None:
        result["egress_port"] = egress_port
    return result


def _write_benchmark_outputs(
    result: Mapping[str, Any],
    *,
    output: str | Path | None,
    replay_log_output: str | Path | None,
) -> None:
    if output:
        Path(output).write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if replay_log_output:
        artifact = {
            "suite": "aura-aiwire-proxy-benchmark",
            "mode": result["mode"],
            "seconds": result["seconds"],
            "exchanges": result["exchanges"],
            "requested_backend": result["requested_backend"],
            "fixture_corpus": result["fixture_corpus"],
            "fixture_variation_profile": result["fixture_variation_profile"],
            "results": [_benchmark_result_row(result)],
        }
        Path(replay_log_output).write_text(
            dumps_replay_log(artifact, source="aura-proxy-benchmark"),
            encoding="utf-8",
        )


def run_proxy_ingress_benchmark(
    *,
    egress_host: str,
    egress_port: int,
    fixture_corpus_path: str | Path = DEFAULT_PROXY_FIXTURE_PATH,
    fixture_variation_profile: str = "none",
    fixture_peer_label: str = "proxy-fixture",
    seconds: float = 60.0,
    max_exchanges: int | None = None,
    backend: BackendName = "python",
    level: int = AI_WIRE_DEFAULT_LEVEL,
    modeled_link_mbps: float = 10.0,
    output: str | Path | None = None,
    replay_log_output: str | Path | None = None,
    ingress_metrics_output: str | Path | None = None,
) -> dict[str, Any]:
    """Benchmark a local ingress/client against an already running egress proxy."""

    if seconds <= 0 and max_exchanges is None:
        raise ValueError("seconds must be positive unless max_exchanges is set")
    if max_exchanges is not None and max_exchanges <= 0:
        raise ValueError("max_exchanges must be positive")

    fixture_path = Path(fixture_corpus_path)
    corpus, fixture_corpus_source = _load_fixture_corpus(fixture_path)
    pairs = build_proxy_fixture_pairs(
        corpus,
        fixture_variation_profile=fixture_variation_profile,
        fixture_peer_label=fixture_peer_label,
    )

    with tempfile.TemporaryDirectory(prefix="aura-proxy-ingress-benchmark-") as tmpdir:
        tmp = Path(tmpdir)
        ingress_metrics_path = (
            Path(ingress_metrics_output) if ingress_metrics_output else tmp / "ingress.metrics.json"
        )
        ingress_ready = threading.Event()
        ingress_port_holder: list[int] = []

        def ingress_ready_callback(port: int) -> None:
            ingress_port_holder.append(port)
            ingress_ready.set()

        ingress_thread, ingress_results = _run_background(
            lambda: run_ingress_proxy(
                listen_host=HOST,
                listen_port=0,
                egress_host=egress_host,
                egress_port=egress_port,
                backend=backend,
                level=level,
                max_connections=1,
                metrics_output=ingress_metrics_path,
                ready_callback=ingress_ready_callback,
            )
        )
        if not ingress_ready.wait(timeout=5):
            raise TimeoutError("ingress proxy did not become ready")

        client_run = _run_fixture_client(
            ingress_host=HOST,
            ingress_port=ingress_port_holder[0],
            pairs=pairs,
            seconds=seconds,
            max_exchanges=max_exchanges,
        )
        ingress_metrics = _background_result(ingress_thread, ingress_results)
        ingress_payload = ingress_metrics.to_dict()

    result = _result_from_ingress_metrics(
        mode="ingress_client",
        client_run=client_run,
        fixture_path=fixture_path,
        fixture_corpus_source=fixture_corpus_source,
        fixture_pair_count=len(pairs),
        fixture_variation_profile=fixture_variation_profile,
        fixture_peer_label=fixture_peer_label,
        seconds=seconds,
        max_exchanges=max_exchanges,
        backend=backend,
        level=level,
        modeled_link_mbps=modeled_link_mbps,
        ingress_payload=ingress_payload,
        egress_host=egress_host,
        egress_port=egress_port,
    )
    _write_benchmark_outputs(result, output=output, replay_log_output=replay_log_output)
    return result


def run_proxy_benchmark(
    *,
    fixture_corpus_path: str | Path = DEFAULT_PROXY_FIXTURE_PATH,
    fixture_variation_profile: str = "none",
    fixture_peer_label: str = "proxy-fixture",
    seconds: float = 60.0,
    max_exchanges: int | None = None,
    backend: BackendName = "python",
    level: int = AI_WIRE_DEFAULT_LEVEL,
    modeled_link_mbps: float = 10.0,
    output: str | Path | None = None,
    replay_log_output: str | Path | None = None,
) -> dict[str, Any]:
    """Run a local ingress -> AIWire tunnel -> egress proxy benchmark."""

    if seconds <= 0 and max_exchanges is None:
        raise ValueError("seconds must be positive unless max_exchanges is set")
    if max_exchanges is not None and max_exchanges <= 0:
        raise ValueError("max_exchanges must be positive")

    fixture_path = Path(fixture_corpus_path)
    corpus, fixture_corpus_source = _load_fixture_corpus(fixture_path)
    pairs = build_proxy_fixture_pairs(
        corpus,
        fixture_variation_profile=fixture_variation_profile,
        fixture_peer_label=fixture_peer_label,
    )

    upstream_listener, upstream_port = _bound_listener()
    upstream_thread, upstream_results = _run_background(
        lambda: _fixture_responder(upstream_listener, pairs=pairs)
    )

    with tempfile.TemporaryDirectory(prefix="aura-proxy-benchmark-") as tmpdir:
        tmp = Path(tmpdir)
        ingress_metrics_path = tmp / "ingress.metrics.json"
        egress_metrics_path = tmp / "egress.metrics.json"

        egress_ready = threading.Event()
        egress_port_holder: list[int] = []

        def egress_ready_callback(port: int) -> None:
            egress_port_holder.append(port)
            egress_ready.set()

        egress_thread, egress_results = _run_background(
            lambda: run_egress_proxy(
                listen_host=HOST,
                listen_port=0,
                upstream_host=HOST,
                upstream_port=upstream_port,
                backend=backend,
                level=level,
                max_connections=1,
                metrics_output=egress_metrics_path,
                ready_callback=egress_ready_callback,
            )
        )
        if not egress_ready.wait(timeout=5):
            raise TimeoutError("egress proxy did not become ready")

        ingress_ready = threading.Event()
        ingress_port_holder: list[int] = []

        def ingress_ready_callback(port: int) -> None:
            ingress_port_holder.append(port)
            ingress_ready.set()

        ingress_thread, ingress_results = _run_background(
            lambda: run_ingress_proxy(
                listen_host=HOST,
                listen_port=0,
                egress_host=HOST,
                egress_port=egress_port_holder[0],
                backend=backend,
                level=level,
                max_connections=1,
                metrics_output=ingress_metrics_path,
                ready_callback=ingress_ready_callback,
            )
        )
        if not ingress_ready.wait(timeout=5):
            raise TimeoutError("ingress proxy did not become ready")

        client_run = _run_fixture_client(
            ingress_host=HOST,
            ingress_port=ingress_port_holder[0],
            pairs=pairs,
            seconds=seconds,
            max_exchanges=max_exchanges,
        )

        ingress_metrics = _background_result(ingress_thread, ingress_results)
        egress_metrics = _background_result(egress_thread, egress_results)
        upstream = _background_result(upstream_thread, upstream_results)

        ingress_payload = ingress_metrics.to_dict()
        egress_payload = egress_metrics.to_dict()

    result = _result_from_ingress_metrics(
        mode="local_proxy_benchmark",
        client_run=client_run,
        fixture_path=fixture_path,
        fixture_corpus_source=fixture_corpus_source,
        fixture_pair_count=len(pairs),
        fixture_variation_profile=fixture_variation_profile,
        fixture_peer_label=fixture_peer_label,
        seconds=seconds,
        max_exchanges=max_exchanges,
        backend=backend,
        level=level,
        modeled_link_mbps=modeled_link_mbps,
        ingress_payload=ingress_payload,
        egress_payload=egress_payload,
        upstream=upstream,
    )
    _write_benchmark_outputs(result, output=output, replay_log_output=replay_log_output)
    return result


__all__ = [
    "AIWIRE_PROXY_BENCHMARK_SCHEMA",
    "AIWIRE_PROXY_FIXTURE_SERVER_SCHEMA",
    "DEFAULT_PROXY_FIXTURE_PATH",
    "FIXTURE_VARIATION_PROFILES",
    "ProxyFixturePair",
    "ProxyFixtureServerMetrics",
    "build_proxy_fixture_pairs",
    "run_proxy_benchmark",
    "run_proxy_fixture_server",
    "run_proxy_ingress_benchmark",
]
