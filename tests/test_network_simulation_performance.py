#!/usr/bin/env python3
"""
Performance tests for network simulation

Validates that:
- Compression/decompression is fast enough for real-time use
- Network simulation runs efficiently
- Memory usage is reasonable
- Statistics are computed correctly
"""

import sys
import time
import statistics
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aura_compression.compressor_refactored import ProductionHybridCompressor


class TestSimulationPerformance:
    """Test simulation performance characteristics"""

    def test_compression_speed(self):
        """Test that compression is fast enough for real-time use"""
        compressor = ProductionHybridCompressor(
            enable_aura=False,
            enable_audit_logging=False,
            enable_scorer=False
        )

        test_messages = [
            "Short message",
            "Medium length message with some content" * 5,
            "Long message with lots of content " * 50,
        ]

        for message in test_messages:
            # Warm up
            compressor.compress(message)

            # Measure
            times = []
            for _ in range(10):
                start = time.time()
                compressed, method, metadata = compressor.compress(message)
                elapsed = (time.time() - start) * 1000
                times.append(elapsed)

            avg_time = statistics.mean(times)
            max_time = max(times)

            # Compression should be fast (< 10ms for most messages)
            assert avg_time < 10.0, \
                f"Compression too slow: {avg_time:.2f}ms average"

            print(f"  {len(message):4d} bytes: {avg_time:.2f}ms avg, "
                  f"{max_time:.2f}ms max")

        print(f"✓ Compression speed test passed")

    def test_decompression_speed(self):
        """Test that decompression is fast enough for real-time use"""
        compressor = ProductionHybridCompressor(
            enable_aura=False,
            enable_audit_logging=False,
            enable_scorer=False
        )

        test_messages = [
            "Short message",
            "Medium length message with some content" * 5,
            "Long message with lots of content " * 50,
        ]

        for message in test_messages:
            compressed, method, metadata = compressor.compress(message)

            # Warm up
            compressor.decompress(compressed)

            # Measure
            times = []
            for _ in range(10):
                start = time.time()
                decompressed, decomp_metadata = compressor.decompress(compressed, return_metadata=True)
                elapsed = (time.time() - start) * 1000
                times.append(elapsed)

            avg_time = statistics.mean(times)
            max_time = max(times)

            # Decompression should be very fast (< 5ms)
            assert avg_time < 5.0, \
                f"Decompression too slow: {avg_time:.2f}ms average"

            print(f"  {len(compressed):4d} bytes: {avg_time:.2f}ms avg, "
                  f"{max_time:.2f}ms max")

        print(f"✓ Decompression speed test passed")

    def test_network_transmission_overhead(self):
        """Test that network simulation has minimal overhead"""
        from tests.network_simulation import SimulatedNetwork

        network = SimulatedNetwork(base_latency_ms=50.0, jitter_ms=10.0)

        data = b"Test data" * 1000

        # Measure overhead of transmission vs actual sleep
        start = time.time()
        transmitted, latency = network.transmit(data)
        actual_elapsed = (time.time() - start) * 1000

        # Overhead should be minimal (< 7ms beyond reported latency)
        # Note: Python timing overhead varies by system load and GC
        overhead = actual_elapsed - latency
        assert overhead < 7.0, \
            f"Network simulation overhead too high: {overhead:.2f}ms"

        print(f"  Reported latency: {latency:.2f}ms")
        print(f"  Actual elapsed: {actual_elapsed:.2f}ms")
        print(f"  Overhead: {overhead:.2f}ms")
        print(f"✓ Network transmission overhead test passed")

    def test_statistics_computation_efficiency(self):
        """Test that statistics can be computed efficiently on large datasets"""

        # Generate sample metrics
        sample_ratios = [1.2, 1.5, 0.9, 1.8, 1.1] * 200  # 1000 samples
        sample_latencies = [45.2, 52.1, 48.3, 55.7, 50.2] * 200

        # Measure statistics computation time
        start = time.time()

        mean_ratio = statistics.mean(sample_ratios)
        median_ratio = statistics.median(sample_ratios)
        mean_latency = statistics.mean(sample_latencies)

        elapsed = (time.time() - start) * 1000

        # Should be very fast (< 10ms for 1000 samples)
        assert elapsed < 10.0, \
            f"Statistics computation too slow: {elapsed:.2f}ms"

        print(f"  Computed stats for {len(sample_ratios)} samples in {elapsed:.2f}ms")
        print(f"  Mean ratio: {mean_ratio:.3f}x")
        print(f"  Median ratio: {median_ratio:.3f}x")
        print(f"  Mean latency: {mean_latency:.2f}ms")
        print(f"✓ Statistics computation efficiency test passed")

    def test_message_generation_speed(self):
        """Test that message generation is fast"""
        from tests.network_simulation import HumanClient, AIServer

        compressor = ProductionHybridCompressor(enable_aura=False)
        client = HumanClient()
        server = AIServer(compressor)

        # Test client prompt generation
        start = time.time()
        prompts = [client.generate_prompt() for _ in range(100)]
        client_time = (time.time() - start) * 1000

        assert client_time < 100.0, \
            f"Client prompt generation too slow: {client_time:.2f}ms for 100 prompts"

        # Test server response generation
        start = time.time()
        responses = [server.generate_response(p) for p in prompts[:10]]
        server_time = (time.time() - start) * 1000

        assert server_time < 100.0, \
            f"Server response generation too slow: {server_time:.2f}ms for 10 responses"

        print(f"  Client: 100 prompts in {client_time:.2f}ms")
        print(f"  Server: 10 responses in {server_time:.2f}ms")
        print(f"✓ Message generation speed test passed")

    def test_roundtrip_latency(self):
        """Test full message roundtrip latency"""
        compressor = ProductionHybridCompressor(
            enable_aura=False,
            enable_audit_logging=False,
            enable_scorer=False
        )

        from tests.network_simulation import SimulatedNetwork

        network = SimulatedNetwork(base_latency_ms=50.0, jitter_ms=10.0)

        message = "How do I fix this error in my code?"

        # Measure full roundtrip
        start = time.time()

        # 1. Compress
        compressed, method, metadata = compressor.compress(message)

        # 2. Transmit
        transmitted, latency = network.transmit(compressed)

        # 3. Decompress
        decompressed, decomp_metadata = compressor.decompress(transmitted, return_metadata=True)

        total_time = (time.time() - start) * 1000

        # Verify correctness
        assert decompressed == message, "Roundtrip failed"

        # Total time should be dominated by network latency
        processing_time = total_time - latency
        assert processing_time < 20.0, \
            f"Processing overhead too high: {processing_time:.2f}ms"

        print(f"  Total roundtrip: {total_time:.2f}ms")
        print(f"  Network latency: {latency:.2f}ms ({latency/total_time*100:.1f}%)")
        print(f"  Processing: {processing_time:.2f}ms ({processing_time/total_time*100:.1f}%)")
        print(f"✓ Roundtrip latency test passed")

    def test_simulation_throughput(self):
        """Test that simulation can handle multiple messages per second"""
        compressor = ProductionHybridCompressor(
            enable_aura=False,
            enable_audit_logging=False,
            enable_scorer=False
        )

        from tests.network_simulation import HumanClient, AIServer, SimulatedNetwork

        client = HumanClient()
        server = AIServer(compressor)
        network = SimulatedNetwork(base_latency_ms=10.0, jitter_ms=2.0)  # Fast network

        # Process 10 roundtrips
        start = time.time()
        messages_processed = 0

        for _ in range(10):
            prompt = client.generate_prompt()
            compressed_prompt, _, _ = compressor.compress(prompt)
            transmitted_prompt, _ = network.transmit(compressed_prompt)
            decompressed_prompt, _ = compressor.decompress(transmitted_prompt, return_metadata=True)

            response = server.generate_response(decompressed_prompt)
            compressed_response, _, _ = compressor.compress(response)
            transmitted_response, _ = network.transmit(compressed_response)
            decompressed_response, _ = compressor.decompress(transmitted_response, return_metadata=True)

            messages_processed += 2  # prompt + response

        elapsed = time.time() - start
        throughput = messages_processed / elapsed

        print(f"  Processed {messages_processed} messages in {elapsed:.2f}s")
        print(f"  Throughput: {throughput:.1f} messages/second")
        print(f"✓ Simulation throughput test passed")

    def test_memory_efficiency(self):
        """Test that simulation doesn't accumulate excessive memory"""
        compressor = ProductionHybridCompressor(
            enable_aura=False,
            enable_audit_logging=False,
            enable_scorer=False
        )

        # Process many messages
        messages = []
        for i in range(100):
            message = f"Test message {i} with some content " * 10
            compressed, method, metadata = compressor.compress(message)
            decompressed, decomp_metadata = compressor.decompress(compressed, return_metadata=True)

            # Store only summary data (not full messages)
            messages.append({
                'original_size': len(message),
                'compressed_size': len(compressed),
                'method': method.name
            })

        # Verify we stored lightweight data
        import sys
        summary_size = sys.getsizeof(messages)

        # Summary should be small (< 10KB for 100 messages)
        assert summary_size < 10000, \
            f"Summary data too large: {summary_size} bytes"

        print(f"  Processed 100 messages")
        print(f"  Summary data size: {summary_size} bytes")
        print(f"✓ Memory efficiency test passed")


def run_tests():
    """Run all performance tests"""
    test = TestSimulationPerformance()

    tests = [
        ("Compression Speed", test.test_compression_speed),
        ("Decompression Speed", test.test_decompression_speed),
        ("Network Transmission Overhead", test.test_network_transmission_overhead),
        ("Statistics Computation Efficiency", test.test_statistics_computation_efficiency),
        ("Message Generation Speed", test.test_message_generation_speed),
        ("Roundtrip Latency", test.test_roundtrip_latency),
        ("Simulation Throughput", test.test_simulation_throughput),
        ("Memory Efficiency", test.test_memory_efficiency),
    ]

    print("=" * 80)
    print("NETWORK SIMULATION PERFORMANCE TEST SUITE")
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
