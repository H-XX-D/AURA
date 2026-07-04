#!/usr/bin/env python3
"""Tests for the AURA AI-to-AI wire codec."""

import json
import zlib

import pytest

from aura_compression.ai_wire import (
    AI_WIRE_DICTIONARY_FNV1A64,
    AI_WIRE_STATIC_DICTIONARY,
    AIWireSessionDecoder,
    AIWireSessionEncoder,
    aiwire_native_status,
    build_aiwire_handshake,
    compress_ai_wire_frames,
    decompress_ai_wire_frames,
    negotiate_aiwire_handshake,
)


def _agent_frames(count: int = 96) -> list[bytes]:
    frames: list[bytes] = []
    for i in range(count):
        payload = {
            "protocol": "mcp" if i % 2 else "a2a",
            "jsonrpc": "2.0",
            "id": i,
            "method": "tools/call" if i % 2 else "message/send",
            "params": {
                "name": "read_file" if i % 3 else "run_shell",
                "arguments": {
                    "trace_id": f"trace-{i // 4:04d}",
                    "task_id": f"task-{i // 8:04d}",
                    "repository": "aura-bridge",
                    "path": f"services/agent_{i % 7}/handler.py",
                    "query": "latency regression retry budget patch validation",
                    "limit": 20 + i % 5,
                },
            },
            "metadata": {
                "agent": "coder" if i % 4 else "reviewer",
                "confidence": round(0.8 + (i % 9) / 100, 3),
            },
        }
        frames.append(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    return frames


def test_static_dictionary_is_zlib_sized() -> None:
    assert 0 < len(AI_WIRE_STATIC_DICTIONARY) <= 32768
    assert b'"method":"tools/call"' in AI_WIRE_STATIC_DICTIONARY


def test_ai_wire_round_trips_ordered_frames() -> None:
    frames = _agent_frames()
    encoder = AIWireSessionEncoder(level=3)
    decoder = AIWireSessionDecoder()

    restored = [decoder.decompress_frame(encoder.compress_frame(frame)) for frame in frames]

    assert restored == frames
    assert encoder.stats.frames == len(frames)
    assert decoder.stats.frames == len(frames)
    assert encoder.stats.bytes_in == sum(len(frame) for frame in frames)
    assert decoder.stats.bytes_out == encoder.stats.bytes_in


def test_ai_wire_helpers_round_trip_string_frames() -> None:
    frames = [frame.decode("utf-8") for frame in _agent_frames(12)]

    compressed, encode_stats = compress_ai_wire_frames(frames)
    restored, decode_stats = decompress_ai_wire_frames(compressed)

    assert restored == [frame.encode("utf-8") for frame in frames]
    assert encode_stats.frames == 12
    assert decode_stats.frames == 12


def test_ai_wire_stream_beats_stateless_zlib_for_agent_json() -> None:
    frames = _agent_frames()

    compressed, stats = compress_ai_wire_frames(frames, level=3)
    aiwire_size = sum(len(frame) for frame in compressed)
    stateless_zlib_size = sum(len(zlib.compress(frame, 3)) for frame in frames)

    assert aiwire_size < stateless_zlib_size
    assert stats.ratio > 4.0


def test_ai_wire_handshake_accepts_matching_peer() -> None:
    peer = build_aiwire_handshake(level=3)
    negotiation = negotiate_aiwire_handshake(peer.to_dict(), level=3)

    assert negotiation.accepted is True
    assert negotiation.codec == "aiwire"
    assert negotiation.version == 1
    assert negotiation.reason is None


def test_ai_wire_handshake_rejects_dictionary_mismatch_without_fallback() -> None:
    peer = build_aiwire_handshake(level=3).to_dict()
    peer["dictionary_sha256"] = "0" * 64

    negotiation = negotiate_aiwire_handshake(
        peer,
        level=3,
        allow_fallback=False,
    )

    assert negotiation.accepted is False
    assert negotiation.codec == ""
    assert negotiation.reason == "dictionary_sha256_mismatch"


def test_ai_wire_handshake_can_negotiate_fallback() -> None:
    peer = build_aiwire_handshake(level=3, fallback_codecs=("zlib", "raw")).to_dict()
    peer["versions"] = [999]

    negotiation = negotiate_aiwire_handshake(
        peer,
        level=3,
        fallback_codecs=("zlib", "raw"),
        allow_fallback=True,
    )

    assert negotiation.accepted is True
    assert negotiation.codec == "zlib"
    assert negotiation.version is None
    assert negotiation.reason == "no_common_aiwire_version"


def test_native_ai_wire_round_trips_and_interops_when_available() -> None:
    status = aiwire_native_status()
    if not status.available:
        pytest.skip(status.error or "native AIWire backend is not built")

    assert status.dictionary_matches_python is True
    assert status.dictionary_size == len(AI_WIRE_STATIC_DICTIONARY)
    assert status.dictionary_checksum == f"{AI_WIRE_DICTIONARY_FNV1A64:016x}"

    frames = _agent_frames()

    native_encoder = AIWireSessionEncoder(level=3, use_native=True)
    native_decoder = AIWireSessionDecoder(use_native=True)
    native_payloads = [native_encoder.compress_frame(frame) for frame in frames]
    native_restored = [native_decoder.decompress_frame(frame) for frame in native_payloads]

    assert native_encoder.backend == "native"
    assert native_decoder.backend == "native"
    assert native_restored == frames

    python_decoder = AIWireSessionDecoder(use_native=False)
    python_restored = [python_decoder.decompress_frame(frame) for frame in native_payloads]
    assert python_restored == frames

    python_encoder = AIWireSessionEncoder(level=3, use_native=False)
    native_decoder_for_python = AIWireSessionDecoder(use_native=True)
    python_payloads = [python_encoder.compress_frame(frame) for frame in frames]
    restored_from_python = [
        native_decoder_for_python.decompress_frame(frame) for frame in python_payloads
    ]
    assert restored_from_python == frames
