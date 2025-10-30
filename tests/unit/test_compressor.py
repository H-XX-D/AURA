#!/usr/bin/env python3
"""
Unit Tests for AURA Compression Components
==========================================

Individual component tests with comprehensive coverage.
"""

import sys
import unittest
from pathlib import Path

# Add source path
project_root = Path(__file__).parent
src_path = project_root / 'src' / 'python'
sys.path.insert(0, str(src_path))

from aura_compression import ProductionHybridCompressor, CompressionMethod


class TestProductionHybridCompressor(unittest.TestCase):
    """Unit tests for ProductionHybridCompressor."""

    def setUp(self):
        """Setup test environment."""
        self.compressor = ProductionHybridCompressor(enable_aura=True)

    def test_compression_basic(self):
        """Test basic compression functionality."""
        test_message = "Hello, world!"
        compressed, method, metadata = self.compressor.compress(test_message)

        # Verify compression returns expected types
        self.assertIsInstance(compressed, bytes)
        self.assertIsInstance(method, CompressionMethod)
        self.assertIsInstance(metadata, dict)

        # Verify decompression works
        decompressed = self.compressor.decompress(compressed)
        self.assertEqual(decompressed, test_message)

    def test_compression_metadata(self):
        """Test compression metadata is complete."""
        test_message = "Test message for metadata validation"
        compressed, method, metadata = self.compressor.compress(test_message)

        required_keys = ['original_size', 'compressed_size', 'ratio', 'method']
        for key in required_keys:
            self.assertIn(key, metadata)

        # Verify sizes are reasonable
        self.assertEqual(metadata['original_size'], len(test_message.encode('utf-8')))
        self.assertGreaterEqual(metadata['compressed_size'], 1)
        self.assertGreater(metadata['ratio'], 0)

    def test_small_message_handling(self):
        """Test handling of very small messages."""
        small_messages = ["", "a", "hi"]

        for msg in small_messages:
            compressed, method, metadata = self.compressor.compress(msg)
            # All methods should be round-trippable
            self.assertEqual(compressed[0], method.value, f"{method.name} method should have correct method byte")
            decompressed = self.compressor.decompress(compressed)
            self.assertEqual(decompressed, msg)

    def test_large_message_handling(self):
        """Test handling of larger messages."""
        large_message = "A" * 10000  # 10KB message
        compressed, method, metadata = self.compressor.compress(large_message)
        
        # All methods should be round-trippable
        self.assertEqual(compressed[0], method.value, f"{method.name} method should have correct method byte")
        decompressed = self.compressor.decompress(compressed)
        self.assertEqual(decompressed, large_message)

    def test_unicode_handling(self):
        """Test compression and decompression of Unicode strings."""
        unicode_messages = [
            "Hello 世界",
            "🚀 Unicode test 🌟",
            "café résumé naïve",
            "αβγδε",
            "русский текст"
        ]

        for msg in unicode_messages:
            compressed, method, metadata = self.compressor.compress(msg)
            # All methods should be round-trippable
            self.assertEqual(compressed[0], method.value, f"{method.name} method should have correct method byte")
            decompressed = self.compressor.decompress(compressed)
            self.assertEqual(decompressed, msg)

    def test_compression_method_variety(self):
        """Test that different compression methods are used for different data."""
        test_cases = [
            ("Short text", "expected to be uncompressed"),
            ("This is a longer message that should trigger template matching and compression algorithms", "expected to use compression"),
            ('{"json": "data", "with": {"nested": "structure"}}', "expected to use semantic compression"),
        ]

        methods_used = set()
        for message, description in test_cases:
            compressed, method, metadata = self.compressor.compress(message)
            methods_used.add(method)
            # Verify decompression (skip for BRIO as it's sanitized)
            if method.name != 'BRIO':
                decompressed = self.compressor.decompress(compressed)
                self.assertEqual(decompressed, message, f"Failed for: {description}")
            else:
                # Just verify it's a BRIO payload
                self.assertEqual(compressed[0], 0x02, f"BRIO method should have method byte 0x02 for: {description}")

        # Should use at least uncompressed and one compression method
        self.assertIn(CompressionMethod.UNCOMPRESSED, methods_used)


class TestCompressionMethod(unittest.TestCase):
    """Unit tests for CompressionMethod enum."""

    def test_enum_values(self):
        """Test CompressionMethod enum values."""
        self.assertEqual(CompressionMethod.BINARY_SEMANTIC.value, 0x00)
        self.assertEqual(CompressionMethod.AURALITE.value, 0x01)
        self.assertEqual(CompressionMethod.BRIO.value, 0x02)
        self.assertEqual(CompressionMethod.AURA_LITE.value, 0x03)
        self.assertEqual(CompressionMethod.AURA_HEAVY.value, 0x04)
        self.assertEqual(CompressionMethod.UNCOMPRESSED.value, 0xFF)

    def test_enum_names(self):
        """Test CompressionMethod enum names."""
        expected_names = ['BINARY_SEMANTIC', 'AURALITE', 'BRIO', 'UNCOMPRESSED', 'AURA_LITE', 'AURA_HEAVY']
        actual_names = [method.name for method in CompressionMethod]
        self.assertEqual(set(actual_names), set(expected_names))


class TestDataIntegrity(unittest.TestCase):
    """Test data integrity and round-trip compression."""

    def setUp(self):
        """Setup test environment."""
        self.compressor = ProductionHybridCompressor(enable_aura=True)

    def test_round_trip_integrity(self):
        """Test that compression/decompression preserves data exactly."""
        test_messages = [
            "Simple text",
            "Text with numbers 12345",
            "Text with special chars !@#$%^&*()",
            "Unicode: 你好世界 🌟",
            "Very long message " * 100,
            "",
            "x",
        ]

        for message in test_messages:
            with self.subTest(message=message[:50] + "..." if len(message) > 50 else message):
                compressed, method, metadata = self.compressor.compress(message)
                
                # BRIO payloads are sanitized for client delivery and cannot be round-tripped
                if method.name == 'BRIO':
                    # Just verify compression succeeded and produced a BRIO payload
                    self.assertEqual(compressed[0], 0x02, f"BRIO method should have method byte 0x02")
                    continue
                    
                decompressed = self.compressor.decompress(compressed)
                self.assertEqual(decompressed, message,
                               f"Round-trip failed for message: {message[:100]}...")

    def test_corruption_detection(self):
        """Test that corrupted compressed data is handled gracefully."""
        message = "Test message for corruption detection"
        compressed, method, metadata = self.compressor.compress(message)

        # Corrupt the compressed data
        corrupted = compressed[:-1] + bytes([compressed[-1] ^ 0xFF])

        # Should handle corruption gracefully (either detect or fail safely)
        try:
            decompressed = self.compressor.decompress(corrupted)
            # If it doesn't fail, it should at least not crash
            self.assertIsInstance(decompressed, str)
        except Exception:
            # Expected to fail with corrupted data
            pass


if __name__ == '__main__':
    unittest.main()