"""Explicit TCP sidecar proxy for AIWire-tunneled agent frames.

The proxy is intentionally opt-in.  Client and upstream applications keep
speaking their normal length-prefixed bytes, while the inter-machine hop carries
AIWire frames plus inspectable control frames.
"""

from __future__ import annotations

import json
import random
import socket
import struct
import threading
import time
import zlib
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Mapping

from .ai_wire import (
    AI_WIRE_DEFAULT_LEVEL,
    AIWireSessionDecoder,
    AIWireSessionEncoder,
    build_aiwire_handshake,
    negotiate_aiwire_handshake,
)
from .aiwire_replay_log import dumps_replay_log

AIWIRE_PROXY_SCHEMA = "aura.aiwire.proxy.tcp.v1"
AIWIRE_PROXY_CONTROL_LANE = "control"
AIWIRE_PROXY_SEMANTIC_LANE = "semantic"
AIWIRE_PROXY_CONTROL_TAG = 0x01
AIWIRE_PROXY_SEMANTIC_TAG = 0x02
DEFAULT_MAX_FRAME_BYTES = 64 * 1024 * 1024

_U32 = struct.Struct("!I")
_LANE_TO_TAG = {
    AIWIRE_PROXY_CONTROL_LANE: AIWIRE_PROXY_CONTROL_TAG,
    AIWIRE_PROXY_SEMANTIC_LANE: AIWIRE_PROXY_SEMANTIC_TAG,
}
_TAG_TO_LANE = {tag: lane for lane, tag in _LANE_TO_TAG.items()}

BackendName = Literal["python", "native", "auto"]
TunnelCodec = Literal["raw", "zlib", "aiwire"]
ProxyMode = Literal["ingress", "egress"]
EgressUpstreamResponder = Callable[[bytes, int], bytes]
TUNNEL_CODECS: tuple[TunnelCodec, ...] = ("raw", "zlib", "aiwire")


class AIWireProxyError(RuntimeError):
    """Base error for explicit AIWire proxy failures."""


class AIWireProxyProtocolError(AIWireProxyError):
    """Raised when a peer sends malformed proxy framing."""


class AIWireProxyHandshakeError(AIWireProxyError):
    """Raised when the proxy control handshake fails closed."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _backend_flag(backend: BackendName) -> bool | None:
    if backend == "python":
        return False
    if backend == "native":
        return True
    if backend == "auto":
        return None
    raise ValueError(f"unsupported AIWire backend: {backend}")


def _validate_tunnel_codec(tunnel_codec: str) -> TunnelCodec:
    if tunnel_codec not in TUNNEL_CODECS:
        raise ValueError(
            "unsupported tunnel codec: "
            f"{tunnel_codec!r}; expected one of {', '.join(TUNNEL_CODECS)}"
        )
    return tunnel_codec  # type: ignore[return-value]


def _zlib_level(level: int) -> int:
    if level == -1:
        return level
    return min(max(level, 0), 9)


def _canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


@dataclass(frozen=True)
class TunnelImpairmentConfig:
    """Shared impairment model for the inter-sidecar AIWire tunnel."""

    bandwidth_mbps: float = 0.0
    one_way_delay_ms: float = 0.0
    jitter_ms: float = 0.0
    tail_pause_probability: float = 0.0
    tail_pause_ms: float = 0.0
    seed: int = 1729

    @property
    def enabled(self) -> bool:
        return any(
            (
                self.bandwidth_mbps > 0,
                self.one_way_delay_ms > 0,
                self.jitter_ms > 0,
                self.tail_pause_probability > 0 and self.tail_pause_ms > 0,
            )
        )

    def validate(self) -> None:
        if self.bandwidth_mbps < 0:
            raise ValueError("tunnel bandwidth must be non-negative")
        if self.one_way_delay_ms < 0:
            raise ValueError("tunnel one-way delay must be non-negative")
        if self.jitter_ms < 0:
            raise ValueError("tunnel jitter must be non-negative")
        if not 0 <= self.tail_pause_probability <= 1:
            raise ValueError("tunnel tail-pause probability must be between 0 and 1")
        if self.tail_pause_ms < 0:
            raise ValueError("tunnel tail-pause duration must be non-negative")

    def to_dict(self) -> dict[str, float | int]:
        return {
            "bandwidth_mbps": self.bandwidth_mbps,
            "one_way_delay_ms": self.one_way_delay_ms,
            "jitter_ms": self.jitter_ms,
            "tail_pause_probability": self.tail_pause_probability,
            "tail_pause_ms": self.tail_pause_ms,
            "seed": self.seed,
        }


class TunnelImpairment:
    """Apply aggregate serialization, propagation, jitter, and tail delay."""

    def __init__(self, config: TunnelImpairmentConfig) -> None:
        config.validate()
        self.config = config
        self._lock = threading.Lock()
        self._rng = random.Random(config.seed)
        self._next_serialized_ns = time.perf_counter_ns()

    def wait_before_write(self, framed_bytes: int) -> int:
        if not self.config.enabled:
            return 0
        with self._lock:
            now_ns = time.perf_counter_ns()
            serialized_start_ns = max(now_ns, self._next_serialized_ns)
            serialization_ns = 0
            if self.config.bandwidth_mbps > 0:
                serialization_seconds = (
                    framed_bytes * 8.0 / (self.config.bandwidth_mbps * 1_000_000.0)
                )
                serialization_ns = int(serialization_seconds * 1_000_000_000)
            serialized_end_ns = serialized_start_ns + serialization_ns
            self._next_serialized_ns = serialized_end_ns

            delay_ms = self.config.one_way_delay_ms
            if self.config.jitter_ms > 0:
                delay_ms += self._rng.uniform(-self.config.jitter_ms, self.config.jitter_ms)
            if (
                self.config.tail_pause_probability > 0
                and self.config.tail_pause_ms > 0
                and self._rng.random() < self.config.tail_pause_probability
            ):
                delay_ms += self._rng.uniform(0.0, self.config.tail_pause_ms)
            due_ns = serialized_end_ns + int(max(0.0, delay_ms) * 1_000_000)

        wait_ns = due_ns - time.perf_counter_ns()
        if wait_ns > 0:
            sleep_started_ns = time.perf_counter_ns()
            time.sleep(wait_ns / 1_000_000_000)
            return time.perf_counter_ns() - sleep_started_ns
        return 0


def read_exact(sock: socket.socket, size: int) -> bytes:
    """Read exactly ``size`` bytes from a socket or raise ``EOFError``."""

    data = bytearray()
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            raise EOFError("socket closed while reading frame")
        data.extend(chunk)
    return bytes(data)


def read_length_prefixed(
    sock: socket.socket,
    *,
    max_frame_bytes: int = DEFAULT_MAX_FRAME_BYTES,
) -> bytes:
    """Read one uint32 length-prefixed payload."""

    size = _U32.unpack(read_exact(sock, _U32.size))[0]
    if size > max_frame_bytes:
        raise AIWireProxyProtocolError(
            f"frame size {size} exceeds max_frame_bytes={max_frame_bytes}"
        )
    return read_exact(sock, size)


def write_length_prefixed(sock: socket.socket, payload: bytes) -> int:
    """Write one uint32 length-prefixed payload and return framed bytes sent."""

    sock.sendall(_U32.pack(len(payload)))
    sock.sendall(payload)
    return _U32.size + len(payload)


def encode_tunnel_frame(lane: str, payload: bytes) -> bytes:
    """Encode one tagged AIWire proxy tunnel frame."""

    try:
        tag = _LANE_TO_TAG[lane]
    except KeyError as exc:
        raise AIWireProxyProtocolError(f"unsupported proxy lane: {lane}") from exc
    return bytes((tag,)) + payload


def decode_tunnel_frame(frame: bytes) -> tuple[str, bytes]:
    """Decode one tagged AIWire proxy tunnel frame."""

    if not frame:
        raise AIWireProxyProtocolError("empty proxy tunnel frame")
    try:
        lane = _TAG_TO_LANE[frame[0]]
    except KeyError as exc:
        raise AIWireProxyProtocolError(f"unsupported proxy lane tag: 0x{frame[0]:02x}") from exc
    return lane, frame[1:]


def write_tunnel_frame(
    sock: socket.socket,
    lane: str,
    payload: bytes,
    *,
    impairment: TunnelImpairment | None = None,
) -> int:
    """Write a tagged proxy tunnel frame and return framed bytes sent."""

    framed_bytes, _impairment_wait_ns = write_tunnel_frame_with_stats(
        sock,
        lane,
        payload,
        impairment=impairment,
    )
    return framed_bytes


def write_tunnel_frame_with_stats(
    sock: socket.socket,
    lane: str,
    payload: bytes,
    *,
    impairment: TunnelImpairment | None = None,
) -> tuple[int, int]:
    """Write a tagged proxy tunnel frame and return bytes plus impairment wait."""

    frame = encode_tunnel_frame(lane, payload)
    framed_bytes = _U32.size + len(frame)
    impairment_wait_ns = 0
    if impairment is not None:
        impairment_wait_ns = impairment.wait_before_write(framed_bytes)
    return write_length_prefixed(sock, frame), impairment_wait_ns


def read_tunnel_frame(
    sock: socket.socket,
    *,
    max_frame_bytes: int = DEFAULT_MAX_FRAME_BYTES,
) -> tuple[str, bytes]:
    """Read a tagged proxy tunnel frame."""

    lane, payload, _framed_bytes = read_tunnel_frame_with_size(
        sock,
        max_frame_bytes=max_frame_bytes,
    )
    return lane, payload


def read_tunnel_frame_with_size(
    sock: socket.socket,
    *,
    max_frame_bytes: int = DEFAULT_MAX_FRAME_BYTES,
) -> tuple[str, bytes, int]:
    """Read a tagged proxy tunnel frame and return its outer framed size."""

    frame = read_length_prefixed(sock, max_frame_bytes=max_frame_bytes)
    lane, payload = decode_tunnel_frame(frame)
    return lane, payload, _U32.size + len(frame)


def _write_control_frame(
    sock: socket.socket,
    payload: Mapping[str, Any],
    *,
    impairment: TunnelImpairment | None = None,
) -> int:
    return write_tunnel_frame(
        sock,
        AIWIRE_PROXY_CONTROL_LANE,
        _canonical_json_bytes(payload),
        impairment=impairment,
    )


def _read_control_frame(
    sock: socket.socket,
    *,
    max_frame_bytes: int,
) -> dict[str, Any]:
    decoded, _framed_bytes = _read_control_frame_with_size(
        sock,
        max_frame_bytes=max_frame_bytes,
    )
    return decoded


def _read_control_frame_with_size(
    sock: socket.socket,
    *,
    max_frame_bytes: int,
) -> tuple[dict[str, Any], int]:
    lane, payload, framed_bytes = read_tunnel_frame_with_size(
        sock,
        max_frame_bytes=max_frame_bytes,
    )
    if lane != AIWIRE_PROXY_CONTROL_LANE:
        raise AIWireProxyProtocolError("expected proxy control frame")
    try:
        decoded = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AIWireProxyProtocolError("malformed proxy control JSON") from exc
    if not isinstance(decoded, dict):
        raise AIWireProxyProtocolError("proxy control payload must be a JSON object")
    if decoded.get("schema") != AIWIRE_PROXY_SCHEMA:
        raise AIWireProxyProtocolError("unsupported AIWire proxy schema")
    return decoded, framed_bytes


def _set_socket_options(sock: socket.socket) -> None:
    try:
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    except OSError:
        pass


@dataclass
class AIWireProxyMetrics:
    """Metrics for one explicit AIWire sidecar proxy process."""

    mode: ProxyMode
    listen_host: str
    listen_port: int
    requested_backend: BackendName = "auto"
    tunnel_codec: TunnelCodec = "aiwire"
    level: int = AI_WIRE_DEFAULT_LEVEL
    max_frame_bytes: int = DEFAULT_MAX_FRAME_BYTES
    target_host: str = ""
    target_port: int = 0
    started_at_utc: str = field(default_factory=_utc_now)
    ended_at_utc: str | None = None
    accepted_connections: int = 0
    handshakes_accepted: int = 0
    handshakes_rejected: int = 0
    exchanges: int = 0
    raw_request_payload_bytes: int = 0
    raw_response_payload_bytes: int = 0
    raw_framed_bytes: int = 0
    tunnel_request_framed_bytes: int = 0
    tunnel_response_framed_bytes: int = 0
    tunnel_control_framed_bytes: int = 0
    encoder_backend: str = ""
    decoder_backend: str = ""
    negotiation_codec: str = ""
    negotiation_version: int | None = None
    negotiation_reason: str | None = None
    tunnel_impairment: dict[str, float | int] = field(default_factory=dict)
    tunnel_impairment_wait_ns: int = 0
    stage_time_ns: dict[str, int] = field(default_factory=dict)
    stage_call_count: dict[str, int] = field(default_factory=dict)
    last_error: str | None = None

    @property
    def tunnel_semantic_framed_bytes(self) -> int:
        return self.tunnel_request_framed_bytes + self.tunnel_response_framed_bytes

    @property
    def tunnel_total_framed_bytes(self) -> int:
        return self.tunnel_semantic_framed_bytes + self.tunnel_control_framed_bytes

    @property
    def bandwidth_capacity_gain(self) -> float:
        if not self.tunnel_semantic_framed_bytes:
            return 0.0
        return self.raw_framed_bytes / self.tunnel_semantic_framed_bytes

    @property
    def tunnel_saved_percent(self) -> float:
        if not self.raw_framed_bytes:
            return 0.0
        return 100.0 * (1.0 - (self.tunnel_semantic_framed_bytes / self.raw_framed_bytes))

    @property
    def tunnel_impairment_wait_seconds(self) -> float:
        return self.tunnel_impairment_wait_ns / 1_000_000_000.0

    @property
    def stage_time_seconds(self) -> dict[str, float]:
        return {
            stage: elapsed_ns / 1_000_000_000.0
            for stage, elapsed_ns in sorted(self.stage_time_ns.items())
        }

    @property
    def stage_mean_ms(self) -> dict[str, float]:
        return {
            stage: (elapsed_ns / count / 1_000_000.0) if count else 0.0
            for stage, elapsed_ns in sorted(self.stage_time_ns.items())
            for count in (self.stage_call_count.get(stage, 0),)
        }

    def record_stage(self, stage: str, elapsed_ns: int) -> None:
        self.stage_time_ns[stage] = self.stage_time_ns.get(stage, 0) + max(0, elapsed_ns)
        self.stage_call_count[stage] = self.stage_call_count.get(stage, 0) + 1

    def add_tunnel_impairment_wait(self, elapsed_ns: int) -> None:
        self.tunnel_impairment_wait_ns += max(0, elapsed_ns)

    def finish(self) -> None:
        self.ended_at_utc = _utc_now()

    def to_result_row(self) -> dict[str, Any]:
        backend = self.encoder_backend or self.decoder_backend or self.requested_backend
        return {
            "target_label": f"{self.target_host}:{self.target_port}",
            "codec": self.tunnel_codec,
            "backend": backend,
            "client_requested_backend": self.requested_backend,
            "server_requested_backend": self.requested_backend,
            "verified": self.last_error is None,
            "exchanges": self.exchanges,
            "deadline_completed_exchanges": self.exchanges,
            "framed_wire_bytes": self.tunnel_semantic_framed_bytes,
            "framed_bytes_per_exchange": (
                self.tunnel_semantic_framed_bytes / self.exchanges if self.exchanges else 0.0
            ),
            "framed_wire_saved_percent": self.tunnel_saved_percent,
            "raw_framed_bytes": self.raw_framed_bytes,
            "tunnel_control_framed_bytes": self.tunnel_control_framed_bytes,
            "bandwidth_capacity_gain": self.bandwidth_capacity_gain,
            "tunnel_impairment_wait_seconds": self.tunnel_impairment_wait_seconds,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": AIWIRE_PROXY_SCHEMA,
            "mode": self.mode,
            "listen_host": self.listen_host,
            "listen_port": self.listen_port,
            "target_host": self.target_host,
            "target_port": self.target_port,
            "requested_backend": self.requested_backend,
            "tunnel_codec": self.tunnel_codec,
            "level": self.level,
            "max_frame_bytes": self.max_frame_bytes,
            "started_at_utc": self.started_at_utc,
            "ended_at_utc": self.ended_at_utc,
            "accepted_connections": self.accepted_connections,
            "handshakes_accepted": self.handshakes_accepted,
            "handshakes_rejected": self.handshakes_rejected,
            "exchanges": self.exchanges,
            "raw_request_payload_bytes": self.raw_request_payload_bytes,
            "raw_response_payload_bytes": self.raw_response_payload_bytes,
            "raw_framed_bytes": self.raw_framed_bytes,
            "tunnel_request_framed_bytes": self.tunnel_request_framed_bytes,
            "tunnel_response_framed_bytes": self.tunnel_response_framed_bytes,
            "tunnel_semantic_framed_bytes": self.tunnel_semantic_framed_bytes,
            "tunnel_control_framed_bytes": self.tunnel_control_framed_bytes,
            "tunnel_total_framed_bytes": self.tunnel_total_framed_bytes,
            "tunnel_saved_percent": self.tunnel_saved_percent,
            "bandwidth_capacity_gain": self.bandwidth_capacity_gain,
            "encoder_backend": self.encoder_backend,
            "decoder_backend": self.decoder_backend,
            "negotiation_codec": self.negotiation_codec,
            "negotiation_version": self.negotiation_version,
            "negotiation_reason": self.negotiation_reason,
            "tunnel_impairment": self.tunnel_impairment,
            "tunnel_impairment_wait_ns": self.tunnel_impairment_wait_ns,
            "tunnel_impairment_wait_seconds": self.tunnel_impairment_wait_seconds,
            "stage_time_ns": dict(sorted(self.stage_time_ns.items())),
            "stage_call_count": dict(sorted(self.stage_call_count.items())),
            "stage_time_seconds": self.stage_time_seconds,
            "stage_mean_ms": self.stage_mean_ms,
            "last_error": self.last_error,
        }


def _write_metrics_outputs(
    metrics: AIWireProxyMetrics,
    *,
    metrics_output: str | Path | None,
    replay_log_output: str | Path | None,
) -> None:
    if metrics_output:
        Path(metrics_output).write_text(
            json.dumps(metrics.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if replay_log_output:
        artifact = {
            "suite": "aura-aiwire-proxy",
            "mode": metrics.mode,
            "requested_backend": metrics.requested_backend,
            "results": [metrics.to_result_row()],
        }
        Path(replay_log_output).write_text(
            dumps_replay_log(artifact, source=f"aura-proxy:{metrics.mode}"),
            encoding="utf-8",
        )


def _connection_metrics_from(metrics: AIWireProxyMetrics) -> AIWireProxyMetrics:
    return AIWireProxyMetrics(
        mode=metrics.mode,
        listen_host=metrics.listen_host,
        listen_port=metrics.listen_port,
        requested_backend=metrics.requested_backend,
        tunnel_codec=metrics.tunnel_codec,
        level=metrics.level,
        max_frame_bytes=metrics.max_frame_bytes,
        target_host=metrics.target_host,
        target_port=metrics.target_port,
        tunnel_impairment=dict(metrics.tunnel_impairment),
    )


def _merge_connection_metrics(
    metrics: AIWireProxyMetrics,
    connection_metrics: AIWireProxyMetrics,
) -> None:
    metrics.handshakes_accepted += connection_metrics.handshakes_accepted
    metrics.handshakes_rejected += connection_metrics.handshakes_rejected
    metrics.exchanges += connection_metrics.exchanges
    metrics.raw_request_payload_bytes += connection_metrics.raw_request_payload_bytes
    metrics.raw_response_payload_bytes += connection_metrics.raw_response_payload_bytes
    metrics.raw_framed_bytes += connection_metrics.raw_framed_bytes
    metrics.tunnel_request_framed_bytes += connection_metrics.tunnel_request_framed_bytes
    metrics.tunnel_response_framed_bytes += connection_metrics.tunnel_response_framed_bytes
    metrics.tunnel_control_framed_bytes += connection_metrics.tunnel_control_framed_bytes
    metrics.tunnel_impairment_wait_ns += connection_metrics.tunnel_impairment_wait_ns
    for stage, elapsed_ns in connection_metrics.stage_time_ns.items():
        metrics.stage_time_ns[stage] = metrics.stage_time_ns.get(stage, 0) + elapsed_ns
    for stage, call_count in connection_metrics.stage_call_count.items():
        metrics.stage_call_count[stage] = metrics.stage_call_count.get(stage, 0) + call_count
    if connection_metrics.encoder_backend:
        metrics.encoder_backend = connection_metrics.encoder_backend
    if connection_metrics.decoder_backend:
        metrics.decoder_backend = connection_metrics.decoder_backend
    if connection_metrics.negotiation_codec:
        metrics.negotiation_codec = connection_metrics.negotiation_codec
    if connection_metrics.negotiation_version is not None:
        metrics.negotiation_version = connection_metrics.negotiation_version
    if connection_metrics.negotiation_reason is not None:
        metrics.negotiation_reason = connection_metrics.negotiation_reason
    if connection_metrics.last_error:
        metrics.last_error = connection_metrics.last_error


def _proxy_client_hello(
    *,
    level: int,
    backend: BackendName,
    tunnel_codec: TunnelCodec,
) -> dict[str, Any]:
    hello: dict[str, Any] = {
        "schema": AIWIRE_PROXY_SCHEMA,
        "role": "ingress",
        "codec": tunnel_codec,
        "requested_backend": backend,
    }
    if tunnel_codec == "aiwire":
        handshake = build_aiwire_handshake(
            level=level,
            use_native=_backend_flag(backend),
            fallback_codecs=(),
        )
        hello["aiwire_handshake"] = handshake.to_dict()
    return hello


def _write_proxy_client_hello(
    sock: socket.socket,
    *,
    level: int,
    backend: BackendName,
    tunnel_codec: TunnelCodec,
    impairment: TunnelImpairment | None = None,
) -> int:
    return _write_control_frame(
        sock,
        _proxy_client_hello(level=level, backend=backend, tunnel_codec=tunnel_codec),
        impairment=impairment,
    )


def _read_proxy_server_ack(
    sock: socket.socket,
    *,
    max_frame_bytes: int,
    tunnel_codec: TunnelCodec,
) -> tuple[dict[str, Any], int]:
    ack, framed_bytes = _read_control_frame_with_size(sock, max_frame_bytes=max_frame_bytes)
    if ack.get("role") != "egress":
        raise AIWireProxyHandshakeError("proxy handshake ack came from unexpected role")
    if not ack.get("accepted"):
        reason = ack.get("reason") or "rejected"
        raise AIWireProxyHandshakeError(f"AIWire proxy handshake rejected: {reason}")
    if ack.get("codec") != tunnel_codec:
        raise AIWireProxyHandshakeError(
            f"proxy codec mismatch: expected {tunnel_codec}, got {ack.get('codec')!r}"
        )
    return ack, framed_bytes


def _accept_proxy_handshake(
    sock: socket.socket,
    *,
    level: int,
    backend: BackendName,
    tunnel_codec: TunnelCodec,
    max_frame_bytes: int,
    impairment: TunnelImpairment | None = None,
) -> tuple[int, dict[str, Any]]:
    control_bytes = 0
    hello, hello_bytes = _read_control_frame_with_size(sock, max_frame_bytes=max_frame_bytes)
    control_bytes += hello_bytes
    if hello.get("role") != "ingress":
        raise AIWireProxyHandshakeError("proxy handshake hello came from unexpected role")
    if hello.get("codec") != tunnel_codec:
        reason = f"codec mismatch: expected {tunnel_codec}, got {hello.get('codec')!r}"
        control_bytes += _write_control_frame(
            sock,
            {
                "schema": AIWIRE_PROXY_SCHEMA,
                "role": "egress",
                "accepted": False,
                "codec": tunnel_codec,
                "version": 1,
                "reason": reason,
                "requested_backend": backend,
            },
            impairment=impairment,
        )
        raise AIWireProxyHandshakeError(reason)
    if tunnel_codec != "aiwire":
        ack = {
            "schema": AIWIRE_PROXY_SCHEMA,
            "role": "egress",
            "accepted": True,
            "codec": tunnel_codec,
            "version": 1,
            "reason": None,
            "requested_backend": backend,
            "negotiation": {
                "accepted": True,
                "codec": tunnel_codec,
                "version": 1,
                "reason": None,
            },
        }
        control_bytes += _write_control_frame(sock, ack, impairment=impairment)
        return control_bytes, ack
    peer_handshake = hello.get("aiwire_handshake")
    if not isinstance(peer_handshake, Mapping):
        raise AIWireProxyHandshakeError("proxy hello is missing AIWire handshake")

    negotiation = negotiate_aiwire_handshake(
        dict(peer_handshake),
        level=level,
        use_native=_backend_flag(backend),
        fallback_codecs=(),
        allow_fallback=False,
    )
    ack = {
        "schema": AIWIRE_PROXY_SCHEMA,
        "role": "egress",
        "accepted": negotiation.accepted,
        "codec": negotiation.codec,
        "version": negotiation.version,
        "reason": negotiation.reason,
        "requested_backend": backend,
        "negotiation": negotiation.to_dict(),
    }
    control_bytes += _write_control_frame(sock, ack, impairment=impairment)
    if not negotiation.accepted:
        reason = negotiation.reason or "rejected"
        raise AIWireProxyHandshakeError(f"AIWire proxy handshake rejected: {reason}")
    return control_bytes, ack


def _encode_semantic_payload(
    tunnel_codec: TunnelCodec,
    payload: bytes,
    *,
    encoder: AIWireSessionEncoder | None,
    level: int,
) -> bytes:
    if tunnel_codec == "raw":
        return payload
    if tunnel_codec == "zlib":
        return zlib.compress(payload, _zlib_level(level))
    if encoder is None:
        raise AIWireProxyProtocolError("AIWire encoder is not initialized")
    return encoder.compress_frame(payload)


def _decode_semantic_payload(
    tunnel_codec: TunnelCodec,
    payload: bytes,
    *,
    decoder: AIWireSessionDecoder | None,
) -> bytes:
    if tunnel_codec == "raw":
        return payload
    if tunnel_codec == "zlib":
        return zlib.decompress(payload)
    if decoder is None:
        raise AIWireProxyProtocolError("AIWire decoder is not initialized")
    return decoder.decompress_frame(payload)


def _handle_ingress_connection(
    client: socket.socket,
    *,
    egress_host: str,
    egress_port: int,
    level: int,
    backend: BackendName,
    tunnel_codec: TunnelCodec,
    max_frame_bytes: int,
    connect_timeout: float,
    tunnel_impairment: TunnelImpairment | None,
    metrics: AIWireProxyMetrics,
) -> None:
    _set_socket_options(client)
    use_native = _backend_flag(backend)
    request_encoder: AIWireSessionEncoder | None = None
    response_decoder: AIWireSessionDecoder | None = None
    if tunnel_codec == "aiwire":
        request_encoder = AIWireSessionEncoder(level=level, use_native=use_native)
        response_decoder = AIWireSessionDecoder(use_native=use_native)
        metrics.encoder_backend = request_encoder.backend
        metrics.decoder_backend = response_decoder.backend
    else:
        metrics.encoder_backend = tunnel_codec
        metrics.decoder_backend = tunnel_codec

    started_ns = time.perf_counter_ns()
    tunnel_socket = socket.create_connection(
        (egress_host, egress_port),
        timeout=connect_timeout,
    )
    metrics.record_stage("connect_egress", time.perf_counter_ns() - started_ns)

    with tunnel_socket as tunnel:
        _set_socket_options(tunnel)
        started_ns = time.perf_counter_ns()
        metrics.tunnel_control_framed_bytes += _write_proxy_client_hello(
            tunnel,
            level=level,
            backend=backend,
            tunnel_codec=tunnel_codec,
            impairment=tunnel_impairment,
        )
        metrics.record_stage("handshake_write_hello", time.perf_counter_ns() - started_ns)
        started_ns = time.perf_counter_ns()
        ack, ack_bytes = _read_proxy_server_ack(
            tunnel,
            max_frame_bytes=max_frame_bytes,
            tunnel_codec=tunnel_codec,
        )
        metrics.record_stage("handshake_read_ack", time.perf_counter_ns() - started_ns)
        metrics.tunnel_control_framed_bytes += ack_bytes
        metrics.handshakes_accepted += 1
        metrics.negotiation_codec = str(ack.get("codec") or "")
        version = ack.get("version")
        metrics.negotiation_version = int(version) if version is not None else None
        metrics.negotiation_reason = (
            str(ack.get("reason")) if ack.get("reason") is not None else None
        )

        while True:
            started_ns = time.perf_counter_ns()
            try:
                raw_request = read_length_prefixed(client, max_frame_bytes=max_frame_bytes)
            except EOFError:
                break
            metrics.record_stage("client_read", time.perf_counter_ns() - started_ns)

            metrics.raw_request_payload_bytes += len(raw_request)
            metrics.raw_framed_bytes += _U32.size + len(raw_request)

            started_ns = time.perf_counter_ns()
            tunneled_request = _encode_semantic_payload(
                tunnel_codec,
                raw_request,
                encoder=request_encoder,
                level=level,
            )
            metrics.record_stage("request_encode", time.perf_counter_ns() - started_ns)

            started_ns = time.perf_counter_ns()
            framed_bytes, impairment_wait_ns = write_tunnel_frame_with_stats(
                tunnel,
                AIWIRE_PROXY_SEMANTIC_LANE,
                tunneled_request,
                impairment=tunnel_impairment,
            )
            metrics.record_stage("tunnel_request_write", time.perf_counter_ns() - started_ns)
            metrics.add_tunnel_impairment_wait(impairment_wait_ns)
            metrics.tunnel_request_framed_bytes += framed_bytes

            started_ns = time.perf_counter_ns()
            lane, tunneled_response, framed_bytes = read_tunnel_frame_with_size(
                tunnel,
                max_frame_bytes=max_frame_bytes,
            )
            metrics.record_stage("tunnel_response_read", time.perf_counter_ns() - started_ns)
            if lane != AIWIRE_PROXY_SEMANTIC_LANE:
                raise AIWireProxyProtocolError("expected semantic response frame")
            metrics.tunnel_response_framed_bytes += framed_bytes

            started_ns = time.perf_counter_ns()
            raw_response = _decode_semantic_payload(
                tunnel_codec,
                tunneled_response,
                decoder=response_decoder,
            )
            metrics.record_stage("response_decode", time.perf_counter_ns() - started_ns)

            started_ns = time.perf_counter_ns()
            write_length_prefixed(client, raw_response)
            metrics.record_stage("client_response_write", time.perf_counter_ns() - started_ns)
            metrics.raw_response_payload_bytes += len(raw_response)
            metrics.raw_framed_bytes += _U32.size + len(raw_response)
            metrics.exchanges += 1


def _handle_egress_connection(
    tunnel: socket.socket,
    *,
    upstream_host: str,
    upstream_port: int,
    upstream_responder: EgressUpstreamResponder | None,
    level: int,
    backend: BackendName,
    tunnel_codec: TunnelCodec,
    max_frame_bytes: int,
    connect_timeout: float,
    tunnel_impairment: TunnelImpairment | None,
    metrics: AIWireProxyMetrics,
) -> None:
    _set_socket_options(tunnel)
    started_ns = time.perf_counter_ns()
    control_bytes, ack = _accept_proxy_handshake(
        tunnel,
        level=level,
        backend=backend,
        tunnel_codec=tunnel_codec,
        max_frame_bytes=max_frame_bytes,
        impairment=tunnel_impairment,
    )
    metrics.record_stage("handshake_accept", time.perf_counter_ns() - started_ns)
    metrics.tunnel_control_framed_bytes += control_bytes
    metrics.handshakes_accepted += 1
    metrics.negotiation_codec = str(ack.get("codec") or "")
    version = ack.get("version")
    metrics.negotiation_version = int(version) if version is not None else None
    metrics.negotiation_reason = str(ack.get("reason")) if ack.get("reason") else None

    use_native = _backend_flag(backend)
    request_decoder: AIWireSessionDecoder | None = None
    response_encoder: AIWireSessionEncoder | None = None
    if tunnel_codec == "aiwire":
        request_decoder = AIWireSessionDecoder(use_native=use_native)
        response_encoder = AIWireSessionEncoder(level=level, use_native=use_native)
        metrics.encoder_backend = response_encoder.backend
        metrics.decoder_backend = request_decoder.backend
    else:
        metrics.encoder_backend = tunnel_codec
        metrics.decoder_backend = tunnel_codec

    if upstream_responder is not None:
        exchange_index = 0
        while True:
            started_ns = time.perf_counter_ns()
            try:
                lane, tunneled_request, framed_bytes = read_tunnel_frame_with_size(
                    tunnel,
                    max_frame_bytes=max_frame_bytes,
                )
            except EOFError:
                break
            metrics.record_stage("tunnel_request_read", time.perf_counter_ns() - started_ns)
            if lane != AIWIRE_PROXY_SEMANTIC_LANE:
                raise AIWireProxyProtocolError("expected semantic request frame")
            metrics.tunnel_request_framed_bytes += framed_bytes

            started_ns = time.perf_counter_ns()
            raw_request = _decode_semantic_payload(
                tunnel_codec,
                tunneled_request,
                decoder=request_decoder,
            )
            metrics.record_stage("request_decode", time.perf_counter_ns() - started_ns)
            metrics.raw_request_payload_bytes += len(raw_request)
            metrics.raw_framed_bytes += _U32.size + len(raw_request)

            started_ns = time.perf_counter_ns()
            raw_response = upstream_responder(raw_request, exchange_index)
            metrics.record_stage("upstream_response_inline", time.perf_counter_ns() - started_ns)
            metrics.raw_response_payload_bytes += len(raw_response)
            metrics.raw_framed_bytes += _U32.size + len(raw_response)

            started_ns = time.perf_counter_ns()
            tunneled_response = _encode_semantic_payload(
                tunnel_codec,
                raw_response,
                encoder=response_encoder,
                level=level,
            )
            metrics.record_stage("response_encode", time.perf_counter_ns() - started_ns)

            started_ns = time.perf_counter_ns()
            framed_bytes, impairment_wait_ns = write_tunnel_frame_with_stats(
                tunnel,
                AIWIRE_PROXY_SEMANTIC_LANE,
                tunneled_response,
                impairment=tunnel_impairment,
            )
            metrics.record_stage("tunnel_response_write", time.perf_counter_ns() - started_ns)
            metrics.add_tunnel_impairment_wait(impairment_wait_ns)
            metrics.tunnel_response_framed_bytes += framed_bytes
            metrics.exchanges += 1
            exchange_index += 1
        return

    started_ns = time.perf_counter_ns()
    upstream_socket = socket.create_connection(
        (upstream_host, upstream_port),
        timeout=connect_timeout,
    )
    metrics.record_stage("connect_upstream", time.perf_counter_ns() - started_ns)

    with upstream_socket as upstream:
        _set_socket_options(upstream)
        while True:
            started_ns = time.perf_counter_ns()
            try:
                lane, tunneled_request, framed_bytes = read_tunnel_frame_with_size(
                    tunnel,
                    max_frame_bytes=max_frame_bytes,
                )
            except EOFError:
                break
            metrics.record_stage("tunnel_request_read", time.perf_counter_ns() - started_ns)
            if lane != AIWIRE_PROXY_SEMANTIC_LANE:
                raise AIWireProxyProtocolError("expected semantic request frame")
            metrics.tunnel_request_framed_bytes += framed_bytes

            started_ns = time.perf_counter_ns()
            raw_request = _decode_semantic_payload(
                tunnel_codec,
                tunneled_request,
                decoder=request_decoder,
            )
            metrics.record_stage("request_decode", time.perf_counter_ns() - started_ns)

            started_ns = time.perf_counter_ns()
            write_length_prefixed(upstream, raw_request)
            metrics.record_stage("upstream_request_write", time.perf_counter_ns() - started_ns)
            metrics.raw_request_payload_bytes += len(raw_request)
            metrics.raw_framed_bytes += _U32.size + len(raw_request)

            started_ns = time.perf_counter_ns()
            raw_response = read_length_prefixed(upstream, max_frame_bytes=max_frame_bytes)
            metrics.record_stage("upstream_response_read", time.perf_counter_ns() - started_ns)
            metrics.raw_response_payload_bytes += len(raw_response)
            metrics.raw_framed_bytes += _U32.size + len(raw_response)

            started_ns = time.perf_counter_ns()
            tunneled_response = _encode_semantic_payload(
                tunnel_codec,
                raw_response,
                encoder=response_encoder,
                level=level,
            )
            metrics.record_stage("response_encode", time.perf_counter_ns() - started_ns)

            started_ns = time.perf_counter_ns()
            framed_bytes, impairment_wait_ns = write_tunnel_frame_with_stats(
                tunnel,
                AIWIRE_PROXY_SEMANTIC_LANE,
                tunneled_response,
                impairment=tunnel_impairment,
            )
            metrics.record_stage("tunnel_response_write", time.perf_counter_ns() - started_ns)
            metrics.add_tunnel_impairment_wait(impairment_wait_ns)
            metrics.tunnel_response_framed_bytes += framed_bytes
            metrics.exchanges += 1


def _run_listener(
    *,
    mode: ProxyMode,
    listen_host: str,
    listen_port: int,
    target_host: str,
    target_port: int,
    level: int,
    backend: BackendName,
    tunnel_codec: TunnelCodec,
    max_frame_bytes: int,
    max_connections: int | None,
    connect_timeout: float,
    tunnel_impairment_config: TunnelImpairmentConfig,
    metrics_output: str | Path | None,
    replay_log_output: str | Path | None,
    ready_callback: Callable[[int], None] | None,
    upstream_responder: EgressUpstreamResponder | None = None,
) -> AIWireProxyMetrics:
    metrics = AIWireProxyMetrics(
        mode=mode,
        listen_host=listen_host,
        listen_port=listen_port,
        requested_backend=backend,
        tunnel_codec=tunnel_codec,
        level=level,
        max_frame_bytes=max_frame_bytes,
        target_host=target_host,
        target_port=target_port,
        tunnel_impairment=tunnel_impairment_config.to_dict(),
    )
    tunnel_impairment = (
        TunnelImpairment(tunnel_impairment_config) if tunnel_impairment_config.enabled else None
    )
    metrics_lock = threading.Lock()
    workers: list[threading.Thread] = []
    errors: list[BaseException] = []

    def handle_connection(conn: socket.socket) -> None:
        connection_metrics = _connection_metrics_from(metrics)
        try:
            with conn:
                try:
                    if mode == "ingress":
                        _handle_ingress_connection(
                            conn,
                            egress_host=target_host,
                            egress_port=target_port,
                            level=level,
                            backend=backend,
                            tunnel_codec=tunnel_codec,
                            max_frame_bytes=max_frame_bytes,
                            connect_timeout=connect_timeout,
                            tunnel_impairment=tunnel_impairment,
                            metrics=connection_metrics,
                        )
                    else:
                        _handle_egress_connection(
                            conn,
                            upstream_host=target_host,
                            upstream_port=target_port,
                            upstream_responder=upstream_responder,
                            level=level,
                            backend=backend,
                            tunnel_codec=tunnel_codec,
                            max_frame_bytes=max_frame_bytes,
                            connect_timeout=connect_timeout,
                            tunnel_impairment=tunnel_impairment,
                            metrics=connection_metrics,
                        )
                except AIWireProxyHandshakeError:
                    connection_metrics.handshakes_rejected += 1
                    raise
        except BaseException as exc:
            connection_metrics.last_error = f"{type(exc).__name__}: {exc}"
            with metrics_lock:
                errors.append(exc)
        finally:
            with metrics_lock:
                _merge_connection_metrics(metrics, connection_metrics)

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind((listen_host, listen_port))
            metrics.listen_port = int(listener.getsockname()[1])
            listener.listen()
            if ready_callback is not None:
                ready_callback(metrics.listen_port)

            while max_connections is None or metrics.accepted_connections < max_connections:
                conn, _addr = listener.accept()
                with metrics_lock:
                    metrics.accepted_connections += 1
                worker = threading.Thread(target=handle_connection, args=(conn,))
                worker.start()
                workers.append(worker)

            for worker in workers:
                worker.join()
            if errors:
                raise errors[0]
    except BaseException as exc:
        metrics.last_error = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        metrics.finish()
        _write_metrics_outputs(
            metrics,
            metrics_output=metrics_output,
            replay_log_output=replay_log_output,
        )

    return metrics


def run_ingress_proxy(
    *,
    listen_host: str,
    listen_port: int,
    egress_host: str,
    egress_port: int,
    level: int = AI_WIRE_DEFAULT_LEVEL,
    backend: BackendName = "auto",
    tunnel_codec: TunnelCodec = "aiwire",
    max_frame_bytes: int = DEFAULT_MAX_FRAME_BYTES,
    max_connections: int | None = None,
    connect_timeout: float = 5.0,
    tunnel_impairment_config: TunnelImpairmentConfig | None = None,
    metrics_output: str | Path | None = None,
    replay_log_output: str | Path | None = None,
    ready_callback: Callable[[int], None] | None = None,
) -> AIWireProxyMetrics:
    """Run an ingress sidecar from raw local frames to an AIWire tunnel."""

    tunnel_codec = _validate_tunnel_codec(tunnel_codec)
    return _run_listener(
        mode="ingress",
        listen_host=listen_host,
        listen_port=listen_port,
        target_host=egress_host,
        target_port=egress_port,
        level=level,
        backend=backend,
        tunnel_codec=tunnel_codec,
        max_frame_bytes=max_frame_bytes,
        max_connections=max_connections,
        connect_timeout=connect_timeout,
        tunnel_impairment_config=tunnel_impairment_config or TunnelImpairmentConfig(),
        metrics_output=metrics_output,
        replay_log_output=replay_log_output,
        ready_callback=ready_callback,
    )


def run_egress_proxy(
    *,
    listen_host: str,
    listen_port: int,
    upstream_host: str = "",
    upstream_port: int = 0,
    upstream_responder: EgressUpstreamResponder | None = None,
    level: int = AI_WIRE_DEFAULT_LEVEL,
    backend: BackendName = "auto",
    tunnel_codec: TunnelCodec = "aiwire",
    max_frame_bytes: int = DEFAULT_MAX_FRAME_BYTES,
    max_connections: int | None = None,
    connect_timeout: float = 5.0,
    tunnel_impairment_config: TunnelImpairmentConfig | None = None,
    metrics_output: str | Path | None = None,
    replay_log_output: str | Path | None = None,
    ready_callback: Callable[[int], None] | None = None,
) -> AIWireProxyMetrics:
    """Run an egress sidecar from an AIWire tunnel to raw upstream frames."""

    tunnel_codec = _validate_tunnel_codec(tunnel_codec)
    if upstream_responder is None and (not upstream_host or upstream_port <= 0):
        raise ValueError("upstream_host and upstream_port are required without a responder")
    return _run_listener(
        mode="egress",
        listen_host=listen_host,
        listen_port=listen_port,
        target_host=upstream_host,
        target_port=upstream_port,
        level=level,
        backend=backend,
        tunnel_codec=tunnel_codec,
        max_frame_bytes=max_frame_bytes,
        max_connections=max_connections,
        connect_timeout=connect_timeout,
        tunnel_impairment_config=tunnel_impairment_config or TunnelImpairmentConfig(),
        metrics_output=metrics_output,
        replay_log_output=replay_log_output,
        ready_callback=ready_callback,
        upstream_responder=upstream_responder,
    )


__all__ = [
    "AIWIRE_PROXY_CONTROL_LANE",
    "AIWIRE_PROXY_SCHEMA",
    "AIWIRE_PROXY_SEMANTIC_LANE",
    "AIWireProxyError",
    "AIWireProxyHandshakeError",
    "AIWireProxyMetrics",
    "AIWireProxyProtocolError",
    "DEFAULT_MAX_FRAME_BYTES",
    "EgressUpstreamResponder",
    "TUNNEL_CODECS",
    "TunnelImpairment",
    "TunnelImpairmentConfig",
    "TunnelCodec",
    "decode_tunnel_frame",
    "encode_tunnel_frame",
    "read_exact",
    "read_length_prefixed",
    "read_tunnel_frame",
    "read_tunnel_frame_with_size",
    "run_egress_proxy",
    "run_ingress_proxy",
    "write_length_prefixed",
    "write_tunnel_frame",
]
