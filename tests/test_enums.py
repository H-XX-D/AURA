#!/usr/bin/env python3
"""
Enums Module Tests
Test compression method enums and constants
"""

import sys
from pathlib import Path

# Add source path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from aura_compression.enums import CompressionMethod


class TestCompressionMethod:
    """Test CompressionMethod enum"""

    def test_enum_values(self):
        """Test that enum values are correct"""
        assert CompressionMethod.BINARY_SEMANTIC.value == 0x00
        assert CompressionMethod.AURALITE.value == 0x01
        assert CompressionMethod.BRIO.value == 0x02
        assert CompressionMethod.AURA_HEAVY.value == 0x04
        assert CompressionMethod.PATTERN_SEMANTIC.value == 0x20
        assert CompressionMethod.UNCOMPRESSED.value == 0xFF

    def test_enum_names(self):
        """Test that enum names are correct"""
        assert CompressionMethod.BINARY_SEMANTIC.name == "BINARY_SEMANTIC"
        assert CompressionMethod.AURALITE.name == "AURALITE"
        assert CompressionMethod.BRIO.name == "BRIO"
        assert CompressionMethod.AURA_HEAVY.name == "AURA_HEAVY"
        assert CompressionMethod.PATTERN_SEMANTIC.name == "PATTERN_SEMANTIC"
        assert CompressionMethod.UNCOMPRESSED.name == "UNCOMPRESSED"

    def test_enum_string_representation(self):
        """Test string representation of enums"""
        assert str(CompressionMethod.BINARY_SEMANTIC) == "CompressionMethod.BINARY_SEMANTIC"
        assert str(CompressionMethod.PATTERN_SEMANTIC) == "CompressionMethod.PATTERN_SEMANTIC"

    def test_enum_iteration(self):
        """Test that we can iterate over enum values"""
        methods = list(CompressionMethod)
        assert len(methods) == 6
        assert CompressionMethod.BINARY_SEMANTIC in methods
        assert CompressionMethod.PATTERN_SEMANTIC in methods
        assert CompressionMethod.UNCOMPRESSED in methods

    def test_enum_uniqueness(self):
        """Test that all enum values are unique"""
        values = [method.value for method in CompressionMethod]
        assert len(values) == len(set(values)), "Enum values are not unique"

    def test_enum_name_lower(self):
        """Test the name.lower() method used in serialization"""
        assert CompressionMethod.BINARY_SEMANTIC.name.lower() == "binary_semantic"
        assert CompressionMethod.PATTERN_SEMANTIC.name.lower() == "pattern_semantic"
        assert CompressionMethod.UNCOMPRESSED.name.lower() == "uncompressed"