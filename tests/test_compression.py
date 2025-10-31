#!/usr/bin/env python3
"""
Simple test to check if compressor initialization works
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aura_compression.compressor_refactored import ProductionHybridCompressor

def test_compression():
    print("Initializing compressor...")
    start_time = time.time()

    compressor = ProductionHybridCompressor(
        enable_aura=True,
        enable_audit_logging=False,
        template_cache_dir=".aura_cache_parallel",
    )

    init_time = time.time() - start_time
    print(".2f")

    print("Compressing test data...")
    test_data = b"Hello, world! This is a test message for compression."
    compress_start = time.time()

    compressed = compressor.compress(test_data)

    compress_time = time.time() - compress_start
    print(".2f")
    print(f"Original size: {len(test_data)} bytes")
    print(f"Compressed size: {len(compressed)} bytes")
    print(".2f")

if __name__ == "__main__":
    test_compression()