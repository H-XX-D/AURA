#!/usr/bin/env python3
"""
AURA Compression System - Comprehensive Test Suite
Test 6-10: Compression Methods Testing
"""

import sys
import os
import pytest
from pathlib import Path
from typing import Dict, Any, List

# Add source path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src' / 'python'))

from aura_compression.compressor import ProductionHybridCompressor
from aura_compression.enums import CompressionMethod


@pytest.fixture
def compressor():
    """Fixture providing a configured compressor for tests."""
    return ProductionHybridCompressor(
        enable_aura=True,
        min_compression_size=1
    )


def test_6_binary_semantic_method(compressor):
    """Test 6: BINARY_SEMANTIC compression method"""
    # Test with template-matching content
    test_message = "I don't have access to your files"
    result = compressor.compress(test_message)

    # BINARY_SEMANTIC should be available and potentially used
    strategies = compressor._compression_strategies
    binary_semantic_available = any(
        s.get_method() == CompressionMethod.BINARY_SEMANTIC
        for s in strategies
    )
    assert binary_semantic_available, "BINARY_SEMANTIC strategy not available"


def test_7_auralite_method(compressor):
    """Test 7: AURALITE compression method"""
    # Test with short message that might use AURALITE
    test_message = "Hello world"
    result = compressor.compress(test_message)

    # AURALITE should be available
    strategies = compressor._compression_strategies
    auralite_available = any(
        s.get_method() == CompressionMethod.AURALITE
        for s in strategies
    )
    assert auralite_available, "AURALITE strategy not available"


def test_8_brio_method(compressor):
    """Test 8: BRIO compression method"""
    # Test with longer message that might use BRIO
    test_message = "This is a longer test message for BRIO compression method testing"
    result = compressor.compress(test_message)

    # BRIO should be available
    strategies = compressor._compression_strategies
    brio_available = any(
        s.get_method() == CompressionMethod.BRIO
        for s in strategies
    )
    assert brio_available, "BRIO strategy not available"


def test_9_aura_heavy_method(compressor):
    """Test 9: AURA_HEAVY compression method"""
    # Test with large message that might use AURA_HEAVY
    test_message = "This is a very long test message designed to test the AURA_HEAVY compression method which should handle large files efficiently with advanced hybrid compression and adaptive routing for optimal performance across all file sizes."
    result = compressor.compress(test_message)

    # AURA_HEAVY should be available
    strategies = compressor._compression_strategies
    aura_heavy_available = any(
        s.get_method() == CompressionMethod.AURA_HEAVY
        for s in strategies
    )
    assert aura_heavy_available, "AURA_HEAVY strategy not available"


def test_10_uncompressed_method(compressor):
    """Test 10: UNCOMPRESSED fallback method"""
    # Test with incompressible data
    test_message = "xYz123!@#"  # Random characters
    result = compressor.compress(test_message)
    compressed_payload, method, metadata = result

    # Should potentially use UNCOMPRESSED for incompressible data
    strategies = compressor._compression_strategies
    uncompressed_available = any(
        s.get_method() == CompressionMethod.UNCOMPRESSED
        for s in strategies
    )
    assert uncompressed_available, "UNCOMPRESSED strategy not available"