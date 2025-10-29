#!/usr/bin/env python3
"""Test hardware-accelerated compression implementation."""

import sys
import os
import time
import json
import platform
from typing import Dict, Any

# Add the project root to Python path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src', 'python'))

from aura_compression.hardware_accelerated_compression import (
    HardwareAcceleratedCompressor, Architecture, HardwareFeature
)
from aura_compression.compressor import ProductionHybridCompressor

def test_hardware_accelerated_compression():
    """Test hardware-accelerated compression with different architectures."""
    print("Testing Hardware-Accelerated Compression Implementation")
    print("=" * 70)

    # Initialize components
    hardware_compressor = HardwareAcceleratedCompressor()
    base_compressor = ProductionHybridCompressor()

    # Get hardware capabilities
    capabilities = hardware_compressor.capabilities

    print("HARDWARE CAPABILITIES DETECTED:")
    print("-" * 40)
    print(f"Architecture: {capabilities.architecture.value}")
    print(f"Features: {[f.value for f in capabilities.features]}")
    print(f"CPU Count: {capabilities.cpu_count}")
    print(f"Memory: {capabilities.memory_gb:.1f} GB")
    print(f"Vector Width: {capabilities.vector_width} bytes")
    print(f"SIMD Efficiency: {capabilities.simd_efficiency:.2f}x")
    print(f"Cache Info: {capabilities.cache_info}")
    print()

    # Test messages of different sizes
    test_messages = [
        "Hello World",  # Small message
        "This is a test message for compression testing purposes.",  # Medium message
        "This is a much longer message that contains more text and should compress better with various algorithms including semantic compression and template matching. It has enough content to test different compression strategies effectively under hardware acceleration."  # Large message
    ]

    results = []

    print("COMPRESSION PERFORMANCE TEST:")
    print("-" * 40)

    for i, message in enumerate(test_messages):
        print(f"\nMessage {i+1} ({len(message)} chars): {message[:60]}{'...' if len(message) > 60 else ''}")

        # Test hardware-accelerated compression
        start_time = time.time()
        compressed, method, metadata = hardware_compressor.compress_hardware_optimized(
            message, base_compressor
        )
        compression_time = (time.time() - start_time) * 1000

        # Calculate compression metrics
        original_size = len(message.encode('utf-8'))
        compressed_size = len(compressed)
        ratio = original_size / compressed_size if compressed_size > 0 else 1.0

        print(f"  Method: {method}")
        print(f"  Hardware Optimized: {metadata.get('hardware_optimized', False)}")
        print(f"  SIMD Used: {metadata.get('simd_used', False)}")
        print(f"  Compression Time: {compression_time:.2f}ms")
        print(f"  Hardware Optimization Time: {metadata.get('hardware_optimization_time', 0):.2f}ms")
        print(f"  Original Size: {original_size} bytes")
        print(f"  Compressed Size: {compressed_size} bytes")
        print(f"  Ratio: {ratio:.2f}x")
        print(f"  Architecture: {metadata.get('architecture', 'unknown')}")
        print(f"  Vector Width: {metadata.get('vector_width', 'unknown')}")

        # Architecture-specific details
        if 'avx2_optimizations' in metadata:
            print(f"  AVX2 Optimizations: {metadata['avx2_optimizations']}")
            print(f"  Vector Operations: {metadata.get('vector_operations', 0)}")
            print(f"  Expected Speedup: {metadata.get('expected_speedup', 1.0)}x")

        if 'neon_optimizations' in metadata:
            print(f"  NEON Optimizations: {metadata['neon_optimizations']}")
            print(f"  Vector Operations: {metadata.get('vector_operations', 0)}")
            print(f"  Expected Speedup: {metadata.get('expected_speedup', 1.0)}x")

        if 'cache_optimizations' in metadata:
            print(f"  Cache Optimizations: {metadata['cache_optimizations']}")
            if 'chunk_size' in metadata:
                print(f"  Chunk Size: {metadata['chunk_size']} bytes")
                print(f"  Num Chunks: {metadata.get('num_chunks', 1)}")

        result = {
            'message_index': i,
            'original_size': original_size,
            'compressed_size': compressed_size,
            'ratio': ratio,
            'method': method,
            'compression_time': compression_time,
            'hardware_optimization_time': metadata.get('hardware_optimization_time', 0),
            'architecture': metadata.get('architecture'),
            'simd_used': metadata.get('simd_used', False),
            'vector_width': metadata.get('vector_width'),
            'simd_efficiency': metadata.get('simd_efficiency'),
            'features': metadata.get('features', []),
            'optimizations_applied': {
                'avx2': 'avx2_optimizations' in metadata,
                'avx512': 'avx512_optimizations' in metadata,
                'neon': 'neon_optimizations' in metadata,
                'cache': 'cache_optimizations' in metadata,
                'memory': 'memory_alignment' in metadata or 'arm_optimizations' in metadata
            }
        }
        results.append(result)

    # Print summary statistics
    print("\n" + "=" * 70)
    print("HARDWARE-ACCELERATED COMPRESSION SUMMARY")
    print("=" * 70)

    total_ratio = sum(r['ratio'] for r in results) / len(results)
    total_time = sum(r['compression_time'] for r in results)
    avg_time = total_time / len(results)
    total_hw_time = sum(r['hardware_optimization_time'] for r in results)
    avg_hw_time = total_hw_time / len(results)

    simd_used_count = sum(1 for r in results if r['simd_used'])
    optimizations_applied = sum(sum(r['optimizations_applied'].values()) for r in results)

    print(f"  Average Compression Ratio: {total_ratio:.2f}x")
    print(f"  Average Compression Time: {avg_time:.2f}ms")
    print(f"  Average Hardware Optimization Time: {avg_hw_time:.2f}ms")
    print(f"  SIMD Acceleration Used: {simd_used_count}/{len(results)} messages")
    print(f"  Total Optimizations Applied: {optimizations_applied}")
    print(f"  Architecture: {capabilities.architecture.value}")
    print(f"  SIMD Efficiency: {capabilities.simd_efficiency:.2f}x")

    # Get hardware stats
    print("\n" + "=" * 70)
    print("HARDWARE STATISTICS")
    print("=" * 70)

    hw_stats = hardware_compressor.get_hardware_stats()
    print(json.dumps(hw_stats, indent=2))

    # Save results to file
    output_file = "/Users/hendrixx./AURA/hardware_accelerated_test_results.json"
    with open(output_file, 'w') as f:
        json.dump({
            'hardware_capabilities': hw_stats['hardware_capabilities'],
            'compression_results': results,
            'summary': {
                'average_ratio': total_ratio,
                'average_time': avg_time,
                'simd_usage': f"{simd_used_count}/{len(results)}",
                'optimizations_applied': optimizations_applied
            }
        }, f, indent=2)

    print(f"\nDetailed results saved to: {output_file}")

    return results, hw_stats

def test_architecture_detection():
    """Test architecture detection logic."""
    print("\n" + "=" * 70)
    print("TESTING ARCHITECTURE DETECTION")
    print("=" * 70)

    from aura_compression.hardware_accelerated_compression import HardwareCapabilities

    capabilities = HardwareCapabilities()

    print("Architecture Detection Results:")
    print(f"  Detected Architecture: {capabilities.architecture.value}")
    print(f"  Platform Machine: {platform.machine()}")
    print(f"  Available Features: {[f.value for f in capabilities.features]}")
    print(f"  Vector Width: {capabilities.vector_width} bytes")
    print(f"  SIMD Efficiency: {capabilities.simd_efficiency:.2f}x")
    print(f"  CPU Count: {capabilities.cpu_count}")
    print(f"  Memory: {capabilities.memory_gb:.1f} GB")

    # Test feature detection
    expected_features = []
    if capabilities.architecture == Architecture.X86_64:
        expected_features = [HardwareFeature.AVX2, HardwareFeature.AVX512]
    elif capabilities.architecture == Architecture.ARM64:
        expected_features = [HardwareFeature.NEON]

    detected_features = [f for f in capabilities.features if f != HardwareFeature.NONE]
    print(f"  Expected Features: {[f.value for f in expected_features]}")
    print(f"  Detected Features: {[f.value for f in detected_features]}")

    print("\nArchitecture detection test completed.")

if __name__ == "__main__":
    try:
        # Test architecture detection
        test_architecture_detection()

        # Test hardware-accelerated compression
        results, hw_stats = test_hardware_accelerated_compression()

        print("\n" + "=" * 70)
        print("ALL HARDWARE ACCELERATION TESTS COMPLETED SUCCESSFULLY")
        print("=" * 70)

    except Exception as e:
        print(f"Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)