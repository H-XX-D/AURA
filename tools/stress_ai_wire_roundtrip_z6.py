#!/usr/bin/env python3
"""Bidirectional AIWire stress benchmark over a real TCP link."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import multiprocessing as mp
import queue
import random
import socket
import struct
import sys
import threading
import time
import zlib
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from aura_compression.ai_wire import (
    AI_WIRE_DEFAULT_LEVEL,
    AIWireHandshake,
    AIWireNativeError,
    AIWireSessionDecoder,
    AIWireSessionEncoder,
    AIWireSessionTemplates,
    aiwire_session_templates_sha256,
    build_ai_wire_messages,
    build_aiwire_handshake,
    discover_ai_wire_session_templates,
    encode_ai_wire_message,
    negotiate_aiwire_handshake,
    negotiate_aiwire_nary_handshake,
    normalize_aiwire_session_templates,
)
from aura_compression.ai_wire_fixtures import load_aiwire_session_fixture_corpus
from aura_compression.ai_wire_token import (
    AIWireTokenAIWireSessionDecoder,
    AIWireTokenAIWireSessionEncoder,
    AIWireTokenSessionDecoder,
    AIWireTokenSessionEncoder,
)
from aura_compression.compressor_refactored import ProductionHybridCompressor

U32 = struct.Struct("!I")
AIWIRE_NEGOTIATED_CODECS = {"aiwire", "aitoken_aiwire"}
STRESS_BACKENDS = ("python", "native", "auto")
STRESS_COORDINATORS = ("threaded", "asyncio")
DEFAULT_FIXTURE_CORPUS = ROOT / "fixtures" / "aiwire_sessions" / "public_session_corpus_v1.json"


def _use_native_for_backend(backend: str) -> bool | None:
    if backend == "python":
        return False
    if backend == "native":
        return True
    if backend == "auto":
        return None
    choices = ", ".join(STRESS_BACKENDS)
    raise ValueError(f"unsupported AIWire backend {backend!r}; choices: {choices}")


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

    async def consume_async(self, byte_count: int) -> None:
        if self.bytes_per_second <= 0 or byte_count <= 0:
            return
        self.bytes_sent += byte_count
        target_elapsed = self.bytes_sent / self.bytes_per_second
        actual_elapsed = (time.perf_counter_ns() - self.start_ns) / 1_000_000_000
        delay = target_elapsed - actual_elapsed
        if delay > 0:
            await asyncio.sleep(delay)


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


class AsyncStreamFrameWriter:
    """Asyncio equivalent of AsyncFrameWriter for coordinator-side fan-out."""

    def __init__(
        self,
        writer: asyncio.StreamWriter,
        mbps: float,
        one_way_delay_ms: float = 0.0,
        jitter_ms: float = 0.0,
        tail_pause_probability: float = 0.0,
        tail_pause_ms: float = 0.0,
        seed: int = 1729,
    ) -> None:
        self.writer = writer
        self.bandwidth = BandwidthLimiter(mbps)
        self.one_way_delay_ms = max(0.0, one_way_delay_ms)
        self.jitter_ms = max(0.0, jitter_ms)
        self.tail_pause_probability = min(1.0, max(0.0, tail_pause_probability))
        self.tail_pause_ms = max(0.0, tail_pause_ms)
        self.rng = random.Random(seed)
        self.frames: asyncio.Queue[bytes | None] = asyncio.Queue()
        self.ready_frames: asyncio.Queue[tuple[int, bytes] | None] = asyncio.Queue()
        self.error: BaseException | None = None
        self.serializer_task = asyncio.create_task(self._serialize())
        self.sender_task = asyncio.create_task(self._send_ready())

    def write(self, payload: bytes) -> None:
        self._raise_error()
        self.frames.put_nowait(payload)

    async def flush(self) -> None:
        await self.frames.join()
        await self.ready_frames.join()
        self._raise_error()

    async def close(self) -> None:
        self.frames.put_nowait(None)
        await self.frames.join()
        await self.ready_frames.join()
        await self.serializer_task
        await self.sender_task
        self._raise_error()

    async def _serialize(self) -> None:
        while True:
            payload = await self.frames.get()
            try:
                if payload is None:
                    await self.ready_frames.put(None)
                    return
                await self.bandwidth.consume_async(U32.size + len(payload))
                await self.ready_frames.put((self._arrival_due_ns(), payload))
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

    async def _send_ready(self) -> None:
        while True:
            item = await self.ready_frames.get()
            try:
                if item is None:
                    return
                due_ns, payload = item
                delay_ns = due_ns - time.perf_counter_ns()
                if delay_ns > 0:
                    await asyncio.sleep(delay_ns / 1_000_000_000)
                self.writer.write(U32.pack(len(payload)))
                if payload:
                    self.writer.write(payload)
                await self.writer.drain()
            except BaseException as exc:  # pragma: no cover - surfaced through flush/close.
                self.error = exc
            finally:
                self.ready_frames.task_done()

    def _raise_error(self) -> None:
        if self.error is not None:
            raise RuntimeError("async stream frame writer failed") from self.error


def _json_bytes(value: Any) -> bytes:
    return encode_ai_wire_message(value)


def _write_frame(sock: socket.socket, payload: bytes) -> None:
    sock.sendall(U32.pack(len(payload)))
    if payload:
        sock.sendall(payload)


async def _async_write_frame(writer: asyncio.StreamWriter, payload: bytes) -> None:
    writer.write(U32.pack(len(payload)))
    if payload:
        writer.write(payload)
    await writer.drain()


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


async def _async_read_exact(reader: asyncio.StreamReader, size: int) -> bytes:
    try:
        return await reader.readexactly(size)
    except asyncio.IncompleteReadError as exc:
        raise EOFError("socket closed while reading frame") from exc


async def _async_read_frame(reader: asyncio.StreamReader) -> bytes:
    length = U32.unpack(await _async_read_exact(reader, U32.size))[0]
    return await _async_read_exact(reader, length) if length else b""


def _configure_low_latency(sock: socket.socket) -> None:
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)


def _configure_async_low_latency(writer: asyncio.StreamWriter) -> None:
    raw_sock = writer.get_extra_info("socket")
    if raw_sock is not None:
        raw_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)


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


@dataclass(frozen=True)
class FixtureReplayCorpus:
    path: str
    schema: str
    session_count: int
    exchange_count: int
    request_frames: tuple[bytes, ...]
    response_frames: tuple[bytes, ...]
    session_templates: tuple[tuple[int, str], ...]
    session_template_mode: str
    request_sha256: str
    response_sha256: str


def _digest_frames(frames: Iterable[bytes]) -> str:
    digest = hashlib.sha256()
    for frame in frames:
        _update_digest(digest, frame)
    return digest.hexdigest()


def _merge_fixture_templates(
    sessions: Iterable[dict[str, Any]],
    *,
    mode: str,
) -> tuple[tuple[int, str], ...]:
    if mode == "none":
        return ()
    if mode not in {"initial", "updated"}:
        raise ValueError("fixture session template mode must be one of: none, initial, updated")

    field = "initial_session_templates" if mode == "initial" else "updated_session_templates"
    merged: dict[int, str] = {}
    for session in sessions:
        for entry in session[field]:
            template_id = int(entry["template_id"])
            pattern = str(entry["pattern"])
            existing = merged.get(template_id)
            if existing is not None and existing != pattern:
                raise ValueError(
                    f"fixture template {template_id} has conflicting patterns across sessions"
                )
            merged[template_id] = pattern
    return normalize_aiwire_session_templates(merged)


def _load_fixture_replay_corpus(
    path: str | Path,
    *,
    session_template_mode: str = "updated",
) -> FixtureReplayCorpus:
    fixture_path = Path(path).expanduser()
    corpus = load_aiwire_session_fixture_corpus(fixture_path)
    request_frames: list[bytes] = []
    response_frames: list[bytes] = []
    sessions = list(corpus["sessions"])
    for session in sessions:
        events = sorted(session["events"], key=lambda event: int(event["sequence"]))
        for event in events:
            frame = encode_ai_wire_message(event["message"])
            if event["direction"] == "client_to_server":
                request_frames.append(frame)
            elif event["direction"] == "server_to_client":
                response_frames.append(frame)

    if not request_frames or not response_frames:
        raise ValueError(f"{fixture_path} did not contain replayable fixture frames")
    if len(request_frames) != len(response_frames):
        raise ValueError(
            f"{fixture_path} request/response fixture frame counts differ: "
            f"{len(request_frames)} != {len(response_frames)}"
        )

    templates = _merge_fixture_templates(sessions, mode=session_template_mode)
    return FixtureReplayCorpus(
        path=str(fixture_path),
        schema=str(corpus.get("schema", "")),
        session_count=int(corpus.get("session_count", len(sessions))),
        exchange_count=len(request_frames),
        request_frames=tuple(request_frames),
        response_frames=tuple(response_frames),
        session_templates=templates,
        session_template_mode=session_template_mode,
        request_sha256=_digest_frames(request_frames),
        response_sha256=_digest_frames(response_frames),
    )


def _repeat_frames(frames: tuple[bytes, ...], count: int) -> list[bytes]:
    if count <= 0:
        return []
    return [frames[index % len(frames)] for index in range(count)]


CLUSTER_VARIATION_ROLES = (
    "coordinator",
    "router",
    "planner",
    "tool-runner",
    "retriever",
    "critic",
    "memory-writer",
    "monitor",
)
CLUSTER_VARIATION_WORKLOADS = (
    "mcp_tool_call",
    "a2a_task_delta",
    "openai_response_stream",
    "local_agent_trace",
    "handoff_review",
    "memory_commit",
    "artifact_update",
    "health_check",
)
CLUSTER_VARIATION_ZONES = ("lab-a", "lab-b", "edge-mesh", "desk-lan")


def _fixture_peer_seed(peer_label: str) -> int:
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

    peer_seed = _fixture_peer_seed(peer_label)
    role = CLUSTER_VARIATION_ROLES[(peer_seed + exchange_index) % len(CLUSTER_VARIATION_ROLES)]
    workload = CLUSTER_VARIATION_WORKLOADS[
        (peer_seed // 3 + exchange_index * 2) % len(CLUSTER_VARIATION_WORKLOADS)
    ]
    zone = CLUSTER_VARIATION_ZONES[(peer_seed // 7 + exchange_index) % len(CLUSTER_VARIATION_ZONES)]
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

    return _json_bytes(message)


def _vary_fixture_frame(
    frame: bytes,
    *,
    direction: str,
    peer_label: str,
    exchange_index: int,
    profile: str,
) -> bytes:
    if profile == "none":
        return frame
    if profile == "cluster":
        return _cluster_variation_frame(
            frame,
            direction=direction,
            peer_label=peer_label,
            exchange_index=exchange_index,
        )
    raise ValueError(f"unsupported fixture variation profile: {profile}")


def _fixture_frame_for(
    fixture_replay: FixtureReplayCorpus,
    *,
    direction: str,
    exchange_index: int,
    profile: str,
    peer_label: str,
) -> bytes:
    frames = (
        fixture_replay.request_frames
        if direction == "client_to_server"
        else fixture_replay.response_frames
    )
    base = frames[exchange_index % fixture_replay.exchange_count]
    return _vary_fixture_frame(
        base,
        direction=direction,
        peer_label=peer_label,
        exchange_index=exchange_index,
        profile=profile,
    )


def _args_fixture_variation_profile(args: argparse.Namespace) -> str:
    return str(getattr(args, "fixture_variation_profile", "none") or "none")


def _args_fixture_peer_label(args: argparse.Namespace) -> str:
    return str(getattr(args, "fixture_peer_label", "client") or "client")


def _client_session_templates(
    args: argparse.Namespace,
    frames: list[bytes],
    fixture_replay: FixtureReplayCorpus | None = None,
) -> tuple[tuple[int, str], ...]:
    templates: dict[int, str] = {}
    if fixture_replay is not None:
        templates.update(dict(fixture_replay.session_templates))
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
    requested_backend: str = "python"

    def __post_init__(self) -> None:
        use_native = _use_native_for_backend(self.requested_backend)
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
                use_native=use_native,
            )
            self.decoder = AIWireSessionDecoder(
                session_templates=self.session_templates,
                use_native=use_native,
            )
            self.backend = self.encoder.backend
        elif self.codec == "aitoken":
            self.token_encoder = AIWireTokenSessionEncoder(use_native=use_native)
            self.token_decoder = AIWireTokenSessionDecoder(use_native=use_native)
            self.backend = f"aitoken+{self.token_encoder.backend}"
        elif self.codec == "aitoken_aiwire":
            self.token_aiwire_encoder = AIWireTokenAIWireSessionEncoder(
                level=self.level,
                session_templates=self.session_templates,
                use_native=use_native,
            )
            self.token_aiwire_decoder = AIWireTokenAIWireSessionDecoder(
                session_templates=self.session_templates,
                use_native=use_native,
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
    expected_response_sha256: str | None
    start_ns: int


@dataclass(frozen=True)
class RelayTarget:
    label: str
    host: str
    port: int


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
    backend: str = "python",
    link_mbps: float = 0.0,
    one_way_delay_ms: float = 0.0,
    jitter_ms: float = 0.0,
    tail_pause_probability: float = 0.0,
    tail_pause_ms: float = 0.0,
    impairment_seed: int = 1729,
    fixture_replay: FixtureReplayCorpus | None = None,
) -> None:
    hello = json.loads(_read_frame(conn))
    requested_codec = hello["codec"]
    exchanges = int(hello["exchanges"])
    duration_mode = bool(hello.get("duration_mode", False))
    session_shards = max(1, int(hello.get("session_shards", 1) or 1))
    session_shard = max(1, int(hello.get("session_shard", 1) or 1))
    connection_link_mbps = link_mbps / session_shards if link_mbps > 0 else 0.0
    fixture_requested = bool(hello.get("fixture_replay", False))
    fixture_variation_profile = str(hello.get("fixture_variation_profile", "none") or "none")
    fixture_peer_label = str(hello.get("fixture_peer_label", "peer") or "peer")
    if fixture_requested:
        if fixture_replay is None:
            _write_frame(
                conn,
                _json_bytes(
                    {
                        "accepted": False,
                        "codec": requested_codec,
                        "negotiated_codec": "",
                        "reason": "fixture_replay_not_configured_on_server",
                    }
                ),
            )
            return
        if hello.get("fixture_request_sha256") != fixture_replay.request_sha256:
            _write_frame(
                conn,
                _json_bytes(
                    {
                        "accepted": False,
                        "codec": requested_codec,
                        "negotiated_codec": "",
                        "reason": "fixture_request_sha256_mismatch",
                        "server_fixture_request_sha256": fixture_replay.request_sha256,
                    }
                ),
            )
            return
        if hello.get("fixture_response_sha256") != fixture_replay.response_sha256:
            _write_frame(
                conn,
                _json_bytes(
                    {
                        "accepted": False,
                        "codec": requested_codec,
                        "negotiated_codec": "",
                        "reason": "fixture_response_sha256_mismatch",
                        "server_fixture_response_sha256": fixture_replay.response_sha256,
                    }
                ),
            )
            return

    codec, negotiation, session_templates = _server_negotiate(hello)
    if bool(hello.get("handshake_probe", False)):
        if not codec:
            _write_frame(
                conn,
                _json_bytes(
                    {
                        "accepted": False,
                        "codec": requested_codec,
                        "negotiated_codec": "",
                        "server_link_mbps": connection_link_mbps,
                        "server_one_way_delay_ms": one_way_delay_ms,
                        "server_jitter_ms": jitter_ms,
                        "server_tail_pause_probability": tail_pause_probability,
                        "server_tail_pause_ms": tail_pause_ms,
                        "handshake_probe": True,
                        "aiwire_negotiation": negotiation,
                    }
                ),
            )
            return

        try:
            probe_session = CodecSession(
                codec=codec,
                level=int(hello.get("aiwire_level", AI_WIRE_DEFAULT_LEVEL)),
                cache_dir=cache_dir,
                session_templates=session_templates,
                requested_backend=backend,
            )
            probe_backend = probe_session.backend
        except AIWireNativeError as exc:
            _write_frame(
                conn,
                _json_bytes(
                    {
                        "accepted": False,
                        "codec": requested_codec,
                        "negotiated_codec": codec,
                        "reason": f"backend_unavailable: {exc}",
                        "requested_backend": backend,
                        "client_requested_backend": hello.get("aiwire_backend", ""),
                        "handshake_probe": True,
                        "aiwire_negotiation": negotiation,
                    }
                ),
            )
            return
        _write_frame(
            conn,
            _json_bytes(
                {
                    "accepted": True,
                    "codec": requested_codec,
                    "negotiated_codec": codec,
                    "backend": probe_backend,
                    "requested_backend": backend,
                    "client_requested_backend": hello.get("aiwire_backend", ""),
                    "server_link_mbps": connection_link_mbps,
                    "server_one_way_delay_ms": one_way_delay_ms,
                    "server_jitter_ms": jitter_ms,
                    "server_tail_pause_probability": tail_pause_probability,
                    "server_tail_pause_ms": tail_pause_ms,
                    "session_shard": session_shard,
                    "session_shards": session_shards,
                    "handshake_probe": True,
                    "session_template_count": len(session_templates),
                    "session_template_sha256": aiwire_session_templates_sha256(session_templates),
                    "fixture_replay": fixture_requested,
                    "fixture_variation_profile": fixture_variation_profile,
                    "fixture_peer_label": fixture_peer_label,
                    "fixture_corpus": fixture_replay.path if fixture_replay else "",
                    "fixture_schema": fixture_replay.schema if fixture_replay else "",
                    "fixture_exchange_count": (
                        fixture_replay.exchange_count if fixture_replay else 0
                    ),
                    "fixture_session_template_mode": (
                        fixture_replay.session_template_mode if fixture_replay else ""
                    ),
                    "fixture_request_sha256": (
                        fixture_replay.request_sha256 if fixture_replay else ""
                    ),
                    "fixture_response_sha256": (
                        fixture_replay.response_sha256 if fixture_replay else ""
                    ),
                    "aiwire_negotiation": negotiation,
                }
            ),
        )
        return

    if not codec:
        _write_frame(
            conn,
            _json_bytes(
                {
                    "accepted": False,
                    "codec": requested_codec,
                    "negotiated_codec": "",
                    "server_link_mbps": connection_link_mbps,
                    "server_one_way_delay_ms": one_way_delay_ms,
                    "server_jitter_ms": jitter_ms,
                    "server_tail_pause_probability": tail_pause_probability,
                    "server_tail_pause_ms": tail_pause_ms,
                    "aiwire_negotiation": negotiation,
                }
            ),
        )
        return

    try:
        session = CodecSession(
            codec=codec,
            level=int(hello.get("aiwire_level", AI_WIRE_DEFAULT_LEVEL)),
            cache_dir=cache_dir,
            session_templates=session_templates,
            requested_backend=backend,
        )
    except AIWireNativeError as exc:
        _write_frame(
            conn,
            _json_bytes(
                {
                    "accepted": False,
                    "codec": requested_codec,
                    "negotiated_codec": codec,
                    "reason": f"backend_unavailable: {exc}",
                    "requested_backend": backend,
                    "client_requested_backend": hello.get("aiwire_backend", ""),
                    "aiwire_negotiation": negotiation,
                }
            ),
        )
        return
    _write_frame(
        conn,
        _json_bytes(
            {
                "accepted": True,
                "codec": requested_codec,
                "negotiated_codec": codec,
                "backend": session.backend,
                "requested_backend": backend,
                "client_requested_backend": hello.get("aiwire_backend", ""),
                "server_link_mbps": connection_link_mbps,
                "server_one_way_delay_ms": one_way_delay_ms,
                "server_jitter_ms": jitter_ms,
                "server_tail_pause_probability": tail_pause_probability,
                "server_tail_pause_ms": tail_pause_ms,
                "session_shard": session_shard,
                "session_shards": session_shards,
                "session_template_count": len(session_templates),
                "session_template_sha256": aiwire_session_templates_sha256(session_templates),
                "fixture_replay": fixture_requested,
                "fixture_variation_profile": fixture_variation_profile,
                "fixture_peer_label": fixture_peer_label,
                "fixture_corpus": fixture_replay.path if fixture_replay else "",
                "fixture_schema": fixture_replay.schema if fixture_replay else "",
                "fixture_exchange_count": fixture_replay.exchange_count if fixture_replay else 0,
                "fixture_session_template_mode": (
                    fixture_replay.session_template_mode if fixture_replay else ""
                ),
                "fixture_request_sha256": fixture_replay.request_sha256 if fixture_replay else "",
                "fixture_response_sha256": fixture_replay.response_sha256 if fixture_replay else "",
                "aiwire_negotiation": negotiation,
            }
        ),
    )
    out_writer = AsyncFrameWriter(
        conn,
        connection_link_mbps,
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

        if fixture_requested:
            assert fixture_replay is not None
            expected_request = _fixture_frame_for(
                fixture_replay,
                direction="client_to_server",
                exchange_index=index,
                profile=fixture_variation_profile,
                peer_label=fixture_peer_label,
            )
            if hashlib.sha256(request).hexdigest() != hashlib.sha256(expected_request).hexdigest():
                raise RuntimeError(f"fixture request verification failed at exchange {index}")
            response = _fixture_frame_for(
                fixture_replay,
                direction="server_to_client",
                exchange_index=index,
                profile=fixture_variation_profile,
                peer_label=fixture_peer_label,
            )
        else:
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
                "requested_backend": backend,
                "client_requested_backend": hello.get("aiwire_backend", ""),
                "exchanges": index,
                "raw_request_bytes": raw_request_bytes,
                "raw_response_bytes": raw_response_bytes,
                "request_wire_bytes": request_wire_bytes,
                "response_wire_bytes": response_wire_bytes,
                "framed_request_wire_bytes": request_wire_bytes + index * U32.size,
                "framed_response_wire_bytes": response_wire_bytes + index * U32.size,
                "link_mbps": connection_link_mbps,
                "session_shard": session_shard,
                "session_shards": session_shards,
                "one_way_delay_ms": one_way_delay_ms,
                "jitter_ms": jitter_ms,
                "tail_pause_probability": tail_pause_probability,
                "tail_pause_ms": tail_pause_ms,
                "fixture_replay": fixture_requested,
                "fixture_variation_profile": fixture_variation_profile,
                "fixture_peer_label": fixture_peer_label,
                "fixture_corpus": fixture_replay.path if fixture_replay else "",
                "fixture_exchange_count": fixture_replay.exchange_count if fixture_replay else 0,
                "server_decompress_ms": server_decompress_ns / 1_000_000,
                "server_compress_ms": server_compress_ns / 1_000_000,
                "request_sha256": request_digest.hexdigest(),
                "response_sha256": response_digest.hexdigest(),
            }
        ),
    )


def _serve_server_connection(
    conn: socket.socket,
    args: argparse.Namespace,
    fixture_replay: FixtureReplayCorpus | None,
) -> None:
    with conn:
        _configure_low_latency(conn)
        server_once(
            conn,
            cache_dir=args.cache_dir,
            backend=args.backend,
            link_mbps=args.link_mbps,
            one_way_delay_ms=args.one_way_delay_ms,
            jitter_ms=args.jitter_ms,
            tail_pause_probability=args.tail_pause_probability,
            tail_pause_ms=args.tail_pause_ms,
            impairment_seed=args.impairment_seed,
            fixture_replay=fixture_replay,
        )


def _run_server_process_worker(
    server_fd: int,
    args: argparse.Namespace,
    fixture_replay: FixtureReplayCorpus | None,
    remaining_accepts: Any,
    accept_lock: Any,
) -> None:
    server = socket.socket(fileno=server_fd)
    try:
        while True:
            with accept_lock:
                if remaining_accepts.value <= 0:
                    return
                remaining_accepts.value -= 1
            conn, _addr = server.accept()
            _serve_server_connection(conn, args, fixture_replay)
    finally:
        server.close()


def run_server(args: argparse.Namespace) -> None:
    fixture_replay = (
        _load_fixture_replay_corpus(
            args.fixture_corpus,
            session_template_mode=args.fixture_session_templates,
        )
        if args.fixture_corpus
        else None
    )
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((args.host, args.port))
        process_workers = max(0, int(args.connection_processes))
        connection_workers = max(1, int(args.connection_workers))
        server.listen(max(8, connection_workers, process_workers))
        if args.ready_file:
            ready_file = Path(args.ready_file)
            ready_file.parent.mkdir(parents=True, exist_ok=True)
            ready_file.write_text(
                json.dumps({"host": args.host, "port": args.port}, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        if process_workers > 0:
            if "fork" not in mp.get_all_start_methods():
                raise RuntimeError("--connection-processes requires multiprocessing fork support")
            ctx = mp.get_context("fork")
            remaining_accepts = ctx.Value("i", int(args.runs))
            accept_lock = ctx.Lock()
            processes = [
                ctx.Process(
                    target=_run_server_process_worker,
                    args=(
                        server.fileno(),
                        args,
                        fixture_replay,
                        remaining_accepts,
                        accept_lock,
                    ),
                )
                for _ in range(process_workers)
            ]
            for process in processes:
                process.start()
            for process in processes:
                process.join()
            failures = [
                process.exitcode for process in processes if process.exitcode not in (0, None)
            ]
            if failures:
                raise RuntimeError(f"server process worker failed with exit codes {failures}")
            return

        if connection_workers == 1:
            for _ in range(args.runs):
                conn, _addr = server.accept()
                _serve_server_connection(conn, args, fixture_replay)
            return

        with ThreadPoolExecutor(max_workers=connection_workers) as executor:
            futures = []
            for _ in range(args.runs):
                conn, _addr = server.accept()
                futures.append(
                    executor.submit(_serve_server_connection, conn, args, fixture_replay)
                )
            for future in as_completed(futures):
                future.result()


def _client_stress_codec(
    codec: str,
    frames: list[bytes],
    args: argparse.Namespace,
    fixture_replay: FixtureReplayCorpus | None = None,
) -> dict[str, Any]:
    duration_mode = args.seconds > 0
    agent_count = max(1, args.agent_count)
    per_agent_pipeline_window = max(1, args.pipeline_window)
    aggregate_pipeline_window = agent_count * per_agent_pipeline_window
    session_shards = max(1, int(getattr(args, "session_shards", 1) or 1))
    session_shard = max(1, int(getattr(args, "session_shard", 1) or 1))
    fixture_variation_profile = _args_fixture_variation_profile(args)
    fixture_peer_label = _args_fixture_peer_label(args)
    session_templates: tuple[tuple[int, str], ...] = ()
    if codec in AIWIRE_NEGOTIATED_CODECS:
        session_templates = _client_session_templates(
            args,
            frames,
            fixture_replay=fixture_replay,
        )
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
        "session_shard": session_shard,
        "session_shards": session_shards,
        "fixture_replay": fixture_replay is not None,
        "aiwire_backend": args.backend,
    }
    if fixture_replay is not None:
        hello.update(
            {
                "fixture_corpus": fixture_replay.path,
                "fixture_schema": fixture_replay.schema,
                "fixture_exchange_count": fixture_replay.exchange_count,
                "fixture_session_template_mode": fixture_replay.session_template_mode,
                "fixture_request_sha256": fixture_replay.request_sha256,
                "fixture_response_sha256": fixture_replay.response_sha256,
                "fixture_variation_profile": fixture_variation_profile,
                "fixture_peer_label": fixture_peer_label,
            }
        )
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
        if fixture_replay is not None and not ack.get("fixture_replay"):
            raise RuntimeError(f"{codec} fixture replay was not accepted by server: {ack}")

        negotiated_codec = ack["negotiated_codec"]
        session = CodecSession(
            codec=negotiated_codec,
            level=args.aiwire_level,
            cache_dir=args.cache_dir,
            session_templates=(
                session_templates if negotiated_codec in AIWIRE_NEGOTIATED_CODECS else None
            ),
            requested_backend=args.backend,
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
            if fixture_replay is not None:
                request = _fixture_frame_for(
                    fixture_replay,
                    direction="client_to_server",
                    exchange_index=sent_exchanges,
                    profile=fixture_variation_profile,
                    peer_label=fixture_peer_label,
                )
            else:
                request = (
                    frames[sent_exchanges % len(frames)]
                    if duration_mode
                    else frames[sent_exchanges]
                )
            request_sha = hashlib.sha256(request).hexdigest()
            expected_response_sha256 = None
            if fixture_replay is not None:
                expected_response_sha256 = hashlib.sha256(
                    _fixture_frame_for(
                        fixture_replay,
                        direction="server_to_client",
                        exchange_index=sent_exchanges,
                        profile=fixture_variation_profile,
                        peer_label=fixture_peer_label,
                    )
                ).hexdigest()
            exchange_start = time.perf_counter_ns()

            raw_request_bytes += len(request)
            _update_digest(request_digest, request)

            start = time.perf_counter_ns()
            wire_request = session.encode(request)
            client_compress_ns += time.perf_counter_ns() - start
            request_wire_bytes += len(wire_request)
            out_writer.write(wire_request)
            outstanding.append(
                InFlightRequest(
                    sent_exchanges,
                    request_sha,
                    expected_response_sha256,
                    exchange_start,
                )
            )
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
            if expected.expected_response_sha256 is not None:
                if hashlib.sha256(response).hexdigest() != expected.expected_response_sha256:
                    raise RuntimeError(
                        f"{codec} fixture response verification failed "
                        f"at exchange {expected.index}"
                    )
            else:
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
        "coordinator": getattr(args, "coordinator", "threaded"),
        "backend": ack.get("backend"),
        "requested_backend": args.backend,
        "client_backend": session.backend,
        "server_backend": ack.get("backend"),
        "server_requested_backend": ack.get("requested_backend", ""),
        "client_requested_backend": ack.get("client_requested_backend", ""),
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
        "session_shard": session_shard,
        "session_shards": session_shards,
        "server_session_shard": ack.get("session_shard", 1),
        "server_session_shards": ack.get("session_shards", 1),
        "session_template_count": (
            len(session_templates) if codec in AIWIRE_NEGOTIATED_CODECS else 0
        ),
        "session_template_sha256": (
            aiwire_session_templates_sha256(session_templates)
            if codec in AIWIRE_NEGOTIATED_CODECS
            else ""
        ),
        "fixture_replay": fixture_replay is not None,
        "fixture_corpus": ack.get("fixture_corpus", ""),
        "fixture_schema": ack.get("fixture_schema", ""),
        "fixture_exchange_count": ack.get("fixture_exchange_count", 0),
        "fixture_session_template_mode": ack.get("fixture_session_template_mode", ""),
        "fixture_variation_profile": ack.get("fixture_variation_profile", "none"),
        "fixture_peer_label": ack.get("fixture_peer_label", ""),
        "fixture_request_sha256": ack.get("fixture_request_sha256", ""),
        "fixture_response_sha256": ack.get("fixture_response_sha256", ""),
        "response_verification": (
            "fixture_sha256" if fixture_replay is not None else "request_sha256"
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


async def _client_stress_codec_async(
    codec: str,
    frames: list[bytes],
    args: argparse.Namespace,
    fixture_replay: FixtureReplayCorpus | None = None,
) -> dict[str, Any]:
    duration_mode = args.seconds > 0
    agent_count = max(1, args.agent_count)
    per_agent_pipeline_window = max(1, args.pipeline_window)
    aggregate_pipeline_window = agent_count * per_agent_pipeline_window
    session_shards = max(1, int(getattr(args, "session_shards", 1) or 1))
    session_shard = max(1, int(getattr(args, "session_shard", 1) or 1))
    fixture_variation_profile = _args_fixture_variation_profile(args)
    fixture_peer_label = _args_fixture_peer_label(args)
    session_templates: tuple[tuple[int, str], ...] = ()
    if codec in AIWIRE_NEGOTIATED_CODECS:
        session_templates = _client_session_templates(
            args,
            frames,
            fixture_replay=fixture_replay,
        )
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
        "session_shard": session_shard,
        "session_shards": session_shards,
        "fixture_replay": fixture_replay is not None,
        "aiwire_backend": args.backend,
    }
    if fixture_replay is not None:
        hello.update(
            {
                "fixture_corpus": fixture_replay.path,
                "fixture_schema": fixture_replay.schema,
                "fixture_exchange_count": fixture_replay.exchange_count,
                "fixture_session_template_mode": fixture_replay.session_template_mode,
                "fixture_request_sha256": fixture_replay.request_sha256,
                "fixture_response_sha256": fixture_replay.response_sha256,
                "fixture_variation_profile": fixture_variation_profile,
                "fixture_peer_label": fixture_peer_label,
            }
        )
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
    reader, writer = await asyncio.wait_for(
        asyncio.open_connection(args.host, args.port),
        timeout=args.timeout,
    )
    try:
        _configure_async_low_latency(writer)
        await _async_write_frame(writer, _json_bytes(hello))
        ack = json.loads(await _async_read_frame(reader))
        handshake_ms = (time.perf_counter_ns() - connect_start) / 1_000_000
        if not ack.get("accepted"):
            raise RuntimeError(f"{codec} stress negotiation failed: {ack}")
        if fixture_replay is not None and not ack.get("fixture_replay"):
            raise RuntimeError(f"{codec} fixture replay was not accepted by server: {ack}")

        negotiated_codec = ack["negotiated_codec"]
        session = CodecSession(
            codec=negotiated_codec,
            level=args.aiwire_level,
            cache_dir=args.cache_dir,
            session_templates=(
                session_templates if negotiated_codec in AIWIRE_NEGOTIATED_CODECS else None
            ),
            requested_backend=args.backend,
        )
        out_writer = AsyncStreamFrameWriter(
            writer,
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
            if fixture_replay is not None:
                request = _fixture_frame_for(
                    fixture_replay,
                    direction="client_to_server",
                    exchange_index=sent_exchanges,
                    profile=fixture_variation_profile,
                    peer_label=fixture_peer_label,
                )
            else:
                request = (
                    frames[sent_exchanges % len(frames)]
                    if duration_mode
                    else frames[sent_exchanges]
                )
            request_sha = hashlib.sha256(request).hexdigest()
            expected_response_sha256 = None
            if fixture_replay is not None:
                expected_response_sha256 = hashlib.sha256(
                    _fixture_frame_for(
                        fixture_replay,
                        direction="server_to_client",
                        exchange_index=sent_exchanges,
                        profile=fixture_variation_profile,
                        peer_label=fixture_peer_label,
                    )
                ).hexdigest()
            exchange_start = time.perf_counter_ns()

            raw_request_bytes += len(request)
            _update_digest(request_digest, request)

            start = time.perf_counter_ns()
            wire_request = session.encode(request)
            client_compress_ns += time.perf_counter_ns() - start
            request_wire_bytes += len(wire_request)
            out_writer.write(wire_request)
            outstanding.append(
                InFlightRequest(
                    sent_exchanges,
                    request_sha,
                    expected_response_sha256,
                    exchange_start,
                )
            )
            sent_exchanges += 1

        async def receive_next() -> None:
            nonlocal client_decompress_ns, raw_response_bytes, response_wire_bytes
            nonlocal deadline_completed_exchanges
            wire_response = await _async_read_frame(reader)
            response_wire_bytes += len(wire_response)
            start = time.perf_counter_ns()
            response = session.decode(wire_response)
            client_decompress_ns += time.perf_counter_ns() - start
            completed_ns = time.perf_counter_ns()

            expected = outstanding.popleft()
            if expected.expected_response_sha256 is not None:
                if hashlib.sha256(response).hexdigest() != expected.expected_response_sha256:
                    raise RuntimeError(
                        f"{codec} fixture response verification failed "
                        f"at exchange {expected.index}"
                    )
            else:
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
                await receive_next()
            while can_send_more():
                send_next()

        if duration_mode:
            out_writer.write(b"")
        await out_writer.close()
        stress_ms = (time.perf_counter_ns() - stress_start) / 1_000_000
        server_summary = json.loads(await _async_read_frame(reader))
    finally:
        writer.close()
        await writer.wait_closed()

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
        "coordinator": "asyncio",
        "backend": ack.get("backend"),
        "requested_backend": args.backend,
        "client_backend": session.backend,
        "server_backend": ack.get("backend"),
        "server_requested_backend": ack.get("requested_backend", ""),
        "client_requested_backend": ack.get("client_requested_backend", ""),
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
        "session_shard": session_shard,
        "session_shards": session_shards,
        "server_session_shard": ack.get("session_shard", 1),
        "server_session_shards": ack.get("session_shards", 1),
        "session_template_count": (
            len(session_templates) if codec in AIWIRE_NEGOTIATED_CODECS else 0
        ),
        "session_template_sha256": (
            aiwire_session_templates_sha256(session_templates)
            if codec in AIWIRE_NEGOTIATED_CODECS
            else ""
        ),
        "fixture_replay": fixture_replay is not None,
        "fixture_corpus": ack.get("fixture_corpus", ""),
        "fixture_schema": ack.get("fixture_schema", ""),
        "fixture_exchange_count": ack.get("fixture_exchange_count", 0),
        "fixture_session_template_mode": ack.get("fixture_session_template_mode", ""),
        "fixture_variation_profile": ack.get("fixture_variation_profile", "none"),
        "fixture_peer_label": ack.get("fixture_peer_label", ""),
        "fixture_request_sha256": ack.get("fixture_request_sha256", ""),
        "fixture_response_sha256": ack.get("fixture_response_sha256", ""),
        "response_verification": (
            "fixture_sha256" if fixture_replay is not None else "request_sha256"
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


def _load_client_frames(
    args: argparse.Namespace,
) -> tuple[list[bytes], FixtureReplayCorpus | None]:
    fixture_replay = (
        _load_fixture_replay_corpus(
            args.fixture_corpus,
            session_template_mode=args.fixture_session_templates,
        )
        if args.fixture_corpus
        else None
    )
    if fixture_replay is not None:
        frames = (
            list(fixture_replay.request_frames)
            if args.seconds > 0
            else _repeat_frames(fixture_replay.request_frames, args.exchanges)
        )
    else:
        frames = build_ai_wire_messages(args.exchanges, args.seed)
    return frames, fixture_replay


def _safe_label(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in value)
    return cleaned.strip("-") or "target"


def _client_args_for_target(
    args: argparse.Namespace,
    target: RelayTarget,
    *,
    session_shard: int = 1,
) -> argparse.Namespace:
    child = argparse.Namespace(**vars(args))
    child.host = target.host
    child.port = target.port
    child.output = None
    session_shards = max(1, int(getattr(args, "session_shards", 1) or 1))
    child.session_shard = max(1, session_shard)
    child.session_shards = session_shards
    child.link_mbps = args.link_mbps / session_shards if args.link_mbps > 0 else 0.0
    shard_suffix = f"-shard-{child.session_shard}" if session_shards > 1 else ""
    child.cache_dir = f"{args.cache_dir}-{_safe_label(target.label + shard_suffix)}"
    child.fixture_peer_label = f"{target.label}{shard_suffix}"
    return child


def _parse_relay_target(value: str, default_port: int) -> RelayTarget:
    if "=" in value:
        label, endpoint = value.split("=", 1)
        label = label.strip()
    else:
        endpoint = value
        label = ""

    endpoint = endpoint.strip()
    port = default_port
    host = endpoint
    if endpoint.startswith("[") and "]" in endpoint:
        host_part, _, port_part = endpoint[1:].partition("]")
        host = host_part
        if port_part.startswith(":") and port_part[1:].isdigit():
            port = int(port_part[1:])
    elif ":" in endpoint:
        host_part, port_part = endpoint.rsplit(":", 1)
        if port_part.isdigit():
            host = host_part
            port = int(port_part)

    label = label or host
    if not label or not host:
        raise ValueError(f"invalid relay target: {value!r}")
    return RelayTarget(label=label, host=host, port=port)


def _collect_relay_targets(args: argparse.Namespace) -> list[RelayTarget]:
    values = list(args.target or [])
    if args.targets_file:
        for line in Path(args.targets_file).read_text().splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                values.append(stripped)
    if not values:
        raise RuntimeError("nary-client requires at least one --target")

    targets = [_parse_relay_target(value, args.port) for value in values]
    labels = [target.label for target in targets]
    if len(labels) != len(set(labels)):
        raise RuntimeError(f"target labels must be unique: {labels}")
    return targets


def _probe_aiwire_peer(
    target: RelayTarget,
    args: argparse.Namespace,
    frames: list[bytes],
    fixture_replay: FixtureReplayCorpus | None,
) -> dict[str, Any]:
    child = _client_args_for_target(args, target)
    fixture_variation_profile = _args_fixture_variation_profile(child)
    fixture_peer_label = _args_fixture_peer_label(child)
    session_templates = _client_session_templates(
        child,
        frames,
        fixture_replay=fixture_replay,
    )
    hello: dict[str, Any] = {
        "codec": "aiwire",
        "exchanges": 0,
        "duration_mode": False,
        "duration_seconds": 0,
        "handshake_probe": True,
        "client_link_mbps": child.link_mbps,
        "client_one_way_delay_ms": child.one_way_delay_ms,
        "client_jitter_ms": child.jitter_ms,
        "client_tail_pause_probability": child.tail_pause_probability,
        "client_tail_pause_ms": child.tail_pause_ms,
        "agent_count": max(1, child.agent_count),
        "per_agent_pipeline_window": max(1, child.pipeline_window),
        "aggregate_pipeline_window": max(1, child.agent_count) * max(1, child.pipeline_window),
        "fixture_replay": fixture_replay is not None,
        "aiwire_backend": child.backend,
        "aiwire_level": child.aiwire_level,
        "allow_aiwire_fallback": child.allow_aiwire_fallback,
        "aiwire_handshake": build_aiwire_handshake(
            level=child.aiwire_level,
            fallback_codecs=("zlib", "raw") if child.allow_aiwire_fallback else (),
            session_templates=session_templates,
            require_session_templates=child.force_session_templates,
        ).to_dict(),
    }
    if fixture_replay is not None:
        hello.update(
            {
                "fixture_corpus": fixture_replay.path,
                "fixture_schema": fixture_replay.schema,
                "fixture_exchange_count": fixture_replay.exchange_count,
                "fixture_session_template_mode": fixture_replay.session_template_mode,
                "fixture_request_sha256": fixture_replay.request_sha256,
                "fixture_response_sha256": fixture_replay.response_sha256,
                "fixture_variation_profile": fixture_variation_profile,
                "fixture_peer_label": fixture_peer_label,
            }
        )

    connect_start = time.perf_counter_ns()
    with socket.create_connection((target.host, target.port), timeout=child.timeout) as sock:
        _configure_low_latency(sock)
        _write_frame(sock, _json_bytes(hello))
        ack = json.loads(_read_frame(sock))
    handshake_ms = (time.perf_counter_ns() - connect_start) / 1_000_000
    if not ack.get("accepted"):
        raise RuntimeError(f"{target.label} AIWire handshake probe failed: {ack}")
    if fixture_replay is not None and not ack.get("fixture_replay"):
        raise RuntimeError(f"{target.label} fixture replay probe was not accepted: {ack}")

    aiwire_negotiation = ack.get("aiwire_negotiation")
    if not isinstance(aiwire_negotiation, dict) or not aiwire_negotiation.get("accepted"):
        raise RuntimeError(f"{target.label} did not return an accepted AIWire negotiation")
    peer_handshake = aiwire_negotiation.get("server")
    if not isinstance(peer_handshake, dict):
        raise RuntimeError(f"{target.label} did not return a server handshake")

    return {
        "target": target.label,
        "handshake_ms": handshake_ms,
        "backend": ack.get("backend"),
        "requested_backend": child.backend,
        "server_requested_backend": ack.get("requested_backend", ""),
        "client_requested_backend": ack.get("client_requested_backend", ""),
        "session_template_count": ack.get("session_template_count", 0),
        "session_template_sha256": ack.get("session_template_sha256", ""),
        "fixture_replay": ack.get("fixture_replay", False),
        "fixture_exchange_count": ack.get("fixture_exchange_count", 0),
        "fixture_variation_profile": ack.get("fixture_variation_profile", "none"),
        "fixture_peer_label": ack.get("fixture_peer_label", ""),
        "peer_handshake": peer_handshake,
        "aiwire_negotiation": aiwire_negotiation,
    }


async def _probe_aiwire_peer_async(
    target: RelayTarget,
    args: argparse.Namespace,
    frames: list[bytes],
    fixture_replay: FixtureReplayCorpus | None,
) -> dict[str, Any]:
    child = _client_args_for_target(args, target)
    fixture_variation_profile = _args_fixture_variation_profile(child)
    fixture_peer_label = _args_fixture_peer_label(child)
    session_templates = _client_session_templates(
        child,
        frames,
        fixture_replay=fixture_replay,
    )
    hello: dict[str, Any] = {
        "codec": "aiwire",
        "exchanges": 0,
        "duration_mode": False,
        "duration_seconds": 0,
        "handshake_probe": True,
        "client_link_mbps": child.link_mbps,
        "client_one_way_delay_ms": child.one_way_delay_ms,
        "client_jitter_ms": child.jitter_ms,
        "client_tail_pause_probability": child.tail_pause_probability,
        "client_tail_pause_ms": child.tail_pause_ms,
        "agent_count": max(1, child.agent_count),
        "per_agent_pipeline_window": max(1, child.pipeline_window),
        "aggregate_pipeline_window": max(1, child.agent_count) * max(1, child.pipeline_window),
        "fixture_replay": fixture_replay is not None,
        "aiwire_backend": child.backend,
        "aiwire_level": child.aiwire_level,
        "allow_aiwire_fallback": child.allow_aiwire_fallback,
        "aiwire_handshake": build_aiwire_handshake(
            level=child.aiwire_level,
            fallback_codecs=("zlib", "raw") if child.allow_aiwire_fallback else (),
            session_templates=session_templates,
            require_session_templates=child.force_session_templates,
        ).to_dict(),
    }
    if fixture_replay is not None:
        hello.update(
            {
                "fixture_corpus": fixture_replay.path,
                "fixture_schema": fixture_replay.schema,
                "fixture_exchange_count": fixture_replay.exchange_count,
                "fixture_session_template_mode": fixture_replay.session_template_mode,
                "fixture_request_sha256": fixture_replay.request_sha256,
                "fixture_response_sha256": fixture_replay.response_sha256,
                "fixture_variation_profile": fixture_variation_profile,
                "fixture_peer_label": fixture_peer_label,
            }
        )

    connect_start = time.perf_counter_ns()
    reader, writer = await asyncio.wait_for(
        asyncio.open_connection(target.host, target.port),
        timeout=child.timeout,
    )
    try:
        _configure_async_low_latency(writer)
        await _async_write_frame(writer, _json_bytes(hello))
        ack = json.loads(await _async_read_frame(reader))
    finally:
        writer.close()
        await writer.wait_closed()

    handshake_ms = (time.perf_counter_ns() - connect_start) / 1_000_000
    if not ack.get("accepted"):
        raise RuntimeError(f"{target.label} AIWire handshake probe failed: {ack}")
    if fixture_replay is not None and not ack.get("fixture_replay"):
        raise RuntimeError(f"{target.label} fixture replay probe was not accepted: {ack}")

    aiwire_negotiation = ack.get("aiwire_negotiation")
    if not isinstance(aiwire_negotiation, dict) or not aiwire_negotiation.get("accepted"):
        raise RuntimeError(f"{target.label} did not return an accepted AIWire negotiation")
    peer_handshake = aiwire_negotiation.get("server")
    if not isinstance(peer_handshake, dict):
        raise RuntimeError(f"{target.label} did not return a server handshake")

    return {
        "target": target.label,
        "handshake_ms": handshake_ms,
        "backend": ack.get("backend"),
        "requested_backend": child.backend,
        "server_requested_backend": ack.get("requested_backend", ""),
        "client_requested_backend": ack.get("client_requested_backend", ""),
        "session_template_count": ack.get("session_template_count", 0),
        "session_template_sha256": ack.get("session_template_sha256", ""),
        "fixture_replay": ack.get("fixture_replay", False),
        "fixture_exchange_count": ack.get("fixture_exchange_count", 0),
        "fixture_variation_profile": ack.get("fixture_variation_profile", "none"),
        "fixture_peer_label": ack.get("fixture_peer_label", ""),
        "peer_handshake": peer_handshake,
        "aiwire_negotiation": aiwire_negotiation,
    }


def _run_target_codec(
    target_index: int,
    target: RelayTarget,
    codec: str,
    args: argparse.Namespace,
    frames: list[bytes],
    fixture_replay: FixtureReplayCorpus | None,
    session_shard: int = 1,
) -> dict[str, Any]:
    child = _client_args_for_target(args, target, session_shard=session_shard)
    row = _client_stress_codec(codec, frames, child, fixture_replay)
    row["target"] = target.label
    row["target_index"] = target_index
    row["session_shard"] = session_shard
    return row


async def _run_target_codec_async(
    target_index: int,
    target: RelayTarget,
    codec: str,
    args: argparse.Namespace,
    frames: list[bytes],
    fixture_replay: FixtureReplayCorpus | None,
    session_shard: int = 1,
) -> dict[str, Any]:
    child = _client_args_for_target(args, target, session_shard=session_shard)
    row = await _client_stress_codec_async(codec, frames, child, fixture_replay)
    row["target"] = target.label
    row["target_index"] = target_index
    row["session_shard"] = session_shard
    return row


def _aggregate_nary_results(
    rows: list[dict[str, Any]],
    codec_order: list[str],
) -> list[dict[str, Any]]:
    by_codec = {codec: [row for row in rows if row["codec"] == codec] for codec in codec_order}
    raw_completed = sum(
        float(row["deadline_completed_exchanges"]) for row in by_codec.get("raw", [])
    )
    raw_eps = sum(float(row["deadline_exchanges_per_second"]) for row in by_codec.get("raw", []))
    aggregates: list[dict[str, Any]] = []
    for codec in codec_order:
        codec_rows = by_codec.get(codec, [])
        if not codec_rows:
            continue
        target_count = len({str(row["target"]) for row in codec_rows})
        session_count = len(codec_rows)
        session_shards_per_target = max(
            int(row.get("session_shards", 1) or 1) for row in codec_rows
        )
        completed = sum(float(row["deadline_completed_exchanges"]) for row in codec_rows)
        eps = sum(float(row["deadline_exchanges_per_second"]) for row in codec_rows)
        exchanges = sum(float(row["exchanges"]) for row in codec_rows)
        raw_bytes = sum(float(row["raw_bytes"]) for row in codec_rows)
        framed_wire_bytes = sum(float(row["framed_wire_bytes"]) for row in codec_rows)
        bandwidth_capacity_eps = sum(
            float(row["bandwidth_capacity_exchanges_per_second"]) for row in codec_rows
        )
        aggregates.append(
            {
                "codec": codec,
                "target_count": target_count,
                "session_count": session_count,
                "session_shards_per_target": session_shards_per_target,
                "deadline_completed_exchanges": completed,
                "deadline_exchanges_per_second": eps,
                "vs_raw_completed": completed / raw_completed if raw_completed else 0.0,
                "vs_raw_exchanges_per_second": eps / raw_eps if raw_eps else 0.0,
                "framed_bytes_per_exchange": (framed_wire_bytes / exchanges if exchanges else 0.0),
                "framed_wire_saved_percent": (
                    (1 - framed_wire_bytes / raw_bytes) * 100 if raw_bytes else 0.0
                ),
                "roundtrip_ms_p95_avg": (
                    sum(float(row["roundtrip_ms_p95"]) for row in codec_rows) / session_count
                ),
                "roundtrip_ms_p95_max": max(float(row["roundtrip_ms_p95"]) for row in codec_rows),
                "bandwidth_capacity_exchanges_per_second": bandwidth_capacity_eps,
                "bandwidth_utilization_percent": (
                    eps / bandwidth_capacity_eps * 100 if bandwidth_capacity_eps else 0.0
                ),
                "verified": all(bool(row["verified"]) for row in codec_rows),
            }
        )
    return aggregates


def _add_fixture_replay_output(
    output: dict[str, Any],
    args: argparse.Namespace,
    fixture_replay: FixtureReplayCorpus | None,
) -> None:
    if fixture_replay is not None:
        output["fixture_replay"] = {
            "fixture_corpus": fixture_replay.path,
            "fixture_schema": fixture_replay.schema,
            "fixture_session_count": fixture_replay.session_count,
            "fixture_exchange_count": fixture_replay.exchange_count,
            "fixture_session_template_mode": fixture_replay.session_template_mode,
            "fixture_session_template_count": len(fixture_replay.session_templates),
            "fixture_request_sha256": fixture_replay.request_sha256,
            "fixture_response_sha256": fixture_replay.response_sha256,
            "fixture_variation_profile": _args_fixture_variation_profile(args),
            "fixture_peer_label": _args_fixture_peer_label(args),
        }


def _emit_json_output(output: dict[str, Any], args: argparse.Namespace) -> None:
    print(json.dumps(output, indent=2, sort_keys=True))
    if args.output:
        Path(args.output).write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")


async def _run_client_async(args: argparse.Namespace) -> None:
    frames, fixture_replay = _load_client_frames(args)
    results = []
    for codec in args.codecs.split(","):
        codec = codec.strip()
        results.append(await _client_stress_codec_async(codec, frames, args, fixture_replay))

    output: dict[str, Any] = {
        "coordinator": "asyncio",
        "requested_backend": args.backend,
        "results": results,
    }
    _add_fixture_replay_output(output, args, fixture_replay)
    _emit_json_output(output, args)


def run_client(args: argparse.Namespace) -> None:
    if args.coordinator == "asyncio":
        asyncio.run(_run_client_async(args))
        return

    frames, fixture_replay = _load_client_frames(args)
    results = []
    for codec in args.codecs.split(","):
        codec = codec.strip()
        results.append(_client_stress_codec(codec, frames, args, fixture_replay))

    output: dict[str, Any] = {
        "coordinator": args.coordinator,
        "requested_backend": args.backend,
        "results": results,
    }
    _add_fixture_replay_output(output, args, fixture_replay)
    _emit_json_output(output, args)


async def _bounded_probe_aiwire_peer(
    semaphore: asyncio.Semaphore,
    target: RelayTarget,
    args: argparse.Namespace,
    frames: list[bytes],
    fixture_replay: FixtureReplayCorpus | None,
) -> tuple[str, dict[str, Any]]:
    async with semaphore:
        return target.label, await _probe_aiwire_peer_async(
            target,
            args,
            frames,
            fixture_replay,
        )


async def _bounded_run_target_codec(
    semaphore: asyncio.Semaphore,
    target_index: int,
    target: RelayTarget,
    codec: str,
    args: argparse.Namespace,
    frames: list[bytes],
    fixture_replay: FixtureReplayCorpus | None,
    session_shard: int,
) -> dict[str, Any]:
    async with semaphore:
        return await _run_target_codec_async(
            target_index,
            target,
            codec,
            args,
            frames,
            fixture_replay,
            session_shard,
        )


async def _run_nary_client_async(args: argparse.Namespace) -> None:
    frames, fixture_replay = _load_client_frames(args)
    targets = _collect_relay_targets(args)
    codec_order = [codec.strip() for codec in args.codecs.split(",") if codec.strip()]
    session_shards = max(1, int(getattr(args, "session_shards", 1) or 1))
    session_templates = _client_session_templates(
        args,
        frames,
        fixture_replay=fixture_replay,
    )

    probe_workers = min(max(1, args.target_parallelism), len(targets))
    probe_semaphore = asyncio.Semaphore(probe_workers)
    probe_tasks = [
        _bounded_probe_aiwire_peer(
            probe_semaphore,
            target,
            args,
            frames,
            fixture_replay,
        )
        for target in targets
    ]
    probe_results = await asyncio.gather(*probe_tasks)
    probes_by_label = dict(probe_results)

    peer_handshakes = [probes_by_label[target.label]["peer_handshake"] for target in targets]
    nary_negotiation = negotiate_aiwire_nary_handshake(
        peer_handshakes,
        level=args.aiwire_level,
        fallback_codecs=(),
        allow_fallback=False,
        session_templates=session_templates,
        require_session_templates=args.force_session_templates,
    )
    if not nary_negotiation.accepted:
        raise RuntimeError(f"n-ary AIWire negotiation failed: {nary_negotiation.reason}")

    results: list[dict[str, Any]] = []
    replay_workers = min(max(1, args.target_parallelism), len(targets) * session_shards)
    replay_semaphore = asyncio.Semaphore(replay_workers)
    for codec in codec_order:
        replay_tasks = [
            _bounded_run_target_codec(
                replay_semaphore,
                index,
                target,
                codec,
                args,
                frames,
                fixture_replay,
                shard,
            )
            for index, target in enumerate(targets, start=1)
            for shard in range(1, session_shards + 1)
        ]
        results.extend(await asyncio.gather(*replay_tasks))

    order = {codec: index for index, codec in enumerate(codec_order)}
    results.sort(
        key=lambda row: (
            order.get(str(row["codec"]), len(order)),
            row["target_index"],
            row.get("session_shard", 1),
        )
    )
    output: dict[str, Any] = {
        "mode": "nary_client",
        "coordinator": "asyncio",
        "participant_count": len(targets) + 1,
        "remote_peer_count": len(targets),
        "session_shards_per_target": session_shards,
        "total_replay_sessions": len(targets) * session_shards,
        "requested_backend": args.backend,
        "targets": [
            {"index": index, "label": target.label} for index, target in enumerate(targets, start=1)
        ],
        "nary_negotiation": nary_negotiation.to_dict(),
        "nary_peer_probes": [
            {
                key: value
                for key, value in probes_by_label[target.label].items()
                if key not in {"peer_handshake", "aiwire_negotiation"}
            }
            for target in targets
        ],
        "aggregate": _aggregate_nary_results(results, codec_order),
        "results": results,
    }
    _add_fixture_replay_output(output, args, fixture_replay)
    _emit_json_output(output, args)


def run_nary_client(args: argparse.Namespace) -> None:
    if args.coordinator == "asyncio":
        asyncio.run(_run_nary_client_async(args))
        return

    frames, fixture_replay = _load_client_frames(args)
    targets = _collect_relay_targets(args)
    codec_order = [codec.strip() for codec in args.codecs.split(",") if codec.strip()]
    session_shards = max(1, int(getattr(args, "session_shards", 1) or 1))
    session_templates = _client_session_templates(
        args,
        frames,
        fixture_replay=fixture_replay,
    )

    probe_workers = min(max(1, args.target_parallelism), len(targets))
    replay_workers = min(max(1, args.target_parallelism), len(targets) * session_shards)
    with ThreadPoolExecutor(max_workers=probe_workers) as executor:
        probe_futures = {
            executor.submit(_probe_aiwire_peer, target, args, frames, fixture_replay): target
            for target in targets
        }
        probes_by_label: dict[str, dict[str, Any]] = {}
        for future in as_completed(probe_futures):
            target = probe_futures[future]
            probes_by_label[target.label] = future.result()

    peer_handshakes = [probes_by_label[target.label]["peer_handshake"] for target in targets]
    nary_negotiation = negotiate_aiwire_nary_handshake(
        peer_handshakes,
        level=args.aiwire_level,
        fallback_codecs=(),
        allow_fallback=False,
        session_templates=session_templates,
        require_session_templates=args.force_session_templates,
    )
    if not nary_negotiation.accepted:
        raise RuntimeError(f"n-ary AIWire negotiation failed: {nary_negotiation.reason}")

    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=replay_workers) as executor:
        for codec in codec_order:
            futures = {
                executor.submit(
                    _run_target_codec,
                    index,
                    target,
                    codec,
                    args,
                    frames,
                    fixture_replay,
                    shard,
                ): target
                for index, target in enumerate(targets, start=1)
                for shard in range(1, session_shards + 1)
            }
            for future in as_completed(futures):
                results.append(future.result())

    order = {codec: index for index, codec in enumerate(codec_order)}
    results.sort(
        key=lambda row: (
            order.get(str(row["codec"]), len(order)),
            row["target_index"],
            row.get("session_shard", 1),
        )
    )
    output: dict[str, Any] = {
        "mode": "nary_client",
        "coordinator": args.coordinator,
        "participant_count": len(targets) + 1,
        "remote_peer_count": len(targets),
        "session_shards_per_target": session_shards,
        "total_replay_sessions": len(targets) * session_shards,
        "requested_backend": args.backend,
        "targets": [
            {"index": index, "label": target.label} for index, target in enumerate(targets, start=1)
        ],
        "nary_negotiation": nary_negotiation.to_dict(),
        "nary_peer_probes": [
            {
                key: value
                for key, value in probes_by_label[target.label].items()
                if key not in {"peer_handshake", "aiwire_negotiation"}
            }
            for target in targets
        ],
        "aggregate": _aggregate_nary_results(results, codec_order),
        "results": results,
    }
    _add_fixture_replay_output(output, args, fixture_replay)
    _emit_json_output(output, args)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)

    server = sub.add_parser("server")
    server.add_argument("--host", default="0.0.0.0")
    server.add_argument("--port", type=int, default=8910)
    server.add_argument(
        "--ready-file",
        help="Optional path written after the server socket is listening.",
    )
    server.add_argument("--runs", type=int, default=1)
    server.add_argument(
        "--connection-workers",
        type=int,
        default=1,
        help="maximum accepted connections to serve concurrently",
    )
    server.add_argument(
        "--connection-processes",
        type=int,
        default=0,
        help=(
            "forked worker processes sharing the listening socket; use for "
            "CPU-bound concurrent replay"
        ),
    )
    server.add_argument("--cache-dir", default="/tmp/aura-aiwire-stress-server-cache")
    server.add_argument(
        "--backend",
        choices=STRESS_BACKENDS,
        default="python",
        help=(
            "AIWire encode/decode backend for negotiated AIWire codecs. "
            "python is reproducible default; native requires libaura_aiwire; "
            "auto uses native when available."
        ),
    )
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
    server.add_argument(
        "--fixture-corpus",
        type=Path,
        help=(
            "replay and verify requests/responses from a public AIWire fixture corpus; "
            f"for example {DEFAULT_FIXTURE_CORPUS}"
        ),
    )
    server.add_argument(
        "--fixture-session-templates",
        choices=("none", "initial", "updated"),
        default="updated",
        help="fixture session-template set to advertise during AIWire handshakes",
    )
    server.set_defaults(func=run_server)

    client = sub.add_parser("client")
    client.add_argument("--host", required=True)
    client.add_argument("--port", type=int, default=8910)
    client.add_argument("--exchanges", type=int, default=5000)
    client.add_argument("--seconds", type=float, default=0.0)
    client.add_argument("--seed", type=int, default=1729)
    client.add_argument("--codecs", default="raw,zlib,aura,aiwire")
    client.add_argument(
        "--backend",
        choices=STRESS_BACKENDS,
        default="python",
        help=(
            "AIWire encode/decode backend for negotiated AIWire codecs. "
            "python is reproducible default; native requires libaura_aiwire; "
            "auto uses native when available."
        ),
    )
    client.add_argument(
        "--coordinator",
        choices=STRESS_COORDINATORS,
        default="threaded",
        help=(
            "client-side network coordinator. threaded preserves the historical "
            "path; asyncio uses one event loop to fan out frames without client "
            "thread-pool contention."
        ),
    )
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
    client.add_argument(
        "--fixture-corpus",
        type=Path,
        help=(
            "replay and verify requests/responses from a public AIWire fixture corpus; "
            f"for example {DEFAULT_FIXTURE_CORPUS}"
        ),
    )
    client.add_argument(
        "--fixture-session-templates",
        choices=("none", "initial", "updated"),
        default="updated",
        help="fixture session-template set to advertise during AIWire handshakes",
    )
    client.add_argument(
        "--fixture-variation-profile",
        choices=("none", "cluster"),
        default="none",
        help="deterministically vary fixture frames to mimic a working cluster",
    )
    client.add_argument(
        "--fixture-peer-label",
        default="client",
        help="peer label used by fixture variation profiles",
    )
    client.add_argument("--output")
    client.set_defaults(func=run_client)

    nary_client = sub.add_parser(
        "nary-client",
        help=(
            "probe multiple AIWire peers, negotiate one fail-closed n-ary "
            "session contract, then run concurrent fixture replay clients"
        ),
    )
    nary_client.add_argument(
        "--target",
        action="append",
        help="target as label=host[:port] or host[:port]; repeat for each peer",
    )
    nary_client.add_argument(
        "--targets-file",
        help="optional newline-delimited target list using the same format as --target",
    )
    nary_client.add_argument("--port", type=int, default=8910)
    nary_client.add_argument("--exchanges", type=int, default=5000)
    nary_client.add_argument("--seconds", type=float, default=0.0)
    nary_client.add_argument("--seed", type=int, default=1729)
    nary_client.add_argument("--codecs", default="raw,zlib,aiwire")
    nary_client.add_argument(
        "--backend",
        choices=STRESS_BACKENDS,
        default="python",
        help=(
            "AIWire encode/decode backend for negotiated AIWire codecs. "
            "python is reproducible default; native requires libaura_aiwire; "
            "auto uses native when available."
        ),
    )
    nary_client.add_argument(
        "--coordinator",
        choices=STRESS_COORDINATORS,
        default="threaded",
        help=(
            "coordinator implementation for peer probes and replay sessions. "
            "asyncio uses one event loop bounded by --target-parallelism."
        ),
    )
    nary_client.add_argument("--aiwire-level", type=int, default=AI_WIRE_DEFAULT_LEVEL)
    nary_client.add_argument("--allow-aiwire-fallback", action="store_true")
    nary_client.add_argument(
        "--session-template-file",
        help="JSON mapping/list of AIWire session templates to require in the handshake",
    )
    nary_client.add_argument(
        "--discover-session-templates",
        action="store_true",
        help="discover bounded AIWire session templates from the benchmark corpus",
    )
    nary_client.add_argument(
        "--force-session-templates",
        action="store_true",
        help="fail AIWire negotiation unless the session template set is non-empty and matched",
    )
    nary_client.add_argument("--session-template-limit", type=int, default=16)
    nary_client.add_argument("--session-template-sample-size", type=int, default=256)
    nary_client.add_argument("--session-template-min-frequency", type=int, default=2)
    nary_client.add_argument("--session-template-threshold", type=float, default=1.01)
    nary_client.add_argument("--cache-dir", default="/tmp/aura-aiwire-stress-nary-cache")
    nary_client.add_argument("--timeout", type=float, default=120.0)
    nary_client.add_argument(
        "--link-mbps", type=float, default=0.0, help="per-direction egress rate; 0 is unlimited"
    )
    nary_client.add_argument(
        "--one-way-delay-ms", type=float, default=0.0, help="egress propagation delay per frame"
    )
    nary_client.add_argument(
        "--jitter-ms", type=float, default=0.0, help="uniform +/- egress jitter per frame"
    )
    nary_client.add_argument(
        "--tail-pause-probability",
        type=float,
        default=0.0,
        help="probability that an egress frame receives an extra queue/retransmit-style delay",
    )
    nary_client.add_argument(
        "--tail-pause-ms",
        type=float,
        default=0.0,
        help="maximum extra delay for tail-pause events",
    )
    nary_client.add_argument("--impairment-seed", type=int, default=1729)
    nary_client.add_argument(
        "--pipeline-window",
        type=int,
        default=1,
        help="maximum in-flight request frames per logical agent",
    )
    nary_client.add_argument(
        "--agent-count",
        type=int,
        default=1,
        help="logical agents sharing the session; aggregate window is agent-count * pipeline-window",
    )
    nary_client.add_argument(
        "--target-parallelism",
        type=int,
        default=64,
        help="maximum target peers or replay sessions to benchmark at once",
    )
    nary_client.add_argument(
        "--session-shards",
        type=int,
        default=1,
        help=(
            "independent replay sessions per target; each shard receives an "
            "equal share of the modeled per-target link"
        ),
    )
    nary_client.add_argument(
        "--fixture-corpus",
        type=Path,
        help=(
            "replay and verify requests/responses from a public AIWire fixture corpus; "
            f"for example {DEFAULT_FIXTURE_CORPUS}"
        ),
    )
    nary_client.add_argument(
        "--fixture-session-templates",
        choices=("none", "initial", "updated"),
        default="updated",
        help="fixture session-template set to advertise during AIWire handshakes",
    )
    nary_client.add_argument(
        "--fixture-variation-profile",
        choices=("none", "cluster"),
        default="none",
        help="deterministically vary fixture frames per target to mimic a working cluster",
    )
    nary_client.add_argument("--output")
    nary_client.set_defaults(func=run_nary_client)

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
