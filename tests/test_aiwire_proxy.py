from __future__ import annotations

import json
import queue
import socket
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

import pytest

from aura_compression import aiwire_proxy as proxy_module
from aura_compression.ai_wire import build_aiwire_compatibility_manifest, build_aiwire_handshake
from aura_compression.aiwire_proxy import (
    AIWIRE_PROXY_CONTROL_LANE,
    AIWIRE_PROXY_SCHEMA,
    AIWIRE_PROXY_SEMANTIC_LANE,
    AIWireProxyHandshakeError,
    AIWireProxyMetrics,
    AIWireProxyProtocolError,
    AIWireProxyResumeConfig,
    decode_tunnel_frame,
    encode_tunnel_frame,
    read_length_prefixed,
    run_egress_proxy,
    run_ingress_proxy,
    write_length_prefixed,
)
from aura_compression.aiwire_replay_log import loads_replay_log
from aura_compression.aiwire_resume_cache import AIWireResumeCache

HOST = "127.0.0.1"
T = TypeVar("T")


def _canonical_json_bytes(value: dict[str, Any]) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((HOST, 0))
        return int(sock.getsockname()[1])


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


def _get_background_result(
    thread: threading.Thread,
    results: "queue.Queue[T | BaseException]",
) -> T:
    thread.join(timeout=10)
    assert not thread.is_alive(), "background worker did not finish"
    result = results.get_nowait()
    if isinstance(result, BaseException):
        raise result
    return result


def _raw_upstream_echo(
    listener: socket.socket,
    *,
    expected: int,
) -> list[dict[str, Any]]:
    seen: list[dict[str, Any]] = []
    with listener:
        conn, _addr = listener.accept()
        with conn:
            for _ in range(expected):
                payload = read_length_prefixed(conn)
                message = json.loads(payload.decode("utf-8"))
                seen.append(message)
                reply = {
                    "protocol": "local.agent",
                    "schema": "local.agent.proxy_ack.v1",
                    "trace_id": message["trace_id"],
                    "sequence": message["params"]["sequence"],
                    "accepted": True,
                    "status": "routed-through-aiwire-proxy",
                }
                write_length_prefixed(conn, _canonical_json_bytes(reply))
    return seen


def _sample_messages(count: int) -> list[dict[str, Any]]:
    return [
        {
            "protocol": "mcp",
            "jsonrpc": "2.0",
            "id": index,
            "method": "tools/call",
            "trace_id": f"trace-proxy-{index}",
            "params": {
                "name": "edge_status",
                "sequence": index,
                "route": ["mac", "z6", "nano-orin"],
                "arguments": {
                    "agent": "worker",
                    "queue_depth": 4 + index,
                    "window": 2,
                    "status": "delta",
                    "changed_fields": ["queue_depth", "token_cursor"],
                },
            },
        }
        for index in range(count)
    ]


def test_tunnel_frame_round_trips_lanes() -> None:
    control = encode_tunnel_frame(AIWIRE_PROXY_CONTROL_LANE, b'{"ok":true}')
    semantic = encode_tunnel_frame(AIWIRE_PROXY_SEMANTIC_LANE, b"\x00\x00\xff\xff")

    assert decode_tunnel_frame(control) == (AIWIRE_PROXY_CONTROL_LANE, b'{"ok":true}')
    assert decode_tunnel_frame(semantic) == (AIWIRE_PROXY_SEMANTIC_LANE, b"\x00\x00\xff\xff")


def test_tunnel_frame_rejects_unknown_lane_tag() -> None:
    with pytest.raises(AIWireProxyProtocolError, match="unsupported proxy lane tag"):
        decode_tunnel_frame(b"\xffpayload")


def test_length_prefixed_reader_rejects_oversized_frame() -> None:
    left, right = socket.socketpair()
    with left, right:
        write_length_prefixed(left, b"abcd")
        with pytest.raises(AIWireProxyProtocolError, match="exceeds max_frame_bytes"):
            read_length_prefixed(right, max_frame_bytes=3)


def test_proxy_aiwire_handshake_rejects_tampered_compatibility_manifest() -> None:
    left, right = socket.socketpair()
    with left, right:
        manifest = build_aiwire_compatibility_manifest(fallback_codecs=()).to_dict()
        manifest["static_dictionary_sha256"] = "0" * 64
        hello = {
            "schema": AIWIRE_PROXY_SCHEMA,
            "role": "ingress",
            "codec": "aiwire",
            "requested_backend": "python",
            "aiwire_compatibility_manifest": manifest,
            "aiwire_compatibility_manifest_sha256": proxy_module.aiwire_compatibility_manifest_sha256(
                manifest
            ),
            "aiwire_handshake": build_aiwire_handshake(
                level=3,
                use_native=False,
                fallback_codecs=(),
            ).to_dict(),
        }
        proxy_module._write_control_frame(left, hello)  # type: ignore[attr-defined]

        with pytest.raises(AIWireProxyHandshakeError, match="dictionary_sha256_mismatch"):
            proxy_module._accept_proxy_handshake(  # type: ignore[attr-defined]
                right,
                level=3,
                backend="python",
                tunnel_codec="aiwire",
                max_frame_bytes=1024 * 1024,
            )

        ack = proxy_module._read_control_frame(  # type: ignore[attr-defined]
            left,
            max_frame_bytes=1024 * 1024,
        )
        assert ack["accepted"] is False
        assert ack["reason"] == "dictionary_sha256_mismatch"
        assert "aiwire_compatibility_manifest" in ack


def test_proxy_aiwire_required_resume_rejects_missing_shared_state(tmp_path: Path) -> None:
    peer_id = "z6-to-nano"
    namespace = "proxy-test"
    client_cache = AIWireResumeCache(tmp_path / "client-resume.json")
    client_cache.put_state(
        peer_id=peer_id,
        app_namespace=namespace,
        session_templates={128: "agent {0} calls tool {1}"},
        epoch=1,
    )
    resume_config = AIWireProxyResumeConfig(
        cache_path=tmp_path / "server-empty-resume.json",
        peer_id=peer_id,
        app_namespace=namespace,
        require_resume=True,
    )

    left, right = socket.socketpair()
    with left, right:
        resume_hello = proxy_module._build_proxy_resume_hello(  # type: ignore[attr-defined]
            client_cache,
            AIWireProxyResumeConfig(
                cache_path=client_cache.path,
                peer_id=peer_id,
                app_namespace=namespace,
                require_resume=True,
            ),
        )
        hello = proxy_module._proxy_client_hello(  # type: ignore[attr-defined]
            level=3,
            backend="python",
            tunnel_codec="aiwire",
            compatibility_manifest=build_aiwire_compatibility_manifest(fallback_codecs=()),
            resume_hello=resume_hello,
        )
        proxy_module._write_control_frame(left, hello)  # type: ignore[attr-defined]

        with pytest.raises(AIWireProxyHandshakeError, match="no_shared_session_dictionary"):
            proxy_module._accept_proxy_handshake(  # type: ignore[attr-defined]
                right,
                level=3,
                backend="python",
                tunnel_codec="aiwire",
                max_frame_bytes=1024 * 1024,
                resume_config=resume_config,
            )

        ack = proxy_module._read_control_frame(  # type: ignore[attr-defined]
            left,
            max_frame_bytes=1024 * 1024,
        )
        assert ack["accepted"] is False
        assert "no_shared_session_dictionary" in ack["reason"]


def test_proxy_aiwire_required_resume_rejects_auth_mismatch(tmp_path: Path) -> None:
    peer_id = "z6-to-nano"
    namespace = "proxy-test"
    templates = {128: "agent {0} calls tool {1}"}
    client_cache = AIWireResumeCache(tmp_path / "client-resume.json")
    server_cache = AIWireResumeCache(tmp_path / "server-resume.json")
    client_cache.put_state(
        peer_id=peer_id,
        app_namespace=namespace,
        session_templates=templates,
        epoch=1,
    )
    server_cache.put_state(
        peer_id=peer_id,
        app_namespace=namespace,
        session_templates=templates,
        epoch=1,
    )

    left, right = socket.socketpair()
    with left, right:
        resume_hello = client_cache.build_resume_hello(
            peer_id=peer_id,
            app_namespace=namespace,
            auth_key=b"client-key",
        )
        hello = proxy_module._proxy_client_hello(  # type: ignore[attr-defined]
            level=3,
            backend="python",
            tunnel_codec="aiwire",
            compatibility_manifest=build_aiwire_compatibility_manifest(fallback_codecs=()),
            resume_hello=resume_hello,
        )
        proxy_module._write_control_frame(left, hello)  # type: ignore[attr-defined]

        with pytest.raises(AIWireProxyHandshakeError, match="auth tag mismatch"):
            proxy_module._accept_proxy_handshake(  # type: ignore[attr-defined]
                right,
                level=3,
                backend="python",
                tunnel_codec="aiwire",
                max_frame_bytes=1024 * 1024,
                resume_config=AIWireProxyResumeConfig(
                    cache_path=server_cache.path,
                    peer_id=peer_id,
                    app_namespace=namespace,
                    require_resume=True,
                    auth_key=b"server-key",
                ),
            )

        ack = proxy_module._read_control_frame(  # type: ignore[attr-defined]
            left,
            max_frame_bytes=1024 * 1024,
        )
        assert ack["accepted"] is False
        assert "auth tag mismatch" in ack["reason"]


def test_aiwire_proxy_round_trips_raw_agent_frames(tmp_path: Path) -> None:
    messages = _sample_messages(8)
    upstream_listener, upstream_port = _bound_listener()
    egress_port = _free_port()
    ingress_port = _free_port()
    ingress_metrics_path = tmp_path / "ingress.metrics.json"
    egress_metrics_path = tmp_path / "egress.metrics.json"
    ingress_replay_path = tmp_path / "ingress.replay.jsonl"

    upstream_thread, upstream_results = _run_background(
        lambda: _raw_upstream_echo(upstream_listener, expected=len(messages))
    )

    egress_ready = threading.Event()
    egress_thread, egress_results = _run_background(
        lambda: run_egress_proxy(
            listen_host=HOST,
            listen_port=egress_port,
            upstream_host=HOST,
            upstream_port=upstream_port,
            backend="python",
            max_connections=1,
            metrics_output=egress_metrics_path,
            ready_callback=lambda _port: egress_ready.set(),
        )
    )
    assert egress_ready.wait(timeout=5)

    ingress_ready = threading.Event()
    ingress_thread, ingress_results = _run_background(
        lambda: run_ingress_proxy(
            listen_host=HOST,
            listen_port=ingress_port,
            egress_host=HOST,
            egress_port=egress_port,
            backend="python",
            max_connections=1,
            metrics_output=ingress_metrics_path,
            replay_log_output=ingress_replay_path,
            ready_callback=lambda _port: ingress_ready.set(),
        )
    )
    assert ingress_ready.wait(timeout=5)

    replies: list[dict[str, Any]] = []
    with socket.create_connection((HOST, ingress_port), timeout=5) as client:
        for message in messages:
            write_length_prefixed(client, _canonical_json_bytes(message))
            reply = json.loads(read_length_prefixed(client).decode("utf-8"))
            replies.append(reply)

    ingress_metrics = _get_background_result(ingress_thread, ingress_results)
    egress_metrics = _get_background_result(egress_thread, egress_results)
    upstream_seen = _get_background_result(upstream_thread, upstream_results)

    assert [reply["trace_id"] for reply in replies] == [message["trace_id"] for message in messages]
    assert upstream_seen == messages

    for metrics in (ingress_metrics, egress_metrics):
        assert isinstance(metrics, AIWireProxyMetrics)
        assert metrics.exchanges == len(messages)
        assert metrics.handshakes_accepted == 1
        assert metrics.negotiation_codec == "aiwire"
        assert metrics.compatibility_codec == "aiwire"
        assert metrics.compatibility_delta_version == 1
        assert metrics.compatibility_reason is None
        assert len(metrics.compatibility_local_manifest_sha256) == 64
        assert len(metrics.compatibility_peer_manifest_sha256) == 64
        assert metrics.raw_framed_bytes > 0
        assert metrics.tunnel_semantic_framed_bytes > 0
        assert metrics.encoder_backend == "python"
        assert metrics.decoder_backend == "python"
        assert metrics.last_error is None

    rendered_metrics = json.loads(ingress_metrics_path.read_text())
    assert rendered_metrics["mode"] == "ingress"
    assert rendered_metrics["exchanges"] == len(messages)
    assert rendered_metrics["compatibility_codec"] == "aiwire"
    assert json.loads(egress_metrics_path.read_text())["mode"] == "egress"

    replay_records = loads_replay_log(ingress_replay_path.read_text())
    assert [record["record_type"] for record in replay_records] == ["header", "result"]
    assert replay_records[1]["payload"]["row"]["exchanges"] == len(messages)


def test_aiwire_proxy_round_trips_with_required_resume_cache(tmp_path: Path) -> None:
    messages = _sample_messages(6)
    upstream_listener, upstream_port = _bound_listener()
    egress_port = _free_port()
    ingress_port = _free_port()
    peer_id = "z6-to-nano"
    namespace = "proxy-test"
    auth_key = b"proxy-shared-resume-key"
    templates = {
        128: '{"protocol":"mcp","jsonrpc":"2.0","method":"{0}","trace_id":"{1}"}',
        129: '{"status":"{0}","route":["{1}","{2}","{3}"]}',
    }

    ingress_cache = AIWireResumeCache(tmp_path / "ingress-resume.json")
    egress_cache = AIWireResumeCache(tmp_path / "egress-resume.json")
    ingress_entry = ingress_cache.put_state(
        peer_id=peer_id,
        app_namespace=namespace,
        session_templates=templates,
        epoch=2,
    )
    egress_entry = egress_cache.put_state(
        peer_id=peer_id,
        app_namespace=namespace,
        session_templates=templates,
        epoch=2,
    )
    assert ingress_entry.state_hash == egress_entry.state_hash

    upstream_thread, upstream_results = _run_background(
        lambda: _raw_upstream_echo(upstream_listener, expected=len(messages))
    )

    egress_ready = threading.Event()
    egress_thread, egress_results = _run_background(
        lambda: run_egress_proxy(
            listen_host=HOST,
            listen_port=egress_port,
            upstream_host=HOST,
            upstream_port=upstream_port,
            backend="python",
            max_connections=1,
            resume_config=AIWireProxyResumeConfig(
                cache_path=egress_cache.path,
                peer_id=peer_id,
                app_namespace=namespace,
                require_resume=True,
                auth_key=auth_key,
            ),
            ready_callback=lambda _port: egress_ready.set(),
        )
    )
    assert egress_ready.wait(timeout=5)

    ingress_ready = threading.Event()
    ingress_thread, ingress_results = _run_background(
        lambda: run_ingress_proxy(
            listen_host=HOST,
            listen_port=ingress_port,
            egress_host=HOST,
            egress_port=egress_port,
            backend="python",
            max_connections=1,
            resume_config=AIWireProxyResumeConfig(
                cache_path=ingress_cache.path,
                peer_id=peer_id,
                app_namespace=namespace,
                require_resume=True,
                auth_key=auth_key,
            ),
            ready_callback=lambda _port: ingress_ready.set(),
        )
    )
    assert ingress_ready.wait(timeout=5)

    replies: list[dict[str, Any]] = []
    with socket.create_connection((HOST, ingress_port), timeout=5) as client:
        for message in messages:
            write_length_prefixed(client, _canonical_json_bytes(message))
            replies.append(json.loads(read_length_prefixed(client).decode("utf-8")))

    ingress_metrics = _get_background_result(ingress_thread, ingress_results)
    egress_metrics = _get_background_result(egress_thread, egress_results)
    upstream_seen = _get_background_result(upstream_thread, upstream_results)

    assert [reply["trace_id"] for reply in replies] == [message["trace_id"] for message in messages]
    assert upstream_seen == messages

    for metrics in (ingress_metrics, egress_metrics):
        assert metrics.exchanges == len(messages)
        assert metrics.session_resume_enabled is True
        assert metrics.session_resume_required is True
        assert metrics.session_resume_authenticated is True
        assert metrics.session_resume_accepted is True
        assert metrics.session_resume_reason is None
        assert metrics.session_resume_state_hash == ingress_entry.state_hash
        assert metrics.session_resume_epoch == 2
        assert metrics.session_resume_template_count == len(templates)
        assert metrics.last_error is None

    assert ingress_metrics.session_resume_offered_hashes == 1
