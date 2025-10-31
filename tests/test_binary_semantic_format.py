#!/usr/bin/env python3
"""
Test that binary semantic compression/decompression works with new whitespace format
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aura_compression.compressor_refactored import ProductionHybridCompressor


def test_binary_semantic_roundtrip():
    """Test basic compression and decompression"""

    compressor = ProductionHybridCompressor(
        enable_aura=False,
        enable_audit_logging=False,
        enable_scorer=False
    )

    test_cases = [
        "How do I create a numpy array?",
        "What's wrong with this code?",
        "Why am I getting this error?",
    ]

    print("Testing binary semantic compression format...")
    print()

    for i, message in enumerate(test_cases, 1):
        print(f"Test {i}: \"{message}\"")

        try:
            # Compress
            compressed, method, metadata = compressor.compress(message)
            print(f"  Compressed: {len(message)} → {len(compressed)} bytes ({method.name})")

            # Decompress
            decompressed = compressor.decompress(compressed)
            print(f"  Decompressed: {len(decompressed)} bytes")

            # Verify
            if decompressed == message:
                print(f"  ✓ PASS")
            else:
                print(f"  ✗ FAIL")
                print(f"    Expected: {repr(message)}")
                print(f"    Got:      {repr(decompressed)}")
                return False

        except Exception as e:
            print(f"  ✗ ERROR: {e}")
            import traceback
            traceback.print_exc()
            return False

        print()

    print("✓ All tests passed")
    return True


if __name__ == "__main__":
    success = test_binary_semantic_roundtrip()
    sys.exit(0 if success else 1)
