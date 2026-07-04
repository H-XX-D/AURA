#!/usr/bin/env python3
"""Bidirectional AIWire stress benchmark over a real TCP link."""

from __future__ import annotations

import argparse
import hashlib
import json
import queue
import random
import socket
import struct
import sys
import threading
import time
import zlib
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from aura_compression.ai_wire import (
    AI_WIRE_DEFAULT_LEVEL,
    AIWireHandshake,
    AIWireSessionDecoder,
    AIWireSessionEncoder,
    AIWireSessionTemplates,
    aiwire_session_templates_sha256,
    build_ai_wire_messages,
    build_aiwire_handshake,
    discover_ai_wire_session_templates,
    encode_ai_wire_message,
    negotiate_aiwire_handshake,
    normalize_aiwire_session_templates,
)
from aura_compression.ai_wire_token import (
    AIWireTokenAIWireSessionDecoder,
    AIWireTokenAIWireSessionEncoder,
    AIWireTokenSessionDecoder,
    AIWireTokenSessionEncoder,
)
from aura_compression.compressor_refactored import ProductionHybridCompressor

U32 = struct.Struct("!I")
AIWIRE_NEGOTIATED_CODECS = {"aiwire", "aitoken_aiwire"}


class BandwidthLimiter:
    """Simple serialization-delay model for a fixed-rate link."""

    def __init__(self, mbps: float) -> None:
        self.bytes_per_second = mbps * 1_000_000 / 8 if mbps > 0 else 0.0
        self.start_ns = time.perf_counter_ns()
        self.bytes_sent = 0

    def consume(self, byte_count: int) -> None:
        if self.bytes_per_second <= 0 or byte_count <= 0:
            return
        self.bytes_sent += byte_count
        target_elapsed = self.bytes_sent / self.bytes_per_second
        actual_elapsed = (time.perf_counter_ns() - self.start_ns) / 1_000_000_000
        delay = target_elapsed - actual_elapsed
        if delay > 0:
            time.sleep(delay)


class AsyncFrameWriter:
    """Queues framed writes so propagation delay does not block the producer."""

    def __init__(
        self,
        sock: socket.socket,
        mbps: float,
        one_way_delay_ms: float = 0.0,
        jitter_ms: float = 0.0,
        tail_pause_probability: float = 0.0,
        tail_pause_ms: float = 0.0,
        seed: int = 1729,
    ) -> None:
        self.sock = sock
        self.bandwidth = BandwidthLimiter(mbps)
        self.one_way_delay_ms = max(0.0, one_way_delay_ms)
        self.jitter_ms = max(0.0, jitter_ms)
        self.tail_pause_probability = min(1.0, max(0.0, tail_pause_probability))
        self.tail_pause_ms = max(0.0, tail_pause_ms)
        self.rng = random.Random(seed)
        self.frames: "queue.Queue[bytes | None]" = queue.Queue()
        self.ready_frames: "queue.Queue[tuple[int, bytes] | None]" = queue.Queue()
        self.error: BaseException | None = None
        self.serializer_thread = threading.Thread(
            target=self._serialize,
            name="aura-aiwire-frame-serializer",
            daemon=True,
        )
        self.sender_thread = threading.Thread(
            target=self._send_ready,
            name="aura-aiwire-frame-sender",
            daemon=True,
        )
        self.serializer_thread.start()
        self.sender_thread.start()

    def write(self, payload: bytes) -> None:
        self._raise_error()
        self.frames.put(payload)

    def flush(self) -> None:
        self.frames.join()
        self.ready_frames.join()
        self._raise_error()

    def close(self) -> None:
        self.frames.put(None)
        self.frames.join()
        self.ready_frames.join()
        self.serializer_thread.join()
        self.sender_thread.join()
        self._raise_error()

    def _serialize(self) -> None:
        while True:
            payload = self.frames.get()
            try:
                if payload is None:
                    self.ready_frames.put(None)
                    return
                self.bandwidth.consume(U32.size + len(payload))
                self.ready_frames.put((self._arrival_due_ns(), payload))
            except BaseException as exc:  # pragma: no cover - surfaced through flush/close.
                self.error = exc
            finally:
                self.frames.task_done()

    def _arrival_due_ns(self) -> int:
        delay_ms = self.one_way_delay_ms
        if self.jitter_ms > 0:
            delay_ms += self.rng.uniform(-self.jitter_ms, self.jitter_ms)
        if self.tail_pause_probability and self.rng.random() < self.tail_pause_probability:
            delay_ms += self.rng.uniform(0.0, self.tail_pause_ms)
        return time.perf_counter_ns() + int(max(0.0, delay_ms) * 1_000_000)

    def _send_ready(self) -> None:
        while True:
            item = self.ready_frames.get()
            try:
                if item is None:
                    return
                due_ns, payload = item
                delay_ns = due_ns - time.perf_counter_ns()
                if delay_ns > 0:
                    time.sleep(delay_ns / 1_000_000_000)
                self.sock.sendall(U32.pack(len(payload)))
                if payload:
                    self.sock.sendall(payload)
            except BaseException as exc:  # pragma: no cover - surfaced through flush/close.
                self.error = exc
            finally:
                self.ready_frames.task_done()

    def _raise_error(self) -> None:
        if self.error is not None:
            raise RuntimeError("async frame writer failed") from self.error


def _json_bytes(value: Any) -> bytes:
    return encode_ai_wire_message(value)


def _write_frame(sock: socket.socket, payload: bytes) -> None:
    sock.sendall(U32.pack(len(payload)))
    if payload:
        sock.sendall(payload)


def _read_exact(sock: socket.socket, size: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < size:
        chunk = sock.recv(size - len(chunks))
        if not chunk:
            raise EOFError("socket closed while reading frame")
        chunks.extend(chunk)
    return bytes(chunks)


def _read_frame(sock: socket.socket) -> bytes:
    length = U32.unpack(_read_exact(sock, U32.size))[0]
    return _read_exact(sock, length) if length else b""


def _configure_low_latency(sock: socket.socket) -> None:
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)


def _make_aura(cache_dir: str) -> ProductionHybridCompressor:
    return ProductionHybridCompressor(
        enable_aura=True,
        enable_audit_logging=False,
        enable_fast_path=True,
        enable_sidechain=False,
        enable_scorer=False,
        enable_ml_selection=False,
        template_sync_interval_seconds=None,
        template_cache_dir=cache_dir,
    )


def _update_digest(digest: "hashlib._Hash", payload: bytes) -> None:
    digest.update(U32.pack(len(payload)))
    digest.update(payload)


def _load_session_templates(path: str) -> tuple[tuple[int, str], ...]:
    data = json.loads(Path(path).read_text())
    return normalize_aiwire_session_templates(data)


def _client_session_templates(
    args: argparse.Namespace,
    frames: list[bytes],
) -> tuple[tuple[int, str], ...]:
    templates: dict[int, str] = {}
    if args.session_template_file:
        templates.update(dict(_load_session_templates(args.session_template_file)))

    if args.discover_session_templates:
        sample_size = min(len(frames), max(1, args.session_template_sample_size))
        templates.update(
            discover_ai_wire_session_templates(
                frames[:sample_size],
                max_templates=args.session_template_limit,
                min_frequency=args.session_template_min_frequency,
                compression_threshold=args.session_template_threshold,
            )
        )

    normalized = normalize_aiwire_session_templates(templates)
    if args.force_session_templates and not normalized:
        raise RuntimeError(
            "AIWire session templates were forced but no templates were loaded or discovered"
        )
    return normalized


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * pct)))
    return ordered[index]


def _response_for(index: int, request: bytes) -> bytes:
    request_sha = hashlib.sha256(request).hexdigest()
    try:
        request_json = json.loads(request)
        trace_id = request_json.get("trace_id") or request_json.get("params", {}).get(
            "message", {}
        ).get("metadata", {}).get("trace_id")
        protocol = request_json.get("protocol", "unknown")
    except json.JSONDecodeError:
        trace_id = None
        protocol = "unknown"

    response = {
        "protocol": "agent.response",
        "jsonrpc": "2.0",
        "id": index,
        "trace_id": trace_id or f"stress-trace-{index // 8:05d}",
        "request": {
            "protocol": protocol,
            "sha256": request_sha,
            "sequence": index,
        },
        "result": {
            "agent": "z6-verifier",
            "status": "accepted" if index % 17 else "needs_review",
            "confidence": round(0.82 + (index % 11) / 100, 3),
            "tool_results": [
                {
                    "name": "policy_check",
                    "ok": True,
                    "elapsed_ms": 3 + index % 9,
                    "summary": "message shape verified and routed",
                },
                {
                    "name": "memory_route",
                    "ok": True,
                    "elapsed_ms": 2 + index % 5,
                    "summary": "trace and task metadata indexed",
                },
            ],
            "next_actions": [
                {"agent": "planner", "action": "continue", "state": "ready"},
                {"agent": "observer", "action": "record_latency", "state": "queued"},
            ],
        },
        "metadata": {
            "transport": "aura.aiwire.stress",
            "exchange": index,
            "request_bytes": len(request),
        },
    }
    return _json_bytes(response)


@dataclass
class CodecSession:
    codec: str
    level: int = AI_WIRE_DEFAULT_LEVEL
    cache_dir: str = "/tmp/aura-aiwire-stress-cache"
    session_templates: AIWireSessionTemplates | None = None

    def __post_init__(self) -> None:
        self.encoder: AIWireSessionEncoder | None = None
        self.decoder: AIWireSessionDecoder | None = None
        self.token_encoder: AIWireTokenSessionEncoder | None = None
        self.token_decoder: AIWireTokenSessionDecoder | None = None
        self.token_aiwire_encoder: AIWireTokenAIWireSessionEncoder | None = None
        self.token_aiwire_decoder: AIWireTokenAIWireSessionDecoder | None = None
        self.aura: ProductionHybridCompressor | None = None
        self.backend = self.codec
        if self.codec == "aiwire":
            self.encoder = AIWireSessionEncoder(
                level=self.level,
                session_templates=self.session_templates,
            )
            self.decoder = AIWireSessionDecoder(session_templates=self.session_templates)
            self.backend = self.encoder.backend
        elif self.codec == "aitoken":
            self.token_encoder = AIWireTokenSessionEncoder()
            self.token_decoder = AIWireTokenSessionDecoder()
            self.backend = f"aitoken+{self.token_encoder.backend}"
        elif self.codec == "aitoken_aiwire":
            self.token_aiwire_encoder = AIWireTokenAIWireSessionEncoder(
                level=self.level,
                session_templates=self.session_templates,
            )
            self.token_aiwire_decoder = AIWireTokenAIWireSessionDecoder(
                session_templates=self.session_templates
            )
            self.backend = self.token_aiwire_encoder.backend
        elif self.codec == "aura":
            self.aura = _make_aura(self.cache_dir)
            self.backend = "aura"

    def encode(self, payload: bytes) -> bytes:
        if self.codec == "raw":
            return payload
        if self.codec == "zlib":
            return zlib.compress(payload, 3)
        if self.codec == "aitoken":
            assert self.token_encoder is not None
            return self.token_encoder.encode_frame(payload)
        if self.codec == "aitoken_aiwire":
            assert self.token_aiwire_encoder is not None
            return self.token_aiwire_encoder.encode_frame(payload)
        if self.codec == "aura":
            assert self.aura is not None
            compressed, _method, _meta = self.aura.compress(payload.decode("utf-8"))
            return compressed
        if self.codec == "aiwire":
            assert self.encoder is not None
            return self.encoder.compress_frame(payload)
        raise ValueError(f"unsupported codec: {self.codec}")

    def decode(self, payload: bytes) -> bytes:
        if self.codec == "raw":
            return payload
        if self.codec == "zlib":
            return zlib.decompress(payload)
        if self.codec == "aitoken":
            assert self.token_decoder is not None
            return self.token_decoder.decode_frame(payload)
        if self.codec == "aitoken_aiwire":
            assert self.token_aiwire_decoder is not None
            return self.token_aiwire_decoder.decode_frame(payload)
        if self.codec == "aura":
            assert self.aura is not None
            restored = self.aura.decompress(payload)
            return restored.encode("utf-8") if isinstance(restored, str) else bytes(restored)
        if self.codec == "aiwire":
            assert self.decoder is not None
            return self.decoder.decompress_frame(payload)
        raise ValueError(f"unsupported codec: {self.codec}")


@dataclass
class InFlightRequest:
    index: int
    sha256: str
    start_ns: int


def _server_negotiate(
    hello: dict[str, Any],
) -> tuple[str, dict[str, Any] | None, tuple[tuple[int, str], ...]]:
    requested_codec = hello["codec"]
    if requested_codec not in AIWIRE_NEGOTIATED_CODECS:
        return requested_codec, None, ()

    peer_handshake = AIWireHandshake.from_dict(hello["aiwire_handshake"])
    session_templates = peer_handshake.session_templates

    negotiation = negotiate_aiwire_handshake(
        peer_handshake,
        level=int(hello.get("aiwire_level", AI_WIRE_DEFAULT_LEVEL)),
        fallback_codecs=("zlib", "raw"),
        allow_fallback=bool(hello.get("allow_aiwire_fallback", False)),
        session_templates=session_templates,
        require_session_templates=peer_handshake.require_session_templates,
    )
    payload = negotiation.to_dict()
    if not negotiation.accepted:
        return "", payload, ()
    negotiated_codec = requested_codec if negotiation.codec == "aiwire" else negotiation.codec
    return (
        negotiated_codec,
        payload,
        session_templates if negotiated_codec in AIWIRE_NEGOTIATED_CODECS else (),
    )


def server_once(
    conn: socket.socket,
    cache_dir: str = "/tmp/aura-aiwire-stress-server-cache",
    link_mbps: float = 0.0,
    one_way_delay_ms: float = 0.0,
    jitter_ms: float = 0.0,
    tail_pause_probability: float = 0.0,
    tail_pause_ms: float = 0.0,
    impairment_seed: int = 1729,
) -> None:
    hello = json.loads(_read_frame(conn))
    requested_codec = hello["codec"]
    exchanges = int(hello["exchanges"])
    duration_mode = bool(hello.get("duration_mode", False))
    codec, negotiation, session_templates = _server_negotiate(hello)
    if not codec:
        _write_frame(
            conn,
            _json_bytes(
                {
                    "accepted": False,
                    "codec": requested_codec,
                    "negotiated_codec": "",
                    "server_link_mbps": link_mbps,
                    "server_one_way_delay_ms": one_way_delay_ms,
                    "server_jitter_ms": jitter_ms,
                    "server_tail_pause_probability": tail_pause_probability,
                    "server_tail_pause_ms": tail_pause_ms,
                    "aiwire_negotiation": negotiation,
                }
            ),
        )
        return

    session = CodecSession(
        codec=codec,
        level=int(hello.get("aiwire_level", AI_WIRE_DEFAULT_LEVEL)),
        cache_dir=cache_dir,
        session_templates=session_templates,
    )
    _write_frame(
        conn,
        _json_bytes(
            {
                "accepted": True,
                "codec": requested_codec,
                "negotiated_codec": codec,
                "backend": session.backend,
                "server_link_mbps": link_mbps,
                "server_one_way_delay_ms": one_way_delay_ms,
                "server_jitter_ms": jitter_ms,
                "server_tail_pause_probability": tail_pause_probability,
                "server_tail_pause_ms": tail_pause_ms,
                "session_template_count": len(session_templates),
                "session_template_sha256": aiwire_session_templates_sha256(session_templates),
                "aiwire_negotiation": negotiation,
            }
        ),
    )
    out_writer = AsyncFrameWriter(
        conn,
        link_mbps,
        one_way_delay_ms,
        jitter_ms,
        tail_pause_probability,
        tail_pause_ms,
        impairment_seed,
    )

    request_digest = hashlib.sha256()
    response_digest = hashlib.sha256()
    raw_request_bytes = 0
    raw_response_bytes = 0
    request_wire_bytes = 0
    response_wire_bytes = 0
    server_decompress_ns = 0
    server_compress_ns = 0

    index = 0
    while duration_mode or index < exchanges:
        wire_request = _read_frame(conn)
        if not wire_request:
            if duration_mode:
                break
            raise EOFError("client stopped before completing fixed exchange count")
        request_wire_bytes += len(wire_request)

        start = time.perf_counter_ns()
        request = session.decode(wire_request)
        server_decompress_ns += time.perf_counter_ns() - start

        raw_request_bytes += len(request)
        _update_digest(request_digest, request)

        response = _response_for(index, request)
        raw_response_bytes += len(response)
        _update_digest(response_digest, response)

        start = time.perf_counter_ns()
        wire_response = session.encode(response)
        server_compress_ns += time.perf_counter_ns() - start
        response_wire_bytes += len(wire_response)
        out_writer.write(wire_response)
        index += 1

    out_writer.close()
    _write_frame(
        conn,
        _json_bytes(
            {
                "codec": requested_codec,
                "negotiated_codec": codec,
                "backend": session.backend,
                "exchanges": index,
                "raw_request_bytes": raw_request_bytes,
                "raw_response_bytes": raw_response_bytes,
                "request_wire_bytes": request_wire_bytes,
                "response_wire_bytes": response_wire_bytes,
                "framed_request_wire_bytes": request_wire_bytes + index * U32.size,
                "framed_response_wire_bytes": response_wire_bytes + index * U32.size,
                "link_mbps": link_mbps,
                "one_way_delay_ms": one_way_delay_ms,
                "jitter_ms": jitter_ms,
                "tail_pause_probability": tail_pause_probability,
                "tail_pause_ms": tail_pause_ms,
                "server_decompress_ms": server_decompress_ns / 1_000_000,
                "server_compress_ms": server_compress_ns / 1_000_000,
                "request_sha256": request_digest.hexdigest(),
                "response_sha256": response_digest.hexdigest(),
            }
        ),
    )


def run_server(args: argparse.Namespace) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((args.host, args.port))
        server.listen(8)
        for _ in range(args.runs):
            conn, _addr = server.accept()
            with conn:
                _configure_low_latency(conn)
                server_once(
                    conn,
                    cache_dir=args.cache_dir,
                    link_mbps=args.link_mbps,
                    one_way_delay_ms=args.one_way_delay_ms,
                    jitter_ms=args.jitter_ms,
                    tail_pause_probability=args.tail_pause_probability,
                    tail_pause_ms=args.tail_pause_ms,
                    impairment_seed=args.impairment_seed,
                )


def _client_stress_codec(
    codec: str,
    frames: list[bytes],
    args: argparse.Namespace,
) -> dict[str, Any]:
    duration_mode = args.seconds > 0
    agent_count = max(1, args.agent_count)
    per_agent_pipeline_window = max(1, args.pipeline_window)
    aggregate_pipeline_window = agent_count * per_agent_pipeline_window
    session_templates: tuple[tuple[int, str], ...] = ()
    if codec in AIWIRE_NEGOTIATED_CODECS:
        session_templates = _client_session_templates(args, frames)
    hello: dict[str, Any] = {
        "codec": codec,
        "exchanges": 0 if duration_mode else args.exchanges,
        "duration_mode": duration_mode,
        "duration_seconds": args.seconds if duration_mode else 0,
        "client_link_mbps": args.link_mbps,
        "client_one_way_delay_ms": args.one_way_delay_ms,
        "client_jitter_ms": args.jitter_ms,
        "client_tail_pause_probability": args.tail_pause_probability,
        "client_tail_pause_ms": args.tail_pause_ms,
        "agent_count": agent_count,
        "per_agent_pipeline_window": per_agent_pipeline_window,
        "aggregate_pipeline_window": aggregate_pipeline_window,
    }
    if codec in AIWIRE_NEGOTIATED_CODECS:
        hello.update(
            {
                "aiwire_level": args.aiwire_level,
                "allow_aiwire_fallback": args.allow_aiwire_fallback,
                "aiwire_handshake": build_aiwire_handshake(
                    level=args.aiwire_level,
                    fallback_codecs=("zlib", "raw") if args.allow_aiwire_fallback else (),
                    session_templates=session_templates,
                    require_session_templates=args.force_session_templates,
                ).to_dict(),
            }
        )

    request_digest = hashlib.sha256()
    response_digest = hashlib.sha256()
    raw_request_bytes = 0
    raw_response_bytes = 0
    request_wire_bytes = 0
    response_wire_bytes = 0
    client_compress_ns = 0
    client_decompress_ns = 0
    exchange_ms: list[float] = []

    connect_start = time.perf_counter_ns()
    with socket.create_connection((args.host, args.port), timeout=args.timeout) as sock:
        _configure_low_latency(sock)
        _write_frame(sock, _json_bytes(hello))
        ack = json.loads(_read_frame(sock))
        handshake_ms = (time.perf_counter_ns() - connect_start) / 1_000_000
        if not ack.get("accepted"):
            raise RuntimeError(f"{codec} stress negotiation failed: {ack}")

        negotiated_codec = ack["negotiated_codec"]
        session = CodecSession(
            codec=negotiated_codec,
            level=args.aiwire_level,
            cache_dir=args.cache_dir,
            session_templates=(
                session_templates if negotiated_codec in AIWIRE_NEGOTIATED_CODECS else None
            ),
        )
        out_writer = AsyncFrameWriter(
            sock,
            args.link_mbps,
            args.one_way_delay_ms,
            args.jitter_ms,
            args.tail_pause_probability,
            args.tail_pause_ms,
            args.impairment_seed,
        )
        stress_start = time.perf_counter_ns()
        deadline_ns = stress_start + int(args.seconds * 1_000_000_000) if duration_mode else None
        deadline_completed_exchanges = 0
        sent_exchanges = 0
        outstanding: deque[InFlightRequest] = deque()

        def can_send_more() -> bool:
            if len(outstanding) >= aggregate_pipeline_window:
                return False
            if duration_mode:
                assert deadline_ns is not None
                return time.perf_counter_ns() < deadline_ns
            return sent_exchanges < len(frames)

        def send_next() -> None:
            nonlocal client_compress_ns, raw_request_bytes, request_wire_bytes, sent_exchanges
            request = (
                frames[sent_exchanges % len(frames)] if duration_mode else frames[sent_exchanges]
            )
            request_sha = hashlib.sha256(request).hexdigest()
            exchange_start = time.perf_counter_ns()

            raw_request_bytes += len(request)
            _update_digest(request_digest, request)

            start = time.perf_counter_ns()
            wire_request = session.encode(request)
            client_compress_ns += time.perf_counter_ns() - start
            request_wire_bytes += len(wire_request)
            out_writer.write(wire_request)
            outstanding.append(InFlightRequest(sent_exchanges, request_sha, exchange_start))
            sent_exchanges += 1

        def receive_next() -> None:
            nonlocal client_decompress_ns, raw_response_bytes, response_wire_bytes, deadline_completed_exchanges
            wire_response = _read_frame(sock)
            response_wire_bytes += len(wire_response)
            start = time.perf_counter_ns()
            response = session.decode(wire_response)
            client_decompress_ns += time.perf_counter_ns() - start
            completed_ns = time.perf_counter_ns()

            expected = outstanding.popleft()
            response_json = json.loads(response)
            if response_json["request"]["sha256"] != expected.sha256:
                raise RuntimeError(
                    f"{codec} response verification failed at exchange {expected.index}"
                )

            raw_response_bytes += len(response)
            _update_digest(response_digest, response)
            exchange_ms.append((completed_ns - expected.start_ns) / 1_000_000)
            if deadline_ns is None or completed_ns <= deadline_ns:
                deadline_completed_exchanges += 1

        while can_send_more():
            send_next()

        while outstanding or can_send_more():
            if outstanding:
                receive_next()
            while can_send_more():
                send_next()

        if duration_mode:
            out_writer.write(b"")
        out_writer.close()
        stress_ms = (time.perf_counter_ns() - stress_start) / 1_000_000
        server_summary = json.loads(_read_frame(sock))

    if server_summary["request_sha256"] != request_digest.hexdigest():
        raise RuntimeError(f"{codec} server request digest mismatch")
    if server_summary["response_sha256"] != response_digest.hexdigest():
        raise RuntimeError(f"{codec} response digest mismatch")

    total_raw = raw_request_bytes + raw_response_bytes
    total_wire = request_wire_bytes + response_wire_bytes
    framed_request_wire = request_wire_bytes + len(exchange_ms) * U32.size
    framed_response_wire = response_wire_bytes + len(exchange_ms) * U32.size
    framed_wire = framed_request_wire + framed_response_wire
    completed_exchanges = max(1, len(exchange_ms))
    request_framed_bytes_per_exchange = framed_request_wire / completed_exchanges
    response_framed_bytes_per_exchange = framed_response_wire / completed_exchanges
    client_link_bytes_per_second = args.link_mbps * 1_000_000 / 8 if args.link_mbps else 0.0
    server_link_mbps = float(ack.get("server_link_mbps") or 0.0)
    server_link_bytes_per_second = server_link_mbps * 1_000_000 / 8 if server_link_mbps else 0.0
    request_capacity_exchanges_per_second = (
        client_link_bytes_per_second / request_framed_bytes_per_exchange
        if client_link_bytes_per_second and request_framed_bytes_per_exchange
        else 0.0
    )
    response_capacity_exchanges_per_second = (
        server_link_bytes_per_second / response_framed_bytes_per_exchange
        if server_link_bytes_per_second and response_framed_bytes_per_exchange
        else 0.0
    )
    if request_capacity_exchanges_per_second and response_capacity_exchanges_per_second:
        bandwidth_capacity_exchanges_per_second = min(
            request_capacity_exchanges_per_second,
            response_capacity_exchanges_per_second,
        )
        bandwidth_bottleneck_direction = (
            "request"
            if request_capacity_exchanges_per_second <= response_capacity_exchanges_per_second
            else "response"
        )
    else:
        bandwidth_capacity_exchanges_per_second = 0.0
        bandwidth_bottleneck_direction = ""
    return {
        "codec": codec,
        "negotiated_codec": negotiated_codec,
        "backend": ack.get("backend"),
        "duration_mode": duration_mode,
        "target_seconds": args.seconds if duration_mode else 0,
        "client_link_mbps": args.link_mbps,
        "server_link_mbps": ack.get("server_link_mbps"),
        "client_one_way_delay_ms": args.one_way_delay_ms,
        "server_one_way_delay_ms": ack.get("server_one_way_delay_ms"),
        "client_jitter_ms": args.jitter_ms,
        "server_jitter_ms": ack.get("server_jitter_ms"),
        "client_tail_pause_probability": args.tail_pause_probability,
        "server_tail_pause_probability": ack.get("server_tail_pause_probability"),
        "client_tail_pause_ms": args.tail_pause_ms,
        "server_tail_pause_ms": ack.get("server_tail_pause_ms"),
        "session_template_count": (
            len(session_templates) if codec in AIWIRE_NEGOTIATED_CODECS else 0
        ),
        "session_template_sha256": (
            aiwire_session_templates_sha256(session_templates)
            if codec in AIWIRE_NEGOTIATED_CODECS
            else ""
        ),
        "agent_count": agent_count,
        "per_agent_pipeline_window": per_agent_pipeline_window,
        "aggregate_pipeline_window": aggregate_pipeline_window,
        "pipeline_window": aggregate_pipeline_window,
        "sent_exchanges": sent_exchanges,
        "deadline_completed_exchanges": deadline_completed_exchanges,
        "deadline_exchanges_per_second": (
            deadline_completed_exchanges / args.seconds if duration_mode and args.seconds else 0
        ),
        "exchanges": len(exchange_ms),
        "handshake_ms": handshake_ms,
        "stress_ms": stress_ms,
        "exchanges_per_second": len(exchange_ms) / (stress_ms / 1000) if stress_ms else 0,
        "roundtrip_ms_avg": sum(exchange_ms) / len(exchange_ms) if exchange_ms else 0,
        "roundtrip_ms_p50": _percentile(exchange_ms, 0.50),
        "roundtrip_ms_p95": _percentile(exchange_ms, 0.95),
        "roundtrip_ms_p99": _percentile(exchange_ms, 0.99),
        "raw_bytes": total_raw,
        "wire_bytes": total_wire,
        "framed_wire_bytes": framed_wire,
        "framed_bytes_per_exchange": framed_wire / completed_exchanges,
        "request_framed_bytes_per_exchange": request_framed_bytes_per_exchange,
        "response_framed_bytes_per_exchange": response_framed_bytes_per_exchange,
        "bandwidth_capacity_exchanges_per_second": bandwidth_capacity_exchanges_per_second,
        "bandwidth_capacity_completed": (
            bandwidth_capacity_exchanges_per_second * args.seconds if duration_mode else 0.0
        ),
        "bandwidth_utilization_percent": (
            deadline_completed_exchanges
            / args.seconds
            / bandwidth_capacity_exchanges_per_second
            * 100
            if duration_mode and args.seconds and bandwidth_capacity_exchanges_per_second
            else 0.0
        ),
        "request_capacity_exchanges_per_second": request_capacity_exchanges_per_second,
        "response_capacity_exchanges_per_second": response_capacity_exchanges_per_second,
        "bandwidth_bottleneck_direction": bandwidth_bottleneck_direction,
        "ratio": total_raw / total_wire if total_wire else 0,
        "framed_ratio": total_raw / framed_wire if framed_wire else 0,
        "wire_saved_percent": (1 - total_wire / total_raw) * 100 if total_raw else 0,
        "framed_wire_saved_percent": (1 - framed_wire / total_raw) * 100 if total_raw else 0,
        "raw_request_bytes": raw_request_bytes,
        "raw_response_bytes": raw_response_bytes,
        "request_wire_bytes": request_wire_bytes,
        "response_wire_bytes": response_wire_bytes,
        "framed_request_wire_bytes": framed_request_wire,
        "framed_response_wire_bytes": framed_response_wire,
        "client_compress_ms": client_compress_ns / 1_000_000,
        "client_decompress_ms": client_decompress_ns / 1_000_000,
        "server_compress_ms": server_summary["server_compress_ms"],
        "server_decompress_ms": server_summary["server_decompress_ms"],
        "verified": True,
        "aiwire_negotiation": ack.get("aiwire_negotiation"),
    }


def run_client(args: argparse.Namespace) -> None:
    frames = build_ai_wire_messages(args.exchanges, args.seed)
    results = []
    for codec in args.codecs.split(","):
        codec = codec.strip()
        results.append(_client_stress_codec(codec, frames, args))

    output = {"results": results}
    print(json.dumps(output, indent=2, sort_keys=True))
    if args.output:
        Path(args.output).write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)

    server = sub.add_parser("server")
    server.add_argument("--host", default="0.0.0.0")
    server.add_argument("--port", type=int, default=8910)
    server.add_argument("--runs", type=int, default=1)
    server.add_argument("--cache-dir", default="/tmp/aura-aiwire-stress-server-cache")
    server.add_argument(
        "--link-mbps", type=float, default=0.0, help="per-direction egress rate; 0 is unlimited"
    )
    server.add_argument(
        "--one-way-delay-ms", type=float, default=0.0, help="egress propagation delay per frame"
    )
    server.add_argument(
        "--jitter-ms", type=float, default=0.0, help="uniform +/- egress jitter per frame"
    )
    server.add_argument(
        "--tail-pause-probability",
        type=float,
        default=0.0,
        help="probability that an egress frame receives an extra queue/retransmit-style delay",
    )
    server.add_argument(
        "--tail-pause-ms",
        type=float,
        default=0.0,
        help="maximum extra delay for tail-pause events",
    )
    server.add_argument("--impairment-seed", type=int, default=1729)
    server.set_defaults(func=run_server)

    client = sub.add_parser("client")
    client.add_argument("--host", required=True)
    client.add_argument("--port", type=int, default=8910)
    client.add_argument("--exchanges", type=int, default=5000)
    client.add_argument("--seconds", type=float, default=0.0)
    client.add_argument("--seed", type=int, default=1729)
    client.add_argument("--codecs", default="raw,zlib,aura,aiwire")
    client.add_argument("--aiwire-level", type=int, default=AI_WIRE_DEFAULT_LEVEL)
    client.add_argument("--allow-aiwire-fallback", action="store_true")
    client.add_argument(
        "--session-template-file",
        help="JSON mapping/list of AIWire session templates to require in the handshake",
    )
    client.add_argument(
        "--discover-session-templates",
        action="store_true",
        help="discover bounded AIWire session templates from the benchmark corpus",
    )
    client.add_argument(
        "--force-session-templates",
        action="store_true",
        help="fail AIWire negotiation unless the session template set is non-empty and matched",
    )
    client.add_argument("--session-template-limit", type=int, default=16)
    client.add_argument("--session-template-sample-size", type=int, default=256)
    client.add_argument("--session-template-min-frequency", type=int, default=2)
    client.add_argument("--session-template-threshold", type=float, default=1.01)
    client.add_argument("--cache-dir", default="/tmp/aura-aiwire-stress-client-cache")
    client.add_argument("--timeout", type=float, default=120.0)
    client.add_argument(
        "--link-mbps", type=float, default=0.0, help="per-direction egress rate; 0 is unlimited"
    )
    client.add_argument(
        "--one-way-delay-ms", type=float, default=0.0, help="egress propagation delay per frame"
    )
    client.add_argument(
        "--jitter-ms", type=float, default=0.0, help="uniform +/- egress jitter per frame"
    )
    client.add_argument(
        "--tail-pause-probability",
        type=float,
        default=0.0,
        help="probability that an egress frame receives an extra queue/retransmit-style delay",
    )
    client.add_argument(
        "--tail-pause-ms",
        type=float,
        default=0.0,
        help="maximum extra delay for tail-pause events",
    )
    client.add_argument("--impairment-seed", type=int, default=1729)
    client.add_argument(
        "--pipeline-window",
        type=int,
        default=1,
        help="maximum in-flight request frames per logical agent",
    )
    client.add_argument(
        "--agent-count",
        type=int,
        default=1,
        help="logical agents sharing the session; aggregate window is agent-count * pipeline-window",
    )
    client.add_argument("--output")
    client.set_defaults(func=run_client)

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
