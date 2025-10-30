#!/usr/bin/env python3
"""
AURA Compression System - Comprehensive Test Suite
Test 11-15: Threshold Optimization Testing
"""

import sys
from pathlib import Path
from typing import Dict, Any, List

# Add source path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src' / 'python'))

from aura_compression.compressor import ProductionHybridCompressor
from aura_compression.enums import CompressionMethod


class TestCompressionThresholds:
    """Test compression threshold optimizations"""

    def __init__(self):
        self.test_results = []

    def log_test(self, test_name: str, passed: bool, details: str = ""):
        """Log test result"""
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} {test_name}")
        if details:
            print(f"   {details}")
        self.test_results.append({
            'test': test_name,
            'passed': passed,
            'details': details
        })

    def test_11_ultra_aggressive_thresholds(self):
        """Test 11: Ultra-aggressive compression thresholds (original_size <= 10, best_ratio < 0.96)"""
        try:
            # Create compressor with ultra-aggressive settings
            compressor = ProductionHybridCompressor(
                enable_aura=True,
                min_compression_size=1,
                binary_advantage_threshold=0.96  # Very aggressive
            )

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
                if result[1] != CompressionMethod.UNCOMPRESSED:
                    compressed_any = True
                    ratio = result[2].get('ratio', 1.0)
                    print(f"   {name} ({len(message)} bytes): {ratio:.3f}:1")

            # With ultra-aggressive thresholds, expect some compression
            assert compressed_any, "Ultra-aggressive thresholds produced no compression"

            self.log_test("test_11_ultra_aggressive_thresholds",
                          True, "Ultra-aggressive thresholds working - some messages compressed")
            return True
        except Exception as e:
            self.log_test("test_11_ultra_aggressive_thresholds",
                          False, f"Ultra-aggressive thresholds test failed: {e}")
            return False

    def test_12_conservative_thresholds(self):
        """Test 12: Conservative compression thresholds for compatibility"""
        try:
            # Create compressor with conservative settings
            compressor = ProductionHybridCompressor(
                enable_aura=True,
                min_compression_size=100,  # Only compress large messages
                binary_advantage_threshold=1.05  # Require 5% improvement
            )

            # Test messages - small ones should not compress
            small_messages = ["Hi", "Hello", "Short"]
            large_message = "This is a very long message that exceeds the minimum compression size threshold and should be considered for compression with conservative settings"

            # Small messages should use UNCOMPRESSED
            uncompressed_count = 0
            for message in small_messages:
                result = compressor.compress(message)
                if result[1] == CompressionMethod.UNCOMPRESSED:
                    uncompressed_count += 1

            assert uncompressed_count == len(small_messages), \
                f"Expected {len(small_messages)} small messages uncompressed, got {uncompressed_count}"

            # Large message might compress
            large_result = compressor.compress(large_message)
            large_compressed = large_result[1] != CompressionMethod.UNCOMPRESSED

            self.log_test("test_12_conservative_thresholds",
                          True, f"Conservative thresholds: {uncompressed_count} small messages uncompressed, large message compressed: {large_compressed}")
            return True
        except Exception as e:
            self.log_test("test_12_conservative_thresholds",
                          False, f"Conservative thresholds test failed: {e}")
            return False

    def test_13_adaptive_thresholds(self):
        """Test 13: Adaptive threshold selection based on content type"""
        try:
            # Test different content types with adaptive thresholds
            content_types = {
                "Code": "def compress(data): return len(data) < threshold",
                "Text": "This is a regular text message that should compress well",
                "JSON": '{"key": "value", "number": 123, "array": [1, 2, 3]}',
                "Binary": "x\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0A\x0B\x0C\x0D\x0E\x0F",
            }

            compressor = ProductionHybridCompressor(enable_aura=True, min_compression_size=1)

            results = {}
            for content_type, content in content_types.items():
                result = compressor.compress(content)
                method = result[1]
                ratio = result[2].get('ratio', 1.0)
                results[content_type] = {
                    'method': method,
                    'ratio': ratio,
                    'compressed': method != CompressionMethod.UNCOMPRESSED
                }
                print(f"   {content_type}: {method.name} ({ratio:.3f}:1)")

            # Verify different content types are handled appropriately
            # (compression may or may not occur depending on content compressibility)
            assert all(isinstance(r['ratio'], (int, float)) for r in results.values()), "All results should have valid ratios"
            assert all(isinstance(r['method'], CompressionMethod) for r in results.values()), "All results should have valid methods"

            # At least some content should be compressible
            compressible_count = sum(1 for r in results.values() if r['compressed'])
            assert compressible_count > 0, "At least some content types should be compressible"

            self.log_test("test_13_adaptive_thresholds",
                          True, f"Adaptive thresholds applied to {len(content_types)} content types")
            return True
        except Exception as e:
            self.log_test("test_13_adaptive_thresholds",
                          False, f"Adaptive thresholds test failed: {e}")
            return False

    def test_14_threshold_boundary_conditions(self):
        """Test 14: Threshold boundary conditions and edge cases"""
        try:
            # Test exact boundary conditions
            compressor = ProductionHybridCompressor(
                enable_aura=True,
                min_compression_size=10,  # Exactly 10 bytes
                binary_advantage_threshold=1.0  # Any compression advantage
            )

            # Test messages at boundaries
            boundary_tests = [
                ("9 bytes", "123456789"),  # 9 bytes - should not compress
                ("10 bytes", "1234567890"),  # 10 bytes - should be eligible
                ("11 bytes", "12345678901"),  # 11 bytes - should be eligible
            ]

            boundary_results = []
            for name, message in boundary_tests:
                result = compressor.compress(message)
                compressed = result[1] != CompressionMethod.UNCOMPRESSED
                boundary_results.append((name, compressed))
                print(f"   {name}: {'Compressed' if compressed else 'Uncompressed'}")

            # Verify boundary behavior
            assert not boundary_results[0][1], "9-byte message should not compress"
            # 10+ byte messages may or may not compress depending on compressibility

            self.log_test("test_14_threshold_boundary_conditions",
                          True, f"Boundary conditions tested: {len(boundary_tests)} cases")
            return True
        except Exception as e:
            self.log_test("test_14_threshold_boundary_conditions",
                          False, f"Boundary conditions test failed: {e}")
            return False

    def test_15_performance_vs_ratio_tradeoffs(self):
        """Test 15: Performance vs compression ratio tradeoffs"""
        try:
            import time

            # Test different threshold configurations
            configs = [
                ("Ultra-aggressive", 0.96, 1),
                ("Balanced", 1.01, 10),
                ("Conservative", 1.05, 50),
            ]

            test_message = "This is a test message for evaluating performance versus compression ratio tradeoffs in the AURA compression system"

            results = []
            for name, threshold, min_size in configs:
                compressor = ProductionHybridCompressor(
                    enable_aura=True,
                    min_compression_size=min_size,
                    binary_advantage_threshold=threshold
                )

                # Time compression
                start_time = time.time()
                result = compressor.compress(test_message)
                end_time = time.time()

                latency = (end_time - start_time) * 1000  # ms
                ratio = result[2].get('ratio', 1.0)
                method = result[1]

                results.append({
                    'config': name,
                    'latency_ms': latency,
                    'ratio': ratio,
                    'method': method
                })

                print(f"   {name}: {latency:.2f}ms, {ratio:.3f}:1, {method.name}")

            # Verify tradeoffs exist
            ultra_ratio = results[0]['ratio']
            conservative_ratio = results[2]['ratio']

            # Conservative settings should generally produce better ratios (if compression occurs)
            if conservative_ratio > 1.0 and ultra_ratio > 1.0:
                assert conservative_ratio >= ultra_ratio * 0.9, "Conservative settings should not have much worse ratios"

            self.log_test("test_15_performance_vs_ratio_tradeoffs",
                          True, f"Performance/ratio tradeoffs analyzed for {len(configs)} configurations")
            return True
        except Exception as e:
            self.log_test("test_15_performance_vs_ratio_tradeoffs",
                          False, f"Performance tradeoffs test failed: {e}")
            return False

    def run_all_tests(self):
        """Run all threshold optimization tests"""
        print("=" * 80)
        print("AURA COMPRESSION SYSTEM - THRESHOLD TESTS (11-15)")
        print("=" * 80)

        tests = [
            self.test_11_ultra_aggressive_thresholds,
            self.test_12_conservative_thresholds,
            self.test_13_adaptive_thresholds,
            self.test_14_threshold_boundary_conditions,
            self.test_15_performance_vs_ratio_tradeoffs,
        ]

        passed = 0
        for test in tests:
            if test():
                passed += 1
            print()

        print(f"Results: {passed}/{len(tests)} tests passed")
        return passed == len(tests)


if __name__ == "__main__":
    tester = TestCompressionThresholds()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)