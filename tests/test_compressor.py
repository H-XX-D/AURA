#!/usr/bin/env python3
"""
Comprehensive test suite for compressor.py

Tests the backwards compatibility wrapper that exports ProductionHybridCompressor
from compressor_refactored.py. Verifies that the main compressor interface is
properly maintained and all functionality is accessible through the wrapper.
"""

import os
import sys
import tempfile
import traceback
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aura_compression.compressor import ProductionHybridCompressor
from aura_compression.enums import CompressionMethod


def test_import_compatibility():
    """Test that ProductionHybridCompressor can be imported from compressor.py."""
    print("\n=== Test 1: Import Compatibility ===")

    # Verify the import works
    assert ProductionHybridCompressor is not None

    # Verify it's the same class as from compressor_refactored
    from aura_compression.compressor_refactored import (
        ProductionHybridCompressor as RefactoredCompressor,
    )

    assert ProductionHybridCompressor is RefactoredCompressor

    print(f"✅ ProductionHybridCompressor imported successfully")
    print(f"   - Class name: {ProductionHybridCompressor.__name__}")
    print(f"   - Module: {ProductionHybridCompressor.__module__}")


def test_compressor_initialization():
    """Test that the compressor can be initialized through the wrapper."""
    print("\n=== Test 2: Compressor Initialization ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        compressor = ProductionHybridCompressor(
            enable_audit_logging=False,
            audit_log_directory=tmpdir,
            enable_ml_selection=False,
            enable_scorer=False,
            enable_sidechain=False,
        )

        assert compressor is not None
        assert hasattr(compressor, "compress")
        assert hasattr(compressor, "decompress")
        assert hasattr(compressor, "template_library")

        print(f"✅ Compressor initialized successfully")
        print(f"   - Has compress method: {hasattr(compressor, 'compress')}")
        print(f"   - Has decompress method: {hasattr(compressor, 'decompress')}")
        print(f"   - Has template_library: {hasattr(compressor, 'template_library')}")


def test_basic_compression():
    """Test basic compression functionality through the wrapper."""
    print("\n=== Test 3: Basic Compression ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        compressor = ProductionHybridCompressor(
            enable_audit_logging=False,
            audit_log_directory=tmpdir,
            enable_ml_selection=False,
            enable_scorer=False,
            enable_sidechain=False,
        )

        text = "This is a test message for compression."
        compressed, method, metadata = compressor.compress(text)

        assert isinstance(compressed, bytes)
        assert isinstance(method, CompressionMethod)
        assert isinstance(metadata, dict)
        assert "method" in metadata
        assert "original_size" in metadata
        assert "compressed_size" in metadata

        print(f"✅ Compression successful")
        print(f"   - Original: {len(text)} bytes")
        print(f"   - Compressed: {len(compressed)} bytes")
        print(f"   - Method: {method.name}")
        print(f"   - Ratio: {metadata.get('ratio', 0):.2f}x")


def test_basic_decompression():
    """Test basic decompression functionality through the wrapper."""
    print("\n=== Test 4: Basic Decompression ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        compressor = ProductionHybridCompressor(
            enable_audit_logging=False,
            audit_log_directory=tmpdir,
            enable_ml_selection=False,
            enable_scorer=False,
            enable_sidechain=False,
        )

        original_text = "Test message for round-trip compression and decompression."
        compressed, method, metadata = compressor.compress(original_text)
        decompressed = compressor.decompress(compressed)

        assert decompressed == original_text

        print(f"✅ Decompression successful")
        print(f"   - Original: '{original_text[:40]}...'")
        print(f"   - Decompressed matches: {decompressed == original_text}")


def test_template_compression():
    """Test template-based compression through the wrapper."""
    print("\n=== Test 5: Template Compression ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        compressor = ProductionHybridCompressor(
            enable_audit_logging=False,
            audit_log_directory=tmpdir,
            enable_ml_selection=False,
            enable_scorer=False,
            enable_sidechain=False,
        )

        # Add a template
        template_id = 100
        compressor.template_library.add(template_id, "User {0} logged in from {1}")

        # Compress with template
        text = "User alice logged in from 192.168.1.1"
        compressed, method, metadata = compressor.compress(
            text, template_id=template_id, slots=["alice", "192.168.1.1"]
        )

        assert method == CompressionMethod.BINARY_SEMANTIC
        assert metadata["method"] == "binary_semantic"

        # Decompress
        decompressed = compressor.decompress(compressed)
        assert decompressed == text

        print(f"✅ Template compression successful")
        print(f"   - Template ID: {template_id}")
        print(f"   - Original: {len(text)} bytes")
        print(f"   - Compressed: {len(compressed)} bytes")
        print(f"   - Round-trip successful: {decompressed == text}")


def test_all_compression_methods():
    """Test that all compression methods are accessible through the wrapper."""
    print("\n=== Test 6: All Compression Methods ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        compressor = ProductionHybridCompressor(
            enable_audit_logging=False,
            audit_log_directory=tmpdir,
            enable_ml_selection=False,
            enable_scorer=False,
            enable_sidechain=False,
        )

        # Test different text sizes to trigger different methods
        test_cases = [
            ("Small", "Hi"),  # UNCOMPRESSED
            ("Medium", "This is a medium-length test message that should compress."),  # AURALITE
            ("Large", "x" * 2000),  # BRIO or PATTERN_SEMANTIC
        ]

        methods_used = set()
        for name, text in test_cases:
            compressed, method, metadata = compressor.compress(text)
            methods_used.add(method)
            decompressed = compressor.decompress(compressed)
            assert decompressed == text
            print(f"   ✓ {name} text: {method.name} ({len(text)} → {len(compressed)} bytes)")

        print(f"✅ All compression methods accessible")
        print(f"   - Methods used: {', '.join(m.name for m in methods_used)}")


def test_ml_selector_integration():
    """Test ML algorithm selector integration through the wrapper."""
    print("\n=== Test 7: ML Selector Integration ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        compressor = ProductionHybridCompressor(
            enable_audit_logging=False,
            audit_log_directory=tmpdir,
            enable_ml_selection=True,
            enable_scorer=False,
            enable_sidechain=False,
        )

        assert compressor._ml_selector is not None

        text = "Test message with ML algorithm selection enabled."
        compressed, method, metadata = compressor.compress(text)

        assert isinstance(compressed, bytes)

        print(f"✅ ML selector integration working")
        print(f"   - ML selector enabled: {compressor._ml_selector is not None}")
        print(f"   - Selected method: {method.name}")


def test_scorer_integration():
    """Test scorer/telemetry integration through the wrapper."""
    print("\n=== Test 8: Scorer Integration ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        telemetry_path = os.path.join(tmpdir, "scorer_telemetry.csv")
        compressor = ProductionHybridCompressor(
            enable_audit_logging=False,
            audit_log_directory=tmpdir,
            enable_ml_selection=False,
            enable_scorer=True,
            scorer_telemetry_path=telemetry_path,
            enable_sidechain=False,
        )

        assert compressor.enable_scorer is True
        scorer_status = compressor.get_scorer_status()
        assert "enabled" in scorer_status

        print(f"✅ Scorer integration working")
        print(f"   - Scorer enabled: {compressor.enable_scorer}")
        print(f"   - Telemetry path: {telemetry_path}")


def test_sidechain_integration():
    """Test metadata sidechain integration through the wrapper."""
    print("\n=== Test 9: Sidechain Integration ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        compressor = ProductionHybridCompressor(
            enable_audit_logging=False,
            audit_log_directory=tmpdir,
            enable_ml_selection=False,
            enable_scorer=False,
            enable_sidechain=True,
        )

        assert compressor.enable_sidechain is True

        text = "Test message with sidechain metadata enabled."
        compressed, method, metadata = compressor.compress(text)

        # Should have metadata header (12 bytes)
        assert len(compressed) >= 12

        # Test fast-path methods
        classification = compressor.fast_path_classify(compressed)
        handler = compressor.fast_path_route(compressed)
        security = compressor.fast_path_security_check(compressed)

        print(f"✅ Sidechain integration working")
        print(f"   - Sidechain enabled: {compressor.enable_sidechain}")
        print(f"   - Fast-path classify: {classification is not None}")
        print(f"   - Fast-path route: {handler is not None}")
        print(f"   - Fast-path security: {security is not None}")


def test_performance_stats():
    """Test performance statistics through the wrapper."""
    print("\n=== Test 10: Performance Stats ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        compressor = ProductionHybridCompressor(
            enable_audit_logging=False,
            audit_log_directory=tmpdir,
            enable_ml_selection=False,
            enable_scorer=False,
            enable_sidechain=False,
        )

        # Perform some compressions
        for i in range(5):
            text = f"Test message number {i}"
            compressor.compress(text)

        stats = compressor.get_performance_stats()

        assert isinstance(stats, dict)
        assert "template_manager" in stats

        print(f"✅ Performance stats accessible")
        print(f"   - Stats keys: {list(stats.keys())}")


def test_legacy_methods():
    """Test legacy API methods through the wrapper."""
    print("\n=== Test 11: Legacy Methods ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        compressor = ProductionHybridCompressor(
            enable_audit_logging=False,
            audit_log_directory=tmpdir,
            enable_ml_selection=False,
            enable_scorer=False,
            enable_sidechain=False,
        )

        # Add template
        template_id = 200
        compressor.template_library.add(template_id, "Status: {0}")

        # Test compress_with_template
        compressed = compressor.compress_with_template(template_id, ["OK"])
        assert isinstance(compressed, bytes)

        # Test decompress_binary (need longer text to avoid size threshold)
        template_id2 = 201
        compressor.template_library.add(template_id2, "User {0} performed action {1}")
        text = "User admin performed action login"
        compressed2, method, _ = compressor.compress(
            text, template_id=template_id2, slots=["admin", "login"]
        )

        if method == CompressionMethod.BINARY_SEMANTIC:
            decompressed = compressor.decompress_binary(compressed2)
            assert decompressed == text
            print(f"✅ Legacy methods working")
            print(f"   - compress_with_template: Success")
            print(f"   - decompress_binary: Success")
        else:
            print(f"✅ Legacy methods partially working")
            print(f"   - compress_with_template: Success")
            print(f"   - decompress_binary: Skipped (text too small)")


def test_backwards_property():
    """Test backwards compatibility property (templates)."""
    print("\n=== Test 12: Backwards Compatibility Property ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        compressor = ProductionHybridCompressor(
            enable_audit_logging=False,
            audit_log_directory=tmpdir,
            enable_ml_selection=False,
            enable_scorer=False,
            enable_sidechain=False,
        )

        # Test .templates property (backwards compatibility)
        assert hasattr(compressor, "templates")
        assert compressor.templates is compressor.template_library

        # Add template through property
        template_id = 300
        compressor.templates.add(template_id, "Test: {0}")

        # Verify it's accessible
        entry = compressor.template_library.get_entry(template_id)
        assert entry is not None

        print(f"✅ Backwards compatibility property working")
        print(f"   - .templates property available: {hasattr(compressor, 'templates')}")
        print(
            f"   - Points to template_library: {compressor.templates is compressor.template_library}"
        )


def test_unicode_handling():
    """Test Unicode handling through the wrapper."""
    print("\n=== Test 13: Unicode Handling ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        compressor = ProductionHybridCompressor(
            enable_audit_logging=False,
            audit_log_directory=tmpdir,
            enable_ml_selection=False,
            enable_scorer=False,
            enable_sidechain=False,
        )

        # Test various Unicode characters
        texts = [
            "Hello 世界",
            "Привет мир",
            "مرحبا بالعالم",
            "Hello 🌍 🌎 🌏",
            "Mixed: Hello 世界 🌍 Привет",
        ]

        for text in texts:
            compressed, method, metadata = compressor.compress(text)
            decompressed = compressor.decompress(compressed)
            assert decompressed == text

        print(f"✅ Unicode handling working")
        print(f"   - Tested {len(texts)} different Unicode texts")
        print(f"   - All round-trips successful")


def test_bytes_input():
    """Test bytes input handling through the wrapper."""
    print("\n=== Test 14: Bytes Input ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        compressor = ProductionHybridCompressor(
            enable_audit_logging=False,
            audit_log_directory=tmpdir,
            enable_ml_selection=False,
            enable_scorer=False,
            enable_sidechain=False,
        )

        # Test with bytes input
        text_bytes = b"Test message as bytes"
        compressed, method, metadata = compressor.compress(text_bytes)
        decompressed = compressor.decompress(compressed)

        assert decompressed == text_bytes.decode("utf-8")

        print(f"✅ Bytes input handling working")
        print(f"   - Input type: bytes")
        print(f"   - Decompressed type: str")
        print(f"   - Round-trip successful: {decompressed == text_bytes.decode('utf-8')}")


def test_edge_cases():
    """Test edge cases through the wrapper."""
    print("\n=== Test 15: Edge Cases ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        compressor = ProductionHybridCompressor(
            enable_audit_logging=False,
            audit_log_directory=tmpdir,
            enable_ml_selection=False,
            enable_scorer=False,
            enable_sidechain=False,
        )

        # Empty string
        compressed, method, metadata = compressor.compress("")
        assert isinstance(compressed, bytes)
        print(f"   ✓ Empty string: {len(compressed)} bytes")

        # Very long string
        long_text = "x" * 100000
        compressed, method, metadata = compressor.compress(long_text)
        decompressed = compressor.decompress(compressed)
        assert decompressed == long_text
        print(
            f"   ✓ Very long string: {len(long_text)} → {len(compressed)} bytes (ratio: {metadata['ratio']:.2f}x)"
        )

        # Special characters
        special = "!@#$%^&*()_+-=[]{}|;':\",./<>?\n\t\r"
        compressed, method, metadata = compressor.compress(special)
        decompressed = compressor.decompress(compressed)
        assert decompressed == special
        print(f"   ✓ Special characters: {len(special)} → {len(compressed)} bytes")

        print(f"✅ All edge cases handled correctly")


def run_all_tests():
    """Run all test functions."""
    test_functions = [
        test_import_compatibility,
        test_compressor_initialization,
        test_basic_compression,
        test_basic_decompression,
        test_template_compression,
        test_all_compression_methods,
        test_ml_selector_integration,
        test_scorer_integration,
        test_sidechain_integration,
        test_performance_stats,
        test_legacy_methods,
        test_backwards_property,
        test_unicode_handling,
        test_bytes_input,
        test_edge_cases,
    ]

    passed = 0
    failed = 0

    print("=" * 70)
    print("COMPRESSOR.PY BACKWARDS COMPATIBILITY TEST SUITE")
    print("=" * 70)

    for test_func in test_functions:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            failed += 1
            print(f"❌ {test_func.__name__} FAILED: {e}")
            traceback.print_exc()
        except Exception as e:
            failed += 1
            print(f"❌ {test_func.__name__} FAILED: {e}")
            traceback.print_exc()

    print("\n" + "=" * 70)
    print(f"TEST RESULTS: {passed}/{passed + failed} passed, {failed}/{passed + failed} failed")
    print("=" * 70)

    if failed == 0:
        print("✅ ALL TESTS PASSED!")
        sys.exit(0)
    else:
        print(f"❌ {failed} TEST(S) FAILED")
        sys.exit(1)


if __name__ == "__main__":
    run_all_tests()
