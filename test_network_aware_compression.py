#!/usr/bin/env python3
"""Test network-aware compression implementation."""

import sys
import os
import time
import json
from typing import Dict, Any

# Add the project root to Python path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src', 'python'))

from aura_compression.network_aware_compression import (
    NetworkAwareCompressor, NetworkCondition, CompressionStrategy
)
from aura_compression.compressor import ProductionHybridCompressor

def test_network_aware_compression():
    """Test network-aware compression with different conditions."""
    print("Testing Network-Aware Compression Implementation")
    print("=" * 60)

    # Initialize components
    network_compressor = NetworkAwareCompressor(enable_network_monitoring=False)
    base_compressor = ProductionHybridCompressor()

    # Test messages of different sizes
    test_messages = [
        "Hello World",  # Small message
        "This is a test message for compression testing purposes.",  # Medium message
        "This is a much longer message that contains more text and should compress better with various algorithms including semantic compression and template matching. It has enough content to test different compression strategies effectively."  # Large message
    ]

    # Test different network conditions
    network_conditions = [
        (NetworkCondition.EXCELLENT, "Excellent Network (< 10ms, > 100 Mbps)"),
        (NetworkCondition.GOOD, "Good Network (< 50ms, > 10 Mbps)"),
        (NetworkCondition.MODERATE, "Moderate Network (< 200ms, > 1 Mbps)"),
        (NetworkCondition.POOR, "Poor Network (< 1000ms, > 100 Kbps)"),
        (NetworkCondition.VERY_POOR, "Very Poor Network (> 1000ms or < 100 Kbps)")
    ]

    results = {}

    for condition, description in network_conditions:
        print(f"\nTesting {description}")
        print("-" * 50)

        # Force network condition for testing
        network_compressor.force_network_condition(condition)

        condition_results = []

        for i, message in enumerate(test_messages):
            print(f"\nMessage {i+1} ({len(message)} chars): {message[:50]}{'...' if len(message) > 50 else ''}")

            # Compress with network-aware strategy
            start_time = time.time()
            compressed, method, metadata = network_compressor.compress_network_aware(
                message, base_compressor
            )
            compression_time = (time.time() - start_time) * 1000

            # Calculate actual compression ratio
            original_size = len(message.encode('utf-8'))
            compressed_size = len(compressed)
            actual_ratio = original_size / compressed_size if compressed_size > 0 else 1.0

            print(f"  Method: {method}")
            print(f"  Strategy: {metadata.get('strategy', 'unknown')}")
            print(f"  Compression Time: {compression_time:.2f}ms")
            print(f"  Original Size: {original_size} bytes")
            print(f"  Compressed Size: {compressed_size} bytes")
            print(f"  Ratio: {actual_ratio:.2f}x")
            print(f"  Target Ratio: {metadata.get('target_ratio', 'N/A')}")
            print(f"  Max Latency: {metadata.get('max_latency', 'N/A')}ms")

            result = {
                'message_index': i,
                'original_size': original_size,
                'compressed_size': compressed_size,
                'ratio': actual_ratio,
                'method': method,
                'strategy': metadata.get('strategy'),
                'compression_time': compression_time,
                'target_ratio': metadata.get('target_ratio'),
                'max_latency': metadata.get('max_latency'),
                'network_condition': condition.value
            }
            condition_results.append(result)

        results[condition.value] = condition_results

        # Reset network condition
        network_compressor.reset_network_condition()

    # Print summary statistics
    print("\n" + "=" * 60)
    print("NETWORK-AWARE COMPRESSION TEST SUMMARY")
    print("=" * 60)

    for condition, condition_results in results.items():
        print(f"\n{condition.upper()} NETWORK:")
        total_ratio = sum(r['ratio'] for r in condition_results) / len(condition_results)
        total_time = sum(r['compression_time'] for r in condition_results)
        avg_time = total_time / len(condition_results)

        strategies_used = set(r['strategy'] for r in condition_results)
        methods_used = set(r['method'] for r in condition_results)

        print(f"  Average Compression Ratio: {total_ratio:.2f}x")
        print(f"  Average Compression Time: {avg_time:.2f}ms")
        print(f"  Strategies Used: {', '.join(strategies_used)}")
        print(f"  Methods Used: {', '.join(methods_used)}")

    # Get final network stats
    print("\n" + "=" * 60)
    print("FINAL NETWORK STATISTICS")
    print("=" * 60)

    stats = network_compressor.get_network_stats()
    print(json.dumps(stats, indent=2))

    # Save results to file
    output_file = "/Users/hendrixx./AURA/network_aware_test_results.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\nDetailed results saved to: {output_file}")

    return results

def test_network_condition_detection():
    """Test network condition detection logic."""
    print("\n" + "=" * 60)
    print("TESTING NETWORK CONDITION DETECTION")
    print("=" * 60)

    network_compressor = NetworkAwareCompressor(enable_network_monitoring=False)
    metrics = network_compressor.network_metrics

    # Test different latency/bandwidth combinations
    test_scenarios = [
        (5.0, 200.0, NetworkCondition.EXCELLENT),     # Low latency, high bandwidth
        (25.0, 50.0, NetworkCondition.GOOD),          # Moderate latency, good bandwidth
        (100.0, 5.0, NetworkCondition.MODERATE),      # Higher latency, moderate bandwidth
        (500.0, 0.5, NetworkCondition.POOR),          # High latency, low bandwidth
        (2000.0, 0.05, NetworkCondition.VERY_POOR)    # Very high latency, very low bandwidth
    ]

    print("Latency (ms) | Bandwidth (Mbps) | Detected Condition")
    print("-" * 55)

    for latency, bandwidth, expected in test_scenarios:
        metrics.update_latency(latency)
        metrics.update_bandwidth(bandwidth)

        detected = metrics.get_condition()
        status = "✓" if detected == expected else "✗"

        print("12")

    print("\nNetwork condition detection test completed.")

if __name__ == "__main__":
    try:
        # Run network condition detection test
        test_network_condition_detection()

        # Run main compression test
        results = test_network_aware_compression()

        print("\n" + "=" * 60)
        print("ALL TESTS COMPLETED SUCCESSFULLY")
        print("=" * 60)

    except Exception as e:
        print(f"Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)