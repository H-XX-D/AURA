#!/usr/bin/env python3
"""
Test whitespace-aware template compression

Verifies that leading/trailing whitespace is preserved with template matching.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aura_compression.compressor_refactored import ProductionHybridCompressor


def _run_whitespace_preservation() -> bool:
    """Execute whitespace preservation checks and return success flag."""

    print("=" * 80)
    print("WHITESPACE-AWARE COMPRESSION TEST")
    print("=" * 80)
    print()

    # Create compressor
    compressor = ProductionHybridCompressor(
        enable_aura=False,
        enable_audit_logging=False,
        enable_scorer=False
    )

    # Test messages with various whitespace patterns
    test_cases = [
        ("No whitespace", "Hello world"),
        ("Leading spaces", "  Hello world"),
        ("Trailing spaces", "Hello world  "),
        ("Both spaces", "  Hello world  "),
        ("Leading tab", "\tHello world"),
        ("Trailing newline", "Hello world\n"),
        ("Mixed whitespace", " \t Hello world \n "),
        ("Template with leading space", "  I don't have access to files. Check permissions."),
        ("Template with trailing newline", "I don't have access to files. Check permissions.\n"),
        ("Template surrounded", "  I don't have access to files. Check permissions.  "),
    ]

    passed = 0
    failed = 0

    for name, message in test_cases:
        print(f"Test: {name}")
        print(f"  Original: {repr(message)}")

        try:
            # Compress
            compressed, method, metadata = compressor.compress(message)

            # Decompress
            decompressed = compressor.decompress(compressed)

            # Verify
            if decompressed == message:
                print(f"  ✓ PASS - Whitespace preserved")
                print(f"  Method: {method.name}, Ratio: {metadata.get('ratio', 0):.3f}x")
                passed += 1
            else:
                print(f"  ✗ FAIL - Whitespace lost!")
                print(f"  Expected: {repr(message)}")
                print(f"  Got:      {repr(decompressed)}")
                failed += 1

        except Exception as e:
            print(f"  ✗ ERROR: {e}")
            failed += 1

        print()

    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Passed: {passed}/{len(test_cases)}")
    print(f"Failed: {failed}/{len(test_cases)}")
    print()

    if failed == 0:
        print("✓ SUCCESS: All whitespace preserved correctly!")
        print()
        print("Whitespace-aware template matching is now working:")
        print("  - Leading whitespace detected and stored")
        print("  - Trailing whitespace detected and stored")
        print("  - Whitespace restored during decompression")
        print("  - Template compression works with any whitespace pattern")
        return True

    print(f"⚠ {failed} test(s) failed")
    return False


def test_whitespace_preservation():
    """Pytest wrapper that asserts the whitespace checks succeed."""
    assert _run_whitespace_preservation()


if __name__ == "__main__":
    success = _run_whitespace_preservation()
    sys.exit(0 if success else 1)
