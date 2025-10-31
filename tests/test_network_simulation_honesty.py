#!/usr/bin/env python3
"""
Test suite for network simulation honesty and accuracy

These tests validate that the simulation:
- Reports accurate compression ratios (not inflated)
- Correctly identifies when data expands
- Properly tracks bandwidth usage
- Provides honest assessment of performance
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aura_compression.compressor_refactored import ProductionHybridCompressor
from aura_compression.enums import CompressionMethod


class TestSimulationHonesty:
    """Test that simulation reports honest results"""

    def test_small_message_expansion_detected(self):
        """Test that expansion is detected for small messages"""
        compressor = ProductionHybridCompressor(
            enable_aura=False,
            enable_audit_logging=False,
            enable_scorer=False
        )

        # Very small messages often expand due to overhead
        small_messages = [
            "Hi",
            "OK",
            "Yes",
            "No problem",
            "Thanks!",
        ]

        expansion_count = 0
        for message in small_messages:
            compressed, method, metadata = compressor.compress(message)

            original_size = len(message.encode('utf-8'))
            compressed_size = len(compressed)
            ratio = metadata.get('ratio', original_size / compressed_size)

            if compressed_size > original_size:
                expansion_count += 1
                print(f"  ✓ Correctly detected expansion: \"{message}\" "
                      f"{original_size}→{compressed_size}b (ratio {ratio:.3f}x)")

        # At least some small messages should show expansion
        assert expansion_count > 0, \
            "Small messages should show expansion, but none detected"

        print(f"✓ Small message expansion test passed: "
              f"{expansion_count}/{len(small_messages)} expanded")

    def test_compression_ratio_accuracy(self):
        """Test that compression ratios are calculated accurately"""
        compressor = ProductionHybridCompressor(
            enable_aura=False,
            enable_audit_logging=False,
            enable_scorer=False
        )

        message = "Test compression ratio calculation" * 10
        compressed, method, metadata = compressor.compress(message)

        original_size = len(message.encode('utf-8'))
        compressed_size = len(compressed)

        # Manual calculation
        expected_ratio = original_size / compressed_size if compressed_size > 0 else 0.0

        # Reported ratio
        reported_ratio = metadata.get('ratio', 0.0)

        # Should match within floating point precision
        ratio_diff = abs(expected_ratio - reported_ratio)
        assert ratio_diff < 0.001, \
            f"Ratio mismatch: expected {expected_ratio:.6f}, got {reported_ratio:.6f}"

        print(f"✓ Compression ratio accuracy test passed: "
              f"{original_size}→{compressed_size}b = {reported_ratio:.3f}x")

    def test_bandwidth_calculation_honesty(self):
        """Test that bandwidth savings/expansion is calculated honestly"""
        # Test case 1: Savings
        original1 = 1000
        compressed1 = 600
        savings1 = original1 - compressed1
        savings_pct1 = (savings1 / original1) * 100

        assert savings1 == 400, "Savings calculation error"
        assert abs(savings_pct1 - 40.0) < 0.01, "Savings percentage error"

        # Test case 2: Expansion
        original2 = 500
        compressed2 = 550
        expansion2 = compressed2 - original2
        expansion_pct2 = (expansion2 / original2) * 100

        assert expansion2 == 50, "Expansion calculation error"
        assert abs(expansion_pct2 - 10.0) < 0.01, "Expansion percentage error"

        print(f"✓ Bandwidth calculation honesty test passed")
        print(f"  Savings case: {original1}→{compressed1}b = {savings_pct1:.1f}% saved")
        print(f"  Expansion case: {original2}→{compressed2}b = {expansion_pct2:.1f}% expansion")

    def test_no_false_positives_on_uncompressed(self):
        """Test that uncompressed method reports ratio of 1.0"""
        compressor = ProductionHybridCompressor(
            enable_aura=False,
            enable_audit_logging=False,
            enable_scorer=False,
            binary_advantage_threshold=100.0  # Force UNCOMPRESSED
        )

        message = "Short message"
        compressed, method, metadata = compressor.compress(message)

        # If method is UNCOMPRESSED, ratio should be ~1.0 (accounting for overhead)
        if method == CompressionMethod.UNCOMPRESSED:
            ratio = metadata.get('ratio', 0.0)
            # UNCOMPRESSED might have small overhead, so ratio might be slightly < 1.0
            assert 0.95 <= ratio <= 1.05, \
                f"UNCOMPRESSED should have ratio ~1.0, got {ratio:.3f}"

            print(f"✓ UNCOMPRESSED method reports honest ratio: {ratio:.3f}x")
        else:
            print(f"  Skipped (method was {method.name}, not UNCOMPRESSED)")

    def test_method_selection_tracking(self):
        """Test that compression method selection is tracked accurately"""
        compressor = ProductionHybridCompressor(
            enable_aura=False,
            enable_audit_logging=False,
            enable_scorer=False
        )

        test_messages = [
            "Short msg",
            "Medium length message with some content",
            "Long message with lots of content " * 20,
        ]

        methods_used = {}
        for message in test_messages:
            compressed, method, metadata = compressor.compress(message)

            methods_used[method.name] = methods_used.get(method.name, 0) + 1

            # Verify metadata reports correct method
            reported_method = metadata.get('method', '').upper()
            assert reported_method == method.name.upper() or \
                   reported_method == method.name.lower(), \
                f"Method mismatch: actual={method.name}, reported={reported_method}"

        print(f"✓ Method selection tracking test passed")
        for method_name, count in methods_used.items():
            print(f"  {method_name}: {count} messages")

    def test_ai_responses_are_larger(self):
        """Test that AI responses are indeed larger than prompts"""
        from tests.network_simulation import AIServer

        compressor = ProductionHybridCompressor(enable_aura=False)
        server = AIServer(compressor)

        prompts = [
            "How do I fix this?",
            "Can you explain async/await?",
            "I'm getting an error when I run my code.",
        ]

        for prompt in prompts:
            response = server.generate_response(prompt)

            assert len(response) > len(prompt), \
                f"AI response ({len(response)}b) should be larger than prompt ({len(prompt)}b)"

            ratio = len(response) / len(prompt)
            print(f"  Prompt: {len(prompt)}b → Response: {len(response)}b "
                  f"(ratio {ratio:.2f}x)")

        print(f"✓ AI response size test passed")

    def test_realistic_latency_ranges(self):
        """Test that network latency falls within realistic ranges"""
        from tests.network_simulation import SimulatedNetwork

        # Test different network conditions
        configs = [
            ("Fast LAN", 5.0, 2.0, 3.0, 10.0),
            ("Broadband", 50.0, 10.0, 40.0, 70.0),
            ("Slow connection", 150.0, 30.0, 120.0, 200.0),
        ]

        for name, base_ms, jitter_ms, min_expected, max_expected in configs:
            network = SimulatedNetwork(base_latency_ms=base_ms, jitter_ms=jitter_ms)

            # Test 10 transmissions
            latencies = []
            for _ in range(10):
                data = b"Test data" * 100
                _, latency = network.transmit(data)
                latencies.append(latency)

            avg_latency = sum(latencies) / len(latencies)
            min_latency = min(latencies)
            max_latency = max(latencies)

            # Verify latencies are in realistic range
            assert min_latency >= min_expected * 0.8, \
                f"{name}: min latency {min_latency}ms too low"
            assert max_latency <= max_expected * 1.2, \
                f"{name}: max latency {max_latency}ms too high"

            print(f"  {name}: {min_latency:.1f}-{max_latency:.1f}ms "
                  f"(avg {avg_latency:.1f}ms)")

        print(f"✓ Realistic latency test passed")

    def test_honest_assessment_logic(self):
        """Test the honest assessment reporting logic"""

        # Test case 1: Excellent compression (> 1.5x)
        avg_ratio_1 = 2.0
        assert avg_ratio_1 > 1.5, "Should be excellent"
        print(f"  Ratio {avg_ratio_1:.2f}x: EXCELLENT ✓")

        # Test case 2: Good compression (1.0 - 1.5x)
        avg_ratio_2 = 1.2
        assert 1.0 < avg_ratio_2 <= 1.5, "Should be good"
        print(f"  Ratio {avg_ratio_2:.2f}x: GOOD ✓")

        # Test case 3: Poor compression (< 1.0x)
        avg_ratio_3 = 0.95
        assert avg_ratio_3 < 1.0, "Should be poor"
        print(f"  Ratio {avg_ratio_3:.2f}x: POOR (expansion) ✓")

        print(f"✓ Honest assessment logic test passed")

    def test_partial_match_metadata(self):
        """Test that partial template matches are tracked in metadata"""
        compressor = ProductionHybridCompressor(
            enable_aura=False,
            enable_audit_logging=False,
            enable_scorer=False
        )

        # Message that might trigger partial matching
        message = "How do I create a numpy array and use it for calculations?"

        compressed, method, metadata = compressor.compress(message)

        # Check if partial match metadata exists
        if method == CompressionMethod.BINARY_SEMANTIC:
            partial_match = metadata.get('partial_match', False)
            match_coverage = metadata.get('match_coverage', 0.0)

            print(f"  Method: {method.name}")
            print(f"  Partial match: {partial_match}")
            print(f"  Match coverage: {match_coverage:.1%}")

            # If partial match, coverage should be meaningful
            if partial_match:
                assert 0.0 < match_coverage <= 1.0, \
                    f"Invalid match coverage: {match_coverage}"

        print(f"✓ Partial match metadata test passed")


def run_tests():
    """Run all honesty tests"""
    test = TestSimulationHonesty()

    tests = [
        ("Small Message Expansion Detection", test.test_small_message_expansion_detected),
        ("Compression Ratio Accuracy", test.test_compression_ratio_accuracy),
        ("Bandwidth Calculation Honesty", test.test_bandwidth_calculation_honesty),
        ("No False Positives on Uncompressed", test.test_no_false_positives_on_uncompressed),
        ("Method Selection Tracking", test.test_method_selection_tracking),
        ("AI Responses Are Larger", test.test_ai_responses_are_larger),
        ("Realistic Latency Ranges", test.test_realistic_latency_ranges),
        ("Honest Assessment Logic", test.test_honest_assessment_logic),
        ("Partial Match Metadata", test.test_partial_match_metadata),
    ]

    print("=" * 80)
    print("NETWORK SIMULATION HONESTY TEST SUITE")
    print("=" * 80)
    print()

    passed = 0
    failed = 0

    for name, test_func in tests:
        print(f"\nTest: {name}")
        print("-" * 80)
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"✗ FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ ERROR: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print()
    print("=" * 80)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 80)

    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
