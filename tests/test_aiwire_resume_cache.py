from __future__ import annotations

import json
from pathlib import Path

import pytest

from aura_compression.ai_wire import AIWireHandshakeError
from aura_compression.aiwire_resume_cache import (
    AI_WIRE_RESUME_CACHE_SCHEMA,
    AIWireResumeCache,
)


def test_aiwire_resume_cache_persists_peer_state(tmp_path: Path):
    cache_path = tmp_path / "resume-cache.json"
    templates = {128: "agent {0} calls tool {1}", 129: "task {0} status {1}"}

    cache = AIWireResumeCache(cache_path)
    entry = cache.put_state(
        peer_id="z6",
        app_namespace="cluster",
        session_templates=templates,
        epoch=2,
        label="z6-to-nano",
    )

    payload = json.loads(cache_path.read_text(encoding="utf-8"))
    assert payload["schema"] == AI_WIRE_RESUME_CACHE_SCHEMA
    assert payload["entries"][0]["state_hash"] == entry.state_hash

    reloaded = AIWireResumeCache(cache_path)
    assert reloaded.cached_state_hashes("z6", "cluster") == (entry.state_hash,)
    assert reloaded.get_state(entry.state_hash, peer_id="z6", app_namespace="cluster") == entry


def test_aiwire_resume_cache_authenticated_round_trip(tmp_path: Path):
    auth_key = b"shared-aiwire-session-key"
    client_cache = AIWireResumeCache(tmp_path / "client.json")
    server_cache = AIWireResumeCache(tmp_path / "server.json")
    templates = {128: "agent {0} calls tool {1}", 130: "observation {0} delta {1}"}

    client_entry = client_cache.put_state(
        peer_id="nano-engineer",
        app_namespace="aura-cluster",
        session_templates=templates,
        epoch=3,
    )
    server_cache.put_state(
        peer_id="nano-engineer",
        app_namespace="aura-cluster",
        session_templates=templates,
        epoch=3,
    )

    hello = client_cache.build_resume_hello(
        peer_id="nano-engineer",
        app_namespace="aura-cluster",
        auth_key=auth_key,
        nonce="a" * 32,
    )
    response = server_cache.negotiate_resume(hello, auth_key=auth_key, nonce="b" * 32)

    assert response.accepted is True
    selected = client_cache.verify_resume_response(hello, response, auth_key=auth_key)
    assert selected.state_hash == client_entry.state_hash


def test_aiwire_resume_cache_rejects_unresolvable_selected_state(tmp_path: Path):
    client_cache = AIWireResumeCache(tmp_path / "client.json")
    server_cache = AIWireResumeCache(tmp_path / "server.json")
    templates = {128: "agent {0} calls tool {1}"}

    client_cache.put_state(
        peer_id="nano-engineer",
        app_namespace="aura-cluster",
        session_templates=templates,
        epoch=1,
    )
    server_cache.put_state(
        peer_id="nano-engineer",
        app_namespace="aura-cluster",
        session_templates=templates,
        epoch=1,
    )
    hello = client_cache.build_resume_hello(
        peer_id="nano-engineer",
        app_namespace="aura-cluster",
        nonce="c" * 32,
    )
    response = server_cache.negotiate_resume(hello, nonce="d" * 32)

    empty_client_cache = AIWireResumeCache(tmp_path / "empty-client.json")
    with pytest.raises(AIWireHandshakeError, match="unknown AIWire resume-cache state hash"):
        empty_client_cache.verify_resume_response(hello, response)


def test_aiwire_resume_cache_negotiation_rejects_unknown_peer_state(tmp_path: Path):
    client_cache = AIWireResumeCache(tmp_path / "client.json")
    server_cache = AIWireResumeCache(tmp_path / "server.json")
    client_cache.put_state(
        peer_id="nano-engineer",
        app_namespace="aura-cluster",
        session_templates={128: "agent {0} calls tool {1}"},
        epoch=1,
    )

    hello = client_cache.build_resume_hello(
        peer_id="nano-engineer",
        app_namespace="aura-cluster",
        nonce="e" * 32,
    )
    response = server_cache.negotiate_resume(hello, nonce="f" * 32)

    assert response.accepted is False
    assert response.reason == "no_shared_session_dictionary"
