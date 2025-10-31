#!/usr/bin/env python3
"""
Stream compress enwik8 (100MB Wikipedia XML) with AURA compression
Tests compression on large-scale real-world data
"""

import sys
import time
from pathlib import Path
from typing import Dict, Any

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aura_compression.compressor_refactored import ProductionHybridCompressor
from aura_compression.enums import CompressionMethod


def stream_compress_file(input_path: str, chunk_size: int = 8192) -> Dict[str, Any]:
    """Stream compress a large file in chunks"""

    print(f"{'='*80}")
    print(f"AURA COMPRESSION - ENWIK8 BENCHMARK")
    print(f"{'='*80}\n")

    print(f"Input file: {input_path}")
    print(f"Chunk size: {chunk_size:,} bytes\n")

    # Initialize compressor
    compressor = ProductionHybridCompressor()

    # Statistics
    stats = {
        'chunks_processed': 0,
        'total_input_bytes': 0,
        'total_compressed_bytes': 0,
        'total_metadata_bytes': 0,
        'compression_time': 0.0,
        'method_counts': {},
        'chunk_ratios': [],
    }

    # Open input file
    input_file = Path(input_path)
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    total_size = input_file.stat().st_size
    print(f"Total file size: {total_size:,} bytes ({total_size/1024/1024:.2f} MB)\n")
    print("Starting compression...\n")

    start_time = time.time()
    last_progress_time = start_time

    with open(input_path, 'rb') as f:
        while True:
            # Read chunk
            chunk = f.read(chunk_size)
            if not chunk:
                break

            chunk_text = chunk.decode('utf-8', errors='ignore')
            stats['chunks_processed'] += 1
            stats['total_input_bytes'] += len(chunk)

            # Compress chunk
            chunk_start = time.time()
            compressed_data, method, extra_metadata = compressor.compress(chunk_text)
            chunk_time = time.time() - chunk_start

            stats['compression_time'] += chunk_time
            stats['total_compressed_bytes'] += len(compressed_data)

            # Estimate metadata overhead (32 bytes per chunk)
            metadata_overhead = 32
            stats['total_metadata_bytes'] += metadata_overhead

            # Track method usage
            method_name = method.name if method else "UNKNOWN"
            stats['method_counts'][method_name] = stats['method_counts'].get(method_name, 0) + 1

            # Track chunk ratio
            chunk_ratio = len(chunk) / len(compressed_data) if len(compressed_data) > 0 else 1.0
            stats['chunk_ratios'].append(chunk_ratio)

            # Progress reporting
            current_time = time.time()
            if current_time - last_progress_time >= 5.0 or stats['chunks_processed'] % 1000 == 0:
                progress_pct = (stats['total_input_bytes'] / total_size) * 100
                elapsed = current_time - start_time
                rate = stats['total_input_bytes'] / elapsed / 1024 / 1024 if elapsed > 0 else 0

                print(f"Progress: {progress_pct:.1f}% | "
                      f"Chunks: {stats['chunks_processed']:,} | "
                      f"Input: {stats['total_input_bytes']/1024/1024:.2f} MB | "
                      f"Rate: {rate:.2f} MB/s")

                last_progress_time = current_time

    total_time = time.time() - start_time
    stats['total_time'] = total_time

    # Calculate final statistics
    total_transferred = stats['total_compressed_bytes'] + stats['total_metadata_bytes']
    overall_ratio = stats['total_input_bytes'] / stats['total_compressed_bytes'] if stats['total_compressed_bytes'] > 0 else 1.0
    compression_ratio_with_metadata = stats['total_input_bytes'] / total_transferred if total_transferred > 0 else 1.0

    bandwidth_saved = stats['total_input_bytes'] - total_transferred
    bandwidth_saved_pct = (bandwidth_saved / stats['total_input_bytes']) * 100 if stats['total_input_bytes'] > 0 else 0

    throughput_mb_s = (stats['total_input_bytes'] / total_time / 1024 / 1024) if total_time > 0 else 0

    # Print results
    print(f"\n{'='*80}")
    print(f"COMPRESSION COMPLETE")
    print(f"{'='*80}\n")

    print(f"Chunks processed: {stats['chunks_processed']:,}")
    print(f"Total time: {total_time:.2f}s")
    print(f"Throughput: {throughput_mb_s:.2f} MB/s\n")

    print("Data Sizes:")
    print(f"  Input:              {stats['total_input_bytes']:>15,} bytes ({stats['total_input_bytes']/1024/1024:>8.2f} MB)")
    print(f"  Compressed:         {stats['total_compressed_bytes']:>15,} bytes ({stats['total_compressed_bytes']/1024/1024:>8.2f} MB)")
    print(f"  Metadata overhead:  {stats['total_metadata_bytes']:>15,} bytes ({stats['total_metadata_bytes']/1024/1024:>8.2f} MB)")
    print(f"  Total transferred:  {total_transferred:>15,} bytes ({total_transferred/1024/1024:>8.2f} MB)\n")

    print("Compression Ratios:")
    print(f"  Payload only:       {overall_ratio:.3f}:1 ({(1-1/overall_ratio)*100:+.1f}%)")
    print(f"  With metadata:      {compression_ratio_with_metadata:.3f}:1 ({bandwidth_saved_pct:+.1f}%)\n")

    print("Performance:")
    print(f"  Total compression:  {stats['compression_time']:.2f}s")
    print(f"  Avg per chunk:      {stats['compression_time']/stats['chunks_processed']*1000:.3f}ms\n")

    print("Compression Methods Used:")
    for method, count in sorted(stats['method_counts'].items(), key=lambda x: x[1], reverse=True):
        pct = 100 * count / stats['chunks_processed']
        print(f"  {method:20s}: {count:>8,} chunks ({pct:>5.1f}%)")

    # Calculate chunk ratio statistics
    if stats['chunk_ratios']:
        import statistics
        print(f"\nChunk Ratio Statistics:")
        print(f"  Mean:   {statistics.mean(stats['chunk_ratios']):.3f}:1")
        print(f"  Median: {statistics.median(stats['chunk_ratios']):.3f}:1")
        print(f"  Min:    {min(stats['chunk_ratios']):.3f}:1")
        print(f"  Max:    {max(stats['chunk_ratios']):.3f}:1")
        print(f"  StdDev: {statistics.stdev(stats['chunk_ratios']):.3f}")

    print(f"\n{'='*80}")
    print("HONEST ASSESSMENT")
    print(f"{'='*80}\n")

    if compression_ratio_with_metadata > 1.5:
        print("✓ EXCELLENT: AURA achieves strong compression on Wikipedia XML data")
        print(f"  Saved {abs(bandwidth_saved):,} bytes ({abs(bandwidth_saved_pct):.1f}%) compared to uncompressed")
    elif compression_ratio_with_metadata > 1.2:
        print("✓ GOOD: AURA provides meaningful compression")
        print(f"  Saved {abs(bandwidth_saved):,} bytes ({abs(bandwidth_saved_pct):.1f}%)")
    elif compression_ratio_with_metadata > 1.0:
        print("✓ MODEST: AURA provides some compression benefit")
        print(f"  Saved {abs(bandwidth_saved):,} bytes ({abs(bandwidth_saved_pct):.1f}%)")
    else:
        print("⚠ LIMITED: Compression is not effective on this data")
        print(f"  Net expansion: {abs(bandwidth_saved):,} bytes ({abs(bandwidth_saved_pct):.1f}%)")
        print("  This is likely due to:")
        print("    - Small chunk size (metadata overhead dominates)")
        print("    - Data not suited for template-based compression")
        print("    - Need for larger chunks or different compression method")

    print()

    return stats


def main():
    input_file = "/Users/hendrixx./Downloads/enwik8"

    # Try different chunk sizes
    chunk_sizes = [8192, 16384, 32768, 65536]  # 8KB, 16KB, 32KB, 64KB

    # For first run, use 32KB chunks (good balance)
    chunk_size = 32768

    if len(sys.argv) > 1:
        try:
            chunk_size = int(sys.argv[1])
        except ValueError:
            print(f"Invalid chunk size: {sys.argv[1]}, using default {chunk_size}")

    stats = stream_compress_file(input_file, chunk_size=chunk_size)

    # Save results
    import json
    from datetime import datetime

    output_file = f"enwik8_compression_{chunk_size}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    with open(output_file, 'w') as f:
        json.dump(stats, f, indent=2, default=str)

    print(f"Results saved to: {output_file}")


if __name__ == "__main__":
    main()
