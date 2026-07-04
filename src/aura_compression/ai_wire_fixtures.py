"""Deterministic public AIWire session fixtures.

The fixtures model negotiated AI-to-AI sessions without storing secrets or
private traffic.  They are intended for docs, tests, and interop experiments.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

from .ai_wire import (
    AI_WIRE_DEFAULT_LEVEL,
    AI_WIRE_DICTIONARY_SHA256,
    AI_WIRE_PROTOCOL,
    AI_WIRE_VERSION,
    AIWireSessionTemplates,
    aiwire_session_dictionary_state_sha256,
    aiwire_session_templates_sha256,
    apply_aiwire_session_dictionary_diff,
    apply_aiwire_session_template_update,
    build_aiwire_handshake,
    build_aiwire_session_dictionary_diff,
    build_aiwire_session_resume_hello,
    build_aiwire_session_template_update,
    compress_ai_wire_frames,
    decompress_ai_wire_frames,
    negotiate_aiwire_handshake,
    negotiate_aiwire_session_resume,
    normalize_aiwire_session_templates,
    verify_aiwire_session_dictionary_ack,
    verify_aiwire_session_resume_response,
)
from .ai_wire_messages import (
    build_structured_ai_messages,
    discover_ai_wire_session_templates,
    encode_ai_wire_message,
)

AIWIRE_SESSION_FIXTURE_CORPUS_SCHEMA = "aura.aiwire.fixture_corpus.v1"
AIWIRE_SESSION_FIXTURE_SCHEMA = "aura.aiwire.session_fixture.v1"
PUBLIC_FIXTURE_AUTH_KEY = "aura-aiwire-public-fixture-auth-v1"
DEFAULT_SESSION_COUNT = 2
DEFAULT_EXCHANGES_PER_SESSION = 18
DEFAULT_FIXTURE_SEED = 7201


_INITIAL_SESSION_TEMPLATES: dict[int, str] = {
    128: '{"protocol":"mcp","jsonrpc":"2.0","id":',
    129: '{"protocol":"a2a","jsonrpc":"2.0","id":',
    130: '{"protocol":"openai.responses","trace_id":"',
    131: '{"protocol":"local.agent","schema":"local.agent.',
}

_SESSION_TEMPLATE_ADDITIONS: dict[int, str] = {
    132: '"schema":"local.agent.delta.status.v1","task_id":"',
    133: '"event":"TaskArtifactUpdateEvent","taskId":"',
    134: '"type":"response.output_text.delta","trace_id":"',
    135: '"protocol":"agent.handoff","from":"planner","to":"',
}


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )


def _sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _deterministic_nonce(seed: int, session_id: str, label: str) -> str:
    payload = f"aura.aiwire.fixture:{seed}:{session_id}:{label}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:32]


def _template_entries(
    templates: AIWireSessionTemplates | None,
) -> list[dict[str, object]]:
    entries = []
    for template_id, pattern in normalize_aiwire_session_templates(templates):
        entries.append(
            {
                "template_id": template_id,
                "pattern": pattern,
                "pattern_sha256": _sha256_hex(pattern.encode("utf-8")),
            }
        )
    return entries


def _phase_for_message(message: Mapping[str, Any], index: int) -> str:
    protocol = str(message.get("protocol", "unknown"))
    if protocol == "mcp":
        method = message.get("method")
        return f"mcp.{method}" if method else "mcp.response"
    if protocol == "a2a":
        event = message.get("event")
        method = message.get("method")
        return f"a2a.{event or method or 'response'}"
    if protocol == "openai.responses":
        return f"openai.{message.get('type') or message.get('operation') or 'event'}"
    if protocol == "local.agent":
        return f"local.{message.get('schema', 'event')}"
    if protocol.startswith("agent."):
        return f"{protocol}.{message.get('event', 'event')}"
    if protocol == "memory.write":
        return "memory.write"
    return f"message.{index % 4}"


def _message_event(
    *,
    message: Mapping[str, Any],
    index: int,
    update_message_index: int,
) -> dict[str, object]:
    raw = encode_ai_wire_message(message)
    return {
        "sequence": index + 1,
        "kind": "message",
        "exchange_index": index // 2,
        "direction": "client_to_server" if index % 2 == 0 else "server_to_client",
        "template_epoch": 0 if index < update_message_index else 1,
        "phase": _phase_for_message(message, index),
        "protocol": message.get("protocol", "unknown"),
        "method": message.get("method"),
        "schema": message.get("schema"),
        "type": message.get("type"),
        "raw_bytes": len(raw),
        "raw_sha256": _sha256_hex(raw),
        "message": dict(message),
    }


def _codec_stats(
    messages: list[Mapping[str, Any]],
    session_templates: AIWireSessionTemplates,
) -> dict[str, object]:
    compressed, encode_stats = compress_ai_wire_frames(
        messages,
        level=AI_WIRE_DEFAULT_LEVEL,
        session_templates=session_templates,
        use_native=False,
    )
    restored, decode_stats = decompress_ai_wire_frames(
        compressed,
        session_templates=session_templates,
        use_native=False,
    )
    expected = [encode_ai_wire_message(message) for message in messages]
    if restored != expected:
        raise AssertionError("AIWire fixture messages did not round-trip")

    return {
        "frames": encode_stats.frames,
        "raw_bytes": encode_stats.bytes_in,
        "wire_bytes": encode_stats.bytes_out,
        "ratio": round(encode_stats.ratio, 6),
        "decode_wire_bytes": decode_stats.bytes_in,
        "decode_raw_bytes": decode_stats.bytes_out,
        "wire_payload_sha256": _sha256_hex(b"".join(compressed)),
    }


def _protocol_mix(events: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    counts = Counter(str(event.get("protocol", "unknown")) for event in events)
    return dict(sorted(counts.items()))


def _build_messages(
    *,
    count: int,
    seed: int,
    session_id: str,
) -> list[dict[str, Any]]:
    messages = build_structured_ai_messages(count=count, seed=seed)
    for index, message in enumerate(messages):
        metadata = message.setdefault("fixture_metadata", {})
        metadata.update(
            {
                "synthetic": True,
                "fixture_session_id": session_id,
                "fixture_sequence": index + 1,
            }
        )
    return messages


def build_aiwire_session_fixture(
    *,
    session_id: str = "fixture-session-0001",
    seed: int = DEFAULT_FIXTURE_SEED,
    exchange_count: int = DEFAULT_EXCHANGES_PER_SESSION,
    template_update_at: int | None = None,
) -> dict[str, object]:
    """Build one deterministic AIWire session fixture."""

    if exchange_count <= 0:
        raise ValueError("exchange_count must be positive")

    message_count = exchange_count * 2
    update_exchange = template_update_at if template_update_at is not None else exchange_count // 2
    update_exchange = max(1, min(exchange_count - 1, update_exchange))
    update_message_index = update_exchange * 2
    messages = _build_messages(count=message_count, seed=seed, session_id=session_id)

    initial_templates = dict(_INITIAL_SESSION_TEMPLATES)
    updated_templates = {**initial_templates, **_SESSION_TEMPLATE_ADDITIONS}
    discovered_preview = discover_ai_wire_session_templates(
        messages,
        max_templates=6,
        min_frequency=2,
        starting_template_id=192,
    )

    client_handshake = build_aiwire_handshake(
        level=AI_WIRE_DEFAULT_LEVEL,
        use_native=False,
        session_templates=initial_templates,
        require_session_templates=True,
    )
    server_negotiation = negotiate_aiwire_handshake(
        client_handshake.to_dict(),
        level=AI_WIRE_DEFAULT_LEVEL,
        use_native=False,
        session_templates=initial_templates,
        require_session_templates=True,
        allow_fallback=False,
    )
    if not server_negotiation.accepted:
        raise AssertionError(f"AIWire fixture handshake failed: {server_negotiation.reason}")

    template_update = build_aiwire_session_template_update(
        initial_templates,
        updated_templates,
        epoch=1,
    )
    applied_templates = apply_aiwire_session_template_update(
        initial_templates,
        template_update.to_dict(),
    )
    if dict(applied_templates) != updated_templates:
        raise AssertionError("AIWire fixture template update did not apply")

    dictionary_diff = build_aiwire_session_dictionary_diff(
        initial_templates,
        updated_templates,
        session_id=session_id,
        epoch=0,
        auth_key=PUBLIC_FIXTURE_AUTH_KEY,
        nonce=_deterministic_nonce(seed, session_id, "dictionary-diff"),
    )
    next_templates, dictionary_ack = apply_aiwire_session_dictionary_diff(
        initial_templates,
        dictionary_diff.to_dict(),
        current_epoch=0,
        auth_key=PUBLIC_FIXTURE_AUTH_KEY,
        replay_cache=set(),
        ack_nonce=_deterministic_nonce(seed, session_id, "dictionary-ack"),
    )
    if dict(next_templates) != updated_templates:
        raise AssertionError("AIWire fixture dictionary diff did not apply")
    verify_aiwire_session_dictionary_ack(
        dictionary_diff,
        dictionary_ack.to_dict(),
        auth_key=PUBLIC_FIXTURE_AUTH_KEY,
    )

    next_state_hash = aiwire_session_dictionary_state_sha256(updated_templates, epoch=1)
    resume_hello = build_aiwire_session_resume_hello(
        peer_id=f"fixture-agent-{seed}",
        app_namespace="aura.aiwire.fixture",
        cached_state_hashes=[next_state_hash],
        auth_key=PUBLIC_FIXTURE_AUTH_KEY,
        nonce=_deterministic_nonce(seed, session_id, "resume-hello"),
    )
    resume_response = negotiate_aiwire_session_resume(
        resume_hello.to_dict(),
        available_state_hashes=[next_state_hash],
        auth_key=PUBLIC_FIXTURE_AUTH_KEY,
        nonce=_deterministic_nonce(seed, session_id, "resume-response"),
    )
    verify_aiwire_session_resume_response(
        resume_hello,
        resume_response.to_dict(),
        auth_key=PUBLIC_FIXTURE_AUTH_KEY,
    )

    events = [
        _message_event(
            message=message,
            index=index,
            update_message_index=update_message_index,
        )
        for index, message in enumerate(messages)
    ]
    epoch_zero_messages = messages[:update_message_index]
    epoch_one_messages = messages[update_message_index:]
    epoch_zero_stats = _codec_stats(epoch_zero_messages, initial_templates)
    epoch_one_stats = _codec_stats(epoch_one_messages, updated_templates)
    raw_bytes = sum(int(event["raw_bytes"]) for event in events)

    return {
        "schema": AIWIRE_SESSION_FIXTURE_SCHEMA,
        "protocol": AI_WIRE_PROTOCOL,
        "version": AI_WIRE_VERSION,
        "session_id": session_id,
        "seed": seed,
        "synthetic_public_data": True,
        "exchange_count": exchange_count,
        "message_count": message_count,
        "template_update_after_exchange": update_exchange,
        "static_dictionary_sha256": AI_WIRE_DICTIONARY_SHA256,
        "auth": {
            "mode": "hmac_sha256",
            "key_id": "public-fixture-key",
            "secret_material": "not_included",
        },
        "initial_session_templates": _template_entries(initial_templates),
        "updated_session_templates": _template_entries(updated_templates),
        "template_hashes": {
            "initial": aiwire_session_templates_sha256(initial_templates),
            "updated": aiwire_session_templates_sha256(updated_templates),
        },
        "session_dictionary_state_hashes": {
            "epoch_0": aiwire_session_dictionary_state_sha256(initial_templates, epoch=0),
            "epoch_1": next_state_hash,
        },
        "template_discovery_preview": {
            "source": "discover_ai_wire_session_templates",
            "message_window": {"start": 0, "count": message_count},
            "starting_template_id": 192,
            "used_for_handshake": False,
            "templates": _template_entries(discovered_preview),
        },
        "client_handshake": client_handshake.to_dict(),
        "server_negotiation": server_negotiation.to_dict(),
        "template_update": template_update.to_dict(),
        "dictionary_diff": dictionary_diff.to_dict(),
        "dictionary_ack": dictionary_ack.to_dict(),
        "resume_hello": resume_hello.to_dict(),
        "resume_response": resume_response.to_dict(),
        "events": events,
        "codec_stats_by_epoch": [
            {"template_epoch": 0, **epoch_zero_stats},
            {"template_epoch": 1, **epoch_one_stats},
        ],
        "summary": {
            "raw_bytes": raw_bytes,
            "protocol_mix": _protocol_mix(events),
            "fixture_sha256": _sha256_hex(
                _canonical_json_bytes(
                    {
                        "session_id": session_id,
                        "seed": seed,
                        "messages": messages,
                        "initial_templates": initial_templates,
                        "updated_templates": updated_templates,
                    }
                )
            ),
        },
    }


def build_aiwire_session_fixture_corpus(
    *,
    session_count: int = DEFAULT_SESSION_COUNT,
    exchanges_per_session: int = DEFAULT_EXCHANGES_PER_SESSION,
    seed: int = DEFAULT_FIXTURE_SEED,
) -> dict[str, object]:
    """Build a deterministic public AIWire session fixture corpus."""

    if session_count <= 0:
        raise ValueError("session_count must be positive")
    if exchanges_per_session <= 0:
        raise ValueError("exchanges_per_session must be positive")

    sessions = [
        build_aiwire_session_fixture(
            session_id=f"fixture-session-{index + 1:04d}",
            seed=seed + index * 101,
            exchange_count=exchanges_per_session,
        )
        for index in range(session_count)
    ]
    message_events = [
        event
        for session in sessions
        for event in session["events"]  # type: ignore[index]
        if event.get("kind") == "message"
    ]
    return {
        "schema": AIWIRE_SESSION_FIXTURE_CORPUS_SCHEMA,
        "generated_by": "aura_compression.ai_wire_fixtures",
        "synthetic_public_data": True,
        "seed": seed,
        "session_count": session_count,
        "exchanges_per_session": exchanges_per_session,
        "message_count": len(message_events),
        "static_dictionary_sha256": AI_WIRE_DICTIONARY_SHA256,
        "sessions": sessions,
        "summary": {
            "raw_bytes": sum(int(event["raw_bytes"]) for event in message_events),
            "protocol_mix": _protocol_mix(message_events),
        },
    }


def write_aiwire_session_fixture_corpus(
    path: str | Path,
    corpus: Mapping[str, Any] | None = None,
) -> Path:
    """Write an AIWire fixture corpus as stable, sorted JSON."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = corpus if corpus is not None else build_aiwire_session_fixture_corpus()
    target.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return target


def load_aiwire_session_fixture_corpus(path: str | Path) -> dict[str, object]:
    """Load a saved AIWire fixture corpus."""

    return json.loads(Path(path).read_text(encoding="utf-8"))


__all__ = [
    "AIWIRE_SESSION_FIXTURE_CORPUS_SCHEMA",
    "AIWIRE_SESSION_FIXTURE_SCHEMA",
    "DEFAULT_EXCHANGES_PER_SESSION",
    "DEFAULT_FIXTURE_SEED",
    "DEFAULT_SESSION_COUNT",
    "PUBLIC_FIXTURE_AUTH_KEY",
    "build_aiwire_session_fixture",
    "build_aiwire_session_fixture_corpus",
    "load_aiwire_session_fixture_corpus",
    "write_aiwire_session_fixture_corpus",
]
