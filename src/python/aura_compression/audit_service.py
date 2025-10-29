#!/usr/bin/env python3
"""
Audit Service - Extracted audit logging functionality from ProductionHybridCompressor
Implements Patent Claim 2, GDPR Article 15, HIPAA 45 CFR 164.312(b), SOC2 CC6.1 compliant logging
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Protocol
from .audit import AuditLogger, get_audit_logger


class AuditServiceInterface(Protocol):
    """Protocol for audit service implementations"""

    def log_compression_event(
        self,
        plaintext: str,
        compressed_payload: bytes,
        metadata: Dict[str, Any],
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> None:
        """Log a compression event"""
        ...

    def log_metadata_only(
        self,
        metadata: Dict[str, Any],
        session_id: Optional[str] = None,
    ) -> None:
        """Log metadata without content for privacy-preserving analytics"""
        ...


class AuditService(AuditServiceInterface):
    """
    Service wrapper for audit logging functionality
    Provides clean interface for compression audit logging
    """

    def __init__(
        self,
        enable_audit_logging: bool = False,
        audit_log_directory: str = "./audit_logs",
    ):
        """
        Initialize audit service

        Args:
            enable_audit_logging: Whether to enable audit logging
            audit_log_directory: Directory for audit logs
        """
        self.enable_audit_logging = enable_audit_logging
        self._audit_logger: Optional[AuditLogger] = None

        if self.enable_audit_logging:
            self._audit_logger = get_audit_logger(audit_log_directory)

    def log_compression_event(
        self,
        plaintext: str,
        compressed_payload: bytes,
        metadata: Dict[str, Any],
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> None:
        """
        Log a compression event with full details

        Args:
            plaintext: Original uncompressed text
            compressed_payload: Compressed binary data
            metadata: Compression metadata
            session_id: Optional session identifier
            user_id: Optional user identifier
        """
        if not self.enable_audit_logging or self._audit_logger is None:
            return

        # Log the compression event
        self._audit_logger.log_compression(
            plaintext=plaintext,
            compressed_payload=compressed_payload,
            metadata=metadata,
            session_id=session_id,
            user_id=user_id,
        )

        # Also log metadata-only for privacy-preserving analytics (Claim 35)
        self._audit_logger.log_metadata_only(
            metadata=metadata,
            session_id=session_id,
        )

    def log_metadata_only(
        self,
        metadata: Dict[str, Any],
        session_id: Optional[str] = None,
    ) -> None:
        """
        Log metadata without content for privacy-preserving analytics

        Args:
            metadata: Compression metadata
            session_id: Optional session identifier
        """
        if not self.enable_audit_logging or self._audit_logger is None:
            return

        self._audit_logger.log_metadata_only(
            metadata=metadata,
            session_id=session_id,
        )

    def is_enabled(self) -> bool:
        """Check if audit logging is enabled"""
        return self.enable_audit_logging

    def get_logger(self) -> Optional[AuditLogger]:
        """Get the underlying audit logger (for advanced operations)"""
        return self._audit_logger


class NoOpAuditService(AuditServiceInterface):
    """
    No-operation audit service for when audit logging is disabled
    Provides same interface but does nothing
    """

    def log_compression_event(
        self,
        plaintext: str,
        compressed_payload: bytes,
        metadata: Dict[str, Any],
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> None:
        """No-op implementation"""
        pass

    def log_metadata_only(
        self,
        metadata: Dict[str, Any],
        session_id: Optional[str] = None,
    ) -> None:
        """No-op implementation"""
        pass


def create_audit_service(
    enable_audit_logging: bool = False,
    audit_log_directory: str = "./audit_logs",
) -> AuditServiceInterface:
    """
    Factory function to create appropriate audit service

    Args:
        enable_audit_logging: Whether to enable audit logging
        audit_log_directory: Directory for audit logs

    Returns:
        AuditServiceInterface implementation
    """
    if enable_audit_logging:
        return AuditService(
            enable_audit_logging=enable_audit_logging,
            audit_log_directory=audit_log_directory,
        )
    else:
        return NoOpAuditService()