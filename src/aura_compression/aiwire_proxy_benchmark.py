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
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypeVar

from .ai_wire import AI_WIRE_DEFAULT_LEVEL, encode_ai_wire_message
from .ai_wire_fixtures import (
    build_aiwire_session_fixture_corpus,
    load_aiwire_session_fixture_corpus,
)
from .aiwire_proxy import (
    BackendName,
    read_length_prefixed,
    run_egress_proxy,
    run_ingress_proxy,
    write_length_prefixed,
)
from .aiwire_replay_log import dumps_replay_log

AIWIRE_PROXY_BENCHMARK_SCHEMA = "aura.aiwire.proxy_benchmark.v1"
DEFAULT_PROXY_FIXTURE_PATH = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "aiwire_sessions"
    / "public_session_corpus_v1.json"
)
HOST = "127.0.0.1"
T = TypeVar("T")


@dataclass(frozen=True)
class ProxyFixturePair:
    """One request/response pair replayed through the proxy."""

    session_id: str
    exchange_index: int
    request: bytes
    response: bytes


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _bound_listener() -> tuple[socket.socket, int]:
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind((HOST, 0))
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


def build_proxy_fixture_pairs(corpus: Mapping[str, Any]) -> list[ProxyFixturePair]:
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
            request_message = requests[exchange_index].get("message")
            response_message = responses[exchange_index].get("message")
            pairs.append(
                ProxyFixturePair(
                    session_id=session_id,
                    exchange_index=exchange_index,
                    request=encode_ai_wire_message(request_message),
                    response=encode_ai_wire_message(response_message),
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
) -> dict[str, Any]:
    exchanges = 0
    raw_request_payload_bytes = 0
    raw_response_payload_bytes = 0
    with listener:
        conn, _addr = listener.accept()
        with conn:
            while True:
                try:
                    request = read_length_prefixed(conn)
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
        "exchanges": exchanges,
        "raw_request_payload_bytes": raw_request_payload_bytes,
        "raw_response_payload_bytes": raw_response_payload_bytes,
    }


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


def run_proxy_benchmark(
    *,
    fixture_corpus_path: str | Path = DEFAULT_PROXY_FIXTURE_PATH,
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
    pairs = build_proxy_fixture_pairs(corpus)

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

        started_at_utc = _utc_now()
        started = time.perf_counter()
        deadline = started + seconds if seconds > 0 else None
        exchanges = 0
        client_raw_framed_bytes = 0
        latencies_ms: list[float] = []
        with socket.create_connection((HOST, ingress_port_holder[0]), timeout=5) as client:
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

        elapsed = max(time.perf_counter() - started, 0.000001)
        ingress_metrics = _background_result(ingress_thread, ingress_results)
        egress_metrics = _background_result(egress_thread, egress_results)
        upstream = _background_result(upstream_thread, upstream_results)

        ingress_payload = ingress_metrics.to_dict()
        egress_payload = egress_metrics.to_dict()

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
        "started_at_utc": started_at_utc,
        "ended_at_utc": _utc_now(),
        "fixture_corpus": str(fixture_path),
        "fixture_corpus_source": fixture_corpus_source,
        "fixture_pair_count": len(pairs),
        "seconds": seconds,
        "max_exchanges": max_exchanges,
        "elapsed_seconds": elapsed,
        "requested_backend": backend,
        "actual_backend": actual_backend,
        "level": level,
        "verified": True,
        "exchanges": exchanges,
        "exchanges_per_second": exchanges / elapsed,
        "client_raw_framed_bytes": client_raw_framed_bytes,
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
        "upstream": upstream,
        "ingress_metrics": ingress_payload,
        "egress_metrics": egress_payload,
    }

    if output:
        Path(output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    if replay_log_output:
        artifact = {
            "suite": "aura-aiwire-proxy-benchmark",
            "mode": "proxy_benchmark",
            "seconds": seconds,
            "exchanges": exchanges,
            "requested_backend": backend,
            "fixture_corpus": str(fixture_path),
            "results": [_benchmark_result_row(result)],
        }
        Path(replay_log_output).write_text(
            dumps_replay_log(artifact, source="aura-proxy-benchmark")
        )
    return result


__all__ = [
    "AIWIRE_PROXY_BENCHMARK_SCHEMA",
    "DEFAULT_PROXY_FIXTURE_PATH",
    "ProxyFixturePair",
    "build_proxy_fixture_pairs",
    "run_proxy_benchmark",
]
