#!/usr/bin/env python3
"""Tests for the experimental AIWire structural token codec."""

import zlib

import pytest

from aura_compression import (
    AIWireTokenAIWireSessionDecoder,
    AIWireTokenAIWireSessionEncoder,
    AIWireTokenSessionDecoder,
    AIWireTokenSessionEncoder,
    aiwire_native_status,
    build_ai_wire_messages,
    build_structured_ai_messages,
    decode_ai_wire_token_aiwire_frames,
    decode_ai_wire_token_frames,
    encode_ai_wire_message,
    encode_ai_wire_token_aiwire_frames,
    encode_ai_wire_token_frames,
)


def test_ai_wire_token_round_trips_structured_messages() -> None:
    messages = build_structured_ai_messages(128, seed=1201)
    raw_frames = [encode_ai_wire_message(message) for message in messages]

    encoded, encode_stats = encode_ai_wire_token_frames(messages)
    restored, decode_stats = decode_ai_wire_token_frames(encoded)

    assert restored == raw_frames
    assert encode_stats.frames == len(messages)
    assert decode_stats.frames == len(messages)
    assert encode_stats.bytes_out < encode_stats.bytes_in


def test_ai_wire_token_round_trips_raw_non_json_bytes() -> None:
    frame = b"\x00\x01not-json\xff"

    encoder = AIWireTokenSessionEncoder()
    decoder = AIWireTokenSessionDecoder()
    encoded = encoder.encode_frame(frame)
    restored = decoder.decode_frame(encoded)

    assert restored == frame


def test_ai_wire_token_session_string_refs_reduce_repeated_values() -> None:
    message = {
        "protocol": "agent.trace",
        "trace_id": "trace-repeated-0001",
        "task_id": "task-repeated-0001",
        "metadata": {
            "repository": "aura-bridge",
            "path": "services/aura-bridge/src/handler.py",
        },
    }

    encoder = AIWireTokenSessionEncoder()
    first = encoder.encode_frame(message)
    second = encoder.encode_frame(message)

    assert len(second) < len(first)


def test_ai_wire_token_beats_raw_json_on_protocol_corpus() -> None:
    frames = build_ai_wire_messages(512, seed=2202)

    encoded, stats = encode_ai_wire_token_frames(frames)
    token_size = sum(len(frame) for frame in encoded)
    raw_size = sum(len(frame) for frame in frames)
    stateless_zlib_size = sum(len(zlib.compress(frame, 3)) for frame in frames)

    assert token_size < raw_size
    assert stats.ratio > 1.5
    # The token codec is structural and low-state; AIWire deflate may still win
    # on pure bandwidth. This assertion keeps the comparison visible.
    assert token_size > 0
    assert stateless_zlib_size > 0


def test_ai_wire_token_aiwire_round_trips_structured_messages() -> None:
    messages = build_structured_ai_messages(128, seed=3303)
    raw_frames = [encode_ai_wire_message(message) for message in messages]

    encoded, encode_stats = encode_ai_wire_token_aiwire_frames(messages)
    restored, decode_stats = decode_ai_wire_token_aiwire_frames(encoded)

    assert restored == raw_frames
    assert encode_stats == decode_stats
    assert encode_stats.frames == len(messages)
    assert encode_stats.bytes_in == sum(len(frame) for frame in raw_frames)
    assert encode_stats.token_bytes > encode_stats.bytes_out


def test_ai_wire_token_aiwire_compresses_token_stream() -> None:
    frames = build_ai_wire_messages(512, seed=4404)

    token_encoded, token_stats = encode_ai_wire_token_frames(frames)
    layered_encoded, layered_stats = encode_ai_wire_token_aiwire_frames(frames)

    assert sum(len(frame) for frame in layered_encoded) == layered_stats.bytes_out
    assert sum(len(frame) for frame in token_encoded) == token_stats.bytes_out
    assert layered_stats.token_bytes == token_stats.bytes_out
    assert layered_stats.bytes_out < token_stats.bytes_out
    assert layered_stats.ratio > token_stats.ratio


def test_ai_wire_token_uses_native_backend_when_available() -> None:
    status = aiwire_native_status()
    if not status.available or not status.supports_token_codec:
        pytest.skip("native AIWire token codec is not available")

    message = build_structured_ai_messages(1, seed=5505)[0]
    raw = encode_ai_wire_message(message)
    encoder = AIWireTokenSessionEncoder(use_native=True)
    decoder = AIWireTokenSessionDecoder(use_native=True)
    try:
        encoded = encoder.encode_frame(message)
        restored = decoder.decode_frame(encoded)
    finally:
        encoder.close()
        decoder.close()

    assert encoder.backend == "native"
    assert decoder.backend == "native"
    assert restored == raw


def test_ai_wire_token_aiwire_uses_native_pipeline_when_available() -> None:
    status = aiwire_native_status()
    if not status.available or not status.supports_token_aiwire:
        pytest.skip("native AIWire token+AIWire codec is not available")

    messages = build_structured_ai_messages(16, seed=6606)
    raw_frames = [encode_ai_wire_message(message) for message in messages]
    encoder = AIWireTokenAIWireSessionEncoder(use_native=True)
    decoder = AIWireTokenAIWireSessionDecoder(use_native=True)
    try:
        encoded = encoder.encode_frames(messages)
        restored = decoder.decode_frames(encoded)
    finally:
        encoder.close()
        decoder.close()

    assert encoder.backend == "aitoken+native"
    assert decoder.backend == "aitoken+native"
    assert restored == raw_frames
