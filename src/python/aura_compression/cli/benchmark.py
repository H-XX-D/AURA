#!/usr/bin/env python3
"""
AURA Compression CLI - Benchmark Command

Usage:
    aura-benchmark [options]

Options:
    -n, --iterations N    Number of benchmark iterations (default: 1000)
    -s, --size SIZE       Message size in bytes (default: 1000)
    --method METHOD       Compression method (auto, gzip, aura_lite, uncompressed)
    --output FILE         Output results to file
    -v, --verbose         Verbose output
    -h, --help            Show this help message
"""

import argparse
import time
import sys
import os
import statistics
from typing import List, Dict, Any

# Add the parent directory to the path so we can import aura_compression
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from aura_compression import ProductionHybridCompressor


def generate_test_message(size: int) -> str:
    """Generate a test message of approximately the given size."""
    base_text = (
        "This is a sample message for compression benchmarking. "
        "It contains various patterns and repetitions that compression "
        "algorithms can exploit to achieve better compression ratios. "
        "The message includes common words, phrases, and structures "
        "that appear frequently in natural language communication. "
    )

    # Repeat the base text to reach desired size
    message = ""
    while len(message.encode('utf-8')) < size:
        message += base_text

    return message[:size]  # Trim to exact size


def benchmark_compression(compressor: ProductionHybridCompressor,
                         messages: List[str],
                         method: str = "auto") -> Dict[str, Any]:
    """Benchmark compression performance."""

    results = {
        'iterations': len(messages),
        'total_original_bytes': 0,
        'total_compressed_bytes': 0,
        'compression_times': [],
        'decompression_times': [],
        'methods_used': [],
    }

    for message in messages:
        original_bytes = len(message.encode('utf-8'))

        # Compress
        start_time = time.perf_counter()
        compressed, method_used, metadata = compressor.compress(message)
        compress_time = time.perf_counter() - start_time

        # Decompress
        start_time = time.perf_counter()
        decompressed = compressor.decompress(compressed)
        decompress_time = time.perf_counter() - start_time

        # Verify correctness
        if decompressed != message:
            raise ValueError("Decompression failed - data corruption detected")

        compressed_bytes = len(compressed)

        results['total_original_bytes'] += original_bytes
        results['total_compressed_bytes'] += compressed_bytes
        results['compression_times'].append(compress_time)
        results['decompression_times'].append(decompress_time)
        results['methods_used'].append(method_used)

    return results


def print_results(results: Dict[str, Any], verbose: bool = False):
    """Print benchmark results."""

    total_original = results['total_original_bytes']
    total_compressed = results['total_compressed_bytes']
    iterations = results['iterations']

    compression_ratio = total_original / total_compressed if total_compressed > 0 else 1.0
    space_saved = total_original - total_compressed
    space_saved_pct = (space_saved / total_original) * 100 if total_original > 0 else 0

    avg_compress_time = statistics.mean(results['compression_times']) * 1000  # ms
    avg_decompress_time = statistics.mean(results['decompression_times']) * 1000  # ms

    compress_throughput = (total_original / 1024 / 1024) / statistics.mean(results['compression_times'])  # MB/s
    decompress_throughput = (total_original / 1024 / 1024) / statistics.mean(results['decompression_times'])  # MB/s

    print("=" * 80)
    print("AURA COMPRESSION BENCHMARK RESULTS")
    print("=" * 80)
    print()

    print("Configuration:")
    print(f"  Iterations: {iterations}")
    print(f"  Average message size: {total_original / iterations:.0f} bytes")
    print()

    print("Compression Results:")
    print(f"  Total original size: {total_original:,} bytes")
    print(f"  Total compressed size: {total_compressed:,} bytes")
    print(f"  Compression ratio: {compression_ratio:.2f}:1")
    print(f"  Space saved: {space_saved:,} bytes ({space_saved_pct:.1f}%)")
    print()

    print("Performance:")
    print(f"  Avg compression time: {avg_compress_time:.2f} ms")
    print(f"  Avg decompression time: {avg_decompress_time:.2f} ms")
    print(f"  Compression throughput: {compress_throughput:.2f} MB/s")
    print(f"  Decompression throughput: {decompress_throughput:.2f} MB/s")
    print()

    if verbose:
        print("Method Usage:")
        method_counts = {}
        for method in results['methods_used']:
            method_counts[method] = method_counts.get(method, 0) + 1

        for method, count in sorted(method_counts.items()):
            pct = (count / iterations) * 100
            print(f"  {method}: {count} times ({pct:.1f}%)")
        print()

        print("Timing Details:")
        print(f"  Compression times - Min: {min(results['compression_times']) * 1000:.2f} ms, "
              f"Max: {max(results['compression_times']) * 1000:.2f} ms")
        print(f"  Decompression times - Min: {min(results['decompression_times']) * 1000:.2f} ms, "
              f"Max: {max(results['decompression_times']) * 1000:.2f} ms")
        print()


def save_results(results: Dict[str, Any], filename: str):
    """Save results to a JSON file."""
    import json

    # Convert numpy types to native Python types if needed
    serializable_results = {}
    for key, value in results.items():
        if isinstance(value, list):
            serializable_results[key] = [float(x) if hasattr(x, 'item') else x for x in value]
        else:
            serializable_results[key] = float(value) if hasattr(value, 'item') else value

    with open(filename, 'w') as f:
        json.dump(serializable_results, f, indent=2)

    print(f"Results saved to {filename}")


def main():
    """Main entry point for aura-benchmark CLI."""
    parser = argparse.ArgumentParser(
        description="Benchmark AURA compression performance",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        '-n', '--iterations',
        type=int,
        default=1000,
        help='Number of benchmark iterations (default: 1000)'
    )

    parser.add_argument(
        '-s', '--size',
        type=int,
        default=1000,
        help='Message size in bytes (default: 1000)'
    )

    parser.add_argument(
        '--method',
        choices=['auto', 'gzip', 'aura_lite', 'uncompressed'],
        default='auto',
        help='Compression method (default: auto)'
    )

    parser.add_argument(
        '--output',
        help='Output results to JSON file'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )

    args = parser.parse_args()

    # Generate test messages
    print(f"Generating {args.iterations} test messages of ~{args.size} bytes each...")
    messages = [generate_test_message(args.size) for _ in range(args.iterations)]

    # Initialize compressor
    enable_aura = args.method in ['auto', 'aura_lite']
    compressor = ProductionHybridCompressor(enable_aura=enable_aura)

    # Run benchmark
    print("Running benchmark...")
    try:
        results = benchmark_compression(compressor, messages, args.method)
    except Exception as e:
        print(f"❌ Benchmark failed: {e}", file=sys.stderr)
        sys.exit(1)

    # Print results
    print_results(results, args.verbose)

    # Save results if requested
    if args.output:
        save_results(results, args.output)


if __name__ == '__main__':
    main()