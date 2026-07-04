"""
Comprehensive test suite for audit_layer module.

Tests cover:
1. AuditEntry creation and serialization
2. Metadata compaction/expansion with aliases
3. AuditDatabase initialization and schema
4. Insert operations with various event types
5. Query filtering (time, event_type, user_id, session_id)
6. Security event logging
7. Aggregate metrics calculation
8. Hash chain integrity verification
9. CompressionAuditor facade functionality
"""

import hashlib
import json
import os
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aura_compression.audit_layer import (
    AuditDatabase,
    AuditEntry,
    AuditLevel,
    CompressionAuditor,
    CompressionEvent,
    compact_metadata,
    expand_metadata,
    register_metadata_aliases,
)


def test_audit_entry_creation():
    """Test AuditEntry dataclass creation and field validation."""
    print("\n=== Test 1: AuditEntry Creation ===")

    entry = AuditEntry(
        timestamp="2024-01-15T10:30:00Z",
        event_id="evt_12345",
        level="INFO",
        event_type="compress_success",
        user_id="user123",
        session_id="sess_abc",
        source_ip="192.0.2.100",
        method="BRIO",
        original_size=1000,
        compressed_size=400,
        compression_ratio=2.5,
        latency_ms=15.5,
        data_hash="abc123",
        result_hash="def456",
        metadata={"key": "value"},
        previous_hash=None,
        entry_hash="hash789",
    )

    assert entry.timestamp == "2024-01-15T10:30:00Z"
    assert entry.event_id == "evt_12345"
    assert entry.level == "INFO"
    assert entry.event_type == "compress_success"
    assert entry.user_id == "user123"
    assert entry.session_id == "sess_abc"
    assert entry.source_ip == "192.0.2.100"
    assert entry.method == "BRIO"
    assert entry.original_size == 1000
    assert entry.compressed_size == 400
    assert entry.compression_ratio == 2.5
    assert entry.latency_ms == 15.5
    assert entry.data_hash == "abc123"
    assert entry.result_hash == "def456"
    assert entry.metadata == {"key": "value"}
    assert entry.previous_hash is None
    assert entry.entry_hash == "hash789"

    print("✅ AuditEntry created successfully with all fields")
    print(f"   - Event: {entry.event_type}, Method: {entry.method}")
    print(f"   - Ratio: {entry.compression_ratio:.2f}x, Latency: {entry.latency_ms}ms")


def test_metadata_compaction_expansion():
    """Test metadata compaction and expansion with aliases."""
    print("\n=== Test 2: Metadata Compaction/Expansion ===")

    # Register some aliases
    register_metadata_aliases(
        {
            "original_size": "os",
            "compressed_size": "cs",
            "compression_method": "cm",
            "file_extension": "ext",
        }
    )

    # Test compaction
    original_metadata = {
        "original_size": 10000,
        "compressed_size": 4000,
        "compression_method": "BRIO_FULL",
        "file_extension": ".txt",
        "unknown_field": "value",
    }

    compacted = compact_metadata(original_metadata)
    print(f"Original metadata: {original_metadata}")
    print(f"Compacted metadata: {compacted}")

    assert compacted["os"] == 10000
    assert compacted["cs"] == 4000
    assert compacted["cm"] == "BRIO_FULL"
    assert compacted["ext"] == ".txt"
    assert compacted["unknown_field"] == "value"  # Unknown fields preserved

    # Test expansion
    expanded = expand_metadata(compacted)
    print(f"Expanded metadata: {expanded}")

    assert expanded["original_size"] == 10000
    assert expanded["compressed_size"] == 4000
    assert expanded["compression_method"] == "BRIO_FULL"
    assert expanded["file_extension"] == ".txt"
    assert expanded["unknown_field"] == "value"

    print("✅ Metadata compaction/expansion working correctly")
    print(f"   - Compacted size: {len(json.dumps(compacted))} bytes")
    print(f"   - Expanded size: {len(json.dumps(expanded))} bytes")


def test_audit_database_initialization():
    """Test AuditDatabase initialization and schema creation."""
    print("\n=== Test 3: AuditDatabase Initialization ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_audit.db")
        db = AuditDatabase(db_path)

        # Verify database file created
        assert os.path.exists(db_path)
        print(f"✅ Database created at: {db_path}")

        # Verify tables exist
        cursor = db.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

        assert "audit_log" in tables
        assert "security_events" in tables
        print(f"✅ Tables created: {tables}")

        # Verify audit_log schema
        cursor.execute("PRAGMA table_info(audit_log)")
        columns = [row[1] for row in cursor.fetchall()]
        expected_columns = [
            "id",
            "timestamp",
            "event_id",
            "level",
            "event_type",
            "user_id",
            "session_id",
            "source_ip",
            "method",
            "original_size",
            "compressed_size",
            "compression_ratio",
            "latency_ms",
            "data_hash",
            "result_hash",
            "metadata",
            "previous_hash",
            "entry_hash",
        ]
        for col in expected_columns:
            assert col in columns, f"Missing column: {col}"

        print(f"✅ audit_log schema verified: {len(columns)} columns")

        # Verify indexes
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = [row[0] for row in cursor.fetchall()]
        print(f"✅ Indexes created: {len(indexes)} indexes")

        db.close()


def test_insert_and_query_operations():
    """Test inserting audit entries and querying with filters."""
    print("\n=== Test 4: Insert and Query Operations ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_audit.db")
        db = AuditDatabase(db_path)

        # Insert multiple entries
        entries = []
        for i in range(5):
            entry = AuditEntry(
                timestamp=f"2024-01-15T10:{i:02d}:00Z",
                event_id=f"evt_{i}",
                level="INFO",
                event_type="compress_success" if i % 2 == 0 else "decompress_success",
                user_id=f"user{i % 2}",
                session_id=f"sess_{i // 2}",
                source_ip="192.0.2.100",
                method="BRIO" if i % 2 == 0 else "BRIO_FULL",
                original_size=1000 * (i + 1),
                compressed_size=400 * (i + 1),
                compression_ratio=2.5,
                latency_ms=10.0 + i,
                data_hash=f"hash_{i}",
                result_hash=f"result_{i}",
                metadata={"index": i},
                previous_hash=None,
                entry_hash=f"entry_{i}",
            )
            db.insert(entry)
            entries.append(entry)

        print(f"✅ Inserted {len(entries)} audit entries")

        # Query all entries
        results = db.query({}, limit=100)
        assert len(results) == 5
        print(f"✅ Query all: {len(results)} entries returned")

        # Note: Results are returned in reverse chronological order (newest first)
        # So results[0] is entry 4, results[4] is entry 0
        first_result = results[-1]  # This should be entry 0

        # Query by event_type
        results = db.query({"event_type": "compress_success"}, limit=100)
        assert len(results) == 3  # entries 0, 2, 4
        print(f"✅ Query by event_type='compress_success': {len(results)} entries")

        # Query by user_id
        results = db.query({"user_id": "user0"}, limit=100)
        assert len(results) == 3  # entries 0, 2, 4
        print(f"✅ Query by user_id='user0': {len(results)} entries")

        # Query by session_id
        results = db.query({"session_id": "sess_1"}, limit=100)
        assert len(results) == 2  # entries 2, 3
        print(f"✅ Query by session_id='sess_1': {len(results)} entries")

        # Query with limit
        results = db.query({}, limit=2)
        assert len(results) == 2
        print(f"✅ Query with limit=2: {len(results)} entries")

        # Query all again to verify metadata expansion
        # Note: Results are returned in reverse chronological order (newest first)
        # So results[0] is entry 4, results[4] is entry 0
        results = db.query({}, limit=100)
        first_result = results[-1]  # This should be entry 0

        # Verify metadata expansion in results
        assert (
            "metadata" in first_result
        ), f"Missing metadata key. Keys: {list(first_result.keys())}"
        metadata = first_result["metadata"]
        assert isinstance(metadata, dict), f"Metadata is {type(metadata)}, not dict: {metadata}"
        assert "index" in metadata, f"Missing index key in metadata: {metadata}"
        assert metadata["index"] == 0, f"Expected index=0, got {metadata['index']}"
        print(f"✅ Metadata properly expanded in query results")

        db.close()


def test_security_event_logging():
    """Test security event insertion and retrieval."""
    print("\n=== Test 5: Security Event Logging ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_audit.db")
        db = AuditDatabase(db_path)

        # Insert security events
        security_events = [
            {
                "timestamp": "2024-01-15T10:00:00Z",
                "event_type": "unauthorized_access",
                "severity": "ERROR",
                "user_id": "attacker123",
                "source_ip": "198.51.100.50",
                "description": "Failed authentication attempt",
                "metadata": {"attempts": 3},
            },
            {
                "timestamp": "2024-01-15T10:05:00Z",
                "event_type": "rate_limit_exceeded",
                "severity": "WARNING",
                "user_id": "user456",
                "source_ip": "192.0.2.200",
                "description": "User exceeded API rate limit",
                "metadata": {"limit": 100, "requests": 150},
            },
        ]

        for event in security_events:
            db.insert_security_event(**event)

        print(f"✅ Inserted {len(security_events)} security events")

        # Query security events directly from database
        cursor = db.conn.cursor()
        cursor.execute("SELECT * FROM security_events")
        results = cursor.fetchall()

        assert len(results) == 2
        print(f"✅ Retrieved {len(results)} security events")

        # Verify first event
        assert results[0][2] == "unauthorized_access"  # event_type
        assert results[0][3] == "ERROR"  # severity
        assert results[0][4] == "attacker123"  # user_id
        assert results[0][5] == "198.51.100.50"  # source_ip
        print(f"✅ Security event verified: {results[0][2]} from {results[0][5]}")

        db.close()


def test_aggregate_metrics():
    """Test aggregate metrics calculation."""
    print("\n=== Test 6: Aggregate Metrics ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_audit.db")
        db = AuditDatabase(db_path)

        # Insert entries with different methods and metrics
        now = datetime.now(timezone.utc)
        for i in range(10):
            timestamp = (now - timedelta(minutes=i)).isoformat().replace("+00:00", "Z")
            entry = AuditEntry(
                timestamp=timestamp,
                event_id=f"evt_{i}",
                level="INFO",
                event_type="compress_success",
                user_id=f"user{i}",
                session_id=f"sess_{i}",
                source_ip="192.0.2.100",
                method="BRIO" if i < 5 else "BRIO_FULL",
                original_size=1000 * (i + 1),
                compressed_size=400 * (i + 1),
                compression_ratio=2.5,
                latency_ms=10.0 + i * 2,
                data_hash=f"hash_{i}",
                result_hash=f"result_{i}",
                metadata={},
                previous_hash=None,
                entry_hash=f"entry_{i}",
            )
            db.insert(entry)

        print(f"✅ Inserted 10 entries (5 BRIO, 5 BRIO_FULL)")

        # Calculate aggregate metrics
        start_time = (now - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
        end_time = now.isoformat().replace("+00:00", "Z")
        metrics = db.aggregate_metrics(start_time, end_time)

        assert "BRIO" in metrics
        assert "BRIO_FULL" in metrics
        print(f"✅ Metrics calculated for methods: {list(metrics.keys())}")

        # Verify BRIO metrics
        brio_metrics = metrics["BRIO"]
        assert brio_metrics["operations"] == 5
        assert brio_metrics["total_bytes_in"] == 1000 + 2000 + 3000 + 4000 + 5000  # 15000
        assert brio_metrics["total_bytes_out"] == 400 + 800 + 1200 + 1600 + 2000  # 6000
        assert brio_metrics["avg_ratio"] == 2.5
        print(
            f"✅ BRIO metrics: {brio_metrics['operations']} ops, "
            f"{brio_metrics['total_bytes_in']} bytes in, "
            f"{brio_metrics['total_bytes_out']} bytes out"
        )

        # Verify BRIO_FULL metrics
        brio_full_metrics = metrics["BRIO_FULL"]
        assert brio_full_metrics["operations"] == 5
        assert brio_full_metrics["total_bytes_in"] == 6000 + 7000 + 8000 + 9000 + 10000  # 40000
        print(
            f"✅ BRIO_FULL metrics: {brio_full_metrics['operations']} ops, "
            f"{brio_full_metrics['total_bytes_in']} bytes in"
        )

        db.close()


def test_compression_auditor_facade():
    """Test CompressionAuditor high-level facade."""
    print("\n=== Test 7: CompressionAuditor Facade ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_audit.db")
        auditor = CompressionAuditor(db_path, enable_chain=False)

        # Log compression events
        test_data = b"Hello, World!" * 100
        compressed_data = b"compressed_output"

        event_id = auditor.log_compression(
            event_type=CompressionEvent.COMPRESS_SUCCESS,
            method="BRIO",
            original_size=len(test_data),
            compressed_size=len(compressed_data),
            latency_ms=12.5,
            data=test_data,
            result=compressed_data,
            user_id="user123",
            session_id="sess_abc",
            source_ip="192.0.2.100",
            metadata={"file": "test.txt"},
        )

        print(f"✅ Logged compression event: {event_id}")

        # Log decompression
        event_id2 = auditor.log_compression(
            event_type=CompressionEvent.DECOMPRESS_SUCCESS,
            method="BRIO",
            original_size=len(compressed_data),
            compressed_size=len(test_data),
            latency_ms=8.3,
            data=compressed_data,
            result=test_data,
            user_id="user123",
            session_id="sess_abc",
        )

        print(f"✅ Logged decompression event: {event_id2}")

        # Query events (results are in reverse chronological order - newest first)
        results = auditor.query({}, limit=100)
        assert len(results) == 2
        print(f"✅ Retrieved {len(results)} events via auditor")

        # results[1] is the compress event (oldest), results[0] is decompress (newest)
        compress_event = results[1]
        decompress_event = results[0]

        # Verify data hashes were computed
        expected_compress_hash = hashlib.sha256(test_data).hexdigest()
        expected_decompress_hash = hashlib.sha256(compressed_data).hexdigest()

        actual_compress_hash = compress_event["data_hash"]
        actual_decompress_hash = decompress_event["data_hash"]

        assert (
            actual_compress_hash == expected_compress_hash
        ), f"Compress data hash mismatch: expected {expected_compress_hash[:16]}, got {actual_compress_hash[:16]}"
        assert (
            actual_decompress_hash == expected_decompress_hash
        ), f"Decompress data hash mismatch: expected {expected_decompress_hash[:16]}, got {actual_decompress_hash[:16]}"

        print(f"✅ Data hashes verified:")
        print(f"   - Compress: {compress_event['data_hash'][:16]}...")
        print(f"   - Decompress: {decompress_event['data_hash'][:16]}...")

        # Log security event
        auditor.log_security_event(
            event_type="suspicious_pattern",
            severity=AuditLevel.WARNING,
            description="Unusual compression pattern detected",
            user_id="user123",
            source_ip="192.0.2.100",
            metadata={"pattern": "repetitive"},
        )

        print(f"✅ Logged security event via auditor")

        auditor.close()


def test_hash_chain_integrity():
    """Test hash chain integrity verification."""
    print("\n=== Test 8: Hash Chain Integrity ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_audit.db")
        auditor = CompressionAuditor(db_path, enable_chain=True)

        # Log multiple events to create a chain
        test_data = b"Test data for chain"
        for i in range(5):
            auditor.log_compression(
                event_type=CompressionEvent.COMPRESS_SUCCESS,
                method="BRIO",
                original_size=len(test_data) + i,
                compressed_size=len(test_data) // 2,
                latency_ms=10.0 + i,
                data=test_data,
                user_id=f"user{i}",
                session_id=f"sess_{i}",
            )

        print(f"✅ Created hash chain with 5 entries")

        # Verify chain integrity
        is_valid, errors = auditor.verify_chain(1, 5)

        assert is_valid, f"Chain verification failed: {errors}"
        assert len(errors) == 0
        print(f"✅ Hash chain integrity verified: no errors")

        # Check that hashes are linked by querying database directly in insertion order
        # Note: auditor.query() returns newest first, but hash chain requires oldest first
        with auditor.db.lock:
            cursor = auditor.db.conn.cursor()
            cursor.execute("SELECT entry_hash, previous_hash FROM audit_log ORDER BY id ASC")
            rows = cursor.fetchall()

        print(f"   Retrieved {len(rows)} entries for chain verification")
        for i in range(1, len(rows)):
            prev_entry_hash = rows[i - 1][0]  # entry_hash of previous entry
            current_prev_hash = rows[i][1]  # previous_hash of current entry
            assert (
                current_prev_hash == prev_entry_hash
            ), f"Chain broken at entry {i}: expected prev={prev_entry_hash[:16]}, got {current_prev_hash[:16] if current_prev_hash else 'None'}"

        print(f"✅ All {len(rows)} entries properly linked in chain")
        print(f"   - First hash: {rows[0][0][:16]}...")
        print(f"   - Last hash: {rows[-1][0][:16]}...")

        auditor.close()


def test_aggregate_metrics_via_auditor():
    """Test aggregate metrics calculation via CompressionAuditor."""
    print("\n=== Test 9: Aggregate Metrics via Auditor ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_audit.db")
        auditor = CompressionAuditor(db_path, enable_chain=False)

        # Log various compression events
        methods = ["BRIO", "BRIO_FULL", "AuraLite"]
        for method in methods:
            for i in range(3):
                auditor.log_compression(
                    event_type=CompressionEvent.COMPRESS_SUCCESS,
                    method=method,
                    original_size=1000 * (i + 1),
                    compressed_size=400 * (i + 1),
                    latency_ms=10.0 + i,
                    data=b"test_data",
                )

        print(f"✅ Logged 9 compression events (3 per method)")

        # Get aggregate metrics
        metrics = auditor.aggregate_metrics(hours=1)

        assert len(metrics) == 3
        assert "BRIO" in metrics
        assert "BRIO_FULL" in metrics
        assert "AuraLite" in metrics
        print(f"✅ Metrics calculated for {len(metrics)} methods")

        # Verify each method has correct operation count
        for method in methods:
            assert metrics[method]["operations"] == 3
            print(
                f"   - {method}: {metrics[method]['operations']} ops, "
                f"{metrics[method]['total_bytes_in']} bytes in, "
                f"avg ratio: {metrics[method]['avg_ratio']:.2f}x"
            )

        auditor.close()


def run_all_tests():
    """Run all test functions."""
    print("=" * 70)
    print("AUDIT LAYER COMPREHENSIVE TEST SUITE")
    print("=" * 70)

    tests = [
        test_audit_entry_creation,
        test_metadata_compaction_expansion,
        test_audit_database_initialization,
        test_insert_and_query_operations,
        test_security_event_logging,
        test_aggregate_metrics,
        test_compression_auditor_facade,
        test_hash_chain_integrity,
        test_aggregate_metrics_via_auditor,
    ]

    passed = 0
    failed = 0

    for test_func in tests:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"❌ {test_func.__name__} FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"❌ {test_func.__name__} ERROR: {e}")
            failed += 1

    print("\n" + "=" * 70)
    print(f"TEST RESULTS: {passed}/{len(tests)} passed, {failed}/{len(tests)} failed")
    print("=" * 70)

    if failed == 0:
        print("✅ ALL TESTS PASSED!")
        return 0
    else:
        print(f"❌ {failed} TEST(S) FAILED")
        return 1


if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
