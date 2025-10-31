#!/usr/bin/env python3
"""
Test that compression falls back to UNCOMPRESSED when expanding data
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aura_compression.compressor_refactored import ProductionHybridCompressor
from aura_compression.enums import CompressionMethod


def test_fallback_to_uncompressed():
    """Test that small diverse messages fall back to UNCOMPRESSED"""

    print("Testing fallback to UNCOMPRESSED when data would expand...\n")

    compressor = ProductionHybridCompressor(
        binary_advantage_threshold=1.01,
        min_compression_size=10,
        enable_audit_logging=False
    )

    # Small, diverse messages that will expand with AuraLite
    test_messages = [
        "a1b2c3d4e5f6",
        "xyz123abc456",
        "test_msg_001",
        "random_data_42",
        "short_text_99",
    ]

    results = []

    for msg in test_messages:
        original_size = len(msg.encode('utf-8'))
        compressed, method, metadata = compressor.compress(msg)
        compressed_size = len(compressed)
        ratio = metadata.get('ratio', 0.0)

        result = {
            'message': msg,
            'original': original_size,
            'compressed': compressed_size,
            'ratio': ratio,
            'method': method.name,
            'expanding': compressed_size > original_size
        }
        results.append(result)

        status = "✅ FALLBACK" if method == CompressionMethod.UNCOMPRESSED else "❌ NO FALLBACK"
        expanding = "EXPANDING" if result['expanding'] else "OK"

        print(f"{status} | {msg:15s} | {original_size:3d}→{compressed_size:3d} bytes | "
              f"{ratio:.3f}:1 | {method.name:15s} | {expanding}")

    # Analysis
    print(f"\n{'='*80}")
    print("ANALYSIS")
    print(f"{'='*80}\n")

    expanding_count = sum(1 for r in results if r['expanding'])
    uncompressed_count = sum(1 for r in results if r['method'] == 'UNCOMPRESSED')
    auralite_count = sum(1 for r in results if r['method'] == 'AURALITE')

    print(f"Messages tested: {len(results)}")
    print(f"Expanding: {expanding_count}")
    print(f"Used UNCOMPRESSED: {uncompressed_count}")
    print(f"Used AURALITE: {auralite_count}\n")

    # Check if fallback is working
    if expanding_count > 0:
        print(f"⚠️  WARNING: {expanding_count} messages expanded")
        print(f"   These SHOULD have fallen back to UNCOMPRESSED")
        print(f"   But {auralite_count} used AURALITE instead\n")

        if auralite_count > 0 and uncompressed_count == 0:
            print("❌ FALLBACK NOT WORKING: All expanding messages used AURALITE")
            print("   Expected: UNCOMPRESSED when ratio <= 1.0")
            return False
        else:
            print("✅ FALLBACK PARTIALLY WORKING: Some used UNCOMPRESSED")
            return True
    else:
        print("✅ All messages compressed successfully (no expansion)")
        return True


def test_larger_message_with_expansion():
    """Test larger message that might expand"""

    print(f"\n{'='*80}")
    print("Testing larger diverse message...")
    print(f"{'='*80}\n")

    compressor = ProductionHybridCompressor()

    # Random-looking message that will likely expand
    msg = ''.join(chr(65 + (i % 26)) for i in range(100))  # ABCDEFGH... x 100 chars

    original_size = len(msg.encode('utf-8'))
    compressed, method, metadata = compressor.compress(msg)
    compressed_size = len(compressed)
    ratio = metadata.get('ratio', 0.0)

    print(f"Message: {msg[:50]}... ({len(msg)} chars)")
    print(f"Original size: {original_size} bytes")
    print(f"Compressed size: {compressed_size} bytes")
    print(f"Ratio: {ratio:.3f}:1")
    print(f"Method: {method.name}")

    if compressed_size > original_size:
        print(f"\n⚠️  Data expanded by {compressed_size - original_size} bytes")
        if method == CompressionMethod.UNCOMPRESSED:
            print("✅ FALLBACK WORKED: Used UNCOMPRESSED")
            return True
        else:
            print(f"❌ FALLBACK FAILED: Used {method.name} instead of UNCOMPRESSED")
            return False
    else:
        print(f"\n✅ Data compressed successfully")
        return True


if __name__ == "__main__":
    print("="*80)
    print("FALLBACK TO UNCOMPRESSED TEST")
    print("="*80)
    print()

    test1 = test_fallback_to_uncompressed()
    test2 = test_larger_message_with_expansion()

    print(f"\n{'='*80}")
    print("FINAL RESULTS")
    print(f"{'='*80}\n")

    if test1 and test2:
        print("✅ FALLBACK TO UNCOMPRESSED: WORKING")
    else:
        print("❌ FALLBACK TO UNCOMPRESSED: NOT WORKING")
        print("\nPossible issues:")
        print("1. best_ratio check may not be triggering")
        print("2. UNCOMPRESSED may not be in available strategies")
        print("3. Metadata may not be returned correctly")
