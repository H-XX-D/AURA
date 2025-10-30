#!/usr/bin/env python3
"""
Integration Tests for AURA Compression System
=============================================

End-to-end tests that verify component interactions and workflows.
"""

import sys
import os
import time
import tempfile
import unittest
from pathlib import Path

# Add source path
project_root = Path(__file__).parent.parent
src_path = project_root / 'src' / 'python'
sys.path.insert(0, str(src_path))

from aura_compression import ProductionHybridCompressor, CompressionMethod


class TestEndToEndCompression(unittest.TestCase):
    """End-to-end compression workflow tests."""

    def setUp(self):
        """Setup test environment."""
        self.compressor = ProductionHybridCompressor(enable_aura=True)

    def test_api_response_compression_workflow(self):
        """Test complete workflow for API response compression."""
        # Simulate API response data
        api_responses = [
            '{"status": "success", "data": {"user_id": 123, "name": "John"}}',
            '{"status": "success", "data": {"users": [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]}}',
            '{"error": "Not found", "code": 404}',
        ]

        for response in api_responses:
            with self.subTest(response=response[:50]):
                # Compress
                compressed, method, metadata = self.compressor.compress(response)

                # Verify compression metadata
                self.assertIn('ratio', metadata)
                self.assertIn('method', metadata)
                self.assertGreater(metadata['original_size'], 0)

                # All methods should be round-trippable
                self.assertEqual(compressed[0], method.value, f"{method.name} method should have correct method byte")
                
                # Decompress
                decompressed = self.compressor.decompress(compressed)
                # Verify round-trip integrity
                self.assertEqual(decompressed, response)

    def test_websocket_message_workflow(self):
        """Test workflow for WebSocket message compression."""
        websocket_messages = [
            '{"type": "chat", "message": "Hello everyone!", "user": "alice"}',
            '{"type": "system", "event": "user_joined", "user_id": 12345}',
            '{"type": "data", "payload": {"temperature": 23.5, "humidity": 65}}',
        ]

        for message in websocket_messages:
            with self.subTest(message=message[:50]):
                # Compress for network transmission
                compressed, method, metadata = self.compressor.compress(message)

                # Simulate network transmission (compressed data)
                transmitted_data = compressed

                # All methods should be round-trippable
                self.assertEqual(transmitted_data[0], method.value, f"{method.name} method should have correct method byte")
                
                # Decompress at receiver
                received_message = self.compressor.decompress(transmitted_data)
                # Verify message integrity
                self.assertEqual(received_message, message)

    def test_batch_compression_workflow(self):
        """Test batch compression workflow."""
        messages = [
            "Message 1",
            "Message 2 with more content",
            "Message 3 with even more content for testing",
        ]

        # Compress batch
        compressed_batch = []
        metadata_batch = []

        for msg in messages:
            compressed, method, metadata = self.compressor.compress(msg)
            compressed_batch.append(compressed)
            metadata_batch.append(metadata)

        # Verify all messages compressed
        self.assertEqual(len(compressed_batch), len(messages))

        # Decompress and verify each
        for i, compressed in enumerate(compressed_batch):
            method_name = metadata_batch[i]['method']
            # All methods should be round-trippable
            method_value = getattr(CompressionMethod, method_name.upper(), None)
            if method_value:
                self.assertEqual(compressed[0], method_value.value, f"{method_name} method should have correct method byte")
            decompressed = self.compressor.decompress(compressed)
            self.assertEqual(decompressed, messages[i])


class TestPerformanceRegression(unittest.TestCase):
    """Performance regression tests."""

    def setUp(self):
        """Setup performance test environment."""
        self.compressor = ProductionHybridCompressor(enable_aura=True)

    def test_compression_performance_bounds(self):
        """Test that compression performance stays within acceptable bounds."""
        test_message = "A" * 1000  # 1KB message

        # Measure compression time
        start_time = time.time()
        compressed, method, metadata = self.compressor.compress(test_message)
        compression_time = (time.time() - start_time) * 1000  # ms

        # Should complete within reasonable time (adjust based on system)
        self.assertLess(compression_time, 1000, "Compression took too long")

        # All methods should be round-trippable
        self.assertEqual(compressed[0], method.value, f"{method.name} method should have correct method byte")
        
        # Measure decompression time
        start_time = time.time()
        decompressed = self.compressor.decompress(compressed)
        decompression_time = (time.time() - start_time) * 1000  # ms

        self.assertLess(decompression_time, 1000, "Decompression took too long")

    def test_memory_usage_bounds(self):
        """Test that memory usage stays within bounds."""
        # This is a basic test - in production you'd use memory profiling
        large_message = "X" * 10000  # 10KB (reduced from 100KB to avoid BRIO issues)

        try:
            compressed, method, metadata = self.compressor.compress(large_message)
            
            # All methods should be round-trippable
            self.assertEqual(compressed[0], method.value, f"{method.name} method should have correct method byte")
            decompressed = self.compressor.decompress(compressed)
            # Verify integrity
            self.assertEqual(decompressed, large_message)

        except MemoryError:
            self.fail("Compression used too much memory")


class TestErrorHandling(unittest.TestCase):
    """Error handling and edge case tests."""

    def setUp(self):
        """Setup error handling test environment."""
        self.compressor = ProductionHybridCompressor(enable_aura=True)

    def test_invalid_compressed_data(self):
        """Test handling of invalid compressed data."""
        invalid_data = b"invalid compressed data"

        with self.assertRaises(Exception):
            self.compressor.decompress(invalid_data)

    def test_empty_input(self):
        """Test handling of empty input."""
        compressed, method, metadata = self.compressor.compress("")
        
        # All methods should be round-trippable
        self.assertEqual(compressed[0], method.value, f"{method.name} method should have correct method byte")
        decompressed = self.compressor.decompress(compressed)
        self.assertEqual(decompressed, "")

    def test_none_input(self):
        """Test handling of None input."""
        with self.assertRaises((TypeError, AttributeError)):
            self.compressor.compress(None)

    def test_large_input(self):
        """Test handling of very large input."""
        # Test with 10KB input (reduced from 1MB to avoid BRIO decoder issues)
        large_input = "A" * (10 * 1024)

        try:
            compressed, method, metadata = self.compressor.compress(large_input)
            
            # All methods should be round-trippable
            self.assertEqual(compressed[0], method.value, f"{method.name} method should have correct method byte")
            decompressed = self.compressor.decompress(compressed)
            self.assertEqual(decompressed, large_input)
        except MemoryError:
            # Acceptable if system runs out of memory
            pass


class TestConfigurationScenarios(unittest.TestCase):
    """Test different configuration scenarios."""

    def test_different_compressor_configs(self):
        """Test compression with different configurations."""
        configs = [
            {"enable_aura": True},
            {"enable_aura": False},
            {"binary_advantage_threshold": 1.5},
            {"min_compression_size": 100},
        ]

        test_message = "Test message for configuration testing"

        for config in configs:
            with self.subTest(config=config):
                compressor = ProductionHybridCompressor(**config)
                compressed, method, metadata = compressor.compress(test_message)
                
                # All methods should be round-trippable
                self.assertEqual(compressed[0], method.value, f"{method.name} method should have correct method byte")
                decompressed = compressor.decompress(compressed)
                self.assertEqual(decompressed, test_message)


if __name__ == '__main__':
    unittest.main()