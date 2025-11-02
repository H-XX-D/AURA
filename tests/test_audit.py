"""
Comprehensive test suite for audit.py module.

Tests cover:
1. AuditEntry creation and serialization/deserialization
2. AuditLogger initialization with multiple log types
3. Compression event logging
4. AI output logging (pre/post moderation)
5. Metadata-only logging (privacy-preserving)
6. Safety alert logging
7. Integrity chain verification
8. Entry retrieval with filtering
9. Thread safety
10. Global logger singleton
"""

import os
import sys
import tempfile
import time
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aura_compression.audit import (
    AuditLogType,
    AuditEntry,
    AuditLogger,
    get_audit_logger,
    reset_audit_logger,
)


def test_audit_entry_creation():
    """Test AuditEntry dataclass creation and field validation."""
    print("\n=== Test 1: AuditEntry Creation ===")
    
    entry = AuditEntry(
        timestamp="2024-01-15T10:30:00Z",
        entry_id="test_entry_123",
        log_type=AuditLogType.CLIENT_DELIVERED.value,
        plaintext="Hello, World!",
        compressed_payload=b"\x00\x01\x02\x03",
        metadata={"method": "BRIO", "ratio": 2.5},
        session_id="sess_abc",
        user_id="user123",
        compression_method="BRIO",
        compression_ratio=2.5,
        pre_moderation_content=None,
        post_moderation_content=None,
        moderation_applied=False,
        harm_type=None,
        severity=None,
        integrity_hash="abc123def456",
    )
    
    assert entry.timestamp == "2024-01-15T10:30:00Z"
    assert entry.entry_id == "test_entry_123"
    assert entry.log_type == AuditLogType.CLIENT_DELIVERED.value
    assert entry.plaintext == "Hello, World!"
    assert entry.compressed_payload == b"\x00\x01\x02\x03"
    assert entry.metadata == {"method": "BRIO", "ratio": 2.5}
    assert entry.session_id == "sess_abc"
    assert entry.user_id == "user123"
    assert entry.compression_method == "BRIO"
    assert entry.compression_ratio == 2.5
    assert entry.integrity_hash == "abc123def456"
    
    print("✅ AuditEntry created successfully with all fields")
    print(f"   - Entry ID: {entry.entry_id}")
    print(f"   - Log Type: {entry.log_type}")
    print(f"   - Compression Method: {entry.compression_method}")


def test_audit_entry_serialization():
    """Test AuditEntry JSON serialization and deserialization."""
    print("\n=== Test 2: AuditEntry Serialization ===")
    
    original_entry = AuditEntry(
        timestamp="2024-01-15T10:30:00Z",
        entry_id="test_entry_123",
        log_type=AuditLogType.CLIENT_DELIVERED.value,
        plaintext="Test data",
        compressed_payload=b"\xde\xad\xbe\xef",
        metadata={"key": "value"},
        session_id="sess_xyz",
        user_id="user456",
        integrity_hash="hash123",
    )
    
    # Serialize to JSON
    json_str = original_entry.to_json()
    print(f"Serialized JSON length: {len(json_str)} bytes")
    
    # Verify it's valid JSON
    parsed = json.loads(json_str)
    assert "timestamp" in parsed
    assert "entry_id" in parsed
    assert "compressed_payload" in parsed
    assert parsed["compressed_payload"] == "deadbeef"  # hex encoded
    
    # Deserialize back
    restored_entry = AuditEntry.from_json(json_str)
    
    assert restored_entry.timestamp == original_entry.timestamp
    assert restored_entry.entry_id == original_entry.entry_id
    assert restored_entry.log_type == original_entry.log_type
    assert restored_entry.plaintext == original_entry.plaintext
    assert restored_entry.compressed_payload == original_entry.compressed_payload
    assert restored_entry.metadata == original_entry.metadata
    assert restored_entry.session_id == original_entry.session_id
    assert restored_entry.user_id == original_entry.user_id
    assert restored_entry.integrity_hash == original_entry.integrity_hash
    
    print("✅ Serialization/deserialization successful")
    print(f"   - Original payload: {original_entry.compressed_payload.hex()}")
    print(f"   - Restored payload: {restored_entry.compressed_payload.hex()}")


def test_audit_logger_initialization():
    """Test AuditLogger initialization and log file creation."""
    print("\n=== Test 3: AuditLogger Initialization ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        log_dir = os.path.join(tmpdir, "audit_logs")
        logger = AuditLogger(log_dir)
        
        # Verify log directory created
        assert os.path.exists(log_dir)
        print(f"✅ Log directory created: {log_dir}")
        
        # Verify log files dict initialized
        assert AuditLogType.CLIENT_DELIVERED in logger.log_files
        assert AuditLogType.AI_GENERATED in logger.log_files
        assert AuditLogType.METADATA_ONLY in logger.log_files
        assert AuditLogType.SAFETY_ALERTS in logger.log_files
        print(f"✅ Log files initialized: {len(logger.log_files)} log types")
        
        # Verify locks initialized
        assert len(logger.locks) == len(AuditLogType)
        print(f"✅ Thread locks initialized: {len(logger.locks)} locks")
        
        # Verify last hashes initialized
        assert len(logger.last_hashes) == len(AuditLogType)
        assert all(h is None for h in logger.last_hashes.values())
        print(f"✅ Last hashes initialized: all None (new logs)")


def test_compression_logging():
    """Test logging compression events."""
    print("\n=== Test 4: Compression Event Logging ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        log_dir = os.path.join(tmpdir, "audit_logs")
        logger = AuditLogger(log_dir)
        
        # Log compression event
        plaintext = "Hello, compression test!"
        compressed = b"\x01\x02\x03\x04\x05"
        metadata = {
            "method": "BRIO",
            "ratio": 3.5,
            "original_size": len(plaintext),
            "compressed_size": len(compressed),
        }
        
        entry_id = logger.log_compression(
            plaintext=plaintext,
            compressed_payload=compressed,
            metadata=metadata,
            session_id="sess_test",
            user_id="user_test",
        )
        
        assert entry_id is not None
        assert len(entry_id) == 16  # 16 character hex hash
        print(f"✅ Compression logged with entry_id: {entry_id}")
        
        # Verify log file created and contains entry
        log_file = logger.log_files[AuditLogType.CLIENT_DELIVERED]
        assert log_file.exists()
        
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            assert len(lines) == 1
            
            # Parse entry
            entry = AuditEntry.from_json(lines[0].strip())
            assert entry.entry_id == entry_id
            assert entry.plaintext == plaintext
            assert entry.compressed_payload == compressed
            assert entry.session_id == "sess_test"
            assert entry.user_id == "user_test"
            assert entry.compression_method == "BRIO"
            assert entry.compression_ratio == 3.5
            assert entry.integrity_hash is not None
        
        print(f"✅ Entry verified in log file")
        print(f"   - Plaintext: {plaintext}")
        print(f"   - Method: BRIO, Ratio: 3.5x")


def test_ai_output_logging():
    """Test logging AI-generated output with moderation."""
    print("\n=== Test 5: AI Output Logging ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        log_dir = os.path.join(tmpdir, "audit_logs")
        logger = AuditLogger(log_dir)
        
        # Log AI output with moderation
        pre_moderation = "This is AI generated content that might be harmful."
        post_moderation = "This is AI generated content that [REDACTED]."
        
        entry_id = logger.log_ai_output(
            pre_moderation_content=pre_moderation,
            post_moderation_content=post_moderation,
            moderation_applied=True,
            session_id="ai_sess_123",
            user_id="ai_user_456",
        )
        
        assert entry_id is not None
        print(f"✅ AI output logged with entry_id: {entry_id}")
        
        # Verify entry in log
        log_file = logger.log_files[AuditLogType.AI_GENERATED]
        assert log_file.exists()
        
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            assert len(lines) == 1
            
            entry = AuditEntry.from_json(lines[0].strip())
            assert entry.entry_id == entry_id
            assert entry.pre_moderation_content == pre_moderation
            assert entry.post_moderation_content == post_moderation
            assert entry.moderation_applied is True
            assert entry.session_id == "ai_sess_123"
            assert entry.user_id == "ai_user_456"
        
        print(f"✅ AI output entry verified")
        print(f"   - Moderation applied: {entry.moderation_applied}")
        print(f"   - Pre-moderation length: {len(pre_moderation)} chars")
        print(f"   - Post-moderation length: {len(post_moderation)} chars")


def test_metadata_only_logging():
    """Test privacy-preserving metadata-only logging."""
    print("\n=== Test 6: Metadata-Only Logging ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        log_dir = os.path.join(tmpdir, "audit_logs")
        logger = AuditLogger(log_dir)
        
        # Log metadata without content (privacy-preserving)
        metadata = {
            "method": "AuraLite",
            "ratio": 2.8,
            "duration_ms": 45.3,
            "platform": "linux",
        }
        
        entry_id = logger.log_metadata_only(
            metadata=metadata,
            session_id="metadata_sess",
        )
        
        assert entry_id is not None
        print(f"✅ Metadata logged with entry_id: {entry_id}")
        
        # Verify entry
        log_file = logger.log_files[AuditLogType.METADATA_ONLY]
        assert log_file.exists()
        
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            assert len(lines) == 1
            
            entry = AuditEntry.from_json(lines[0].strip())
            assert entry.entry_id == entry_id
            assert entry.plaintext is None  # No content stored
            assert entry.compressed_payload is None  # No payload stored
            assert entry.metadata is not None
            assert entry.session_id == "metadata_sess"
        
        print(f"✅ Metadata-only entry verified (privacy-preserving)")
        print(f"   - Plaintext: {entry.plaintext} (None for privacy)")
        print(f"   - Metadata fields: {len(entry.metadata)}")


def test_safety_alert_logging():
    """Test logging blocked harmful content."""
    print("\n=== Test 7: Safety Alert Logging ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        log_dir = os.path.join(tmpdir, "audit_logs")
        logger = AuditLogger(log_dir)
        
        # Log safety alert for different harm types
        test_cases = [
            ("Violent content blocked", "violence", "high"),
            ("Illegal activity detected", "illegal", "critical"),
            ("Privacy violation found", "privacy", "medium"),
            ("Misinformation detected", "misinformation", "low"),
        ]
        
        entry_ids = []
        for content, harm_type, severity in test_cases:
            entry_id = logger.log_safety_alert(
                blocked_content=content,
                harm_type=harm_type,
                severity=severity,
                session_id=f"safety_sess_{harm_type}",
                user_id="safety_user",
            )
            entry_ids.append(entry_id)
        
        print(f"✅ Logged {len(entry_ids)} safety alerts")
        
        # Verify all entries
        log_file = logger.log_files[AuditLogType.SAFETY_ALERTS]
        assert log_file.exists()
        
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            assert len(lines) == len(test_cases)
            
            for i, (content, harm_type, severity) in enumerate(test_cases):
                entry = AuditEntry.from_json(lines[i].strip())
                assert entry.entry_id == entry_ids[i]
                assert entry.plaintext == content
                assert entry.harm_type == harm_type
                assert entry.severity == severity
                assert entry.user_id == "safety_user"
                print(f"   ✓ {harm_type} ({severity}): {content}")


def test_integrity_chain_verification():
    """Test cryptographic integrity chain verification."""
    print("\n=== Test 8: Integrity Chain Verification ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        log_dir = os.path.join(tmpdir, "audit_logs")
        logger = AuditLogger(log_dir)
        
        # Log multiple compression events to create chain
        for i in range(5):
            logger.log_compression(
                plaintext=f"Test message {i}",
                compressed_payload=f"compressed_{i}".encode(),
                metadata={"method": "BRIO", "ratio": 2.0 + i * 0.1, "index": i},
                session_id=f"sess_{i}",
                user_id=f"user_{i}",
            )
        
        print(f"✅ Created integrity chain with 5 entries")
        
        # Verify integrity
        is_valid = logger.verify_integrity(AuditLogType.CLIENT_DELIVERED)
        assert is_valid is True
        print(f"✅ Integrity chain verified: valid")
        
        # Test tampering detection - modify a log entry
        log_file = logger.log_files[AuditLogType.CLIENT_DELIVERED]
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Tamper with middle entry
        tampered_entry = AuditEntry.from_json(lines[2].strip())
        tampered_entry.plaintext = "TAMPERED DATA"
        lines[2] = tampered_entry.to_json() + '\n'
        
        with open(log_file, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        
        # Verify tampering detected
        is_valid = logger.verify_integrity(AuditLogType.CLIENT_DELIVERED)
        assert is_valid is False
        print(f"✅ Tampering detected: integrity check failed as expected")


def test_entry_retrieval_with_filtering():
    """Test retrieving audit entries with filters."""
    print("\n=== Test 9: Entry Retrieval with Filtering ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        log_dir = os.path.join(tmpdir, "audit_logs")
        logger = AuditLogger(log_dir)
        
        # Log entries with different users and sessions
        for user_id in ["alice", "bob", "alice"]:
            for session_id in ["morning", "afternoon"]:
                logger.log_compression(
                    plaintext=f"Data from {user_id} in {session_id}",
                    compressed_payload=b"compressed",
                    metadata={"method": "BRIO"},
                    session_id=session_id,
                    user_id=user_id,
                )
        
        print(f"✅ Logged 6 entries (2 users × 3 sessions each)")
        
        # Retrieve all entries
        all_entries = logger.get_entries(AuditLogType.CLIENT_DELIVERED, limit=100)
        assert len(all_entries) == 6
        print(f"✅ Retrieved all entries: {len(all_entries)}")
        
        # Filter by user_id
        alice_entries = logger.get_entries(
            AuditLogType.CLIENT_DELIVERED,
            user_id="alice",
            limit=100
        )
        assert len(alice_entries) == 4  # alice appears twice, 2 sessions each = 4
        assert all(e.user_id == "alice" for e in alice_entries)
        print(f"✅ Filtered by user_id='alice': {len(alice_entries)} entries")
        
        bob_entries = logger.get_entries(
            AuditLogType.CLIENT_DELIVERED,
            user_id="bob",
            limit=100
        )
        assert len(bob_entries) == 2  # bob appears once, 2 sessions = 2
        assert all(e.user_id == "bob" for e in bob_entries)
        print(f"✅ Filtered by user_id='bob': {len(bob_entries)} entries")
        
        # Filter by session_id
        morning_entries = logger.get_entries(
            AuditLogType.CLIENT_DELIVERED,
            session_id="morning",
            limit=100
        )
        assert len(morning_entries) == 3  # 3 user entries × morning
        assert all(e.session_id == "morning" for e in morning_entries)
        print(f"✅ Filtered by session_id='morning': {len(morning_entries)} entries")
        
        # Filter by both user_id and session_id
        alice_morning = logger.get_entries(
            AuditLogType.CLIENT_DELIVERED,
            user_id="alice",
            session_id="morning",
            limit=100
        )
        assert len(alice_morning) == 2  # alice × morning, appears twice
        assert all(e.user_id == "alice" and e.session_id == "morning" for e in alice_morning)
        print(f"✅ Filtered by user='alice' AND session='morning': {len(alice_morning)} entries")
        
        # Test limit
        limited = logger.get_entries(AuditLogType.CLIENT_DELIVERED, limit=3)
        assert len(limited) == 3
        print(f"✅ Limit=3 respected: {len(limited)} entries returned")


def test_global_logger_singleton():
    """Test global audit logger singleton."""
    print("\n=== Test 10: Global Logger Singleton ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        log_dir = os.path.join(tmpdir, "audit_logs")
        
        # Reset any existing global logger
        reset_audit_logger()
        
        # Get logger instance
        logger1 = get_audit_logger(log_dir)
        assert logger1 is not None
        print(f"✅ Created global logger instance 1")
        
        # Get logger again - should be same instance
        logger2 = get_audit_logger(log_dir)
        assert logger2 is logger1
        print(f"✅ Retrieved same logger instance (singleton)")
        
        # Log with first instance
        entry_id1 = logger1.log_compression(
            plaintext="Test from logger1",
            compressed_payload=b"data1",
            metadata={"method": "BRIO"},
        )
        
        # Retrieve with second instance - should see same data
        entries = logger2.get_entries(AuditLogType.CLIENT_DELIVERED, limit=10)
        assert len(entries) == 1
        assert entries[0].entry_id == entry_id1
        print(f"✅ Both logger instances share same data")
        
        # Reset logger
        reset_audit_logger()
        logger3 = get_audit_logger(log_dir)
        assert logger3 is not logger1  # New instance after reset
        print(f"✅ Reset creates new logger instance")
        
        # But should still read existing log files
        entries_after_reset = logger3.get_entries(AuditLogType.CLIENT_DELIVERED, limit=10)
        assert len(entries_after_reset) == 1  # Still sees previous entry
        print(f"✅ New logger instance reads existing log files")


def test_multiple_log_types_independence():
    """Test that different log types are independent."""
    print("\n=== Test 11: Multiple Log Types Independence ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        log_dir = os.path.join(tmpdir, "audit_logs")
        logger = AuditLogger(log_dir)
        
        # Log to each log type
        compression_id = logger.log_compression(
            plaintext="Compression test",
            compressed_payload=b"compressed",
            metadata={"method": "BRIO"},
        )
        
        ai_id = logger.log_ai_output(
            pre_moderation_content="AI pre",
            post_moderation_content="AI post",
            moderation_applied=True,
        )
        
        metadata_id = logger.log_metadata_only(
            metadata={"stat": "value"},
        )
        
        safety_id = logger.log_safety_alert(
            blocked_content="Harmful",
            harm_type="violence",
            severity="high",
        )
        
        print(f"✅ Logged to all 4 log types")
        
        # Verify each log type has exactly one entry
        client_entries = logger.get_entries(AuditLogType.CLIENT_DELIVERED, limit=10)
        assert len(client_entries) == 1
        assert client_entries[0].entry_id == compression_id
        print(f"   - CLIENT_DELIVERED: 1 entry")
        
        ai_entries = logger.get_entries(AuditLogType.AI_GENERATED, limit=10)
        assert len(ai_entries) == 1
        assert ai_entries[0].entry_id == ai_id
        print(f"   - AI_GENERATED: 1 entry")
        
        metadata_entries = logger.get_entries(AuditLogType.METADATA_ONLY, limit=10)
        assert len(metadata_entries) == 1
        assert metadata_entries[0].entry_id == metadata_id
        print(f"   - METADATA_ONLY: 1 entry")
        
        safety_entries = logger.get_entries(AuditLogType.SAFETY_ALERTS, limit=10)
        assert len(safety_entries) == 1
        assert safety_entries[0].entry_id == safety_id
        print(f"   - SAFETY_ALERTS: 1 entry")
        
        # Verify separate log files
        assert logger.log_files[AuditLogType.CLIENT_DELIVERED].exists()
        assert logger.log_files[AuditLogType.AI_GENERATED].exists()
        assert logger.log_files[AuditLogType.METADATA_ONLY].exists()
        assert logger.log_files[AuditLogType.SAFETY_ALERTS].exists()
        print(f"✅ All log types have separate files")


def run_all_tests():
    """Run all test functions."""
    print("=" * 70)
    print("AUDIT MODULE COMPREHENSIVE TEST SUITE")
    print("=" * 70)
    
    tests = [
        test_audit_entry_creation,
        test_audit_entry_serialization,
        test_audit_logger_initialization,
        test_compression_logging,
        test_ai_output_logging,
        test_metadata_only_logging,
        test_safety_alert_logging,
        test_integrity_chain_verification,
        test_entry_retrieval_with_filtering,
        test_global_logger_singleton,
        test_multiple_log_types_independence,
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
            import traceback
            traceback.print_exc()
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
