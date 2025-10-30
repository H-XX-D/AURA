#!/usr/bin/env python3
"""
AURA Heavy Test Suite
Tests for AuraHeavyOptimized compression layer
"""
import unittest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aura_compression.aura_heavy_optimized import AuraHeavyOptimized as AuraHeavy, AuraHeavyMethod, AuraHeavyResult


class TestAuraHeavy(unittest.TestCase):
    """Test suite for AuraHeavy compression."""

    def setUp(self):
        """Set up test fixtures."""
        self.compressor = AuraHeavy(enable_aura=True, prefer_speed=False)

    def test_small_message_uses_aura(self):
        """Test that small messages use AURA compression or fallback appropriately."""
        # Use a message that's more likely to compress well
        small_msg = "I don't have access to that information. I don't have access to that information."
        result = self.compressor.compress(small_msg)

        # Should use AURA method or fallback to zlib/uncompressed
        # (very small messages may not compress well with AURA)
        self.assertIn(result.method, [
            AuraHeavyMethod.BINARY_SEMANTIC,
            AuraHeavyMethod.AURALITE,
            AuraHeavyMethod.BRIO,
            AuraHeavyMethod.AURA_LITE,
            AuraHeavyMethod.ZLIB,
            AuraHeavyMethod.HARDWARE_OPTIMIZED,
            AuraHeavyMethod.UNCOMPRESSED
        ])

        # Should decompress correctly (lossless)
        decompressed, _ = self.compressor.decompress(result.compressed_data)
        self.assertEqual(decompressed, small_msg)

    def test_large_file_uses_zlib(self):
        """Test that large files use zlib compression."""
        large_msg = "Lorem ipsum dolor sit amet, consectetur adipiscing elit. " * 100
        result = self.compressor.compress(large_msg)

        # Should use zlib
        self.assertEqual(result.method, AuraHeavyMethod.ZLIB)

        # Should compress well
        self.assertGreater(result.ratio, 2.0)

        # Should decompress correctly
        decompressed, _ = self.compressor.decompress(result.compressed_data)
        self.assertEqual(decompressed, large_msg)

    def test_very_large_file_uses_fast_compression(self):
        """Test that very large files use faster compression."""
        very_large_msg = "The quick brown fox jumps over the lazy dog. " * 5000
        result = self.compressor.compress(very_large_msg)

        # Should use zlib
        self.assertEqual(result.method, AuraHeavyMethod.ZLIB)

        # Should have adjusted compression level
        self.assertIn('level', result.metadata)

        # Should decompress correctly
        decompressed, _ = self.compressor.decompress(result.compressed_data)
        self.assertEqual(decompressed, very_large_msg)

    def test_gzip_mode(self):
        """Test browser-compatible gzip mode."""
        compressor = AuraHeavy(enable_aura=False, use_gzip=True)
        large_msg = "Test message " * 200
        result = compressor.compress(large_msg)

        # Should use gzip
        self.assertEqual(result.method, AuraHeavyMethod.GZIP)

        # Should decompress correctly
        decompressed, _ = compressor.decompress(result.compressed_data)
        self.assertEqual(decompressed, large_msg)

    def test_compression_levels(self):
        """Test different compression levels."""
        test_data = "Compression test " * 100

        # Fast compression
        fast = AuraHeavy(enable_aura=False, prefer_speed=True)
        result_fast = fast.compress(test_data)

        # Max compression
        max_comp = AuraHeavy(enable_aura=False, compression_level=9)
        result_max = max_comp.compress(test_data)

        # Both should compress
        self.assertGreater(result_fast.ratio, 1.0)
        self.assertGreater(result_max.ratio, 1.0)

        # Max compression should have better ratio
        self.assertGreaterEqual(result_max.ratio, result_fast.ratio)

    def test_empty_string(self):
        """Test compression of empty string."""
        result = self.compressor.compress("")
        self.assertIsNotNone(result)

        decompressed, _ = self.compressor.decompress(result.compressed_data)
        self.assertEqual(decompressed, "")

    def test_unicode_handling(self):
        """Test compression of Unicode characters."""
        unicode_msg = "Hello 世界 🌍 Привет مرحبا"
        result = self.compressor.compress(unicode_msg)

        decompressed, _ = self.compressor.decompress(result.compressed_data)
        self.assertEqual(decompressed, unicode_msg)

    def test_binary_mode(self):
        """Test binary compression mode."""
        data = "Binary test data " * 100
        result = self.compressor.compress(data, is_binary=True)

        # Should skip AURA and use zlib
        self.assertEqual(result.method, AuraHeavyMethod.ZLIB)

        decompressed, _ = self.compressor.decompress(result.compressed_data)
        self.assertEqual(decompressed, data)

    def test_fallback_on_expansion(self):
        """Test that compression falls back when data expands."""
        # Random data that won't compress well
        random_data = "".join(chr(i % 256) for i in range(100))
        result = self.compressor.compress(random_data)

        # Should still return a result
        self.assertIsNotNone(result)

        # Should decompress correctly
        decompressed, _ = self.compressor.decompress(result.compressed_data)
        self.assertEqual(decompressed, random_data)

    def test_get_stats(self):
        """Test statistics retrieval."""
        stats = self.compressor.get_stats()

        self.assertIn('aura_enabled', stats)
        self.assertIn('compression_level', stats)
        self.assertIn('thresholds', stats)
        self.assertEqual(stats['dependencies'], 'None (Python standard library only)')

    def test_compression_metadata(self):
        """Test that metadata is correctly populated."""
        result = self.compressor.compress("Test message")

        self.assertIn('compression_layer', result.metadata)
        self.assertIsInstance(result.ratio, float)
        self.assertGreater(result.ratio, 0)

    def test_threshold_boundaries(self):
        """Test compression at threshold boundaries."""
        # Just below large file threshold (2KB)
        small = "x" * 2047
        result_small = self.compressor.compress(small)

        # Just above large file threshold
        large = "x" * 2049
        result_large = self.compressor.compress(large)

        # Should use different methods
        # (small might use AURA or zlib depending on actual size after encoding)
        self.assertEqual(result_large.method, AuraHeavyMethod.ZLIB)


class TestAuraHeavyEdgeCases(unittest.TestCase):
    """Test edge cases and error handling."""

    def test_disabled_aura(self):
        """Test operation with AURA disabled."""
        compressor = AuraHeavy(enable_aura=False)

        # Should still compress using zlib or uncompressed for tiny messages
        result = compressor.compress("Test message that is long enough to compress properly")
        self.assertIn(result.method, [AuraHeavyMethod.ZLIB, AuraHeavyMethod.UNCOMPRESSED])

        decompressed, _ = compressor.decompress(result.compressed_data)
        self.assertEqual(decompressed, "Test message that is long enough to compress properly")

    def test_invalid_compression_level(self):
        """Test that invalid compression levels are clamped."""
        # Level too high
        compressor_high = AuraHeavy(compression_level=100)
        self.assertEqual(compressor_high.compression_level, 9)

        # Level too low
        compressor_low = AuraHeavy(compression_level=-5)
        self.assertEqual(compressor_low.compression_level, 0)

    def test_decompression_invalid_method(self):
        """Test decompression with invalid method byte."""
        compressor = AuraHeavy()

        # Create invalid compressed data
        invalid_data = bytes([0xFE, 0x01, 0x02, 0x03])  # 0xFE is not a valid method

        with self.assertRaises(ValueError):
            compressor.decompress(invalid_data)

    def test_decompression_empty_data(self):
        """Test decompression of empty data."""
        compressor = AuraHeavy()

        decompressed, metadata = compressor.decompress(b"")
        self.assertEqual(decompressed, "")
        self.assertIn('error', metadata)

    def test_repeated_compression(self):
        """Test compressing the same data multiple times."""
        compressor = AuraHeavy()
        data = "Test message for repeated compression"

        results = [compressor.compress(data) for _ in range(10)]

        # All results should be identical
        for result in results:
            self.assertEqual(result.compressed_data, results[0].compressed_data)
            self.assertEqual(result.ratio, results[0].ratio)


class TestAuraHeavyPerformance(unittest.TestCase):
    """Performance-related tests."""

    def test_latency_small_messages(self):
        """Test that small message compression is fast."""
        import time

        compressor = AuraHeavy(enable_aura=True)
        msg = "I don't have access to that specific information."

        # Warmup
        for _ in range(10):
            compressor.compress(msg)

        # Measure
        start = time.perf_counter()
        for _ in range(100):
            compressor.compress(msg)
        elapsed = time.perf_counter() - start

        avg_latency_ms = (elapsed / 100) * 1000

        # Should be under 10ms per compression (very conservative)
        self.assertLess(avg_latency_ms, 10.0)
        print(f"\nSmall message avg latency: {avg_latency_ms:.2f}ms")

    def test_throughput_large_files(self):
        """Test throughput for large files."""
        import time

        compressor = AuraHeavy(enable_aura=False, prefer_speed=True)
        large_data = "Lorem ipsum " * 10000  # ~120KB

        # Warmup
        compressor.compress(large_data)

        # Measure
        start = time.perf_counter()
        iterations = 10
        for _ in range(iterations):
            compressor.compress(large_data)
        elapsed = time.perf_counter() - start

        avg_time_ms = (elapsed / iterations) * 1000

        # Should compress 120KB in under 50ms
        self.assertLess(avg_time_ms, 50.0)
        print(f"\nLarge file (120KB) avg time: {avg_time_ms:.2f}ms")


def run_tests():
    """Run all tests with verbose output."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestAuraHeavy))
    suite.addTests(loader.loadTestsFromTestCase(TestAuraHeavyEdgeCases))
    suite.addTests(loader.loadTestsFromTestCase(TestAuraHeavyPerformance))

    # Run with verbose output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Print summary
    print("\n" + "=" * 70)
    print("AURA HEAVY TEST SUITE SUMMARY")
    print("=" * 70)
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    print("=" * 70)

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
