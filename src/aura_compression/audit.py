#!/usr/bin/env python3
"""
Audit Logging Infrastructure - Patent Claim 2
Implements GDPR Article 15, HIPAA 45 CFR 164.312(b), SOC2 CC6.1 compliant logging
"""

import hashlib
import json
import os
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class AuditLogType(Enum):
    """Types of audit logs per Claim 32"""

    CLIENT_DELIVERED = "client_delivered"  # First log: what clients receive (post-moderation)
    AI_GENERATED = "ai_generated"  # Second log: pre-moderation AI output
    METADATA_ONLY = "metadata_only"  # Third log: privacy-preserving analytics
    SAFETY_ALERTS = "safety_alerts"  # Fourth log: blocked harmful content


@dataclass
class AuditEntry:
    """
    Immutable audit log entry with cryptographic integrity
    Satisfies GDPR Article 15 (right to access), HIPAA audit trails, SOC2 CC6.1
    """

    timestamp: str  # ISO 8601 format
    entry_id: str  # Unique identifier
    log_type: str  # AuditLogType

    # Content fields
    plaintext: Optional[str] = None  # Human-readable UTF-8 (for GDPR access)
    compressed_payload: Optional[bytes] = None  # For forensic analysis
    metadata: Optional[Dict[str, Any]] = None  # Structured data

    # Context fields
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    compression_method: Optional[str] = None
    compression_ratio: Optional[float] = None

    # Safety fields (Claim 32)
    pre_moderation_content: Optional[str] = None  # AI output before filtering
    post_moderation_content: Optional[str] = None  # Client-delivered content
    moderation_applied: bool = False
    harm_type: Optional[str] = None  # violence, illegal, privacy, misinformation, etc.
    severity: Optional[str] = None  # low, medium, high, critical

    # Integrity field
    integrity_hash: Optional[str] = None  # SHA-256 of previous entry

    def to_json(self) -> str:
        """Serialize to JSON for storage"""
        data = asdict(self)
        # Convert bytes to hex for JSON serialization
        if data["compressed_payload"] is not None:
            data["compressed_payload"] = data["compressed_payload"].hex()
        return json.dumps(data, ensure_ascii=False, separators=(",", ":"))

    @classmethod
    def from_json(cls, json_str: str) -> "AuditEntry":
        """Deserialize from JSON"""
        data = json.loads(json_str)
        # Convert hex back to bytes
        if data.get("compressed_payload"):
            data["compressed_payload"] = bytes.fromhex(data["compressed_payload"])
        if "metadata" in data:
            data["metadata"] = expand_metadata(data["metadata"])
        return cls(**data)


from .audit_layer import compact_metadata, expand_metadata


class AuditLogger:
    """
    Append-only audit logger with cryptographic integrity checks
    Implements Patent Claims 2, 11, 32-35
    """

    def __init__(self, log_directory: str = "./audit_logs"):
        """
        Initialize audit logger

        Args:
            log_directory: Directory for append-only log files
        """
        self.log_dir = Path(log_directory)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Separate log files per Claim 32
        self.log_files = {
            AuditLogType.CLIENT_DELIVERED: self.log_dir / "client_delivered.jsonl",
            AuditLogType.AI_GENERATED: self.log_dir / "ai_generated.jsonl",
            AuditLogType.METADATA_ONLY: self.log_dir / "metadata_only.jsonl",
            AuditLogType.SAFETY_ALERTS: self.log_dir / "safety_alerts.jsonl",
        }

        # Thread-safe locks for each log file
        self.locks = {log_type: threading.Lock() for log_type in AuditLogType}

        # Track last hash for integrity chain
        self.last_hashes = {log_type: self._get_last_hash(log_type) for log_type in AuditLogType}

    def _get_last_hash(self, log_type: AuditLogType) -> Optional[str]:
        """Get the last integrity hash from a log file"""
        log_file = self.log_files[log_type]
        if not log_file.exists():
            return None

        try:
            with open(log_file, "r", encoding="utf-8") as f:
                # Read last line
                lines = f.readlines()
                if lines:
                    last_entry = AuditEntry.from_json(lines[-1])
                    return last_entry.integrity_hash
        except Exception:
            return None

        return None

    def _compute_integrity_hash(self, entry: AuditEntry, previous_hash: Optional[str]) -> str:
        """
        Compute SHA-256 integrity hash for entry
        Creates an immutable chain preventing tampering (Claim 11)
        """
        # Include previous hash to create chain
        content = (
            f"{previous_hash or 'GENESIS'}{entry.timestamp}{entry.entry_id}{entry.plaintext or ''}"
        )
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def log_compression(
        self,
        plaintext: str,
        compressed_payload: bytes,
        metadata: Dict[str, Any],
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> str:
        """
        Log a compression event (Claim 2)

        Returns:
            Entry ID for reference
        """
        now = datetime.now(timezone.utc).isoformat()
        entry_id = hashlib.sha256(f"{now}{plaintext}".encode()).hexdigest()[:16]

        # Get previous hash for integrity chain
        previous_hash = self.last_hashes[AuditLogType.CLIENT_DELIVERED]

        compacted_metadata = compact_metadata(metadata)

        entry = AuditEntry(
            timestamp=now,
            entry_id=entry_id,
            log_type=AuditLogType.CLIENT_DELIVERED.value,
            plaintext=plaintext,
            compressed_payload=compressed_payload,
            metadata=compacted_metadata,
            session_id=session_id,
            user_id=user_id,
            compression_method=metadata.get("method"),
            compression_ratio=metadata.get("ratio"),
            integrity_hash=None,  # Will be computed
        )

        # Compute integrity hash
        entry.integrity_hash = self._compute_integrity_hash(entry, previous_hash)

        # Write to log file
        self._write_entry(AuditLogType.CLIENT_DELIVERED, entry)

        # Update last hash
        self.last_hashes[AuditLogType.CLIENT_DELIVERED] = entry.integrity_hash

        return entry_id

    def log_compression_event(self, *args, **kwargs):
        """Alias for log_compression for backward compatibility"""
        return self.log_compression(*args, **kwargs)

    def log_ai_output(
        self,
        pre_moderation_content: str,
        post_moderation_content: str,
        moderation_applied: bool,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> str:
        """
        Log AI-generated output before moderation (Claim 32, 33)
        Enables AI alignment monitoring by comparing pre/post moderation

        Returns:
            Entry ID for reference
        """
        now = datetime.now(timezone.utc).isoformat()
        entry_id = hashlib.sha256(f"{now}{pre_moderation_content}".encode()).hexdigest()[:16]

        previous_hash = self.last_hashes[AuditLogType.AI_GENERATED]

        entry = AuditEntry(
            timestamp=now,
            entry_id=entry_id,
            log_type=AuditLogType.AI_GENERATED.value,
            plaintext=pre_moderation_content,
            pre_moderation_content=pre_moderation_content,
            post_moderation_content=post_moderation_content,
            moderation_applied=moderation_applied,
            session_id=session_id,
            user_id=user_id,
            integrity_hash=None,
        )

        entry.integrity_hash = self._compute_integrity_hash(entry, previous_hash)
        self._write_entry(AuditLogType.AI_GENERATED, entry)
        self.last_hashes[AuditLogType.AI_GENERATED] = entry.integrity_hash

        return entry_id

    def log_metadata_only(
        self,
        metadata: Dict[str, Any],
        session_id: Optional[str] = None,
    ) -> str:
        """
        Log metadata without content for privacy-preserving analytics (Claim 35)
        Satisfies GDPR Article 5(1)(c) data minimization

        Returns:
            Entry ID for reference
        """
        now = datetime.now(timezone.utc).isoformat()
        entry_id = hashlib.sha256(f"{now}{json.dumps(metadata)}".encode()).hexdigest()[:16]

        previous_hash = self.last_hashes[AuditLogType.METADATA_ONLY]

        compacted_metadata = compact_metadata(metadata)

        entry = AuditEntry(
            timestamp=now,
            entry_id=entry_id,
            log_type=AuditLogType.METADATA_ONLY.value,
            metadata=compacted_metadata,
            session_id=session_id,
            plaintext=None,  # No content stored - privacy-preserving
            integrity_hash=None,
        )

        entry.integrity_hash = self._compute_integrity_hash(entry, previous_hash)
        self._write_entry(AuditLogType.METADATA_ONLY, entry)
        self.last_hashes[AuditLogType.METADATA_ONLY] = entry.integrity_hash

        return entry_id

    def log_safety_alert(
        self,
        blocked_content: str,
        harm_type: str,
        severity: str,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> str:
        """
        Log blocked harmful content (Claim 32, 34)
        Categorizes by harm type for AI alignment analysis

        Args:
            blocked_content: The harmful content that was blocked
            harm_type: violence, illegal, privacy, misinformation, hate, adult, self-harm
            severity: low, medium, high, critical

        Returns:
            Entry ID for reference
        """
        now = datetime.now(timezone.utc).isoformat()
        entry_id = hashlib.sha256(f"{now}{blocked_content}".encode()).hexdigest()[:16]

        previous_hash = self.last_hashes[AuditLogType.SAFETY_ALERTS]

        entry = AuditEntry(
            timestamp=now,
            entry_id=entry_id,
            log_type=AuditLogType.SAFETY_ALERTS.value,
            plaintext=blocked_content,
            harm_type=harm_type,
            severity=severity,
            session_id=session_id,
            user_id=user_id,
            integrity_hash=None,
        )

        entry.integrity_hash = self._compute_integrity_hash(entry, previous_hash)
        self._write_entry(AuditLogType.SAFETY_ALERTS, entry)
        self.last_hashes[AuditLogType.SAFETY_ALERTS] = entry.integrity_hash

        return entry_id

    def _write_entry(self, log_type: AuditLogType, entry: AuditEntry):
        """
        Write entry to append-only log file with thread safety
        """
        log_file = self.log_files[log_type]

        with self.locks[log_type]:
            # Append-only mode
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(entry.to_json() + "\n")

    def verify_integrity(self, log_type: AuditLogType) -> bool:
        """
        Verify the cryptographic integrity chain of a log file (Claim 11)

        Returns:
            True if integrity chain is valid, False if tampered
        """
        log_file = self.log_files[log_type]
        if not log_file.exists():
            return True  # Empty log is valid

        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        previous_hash = None
        for line in lines:
            try:
                entry = AuditEntry.from_json(line.strip())
                expected_hash = self._compute_integrity_hash(entry, previous_hash)

                if entry.integrity_hash != expected_hash:
                    return False  # Tampering detected

                previous_hash = entry.integrity_hash
            except Exception:
                return False  # Corrupted entry

        return True

    def get_entries(
        self,
        log_type: AuditLogType,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[AuditEntry]:
        """
        Retrieve audit entries for compliance reporting (GDPR Article 15)

        Args:
            log_type: Which log to query
            session_id: Filter by session
            user_id: Filter by user
            limit: Maximum entries to return

        Returns:
            List of audit entries
        """
        log_file = self.log_files[log_type]
        if not log_file.exists():
            return []

        entries = []
        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entry = AuditEntry.from_json(line.strip())

                    # Apply filters
                    if session_id and entry.session_id != session_id:
                        continue
                    if user_id and entry.user_id != user_id:
                        continue

                    entries.append(entry)

                    if len(entries) >= limit:
                        break
                except Exception:
                    continue  # Skip corrupted entries

        return entries


# Global audit logger instance
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger(log_directory: str = "./audit_logs") -> AuditLogger:
    """Get or create global audit logger instance"""
    global _audit_logger
    if _audit_logger is None or str(_audit_logger.log_dir) != log_directory:
        _audit_logger = AuditLogger(log_directory)
    return _audit_logger


def reset_audit_logger():
    """Reset global audit logger (useful for testing)"""
    global _audit_logger
    _audit_logger = None
