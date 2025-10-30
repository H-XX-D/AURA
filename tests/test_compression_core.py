#!/usr/bin/env python3
"""
AURA Compression System - Comprehensive Test Suite
Test 1-5: Core Compression Functionality
"""

import sys
import os
import tempfile
import json
import pytest
from pathlib import Path
from typing import Dict, Any, List

# Add source path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from aura_compression.compressor import ProductionHybridCompressor
from aura_compression.enums import CompressionMethod


@pytest.fixture
def compressor():
    """Fixture providing a configured compressor for tests."""
    return ProductionHybridCompressor(
        enable_aura=True,
        min_compression_size=1,  # Test all sizes
        binary_advantage_threshold=0.96  # Ultra-aggressive threshold
    )


def test_1_compression_initialization(compressor):
    """Test 1: Compressor initialization with optimized settings"""
    # Verify compressor has all required strategies
    strategies = compressor._strategy_manager.get_available_strategies()
    expected_methods = [
        CompressionMethod.BINARY_SEMANTIC,
        CompressionMethod.AURALITE,
        CompressionMethod.BRIO,
        CompressionMethod.UNCOMPRESSED
    ]

    found_methods = strategies
    for method in expected_methods:
        assert method in found_methods, f"Missing method: {method}"

    assert len(strategies) > 0, "No compression strategies found"


def test_2_ultra_aggressive_thresholds(compressor):
    """Test 2: Ultra-aggressive compression thresholds"""
    # Test messages of various sizes
    test_cases = [
        ("Tiny", "Hi"),
        ("Small", "Hello"),
        ("Medium", "Hello world"),
        ("Large", "This is a longer message that should compress very aggressively"),
    ]

    compressed_any = False
    for name, message in test_cases:
        result = compressor.compress(message)
        compressed_payload, method, metadata = result
        if method.name != "UNCOMPRESSED":
            compressed_any = True
            ratio = metadata.get('ratio', 1.0)
            print(f"   {name} ({len(message)} bytes): {ratio:.3f}:1")

    # With ultra-aggressive thresholds, we expect some compression
    assert compressed_any, "Ultra-aggressive thresholds produced no compression"


def test_3_uncompressed_fallback(compressor):
    """Test 3: Intelligent uncompressed fallback for incompressible data"""
    # Test messages that shouldn't compress
    incompressible_messages = [
        "a",  # Single character
        "Hi",  # Very short
        "xYz123!@#",  # Random characters
    ]

    uncompressed_count = 0
    for message in incompressible_messages:
        result = compressor.compress(message)
        compressed_payload, method, metadata = result
        if method == CompressionMethod.UNCOMPRESSED:
            uncompressed_count += 1

    # All incompressible messages should use UNCOMPRESSED
    assert uncompressed_count == len(incompressible_messages), \
        f"Expected all {len(incompressible_messages)} to be uncompressed, got {uncompressed_count}"


def test_4_compression_ratio_calculation(compressor):
    """Test 4: Accurate compression ratio calculations"""
    test_message = "This is a test message for compression ratio validation"
    result = compressor.compress(test_message)
    compressed_payload, method, metadata = result

    original_size = len(test_message.encode('utf-8'))
    compressed_size = len(compressed_payload)
    calculated_ratio = original_size / compressed_size if compressed_size > 0 else 1.0

    # Verify ratio calculation
    reported_ratio = metadata.get('ratio', 1.0)
    assert abs(calculated_ratio - reported_ratio) < 0.01, \
        f"Ratio mismatch: calculated {calculated_ratio:.3f}, reported {reported_ratio:.3f}"


def test_5_round_trip_integrity(compressor):
    """Test 5: Round-trip compression/decompression integrity"""
    test_messages = [
        "Hello World",
        "This is a test message with special characters: àáâãäåæçèéêë",
        "Numbers: 1234567890",
        "Symbols: !@#$%^&*()_+-=[]{}|;:,.<>?",
        "",  # Empty string
        "A",  # Single character
    ]

    for original in test_messages:
        # Compress
        compressed_result = compressor.compress(original)
        compressed_payload, method, metadata = compressed_result

        # Decompress
        decompressed = compressor.decompress(compressed_payload)

        # Verify integrity
        assert decompressed == original, \
            f"Round-trip failed for: '{original}' → '{decompressed}'"