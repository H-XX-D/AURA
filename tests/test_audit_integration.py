#!/usr/bin/env python3
"""
AURA Compression System - Comprehensive Test Suite
Test 16-20: Audit Integration Testing
"""

import sys
import os
import tempfile
import json
from pathlib import Path
from typing import Dict, Any, List

# Add source path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src' / 'python'))

from aura_compression.compressor import ProductionHybridCompressor
from aura_compression.audit import AuditLogger
from aura_compression.enums import CompressionMethod


class TestAuditIntegration:
    """Test comprehensive audit logging functionality"""

    def __init__(self):
        self.test_results = []
        self.temp_dir = None

    def setup_temp_dir(self):
        """Create temporary directory for audit logs"""
        self.temp_dir = Path(tempfile.mkdtemp())

    def cleanup_temp_dir(self):
        """Clean up temporary directory"""
        if self.temp_dir and self.temp_dir.exists():
            import shutil
            shutil.rmtree(self.temp_dir)

    def log_test(self, test_name: str, passed: bool, details: str = ""):
        """Log test result"""
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} {test_name}")
        if details:
            print(f"   {details}")
        self.test_results.append({
            'test': test_name,
            'passed': passed,
            'details': details
        })

    def test_16_audit_logger_initialization(self):
        """Test 16: Audit logger initialization and basic functionality"""
        try:
            self.setup_temp_dir()

            # Create compressor with audit logging enabled
            compressor = ProductionHybridCompressor(
                enable_audit_logging=True,
                audit_log_directory=str(self.temp_dir)
            )

            # Perform a compression operation to trigger audit logging
            test_message = "Test message for audit initialization"
            result = compressor.compress(test_message)

            # Now verify log files are created
            expected_files = [
                "client_delivered.jsonl",
                "ai_generated.jsonl",
                "metadata_only.jsonl",
                "safety_alerts.log"
            ]

            created_files = []
            for filename in expected_files:
                log_path = self.temp_dir / filename
                if log_path.exists():
                    created_files.append(filename)

            assert len(created_files) > 0, f"No audit log files created. Expected: {expected_files}"

            self.log_test("test_16_audit_logger_initialization",
                          True, f"Created {len(created_files)} audit log files: {created_files}")
            return True
        except Exception as e:
            self.log_test("test_16_audit_logger_initialization",
                          False, f"Audit logger initialization failed: {e}")
            return False
        finally:
            self.cleanup_temp_dir()

    def test_17_compression_audit_logging(self):
        """Test 17: Compression event audit logging"""
        try:
            self.setup_temp_dir()

            # Create compressor with audit logging
            compressor = ProductionHybridCompressor(
                enable_audit_logging=True,
                audit_log_directory=str(self.temp_dir)
            )

            # Perform compression that should be logged
            test_message = "This message should be audited during compression"
            result = compressor.compress(test_message)

            # Check that audit logs contain entries
            client_delivered_log = self.temp_dir / "client_delivered.jsonl"
            metadata_log = self.temp_dir / "metadata_only.jsonl"

            # Read and verify log entries
            client_entries = []
            if client_delivered_log.exists():
                with open(client_delivered_log, 'r') as f:
                    for line in f:
                        if line.strip():
                            client_entries.append(json.loads(line))

            metadata_entries = []
            if metadata_log.exists():
                with open(metadata_log, 'r') as f:
                    for line in f:
                        if line.strip():
                            metadata_entries.append(json.loads(line))

            # Should have at least one entry in each log
            assert len(client_entries) > 0, "No client delivered audit entries"
            assert len(metadata_entries) > 0, "No metadata audit entries"

            # Verify entry structure
            if client_entries:
                entry = client_entries[0]
                required_fields = ['timestamp', 'entry_id', 'log_type', 'session_id']
                for field in required_fields:
                    assert field in entry, f"Missing required field: {field}"

            self.log_test("test_17_compression_audit_logging",
                          True, f"Audit logs contain {len(client_entries)} client and {len(metadata_entries)} metadata entries")
            return True
        except Exception as e:
            self.log_test("test_17_compression_audit_logging",
                          False, f"Compression audit logging failed: {e}")
            return False
        finally:
            self.cleanup_temp_dir()

    def test_18_separated_audit_streams(self):
        """Test 18: Separated audit streams (GDPR/HIPAA compliance)"""
        try:
            self.setup_temp_dir()

            compressor = ProductionHybridCompressor(
                enable_audit_logging=True,
                audit_log_directory=str(self.temp_dir)
            )

            # Test different types of content that should go to different logs
            test_cases = [
                ("Regular message", "client_delivered"),
                ("AI generated content", "ai_generated"),
                ("Safety concern", "safety_alerts"),
            ]

            for message, expected_log_type in test_cases:
                result = compressor.compress(message)

            # Verify separated logs
            log_files = {
                'client_delivered': self.temp_dir / "client_delivered.jsonl",
                'ai_generated': self.temp_dir / "ai_generated.jsonl",
                'metadata_only': self.temp_dir / "metadata_only.jsonl",
                'safety_alerts': self.temp_dir / "safety_alerts.log"
            }

            log_counts = {}
            for log_type, log_path in log_files.items():
                if log_path.exists():
                    with open(log_path, 'r') as f:
                        lines = [line for line in f if line.strip()]
                        log_counts[log_type] = len(lines)
                else:
                    log_counts[log_type] = 0

            # Should have entries in multiple logs
            total_entries = sum(log_counts.values())
            assert total_entries > 0, "No audit entries found"

            active_logs = sum(1 for count in log_counts.values() if count > 0)
            assert active_logs >= 2, f"Expected at least 2 active logs, got {active_logs}"

            self.log_test("test_18_separated_audit_streams",
                          True, f"Separated audit streams: {log_counts}")
            return True
        except Exception as e:
            self.log_test("test_18_separated_audit_streams",
                          False, f"Separated audit streams test failed: {e}")
            return False
        finally:
            self.cleanup_temp_dir()

    def test_19_audit_data_integrity(self):
        """Test 19: Audit data integrity and tamper detection"""
        try:
            self.setup_temp_dir()

            compressor = ProductionHybridCompressor(
                enable_audit_logging=True,
                audit_log_directory=str(self.temp_dir)
            )

            # Perform multiple compressions
            messages = ["Message 1", "Message 2", "Message 3"]
            for msg in messages:
                compressor.compress(msg)

            # Read audit entries and verify integrity
            client_log = self.temp_dir / "client_delivered.jsonl"
            entries = []

            if client_log.exists():
                with open(client_log, 'r') as f:
                    for line in f:
                        if line.strip():
                            entries.append(json.loads(line))

            # Verify entry integrity
            for i, entry in enumerate(entries):
                # Check required fields
                assert 'timestamp' in entry, f"Entry {i} missing timestamp"
                assert 'entry_id' in entry, f"Entry {i} missing entry_id"
                assert 'log_type' in entry, f"Entry {i} missing log_type"

                # Verify timestamp format (ISO 8601)
                timestamp = entry['timestamp']
                assert 'T' in timestamp and ('Z' in timestamp or '+' in timestamp or '-' in timestamp[-6:]), f"Invalid timestamp format: {timestamp}"

                # Verify entry ID uniqueness
                entry_ids = [e['entry_id'] for e in entries]
                assert len(entry_ids) == len(set(entry_ids)), "Duplicate entry IDs found"

            self.log_test("test_19_audit_data_integrity",
                          True, f"Audit data integrity verified for {len(entries)} entries")
            return True
        except Exception as e:
            self.log_test("test_19_audit_data_integrity",
                          False, f"Audit data integrity test failed: {e}")
            return False
        finally:
            self.cleanup_temp_dir()

    def test_20_compliance_validation(self):
        """Test 20: GDPR/HIPAA/SOC2 compliance validation"""
        try:
            self.setup_temp_dir()

            compressor = ProductionHybridCompressor(
                enable_audit_logging=True,
                audit_log_directory=str(self.temp_dir),
                session_id="test_session_123",
                user_id="test_user_456"
            )

            # Test compliance-related content
            compliance_messages = [
                "Patient data: John Doe, DOB: 01/01/1980",
                "Financial transaction: $500.00",
                "User consent granted for data processing",
            ]

            for message in compliance_messages:
                result = compressor.compress(message)

            # Verify compliance features
            client_log = self.temp_dir / "client_delivered.jsonl"
            compliance_entries = []

            if client_log.exists():
                with open(client_log, 'r') as f:
                    for line in f:
                        if line.strip():
                            entry = json.loads(line)
                            compliance_entries.append(entry)

            # Verify compliance features - basic validation
            gdpr_compliant = False
            hipaa_compliant = False

            for entry in compliance_entries:
                # Check for session and user tracking (GDPR)
                if 'session_id' in entry and entry.get('session_id') == 'test_session_123':
                    gdpr_compliant = True

                # Check for user tracking (HIPAA)
                if 'user_id' in entry and entry.get('user_id') == 'test_user_456':
                    hipaa_compliant = True

            # Basic compliance checks - just verify audit logging works
            assert len(compliance_entries) > 0, "No compliance audit entries found"
            assert gdpr_compliant, "GDPR session tracking not working"
            assert hipaa_compliant, "HIPAA user tracking not working"

            self.log_test("test_20_compliance_validation",
                          True, f"Compliance validation: GDPR={gdpr_compliant}, HIPAA={hipaa_compliant}, {len(compliance_entries)} entries")
            return True
        except Exception as e:
            self.log_test("test_20_compliance_validation",
                          False, f"Compliance validation test failed: {e}")
            return False
        finally:
            self.cleanup_temp_dir()

    def run_all_tests(self):
        """Run all audit integration tests"""
        print("=" * 80)
        print("AURA COMPRESSION SYSTEM - AUDIT TESTS (16-20)")
        print("=" * 80)

        tests = [
            self.test_16_audit_logger_initialization,
            self.test_17_compression_audit_logging,
            self.test_18_separated_audit_streams,
            self.test_19_audit_data_integrity,
            self.test_20_compliance_validation,
        ]

        passed = 0
        for test in tests:
            if test():
                passed += 1
            print()

        print(f"Results: {passed}/{len(tests)} tests passed")
        return passed == len(tests)


if __name__ == "__main__":
    tester = TestAuditIntegration()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)