"""Full system tests covering end-to-end compression, audit logging, and metrics."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from aura_compression.audit import AuditEntry as FileAuditEntry
from aura_compression.audit import reset_audit_logger
from aura_compression.audit_layer import CompressionAuditor, CompressionEvent
from aura_compression.compressor import CompressionMethod, ProductionHybridCompressor
from aura_compression.templates import TemplateLibrary


@pytest.fixture
def template_text() -> tuple[str, int, list[str]]:
    library = TemplateLibrary()
    template_id = 100
    slots = ["advanced observability"]
    text = library.format_template(template_id, slots)
    return text, template_id, slots


def _read_log_lines(log_file: Path) -> list[str]:
    if not log_file.exists():
        return []
    return [line.strip() for line in log_file.read_text().splitlines() if line.strip()]


def _iso_utc(offset: timedelta = timedelta(0)) -> str:
    return (datetime.now(timezone.utc) + offset).isoformat().replace("+00:00", "Z")


def test_full_system_roundtrip_and_audit_logs(tmp_path: Path, template_text: tuple[str, int, list[str]]) -> None:
    reset_audit_logger()
    audit_dir = tmp_path / "audit"
    text, template_id, slots = template_text

    compressor = ProductionHybridCompressor(
        min_compression_size=0,
        enable_audit_logging=True,
        audit_log_directory=str(audit_dir),
        session_id="session-42",
        user_id="user-7",
        enable_aura=False,
    )

    compressed, method, metadata = compressor.compress(text, template_id=template_id, slots=slots)
    decompressed = compressor.decompress(compressed)

    assert decompressed == text
    assert method in {
        CompressionMethod.BINARY_SEMANTIC,
        CompressionMethod.AURA_LITE,
        CompressionMethod.BRIO,
        CompressionMethod.UNCOMPRESSED,
    }

    client_log = audit_dir / "client_delivered.jsonl"
    metadata_log = audit_dir / "metadata_only.jsonl"

    client_lines = _read_log_lines(client_log)
    metadata_lines = _read_log_lines(metadata_log)

    assert client_lines, "client-delivered audit log should contain at least one entry"
    assert metadata_lines, "metadata-only audit log should contain at least one entry"

    last_client_entry = FileAuditEntry.from_json(client_lines[-1])
    assert last_client_entry.metadata["compressed_size"] == metadata["compressed_size"]
    assert last_client_entry.metadata["original_size"] == metadata["original_size"]
    logged_ratio = last_client_entry.metadata.get("ratio", last_client_entry.metadata.get("compression_ratio"))
    assert logged_ratio == pytest.approx(metadata["ratio"])
    assert last_client_entry.integrity_hash is not None

    raw_metadata = json.loads(metadata_lines[-1])
    stored_metadata = raw_metadata.get("metadata", {})
    assert "cr" in stored_metadata and "ratio" not in stored_metadata
    assert stored_metadata["cr"] == pytest.approx(metadata["ratio"])
    assert stored_metadata["cs"] == metadata["compressed_size"]
    assert raw_metadata.get("integrity_hash")


def test_compression_auditor_chain_and_metrics(tmp_path: Path) -> None:
    db_path = tmp_path / "compression_audit.db"
    auditor = CompressionAuditor(db_path=str(db_path))

    first_id = auditor.log_compression(
        event_type=CompressionEvent.COMPRESS_SUCCESS,
        method="binary_semantic",
        original_size=180,
        compressed_size=45,
        latency_ms=1.25,
        data=b"alpha",
        result=b"omega",
        metadata={"ratio": 4.0, "template_id": 10, "fast_path_candidate": True},
    )

    second_id = auditor.log_compression(
        event_type=CompressionEvent.COMPRESS_SUCCESS,
        method="binary_semantic",
        original_size=120,
        compressed_size=40,
        latency_ms=1.10,
        data=b"bravo",
        result=b"delta",
        metadata={"ratio": 3.0, "template_id": 11, "fast_path_candidate": False},
    )

    assert first_id != second_id

    with auditor.db.lock:
        cursor = auditor.db.conn.cursor()
        cursor.execute(
            "SELECT metadata, previous_hash, entry_hash FROM audit_log ORDER BY id ASC"
        )
        rows = cursor.fetchall()

    assert len(rows) == 2
    first_metadata_blob, first_prev_hash, first_entry_hash = rows[0]
    second_metadata_blob, second_prev_hash, second_entry_hash = rows[1]

    first_metadata = json.loads(first_metadata_blob)
    second_metadata = json.loads(second_metadata_blob)

    assert "cr" in first_metadata and "ratio" not in first_metadata
    assert first_metadata["cr"] == pytest.approx(4.0)
    assert first_metadata["tid"] == 10

    assert "cr" in second_metadata and second_metadata["cr"] == pytest.approx(3.0)
    assert second_prev_hash == first_entry_hash
    assert second_entry_hash and first_entry_hash

    start = _iso_utc(timedelta(minutes=-1))
    end = _iso_utc(timedelta(minutes=1))

    metrics = auditor.db.aggregate_metrics(start, end)

    assert "binary_semantic" in metrics
    assert metrics["binary_semantic"]["operations"] == 2
    assert metrics["binary_semantic"]["total_bytes_in"] == 300
    assert metrics["binary_semantic"]["total_bytes_out"] == 85
    assert metrics["binary_semantic"]["avg_ratio"] == pytest.approx((4.0 + 3.0) / 2)

    auditor.close()


def test_full_system_conversation_flow(tmp_path: Path, template_text: tuple[str, int, list[str]]) -> None:
    reset_audit_logger()
    audit_dir = tmp_path / "audit_conversation"
    db_path = tmp_path / "audit_conversation.db"

    compressor = ProductionHybridCompressor(
        min_compression_size=0,
        enable_audit_logging=True,
        audit_log_directory=str(audit_dir),
        session_id="session-convo",
        user_id="user-convo",
        enable_aura=False,
    )

    auditor = CompressionAuditor(db_path=str(db_path))

    user_message = "Can you walk me through the diagnostics flow?"
    text, template_id, slots = template_text
    ai_response = text

    user_payload, user_method, user_metadata = compressor.compress(user_message)
    restored_user = compressor.decompress(user_payload)
    assert restored_user == user_message

    auditor.log_compression(
        event_type=CompressionEvent.COMPRESS_SUCCESS,
        method=user_metadata["method"],
        original_size=user_metadata["original_size"],
        compressed_size=user_metadata["compressed_size"],
        latency_ms=user_metadata.get("latency_ms", 0.0),
        metadata=user_metadata,
    )

    ai_payload, ai_method, ai_metadata = compressor.compress(
        ai_response,
        template_id=template_id,
        slots=slots,
    )
    restored_ai = compressor.decompress(ai_payload)
    assert restored_ai == ai_response
    assert ai_method == CompressionMethod.BINARY_SEMANTIC

    auditor.log_compression(
        event_type=CompressionEvent.COMPRESS_SUCCESS,
        method=ai_metadata["method"],
        original_size=ai_metadata["original_size"],
        compressed_size=ai_metadata["compressed_size"],
        latency_ms=ai_metadata.get("latency_ms", 0.0),
        metadata=ai_metadata,
    )

    client_log = audit_dir / "client_delivered.jsonl"
    lines = _read_log_lines(client_log)
    assert len(lines) >= 2

    parsed_entries = [FileAuditEntry.from_json(line) for line in lines[-2:]]
    for entry in parsed_entries:
        assert entry.integrity_hash
        assert entry.metadata["compressed_size"] >= 0
        # Allow small expansion (1-2 bytes) when no compression benefit
        # This can happen with very short messages where overhead exceeds savings
        assert (entry.metadata["original_size"] >= entry.metadata["compressed_size"] or
                entry.metadata.get("reason") in ["message_too_small", "no_compression_benefit"] or
                entry.metadata["compressed_size"] - entry.metadata["original_size"] <= 2)

    start = _iso_utc(timedelta(minutes=-1))
    end = _iso_utc(timedelta(minutes=1))
    metrics = auditor.db.aggregate_metrics(start, end)
    assert metrics
    assert any(details["operations"] >= 1 for details in metrics.values())

    auditor.close()
