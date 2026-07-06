"""Versioned replay-log records for AIWire benchmark artifacts.

The replay log is an offline capture format. It does not redefine AIWire
transport framing; it records benchmark inputs, negotiations, and result rows
from existing stress outputs in a deterministic JSONL envelope.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

AIWIRE_REPLAY_LOG_SCHEMA = "aura.aiwire.replay_log.v1"

_SETTING_KEYS = (
    "suite",
    "mode",
    "seconds",
    "exchanges",
    "agent_count",
    "codecs",
    "requested_backend",
    "coordinator",
    "fixture_corpus",
    "fixture_session_templates",
    "fixture_variation_profile",
    "participant_count",
    "remote_peer_count",
    "session_shards_per_target",
    "total_replay_sessions",
)

_RESULT_SUMMARY_KEYS = (
    "network_profile",
    "target_label",
    "target_index",
    "session_shard",
    "codec",
    "backend",
    "client_backend",
    "server_backend",
    "client_requested_backend",
    "server_requested_backend",
    "verified",
    "exchanges",
    "deadline_completed_exchanges",
    "deadline_exchanges_per_second",
    "framed_wire_bytes",
    "framed_bytes_per_exchange",
    "framed_wire_saved_percent",
    "roundtrip_ms_p50",
    "roundtrip_ms_p95",
    "roundtrip_ms_p99",
    "client_link_mbps",
    "server_link_mbps",
    "client_one_way_delay_ms",
    "server_one_way_delay_ms",
)


def canonical_json_bytes(value: Any) -> bytes:
    """Return canonical JSON bytes used for replay-log hashes."""

    return json.dumps(
        _json_ready(value),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def sha256_hex(value: bytes) -> str:
    """Return a lowercase SHA-256 hex digest."""

    return hashlib.sha256(value).hexdigest()


def _json_ready(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _json_ready(nested) for key, nested in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    return value


def _copy_keys(
    source: Mapping[str, Any],
    keys: tuple[str, ...],
) -> dict[str, Any]:
    copied: dict[str, Any] = {}
    for key in keys:
        if key in source and source[key] is not None:
            copied[key] = _json_ready(source[key])
    return copied


def _input_kind(payload: Mapping[str, Any]) -> str:
    if payload.get("suite") == "aura-aiwire-realistic-network":
        return "network_suite"
    if payload.get("mode") == "nary_client":
        return "nary_client"
    if "backend_results" in payload:
        return "backend_comparison"
    if "summaries" in payload and "deltas" in payload:
        return "coordinator_comparison"
    if "results" in payload:
        return "stress_client"
    return "aiwire_artifact"


def _record(
    sequence: int,
    record_type: str,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    ready_payload = _json_ready(payload)
    return {
        "schema": AIWIRE_REPLAY_LOG_SCHEMA,
        "sequence": sequence,
        "record_type": record_type,
        "payload_sha256": sha256_hex(canonical_json_bytes(ready_payload)),
        "payload": ready_payload,
    }


def _header_payload(
    benchmark: Mapping[str, Any],
    *,
    source: str = "",
    source_sha256: str = "",
) -> dict[str, Any]:
    results = benchmark.get("results")
    aggregate = benchmark.get("aggregate")
    targets = benchmark.get("targets")
    profiles = benchmark.get("profiles")
    profile_names = []
    if isinstance(profiles, list):
        profile_names = [
            str(profile.get("name", ""))
            for profile in profiles
            if isinstance(profile, Mapping) and profile.get("name")
        ]

    settings = _copy_keys(benchmark, _SETTING_KEYS)
    if profile_names:
        settings["profiles"] = profile_names

    return {
        "input_kind": _input_kind(benchmark),
        "source": source,
        "source_sha256": source_sha256,
        "settings": settings,
        "counts": {
            "results": len(results) if isinstance(results, list) else 0,
            "aggregate": len(aggregate) if isinstance(aggregate, list) else 0,
            "targets": len(targets) if isinstance(targets, list) else 0,
        },
    }


def _fixture_payload(fixture: Mapping[str, Any]) -> dict[str, Any]:
    return dict(_json_ready(fixture))


def _target_payload(index: int, target: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(_json_ready(target))
    payload.setdefault("index", index)
    return payload


def _probe_payload(index: int, probe: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(_json_ready(probe))
    payload.setdefault("index", index)
    return payload


def _aggregate_payload(index: int, row: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(_json_ready(row))
    payload.setdefault("index", index)
    return payload


def _result_payload(index: int, row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "index": index,
        "codec": row.get("codec", ""),
        "network_profile": row.get("network_profile", ""),
        "target_label": row.get("target_label", ""),
        "target_index": row.get("target_index", ""),
        "session_shard": row.get("session_shard", ""),
        "verified": bool(row.get("verified")),
        "summary": _copy_keys(row, _RESULT_SUMMARY_KEYS),
        "row": dict(_json_ready(row)),
    }


def build_replay_records(
    benchmark: Mapping[str, Any],
    *,
    source: str = "",
    source_sha256: str = "",
) -> list[dict[str, Any]]:
    """Build deterministic replay-log records from an AIWire artifact."""

    records: list[dict[str, Any]] = []
    sequence = 0

    records.append(
        _record(
            sequence,
            "header",
            _header_payload(
                benchmark,
                source=source,
                source_sha256=source_sha256,
            ),
        )
    )
    sequence += 1

    fixture = benchmark.get("fixture_replay")
    if isinstance(fixture, Mapping):
        fixture_record = _fixture_payload(fixture)
        records.append(_record(sequence, "fixture_replay", fixture_record))
        sequence += 1

    nary_negotiation = benchmark.get("nary_negotiation")
    if isinstance(nary_negotiation, Mapping):
        negotiation = dict(nary_negotiation)
        records.append(_record(sequence, "nary_negotiation", negotiation))
        sequence += 1

    targets = benchmark.get("targets")
    if isinstance(targets, list):
        for index, target in enumerate(targets, start=1):
            if isinstance(target, Mapping):
                target_record = _target_payload(index, target)
                records.append(_record(sequence, "target", target_record))
                sequence += 1

    probes = benchmark.get("nary_peer_probes")
    if isinstance(probes, list):
        for index, probe in enumerate(probes, start=1):
            if isinstance(probe, Mapping):
                probe_record = _probe_payload(index, probe)
                records.append(_record(sequence, "peer_probe", probe_record))
                sequence += 1

    aggregate = benchmark.get("aggregate")
    if isinstance(aggregate, list):
        for index, row in enumerate(aggregate, start=1):
            if isinstance(row, Mapping):
                records.append(
                    _record(
                        sequence,
                        "aggregate_result",
                        _aggregate_payload(index, row),
                    )
                )
                sequence += 1

    results = benchmark.get("results")
    if isinstance(results, list):
        for index, row in enumerate(results, start=1):
            if isinstance(row, Mapping):
                result_record = _result_payload(index, row)
                records.append(_record(sequence, "result", result_record))
                sequence += 1

    return records


def dumps_replay_log(
    benchmark: Mapping[str, Any],
    *,
    source: str = "",
    source_sha256: str = "",
) -> str:
    """Serialize replay-log records as canonical JSONL."""

    records = build_replay_records(
        benchmark,
        source=source,
        source_sha256=source_sha256,
    )
    return (
        "\n".join(
            json.dumps(
                record,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
            for record in records
        )
        + "\n"
    )


def loads_replay_log(text: str) -> list[dict[str, Any]]:
    """Load and validate replay-log JSONL records."""

    records: list[dict[str, Any]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        expected_sequence = len(records)
        record = json.loads(line)
        if not isinstance(record, dict):
            message = f"record {expected_sequence} is not an object"
            raise ValueError(message)
        if record.get("schema") != AIWIRE_REPLAY_LOG_SCHEMA:
            message = f"record {expected_sequence} has unsupported schema"
            raise ValueError(message)
        if record.get("sequence") != expected_sequence:
            message = f"record {expected_sequence} has a sequence mismatch"
            raise ValueError(message)
        payload = record.get("payload")
        if not isinstance(payload, Mapping):
            message = f"record {expected_sequence} is missing payload"
            raise ValueError(message)
        expected_hash = sha256_hex(canonical_json_bytes(payload))
        if record.get("payload_sha256") != expected_hash:
            message = f"record {expected_sequence} payload hash mismatch"
            raise ValueError(message)
        records.append(record)
    return records
