#!/usr/bin/env python3
"""Benchmark AI-to-AI message compression over a real TCP link.

The client builds protocol-shaped agent messages, compresses them locally, sends
length-prefixed frames to a remote server, and the server decompresses and hashes
the restored payloads before acknowledging the run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import socket
import struct
import time
import zlib
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parent.parent / "src"
import sys

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aura_compression.ai_wire import (
    AI_WIRE_DEFAULT_LEVEL,
    AI_WIRE_VERSION,
    AIWireSessionDecoder,
    AIWireSessionEncoder,
    build_aiwire_handshake,
    negotiate_aiwire_handshake,
)
from aura_compression.brio_full import BrioDecoder, BrioEncoder
from aura_compression.compressor_refactored import ProductionHybridCompressor

U32 = struct.Struct("!I")


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


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
    header = _read_exact(sock, U32.size)
    length = U32.unpack(header)[0]
    if length == 0:
        return b""
    return _read_exact(sock, length)


def _configure_low_latency(sock: socket.socket) -> None:
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)


def _make_aura(cache_dir: str) -> ProductionHybridCompressor:
    return ProductionHybridCompressor(
        enable_aura=True,
        enable_audit_logging=False,
        enable_fast_path=True,
        enable_sidechain=False,
        enable_scorer=False,
        enable_ml_selection=True,
        template_sync_interval_seconds=None,
        template_cache_dir=cache_dir,
    )


def build_ai_messages(count: int, seed: int = 1729) -> list[bytes]:
    """Build realistic protocol-shaped AI/agent messages.

    Shapes are based on common agent traffic: model requests, tool calls,
    JSON-RPC tool invocations, agent task messages, tool results, and handoffs.
    """

    rng = random.Random(seed)
    tools = ["web_search", "read_file", "write_patch", "run_shell", "vector_lookup"]
    agents = ["planner", "researcher", "coder", "reviewer", "executor", "summarizer"]
    repos = ["payments-api", "retrieval-worker", "aura-bridge", "policy-gateway"]
    cities = ["Austin", "Seattle", "San Jose", "Chicago", "Boston", "Denver"]
    messages: list[bytes] = []

    for i in range(count):
        tool = tools[i % len(tools)]
        agent = agents[i % len(agents)]
        repo = repos[i % len(repos)]
        city = cities[i % len(cities)]
        trace_id = f"trace-{seed}-{i:05d}"
        task_id = f"task-{(i // 4):04d}"
        call_id = f"call_{i:06d}"
        variant = i % 12

        if variant == 0:
            payload = {
                "protocol": "openai.responses",
                "operation": "responses.create",
                "trace_id": trace_id,
                "model": "gpt-4.1-mini",
                "input": [
                    {
                        "role": "system",
                        "content": "You are the planner agent. Produce executable subgoals and request tools only when needed.",
                    },
                    {
                        "role": "user",
                        "content": f"Investigate latency regression in {repo} for the {city} deployment.",
                    },
                ],
                "tools": [
                    {
                        "type": "function",
                        "name": "search_logs",
                        "description": "Search structured service logs by query and time range.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "service": {"type": "string"},
                                "query": {"type": "string"},
                                "since_minutes": {"type": "integer"},
                            },
                            "required": ["service", "query"],
                        },
                    }
                ],
                "metadata": {"tenant": "bench", "task_id": task_id, "priority": i % 5},
            }
        elif variant == 1:
            payload = {
                "protocol": "openai.responses",
                "type": "response.output_item.done",
                "trace_id": trace_id,
                "item": {
                    "type": "function_call",
                    "call_id": call_id,
                    "name": tool,
                    "arguments": {
                        "repository": repo,
                        "path": f"services/{repo}/src/handler_{i % 9}.py",
                        "query": f"timeout OR retry OR p95 city:{city}",
                        "limit": 20 + (i % 7),
                    },
                },
            }
        elif variant == 2:
            payload = {
                "protocol": "mcp",
                "jsonrpc": "2.0",
                "id": i,
                "method": "tools/call",
                "params": {
                    "name": tool,
                    "arguments": {
                        "session_id": task_id,
                        "uri": f"repo://{repo}/services/{agent}/config.yaml",
                        "line_start": 10 + i % 40,
                        "line_end": 35 + i % 80,
                    },
                },
            }
        elif variant == 3:
            payload = {
                "protocol": "mcp",
                "jsonrpc": "2.0",
                "id": i,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": f"{agent} found repeated retry budget exhaustion in {repo}; next action is patch validation.",
                        }
                    ],
                    "isError": False,
                    "structuredContent": {
                        "matches": [
                            {
                                "file": f"{repo}/handler.py",
                                "line": 42 + j,
                                "score": round(0.91 - j * 0.07, 3),
                            }
                            for j in range(3)
                        ],
                        "trace_id": trace_id,
                    },
                },
            }
        elif variant == 4:
            payload = {
                "protocol": "a2a",
                "jsonrpc": "2.0",
                "id": i,
                "method": "message/send",
                "params": {
                    "message": {
                        "messageId": f"msg-{i:06d}",
                        "role": "user",
                        "parts": [
                            {
                                "kind": "text",
                                "text": f"Agent {agent}, produce a remediation plan for {repo} using only verified evidence.",
                            }
                        ],
                        "metadata": {"trace_id": trace_id, "task_id": task_id},
                    }
                },
            }
        elif variant == 5:
            payload = {
                "protocol": "a2a",
                "jsonrpc": "2.0",
                "id": i,
                "result": {
                    "id": task_id,
                    "contextId": f"ctx-{i // 12:04d}",
                    "status": {
                        "state": "working" if i % 3 else "completed",
                        "message": {
                            "role": "agent",
                            "parts": [
                                {
                                    "kind": "text",
                                    "text": f"{agent} completed evidence pass {i % 5}; confidence={0.72 + (i % 9) / 100:.2f}",
                                }
                            ],
                        },
                    },
                    "artifacts": [
                        {
                            "artifactId": f"artifact-{i:06d}",
                            "name": "diagnostic-summary",
                            "parts": [
                                {
                                    "kind": "text",
                                    "text": "p95 latency increased after retry fanout change",
                                }
                            ],
                        }
                    ],
                },
            }
        elif variant == 6:
            payload = {
                "protocol": "agent.trace",
                "event": "plan.created",
                "trace_id": trace_id,
                "agent": agent,
                "task": {
                    "id": task_id,
                    "objective": f"Reduce {repo} tail latency without increasing error budget burn.",
                    "constraints": [
                        "no schema migration",
                        "rollback must be single commit",
                        "verify with replay",
                    ],
                    "subgoals": [
                        "read deployment diff",
                        "inspect retry policy",
                        "run focused load probe",
                        "draft patch",
                    ],
                },
            }
        elif variant == 7:
            payload = {
                "protocol": "agent.handoff",
                "from": "planner",
                "to": agent,
                "trace_id": trace_id,
                "handoff": {
                    "task_id": task_id,
                    "working_memory": {
                        "facts": [
                            f"{repo} p95 increased in {city}",
                            "no database saturation observed",
                            "retry fanout changed in latest deploy",
                        ],
                        "open_questions": [
                            "does circuit breaker trip before retry budget?",
                            "are cache misses correlated with provider region?",
                        ],
                    },
                    "requested_output_schema": {
                        "type": "object",
                        "required": ["finding", "evidence", "next_action", "confidence"],
                    },
                },
            }
        elif variant == 8:
            payload = {
                "protocol": "tool.result",
                "trace_id": trace_id,
                "tool_call_id": call_id,
                "name": tool,
                "ok": True,
                "elapsed_ms": 18 + (i % 37),
                "output": {
                    "rows": [
                        {
                            "timestamp": f"2026-06-29T18:{(i + j) % 60:02d}:{(11 + j) % 60:02d}Z",
                            "service": repo,
                            "level": "WARN" if j % 2 else "INFO",
                            "message": f"retry budget consumed for shard={j} city={city} attempt={1 + j}",
                        }
                        for j in range(5)
                    ]
                },
            }
        elif variant == 9:
            payload = {
                "protocol": "memory.write",
                "trace_id": trace_id,
                "kind": "observation",
                "title": f"{repo} retry fanout suspected",
                "body": f"{agent} observed matching latency spike and retry count increase in {city}.",
                "confidence": round(0.74 + (i % 11) / 100, 3),
                "evidence": {
                    "source_refs": [
                        f"logs://{repo}/{city}/{i % 24:02d}",
                        f"repo://{repo}/deploy/{i % 13}",
                    ],
                    "supports": [],
                    "contradicts": [],
                },
            }
        elif variant == 10:
            payload = {
                "protocol": "agent.review",
                "trace_id": trace_id,
                "reviewer": "reviewer",
                "patch": {
                    "repo": repo,
                    "files_changed": [
                        f"services/{repo}/retry.py",
                        f"services/{repo}/tests/test_retry_policy.py",
                    ],
                    "diff_summary": [
                        "cap retry fanout per upstream request",
                        "add histogram bucket for retry exhaustion",
                        "preserve existing timeout envelope",
                    ],
                },
                "verdict": "request_changes" if i % 4 == 0 else "approve",
                "comments": [
                    {
                        "line": 58,
                        "severity": "medium",
                        "text": "Add replay test for retry budget boundary.",
                    },
                    {"line": 91, "severity": "low", "text": "Name the metric with service prefix."},
                ],
            }
        else:
            payload = {
                "protocol": "agent.final",
                "trace_id": trace_id,
                "task_id": task_id,
                "agent": "summarizer",
                "status": "completed",
                "answer": {
                    "summary": f"Root cause likely retry fanout in {repo}; mitigation is bounded retries plus replay verification.",
                    "actions": [
                        {"owner": "coder", "action": "apply retry cap", "state": "ready"},
                        {"owner": "executor", "action": "run canary replay", "state": "queued"},
                    ],
                    "confidence": round(0.81 + (i % 13) / 100, 3),
                },
            }

        messages.append(_json_bytes(payload))

    rng.shuffle(messages)
    return messages


def batch_messages(messages: list[bytes], batch_size: int) -> list[bytes]:
    if batch_size <= 1:
        return messages
    return [b"\n".join(messages[i : i + batch_size]) for i in range(0, len(messages), batch_size)]


def _sha_update_frames(frames: Iterable[bytes]) -> str:
    digest = hashlib.sha256()
    for frame in frames:
        digest.update(U32.pack(len(frame)))
        digest.update(frame)
    return digest.hexdigest()


def encode_frames(
    codec: str,
    frames: list[bytes],
    cache_dir: str,
    aiwire_level: int = AI_WIRE_DEFAULT_LEVEL,
) -> tuple[list[bytes], dict[str, Any]]:
    compress_ns = 0
    methods: Counter[str] = Counter()
    encoded: list[bytes] = []

    aura: ProductionHybridCompressor | None = None
    if codec == "aura":
        aura = _make_aura(cache_dir)
    brio_encoder: BrioEncoder | None = BrioEncoder() if codec == "brio" else None
    aiwire_encoder: AIWireSessionEncoder | None = None
    if codec == "aiwire":
        aiwire_encoder = AIWireSessionEncoder(level=aiwire_level)

    for frame in frames:
        start = time.perf_counter_ns()
        if codec == "raw":
            payload = frame
        elif codec == "aura":
            assert aura is not None
            payload, method, meta = aura.compress(frame.decode("utf-8"))
            methods[meta.get("method", method.name.lower())] += 1
        elif codec == "brio":
            assert brio_encoder is not None
            payload = brio_encoder.compress(frame.decode("utf-8")).payload
        elif codec == "zlib":
            payload = zlib.compress(frame, 3)
        elif codec == "aiwire":
            assert aiwire_encoder is not None
            payload = aiwire_encoder.compress_frame(frame)
            methods[f"aiwire-v{AI_WIRE_VERSION}-{aiwire_encoder.backend}-level{aiwire_level}"] += 1
        else:
            raise ValueError(f"unsupported codec: {codec}")
        compress_ns += time.perf_counter_ns() - start
        encoded.append(payload)

    return encoded, {
        "client_compress_ms": compress_ns / 1_000_000,
        "method_counts": dict(methods),
    }


def server_once(conn: socket.socket, cache_dir: str) -> None:
    hello = json.loads(_read_frame(conn))
    requested_codec = hello["codec"]
    codec = requested_codec
    expected_sha = hello["expected_sha256"]
    negotiation_payload: dict[str, Any] | None = None

    if requested_codec == "aiwire":
        negotiation = negotiate_aiwire_handshake(
            hello["aiwire_handshake"],
            level=int(hello.get("aiwire_level", AI_WIRE_DEFAULT_LEVEL)),
            allow_fallback=bool(hello.get("allow_aiwire_fallback", True)),
        )
        negotiation_payload = negotiation.to_dict()
        if not negotiation.accepted:
            _write_frame(
                conn,
                _json_bytes(
                    {
                        "accepted": False,
                        "codec": requested_codec,
                        "requested_codec": requested_codec,
                        "aiwire_negotiation": negotiation_payload,
                    }
                ),
            )
            return
        codec = negotiation.codec

    _write_frame(
        conn,
        _json_bytes(
            {
                "accepted": True,
                "codec": codec,
                "requested_codec": requested_codec,
                "aiwire_negotiation": negotiation_payload,
            }
        ),
    )

    aura: ProductionHybridCompressor | None = None
    if codec == "aura":
        aura = _make_aura(cache_dir)
    brio_decoder: BrioDecoder | None = BrioDecoder() if codec == "brio" else None
    aiwire_decoder: AIWireSessionDecoder | None = (
        AIWireSessionDecoder() if codec == "aiwire" else None
    )

    restored_frames: list[bytes] = []
    compressed_bytes = 0
    decompress_ns = 0
    frame_count = 0

    while True:
        payload = _read_frame(conn)
        if not payload:
            break
        compressed_bytes += len(payload)
        frame_count += 1
        start = time.perf_counter_ns()
        if codec == "raw":
            restored = payload
        elif codec == "aura":
            assert aura is not None
            decoded = aura.decompress(payload)
            restored = decoded.encode("utf-8") if isinstance(decoded, str) else bytes(decoded)
        elif codec == "brio":
            assert brio_decoder is not None
            restored = brio_decoder.decompress(payload).text.encode("utf-8")
        elif codec == "zlib":
            restored = zlib.decompress(payload)
        elif codec == "aiwire":
            assert aiwire_decoder is not None
            restored = aiwire_decoder.decompress_frame(payload)
        else:
            raise ValueError(f"unsupported codec: {codec}")
        decompress_ns += time.perf_counter_ns() - start
        restored_frames.append(restored)

    sha = _sha_update_frames(restored_frames)
    response = {
        "codec": requested_codec,
        "negotiated_codec": codec,
        "frames": frame_count,
        "compressed_bytes": compressed_bytes,
        "restored_bytes": sum(len(frame) for frame in restored_frames),
        "server_decompress_ms": decompress_ns / 1_000_000,
        "sha256": sha,
        "verified": sha == expected_sha,
        "aiwire_negotiation": negotiation_payload,
    }
    _write_frame(conn, _json_bytes(response))


def run_server(args: argparse.Namespace) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((args.host, args.port))
        server.listen(8)
        for _ in range(args.runs):
            conn, _addr = server.accept()
            with conn:
                _configure_low_latency(conn)
                server_once(conn, args.cache_dir)


def run_client(args: argparse.Namespace) -> None:
    messages = build_ai_messages(args.messages, args.seed)
    frames = batch_messages(messages, args.batch_size)
    raw_bytes = sum(len(frame) for frame in frames)
    raw_sha = _sha_update_frames(frames)

    results = []
    for codec in args.codecs.split(","):
        codec = codec.strip()
        hello = {
            "codec": codec,
            "frames": len(frames),
            "expected_sha256": raw_sha,
            "raw_bytes": raw_bytes,
        }
        if codec == "aiwire":
            hello.update(
                {
                    "aiwire_level": args.aiwire_level,
                    "allow_aiwire_fallback": args.allow_aiwire_fallback,
                    "aiwire_handshake": build_aiwire_handshake(
                        level=args.aiwire_level,
                        fallback_codecs=("zlib", "raw") if args.allow_aiwire_fallback else (),
                    ).to_dict(),
                }
            )

        handshake_start = time.perf_counter_ns()
        with socket.create_connection((args.host, args.port), timeout=args.timeout) as sock:
            _configure_low_latency(sock)
            _write_frame(sock, _json_bytes(hello))
            ack = json.loads(_read_frame(sock))
            handshake_ms = (time.perf_counter_ns() - handshake_start) / 1_000_000
            if not ack.get("accepted"):
                raise RuntimeError(f"{codec} negotiation failed: {ack}")

            negotiated_codec = ack["codec"]
            encoded, encode_stats = encode_frames(
                negotiated_codec,
                frames,
                args.cache_dir,
                args.aiwire_level,
            )
            compressed_bytes = sum(len(frame) for frame in encoded)

            start = time.perf_counter_ns()
            for payload in encoded:
                _write_frame(sock, payload)
            _write_frame(sock, b"")
            response = json.loads(_read_frame(sock))
        total_ms = (time.perf_counter_ns() - start) / 1_000_000

        result = {
            "codec": codec,
            "negotiated_codec": response.get("negotiated_codec", negotiated_codec),
            "batch_size": args.batch_size,
            "messages": args.messages,
            "frames": len(encoded),
            "raw_bytes": raw_bytes,
            "wire_bytes": compressed_bytes,
            "ratio": raw_bytes / compressed_bytes if compressed_bytes else 0,
            "wire_saved_percent": (1 - compressed_bytes / raw_bytes) * 100 if raw_bytes else 0,
            "client_compress_ms": encode_stats["client_compress_ms"],
            "wire_plus_remote_decompress_ms": total_ms,
            "handshake_ms": handshake_ms,
            "server_decompress_ms": response["server_decompress_ms"],
            "verified": response["verified"],
            "method_counts": encode_stats["method_counts"],
            "aiwire_negotiation": ack.get("aiwire_negotiation"),
        }
        if not response["verified"]:
            raise RuntimeError(f"{codec} verification failed: {response}")
        results.append(result)

    print(json.dumps({"results": results}, indent=2, sort_keys=True))
    if args.output:
        Path(args.output).write_text(
            json.dumps({"results": results}, indent=2, sort_keys=True) + "\n"
        )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)

    server = sub.add_parser("server")
    server.add_argument("--host", default="0.0.0.0")
    server.add_argument("--port", type=int, default=8765)
    server.add_argument("--runs", type=int, default=1)
    server.add_argument("--cache-dir", default="/tmp/aura-wire-server-cache")
    server.set_defaults(func=run_server)

    client = sub.add_parser("client")
    client.add_argument("--host", required=True)
    client.add_argument("--port", type=int, default=8765)
    client.add_argument("--messages", type=int, default=480)
    client.add_argument("--batch-size", type=int, default=1)
    client.add_argument("--seed", type=int, default=1729)
    client.add_argument("--codecs", default="raw,aura,aiwire,zlib")
    client.add_argument("--aiwire-level", type=int, default=AI_WIRE_DEFAULT_LEVEL)
    client.add_argument("--allow-aiwire-fallback", action="store_true")
    client.add_argument("--cache-dir", default="/tmp/aura-wire-client-cache")
    client.add_argument("--timeout", type=float, default=60.0)
    client.add_argument("--output")
    client.set_defaults(func=run_client)

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
