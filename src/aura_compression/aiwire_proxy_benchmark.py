"""Local benchmark harness for the explicit AIWire sidecar proxy."""

from __future__ import annotations

import concurrent.futures
import json
import queue
import random
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
    TUNNEL_CODECS,
    AIWireProxyResumeConfig,
    BackendName,
    EgressUpstreamResponder,
    TunnelCodec,
    TunnelImpairmentConfig,
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
UPSTREAM_AGENT_PROFILES = ("none", "edge-light", "edge-mixed")
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
    upstream_agent_profile: str
    upstream_agent_seed: int
    upstream_agent_delay_seconds: float
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


def _validate_upstream_agent_profile(profile: str) -> None:
    if profile not in UPSTREAM_AGENT_PROFILES:
        raise ValueError(
            "upstream_agent_profile must be one of: " + ", ".join(UPSTREAM_AGENT_PROFILES)
        )


def _upstream_agent_delay_ms(profile: str, rng: random.Random) -> float:
    _validate_upstream_agent_profile(profile)
    if profile == "none":
        return 0.0
    if profile == "edge-light":
        delay_ms = 0.25 + rng.uniform(0.0, 1.25)
        if rng.random() < 0.025:
            delay_ms += rng.uniform(2.0, 8.0)
        return delay_ms
    delay_ms = 0.75 + rng.uniform(0.0, 4.0)
    if rng.random() < 0.05:
        delay_ms += rng.uniform(8.0, 35.0)
    return delay_ms


def _wait_upstream_agent(profile: str, rng: random.Random) -> int:
    delay_ms = _upstream_agent_delay_ms(profile, rng)
    if delay_ms <= 0:
        return 0
    started_ns = time.perf_counter_ns()
    time.sleep(delay_ms / 1000.0)
    return time.perf_counter_ns() - started_ns


def load_proxy_fixture_pairs(
    fixture_corpus_path: str | Path = DEFAULT_PROXY_FIXTURE_PATH,
    *,
    fixture_variation_profile: str = "none",
    fixture_peer_label: str = "proxy-fixture",
) -> tuple[list[ProxyFixturePair], Path, str]:
    """Load replayable proxy request/response pairs plus corpus metadata."""

    fixture_path = Path(fixture_corpus_path)
    corpus, fixture_corpus_source = _load_fixture_corpus(fixture_path)
    return (
        build_proxy_fixture_pairs(
            corpus,
            fixture_variation_profile=fixture_variation_profile,
            fixture_peer_label=fixture_peer_label,
        ),
        fixture_path,
        fixture_corpus_source,
    )


def build_proxy_fixture_responder(
    pairs: Sequence[ProxyFixturePair],
    *,
    upstream_agent_profile: str = "none",
    upstream_agent_seed: int = 1729,
) -> EgressUpstreamResponder:
    """Build a benchmark-only in-process responder for egress fixture isolation."""

    _validate_upstream_agent_profile(upstream_agent_profile)
    thread_state = threading.local()

    def rng_for_thread() -> random.Random:
        existing = getattr(thread_state, "rng", None)
        if isinstance(existing, random.Random):
            return existing
        rng = random.Random(upstream_agent_seed + (threading.get_ident() % 1_000_003))
        thread_state.rng = rng
        return rng

    def responder(request: bytes, exchange_index: int) -> bytes:
        pair = pairs[exchange_index % len(pairs)]
        if request != pair.request:
            raise AssertionError(
                f"request payload mismatch at inline exchange {exchange_index}; "
                f"fixture={pair.session_id}:{pair.exchange_index}"
            )
        _wait_upstream_agent(upstream_agent_profile, rng_for_thread())
        return pair.response

    return responder


def _fixture_responder(
    listener: socket.socket,
    *,
    pairs: Sequence[ProxyFixturePair],
    max_connections: int | None = 1,
    max_frame_bytes: int = DEFAULT_MAX_FRAME_BYTES,
    upstream_agent_profile: str = "none",
    upstream_agent_seed: int = 1729,
) -> dict[str, Any]:
    _validate_upstream_agent_profile(upstream_agent_profile)
    accepted_connections = 0
    exchanges = 0
    raw_request_payload_bytes = 0
    raw_response_payload_bytes = 0
    upstream_agent_delay_ns = 0
    totals_lock = threading.Lock()
    workers: list[threading.Thread] = []
    errors: list[BaseException] = []

    def handle_connection(conn: socket.socket, connection_index: int) -> None:
        nonlocal exchanges, raw_request_payload_bytes, raw_response_payload_bytes
        nonlocal upstream_agent_delay_ns
        local_exchanges = 0
        local_request_bytes = 0
        local_response_bytes = 0
        local_delay_ns = 0
        rng = random.Random(upstream_agent_seed + connection_index * 1_000_003)
        try:
            with conn:
                while True:
                    try:
                        request = read_length_prefixed(
                            conn,
                            max_frame_bytes=max_frame_bytes,
                        )
                    except EOFError:
                        break
                    pair = pairs[local_exchanges % len(pairs)]
                    if request != pair.request:
                        raise AssertionError(
                            f"request payload mismatch on connection {connection_index} "
                            f"at exchange {local_exchanges}; "
                            f"fixture={pair.session_id}:{pair.exchange_index}"
                        )
                    local_request_bytes += len(request)
                    local_response_bytes += len(pair.response)
                    local_delay_ns += _wait_upstream_agent(upstream_agent_profile, rng)
                    write_length_prefixed(conn, pair.response)
                    local_exchanges += 1
        except BaseException as exc:
            with totals_lock:
                errors.append(exc)
        finally:
            with totals_lock:
                exchanges += local_exchanges
                raw_request_payload_bytes += local_request_bytes
                raw_response_payload_bytes += local_response_bytes
                upstream_agent_delay_ns += local_delay_ns

    with listener:
        while max_connections is None or accepted_connections < max_connections:
            conn, _addr = listener.accept()
            accepted_connections += 1
            worker = threading.Thread(
                target=handle_connection,
                args=(conn, accepted_connections),
            )
            worker.start()
            workers.append(worker)

        for worker in workers:
            worker.join()
        if errors:
            raise errors[0]

    return {
        "accepted_connections": accepted_connections,
        "exchanges": exchanges,
        "raw_request_payload_bytes": raw_request_payload_bytes,
        "raw_response_payload_bytes": raw_response_payload_bytes,
        "upstream_agent_delay_seconds": upstream_agent_delay_ns / 1_000_000_000.0,
    }


def run_proxy_fixture_server(
    *,
    listen_host: str = HOST,
    listen_port: int = 8765,
    fixture_corpus_path: str | Path = DEFAULT_PROXY_FIXTURE_PATH,
    fixture_variation_profile: str = "none",
    fixture_peer_label: str = "proxy-fixture",
    upstream_agent_profile: str = "none",
    upstream_agent_seed: int = 1729,
    max_connections: int | None = 1,
    max_frame_bytes: int = DEFAULT_MAX_FRAME_BYTES,
    metrics_output: str | Path | None = None,
    ready_callback: Callable[[int], None] | None = None,
) -> ProxyFixtureServerMetrics:
    """Run a raw length-prefixed upstream responder for proxy benchmarks."""

    if max_connections is not None and max_connections <= 0:
        raise ValueError("max_connections must be positive when provided")
    _validate_upstream_agent_profile(upstream_agent_profile)
    started_at_utc = _utc_now()
    pairs, fixture_path, fixture_corpus_source = load_proxy_fixture_pairs(
        fixture_corpus_path,
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
        upstream_agent_profile=upstream_agent_profile,
        upstream_agent_seed=upstream_agent_seed,
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
        upstream_agent_profile=upstream_agent_profile,
        upstream_agent_seed=upstream_agent_seed,
        upstream_agent_delay_seconds=float(responder["upstream_agent_delay_seconds"]),
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


def _tunnel_impairment_config(
    *,
    bandwidth_mbps: float = 0.0,
    one_way_delay_ms: float = 0.0,
    jitter_ms: float = 0.0,
    tail_pause_probability: float = 0.0,
    tail_pause_ms: float = 0.0,
    seed: int = 1729,
) -> TunnelImpairmentConfig:
    config = TunnelImpairmentConfig(
        bandwidth_mbps=bandwidth_mbps,
        one_way_delay_ms=one_way_delay_ms,
        jitter_ms=jitter_ms,
        tail_pause_probability=tail_pause_probability,
        tail_pause_ms=tail_pause_ms,
        seed=seed,
    )
    config.validate()
    return config


def _benchmark_result_row(result: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "codec": result.get("tunnel_codec", "aiwire"),
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


def _validate_connections(connections: int) -> None:
    if connections <= 0:
        raise ValueError("connections must be positive")


def _active_connections(*, connections: int, max_exchanges: int | None) -> int:
    _validate_connections(connections)
    if max_exchanges is None:
        return connections
    return max(1, min(connections, max_exchanges))


def _split_max_exchanges(total: int, connections: int) -> list[int]:
    base, remainder = divmod(total, connections)
    return [base + (1 if index < remainder else 0) for index in range(connections)]


def _run_fixture_clients(
    *,
    ingress_host: str,
    ingress_port: int,
    pairs: Sequence[ProxyFixturePair],
    seconds: float,
    max_exchanges: int | None,
    connections: int,
) -> dict[str, Any]:
    active_connections = _active_connections(
        connections=connections,
        max_exchanges=max_exchanges,
    )
    started_at_utc = _utc_now()
    started = time.perf_counter()
    per_connection_max = (
        _split_max_exchanges(max_exchanges, active_connections)
        if max_exchanges is not None
        else [None] * active_connections
    )

    with concurrent.futures.ThreadPoolExecutor(max_workers=active_connections) as executor:
        futures = [
            executor.submit(
                _run_fixture_client,
                ingress_host=ingress_host,
                ingress_port=ingress_port,
                pairs=pairs,
                seconds=seconds,
                max_exchanges=max_for_connection,
            )
            for max_for_connection in per_connection_max
        ]
        runs = [future.result() for future in concurrent.futures.as_completed(futures)]

    latencies_ms = [latency for run in runs for latency in list(run.get("latencies_ms", []))]
    return {
        "started_at_utc": started_at_utc,
        "elapsed_seconds": max(time.perf_counter() - started, 0.000001),
        "requested_connections": connections,
        "connections": active_connections,
        "exchanges": sum(int(run["exchanges"]) for run in runs),
        "client_raw_framed_bytes": sum(int(run["client_raw_framed_bytes"]) for run in runs),
        "latencies_ms": latencies_ms,
        "client_runs": [
            {
                "exchanges": int(run["exchanges"]),
                "elapsed_seconds": float(run["elapsed_seconds"]),
                "client_raw_framed_bytes": int(run["client_raw_framed_bytes"]),
                "roundtrip_ms_p95": _percentile(list(run.get("latencies_ms", [])), 0.95),
            }
            for run in runs
        ],
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
    upstream_agent_profile: str,
    upstream_agent_seed: int,
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
    tunnel_codec = str(ingress_payload.get("tunnel_codec") or "aiwire")
    if tunnel_codec not in TUNNEL_CODECS:
        raise ValueError(f"unsupported tunnel codec in ingress metrics: {tunnel_codec!r}")
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
        "upstream_agent_profile": upstream_agent_profile,
        "upstream_agent_seed": upstream_agent_seed,
        "seconds": seconds,
        "max_exchanges": max_exchanges,
        "requested_connections": client_run.get("requested_connections", 1),
        "connections": client_run.get("connections", 1),
        "elapsed_seconds": elapsed,
        "requested_backend": backend,
        "tunnel_codec": tunnel_codec,
        "actual_backend": actual_backend,
        "level": level,
        "verified": True,
        "exchanges": exchanges,
        "exchanges_per_second": exchanges / elapsed,
        "client_raw_framed_bytes": client_run["client_raw_framed_bytes"],
        "client_runs": list(client_run.get("client_runs", [])),
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
        "tunnel_impairment": dict(ingress_payload.get("tunnel_impairment") or {}),
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
            "tunnel_codec": result.get("tunnel_codec", "aiwire"),
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
    upstream_agent_profile: str = "none",
    upstream_agent_seed: int = 1729,
    seconds: float = 60.0,
    max_exchanges: int | None = None,
    connections: int = 1,
    backend: BackendName = "python",
    tunnel_codec: TunnelCodec = "aiwire",
    level: int = AI_WIRE_DEFAULT_LEVEL,
    modeled_link_mbps: float = 10.0,
    tunnel_bandwidth_mbps: float = 0.0,
    tunnel_one_way_delay_ms: float = 0.0,
    tunnel_jitter_ms: float = 0.0,
    tunnel_tail_pause_probability: float = 0.0,
    tunnel_tail_pause_ms: float = 0.0,
    impairment_seed: int = 1729,
    output: str | Path | None = None,
    replay_log_output: str | Path | None = None,
    ingress_metrics_output: str | Path | None = None,
    ingress_resume_config: AIWireProxyResumeConfig | None = None,
) -> dict[str, Any]:
    """Benchmark a local ingress/client against an already running egress proxy."""

    if tunnel_codec not in TUNNEL_CODECS:
        raise ValueError("tunnel_codec must be one of: " + ", ".join(TUNNEL_CODECS))
    if seconds <= 0 and max_exchanges is None:
        raise ValueError("seconds must be positive unless max_exchanges is set")
    if max_exchanges is not None and max_exchanges <= 0:
        raise ValueError("max_exchanges must be positive")
    _validate_upstream_agent_profile(upstream_agent_profile)
    connection_count = _active_connections(
        connections=connections,
        max_exchanges=max_exchanges,
    )

    pairs, fixture_path, fixture_corpus_source = load_proxy_fixture_pairs(
        fixture_corpus_path,
        fixture_variation_profile=fixture_variation_profile,
        fixture_peer_label=fixture_peer_label,
    )
    tunnel_impairment_config = _tunnel_impairment_config(
        bandwidth_mbps=tunnel_bandwidth_mbps,
        one_way_delay_ms=tunnel_one_way_delay_ms,
        jitter_ms=tunnel_jitter_ms,
        tail_pause_probability=tunnel_tail_pause_probability,
        tail_pause_ms=tunnel_tail_pause_ms,
        seed=impairment_seed,
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
                tunnel_codec=tunnel_codec,
                level=level,
                max_connections=connection_count,
                tunnel_impairment_config=tunnel_impairment_config,
                metrics_output=ingress_metrics_path,
                resume_config=ingress_resume_config,
                ready_callback=ingress_ready_callback,
            )
        )
        if not ingress_ready.wait(timeout=5):
            raise TimeoutError("ingress proxy did not become ready")

        client_run = _run_fixture_clients(
            ingress_host=HOST,
            ingress_port=ingress_port_holder[0],
            pairs=pairs,
            seconds=seconds,
            max_exchanges=max_exchanges,
            connections=connections,
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
        upstream_agent_profile=upstream_agent_profile,
        upstream_agent_seed=upstream_agent_seed,
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
    upstream_agent_profile: str = "none",
    upstream_agent_seed: int = 1729,
    seconds: float = 60.0,
    max_exchanges: int | None = None,
    connections: int = 1,
    backend: BackendName = "python",
    tunnel_codec: TunnelCodec = "aiwire",
    level: int = AI_WIRE_DEFAULT_LEVEL,
    modeled_link_mbps: float = 10.0,
    tunnel_bandwidth_mbps: float = 0.0,
    tunnel_one_way_delay_ms: float = 0.0,
    tunnel_jitter_ms: float = 0.0,
    tunnel_tail_pause_probability: float = 0.0,
    tunnel_tail_pause_ms: float = 0.0,
    impairment_seed: int = 1729,
    output: str | Path | None = None,
    replay_log_output: str | Path | None = None,
    inline_upstream_fixture: bool = False,
) -> dict[str, Any]:
    """Run a local ingress -> AIWire tunnel -> egress proxy benchmark."""

    if tunnel_codec not in TUNNEL_CODECS:
        raise ValueError("tunnel_codec must be one of: " + ", ".join(TUNNEL_CODECS))
    if seconds <= 0 and max_exchanges is None:
        raise ValueError("seconds must be positive unless max_exchanges is set")
    if max_exchanges is not None and max_exchanges <= 0:
        raise ValueError("max_exchanges must be positive")
    _validate_upstream_agent_profile(upstream_agent_profile)
    connection_count = _active_connections(
        connections=connections,
        max_exchanges=max_exchanges,
    )

    pairs, fixture_path, fixture_corpus_source = load_proxy_fixture_pairs(
        fixture_corpus_path,
        fixture_variation_profile=fixture_variation_profile,
        fixture_peer_label=fixture_peer_label,
    )
    tunnel_impairment_config = _tunnel_impairment_config(
        bandwidth_mbps=tunnel_bandwidth_mbps,
        one_way_delay_ms=tunnel_one_way_delay_ms,
        jitter_ms=tunnel_jitter_ms,
        tail_pause_probability=tunnel_tail_pause_probability,
        tail_pause_ms=tunnel_tail_pause_ms,
        seed=impairment_seed,
    )

    upstream_port = 0
    upstream_thread: threading.Thread | None = None
    upstream_results: queue.Queue[dict[str, Any] | BaseException] | None = None
    upstream_responder: EgressUpstreamResponder | None = None
    if inline_upstream_fixture:
        upstream_responder = build_proxy_fixture_responder(
            pairs,
            upstream_agent_profile=upstream_agent_profile,
            upstream_agent_seed=upstream_agent_seed,
        )
    else:
        upstream_listener, upstream_port = _bound_listener()
        upstream_thread, upstream_results = _run_background(
            lambda: _fixture_responder(
                upstream_listener,
                pairs=pairs,
                max_connections=connection_count,
                upstream_agent_profile=upstream_agent_profile,
                upstream_agent_seed=upstream_agent_seed,
            )
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
                upstream_host=HOST if not inline_upstream_fixture else "",
                upstream_port=upstream_port,
                upstream_responder=upstream_responder,
                backend=backend,
                tunnel_codec=tunnel_codec,
                level=level,
                max_connections=connection_count,
                tunnel_impairment_config=tunnel_impairment_config,
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
                tunnel_codec=tunnel_codec,
                level=level,
                max_connections=connection_count,
                tunnel_impairment_config=tunnel_impairment_config,
                metrics_output=ingress_metrics_path,
                ready_callback=ingress_ready_callback,
            )
        )
        if not ingress_ready.wait(timeout=5):
            raise TimeoutError("ingress proxy did not become ready")

        client_run = _run_fixture_clients(
            ingress_host=HOST,
            ingress_port=ingress_port_holder[0],
            pairs=pairs,
            seconds=seconds,
            max_exchanges=max_exchanges,
            connections=connections,
        )

        ingress_metrics = _background_result(ingress_thread, ingress_results)
        egress_metrics = _background_result(egress_thread, egress_results)
        if inline_upstream_fixture:
            upstream = {
                "mode": "inline_fixture",
                "accepted_connections": egress_metrics.accepted_connections,
                "exchanges": egress_metrics.exchanges,
                "raw_request_payload_bytes": egress_metrics.raw_request_payload_bytes,
                "raw_response_payload_bytes": egress_metrics.raw_response_payload_bytes,
                "upstream_agent_profile": upstream_agent_profile,
                "upstream_agent_seed": upstream_agent_seed,
                "upstream_agent_delay_seconds": egress_metrics.stage_time_ns.get(
                    "upstream_response_inline", 0
                )
                / 1_000_000_000.0,
            }
        else:
            if upstream_thread is None or upstream_results is None:
                raise RuntimeError("fixture responder did not start")
            upstream_payload: dict[str, Any] = _background_result(
                upstream_thread,
                upstream_results,
            )
            upstream = {
                "mode": "tcp_fixture",
                "upstream_agent_profile": upstream_agent_profile,
                "upstream_agent_seed": upstream_agent_seed,
                **upstream_payload,
            }

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
        upstream_agent_profile=upstream_agent_profile,
        upstream_agent_seed=upstream_agent_seed,
        seconds=seconds,
        max_exchanges=max_exchanges,
        backend=backend,
        level=level,
        modeled_link_mbps=modeled_link_mbps,
        ingress_payload=ingress_payload,
        egress_payload=egress_payload,
        upstream=upstream,
    )
    result["inline_upstream_fixture"] = inline_upstream_fixture
    result["upstream_mode"] = "inline_fixture" if inline_upstream_fixture else "tcp_fixture"
    _write_benchmark_outputs(result, output=output, replay_log_output=replay_log_output)
    return result


__all__ = [
    "AIWIRE_PROXY_BENCHMARK_SCHEMA",
    "AIWIRE_PROXY_FIXTURE_SERVER_SCHEMA",
    "DEFAULT_PROXY_FIXTURE_PATH",
    "FIXTURE_VARIATION_PROFILES",
    "ProxyFixturePair",
    "ProxyFixtureServerMetrics",
    "UPSTREAM_AGENT_PROFILES",
    "build_proxy_fixture_responder",
    "build_proxy_fixture_pairs",
    "load_proxy_fixture_pairs",
    "run_proxy_benchmark",
    "run_proxy_fixture_server",
    "run_proxy_ingress_benchmark",
]
