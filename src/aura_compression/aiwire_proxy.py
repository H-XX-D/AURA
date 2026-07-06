"""Explicit TCP sidecar proxy for AIWire-tunneled agent frames.

The proxy is intentionally opt-in.  Client and upstream applications keep
speaking their normal length-prefixed bytes, while the inter-machine hop carries
AIWire frames plus inspectable control frames.
"""

from __future__ import annotations

import json
import socket
import struct
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
ProxyMode = Literal["ingress", "egress"]


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


def _canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


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


def write_tunnel_frame(sock: socket.socket, lane: str, payload: bytes) -> int:
    """Write a tagged proxy tunnel frame and return framed bytes sent."""

    return write_length_prefixed(sock, encode_tunnel_frame(lane, payload))


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


def _write_control_frame(sock: socket.socket, payload: Mapping[str, Any]) -> int:
    return write_tunnel_frame(
        sock,
        AIWIRE_PROXY_CONTROL_LANE,
        _canonical_json_bytes(payload),
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

    def finish(self) -> None:
        self.ended_at_utc = _utc_now()

    def to_result_row(self) -> dict[str, Any]:
        backend = self.encoder_backend or self.decoder_backend or self.requested_backend
        return {
            "target_label": f"{self.target_host}:{self.target_port}",
            "codec": "aiwire",
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


def _proxy_client_hello(
    *,
    level: int,
    backend: BackendName,
) -> dict[str, Any]:
    handshake = build_aiwire_handshake(
        level=level,
        use_native=_backend_flag(backend),
        fallback_codecs=(),
    )
    return {
        "schema": AIWIRE_PROXY_SCHEMA,
        "role": "ingress",
        "codec": "aiwire",
        "requested_backend": backend,
        "aiwire_handshake": handshake.to_dict(),
    }


def _write_proxy_client_hello(
    sock: socket.socket,
    *,
    level: int,
    backend: BackendName,
) -> int:
    return _write_control_frame(sock, _proxy_client_hello(level=level, backend=backend))


def _read_proxy_server_ack(
    sock: socket.socket,
    *,
    max_frame_bytes: int,
) -> tuple[dict[str, Any], int]:
    ack, framed_bytes = _read_control_frame_with_size(sock, max_frame_bytes=max_frame_bytes)
    if ack.get("role") != "egress":
        raise AIWireProxyHandshakeError("proxy handshake ack came from unexpected role")
    if not ack.get("accepted"):
        reason = ack.get("reason") or "rejected"
        raise AIWireProxyHandshakeError(f"AIWire proxy handshake rejected: {reason}")
    if ack.get("codec") != "aiwire":
        raise AIWireProxyHandshakeError("AIWire proxy requires aiwire codec")
    return ack, framed_bytes


def _accept_proxy_handshake(
    sock: socket.socket,
    *,
    level: int,
    backend: BackendName,
    max_frame_bytes: int,
) -> tuple[int, dict[str, Any]]:
    control_bytes = 0
    hello, hello_bytes = _read_control_frame_with_size(sock, max_frame_bytes=max_frame_bytes)
    control_bytes += hello_bytes
    if hello.get("role") != "ingress":
        raise AIWireProxyHandshakeError("proxy handshake hello came from unexpected role")
    if hello.get("codec") != "aiwire":
        raise AIWireProxyHandshakeError("AIWire proxy requires aiwire codec")
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
    control_bytes += _write_control_frame(sock, ack)
    if not negotiation.accepted:
        reason = negotiation.reason or "rejected"
        raise AIWireProxyHandshakeError(f"AIWire proxy handshake rejected: {reason}")
    return control_bytes, ack


def _handle_ingress_connection(
    client: socket.socket,
    *,
    egress_host: str,
    egress_port: int,
    level: int,
    backend: BackendName,
    max_frame_bytes: int,
    connect_timeout: float,
    metrics: AIWireProxyMetrics,
) -> None:
    _set_socket_options(client)
    use_native = _backend_flag(backend)
    request_encoder = AIWireSessionEncoder(level=level, use_native=use_native)
    response_decoder = AIWireSessionDecoder(use_native=use_native)
    metrics.encoder_backend = request_encoder.backend
    metrics.decoder_backend = response_decoder.backend

    with socket.create_connection(
        (egress_host, egress_port),
        timeout=connect_timeout,
    ) as tunnel:
        _set_socket_options(tunnel)
        metrics.tunnel_control_framed_bytes += _write_proxy_client_hello(
            tunnel,
            level=level,
            backend=backend,
        )
        ack, ack_bytes = _read_proxy_server_ack(tunnel, max_frame_bytes=max_frame_bytes)
        metrics.tunnel_control_framed_bytes += ack_bytes
        metrics.handshakes_accepted += 1
        metrics.negotiation_codec = str(ack.get("codec") or "")
        version = ack.get("version")
        metrics.negotiation_version = int(version) if version is not None else None
        metrics.negotiation_reason = (
            str(ack.get("reason")) if ack.get("reason") is not None else None
        )

        while True:
            try:
                raw_request = read_length_prefixed(client, max_frame_bytes=max_frame_bytes)
            except EOFError:
                break

            metrics.raw_request_payload_bytes += len(raw_request)
            metrics.raw_framed_bytes += _U32.size + len(raw_request)

            compressed_request = request_encoder.compress_frame(raw_request)
            metrics.tunnel_request_framed_bytes += write_tunnel_frame(
                tunnel,
                AIWIRE_PROXY_SEMANTIC_LANE,
                compressed_request,
            )

            lane, compressed_response = read_tunnel_frame(
                tunnel,
                max_frame_bytes=max_frame_bytes,
            )
            if lane != AIWIRE_PROXY_SEMANTIC_LANE:
                raise AIWireProxyProtocolError("expected semantic response frame")
            metrics.tunnel_response_framed_bytes += _U32.size + 1 + len(compressed_response)

            raw_response = response_decoder.decompress_frame(compressed_response)
            write_length_prefixed(client, raw_response)
            metrics.raw_response_payload_bytes += len(raw_response)
            metrics.raw_framed_bytes += _U32.size + len(raw_response)
            metrics.exchanges += 1


def _handle_egress_connection(
    tunnel: socket.socket,
    *,
    upstream_host: str,
    upstream_port: int,
    level: int,
    backend: BackendName,
    max_frame_bytes: int,
    connect_timeout: float,
    metrics: AIWireProxyMetrics,
) -> None:
    _set_socket_options(tunnel)
    control_bytes, ack = _accept_proxy_handshake(
        tunnel,
        level=level,
        backend=backend,
        max_frame_bytes=max_frame_bytes,
    )
    metrics.tunnel_control_framed_bytes += control_bytes
    metrics.handshakes_accepted += 1
    metrics.negotiation_codec = str(ack.get("codec") or "")
    version = ack.get("version")
    metrics.negotiation_version = int(version) if version is not None else None
    metrics.negotiation_reason = str(ack.get("reason")) if ack.get("reason") else None

    use_native = _backend_flag(backend)
    request_decoder = AIWireSessionDecoder(use_native=use_native)
    response_encoder = AIWireSessionEncoder(level=level, use_native=use_native)
    metrics.encoder_backend = response_encoder.backend
    metrics.decoder_backend = request_decoder.backend

    with socket.create_connection(
        (upstream_host, upstream_port),
        timeout=connect_timeout,
    ) as upstream:
        _set_socket_options(upstream)
        while True:
            try:
                lane, compressed_request = read_tunnel_frame(
                    tunnel,
                    max_frame_bytes=max_frame_bytes,
                )
            except EOFError:
                break
            if lane != AIWIRE_PROXY_SEMANTIC_LANE:
                raise AIWireProxyProtocolError("expected semantic request frame")
            metrics.tunnel_request_framed_bytes += _U32.size + 1 + len(compressed_request)

            raw_request = request_decoder.decompress_frame(compressed_request)
            write_length_prefixed(upstream, raw_request)
            metrics.raw_request_payload_bytes += len(raw_request)
            metrics.raw_framed_bytes += _U32.size + len(raw_request)

            raw_response = read_length_prefixed(upstream, max_frame_bytes=max_frame_bytes)
            metrics.raw_response_payload_bytes += len(raw_response)
            metrics.raw_framed_bytes += _U32.size + len(raw_response)

            compressed_response = response_encoder.compress_frame(raw_response)
            metrics.tunnel_response_framed_bytes += write_tunnel_frame(
                tunnel,
                AIWIRE_PROXY_SEMANTIC_LANE,
                compressed_response,
            )
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
    max_frame_bytes: int,
    max_connections: int | None,
    connect_timeout: float,
    metrics_output: str | Path | None,
    replay_log_output: str | Path | None,
    ready_callback: Callable[[int], None] | None,
) -> AIWireProxyMetrics:
    metrics = AIWireProxyMetrics(
        mode=mode,
        listen_host=listen_host,
        listen_port=listen_port,
        requested_backend=backend,
        level=level,
        max_frame_bytes=max_frame_bytes,
        target_host=target_host,
        target_port=target_port,
    )

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
                metrics.accepted_connections += 1
                with conn:
                    try:
                        if mode == "ingress":
                            _handle_ingress_connection(
                                conn,
                                egress_host=target_host,
                                egress_port=target_port,
                                level=level,
                                backend=backend,
                                max_frame_bytes=max_frame_bytes,
                                connect_timeout=connect_timeout,
                                metrics=metrics,
                            )
                        else:
                            _handle_egress_connection(
                                conn,
                                upstream_host=target_host,
                                upstream_port=target_port,
                                level=level,
                                backend=backend,
                                max_frame_bytes=max_frame_bytes,
                                connect_timeout=connect_timeout,
                                metrics=metrics,
                            )
                    except AIWireProxyHandshakeError:
                        metrics.handshakes_rejected += 1
                        raise
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
    max_frame_bytes: int = DEFAULT_MAX_FRAME_BYTES,
    max_connections: int | None = None,
    connect_timeout: float = 5.0,
    metrics_output: str | Path | None = None,
    replay_log_output: str | Path | None = None,
    ready_callback: Callable[[int], None] | None = None,
) -> AIWireProxyMetrics:
    """Run an ingress sidecar from raw local frames to an AIWire tunnel."""

    return _run_listener(
        mode="ingress",
        listen_host=listen_host,
        listen_port=listen_port,
        target_host=egress_host,
        target_port=egress_port,
        level=level,
        backend=backend,
        max_frame_bytes=max_frame_bytes,
        max_connections=max_connections,
        connect_timeout=connect_timeout,
        metrics_output=metrics_output,
        replay_log_output=replay_log_output,
        ready_callback=ready_callback,
    )


def run_egress_proxy(
    *,
    listen_host: str,
    listen_port: int,
    upstream_host: str,
    upstream_port: int,
    level: int = AI_WIRE_DEFAULT_LEVEL,
    backend: BackendName = "auto",
    max_frame_bytes: int = DEFAULT_MAX_FRAME_BYTES,
    max_connections: int | None = None,
    connect_timeout: float = 5.0,
    metrics_output: str | Path | None = None,
    replay_log_output: str | Path | None = None,
    ready_callback: Callable[[int], None] | None = None,
) -> AIWireProxyMetrics:
    """Run an egress sidecar from an AIWire tunnel to raw upstream frames."""

    return _run_listener(
        mode="egress",
        listen_host=listen_host,
        listen_port=listen_port,
        target_host=upstream_host,
        target_port=upstream_port,
        level=level,
        backend=backend,
        max_frame_bytes=max_frame_bytes,
        max_connections=max_connections,
        connect_timeout=connect_timeout,
        metrics_output=metrics_output,
        replay_log_output=replay_log_output,
        ready_callback=ready_callback,
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
