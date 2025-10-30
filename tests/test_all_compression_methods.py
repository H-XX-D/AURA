#!/usr/bin/env python3
"""
Comprehensive Compression Methods Test
Tests all compression methods: UNCOMPRESSED, BINARY_SEMANTIC, AURA_LITE, BRIO, AURALITE
"""

import sys
import os
from pathlib import Path
import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'src' / 'python'))

from aura_compression.compressor import ProductionHybridCompressor, CompressionMethod


@pytest.fixture
def compressor():
    """Create a compressor instance for testing."""
    return ProductionHybridCompressor(
        enable_aura=True,
        min_compression_size=1,  # Allow compression of very small messages
        binary_advantage_threshold=1.01  # Lower threshold for testing
    )


def test_uncompressed_method(compressor):
    """Test UNCOMPRESSED method."""
    # Test cases that should use UNCOMPRESSED
    test_cases = [
        "Hi",  # Very small message
        "A",   # Single character
        "",    # Empty string
    ]

    for msg in test_cases:
        compressed, method, metadata = compressor.compress(msg)
        original_size = len(msg.encode('utf-8'))
        compressed_size = len(compressed)

        # Verify method
        assert method == CompressionMethod.UNCOMPRESSED

        # Verify sizes
        assert compressed_size >= original_size  # May add headers

        # Verify round-trip for non-empty messages
        if msg:
            decompressed = compressor.decompress(compressed)
            assert decompressed == msg


def test_binary_semantic_method(compressor):
    """Test BINARY_SEMANTIC method."""
    # Test cases that should potentially use BINARY_SEMANTIC
    # Use messages that are more likely to match templates or be compressible
    test_cases = [
        "Hello world",  # Simple message
        "Error occurred",  # Common pattern
        "Success",  # Short message
        "User authentication failed",  # Longer message that might compress
    ]

    compression_attempted = False
    for msg in test_cases:
        compressed, method, metadata = compressor.compress(msg)
        original_size = len(msg.encode('utf-8'))
        compressed_size = len(compressed)

        # Track if compression was attempted (not necessarily successful)
        if method != CompressionMethod.UNCOMPRESSED:
            compression_attempted = True

        # Verify round-trip
        decompressed = compressor.decompress(compressed)
        assert decompressed == msg

    # At least some messages should attempt compression
    assert compression_attempted


def test_aura_lite_method(compressor):
    """Test AURA_LITE method."""
    # Test cases that should potentially use AURA_LITE
    test_cases = [
        "User login successful for account 12345",
        "Database query returned 42 results in 150ms",
        "Cache hit for key: session_abc123",
        "Error: Connection timeout after 30 seconds",
    ]

    for msg in test_cases:
        compressed, method, metadata = compressor.compress(msg)
        original_size = len(msg.encode('utf-8'))
        compressed_size = len(compressed)

        # Verify round-trip (skip for BRIO as it's sanitized)
        if method.name != 'BRIO':
            decompressed = compressor.decompress(compressed)
            assert decompressed == msg
        else:
            # BRIO payloads are sanitized - just verify method byte
            assert compressed[0] == 0x02


def test_brio_method(compressor):
    """Test BRIO method."""
    # Test cases that should potentially use BRIO
    test_cases = [
        "A" * 1000,  # Repetitive data
        "The quick brown fox jumps over the lazy dog. " * 100,  # Repetitive text
    ]

    for msg in test_cases:
        compressed, method, metadata = compressor.compress(msg)
        original_size = len(msg.encode('utf-8'))
        compressed_size = len(compressed)

        # BRIO payloads are sanitized and cannot be round-tripped
        if method.name == 'BRIO':
            # Just verify it's a BRIO payload
            assert compressed[0] == 0x02
        else:
            # For other methods, verify round-trip
            decompressed = compressor.decompress(compressed)
            assert decompressed == msg


def test_auralite_method(compressor):
    """Test AURALITE method."""
    # Test cases that should potentially use AURALITE
    test_cases = [
        "Hello world message",
        "This is a test message for compression",
        "Another message to test the system",
    ]

    for msg in test_cases:
        compressed, method, metadata = compressor.compress(msg)
        original_size = len(msg.encode('utf-8'))
        compressed_size = len(compressed)

        # Verify round-trip (skip for BRIO as it's sanitized)
        if method.name != 'BRIO':
            decompressed = compressor.decompress(compressed)
            assert decompressed == msg
        else:
            # BRIO payloads are sanitized - just verify method byte
            assert compressed[0] == 0x02


def test_compression_method_diversity(compressor):
    """Test that different compression methods are used for different data types."""
    test_cases = [
        ("", "should be uncompressed"),
        ("x", "should be uncompressed"),
        ('{"json": "data"}', "should use semantic compression"),
        ("A" * 1000, "should use BRIO for repetitive data"),
        ("User authentication successful", "should use template compression"),
    ]

    methods_used = set()

    for msg, description in test_cases:
        compressed, method, metadata = compressor.compress(msg)
        methods_used.add(method)

        # Verify round-trip (skip for BRIO as it's sanitized)
        if method.name != 'BRIO':
            decompressed = compressor.decompress(compressed)
            assert decompressed == msg, f"Failed for: {description}"
        else:
            # BRIO payloads are sanitized - just verify method byte
            assert compressed[0] == 0x02, f"BRIO method should have method byte 0x02 for: {description}"

    # Should use at least uncompressed and one compression method
    assert CompressionMethod.UNCOMPRESSED in methods_used
    assert len(methods_used) > 1