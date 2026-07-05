#!/usr/bin/env python3
"""Tests for the AURA AI-to-AI wire codec."""

import zlib

import pytest

from aura_compression.ai_wire import (
    AI_WIRE_CORPUS_METADATA_SCHEMA,
    AI_WIRE_DICTIONARY_FNV1A64,
    AI_WIRE_DICTIONARY_SHA256,
    AI_WIRE_FALLBACK_CODECS,
    AI_WIRE_SYNC_FLUSH_SUFFIX,
    AI_WIRE_STATIC_DICTIONARY,
    AIWireControlLUTEntry,
    AIWireFallbackError,
    AIWireFrameError,
    AIWireSessionDecoder,
    AIWireSessionEncoder,
    AIWireStats,
    aiwire_control_lut_frame_hex,
    aiwire_control_lut_sha256,
    aiwire_native_status,
    aiwire_session_dictionary_state_sha256,
    aiwire_session_templates_sha256,
    apply_aiwire_session_dictionary_diff,
    apply_aiwire_session_template_update,
    build_ai_wire_messages,
    build_aiwire_handshake,
    build_aiwire_session_dictionary_diff,
    build_aiwire_session_resume_hello,
    build_aiwire_session_template_update,
    build_aiwire_system_control_message,
    build_delta_structured_ai_messages,
    build_structured_ai_messages,
    compress_ai_wire_frames,
    decode_aiwire_fallback_frame,
    decode_aiwire_control_lut_frame,
    decode_ai_wire_message,
    decompress_ai_wire_frames,
    discover_ai_wire_session_templates,
    encode_aiwire_control_lut_frame,
    encode_aiwire_fallback_frame,
    encode_ai_wire_message,
    negotiate_aiwire_handshake,
    negotiate_aiwire_session_resume,
    normalize_aiwire_control_lut,
    summarize_ai_wire_corpus,
    verify_aiwire_session_dictionary_ack,
    verify_aiwire_session_resume_response,
    verify_aiwire_system_control_message,
)


def _agent_frames(count: int = 96) -> list[bytes]:
    return build_ai_wire_messages(count=count)


def test_static_dictionary_is_zlib_sized() -> None:
    assert 0 < len(AI_WIRE_STATIC_DICTIONARY) <= 32768
    assert b'"method":"tools/call"' in AI_WIRE_STATIC_DICTIONARY


def test_static_dictionary_identity_is_pinned_for_v1_compatibility() -> None:
    assert len(AI_WIRE_STATIC_DICTIONARY) == 32768
    assert AI_WIRE_DICTIONARY_SHA256 == (
        "f5c9d524606a4cec9c397cb7ae177a8e1ec87f9819c749f6fd0b24a155313117"
    )
    assert f"{AI_WIRE_DICTIONARY_FNV1A64:016x}" == "94dd21718372952e"


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


def test_ai_wire_decoder_rejects_truncated_frame_without_advancing_stats() -> None:
    encoder = AIWireSessionEncoder(level=3, use_native=False)
    decoder = AIWireSessionDecoder(use_native=False)
    frame = encoder.compress_message({"protocol": "mcp", "jsonrpc": "2.0", "id": 1})

    assert frame.endswith(AI_WIRE_SYNC_FLUSH_SUFFIX)
    with pytest.raises(AIWireFrameError, match="truncated"):
        decoder.decompress_frame(frame[:-1])

    assert decoder.interrupted is True
    assert decoder.failed_reason == "AIWire frame is truncated or missing Z_SYNC_FLUSH marker"
    assert decoder.stats.frames == 0
    assert decoder.stats.bytes_in == 0
    assert decoder.stats.bytes_out == 0


def test_ai_wire_decoder_rejects_corrupt_frame_without_advancing_stats() -> None:
    encoder = AIWireSessionEncoder(level=3, use_native=False)
    decoder = AIWireSessionDecoder(use_native=False)
    frame = encoder.compress_message({"protocol": "mcp", "jsonrpc": "2.0", "id": 1})
    corrupt = (b"\xff" * (len(frame) - len(AI_WIRE_SYNC_FLUSH_SUFFIX))) + AI_WIRE_SYNC_FLUSH_SUFFIX

    with pytest.raises(AIWireFrameError, match="decompression failed"):
        decoder.decompress_frame(corrupt)

    assert decoder.interrupted is True
    assert decoder.failed_reason is not None
    assert decoder.stats.frames == 0
    assert decoder.stats.bytes_in == 0
    assert decoder.stats.bytes_out == 0


def test_ai_wire_decoder_requires_fresh_stream_after_frame_error() -> None:
    messages = [
        {"protocol": "mcp", "jsonrpc": "2.0", "id": 1},
        {"protocol": "mcp", "jsonrpc": "2.0", "id": 2},
        {"protocol": "mcp", "jsonrpc": "2.0", "id": 3},
    ]
    encoder = AIWireSessionEncoder(level=3, use_native=False)
    decoder = AIWireSessionDecoder(use_native=False)
    frames = [encoder.compress_message(message) for message in messages]
    corrupt = (b"\xff" * (len(frames[1]) - len(AI_WIRE_SYNC_FLUSH_SUFFIX))) + (
        AI_WIRE_SYNC_FLUSH_SUFFIX
    )

    assert decoder.decompress_message(frames[0]) == messages[0]
    with pytest.raises(AIWireFrameError, match="decompression failed"):
        decoder.decompress_frame(corrupt)
    with pytest.raises(AIWireFrameError, match="fresh handshake required"):
        decoder.decompress_frame(frames[2])

    assert decoder.interrupted is True
    assert decoder.stats.frames == 1
    assert decoder.stats.bytes_out == len(encode_ai_wire_message(messages[0]))

    fresh_encoder = AIWireSessionEncoder(level=3, use_native=False)
    fresh_decoder = AIWireSessionDecoder(use_native=False)
    fresh_frame = fresh_encoder.compress_message(messages[2])
    assert fresh_decoder.decompress_message(fresh_frame) == messages[2]


def test_ai_wire_helpers_round_trip_string_frames() -> None:
    frames = [frame.decode("utf-8") for frame in _agent_frames(12)]

    compressed, encode_stats = compress_ai_wire_frames(frames)
    restored, decode_stats = decompress_ai_wire_frames(compressed)

    assert restored == [frame.encode("utf-8") for frame in frames]
    assert encode_stats.frames == 12
    assert decode_stats.frames == 12


def test_ai_wire_stats_as_dict_has_stable_benchmark_schema() -> None:
    stats = AIWireStats(frames=4, bytes_in=1000, bytes_out=250)

    assert stats.as_dict() == {
        "frames": 4,
        "bytes_in": 1000,
        "bytes_out": 250,
        "ratio": 4.0,
        "average_bytes_in": 250.0,
        "average_bytes_out": 62.5,
    }
    assert tuple(stats.as_dict()) == (
        "frames",
        "bytes_in",
        "bytes_out",
        "ratio",
        "average_bytes_in",
        "average_bytes_out",
    )


def test_ai_wire_stats_as_dict_handles_empty_sessions() -> None:
    assert AIWireStats(frames=0, bytes_in=0, bytes_out=0).as_dict() == {
        "frames": 0,
        "bytes_in": 0,
        "bytes_out": 0,
        "ratio": 0.0,
        "average_bytes_in": 0.0,
        "average_bytes_out": 0.0,
    }


def test_ai_wire_round_trips_structured_messages() -> None:
    messages = build_structured_ai_messages(48, seed=9001)

    compressed, encode_stats = compress_ai_wire_frames(messages)
    restored, decode_stats = decompress_ai_wire_frames(compressed)

    assert restored == [encode_ai_wire_message(message) for message in messages]
    assert [decode_ai_wire_message(frame) for frame in restored] == messages
    assert encode_stats.frames == len(messages)
    assert decode_stats.frames == len(messages)


def test_structured_ai_message_corpus_covers_protocol_families() -> None:
    messages = build_structured_ai_messages(180, seed=9002)
    protocols = {message["protocol"] for message in messages}
    methods = {message.get("method") for message in messages if message.get("method")}
    event_types = {message.get("type") for message in messages if message.get("type")}
    schemas = {message.get("schema") for message in messages if message.get("schema")}

    assert {
        "openai.responses",
        "mcp",
        "a2a",
        "local.agent",
        "agent.trace",
        "agent.handoff",
        "memory.write",
        "agent.review",
        "agent.final",
    }.issubset(protocols)
    assert {
        "initialize",
        "tools/list",
        "tools/call",
        "resources/read",
        "prompts/get",
        "sampling/createMessage",
        "message/send",
        "message/stream",
        "tasks/get",
    }.issubset(methods)
    assert {
        "function_call_output",
        "response.completed",
        "response.output_item.done",
        "response.output_text.delta",
    }.issubset(event_types)
    assert {
        "local.agent.broker.envelope.v1",
        "local.agent.session.handshake.v1",
        "local.agent.delta.status.v1",
        "local.agent.delta.tool_result.v1",
        "local.agent.route_hint.v1",
    }.issubset(schemas)


def test_structured_ai_message_corpus_metadata_is_opt_in() -> None:
    default_messages = build_structured_ai_messages(8, seed=9003)
    marked_messages = build_structured_ai_messages(
        8,
        seed=9003,
        include_corpus_metadata=True,
    )

    assert all("corpus_metadata" not in message for message in default_messages)
    assert [message["protocol"] for message in marked_messages] == [
        message["protocol"] for message in default_messages
    ]
    for sequence, message in enumerate(marked_messages, start=1):
        metadata = message["corpus_metadata"]
        assert metadata == {
            "schema": AI_WIRE_CORPUS_METADATA_SCHEMA,
            "corpus": "structured",
            "seed": 9003,
            "sequence": sequence,
            "synthetic": True,
            "public_safe": True,
        }


def test_delta_structured_ai_message_corpus_keeps_session_shape_stable() -> None:
    messages = build_delta_structured_ai_messages(80, seed=5150)

    assert len(messages) == 80
    assert {message["session"]["id"] for message in messages} == {"delta-session-5150"}
    assert {message["session"]["template_epoch"] for message in messages} == {1}
    assert {message["delta_profile"]["task_id"] for message in messages} == {"delta-task-5150"}
    assert {message["delta_profile"]["changed_value"] for message in messages}.issuperset(
        {"argument", "artifact", "route", "status", "token", "trace"}
    )
    assert {message["protocol"] for message in messages}.issuperset(
        {"a2a", "agent.trace", "local.agent", "mcp", "openai.responses"}
    )


def test_delta_structured_ai_message_corpus_metadata_is_opt_in() -> None:
    default_messages = build_delta_structured_ai_messages(12, seed=5151)
    marked_messages = build_delta_structured_ai_messages(
        12,
        seed=5151,
        include_corpus_metadata=True,
    )

    assert all("corpus_metadata" not in message for message in default_messages)
    assert all(message["corpus_metadata"]["corpus"] == "delta" for message in marked_messages)
    assert all(message["corpus_metadata"]["public_safe"] is True for message in marked_messages)
    assert [message["delta_profile"] for message in marked_messages] == [
        message["delta_profile"] for message in default_messages
    ]


def test_delta_structured_ai_message_corpus_round_trips_and_discovers_templates() -> None:
    messages = build_delta_structured_ai_messages(120, seed=6161)
    raw_frames = [encode_ai_wire_message(message) for message in messages]

    discovered_templates = discover_ai_wire_session_templates(
        messages,
        max_templates=6,
        min_frequency=4,
        starting_template_id=192,
    )
    compressed, encode_stats = compress_ai_wire_frames(messages, level=3, use_native=False)
    restored, decode_stats = decompress_ai_wire_frames(compressed, use_native=False)

    assert restored == raw_frames
    assert discovered_templates
    assert encode_stats.frames == len(messages)
    assert decode_stats.frames == len(messages)
    assert encode_stats.ratio > 5.0


def test_ai_wire_corpus_summary_tracks_size_keys_and_protocol_mix() -> None:
    messages = build_structured_ai_messages(60, seed=6262)
    raw_lengths = [len(encode_ai_wire_message(message)) for message in messages]

    summary = summarize_ai_wire_corpus(messages)
    encoded_summary = summarize_ai_wire_corpus(
        [encode_ai_wire_message(message) for message in messages]
    )

    assert summary["message_count"] == 60
    assert summary["json_message_count"] == 60
    assert summary["non_json_message_count"] == 0
    assert summary["total_bytes"] == sum(raw_lengths)
    assert summary["average_frame_bytes"] == pytest.approx(sum(raw_lengths) / len(raw_lengths))
    assert summary["min_frame_bytes"] == min(raw_lengths)
    assert summary["max_frame_bytes"] == max(raw_lengths)
    assert len(summary["corpus_sha256"]) == 64
    assert summary["protocol_mix"]["mcp"] > 0
    assert summary["protocol_mix"]["openai.responses"] > 0
    assert summary["top_level_key_counts"]["protocol"] == 60
    assert summary["nested_key_counts"]["trace_id"] > 0
    assert encoded_summary["protocol_mix"] == summary["protocol_mix"]
    assert encoded_summary["corpus_sha256"] == summary["corpus_sha256"]


def test_delta_ai_wire_corpus_summary_tracks_changed_value_mix() -> None:
    messages = build_delta_structured_ai_messages(80, seed=5150)
    summary = summarize_ai_wire_corpus(messages)

    assert summary["message_count"] == 80
    assert summary["protocol_mix"] == {
        "a2a": 16,
        "agent.trace": 8,
        "local.agent": 24,
        "mcp": 16,
        "openai.responses": 16,
    }
    assert summary["delta_changed_value_mix"] == {
        "argument": 16,
        "artifact": 16,
        "route": 8,
        "status": 24,
        "token": 8,
        "trace": 8,
    }
    assert summary["top_level_key_counts"]["delta_profile"] == 80
    assert summary["nested_key_counts"]["session_id"] >= 80


def test_ai_wire_session_message_api_decodes_json() -> None:
    message = build_structured_ai_messages(1)[0]

    with AIWireSessionEncoder(level=3) as encoder, AIWireSessionDecoder() as decoder:
        payload = encoder.compress_message(message)
        restored = decoder.decompress_message(payload)

    assert restored == message
    assert encoder.stats.frames == 1
    assert decoder.stats.frames == 1


def test_ai_wire_stream_beats_stateless_zlib_for_agent_json() -> None:
    frames = _agent_frames()

    compressed, stats = compress_ai_wire_frames(frames, level=3)
    aiwire_size = sum(len(frame) for frame in compressed)
    stateless_zlib_size = sum(len(zlib.compress(frame, 3)) for frame in frames)

    assert aiwire_size < stateless_zlib_size
    assert stats.ratio > 4.0


def test_ai_wire_high_volume_structured_stream_stays_compact() -> None:
    messages = build_structured_ai_messages(1024, seed=44)
    raw_frames = [encode_ai_wire_message(message) for message in messages]

    compressed, encode_stats = compress_ai_wire_frames(messages, level=3)
    restored, decode_stats = decompress_ai_wire_frames(compressed)
    aiwire_size = sum(len(frame) for frame in compressed)
    stateless_zlib_size = sum(len(zlib.compress(frame, 3)) for frame in raw_frames)

    assert restored == raw_frames
    assert aiwire_size < stateless_zlib_size
    assert encode_stats.frames == len(messages)
    assert decode_stats.frames == len(messages)
    assert encode_stats.average_bytes_in > encode_stats.average_bytes_out
    assert encode_stats.ratio > 4.0


def test_ai_wire_handshake_accepts_matching_peer() -> None:
    peer = build_aiwire_handshake(level=3)
    negotiation = negotiate_aiwire_handshake(peer.to_dict(), level=3)

    assert negotiation.accepted is True
    assert negotiation.codec == "aiwire"
    assert negotiation.version == 1
    assert negotiation.reason is None


def test_ai_wire_handshake_accepts_forced_session_templates() -> None:
    session_templates = {
        128: '{"protocol":"mcp","jsonrpc":"2.0","id":{0},"method":"tools/call"',
        129: '"trace_id":"{0}","task_id":"{1}","metadata":{2}',
    }
    peer = build_aiwire_handshake(
        level=3,
        session_templates=session_templates,
        require_session_templates=True,
    )

    negotiation = negotiate_aiwire_handshake(
        peer.to_dict(),
        level=3,
        session_templates=dict(reversed(list(session_templates.items()))),
        require_session_templates=True,
        allow_fallback=False,
    )

    assert negotiation.accepted is True
    assert negotiation.codec == "aiwire"
    assert negotiation.server_handshake.session_template_count == 2
    assert negotiation.server_handshake.session_template_sha256 == aiwire_session_templates_sha256(
        session_templates
    )


def test_ai_wire_handshake_rejects_session_template_mismatch() -> None:
    peer = build_aiwire_handshake(
        level=3,
        session_templates={128: "agent {0} calls tool {1}"},
        require_session_templates=True,
    )

    negotiation = negotiate_aiwire_handshake(
        peer.to_dict(),
        level=3,
        session_templates={128: "agent {0} calls different tool {1}"},
        require_session_templates=True,
        allow_fallback=False,
    )

    assert negotiation.accepted is False
    assert negotiation.codec == ""
    assert negotiation.reason == "session_template_sha256_mismatch"


def test_ai_wire_handshake_accepts_matching_control_lut() -> None:
    control_lut = [
        AIWireControlLUTEntry(0x0010, "heartbeat", "aura.aiwire.heartbeat.v1"),
        AIWireControlLUTEntry(0x0011, "route_status", "aura.aiwire.route_status.v1"),
    ]
    peer = build_aiwire_handshake(
        level=3,
        control_lut=control_lut,
        control_lut_epoch=2,
        require_control_lut=True,
    )

    negotiation = negotiate_aiwire_handshake(
        peer.to_dict(),
        level=3,
        control_lut=list(reversed(control_lut)),
        control_lut_epoch=2,
        require_control_lut=True,
        allow_fallback=False,
    )

    assert negotiation.accepted is True
    assert negotiation.codec == "aiwire"
    assert peer.control_lut_sha256 == aiwire_control_lut_sha256(control_lut)
    assert negotiation.server_handshake.control_lut_count == 2
    assert negotiation.server_handshake.control_lut_epoch == 2


def test_ai_wire_handshake_rejects_control_lut_mismatch() -> None:
    peer = build_aiwire_handshake(
        control_lut=[AIWireControlLUTEntry(0x0010, "heartbeat")],
        require_control_lut=True,
    )

    negotiation = negotiate_aiwire_handshake(
        peer.to_dict(),
        control_lut=[AIWireControlLUTEntry(0x0010, "different_heartbeat")],
        require_control_lut=True,
        allow_fallback=False,
    )

    assert negotiation.accepted is False
    assert negotiation.reason == "control_lut_sha256_mismatch"


def test_ai_wire_control_lut_rejects_mission_critical_entries() -> None:
    with pytest.raises(Exception, match="mission-critical"):
        normalize_aiwire_control_lut(
            [
                {
                    "code": "0xc001",
                    "meaning": "emergency_stop",
                    "criticality": "mission_critical",
                }
            ]
        )


def test_ai_wire_control_lut_frame_round_trips_bytes_and_hex() -> None:
    control_lut = [
        AIWireControlLUTEntry(0x0010, "heartbeat", "aura.aiwire.heartbeat.v1"),
        AIWireControlLUTEntry(0x0011, "route_status", "aura.aiwire.route_status.v1"),
    ]

    frame = encode_aiwire_control_lut_frame(
        control_lut,
        meaning="route_status",
        payload={"queue_depth": 7, "route": "edge-a"},
    )
    restored = decode_aiwire_control_lut_frame(control_lut, frame)
    restored_from_hex = decode_aiwire_control_lut_frame(
        control_lut,
        aiwire_control_lut_frame_hex(frame),
    )

    assert frame[:2] == b"\x00\x11"
    assert restored.meaning == "route_status"
    assert restored.payload == {"queue_depth": 7, "route": "edge-a"}
    assert restored.to_dict()["code"] == "0x0011"
    assert restored_from_hex == restored


def test_ai_wire_control_lut_frame_supports_empty_payload() -> None:
    control_lut = [AIWireControlLUTEntry(0x0010, "heartbeat")]

    frame = encode_aiwire_control_lut_frame(control_lut, code="0x0010")
    restored = decode_aiwire_control_lut_frame(control_lut, "0x0010")

    assert frame == b"\x00\x10"
    assert restored.meaning == "heartbeat"
    assert restored.payload == {}


def test_ai_wire_control_lut_frame_rejects_unknown_code_and_bad_payload() -> None:
    control_lut = [AIWireControlLUTEntry(0x0010, "heartbeat")]

    with pytest.raises(Exception, match="unknown control LUT code"):
        decode_aiwire_control_lut_frame(control_lut, b"\x00\x11")

    with pytest.raises(Exception, match="payload must decode to a mapping"):
        decode_aiwire_control_lut_frame(control_lut, b"\x00\x10[]")

    with pytest.raises(Exception, match="provide exactly one"):
        encode_aiwire_control_lut_frame(control_lut, meaning="heartbeat", code=0x0010)


def test_ai_wire_system_control_message_authenticates_and_fails_closed() -> None:
    message = build_aiwire_system_control_message(
        control_type="emergency_stop",
        session_id="session-1",
        epoch=3,
        sequence=9,
        payload={"reason": "operator_stop"},
        auth_key=b"critical-secret",
        nonce="a" * 32,
    )

    restored = verify_aiwire_system_control_message(
        message.to_dict(),
        auth_key=b"critical-secret",
    )
    assert restored.control_type == "emergency_stop"
    assert restored.payload == {"reason": "operator_stop"}

    tampered = message.to_dict()
    tampered["payload"] = {"reason": "changed"}
    with pytest.raises(Exception, match="auth tag mismatch"):
        verify_aiwire_system_control_message(tampered, auth_key=b"critical-secret")

    unknown = message.to_dict()
    unknown["control_type"] = "experimental_critical_action"
    with pytest.raises(Exception, match="unknown mission-critical"):
        verify_aiwire_system_control_message(unknown, auth_key=b"critical-secret")


def test_ai_wire_session_template_update_signal_applies_delta() -> None:
    current_templates = {
        128: "agent {0} calls tool {1}",
        129: "tool {0} returned result {1}",
    }
    next_templates = {
        129: "tool {0} returned structured result {1}",
        130: "handoff from {0} to {1}: {2}",
    }

    update = build_aiwire_session_template_update(
        current_templates,
        next_templates,
        epoch=7,
    )
    restored = apply_aiwire_session_template_update(current_templates, update.to_dict())

    assert dict(restored) == next_templates
    assert update.previous_sha256 == aiwire_session_templates_sha256(current_templates)
    assert update.next_sha256 == aiwire_session_templates_sha256(next_templates)
    assert update.add_or_update == (
        (129, "tool {0} returned structured result {1}"),
        (130, "handoff from {0} to {1}: {2}"),
    )
    assert update.remove == (128,)
    assert update.epoch == 7
    assert update.requires_session_reset is True


def test_ai_wire_session_template_update_rejects_wrong_base() -> None:
    update = build_aiwire_session_template_update(
        {128: "agent {0} calls tool {1}"},
        {128: "agent {0} calls tool {1}", 129: "trace {0} status {1}"},
    )

    with pytest.raises(Exception, match="previous hash mismatch"):
        apply_aiwire_session_template_update({128: "different base {0}"}, update)


def test_ai_wire_session_dictionary_diff_requires_ack_before_use() -> None:
    current_templates = {128: "agent {0} calls tool {1}"}
    discovered_templates = {
        128: "agent {0} calls tool {1}",
        129: "task {0} status {1} tokens {2}",
    }
    auth_key = b"session-secret"

    diff = build_aiwire_session_dictionary_diff(
        current_templates,
        discovered_templates,
        session_id="session-1",
        epoch=2,
        auth_key=auth_key,
        nonce="0" * 32,
    )
    next_templates, ack = apply_aiwire_session_dictionary_diff(
        current_templates,
        diff.to_dict(),
        current_epoch=2,
        auth_key=auth_key,
    )

    verify_aiwire_session_dictionary_ack(diff, ack.to_dict(), auth_key=auth_key)
    assert dict(next_templates) == discovered_templates
    assert diff.previous_state_hash == aiwire_session_dictionary_state_sha256(
        current_templates,
        epoch=2,
    )
    assert diff.next_state_hash == aiwire_session_dictionary_state_sha256(
        discovered_templates,
        epoch=3,
    )
    assert ack.accepted is True
    assert ack.state_hash == diff.next_state_hash


def test_ai_wire_session_dictionary_diff_rejects_template_overwrite() -> None:
    with pytest.raises(Exception, match="already has a different shape"):
        build_aiwire_session_dictionary_diff(
            {128: "agent {0} calls tool {1}"},
            {128: "agent {0} calls different tool {1}"},
            session_id="session-1",
        )


def test_ai_wire_session_dictionary_diff_rejects_wrong_base_hash() -> None:
    diff = build_aiwire_session_dictionary_diff(
        {128: "agent {0} calls tool {1}"},
        {129: "task {0} status {1}"},
        session_id="session-1",
        epoch=4,
    )

    with pytest.raises(Exception, match="previous state hash mismatch"):
        apply_aiwire_session_dictionary_diff(
            {128: "different base {0}"},
            diff,
            current_epoch=4,
        )


def test_ai_wire_session_dictionary_diff_rejects_tampered_auth() -> None:
    diff = build_aiwire_session_dictionary_diff(
        {},
        {128: "task {0} status {1}"},
        session_id="session-1",
        auth_key=b"session-secret",
    ).to_dict()
    diff["additions"] = [
        {
            "template_id": 128,
            "pattern": "task {0} status {1} with tampering",
            "pattern_sha256": diff["additions"][0]["pattern_sha256"],  # type: ignore[index]
        }
    ]

    with pytest.raises(Exception, match="diff"):
        apply_aiwire_session_dictionary_diff({}, diff, auth_key=b"session-secret")


def test_ai_wire_session_dictionary_diff_rejects_replay() -> None:
    replay_cache: set[str] = set()
    diff = build_aiwire_session_dictionary_diff(
        {},
        {128: "task {0} status {1}"},
        session_id="session-1",
    )
    apply_aiwire_session_dictionary_diff({}, diff, replay_cache=replay_cache)

    with pytest.raises(Exception, match="replay"):
        apply_aiwire_session_dictionary_diff({}, diff, replay_cache=replay_cache)


def test_ai_wire_session_resume_handshake_accepts_known_state_hash() -> None:
    state_hash = aiwire_session_dictionary_state_sha256(
        {128: "task {0} status {1}"},
        epoch=1,
    )
    hello = build_aiwire_session_resume_hello(
        peer_id="agent-a",
        app_namespace="bench",
        cached_state_hashes=[state_hash],
        auth_key=b"resume-secret",
        nonce="1" * 32,
    )

    response = negotiate_aiwire_session_resume(
        hello.to_dict(),
        available_state_hashes=[state_hash],
        auth_key=b"resume-secret",
        nonce="2" * 32,
    )

    verify_aiwire_session_resume_response(hello, response.to_dict(), auth_key=b"resume-secret")
    assert response.accepted is True
    assert response.resume_state_hash == state_hash


def test_ai_wire_session_resume_handshake_rejects_unknown_state_hash() -> None:
    offered = aiwire_session_dictionary_state_sha256({128: "offered {0}"}, epoch=1)
    available = aiwire_session_dictionary_state_sha256({129: "available {0}"}, epoch=1)
    hello = build_aiwire_session_resume_hello(
        peer_id="agent-a",
        cached_state_hashes=[offered],
    )

    response = negotiate_aiwire_session_resume(
        hello,
        available_state_hashes=[available],
    )

    assert response.accepted is False
    assert response.reason == "no_shared_session_dictionary"
    with pytest.raises(Exception, match="no_shared_session_dictionary"):
        verify_aiwire_session_resume_response(hello, response)


def test_ai_wire_session_templates_round_trip_on_python_backend() -> None:
    session_templates = {
        128: '{"protocol":"agent.trace","event":"plan.created","trace_id":"{0}"',
        129: '"objective":"Reduce {0} tail latency without increasing error budget burn."',
    }
    messages = build_structured_ai_messages(96, seed=303)
    raw_frames = [encode_ai_wire_message(message) for message in messages]

    compressed, encode_stats = compress_ai_wire_frames(
        messages,
        session_templates=session_templates,
        use_native=False,
    )
    restored, decode_stats = decompress_ai_wire_frames(
        compressed,
        session_templates=session_templates,
        use_native=False,
    )

    assert restored == raw_frames
    assert encode_stats.frames == len(messages)
    assert decode_stats.frames == len(messages)
    assert encode_stats.ratio > 4.0


def test_ai_wire_session_templates_round_trip_on_native_backend_when_available() -> None:
    status = aiwire_native_status()
    if not status.available:
        pytest.skip(status.error or "native AIWire backend is not built")
    if not status.supports_custom_dictionary:
        pytest.skip("native AIWire backend lacks custom dictionary support")

    session_templates = {
        128: '{"protocol":"mcp","jsonrpc":"2.0","id":{0}',
        129: '"trace_id":"{0}","task_id":"{1}"',
    }
    messages = build_structured_ai_messages(64, seed=515)

    with (
        AIWireSessionEncoder(
            session_templates=session_templates,
            use_native=True,
        ) as encoder,
        AIWireSessionDecoder(
            session_templates=session_templates,
            use_native=True,
        ) as decoder,
    ):
        payloads = [encoder.compress_message(message) for message in messages]
        restored = [decoder.decompress_message(payload) for payload in payloads]

    assert encoder.backend == "native"
    assert decoder.backend == "native"
    assert restored == messages
    assert encoder.stats.ratio > 4.0


def test_ai_wire_discovers_session_templates_from_structured_messages() -> None:
    messages = build_structured_ai_messages(96, seed=404)

    templates = discover_ai_wire_session_templates(messages, max_templates=4)

    assert 0 < len(templates) <= 4
    assert all(128 <= template_id <= 131 for template_id in templates)
    assert all(pattern for pattern in templates.values())


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


def test_ai_wire_handshake_rejects_dictionary_size_mismatch_without_fallback() -> None:
    peer = build_aiwire_handshake(level=3).to_dict()
    peer["dictionary_size"] = len(AI_WIRE_STATIC_DICTIONARY) - 1

    negotiation = negotiate_aiwire_handshake(
        peer,
        level=3,
        allow_fallback=False,
    )

    assert negotiation.accepted is False
    assert negotiation.codec == ""
    assert negotiation.reason == "dictionary_size_mismatch"


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


def test_ai_wire_handshake_can_negotiate_raw_fallback_when_zlib_is_not_common() -> None:
    peer = build_aiwire_handshake(level=3, fallback_codecs=("raw",)).to_dict()
    peer["dictionary_sha256"] = "0" * 64

    negotiation = negotiate_aiwire_handshake(
        peer,
        level=3,
        fallback_codecs=("zlib", "raw"),
        allow_fallback=True,
    )

    assert negotiation.accepted is True
    assert negotiation.codec == "raw"
    assert negotiation.version is None
    assert negotiation.reason == "dictionary_sha256_mismatch"


def test_ai_wire_legacy_dictionary_identity_can_only_use_fallback() -> None:
    peer = build_aiwire_handshake(level=3, fallback_codecs=("zlib", "raw")).to_dict()
    peer["dictionary_sha256"] = "1" * 64
    peer["dictionary_size"] = len(AI_WIRE_STATIC_DICTIONARY) - 128

    negotiation = negotiate_aiwire_handshake(
        peer,
        level=3,
        fallback_codecs=("zlib", "raw"),
        allow_fallback=True,
    )

    assert negotiation.accepted is True
    assert negotiation.codec == "zlib"
    assert negotiation.version is None
    assert negotiation.reason == "dictionary_sha256_mismatch"


def test_ai_wire_session_dictionary_state_hash_tracks_static_dictionary_identity() -> None:
    session_templates = {128: '{"protocol":"mcp","id":{0}'}
    current_state = aiwire_session_dictionary_state_sha256(
        session_templates,
        epoch=2,
        static_dictionary_sha256=AI_WIRE_DICTIONARY_SHA256,
    )
    legacy_state = aiwire_session_dictionary_state_sha256(
        session_templates,
        epoch=2,
        static_dictionary_sha256="2" * 64,
    )

    assert current_state != legacy_state

    hello = build_aiwire_session_resume_hello(
        peer_id="agent-legacy",
        cached_state_hashes=[legacy_state],
        static_dictionary_sha256="2" * 64,
    )
    response = negotiate_aiwire_session_resume(
        hello,
        available_state_hashes=[legacy_state],
        static_dictionary_sha256=AI_WIRE_DICTIONARY_SHA256,
    )

    assert response.accepted is False
    assert response.reason == "static_dictionary_sha256_mismatch"


def test_ai_wire_fallback_frames_round_trip_raw_and_zlib() -> None:
    message = build_structured_ai_messages(1, seed=123)[0]
    canonical = encode_ai_wire_message(message)

    for codec in AI_WIRE_FALLBACK_CODECS:
        frame = encode_aiwire_fallback_frame(codec, message, level=3)
        restored = decode_aiwire_fallback_frame(codec, frame)

        assert restored == canonical
        assert decode_ai_wire_message(restored) == message
        if codec == "raw":
            assert frame == canonical
        else:
            assert frame != canonical


def test_ai_wire_zlib_fallback_rejects_corrupt_and_trailing_data() -> None:
    frame = encode_aiwire_fallback_frame("zlib", {"protocol": "mcp", "id": 1})

    with pytest.raises(AIWireFallbackError, match="decompression failed"):
        decode_aiwire_fallback_frame("zlib", b"not-a-zlib-frame")

    with pytest.raises(AIWireFallbackError, match="unused compressed data"):
        decode_aiwire_fallback_frame("zlib", frame + b"trailing")

    with pytest.raises(AIWireFallbackError, match="unsupported"):
        encode_aiwire_fallback_frame("brotli", {"protocol": "mcp"})

    with pytest.raises(AIWireFallbackError, match="unsupported"):
        build_aiwire_handshake(fallback_codecs=("brotli",))


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
