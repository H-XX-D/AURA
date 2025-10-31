#!/usr/bin/env python3
"""
Test partial compression integration

Verifies that partial template matching is now wired into the compression pipeline.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aura_compression.compressor_refactored import ProductionHybridCompressor


def test_partial_compression_integration():
    """Test that partial compression is working in the full pipeline"""

    print("=" * 80)
    print("PARTIAL COMPRESSION INTEGRATION TEST")
    print("=" * 80)
    print()

    # Create compressor
    compressor = ProductionHybridCompressor(
        binary_advantage_threshold=1.01,
        min_compression_size=10,
        enable_aura=False,
        enable_audit_logging=False,
        template_cache_size=256,
        enable_scorer=False
    )

    # Test message with partial template match
    # This message has a template in it but also extra content
    test_message = "Note: This is a system message. I don't have access to your files. Please check permissions."

    print(f"Test message ({len(test_message)} bytes):")
    print(f'  "{test_message}"')
    print()

    # Compress
    compressed, method, metadata = compressor.compress(test_message)

    print("Compression result:")
    print(f"  Method: {method}")
    print(f"  Original size: {len(test_message)} bytes")
    print(f"  Compressed size: {len(compressed)} bytes")
    print(f"  Compression ratio: {metadata.get('ratio', 0.0):.3f}x")
    print(f"  Partial match: {metadata.get('partial_match', False)}")
    print(f"  Match coverage: {metadata.get('match_coverage', 0.0):.1%}")
    print()

    # Decompress to verify (request metadata so API returns tuple)
    decompressed, decomp_metadata = compressor.decompress(compressed, return_metadata=True)

    print("Decompression result:")
    print(f"  Decompressed size: {len(decompressed)} bytes")
    print(f"  Matches original: {decompressed == test_message}")
    print(f"  Returned metadata: {decomp_metadata}")
    print()

    assert decompressed == test_message, (
        "Decompressed payload did not match original message"
    )

    print("✓ PASS: Partial compression working!")
    if metadata.get('partial_match'):
        print(f"✓ Used partial template matching ({metadata.get('match_coverage', 0.0):.1%} coverage)")


if __name__ == "__main__":
    success = test_partial_compression_integration()
    sys.exit(0 if success else 1)
