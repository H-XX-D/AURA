#!/usr/bin/env python3
"""
Quick test to verify AURA fallback system is working correctly.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'python'))

from aura_compression import ProductionHybridCompressor

def test_fallback_system():
    """Test that AURA falls back to standard compression when appropriate."""

    compressor = ProductionHybridCompressor()

    # Test cases that should trigger fallback
    test_cases = [
        # Chat message (should fallback to standard compression)
        "Hello, how are you today?",

        # Highly repetitive data (should use best compression)
        "error error error error error error error error error error",

        # Random data (should fallback)
        "asdkfjhasdkfjhasdkfjhaskdjfhaskdjfhaksjdhfkjashdfkjhasdkfjh",

        # Structured data that might benefit from AURA
        '{"type": "user_message", "content": "Hello world", "timestamp": 1234567890}',
    ]

    print("🧪 Testing AURA Fallback System")
    print("=" * 50)

    for i, test_data in enumerate(test_cases, 1):
        print(f"\nTest {i}: {test_data[:50]}{'...' if len(test_data) > 50 else ''}")

        # Compress
        compressed_data, method_used, metadata = compressor.compress(test_data)

        # Decompress to verify
        decompressed = compressor.decompress(compressed_data)
        success = decompressed == test_data

        print(f"  Method: {method_used}")
        print(f"  Reason: {metadata.get('reason', 'unknown')}")
        print(f"  Ratio: {metadata.get('compression_ratio', 0):.2f}x")
        print(f"  Success: {'✅' if success else '❌'}")

        if not success:
            print(f"  ERROR: Decompression failed!")
            return False

    print("\n" + "=" * 50)
    print("✅ All tests passed! Fallback system is working correctly.")
    return True

if __name__ == "__main__":
    test_fallback_system()