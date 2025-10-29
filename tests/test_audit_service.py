#!/usr/bin/env python3
"""
Unit tests for AuditService
"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from aura_compression.audit_service import AuditService, NoOpAuditService, create_audit_service


class TestAuditService(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def test_audit_service_enabled(self):
        """Test AuditService with audit logging enabled"""
        service = AuditService(enable_audit_logging=True, audit_log_directory=self.temp_dir)

        self.assertTrue(service.is_enabled())
        self.assertIsNotNone(service.get_logger())

        # Test logging methods don't raise exceptions
        service.log_compression_event(
            plaintext="test",
            compressed_payload=b"compressed",
            metadata={"test": "data"},
            session_id="session1",
            user_id="user1"
        )

        service.log_metadata_only(
            metadata={"test": "data"},
            session_id="session1"
        )

    def test_audit_service_disabled(self):
        """Test AuditService with audit logging disabled"""
        service = AuditService(enable_audit_logging=False, audit_log_directory=self.temp_dir)

        self.assertFalse(service.is_enabled())
        self.assertIsNone(service.get_logger())

        # Test logging methods don't raise exceptions
        service.log_compression_event(
            plaintext="test",
            compressed_payload=b"compressed",
            metadata={"test": "data"}
        )

        service.log_metadata_only(metadata={"test": "data"})

    def test_noop_audit_service(self):
        """Test NoOpAuditService"""
        service = NoOpAuditService()

        # Test logging methods don't raise exceptions and do nothing
        service.log_compression_event(
            plaintext="test",
            compressed_payload=b"compressed",
            metadata={"test": "data"}
        )

        service.log_metadata_only(metadata={"test": "data"})

    def test_create_audit_service_enabled(self):
        """Test factory function creates AuditService when enabled"""
        service = create_audit_service(enable_audit_logging=True, audit_log_directory=self.temp_dir)
        self.assertIsInstance(service, AuditService)
        self.assertTrue(service.is_enabled())

    def test_create_audit_service_disabled(self):
        """Test factory function creates NoOpAuditService when disabled"""
        service = create_audit_service(enable_audit_logging=False, audit_log_directory=self.temp_dir)
        self.assertIsInstance(service, NoOpAuditService)

    @patch('aura_compression.audit_service.get_audit_logger')
    def test_audit_service_initialization(self, mock_get_logger):
        """Test that AuditService properly initializes the audit logger"""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        service = AuditService(enable_audit_logging=True, audit_log_directory=self.temp_dir)

        mock_get_logger.assert_called_once_with(self.temp_dir)
        self.assertEqual(service.get_logger(), mock_logger)


if __name__ == '__main__':
    unittest.main()