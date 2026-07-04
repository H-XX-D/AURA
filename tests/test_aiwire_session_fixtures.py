from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Mapping

from aura_compression.ai_wire import (
    apply_aiwire_session_dictionary_diff,
    apply_aiwire_session_template_update,
    compress_ai_wire_frames,
    decompress_ai_wire_frames,
    encode_ai_wire_message,
    negotiate_aiwire_handshake,
    negotiate_aiwire_session_resume,
    verify_aiwire_session_dictionary_ack,
    verify_aiwire_session_resume_response,
)
from aura_compression.ai_wire_fixtures import (
    AIWIRE_SESSION_FIXTURE_CORPUS_SCHEMA,
    PUBLIC_FIXTURE_AUTH_KEY,
    build_aiwire_session_fixture_corpus,
    load_aiwire_session_fixture_corpus,
)

FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "aiwire_sessions"
    / "public_session_corpus_v1.json"
)


def _templates_from_entries(entries: list[Mapping[str, Any]]) -> dict[int, str]:
    return {int(entry["template_id"]): str(entry["pattern"]) for entry in entries}


def test_aiwire_session_fixture_builder_is_deterministic() -> None:
    first = build_aiwire_session_fixture_corpus()
    second = build_aiwire_session_fixture_corpus()

    assert first == second
    assert first["schema"] == AIWIRE_SESSION_FIXTURE_CORPUS_SCHEMA
    assert first["session_count"] == 2
    assert first["message_count"] == 72


def test_saved_aiwire_session_fixture_matches_builder() -> None:
    saved = load_aiwire_session_fixture_corpus(FIXTURE_PATH)
    generated = build_aiwire_session_fixture_corpus()

    assert saved == generated


def test_saved_aiwire_session_fixture_verifies_side_channel_messages() -> None:
    corpus = load_aiwire_session_fixture_corpus(FIXTURE_PATH)

    for session in corpus["sessions"]:
        initial_templates = _templates_from_entries(session["initial_session_templates"])
        updated_templates = _templates_from_entries(session["updated_session_templates"])

        negotiation = negotiate_aiwire_handshake(
            session["client_handshake"],
            use_native=False,
            session_templates=initial_templates,
            require_session_templates=True,
            allow_fallback=False,
        )
        assert negotiation.to_dict() == session["server_negotiation"]
        assert negotiation.accepted is True

        applied_templates = apply_aiwire_session_template_update(
            initial_templates,
            session["template_update"],
        )
        assert dict(applied_templates) == updated_templates

        next_templates, ack = apply_aiwire_session_dictionary_diff(
            initial_templates,
            session["dictionary_diff"],
            current_epoch=0,
            auth_key=PUBLIC_FIXTURE_AUTH_KEY,
            replay_cache=set(),
            ack_nonce=session["dictionary_ack"]["nonce"],
        )
        assert dict(next_templates) == updated_templates
        assert ack.to_dict() == session["dictionary_ack"]
        verify_aiwire_session_dictionary_ack(
            session["dictionary_diff"],
            session["dictionary_ack"],
            auth_key=PUBLIC_FIXTURE_AUTH_KEY,
        )

        resume_response = negotiate_aiwire_session_resume(
            session["resume_hello"],
            available_state_hashes=[session["session_dictionary_state_hashes"]["epoch_1"]],
            auth_key=PUBLIC_FIXTURE_AUTH_KEY,
            nonce=session["resume_response"]["nonce"],
        )
        assert resume_response.to_dict() == session["resume_response"]
        verify_aiwire_session_resume_response(
            session["resume_hello"],
            session["resume_response"],
            auth_key=PUBLIC_FIXTURE_AUTH_KEY,
        )


def test_saved_aiwire_session_fixture_round_trips_message_epochs() -> None:
    corpus = load_aiwire_session_fixture_corpus(FIXTURE_PATH)

    for session in corpus["sessions"]:
        initial_templates = _templates_from_entries(session["initial_session_templates"])
        updated_templates = _templates_from_entries(session["updated_session_templates"])
        messages_by_epoch = {0: [], 1: []}

        for event in session["events"]:
            raw = encode_ai_wire_message(event["message"])
            assert event["kind"] == "message"
            assert event["raw_bytes"] == len(raw)
            assert event["raw_sha256"] == hashlib.sha256(raw).hexdigest()
            messages_by_epoch[int(event["template_epoch"])].append(event["message"])

        for stats in session["codec_stats_by_epoch"]:
            epoch = int(stats["template_epoch"])
            templates = initial_templates if epoch == 0 else updated_templates
            messages = messages_by_epoch[epoch]
            compressed, encode_stats = compress_ai_wire_frames(
                messages,
                session_templates=templates,
                use_native=False,
            )
            restored, decode_stats = decompress_ai_wire_frames(
                compressed,
                session_templates=templates,
                use_native=False,
            )

            assert restored == [encode_ai_wire_message(message) for message in messages]
            assert stats["frames"] == encode_stats.frames == decode_stats.frames
            assert stats["raw_bytes"] == encode_stats.bytes_in == decode_stats.bytes_out
            assert stats["wire_bytes"] == encode_stats.bytes_out == decode_stats.bytes_in
            assert float(stats["ratio"]) > 3.0


def test_aiwire_session_fixture_includes_discovery_preview() -> None:
    corpus = load_aiwire_session_fixture_corpus(FIXTURE_PATH)

    for session in corpus["sessions"]:
        preview = session["template_discovery_preview"]
        assert preview["source"] == "discover_ai_wire_session_templates"
        assert preview["used_for_handshake"] is False
        assert preview["templates"]
        assert all(entry["template_id"] >= 192 for entry in preview["templates"])
