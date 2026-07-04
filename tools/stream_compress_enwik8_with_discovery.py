#!/usr/bin/env python3
"""
Stream compress enwik8 with BINARY_SEMANTIC compression and pattern discovery
- 100-byte chunks for optimal template discovery
- Background discovery enabled for progressive learning
- Binary semantic compression for structured data
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aura_compression.background_workers import TemplateDiscoveryWorker
from aura_compression.compressor_refactored import ProductionHybridCompressor
from aura_compression.discovery import TemplateDiscoveryEngine
from aura_compression.enums import CompressionMethod


def stream_compress_with_discovery(input_path: str, chunk_size: int = 100) -> Dict[str, Any]:
    """Stream compress with binary semantics and pattern discovery enabled"""

    print(f"{'='*80}")
    print(f"AURA COMPRESSION - ENWIK8 WITH BINARY SEMANTICS + DISCOVERY")
    print(f"{'='*80}\n")

    print(f"Input file: {input_path}")
    print(f"Chunk size: {chunk_size} bytes (optimized for template discovery)")
    print(f"Mode: BINARY_SEMANTIC with pattern discovery\n")

    # Initialize compressor with template sync enabled
    compressor = ProductionHybridCompressor(
        template_sync_interval_seconds=10  # Sync templates every 10 seconds
    )

    # Initialize discovery engine directly
    print("Initializing pattern discovery engine...")
    discovery_engine = TemplateDiscoveryEngine(
        min_frequency=2,  # Pattern must appear 2+ times
        compression_threshold=1.05,  # 5% compression advantage
        similarity_threshold=0.6,  # 60% similarity for clustering
        starting_template_id=14000,  # Use dynamic range
        max_template_id=16383,
    )
    print("Discovery engine initialized!\n")

    # Statistics
    stats = {
        "chunks_processed": 0,
        "total_input_bytes": 0,
        "total_compressed_bytes": 0,
        "total_metadata_bytes": 0,
        "compression_time": 0.0,
        "method_counts": {},
        "chunk_ratios": [],
        "templates_discovered": 0,
        "binary_semantic_count": 0,
    }

    # Create audit log directory
    audit_dir = Path(".aura_cache/audit_logs")
    audit_dir.mkdir(parents=True, exist_ok=True)

    # Open input file
    input_file = Path(input_path)
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    total_size = input_file.stat().st_size
    print(f"Total file size: {total_size:,} bytes ({total_size/1024/1024:.2f} MB)\n")
    print("Starting compression with pattern discovery...\n")

    start_time = time.time()
    last_progress_time = start_time
    last_discovery_run = start_time

    # Open audit log for discovery
    audit_log_file = audit_dir / f"enwik8_stream_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    audit_log = open(audit_log_file, "w")

    chunk_messages = []  # Buffer for discovery

    with open(input_path, "rb") as f:
        while True:
            # Read chunk
            chunk = f.read(chunk_size)
            if not chunk:
                break

            chunk_text = chunk.decode("utf-8", errors="ignore")
            stats["chunks_processed"] += 1
            stats["total_input_bytes"] += len(chunk)

            # Compress chunk
            chunk_start = time.time()
            compressed_data, method, extra_metadata = compressor.compress(chunk_text)
            chunk_time = time.time() - chunk_start

            stats["compression_time"] += chunk_time
            stats["total_compressed_bytes"] += len(compressed_data)

            # Estimate metadata overhead
            metadata_overhead = 32
            stats["total_metadata_bytes"] += metadata_overhead

            # Track method usage
            method_name = method.name if method else "UNKNOWN"
            stats["method_counts"][method_name] = stats["method_counts"].get(method_name, 0) + 1

            if method == CompressionMethod.BINARY_SEMANTIC:
                stats["binary_semantic_count"] += 1

            # Track chunk ratio
            chunk_ratio = len(chunk) / len(compressed_data) if len(compressed_data) > 0 else 1.0
            stats["chunk_ratios"].append(chunk_ratio)

            # Write to audit log for discovery
            audit_log.write(chunk_text + "\n")
            chunk_messages.append(chunk_text)

            # Run discovery periodically
            current_time = time.time()
            if current_time - last_discovery_run >= 30.0 and len(chunk_messages) >= 50:
                print(f"\n  Running template discovery on {len(chunk_messages)} chunks...")

                # Run discovery
                try:
                    discovered = discovery_engine.discover_from_messages(chunk_messages)
                    new_templates = len(discovered)
                    stats["templates_discovered"] += new_templates

                    if new_templates > 0:
                        print(f"  ✓ Discovered {new_templates} new templates!")
                        # Add discovered templates to compressor
                        for template_id, candidate in discovered.items():
                            compressor._template_service.library.add(template_id, candidate.pattern)
                        # Sync templates to compressor
                        compressor._template_service.sync_template_store()
                    else:
                        print(f"  No new templates discovered (threshold not met)")
                except Exception as e:
                    print(f"  Discovery error: {e}")

                chunk_messages = []
                last_discovery_run = current_time

            # Progress reporting
            if current_time - last_progress_time >= 5.0 or stats["chunks_processed"] % 1000 == 0:
                progress_pct = (stats["total_input_bytes"] / total_size) * 100
                elapsed = current_time - start_time
                rate = stats["total_input_bytes"] / elapsed / 1024 / 1024 if elapsed > 0 else 0

                print(
                    f"Progress: {progress_pct:.1f}% | "
                    f"Chunks: {stats['chunks_processed']:,} | "
                    f"Input: {stats['total_input_bytes']/1024/1024:.2f} MB | "
                    f"Rate: {rate:.2f} MB/s | "
                    f"Templates: {stats['templates_discovered']}"
                )

                last_progress_time = current_time

    audit_log.close()

    # Final discovery run
    if len(chunk_messages) > 0:
        print(f"\n  Final discovery run on {len(chunk_messages)} chunks...")
        try:
            discovered = discovery_engine.discover_from_messages(chunk_messages)
            new_templates = len(discovered)
            stats["templates_discovered"] += new_templates
            if new_templates > 0:
                print(f"  ✓ Discovered {new_templates} new templates!")
                # Add discovered templates
                for template_id, candidate in discovered.items():
                    compressor._template_service.library.add(template_id, candidate.pattern)
        except Exception as e:
            print(f"  Discovery error: {e}")

    total_time = time.time() - start_time
    stats["total_time"] = total_time

    # Calculate final statistics
    total_transferred = stats["total_compressed_bytes"] + stats["total_metadata_bytes"]
    overall_ratio = (
        stats["total_input_bytes"] / stats["total_compressed_bytes"]
        if stats["total_compressed_bytes"] > 0
        else 1.0
    )
    compression_ratio_with_metadata = (
        stats["total_input_bytes"] / total_transferred if total_transferred > 0 else 1.0
    )

    bandwidth_saved = stats["total_input_bytes"] - total_transferred
    bandwidth_saved_pct = (
        (bandwidth_saved / stats["total_input_bytes"]) * 100
        if stats["total_input_bytes"] > 0
        else 0
    )

    throughput_mb_s = (
        (stats["total_input_bytes"] / total_time / 1024 / 1024) if total_time > 0 else 0
    )

    # Print results
    print(f"\n{'='*80}")
    print(f"COMPRESSION COMPLETE")
    print(f"{'='*80}\n")

    print(f"Chunks processed: {stats['chunks_processed']:,}")
    print(f"Templates discovered: {stats['templates_discovered']}")
    print(f"Total time: {total_time:.2f}s")
    print(f"Throughput: {throughput_mb_s:.2f} MB/s\n")

    print("Data Sizes:")
    print(
        f"  Input:              {stats['total_input_bytes']:>15,} bytes ({stats['total_input_bytes']/1024/1024:>8.2f} MB)"
    )
    print(
        f"  Compressed:         {stats['total_compressed_bytes']:>15,} bytes ({stats['total_compressed_bytes']/1024/1024:>8.2f} MB)"
    )
    print(
        f"  Metadata overhead:  {stats['total_metadata_bytes']:>15,} bytes ({stats['total_metadata_bytes']/1024/1024:>8.2f} MB)"
    )
    print(
        f"  Total transferred:  {total_transferred:>15,} bytes ({total_transferred/1024/1024:>8.2f} MB)\n"
    )

    print("Compression Ratios:")
    print(f"  Payload only:       {overall_ratio:.3f}:1 ({(1-1/overall_ratio)*100:+.1f}%)")
    print(
        f"  With metadata:      {compression_ratio_with_metadata:.3f}:1 ({bandwidth_saved_pct:+.1f}%)\n"
    )

    print("Performance:")
    print(f"  Total compression:  {stats['compression_time']:.2f}s")
    print(
        f"  Avg per chunk:      {stats['compression_time']/stats['chunks_processed']*1000:.3f}ms\n"
    )

    print("Compression Methods Used:")
    for method, count in sorted(stats["method_counts"].items(), key=lambda x: x[1], reverse=True):
        pct = 100 * count / stats["chunks_processed"]
        print(f"  {method:20s}: {count:>8,} chunks ({pct:>5.1f}%)")

    print(
        f"\nBinary Semantic Usage: {stats['binary_semantic_count']:,} chunks ({100*stats['binary_semantic_count']/stats['chunks_processed']:.1f}%)"
    )

    # Calculate chunk ratio statistics
    if stats["chunk_ratios"]:
        import statistics

        print(f"\nChunk Ratio Statistics:")
        print(f"  Mean:   {statistics.mean(stats['chunk_ratios']):.3f}:1")
        print(f"  Median: {statistics.median(stats['chunk_ratios']):.3f}:1")
        print(f"  Min:    {min(stats['chunk_ratios']):.3f}:1")
        print(f"  Max:    {max(stats['chunk_ratios']):.3f}:1")
        print(f"  StdDev: {statistics.stdev(stats['chunk_ratios']):.3f}")

    print(f"\n{'='*80}")
    print("PATTERN DISCOVERY RESULTS")
    print(f"{'='*80}\n")

    print(f"Total templates discovered: {stats['templates_discovered']}")
    print(f"Discovery runs: {int(total_time / 30) + 1}")
    print(f"Audit log: {audit_log_file}")

    print(f"\n{'='*80}")
    print("HONEST ASSESSMENT")
    print(f"{'='*80}\n")

    if compression_ratio_with_metadata > 1.5:
        print("✓ EXCELLENT: Discovery + Binary Semantics achieved strong compression")
        print(f"  Saved {abs(bandwidth_saved):,} bytes ({abs(bandwidth_saved_pct):.1f}%)")
    elif compression_ratio_with_metadata > 1.2:
        print("✓ GOOD: Pattern discovery improved compression meaningfully")
        print(f"  Saved {abs(bandwidth_saved):,} bytes ({abs(bandwidth_saved_pct):.1f}%)")
    elif compression_ratio_with_metadata > 1.0:
        print("✓ MODEST: Some benefit from discovery and smaller chunks")
        print(f"  Saved {abs(bandwidth_saved):,} bytes ({abs(bandwidth_saved_pct):.1f}%)")
    else:
        print("⚠ LIMITED: Small chunks + metadata overhead exceeded compression gains")
        print(f"  Net expansion: {abs(bandwidth_saved):,} bytes ({abs(bandwidth_saved_pct):.1f}%)")
        print("  100-byte chunks have high metadata overhead (32 bytes = 32% overhead)")

    print()

    return stats


def main():
    input_file = "/Users/hendrixx./Downloads/enwik8"
    chunk_size = 100  # 100-byte chunks for optimal template discovery

    if len(sys.argv) > 1:
        try:
            chunk_size = int(sys.argv[1])
        except ValueError:
            print(f"Invalid chunk size: {sys.argv[1]}, using default {chunk_size}")

    stats = stream_compress_with_discovery(input_file, chunk_size=chunk_size)

    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"enwik8_discovery_{chunk_size}_{timestamp}.json"

    with open(output_file, "w") as f:
        json.dump(stats, f, indent=2, default=str)

    print(f"Results saved to: {output_file}")


if __name__ == "__main__":
    main()
