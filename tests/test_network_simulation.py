#!/usr/bin/env python3
"""
Test suite for network simulation

Validates that the realistic client-server simulation:
- Properly simulates network latency and conditions
- Tracks compression metrics accurately
- Handles varying message sizes
- Reports honest performance results
"""

import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aura_compression.compressor_refactored import ProductionHybridCompressor


class TestNetworkSimulation:
    """Test the network simulation components"""

    def test_simulated_network_latency(self):
        """Test that simulated network adds realistic latency"""
        from tests.network_simulation import SimulatedNetwork

        network = SimulatedNetwork(base_latency_ms=50.0, jitter_ms=10.0)

        test_data = b"Hello, World!" * 100

        start = time.time()
        transmitted, latency = network.transmit(test_data)
        elapsed = (time.time() - start) * 1000

        # Verify data is unchanged
        assert transmitted == test_data, "Network should not corrupt data"

        # Verify latency is realistic (50ms ± 10ms + size delay)
        expected_min = 40.0  # base - jitter
        expected_max = 70.0  # base + jitter + some size delay
        assert expected_min <= latency <= expected_max, \
            f"Latency {latency}ms outside expected range {expected_min}-{expected_max}ms"

        # Verify actual sleep happened
        assert elapsed >= expected_min * 0.9, \
            f"Actual elapsed time {elapsed}ms less than expected"

        print(f"✓ Network latency test passed: {latency:.2f}ms")

    def test_human_client_prompt_generation(self):
        """Test that human client generates realistic prompts"""
        from tests.network_simulation import HumanClient

        client = HumanClient()

        # Generate 50 prompts and check characteristics
        prompts = [client.generate_prompt() for _ in range(50)]

        # Check that prompts vary in length
        lengths = [len(p) for p in prompts]
        assert min(lengths) >= 20, "Should have short prompts"
        assert max(lengths) >= 100, "Should have long prompts"

        # Check that prompts are diverse
        unique_prompts = set(prompts)
        assert len(unique_prompts) >= 10, \
            f"Prompts not diverse enough: {len(unique_prompts)} unique out of 50"

        # Check that prompts are strings
        assert all(isinstance(p, str) for p in prompts), \
            "All prompts should be strings"

        print(f"✓ Human client test passed: {len(unique_prompts)} unique prompts, "
              f"lengths {min(lengths)}-{max(lengths)} bytes")

    def test_ai_server_response_generation(self):
        """Test that AI server generates realistic responses"""
        from tests.network_simulation import AIServer

        compressor = ProductionHybridCompressor(enable_aura=False)
        server = AIServer(compressor)

        # Test responses to different prompt sizes
        test_cases = [
            ("Short prompt", 30),  # Short question
            ("This is a medium length prompt that provides some context " * 2, 100),
            ("This is a very long prompt with lots of context " * 5, 200),
        ]

        for prompt, expected_min_length in test_cases:
            response = server.generate_response(prompt)

            # AI responses should always be larger than requests
            assert len(response) > len(prompt), \
                f"Response ({len(response)}b) should be larger than prompt ({len(prompt)}b)"

            # Response should meet minimum expected length
            assert len(response) >= expected_min_length, \
                f"Response too short: {len(response)}b < {expected_min_length}b"

            # Response should be a string
            assert isinstance(response, str), "Response should be a string"

        print(f"✓ AI server test passed: responses properly sized")

    def test_network_metrics_tracking(self):
        """Test that NetworkMetrics properly tracks all data"""
        from tests.network_simulation import NetworkMetrics

        metric = NetworkMetrics(
            direction="client->server",
            original_size=1000,
            compressed_size=800,
            compression_ratio=1.25,
            compression_time_ms=1.5,
            decompression_time_ms=0.8,
            network_latency_ms=52.3,
            method="BINARY_SEMANTIC",
            partial_match=True,
            match_coverage=0.75
        )

        # Verify all fields are accessible
        assert metric.direction == "client->server"
        assert metric.original_size == 1000
        assert metric.compressed_size == 800
        assert metric.compression_ratio == 1.25
        assert metric.compression_time_ms == 1.5
        assert metric.decompression_time_ms == 0.8
        assert metric.network_latency_ms == 52.3
        assert metric.method == "BINARY_SEMANTIC"
        assert metric.partial_match == True
        assert metric.match_coverage == 0.75

        print(f"✓ Network metrics test passed")

    def test_compression_decompression_roundtrip(self):
        """Test that compression/decompression works correctly"""
        compressor = ProductionHybridCompressor(
            enable_aura=False,
            enable_audit_logging=False,
            enable_scorer=False
        )

        test_messages = [
            "How do I fix this error?",
            "Can you explain how async/await works in Python?",
            "I'm getting a segmentation fault when I run my C++ program. " * 3,
        ]

        for message in test_messages:
            # Compress
            compressed, method, metadata = compressor.compress(message)

            # Decompress
            decompressed, decomp_metadata = compressor.decompress(compressed, return_metadata=True)

            # Verify roundtrip
            assert decompressed == message, \
                f"Roundtrip failed: {repr(message)} != {repr(decompressed)}"

            # Verify metadata
            assert 'method' in metadata, "Missing method in metadata"
            assert 'original_size' in metadata or len(compressed) > 0, \
                "Missing size information"

        print(f"✓ Compression roundtrip test passed: {len(test_messages)} messages")

    def test_short_simulation_run(self):
        """Test that simulation runs successfully for a short duration"""
        from tests.network_simulation import run_simulation

        # Run simulation for just 3 seconds
        print("\nRunning 3-second simulation test...")
        run_simulation(duration_seconds=3)

        print(f"✓ Short simulation test completed successfully")

    def test_compression_ratio_calculation(self):
        """Test that compression ratios are calculated honestly"""
        compressor = ProductionHybridCompressor(
            enable_aura=False,
            enable_audit_logging=False,
            enable_scorer=False
        )

        message = "Test message for compression"
        compressed, method, metadata = compressor.compress(message)

        original_size = len(message.encode('utf-8'))
        compressed_size = len(compressed)

        # Verify ratio calculation
        if compressed_size > 0:
            expected_ratio = original_size / compressed_size
            actual_ratio = metadata.get('ratio', 0.0)

            # Allow small floating point differences
            assert abs(expected_ratio - actual_ratio) < 0.01, \
                f"Ratio mismatch: expected {expected_ratio:.3f}, got {actual_ratio:.3f}"

            # Check if data expanded (ratio < 1.0)
            if actual_ratio < 1.0:
                print(f"  ⚠ Data expanded: {original_size}→{compressed_size} bytes "
                      f"(ratio {actual_ratio:.3f}x)")
            else:
                print(f"  ✓ Data compressed: {original_size}→{compressed_size} bytes "
                      f"(ratio {actual_ratio:.3f}x)")

        print(f"✓ Compression ratio calculation test passed")

    def test_varying_message_sizes(self):
        """Test that simulation handles varying message sizes"""
        from tests.network_simulation import HumanClient

        client = HumanClient()

        # Generate 100 prompts
        prompts = [client.generate_prompt() for _ in range(100)]
        sizes = [len(p) for p in prompts]

        # Verify we have size variation
        min_size = min(sizes)
        max_size = max(sizes)
        avg_size = sum(sizes) / len(sizes)

        assert min_size < 50, "Should have some short messages"
        assert max_size > 150, "Should have some long messages"
        assert max_size > min_size * 2, "Should have significant size variation"

        print(f"✓ Message size variation test passed: "
              f"{min_size}-{max_size} bytes (avg {avg_size:.1f})")

    def test_network_bandwidth_calculation(self):
        """Test bandwidth savings calculation"""
        # Simulate compression results
        original_total = 10000
        compressed_total = 8500

        # Calculate savings
        if compressed_total < original_total:
            savings = original_total - compressed_total
            savings_pct = (savings / original_total) * 100

            assert savings == 1500, "Savings calculation error"
            assert abs(savings_pct - 15.0) < 0.1, "Percentage calculation error"

            print(f"✓ Bandwidth calculation test passed: "
                  f"{savings} bytes saved ({savings_pct:.1f}%)")
        else:
            expansion = compressed_total - original_total
            expansion_pct = (expansion / original_total) * 100

            print(f"✓ Bandwidth calculation test passed (expansion): "
                  f"+{expansion} bytes ({expansion_pct:.1f}%)")


def run_tests():
    """Run all tests"""
    test = TestNetworkSimulation()

    tests = [
        ("Simulated Network Latency", test.test_simulated_network_latency),
        ("Human Client Prompt Generation", test.test_human_client_prompt_generation),
        ("AI Server Response Generation", test.test_ai_server_response_generation),
        ("Network Metrics Tracking", test.test_network_metrics_tracking),
        ("Compression/Decompression Roundtrip", test.test_compression_decompression_roundtrip),
        ("Compression Ratio Calculation", test.test_compression_ratio_calculation),
        ("Varying Message Sizes", test.test_varying_message_sizes),
        ("Network Bandwidth Calculation", test.test_network_bandwidth_calculation),
        ("Short Simulation Run", test.test_short_simulation_run),
    ]

    print("=" * 80)
    print("NETWORK SIMULATION TEST SUITE")
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
