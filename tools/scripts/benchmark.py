#!/usr/bin/env python3
"""
Simple performance benchmark for AURA compressor
"""
import time
import sys
sys.path.insert(0, '/Users/hendrixx./Desktop/AURA-main')

from aura_compression import ProductionHybridCompressor

def benchmark_compression():
    compressor = ProductionHybridCompressor(enable_aura=True)

    # Test messages of different sizes
    test_messages = [
        "Hello world",  # Short
        "I don't have access to real-time data. However, I can help you with general information.",  # Medium
        "This is a much longer message that contains more text and should provide better compression opportunities when using template-based compression algorithms. The system should be able to identify patterns and compress them efficiently.",  # Long
    ]

    print("AURA Compressor Performance Benchmark")
    print("=" * 50)

    for i, message in enumerate(test_messages):
        print(f"\nTest {i+1}: {len(message)} characters")

        # Warm up
        for _ in range(5):
            compressed, method, metadata = compressor.compress(message)
            decompressed = compressor.decompress(compressed)

        # Benchmark
        start_time = time.time()
        iterations = 100

        for _ in range(iterations):
            compressed, method, metadata = compressor.compress(message)
            decompressed = compressor.decompress(compressed)
            assert decompressed == message

        end_time = time.time()
        avg_time = (end_time - start_time) / iterations * 1000  # ms

        original_size = len(message.encode('utf-8'))
        compressed_size = len(compressed)
        ratio = original_size / compressed_size if compressed_size > 0 else 0

        print(".2f")
        print(".2f")
        print(".2f")
        print(f"  Method: {method.name}")

if __name__ == "__main__":
    benchmark_compression()