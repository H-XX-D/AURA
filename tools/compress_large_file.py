#!/usr/bin/env python3
"""
AURA Large File Compression Tool
Compress large files using streaming with parallel processing.

Usage:
    python compress_large_file.py input.txt output.aura
    python compress_large_file.py input.txt output.aura --workers 16 --chunk-size 10
"""

import sys
import time
import argparse
from pathlib import Path
from multiprocessing import cpu_count, Pool
from typing import Tuple

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from aura_compression.compressor_refactored import ProductionHybridCompressor


def compress_chunk(args: Tuple[bytes, int, str]) -> Tuple[int, bytes]:
    """Worker function to compress a single chunk."""
    chunk_data, chunk_id, cache_dir = args
    
    # Each worker needs its own compressor instance
    compressor = ProductionHybridCompressor(
        enable_aura=True,
        enable_ml_selection=False,
        template_cache_dir=cache_dir
    )
    
    compressed = compressor.compress(chunk_data)
    return (chunk_id, compressed)


def compress_large_file_parallel(input_path: str, output_path: str,
                                 chunk_size_bytes: int = 100,
                                 num_workers: int = None,
                                 cache_dir: str = '.aura_cache'):
    """
    Compress a large file using parallel processing.
    
    Args:
        input_path: Path to input file
        output_path: Path to output compressed file
        chunk_size_bytes: Size of each chunk in bytes
        num_workers: Number of worker processes (defaults to CPU count)
        cache_dir: Path to cache directory with SQLite DB
    """
    
    if num_workers is None:
        num_workers = cpu_count()
    
    chunk_size = chunk_size_bytes
    input_size = Path(input_path).stat().st_size
    input_size_mb = input_size / (1024 * 1024)
    
    print(f"AURA Large File Compression")
    print("=" * 70)
    print(f"Input file:     {input_path}")
    print(f"Output file:    {output_path}")
    print(f"Input size:     {input_size_mb:.2f} MB ({input_size:,} bytes)")
    print(f"Chunk size:     {chunk_size_bytes} bytes")
    print(f"Workers:        {num_workers}")
    print(f"Template store: {template_store}")
    print("-" * 70)
    print()
    
    # Read all chunks
    print("Reading chunks...")
    chunks = []
    with open(input_path, 'rb') as infile:
        chunk_id = 0
        while True:
            chunk = infile.read(chunk_size)
            if not chunk:
                break
            chunks.append((chunk, chunk_id, cache_dir))
            chunk_id += 1
    
    total_chunks = len(chunks)
    print(f"Total chunks: {total_chunks}")
    print()
    
    # Compress in parallel
    print(f"Compressing with {num_workers} workers...")
    start_time = time.time()
    
    with Pool(num_workers) as pool:
        results = []
        for i, result in enumerate(pool.imap(compress_chunk, chunks)):
            results.append(result)
            if (i + 1) % 10 == 0 or (i + 1) == total_chunks:
                elapsed = time.time() - start_time
                progress = ((i + 1) / total_chunks) * 100
                speed_kbs = ((i + 1) * chunk_size_bytes / 1024) / elapsed
                print(f"  Progress: {i+1}/{total_chunks} chunks ({progress:.1f}%) - {speed_mbs:.1f} MB/s")
    
    compression_time = time.time() - start_time
    
    # Write results in order
    print()
    print("Writing compressed file...")
    write_start = time.time()
    
    output_size = 0
    with open(output_path, 'wb') as outfile:
        for chunk_id, compressed in sorted(results):
            # Write chunk size (4 bytes) + compressed data
            outfile.write(len(compressed).to_bytes(4, 'big'))
            outfile.write(compressed)
            output_size += 4 + len(compressed)
    
    write_time = time.time() - write_start
    total_time = time.time() - start_time
    
    # Statistics
    output_size_mb = output_size / (1024 * 1024)
    compression_ratio = input_size / output_size
    space_saved = ((input_size - output_size) / input_size) * 100
    
    print()
    print("=" * 70)
    print("COMPRESSION COMPLETE")
    print("=" * 70)
    print(f"Input size:        {input_size_mb:.2f} MB")
    print(f"Output size:       {output_size_mb:.2f} MB")
    print(f"Compression ratio: {compression_ratio:.2f}x")
    print(f"Space saved:       {space_saved:.1f}%")
    print()
    print(f"Compression time:  {compression_time:.2f} seconds")
    print(f"Write time:        {write_time:.2f} seconds")
    print(f"Total time:        {total_time:.2f} seconds")
    print(f"Throughput:        {input_size_mb / total_time:.2f} MB/s")
    print()


def compress_large_file_streaming(input_path: str, output_path: str,
                                  chunk_size_bytes: int = 100,
                                  cache_dir: str = '.aura_cache'):
    """
    Compress a large file using single-threaded streaming.
    More memory efficient for HUGE files.
    
    Args:
        input_path: Path to input file
        output_path: Path to output compressed file
        chunk_size_bytes: Size of each chunk in bytes
        cache_dir: Path to cache directory with SQLite DB
    """
    
    compressor = ProductionHybridCompressor(
        enable_aura=True,
        enable_ml_selection=False,
        template_cache_dir=cache_dir
    )
    
    chunk_size = chunk_size_bytes
    input_size = Path(input_path).stat().st_size
    input_size_mb = input_size / (1024 * 1024)
    
    print(f"AURA Streaming Compression")
    print("=" * 70)
    print(f"Input file:     {input_path}")
    print(f"Output file:    {output_path}")
    print(f"Input size:     {input_size_mb:.2f} MB")
    print(f"Chunk size:     {chunk_size_bytes} bytes")
    print("-" * 70)
    print()
    
    start_time = time.time()
    output_size = 0
    chunks_processed = 0
    
    with open(input_path, 'rb') as infile, \
         open(output_path, 'wb') as outfile:
        
        while True:
            chunk = infile.read(chunk_size)
            if not chunk:
                break
            
            # Compress
            compressed = compressor.compress(chunk)
            
            # Write
            outfile.write(len(compressed).to_bytes(4, 'big'))
            outfile.write(compressed)
            
            output_size += 4 + len(compressed)
            chunks_processed += 1
            
            if chunks_processed % 10 == 0:
                elapsed = time.time() - start_time
                speed_kbs = (chunks_processed * chunk_size_bytes / 1024) / elapsed
                print(f"  Processed {chunks_processed} chunks - {speed_mbs:.1f} MB/s")
    
    total_time = time.time() - start_time
    output_size_mb = output_size / (1024 * 1024)
    compression_ratio = input_size / output_size
    space_saved = ((input_size - output_size) / input_size) * 100
    
    print()
    print("=" * 70)
    print("COMPRESSION COMPLETE")
    print("=" * 70)
    print(f"Input size:        {input_size_mb:.2f} MB")
    print(f"Output size:       {output_size_mb:.2f} MB")
    print(f"Compression ratio: {compression_ratio:.2f}x")
    print(f"Space saved:       {space_saved:.1f}%")
    print(f"Total time:        {total_time:.2f} seconds")
    print(f"Throughput:        {input_size_mb / total_time:.2f} MB/s")
    print()


def main():
    parser = argparse.ArgumentParser(
        description='Compress large files with AURA compression',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Compress with default settings (use all CPU cores)
  python compress_large_file.py input.txt output.aura
  
  # Use specific number of workers
  python compress_large_file.py input.txt output.aura --workers 8
  
  # Adjust chunk size (MB)
  python compress_large_file.py input.txt output.aura --chunk-size 10
  
  # Single-threaded streaming (for memory-constrained systems)
  python compress_large_file.py input.txt output.aura --streaming
  
  # Custom template store location
  python compress_large_file.py input.txt output.aura --cache-dir ./my_templates.json
        """
    )
    
    parser.add_argument('input', help='Input file to compress')
    parser.add_argument('output', help='Output compressed file')
    parser.add_argument('--workers', type=int, default=None,
                       help='Number of worker processes (default: CPU count)')
    parser.add_argument('--chunk-size', type=int, default=100,
                       help='Chunk size in bytes (default: 100)')
    parser.add_argument('--streaming', action='store_true',
                       help='Use single-threaded streaming (more memory efficient)')
    parser.add_argument('--cache-dir', default='.aura_cache',
                       help='Path to cache directory (default: .aura_cache)')
    
    args = parser.parse_args()
    
    # Validate input file
    if not Path(args.input).exists():
        print(f"Error: Input file not found: {args.input}")
        return 1
    
    # Run compression
    try:
        if args.streaming:
            compress_large_file_streaming(
                args.input,
                args.output,
                chunk_size_bytes=args.chunk_size,
                cache_dir=args.cache_dir
            )
        else:
            compress_large_file_parallel(
                args.input,
                args.output,
                chunk_size_bytes=args.chunk_size,
                num_workers=args.workers,
                cache_dir=args.cache_dir
            )
        return 0
    except Exception as e:
        print(f"Error during compression: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
