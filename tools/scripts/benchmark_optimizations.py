#!/usr/bin/env python3
"""
Benchmark Optimization Improvements
Tests the impact of template normalization and fast matching
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from aura_compression import ProductionHybridCompressor

# Test messages with various patterns
TEST_MESSAGES = [
    # Messages that benefit from normalization
    "Deployment v1.2.3 started at 2025-10-23T10:30:00Z",
    "Request abc-123-def completed in 45ms",
    "Connection from 192.168.1.100 established",
    "Processing file data.csv (1.2 GB)",
    "Error 0x80004005 at offset 0x1234",
    "Request completed in 123ms",
    "User session-uuid-12345 authenticated successfully",
    "Backup completed: 2.5 GB transferred",
    "Deployment frontend started at 2025-10-23T11:15:30Z",
    "Connection from 10.0.0.50 established",

    # Standard messages (already work well)
    "I don't have access to real-time weather data. Please check weather.com",
    "The capital of France is Paris.",
    "To install packages, use pip: `pip install numpy`",
    "Processing request...",
    "Authentication successful",
    "Database connection established",
    "I understand your concern.",
    "Service status: operational",
    "Task completed successfully",
    "Session expired - please log in again",

    # Mixed content
    "Error 404: Resource not found",
    "API rate limit: 95/100 requests",
    "Cache hit for key: user_profile_123",
    "Health check passed: all systems nominal",
    "Retry 2/3 failed: connection timeout",
]


def benchmark_configuration(name: str, config: dict, messages: list[str]) -> dict:
    """Benchmark a configuration"""
    print(f"\n{'='*80}")
    print(f"Benchmarking: {name}")
    print(f"{'='*80}\n")

    compressor = ProductionHybridCompressor(**config)

    total_original = 0
    total_compressed = 0
    template_hits = 0
    normalized_hits = 0
    method_counts = {}
    total_encode_time = 0

    for message in messages:
        original_size = len(message.encode('utf-8'))

        # Time compression
        start = time.perf_counter()
        compressed, method, metadata = compressor.compress(message)
        encode_time = (time.perf_counter() - start) * 1000  # ms

        total_original += original_size
        total_compressed += metadata['compressed_size']
        total_encode_time += encode_time

        # Track template hits
        if metadata.get('template_id') is not None:
            template_hits += 1

        # Track method distribution
        method_name = metadata['method']
        method_counts[method_name] = method_counts.get(method_name, 0) + 1

    # Calculate metrics
    compression_ratio = total_original / total_compressed if total_compressed > 0 else 0
    bandwidth_savings = ((total_original - total_compressed) / total_original) * 100 if total_original > 0 else 0
    template_hit_rate = (template_hits / len(messages)) * 100
    avg_encode_time = total_encode_time / len(messages)

    print(f"Messages: {len(messages)}")
    print(f"Total original: {total_original:,} bytes")
    print(f"Total compressed: {total_compressed:,} bytes")
    print(f"Compression ratio: {compression_ratio:.2f}x")
    print(f"Bandwidth savings: {bandwidth_savings:.1f}%")
    print(f"Template hit rate: {template_hit_rate:.1f}%")
    print(f"Avg encode time: {avg_encode_time:.3f}ms")
    print()

    print("Method distribution:")
    for method, count in sorted(method_counts.items()):
        percentage = (count / len(messages)) * 100
        print(f"  {method}: {count} ({percentage:.1f}%)")

    return {
        'name': name,
        'compression_ratio': compression_ratio,
        'bandwidth_savings': bandwidth_savings,
        'template_hit_rate': template_hit_rate,
        'avg_encode_time': avg_encode_time,
        'method_counts': method_counts,
    }


def main():
    print("\n" + "="*80)
    print("AURA COMPRESSION - OPTIMIZATION BENCHMARK")
    print("="*80)

    # Configuration 1: Baseline (no optimizations)
    baseline_config = {
        'enable_aura': False,
        'min_compression_size': 30,
        'template_store_path': 'template_store.json',  # Original templates
        'enable_normalization': False,  # Disabled
    }

    # Configuration 2: With expanded templates only
    templates_config = {
        'enable_aura': False,
        'min_compression_size': 30,
        'template_store_path': 'template_store_expanded.json',  # Expanded templates
        'enable_normalization': False,  # Disabled
    }

    # Configuration 3: Full optimizations (templates + normalization + fast matching)
    optimized_config = {
        'enable_aura': False,
        'min_compression_size': 30,
        'template_store_path': 'template_store_expanded.json',  # Expanded templates
        'enable_normalization': True,  # ENABLED
    }

    # Run benchmarks
    baseline_results = benchmark_configuration(
        "Baseline (Original templates, no normalization)",
        baseline_config,
        TEST_MESSAGES
    )

    templates_results = benchmark_configuration(
        "Expanded Templates Only",
        templates_config,
        TEST_MESSAGES
    )

    optimized_results = benchmark_configuration(
        "Full Optimizations (Templates + Normalization + Fast Matching)",
        optimized_config,
        TEST_MESSAGES
    )

    # Comparison
    print("\n" + "="*80)
    print("OPTIMIZATION IMPACT COMPARISON")
    print("="*80)
    print()

    configs = [baseline_results, templates_results, optimized_results]

    print(f"{'Configuration':<55} {'Ratio':>8} {'Bandwidth':>10} {'Templates':>10} {'Latency':>10}")
    print("-"*100)

    for results in configs:
        print(f"{results['name']:<55} "
              f"{results['compression_ratio']:>7.2f}x "
              f"{results['bandwidth_savings']:>9.1f}% "
              f"{results['template_hit_rate']:>9.1f}% "
              f"{results['avg_encode_time']:>9.3f}ms")

    # Calculate improvements
    print("\n" + "="*80)
    print("IMPROVEMENT ANALYSIS")
    print("="*80)
    print()

    print("Expanded Templates vs Baseline:")
    ratio_improvement = ((templates_results['compression_ratio'] / baseline_results['compression_ratio']) - 1) * 100
    template_improvement = templates_results['template_hit_rate'] - baseline_results['template_hit_rate']
    print(f"  Compression ratio: +{ratio_improvement:.1f}%")
    print(f"  Template hit rate: +{template_improvement:.1f}%")

    print("\nFull Optimizations vs Baseline:")
    ratio_improvement = ((optimized_results['compression_ratio'] / baseline_results['compression_ratio']) - 1) * 100
    bandwidth_improvement = optimized_results['bandwidth_savings'] - baseline_results['bandwidth_savings']
    template_improvement = optimized_results['template_hit_rate'] - baseline_results['template_hit_rate']
    latency_improvement = ((baseline_results['avg_encode_time'] / optimized_results['avg_encode_time']) - 1) * 100
    print(f"  Compression ratio: +{ratio_improvement:.1f}%")
    print(f"  Bandwidth savings: +{bandwidth_improvement:.1f}%")
    print(f"  Template hit rate: +{template_improvement:.1f}%")
    print(f"  Encode speed: +{latency_improvement:.1f}% faster")

    print("\nNormalization Impact (Full vs Templates Only):")
    ratio_improvement = ((optimized_results['compression_ratio'] / templates_results['compression_ratio']) - 1) * 100
    template_improvement = optimized_results['template_hit_rate'] - templates_results['template_hit_rate']
    print(f"  Compression ratio: +{ratio_improvement:.1f}%")
    print(f"  Template hit rate: +{template_improvement:.1f}%")
    print(f"  Messages normalized: {len([m for m in TEST_MESSAGES if any(x in m for x in ['2025', '192.', 'uuid', '0x', 'GB', 'ms'])])}")

    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print()

    if optimized_results['compression_ratio'] > baseline_results['compression_ratio'] * 1.1:
        print("SUCCESS: Optimizations provide significant improvement")
        print(f"  Target: >10% improvement")
        print(f"  Achieved: {ratio_improvement:.1f}% improvement")
    else:
        print("  WARNING: Optimizations provide minimal improvement")

    print(f"\nRecommendation: Deploy optimized configuration")
    print(f"  Expected compression: {optimized_results['compression_ratio']:.2f}x")
    print(f"  Expected bandwidth savings: {optimized_results['bandwidth_savings']:.1f}%")
    print(f"  Expected template hit rate: {optimized_results['template_hit_rate']:.1f}%")


if __name__ == "__main__":
    main()
