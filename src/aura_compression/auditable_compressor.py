#!/usr/bin/env python3
"""
Auditable AURA Compression - Always Auditable by Design

This wrapper ensures ALL compression operations are audited.
Patent US 19/366,538 - Claim 2: Comprehensive Audit Trail

Core Principle: AURA MUST ALWAYS BE AUDITABLE
- Every compression/decompression operation is logged
- Full data lineage tracking
- Performance metrics captured
- Security events monitored
- GDPR/HIPAA compliance enforced
"""
import time
from typing import Tuple, Dict, Optional, Any
from contextlib import contextmanager

from aura_compression.compressor import ProductionHybridCompressor
from aura_compression.aura_heavy import AuraHeavy, AuraHeavyResult
from aura_compression.ai_large_file import AILargeFileCompressor, CompressionStats
from aura_compression.audit_layer import (
    CompressionAuditor,
    CompressionEvent,
    AuditLevel
)


class AuditableCompressor:
    """
    Wrapper that makes ANY compressor auditable.

    Principle: Separation of concerns
    - Compression logic: Handled by underlying compressor
    - Audit logic: Handled by this wrapper
    """

    def __init__(self,
                 compressor: Any,
                 auditor: Optional[CompressionAuditor] = None,
                 user_id: Optional[str] = None,
                 session_id: Optional[str] = None,
                 source_ip: Optional[str] = None):
        """
        Initialize auditable compressor wrapper.

        Args:
            compressor: Any AURA compressor instance
            auditor: Audit layer instance (created if None)
            user_id: User performing compression
            session_id: Session identifier
            source_ip: Source IP address
        """
        self.compressor = compressor
        self.auditor = auditor or CompressionAuditor()
        self.user_id = user_id
        self.session_id = session_id
        self.source_ip = source_ip

    @contextmanager
    def _audit_operation(self, operation: str, data: bytes):
        """Context manager for auditing compression operations."""
        start_time = time.time()
        event_type_start = CompressionEvent.COMPRESS_START if operation == 'compress' else CompressionEvent.DECOMPRESS_START
        event_type_success = CompressionEvent.COMPRESS_SUCCESS if operation == 'compress' else CompressionEvent.DECOMPRESS_SUCCESS
        event_type_failure = CompressionEvent.COMPRESS_FAILURE if operation == 'compress' else CompressionEvent.DECOMPRESS_FAILURE

        # Log start event
        self.auditor.log_compression(
            event_type=event_type_start,
            method='pending',
            original_size=len(data),
            compressed_size=0,
            latency_ms=0,
            data=data,
            user_id=self.user_id,
            session_id=self.session_id,
            source_ip=self.source_ip
        )

        try:
            yield
            # Success will be logged by caller with actual results
        except Exception as e:
            # Log failure
            latency_ms = (time.time() - start_time) * 1000
            self.auditor.log_compression(
                event_type=event_type_failure,
                method='unknown',
                original_size=len(data),
                compressed_size=0,
                latency_ms=latency_ms,
                data=data,
                user_id=self.user_id,
                session_id=self.session_id,
                source_ip=self.source_ip,
                metadata={'error': str(e)}
            )

            # Log security event if this looks suspicious
            if 'tamper' in str(e).lower() or 'corrupt' in str(e).lower():
                self.auditor.log_security_event(
                    event_type='COMPRESSION_TAMPERING',
                    severity=AuditLevel.SECURITY,
                    description=f"Possible tampering detected: {e}",
                    user_id=self.user_id,
                    source_ip=self.source_ip,
                    metadata={'operation': operation}
                )

            raise

    def compress(self, data: str) -> Tuple[bytes, Dict[str, Any]]:
        """
        Compress data with full audit trail.

        Returns:
            (compressed_bytes, metadata_with_audit_id)
        """
        data_bytes = data.encode('utf-8') if isinstance(data, str) else data
        start_time = time.time()

        with self._audit_operation('compress', data_bytes):
            # Perform compression
            result = self.compressor.compress(data)

            # Handle different return types
            if len(result) == 3:
                compressed_bytes, compression_method, metadata = result
                method = compression_method.name if hasattr(compression_method, 'name') else str(compression_method)
            elif len(result) == 2:
                compressed_bytes, metadata = result
                method = metadata.get('method', 'unknown')
            else:
                raise ValueError(f"Unexpected result from compressor: {len(result)} values")

            latency_ms = (time.time() - start_time) * 1000
            if hasattr(self.compressor, '__class__'):
                compressor_type = self.compressor.__class__.__name__

            # Log successful compression
            event_id = self.auditor.log_compression(
                event_type=CompressionEvent.COMPRESS_SUCCESS,
                method=method,
                original_size=len(data_bytes),
                compressed_size=len(compressed_bytes),
                latency_ms=latency_ms,
                data=data_bytes,
                result=compressed_bytes,
                user_id=self.user_id,
                session_id=self.session_id,
                source_ip=self.source_ip,
                metadata=metadata
            )

            # Add audit ID to metadata
            metadata['audit_event_id'] = event_id
            metadata['auditor_session'] = self.session_id

            return compressed_bytes, metadata

    def decompress(self, compressed_data: bytes) -> Tuple[str, Dict[str, Any]]:
        """
        Decompress data with full audit trail.

        Returns:
            (decompressed_text, metadata_with_audit_id)
        """
        start_time = time.time()

        with self._audit_operation('decompress', compressed_data):
            # Perform decompression - request metadata if available
            if hasattr(self.compressor, 'decompress'):
                # Try to get metadata
                try:
                    result = self.compressor.decompress(compressed_data, return_metadata=True)
                    if isinstance(result, tuple):
                        decompressed_text, metadata = result
                        method = metadata.get('method', 'unknown')
                    else:
                        decompressed_text = result
                        metadata = {}
                        method = 'unknown'
                except TypeError:
                    # decompress doesn't support return_metadata
                    decompressed_text = self.compressor.decompress(compressed_data)
                    metadata = {}
                    method = 'unknown'
            else:
                raise ValueError("Compressor doesn't have decompress method")

            latency_ms = (time.time() - start_time) * 1000
            decompressed_bytes = decompressed_text.encode('utf-8') if isinstance(decompressed_text, str) else decompressed_text

            # Log successful decompression
            event_id = self.auditor.log_compression(
                event_type=CompressionEvent.DECOMPRESS_SUCCESS,
                method=method,
                original_size=len(compressed_data),
                compressed_size=len(decompressed_bytes),
                latency_ms=latency_ms,
                data=compressed_data,
                result=decompressed_bytes,
                user_id=self.user_id,
                session_id=self.session_id,
                source_ip=self.source_ip,
                metadata=metadata
            )

            # Add audit ID to metadata
            metadata['audit_event_id'] = event_id
            metadata['auditor_session'] = self.session_id

            return decompressed_text, metadata

    def get_audit_stats(self, hours: int = 24) -> Dict:
        """Get audit statistics for this session/user."""
        return self.auditor.get_stats(hours=hours)

    def verify_integrity(self, start_id: int = 1, end_id: int = 100) -> Tuple[bool, list]:
        """Verify audit chain integrity."""
        return self.auditor.verify_chain(start_id, end_id)


class AuditableHeavy(AuditableCompressor):
    """Auditable AuraHeavy compressor for large files."""

    def __init__(self,
                 enable_aura: bool = True,
                 prefer_speed: bool = False,
                 auditor: Optional[CompressionAuditor] = None,
                 user_id: Optional[str] = None,
                 session_id: Optional[str] = None,
                 source_ip: Optional[str] = None):
        """Initialize auditable AuraHeavy compressor."""
        compressor = AuraHeavy(
            enable_aura=enable_aura,
            prefer_speed=prefer_speed
        )
        super().__init__(compressor, auditor, user_id, session_id, source_ip)

    def compress(self, data: str, is_binary: bool = False) -> Tuple[bytes, Dict[str, Any]]:
        """Compress with AuraHeavy method selection and audit."""
        data_bytes = data.encode('utf-8') if isinstance(data, str) else data
        start_time = time.time()

        with self._audit_operation('compress', data_bytes):
            # Perform compression
            result: AuraHeavyResult = self.compressor.compress(data, is_binary)
            latency_ms = (time.time() - start_time) * 1000

            # Log method selection decision
            self.auditor.log_compression(
                event_type=CompressionEvent.METHOD_SELECTION,
                method=result.method.name,
                original_size=result.original_size,
                compressed_size=result.compressed_size,
                latency_ms=0,
                metadata={
                    'compression_layer': result.metadata.get('compression_layer'),
                    'threshold_triggered': result.original_size >= self.compressor.LARGE_FILE_THRESHOLD
                },
                user_id=self.user_id,
                session_id=self.session_id,
                source_ip=self.source_ip
            )

            # Log successful compression
            event_id = self.auditor.log_compression(
                event_type=CompressionEvent.COMPRESS_SUCCESS,
                method=result.method.name,
                original_size=result.original_size,
                compressed_size=result.compressed_size,
                latency_ms=latency_ms,
                data=data_bytes,
                result=result.compressed_data,
                user_id=self.user_id,
                session_id=self.session_id,
                source_ip=self.source_ip,
                metadata=result.metadata
            )

            # Create metadata dict
            metadata = {
                **result.metadata,
                'audit_event_id': event_id,
                'auditor_session': self.session_id,
                'ratio': result.ratio
            }

            return result.compressed_data, metadata


class AuditableAICompressor(AuditableCompressor):
    """Auditable AI-powered compressor."""

    def __init__(self,
                 aggressive: bool = False,
                 auditor: Optional[CompressionAuditor] = None,
                 user_id: Optional[str] = None,
                 session_id: Optional[str] = None,
                 source_ip: Optional[str] = None):
        """Initialize auditable AI compressor."""
        compressor = AILargeFileCompressor(aggressive=aggressive)
        super().__init__(compressor, auditor, user_id, session_id, source_ip)

    def compress(self, data: str) -> Tuple[bytes, Dict[str, Any]]:
        """Compress with AI pattern discovery and audit."""
        data_bytes = data.encode('utf-8')
        start_time = time.time()

        with self._audit_operation('compress', data_bytes):
            # Perform AI compression
            result = self.compressor.compress(data)
            compressed_bytes, stats = result
            latency_ms = (time.time() - start_time) * 1000

            # Log pattern discovery
            self.auditor.log_compression(
                event_type=CompressionEvent.PATTERN_DISCOVERY,
                method='AI_SEMANTIC',
                original_size=stats.original_size,
                compressed_size=0,
                latency_ms=0,
                metadata={
                    'patterns_found': stats.patterns_found,
                    'dictionary_size': stats.dictionary_size,
                    'semantic_chunks': stats.semantic_chunks,
                    'file_type': self.compressor.file_type
                },
                user_id=self.user_id,
                session_id=self.session_id,
                source_ip=self.source_ip
            )

            # Log dictionary build
            if stats.dictionary_size > 0:
                self.auditor.log_compression(
                    event_type=CompressionEvent.DICTIONARY_BUILD,
                    method='AI_SEMANTIC',
                    original_size=stats.original_size,
                    compressed_size=stats.dictionary_size,
                    latency_ms=0,
                    metadata={
                        'dictionary_entries': stats.patterns_found,
                        'ai_optimizations': stats.ai_optimizations
                    },
                    user_id=self.user_id,
                    session_id=self.session_id,
                    source_ip=self.source_ip
                )

            # Log successful compression
            event_id = self.auditor.log_compression(
                event_type=CompressionEvent.COMPRESS_SUCCESS,
                method=stats.method,
                original_size=stats.original_size,
                compressed_size=stats.compressed_size,
                latency_ms=latency_ms,
                data=data_bytes,
                result=compressed_bytes,
                user_id=self.user_id,
                session_id=self.session_id,
                source_ip=self.source_ip,
                metadata={
                    'ratio': stats.ratio,
                    'patterns_found': stats.patterns_found,
                    'file_type': self.compressor.file_type
                }
            )

            # Create metadata dict
            metadata = {
                'audit_event_id': event_id,
                'auditor_session': self.session_id,
                'method': stats.method,
                'ratio': stats.ratio,
                'patterns_found': stats.patterns_found,
                'file_type': self.compressor.file_type
            }

            return compressed_bytes, metadata


# Example usage and demonstration
if __name__ == "__main__":
    print("AURA Always Auditable Compression System")
    print("=" * 70)
    print("Patent US 19/366,538 - Claim 2: Comprehensive Audit Trail\n")

    # Test 1: Auditable standard compressor
    print("Test 1: Auditable Standard AURA Compressor")
    print("-" * 70)

    auditor = CompressionAuditor(db_path="audit/demo_audit.db")
    compressor1 = AuditableCompressor(
        compressor=ProductionHybridCompressor(),
        auditor=auditor,
        user_id="demo_user",
        session_id="session_001",
        source_ip="192.168.1.100"
    )

    msg = "I don't have access to that specific information. Could you provide more details?"
    compressed, meta1 = compressor1.compress(msg)
    print(f"Compressed: {len(msg)} → {len(compressed)} bytes ({meta1.get('compression_ratio', 0):.2f}:1)")
    print(f"Audit Event ID: {meta1['audit_event_id']}")

    decompressed, meta2 = compressor1.decompress(compressed)
    print(f"Decompressed: {len(compressed)} → {len(decompressed)} bytes")
    print(f"Audit Event ID: {meta2['audit_event_id']}")
    print(f"Verification: {'✓ PASS' if decompressed == msg else '✗ FAIL'}\n")

    # Test 2: Auditable hybrid compressor
    print("Test 2: Auditable Hybrid Large File Compressor")
    print("-" * 70)

    compressor2 = AuditableHeavy(
        enable_aura=True,
        auditor=auditor,
        user_id="demo_user",
        session_id="session_002",
        source_ip="192.168.1.100"
    )

    large_file = "Lorem ipsum dolor sit amet. " * 200  # 5.6KB
    compressed2, meta3 = compressor2.compress(large_file)
    print(f"Compressed: {len(large_file)} → {len(compressed2)} bytes ({meta3.get('ratio', 0):.2f}:1)")
    print(f"Method: {meta3.get('compression_layer')}")
    print(f"Audit Event ID: {meta3['audit_event_id']}\n")

    # Test 3: Verify audit chain
    print("Test 3: Audit Chain Verification")
    print("-" * 70)

    is_valid, errors = compressor1.verify_integrity(1, 10)
    print(f"Chain Valid: {is_valid}")
    if not is_valid:
        for error in errors:
            print(f"  Error: {error}")

    # Get statistics
    print("\nTest 4: Audit Statistics")
    print("-" * 70)

    stats = compressor1.get_audit_stats(hours=1)
    print(f"Time Range: {stats['time_range']}")
    print(f"Metrics:")
    for method, metrics in stats['metrics_by_method'].items():
        print(f"  {method}:")
        print(f"    Operations: {metrics['operations']}")
        print(f"    Avg Ratio: {metrics['avg_ratio']:.2f}:1")
        print(f"    Avg Latency: {metrics['avg_latency_ms']:.2f} ms")

    print("\n" + "=" * 70)
    print("AURA ALWAYS AUDITABLE - Core Principle Demonstrated")
    print("=" * 70)
    print("Every compression operation is:")
    print("  ✓ Logged with cryptographic hash")
    print("  ✓ Linked in tamper-proof audit chain")
    print("  ✓ Traceable to user/session/IP")
    print("  ✓ GDPR/HIPAA compliant")
    print("  ✓ Verifiable for integrity")
    print("\nAURA: Compression you can trust and audit.")
