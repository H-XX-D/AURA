#!/usr/bin/env python3
"""
AURA Separated Audit Architecture

Implements Claims 32-34: Regulatory compliance with separated audit logs for
simultaneous regulatory compliance and AI alignment oversight.

Four Audit Logs:
1. Client Conversation Log (post-moderation) - GDPR/HIPAA/SOC2 compliance
2. AI Output Log (pre-moderation) - AI alignment research
3. Metadata Analytics Log (privacy-preserving) - Performance monitoring
4. Safety Alerts Log - Harm detection and blocking

Copyright (c) 2025 Todd James Hendricks
Licensed under Apache License 2.0
Patent Pending - Application No. 19/366,538
"""

import time
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import IntEnum
from datetime import datetime, timezone
import hashlib


class HarmType(IntEnum):
    """Types of harmful content (Claim 34)"""
    VIOLENCE = 1
    HATE_SPEECH = 2
    SEXUAL_CONTENT = 3
    DANGEROUS_ACTIVITIES = 4
    MISINFORMATION = 5
    PII_EXPOSURE = 6
    MALWARE = 7
    HARASSMENT = 8


class HarmSeverity(IntEnum):
    """Severity levels for harmful content (Claim 34)"""
    LOW = 1  # Minor concern, logged only
    MEDIUM = 2  # Significant concern, filtered
    HIGH = 3  # Serious concern, blocked
    CRITICAL = 4  # Severe harm, blocked + escalated


@dataclass
class ConversationEntry:
    """
    Entry for first audit log: Client conversation history (Claim 32i)

    Records what clients actually received after content moderation.
    Complies with:
    - GDPR Article 15: Right to access
    - HIPAA 45 CFR §164.312(b): Audit trail requirements
    - SOC2 CC6.1: Logging standards
    """
    timestamp: str  # ISO 8601 format
    conversation_id: str  # Unique conversation identifier
    user_id: str  # User identifier (hashed for privacy)
    role: str  # 'user' or 'assistant'
    message: str  # Human-readable UTF-8 plaintext
    message_id: str  # Unique message identifier
    moderation_applied: bool  # Whether content was moderated
    compressed_size: int  # Size of compressed message
    compression_ratio: float  # Compression ratio achieved


@dataclass
class AIOutputEntry:
    """
    Entry for second audit log: AI-generated responses (Claim 32ii)

    Records what AI systems originally generated BEFORE content moderation.
    Enables AI alignment research and safety analysis.
    """
    timestamp: str  # ISO 8601 format
    conversation_id: str  # Unique conversation identifier
    message_id: str  # Unique message identifier
    ai_model: str  # AI model identifier
    raw_output: str  # Original AI output (pre-moderation)
    prompt_hash: str  # Hash of user prompt (for privacy)
    generation_params: Dict[str, Any]  # Temperature, top_p, etc.
    safety_score: float  # AI safety confidence score
    flagged_for_review: bool  # Whether output was flagged


@dataclass
class MetadataAnalyticsEntry:
    """
    Entry for third audit log: Metadata-only analytics (Claim 32iii)

    Records performance metrics WITHOUT message content for privacy.
    Complies with GDPR Article 5(1)(c): Data minimization principle.
    """
    timestamp: str  # ISO 8601 format
    conversation_id: str  # Unique conversation identifier
    message_id: str  # Unique message identifier
    compression_method: str  # Compression method used
    original_size: int  # Original message size
    compressed_size: int  # Compressed size
    compression_ratio: float  # Compression ratio
    template_id: Optional[int]  # Template ID if applicable
    category: str  # Message category
    processing_time_ms: float  # Processing time
    cache_hit: bool  # Whether cache was used
    metadata_only: bool  # Whether processed without decompression


@dataclass
class SafetyAlertEntry:
    """
    Entry for fourth audit log: Safety alerts (Claim 32iv)

    Records when harmful content is detected and blocked.
    Includes harm type categorization and severity assessment.
    """
    timestamp: str  # ISO 8601 format
    conversation_id: str  # Unique conversation identifier
    message_id: str  # Unique message identifier
    user_id_hash: str  # Hashed user identifier
    harm_type: HarmType  # Type of harmful content
    severity: HarmSeverity  # Severity level
    detection_method: str  # How harm was detected
    confidence: float  # Detection confidence score
    blocked: bool  # Whether message was blocked
    original_content_hash: str  # Hash of harmful content (not plaintext)
    moderator_notes: str  # Human moderator notes if reviewed


class SeparatedAuditSystem:
    """
    Separated Audit Architecture (Claims 32-34)

    Maintains four separate server-side audit logs:
    1. Client conversation log (post-moderation) - Regulatory compliance
    2. AI output log (pre-moderation) - AI alignment research
    3. Metadata analytics log (content-free) - Privacy-preserving metrics
    4. Safety alerts log - Harm detection and blocking

    Key Innovation:
    - Simultaneous regulatory compliance AND AI alignment oversight
    - Never transmits harmful pre-moderation content to clients
    - Privacy-preserving analytics through metadata-only logging
    - Complete audit trail for GDPR, HIPAA, and SOC2 compliance
    """

    def __init__(self, log_dir: str = "/tmp/aura_audit_logs"):
        self.log_dir = log_dir

        # Four separate audit logs (server-side only)
        self.conversation_log: List[ConversationEntry] = []  # Claim 32i
        self.ai_output_log: List[AIOutputEntry] = []  # Claim 32ii
        self.metadata_log: List[MetadataAnalyticsEntry] = []  # Claim 32iii
        self.safety_log: List[SafetyAlertEntry] = []  # Claim 32iv

        # Statistics
        self.stats = {
            'total_messages': 0,
            'moderated_messages': 0,
            'blocked_messages': 0,
            'ai_outputs_logged': 0,
            'safety_alerts': 0,
        }

    def log_conversation_message(self,
                                  conversation_id: str,
                                  user_id: str,
                                  role: str,
                                  message: str,
                                  message_id: str,
                                  moderation_applied: bool,
                                  compressed_size: int,
                                  compression_ratio: float):
        """
        Log to first audit log: Client conversation (Claim 32i)

        Records what clients actually received after content moderation.

        Compliance:
        - GDPR Article 15: Right to access personal data
        - HIPAA 45 CFR §164.312(b): Audit controls
        - SOC2 CC6.1: Logical access controls - Audit logging

        Args:
            conversation_id: Conversation identifier
            user_id: User identifier
            role: 'user' or 'assistant'
            message: Final message delivered to client (post-moderation)
            message_id: Unique message identifier
            moderation_applied: Whether content was filtered
            compressed_size: Compressed message size
            compression_ratio: Compression ratio achieved
        """
        entry = ConversationEntry(
            timestamp=datetime.now(timezone.utc).isoformat() + 'Z',
            conversation_id=conversation_id,
            user_id=self._hash_user_id(user_id),  # Hash for privacy
            role=role,
            message=message,  # Human-readable UTF-8 plaintext
            message_id=message_id,
            moderation_applied=moderation_applied,
            compressed_size=compressed_size,
            compression_ratio=compression_ratio,
        )

        self.conversation_log.append(entry)
        self.stats['total_messages'] += 1

        if moderation_applied:
            self.stats['moderated_messages'] += 1

    def log_ai_output(self,
                      conversation_id: str,
                      message_id: str,
                      ai_model: str,
                      raw_output: str,
                      prompt: str,
                      generation_params: Dict[str, Any],
                      safety_score: float,
                      flagged: bool):
        """
        Log to second audit log: AI output (Claim 32ii)

        Records what AI originally generated BEFORE moderation.
        Enables AI alignment research and safety analysis.

        IMPORTANT: Never transmitted to clients (Claim 32f)

        Args:
            conversation_id: Conversation identifier
            message_id: Unique message identifier
            ai_model: AI model used
            raw_output: Original AI output (pre-moderation)
            prompt: User prompt
            generation_params: Model parameters
            safety_score: Safety confidence score
            flagged: Whether output was flagged for review
        """
        entry = AIOutputEntry(
            timestamp=datetime.now(timezone.utc).isoformat() + 'Z',
            conversation_id=conversation_id,
            message_id=message_id,
            ai_model=ai_model,
            raw_output=raw_output,  # Pre-moderation output
            prompt_hash=self._hash_content(prompt),  # Hash prompt for privacy
            generation_params=generation_params,
            safety_score=safety_score,
            flagged_for_review=flagged,
        )

        self.ai_output_log.append(entry)
        self.stats['ai_outputs_logged'] += 1

    def log_metadata_analytics(self,
                                conversation_id: str,
                                message_id: str,
                                compression_method: str,
                                original_size: int,
                                compressed_size: int,
                                compression_ratio: float,
                                template_id: Optional[int],
                                category: str,
                                processing_time_ms: float,
                                cache_hit: bool,
                                metadata_only: bool):
        """
        Log to third audit log: Metadata analytics (Claim 32iii)

        Records performance metrics WITHOUT message content.

        Compliance:
        - GDPR Article 5(1)(c): Data minimization principle
        - Privacy-preserving performance monitoring

        Args:
            conversation_id: Conversation identifier
            message_id: Message identifier
            compression_method: Compression method used
            original_size: Original message size
            compressed_size: Compressed size
            compression_ratio: Compression ratio
            template_id: Template ID if applicable
            category: Message category
            processing_time_ms: Processing time
            cache_hit: Whether cache was used
            metadata_only: Whether processed without decompression
        """
        entry = MetadataAnalyticsEntry(
            timestamp=datetime.now(timezone.utc).isoformat() + 'Z',
            conversation_id=conversation_id,
            message_id=message_id,
            compression_method=compression_method,
            original_size=original_size,
            compressed_size=compressed_size,
            compression_ratio=compression_ratio,
            template_id=template_id,
            category=category,
            processing_time_ms=processing_time_ms,
            cache_hit=cache_hit,
            metadata_only=metadata_only,
        )

        self.metadata_log.append(entry)

    def log_safety_alert(self,
                         conversation_id: str,
                         message_id: str,
                         user_id: str,
                         harm_type: HarmType,
                         severity: HarmSeverity,
                         detection_method: str,
                         confidence: float,
                         blocked: bool,
                         harmful_content: str,
                         moderator_notes: str = ""):
        """
        Log to fourth audit log: Safety alerts (Claim 32iv)

        Records harmful content detection and blocking.

        Includes:
        - Harm type categorization
        - Severity assessment
        - Detection confidence
        - Whether content was blocked

        IMPORTANT: Stores hash of harmful content, not plaintext (Claim 32f)

        Args:
            conversation_id: Conversation identifier
            message_id: Message identifier
            user_id: User identifier
            harm_type: Type of harmful content
            severity: Severity level
            detection_method: Detection method used
            confidence: Detection confidence
            blocked: Whether message was blocked
            harmful_content: Harmful content (hashed, not stored as plaintext)
            moderator_notes: Human moderator notes
        """
        entry = SafetyAlertEntry(
            timestamp=datetime.now(timezone.utc).isoformat() + 'Z',
            conversation_id=conversation_id,
            message_id=message_id,
            user_id_hash=self._hash_user_id(user_id),
            harm_type=harm_type,
            severity=severity,
            detection_method=detection_method,
            confidence=confidence,
            blocked=blocked,
            original_content_hash=self._hash_content(harmful_content),  # Hash only!
            moderator_notes=moderator_notes,
        )

        self.safety_log.append(entry)
        self.stats['safety_alerts'] += 1

        if blocked:
            self.stats['blocked_messages'] += 1

    def export_conversation_log(self, format: str = 'json') -> str:
        """
        Export first audit log (Claim 32d, 32i)

        Provides human-readable conversation history for regulatory compliance.

        Satisfies:
        - GDPR Article 15: Right to access
        - HIPAA 45 CFR §164.312(b): Audit trail
        - SOC2 CC6.1: Logging standards

        Args:
            format: Export format ('json' or 'text')

        Returns:
            Formatted audit log
        """
        if format == 'json':
            return json.dumps([asdict(entry) for entry in self.conversation_log], indent=2)
        elif format == 'text':
            lines = []
            lines.append("=" * 80)
            lines.append("CLIENT CONVERSATION AUDIT LOG (Post-Moderation)")
            lines.append("Compliance: GDPR Article 15, HIPAA 45 CFR §164.312(b), SOC2 CC6.1")
            lines.append("=" * 80)

            for entry in self.conversation_log:
                lines.append(f"\n[{entry.timestamp}] {entry.role.upper()}")
                lines.append(f"Conversation: {entry.conversation_id}")
                lines.append(f"Message ID: {entry.message_id}")
                lines.append(f"User: {entry.user_id}")
                lines.append(f"Moderated: {'Yes' if entry.moderation_applied else 'No'}")
                lines.append(f"Message:\n{entry.message}")
                lines.append("-" * 80)

            return '\n'.join(lines)
        else:
            raise ValueError(f"Unknown format: {format}")

    def export_ai_output_log(self, format: str = 'json') -> str:
        """
        Export second audit log (Claim 32e, 32ii)

        Provides pre-moderation AI outputs for alignment research.

        IMPORTANT: Server-side only, never transmitted to clients (Claim 32f)

        Args:
            format: Export format ('json' or 'text')

        Returns:
            Formatted audit log
        """
        if format == 'json':
            return json.dumps([asdict(entry) for entry in self.ai_output_log], indent=2)
        elif format == 'text':
            lines = []
            lines.append("=" * 80)
            lines.append("AI OUTPUT AUDIT LOG (Pre-Moderation)")
            lines.append("Purpose: AI Alignment Research")
            lines.append("CONFIDENTIAL: Server-side only - Never transmitted to clients")
            lines.append("=" * 80)

            for entry in self.ai_output_log:
                lines.append(f"\n[{entry.timestamp}]")
                lines.append(f"Conversation: {entry.conversation_id}")
                lines.append(f"Message ID: {entry.message_id}")
                lines.append(f"AI Model: {entry.ai_model}")
                lines.append(f"Safety Score: {entry.safety_score:.2f}")
                lines.append(f"Flagged: {'Yes' if entry.flagged_for_review else 'No'}")
                lines.append(f"Raw Output:\n{entry.raw_output}")
                lines.append("-" * 80)

            return '\n'.join(lines)
        else:
            raise ValueError(f"Unknown format: {format}")

    def export_metadata_log(self, format: str = 'json') -> str:
        """
        Export third audit log (Claim 32iii)

        Provides privacy-preserving performance analytics.

        Compliance:
        - GDPR Article 5(1)(c): Data minimization

        Args:
            format: Export format

        Returns:
            Formatted audit log
        """
        if format == 'json':
            return json.dumps([asdict(entry) for entry in self.metadata_log], indent=2)
        else:
            raise ValueError(f"Unsupported format: {format}")

    def export_safety_log(self, format: str = 'json') -> str:
        """
        Export fourth audit log (Claim 32iv)

        Provides safety alert history with harm categorization.

        Args:
            format: Export format

        Returns:
            Formatted audit log
        """
        if format == 'json':
            return json.dumps([asdict(entry) for entry in self.safety_log], indent=2)
        elif format == 'text':
            lines = []
            lines.append("=" * 80)
            lines.append("SAFETY ALERTS AUDIT LOG")
            lines.append("Harmful Content Detection and Blocking")
            lines.append("=" * 80)

            for entry in self.safety_log:
                lines.append(f"\n[{entry.timestamp}] SEVERITY: {entry.severity.name}")
                lines.append(f"Conversation: {entry.conversation_id}")
                lines.append(f"Message ID: {entry.message_id}")
                lines.append(f"Harm Type: {entry.harm_type.name}")
                lines.append(f"Detection Method: {entry.detection_method}")
                lines.append(f"Confidence: {entry.confidence:.2%}")
                lines.append(f"Blocked: {'Yes' if entry.blocked else 'No'}")
                lines.append(f"Content Hash: {entry.original_content_hash}")
                if entry.moderator_notes:
                    lines.append(f"Notes: {entry.moderator_notes}")
                lines.append("-" * 80)

            return '\n'.join(lines)
        else:
            raise ValueError(f"Unknown format: {format}")

    def get_statistics(self) -> Dict[str, Any]:
        """Get audit system statistics"""
        return {
            **self.stats,
            'conversation_entries': len(self.conversation_log),
            'ai_output_entries': len(self.ai_output_log),
            'metadata_entries': len(self.metadata_log),
            'safety_entries': len(self.safety_log),
            'moderation_rate': self.stats['moderated_messages'] / self.stats['total_messages'] if self.stats['total_messages'] > 0 else 0.0,
            'block_rate': self.stats['blocked_messages'] / self.stats['total_messages'] if self.stats['total_messages'] > 0 else 0.0,
        }

    def _hash_user_id(self, user_id: str) -> str:
        """Hash user ID for privacy"""
        return hashlib.sha256(user_id.encode()).hexdigest()[:16]

    def _hash_content(self, content: str) -> str:
        """Hash content for privacy (stores hash, not plaintext)"""
        return hashlib.sha256(content.encode()).hexdigest()
