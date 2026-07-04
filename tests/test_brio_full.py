#!/usr/bin/env python3
"""Comprehensive tests for brio_full module"""

import sys

from aura_compression.brio_full import BrioDecoder, BrioEncoder


def test_basic_compression():
    """Test basic compression and decompression"""
    print("=" * 60)
    print("TEST 1: Basic Compression/Decompression")
    print("=" * 60)

    encoder = BrioEncoder()
    decoder = BrioDecoder()

    test_text = "Hello, this is a test message for BRIO compression!"
    print(f"Original text: {test_text}")
    print(f"Original size: {len(test_text.encode('utf-8'))} bytes")

    # Compress
    compressed = encoder.compress(test_text)
    print(f"Compressed size: {len(compressed.payload)} bytes")
    print(f"Compression ratio: {len(test_text.encode('utf-8')) / len(compressed.payload):.2f}x")

    # Decompress
    decompressed = decoder.decompress(compressed.payload)
    print(f"Decompressed text: {decompressed.text}")

    # Verify
    if decompressed.text == test_text:
        print("✅ PASSED: Text matches original")
        return True
    else:
        print("❌ FAILED: Text doesn't match")
        return False


def test_long_text():
    """Test with longer repeating text"""
    print("\n" + "=" * 60)
    print("TEST 2: Long Repeating Text")
    print("=" * 60)

    encoder = BrioEncoder()
    decoder = BrioDecoder()

    test_text = "The quick brown fox jumps over the lazy dog. " * 20
    print(f"Text length: {len(test_text)} bytes")

    compressed = encoder.compress(test_text)
    print(f"Compressed size: {len(compressed.payload)} bytes")
    print(f"Compression ratio: {len(test_text) / len(compressed.payload):.2f}x")

    decompressed = decoder.decompress(compressed.payload)

    if decompressed.text == test_text:
        print("✅ PASSED: Long text compression works")
        return True
    else:
        print("❌ FAILED: Decompressed text doesn't match")
        return False


def test_edge_cases():
    """Test edge cases"""
    print("\n" + "=" * 60)
    print("TEST 3: Edge Cases")
    print("=" * 60)

    encoder = BrioEncoder()
    decoder = BrioDecoder()

    test_cases = [
        ("", "Empty string"),
        ("a", "Single character"),
        ("Hello World", "Simple text"),
        ("Hello 世界 🌍", "Unicode"),
        ("1234567890" * 10, "Numbers"),
        ("   spaces   ", "Spaces"),
        ("\n\t\r", "Whitespace characters"),
    ]

    passed = 0
    for text, description in test_cases:
        try:
            compressed = encoder.compress(text)
            decompressed = decoder.decompress(compressed.payload)

            if decompressed.text == text:
                print(f"✅ {description}: PASSED")
                passed += 1
            else:
                print(f"❌ {description}: FAILED - text mismatch")
        except Exception as e:
            print(f"⚠️  {description}: Exception - {e}")

    print(f"\nPassed {passed}/{len(test_cases)} edge case tests")
    return passed == len(test_cases)


def test_dictionary_compression():
    """Test dictionary-based compression with common words"""
    print("\n" + "=" * 60)
    print("TEST 4: Dictionary Compression")
    print("=" * 60)

    encoder = BrioEncoder()
    decoder = BrioDecoder()

    # Text with common words that should be in dictionary
    test_text = "the quick brown fox and the lazy dog the cat and the mouse"
    print(f"Text: {test_text}")
    print(f"Original size: {len(test_text)} bytes")

    compressed = encoder.compress(test_text)
    print(f"Compressed size: {len(compressed.payload)} bytes")
    print(f"Compression ratio: {len(test_text) / len(compressed.payload):.2f}x")

    decompressed = decoder.decompress(compressed.payload)

    if decompressed.text == test_text:
        print("✅ PASSED: Dictionary compression works")
        return True
    else:
        print("❌ FAILED: Decompressed text doesn't match")
        return False


def test_lz77_compression():
    """Test LZ77 pattern matching"""
    print("\n" + "=" * 60)
    print("TEST 5: LZ77 Pattern Matching")
    print("=" * 60)

    encoder = BrioEncoder()
    decoder = BrioDecoder()

    # Text with repeated patterns
    test_text = "ABCABCABCABC" * 5
    print(f"Text (repeated pattern): {test_text[:40]}...")
    print(f"Original size: {len(test_text)} bytes")

    compressed = encoder.compress(test_text)
    print(f"Compressed size: {len(compressed.payload)} bytes")
    print(f"Compression ratio: {len(test_text) / len(compressed.payload):.2f}x")

    decompressed = decoder.decompress(compressed.payload)

    if decompressed.text == test_text:
        print("✅ PASSED: LZ77 compression works")
        return True
    else:
        print("❌ FAILED: Decompressed text doesn't match")
        return False


def test_realistic_data():
    """Test with realistic API request data"""
    print("\n" + "=" * 60)
    print("TEST 6: Realistic API Request Data")
    print("=" * 60)

    encoder = BrioEncoder()
    decoder = BrioDecoder()

    test_text = "API REQUEST user=1001 action=login timestamp=2025-11-02T10:30:00Z status=success latency=45ms region=us-east device=mobile ip=192.0.2.100"
    print(f"Text: {test_text}")
    print(f"Original size: {len(test_text)} bytes")

    compressed = encoder.compress(test_text)
    print(f"Compressed size: {len(compressed.payload)} bytes")
    print(f"Compression ratio: {len(test_text) / len(compressed.payload):.2f}x")

    decompressed = decoder.decompress(compressed.payload)

    if decompressed.text == test_text:
        print("✅ PASSED: Realistic data compression works")
        return True
    else:
        print("❌ FAILED: Decompressed text doesn't match")
        print(f"Expected: {test_text}")
        print(f"Got: {decompressed.text}")
        return False


def main():
    """Run all tests"""
    print("\n🧪 BRIO_FULL MODULE COMPREHENSIVE TESTS")
    print("=" * 60)

    results = []

    try:
        results.append(("Basic Compression", test_basic_compression()))
        results.append(("Long Text", test_long_text()))
        results.append(("Edge Cases", test_edge_cases()))
        results.append(("Dictionary Compression", test_dictionary_compression()))
        results.append(("LZ77 Compression", test_lz77_compression()))
        results.append(("Realistic Data", test_realistic_data()))
    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}")
        import traceback

        traceback.print_exc()
        return False

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{name}: {status}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        return True
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
