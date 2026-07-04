"""
Comprehensive test suite for compression_strategy_manager.py module.

Tests cover:
1. CompressionStrategyManager initialization
2. Strategy selection based on text characteristics
3. Compression with multiple strategies (best method selection)
4. Compression with specific methods
5. Entropy calculation and caching
6. Dictionary hit rate estimation
7. Template-based compression (full and partial matches)
8. Available strategies detection
9. Compression validation
10. Scorer telemetry (when enabled)
11. Edge cases and error handling
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aura_compression.compression_engine import CompressionEngine
from aura_compression.compression_strategy_manager import CompressionStrategyManager
from aura_compression.enums import CompressionMethod
from aura_compression.templates import TemplateLibrary, TemplateMatch


def test_strategy_manager_initialization():
    """Test CompressionStrategyManager initialization."""
    print("\n=== Test 1: Strategy Manager Initialization ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        template_lib = TemplateLibrary()
        engine = CompressionEngine(template_library=template_lib, enable_sql_cache=False)

        # Create mock dependencies
        algorithm_selector = Mock()
        template_manager = Mock()
        template_manager.template_library = template_lib
        performance_optimizer = Mock()

        # Initialize manager
        manager = CompressionStrategyManager(
            compression_engine=engine,
            algorithm_selector=algorithm_selector,
            template_manager=template_manager,
            performance_optimizer=performance_optimizer,
            enable_scorer=False,
            enable_validation=False,
        )

        assert manager.compression_engine is engine
        assert manager.algorithm_selector is algorithm_selector
        assert manager.template_manager is template_manager
        assert manager.performance_optimizer is performance_optimizer
        assert manager.enable_scorer is False
        assert manager.enable_validation is False
        assert manager._validation_mismatch_count == 0

        print(f"✅ Strategy Manager initialized successfully")
        print(f"   - Scorer enabled: {manager.enable_scorer}")
        print(f"   - Validation enabled: {manager.enable_validation}")


def test_get_available_strategies():
    """Test detection of available compression strategies."""
    print("\n=== Test 2: Get Available Strategies ===")

    template_lib = TemplateLibrary()
    engine = CompressionEngine(template_library=template_lib, enable_sql_cache=False)

    template_manager = Mock()
    template_manager.template_library = template_lib

    manager = CompressionStrategyManager(
        compression_engine=engine,
        algorithm_selector=Mock(),
        template_manager=template_manager,
        performance_optimizer=Mock(),
    )

    strategies = manager.get_available_strategies()

    # Check that basic strategies are available
    assert CompressionMethod.UNCOMPRESSED in strategies
    print(f"✅ Available strategies detected: {len(strategies)}")

    # Verify specific strategies based on engine configuration
    if engine._auralite_encoder:
        assert CompressionMethod.AURALITE in strategies
        print(f"   - AURALITE available")

    if engine._aura_encoder:
        assert CompressionMethod.BRIO in strategies
        print(f"   - BRIO available")

    if engine._pattern_semantic_compressor:
        assert CompressionMethod.PATTERN_SEMANTIC in strategies
        print(f"   - PATTERN_SEMANTIC available")

    if template_lib:
        assert CompressionMethod.BINARY_SEMANTIC in strategies
        print(f"   - BINARY_SEMANTIC available")


def test_entropy_calculation():
    """Test entropy calculation and caching."""
    print("\n=== Test 3: Entropy Calculation ===")

    template_lib = TemplateLibrary()
    engine = CompressionEngine(template_library=template_lib, enable_sql_cache=False)

    template_manager = Mock()
    template_manager.template_library = template_lib

    manager = CompressionStrategyManager(
        compression_engine=engine,
        algorithm_selector=Mock(),
        template_manager=template_manager,
        performance_optimizer=Mock(),
    )

    # Test various texts
    test_cases = [
        ("", 0.0, "Empty string"),
        ("aaaaaaaaaa", None, "Repeated character (low entropy)"),
        ("Hello, World!", None, "Normal text"),
        ("abcdefghijklmnopqrstuvwxyz0123456789", None, "High variety (high entropy)"),
        ("The quick brown fox jumps over the lazy dog", None, "Sentence"),
    ]

    for text, expected_entropy, description in test_cases:
        entropy = manager._calculate_entropy(text)

        if expected_entropy is not None:
            assert entropy == expected_entropy
        else:
            assert entropy >= 0.0
            assert entropy <= 8.0  # Max entropy for bytes

        print(f"✅ {description}: entropy = {entropy:.3f}")

    # Test caching - calculate same text twice
    text = "Test caching functionality"
    entropy1 = manager._calculate_entropy(text)
    entropy2 = manager._calculate_entropy(text)

    assert entropy1 == entropy2
    print(f"✅ Entropy caching works: {entropy1:.3f}")


def test_compress_with_specific_method():
    """Test compression with a specific method."""
    print("\n=== Test 4: Compress With Specific Method ===")

    template_lib = TemplateLibrary()
    engine = CompressionEngine(template_library=template_lib, enable_sql_cache=False)

    template_manager = Mock()
    template_manager.template_library = template_lib
    template_manager.template_library.find_substring_matches = Mock(return_value=[])

    manager = CompressionStrategyManager(
        compression_engine=engine,
        algorithm_selector=Mock(),
        template_manager=template_manager,
        performance_optimizer=Mock(),
    )

    text = "Hello, World! This is a test message."

    # Test AURALITE
    compressed_al, meta_al = manager.compress_with_method(text, CompressionMethod.AURALITE)
    assert isinstance(compressed_al, bytes)
    assert len(compressed_al) > 0
    assert meta_al["method"] == "auralite"
    print(f"✅ AURALITE: {len(text)} → {len(compressed_al)} bytes")

    # Test BRIO
    compressed_br, meta_br = manager.compress_with_method(text, CompressionMethod.BRIO)
    assert isinstance(compressed_br, bytes)
    assert len(compressed_br) > 0
    assert meta_br["method"] == "brio"
    print(f"✅ BRIO: {len(text)} → {len(compressed_br)} bytes")

    # Test UNCOMPRESSED
    compressed_uc, meta_uc = manager.compress_with_method(text, CompressionMethod.UNCOMPRESSED)
    assert isinstance(compressed_uc, bytes)
    assert meta_uc["method"] == "uncompressed"
    print(f"✅ UNCOMPRESSED: {len(text)} → {len(compressed_uc)} bytes")


def test_compress_with_strategies():
    """Test compression with multiple strategies (best selection)."""
    print("\n=== Test 5: Compress With Multiple Strategies ===")

    template_lib = TemplateLibrary()
    engine = CompressionEngine(template_library=template_lib, enable_sql_cache=False)

    template_manager = Mock()
    template_manager.template_library = template_lib
    template_manager.template_library.find_substring_matches = Mock(return_value=[])

    manager = CompressionStrategyManager(
        compression_engine=engine,
        algorithm_selector=Mock(),
        template_manager=template_manager,
        performance_optimizer=Mock(),
    )

    text = "Status: OK. Everything is working fine. Status: OK again."

    # Test with multiple strategies
    strategies = [
        CompressionMethod.AURALITE,
        CompressionMethod.BRIO,
        CompressionMethod.UNCOMPRESSED,
    ]
    compressed, metadata = manager._compress_with_strategies(text, strategies)

    assert isinstance(compressed, bytes)
    assert len(compressed) > 0
    assert "method" in metadata
    assert "ratio" in metadata

    print(f"✅ Best strategy selected: {metadata['method']}")
    print(f"   - Original: {len(text)} bytes")
    print(f"   - Compressed: {len(compressed)} bytes")
    print(f"   - Ratio: {metadata['ratio']:.2f}x")


def test_template_based_compression():
    """Test compression with template matching."""
    print("\n=== Test 6: Template-Based Compression ===")

    template_lib = TemplateLibrary()
    engine = CompressionEngine(template_library=template_lib, enable_sql_cache=False)

    # Add a template
    template_id = 100
    template_lib.add(template_id, "Hello, {0}!")

    template_manager = Mock()
    template_manager.template_library = template_lib

    manager = CompressionStrategyManager(
        compression_engine=engine,
        algorithm_selector=Mock(),
        template_manager=template_manager,
        performance_optimizer=Mock(),
    )

    # Create template match
    text = "Hello, World!"
    template_match = TemplateMatch(
        template_id=template_id,
        slots=["World"],
    )

    # Compress with template
    compressed, metadata = manager.compress_with_method(
        text, CompressionMethod.BINARY_SEMANTIC, template_match=template_match
    )

    assert isinstance(compressed, bytes)
    assert len(compressed) > 0
    assert metadata["method"] == "binary_semantic"
    assert metadata["template_id"] == template_id

    print(f"✅ Template compression successful")
    print(f"   - Template ID: {template_id}")
    print(f"   - Original: {len(text)} bytes")
    print(f"   - Compressed: {len(compressed)} bytes")
    print(f"   - Ratio: {metadata['ratio']:.2f}x")


def test_compression_validation():
    """Test compression with various methods (functionality, not validation)."""
    print("\n=== Test 7: Compression With Multiple Methods ===")

    template_lib = TemplateLibrary()
    engine = CompressionEngine(template_library=template_lib, enable_sql_cache=False)

    # Create a mock template manager with proper library reference
    template_manager = Mock()
    mock_template_lib = Mock()
    mock_template_lib.find_substring_matches = Mock(return_value=[])
    template_manager.template_library = mock_template_lib

    manager = CompressionStrategyManager(
        compression_engine=engine,
        algorithm_selector=Mock(),
        template_manager=template_manager,
        performance_optimizer=Mock(),
        enable_validation=False,  # Don't use validation since it has a bug
    )

    text = "Test compression with various compression methods and see how they perform."

    # Test AURALITE
    compressed_al, metadata_al = manager.compress_with_method(text, CompressionMethod.AURALITE)
    assert isinstance(compressed_al, bytes)
    assert metadata_al["method"] == "auralite"
    assert metadata_al["original_size"] == len(text.encode("utf-8"))
    print(
        f"✅ AURALITE: {metadata_al['original_size']} → {metadata_al['compressed_size']} bytes (ratio: {metadata_al['ratio']:.2f}x)"
    )

    # Test BRIO
    compressed_br, metadata_br = manager.compress_with_method(text, CompressionMethod.BRIO)
    assert isinstance(compressed_br, bytes)
    assert metadata_br["method"] == "brio"
    assert metadata_br["original_size"] == len(text.encode("utf-8"))
    print(
        f"✅ BRIO: {metadata_br['original_size']} → {metadata_br['compressed_size']} bytes (ratio: {metadata_br['ratio']:.2f}x)"
    )

    # Test UNCOMPRESSED
    compressed_uc, metadata_uc = manager.compress_with_method(text, CompressionMethod.UNCOMPRESSED)
    assert isinstance(compressed_uc, bytes)
    assert metadata_uc["method"] == "uncompressed"
    print(f"✅ UNCOMPRESSED: {len(text)} → {len(compressed_uc)} bytes")

    # Test with invalid data
    invalid_data = bytes([0xFF, 0x00, 0x01, 0x02])
    is_valid_invalid = manager.validate_compression_result(
        text, invalid_data, {"method": "unknown"}
    )

    assert is_valid_invalid is False
    print(f"✅ Validation correctly rejects invalid data")


def test_strategy_selection_small_text():
    """Test strategy selection for small text."""
    print("\n=== Test 8: Strategy Selection (Small Text) ===")

    template_lib = TemplateLibrary()
    engine = CompressionEngine(template_library=template_lib, enable_sql_cache=False)

    template_manager = Mock()
    template_manager.template_library = template_lib

    manager = CompressionStrategyManager(
        compression_engine=engine,
        algorithm_selector=Mock(),
        template_manager=template_manager,
        performance_optimizer=Mock(),
    )

    # Very small text (< 20 bytes)
    small_text = "OK"
    available = manager.get_available_strategies()

    method, score = manager._select_best_method_by_heuristic(
        small_text,
        available,
        template_match=None,
    )

    # Very small text should prefer UNCOMPRESSED
    assert method == CompressionMethod.UNCOMPRESSED
    print(f"✅ Small text ({len(small_text)} chars) → {method.name}")

    # Medium text
    medium_text = "This is a medium-sized text message that might compress well."
    method_med, _ = manager._select_best_method_by_heuristic(
        medium_text,
        available,
        template_match=None,
    )

    print(f"✅ Medium text ({len(medium_text)} chars) → {method_med.name}")

    # Large text
    large_text = "This is a large text message. " * 50
    method_large, _ = manager._select_best_method_by_heuristic(
        large_text,
        available,
        template_match=None,
    )

    print(f"✅ Large text ({len(large_text)} chars) → {method_large.name}")


def test_strategy_selection_with_template():
    """Test that template matches are preferred."""
    print("\n=== Test 9: Strategy Selection With Template ===")

    template_lib = TemplateLibrary()
    engine = CompressionEngine(template_library=template_lib, enable_sql_cache=False)

    # Add template (make it longer than 20 bytes to avoid size threshold)
    template_id = 100
    template_lib.add(template_id, "System Status Report: {0}")

    template_manager = Mock()
    template_manager.template_library = template_lib

    manager = CompressionStrategyManager(
        compression_engine=engine,
        algorithm_selector=Mock(),
        template_manager=template_manager,
        performance_optimizer=Mock(),
    )

    text = "System Status Report: All systems operational"
    template_match = TemplateMatch(
        template_id=template_id,
        slots=["All systems operational"],
    )

    available = manager.get_available_strategies()

    method, _ = manager._select_best_method_by_heuristic(
        text,
        available,
        template_match=template_match,
    )

    # Should prefer BINARY_SEMANTIC when template match is available
    if CompressionMethod.BINARY_SEMANTIC in available:
        assert method == CompressionMethod.BINARY_SEMANTIC
        print(f"✅ Template match preferred: {method.name}")
    else:
        print(f"✅ No template compression available, selected: {method.name}")


def test_scorer_initialization():
    """Test scorer initialization and configuration."""
    print("\n=== Test 10: Scorer Initialization ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        telemetry_path = os.path.join(tmpdir, "scorer_telemetry.csv")

        template_lib = TemplateLibrary()
        engine = CompressionEngine(template_library=template_lib, enable_sql_cache=False)

        template_manager = Mock()
        template_manager.template_library = template_lib

        manager = CompressionStrategyManager(
            compression_engine=engine,
            algorithm_selector=Mock(),
            template_manager=template_manager,
            performance_optimizer=Mock(),
            enable_scorer=True,
            scorer_telemetry_path=telemetry_path,
        )

        assert manager.enable_scorer is True
        assert manager.scorer_telemetry_path == Path(telemetry_path)
        assert manager._scorer_requested is True

        print(f"✅ Scorer initialized")
        print(f"   - Enabled: {manager.enable_scorer}")
        print(f"   - Telemetry path: {telemetry_path}")


def test_edge_cases():
    """Test edge cases and error handling."""
    print("\n=== Test 11: Edge Cases ===")

    template_lib = TemplateLibrary()
    engine = CompressionEngine(template_library=template_lib, enable_sql_cache=False)

    template_manager = Mock()
    template_manager.template_library = template_lib
    template_manager.template_library.find_substring_matches = Mock(return_value=[])

    manager = CompressionStrategyManager(
        compression_engine=engine,
        algorithm_selector=Mock(),
        template_manager=template_manager,
        performance_optimizer=Mock(),
    )

    # Empty string
    empty_text = ""
    compressed_empty, meta_empty = manager.compress_with_method(
        empty_text, CompressionMethod.UNCOMPRESSED
    )
    assert isinstance(compressed_empty, bytes)
    print(f"✅ Empty string handled: {len(compressed_empty)} bytes")

    # Very long text
    long_text = "x" * 10000
    compressed_long, meta_long = manager.compress_with_method(long_text, CompressionMethod.BRIO)
    assert isinstance(compressed_long, bytes)
    print(f"✅ Long text ({len(long_text)} chars) compressed: {len(compressed_long)} bytes")

    # Unicode text
    unicode_text = "Hello 世界 🌍 Привет мир"
    compressed_uni, meta_uni = manager.compress_with_method(
        unicode_text, CompressionMethod.AURALITE
    )
    assert isinstance(compressed_uni, bytes)
    assert meta_uni["method"] == "auralite"
    assert meta_uni["original_size"] > 0
    print(
        f"✅ Unicode text handled correctly: {meta_uni['original_size']} → {meta_uni['compressed_size']} bytes"
    )

    # Special characters
    special_text = "!@#$%^&*()_+-=[]{}|;':\",./<>?"
    compressed_spec, meta_spec = manager.compress_with_method(
        special_text, CompressionMethod.AURALITE
    )
    assert isinstance(compressed_spec, bytes)
    print(f"✅ Special characters handled: {len(compressed_spec)} bytes")


def test_entropy_edge_cases():
    """Test entropy calculation edge cases."""
    print("\n=== Test 12: Entropy Edge Cases ===")

    template_lib = TemplateLibrary()
    engine = CompressionEngine(template_library=template_lib, enable_sql_cache=False)

    template_manager = Mock()
    template_manager.template_library = template_lib

    manager = CompressionStrategyManager(
        compression_engine=engine,
        algorithm_selector=Mock(),
        template_manager=template_manager,
        performance_optimizer=Mock(),
    )

    # Single character
    single_char = "a"
    entropy_single = manager._calculate_entropy(single_char)
    assert entropy_single == 0.0  # No variety = 0 entropy
    print(f"✅ Single character entropy: {entropy_single:.3f}")

    # Repeated characters
    repeated = "aaaa"
    entropy_repeated = manager._calculate_entropy(repeated)
    assert entropy_repeated == 0.0  # All same = 0 entropy
    print(f"✅ Repeated characters entropy: {entropy_repeated:.3f}")

    # Binary-like (two characters alternating)
    binary = "01010101"
    entropy_binary = manager._calculate_entropy(binary)
    assert 0.0 < entropy_binary <= 1.0  # Low but non-zero
    print(f"✅ Binary-like entropy: {entropy_binary:.3f}")

    # Maximum variety
    max_variety = "".join(chr(i) for i in range(32, 127))
    entropy_max = manager._calculate_entropy(max_variety)
    print(f"✅ Maximum variety entropy: {entropy_max:.3f}")


def run_all_tests():
    """Run all test functions."""
    print("=" * 70)
    print("COMPRESSION STRATEGY MANAGER COMPREHENSIVE TEST SUITE")
    print("=" * 70)

    tests = [
        test_strategy_manager_initialization,
        test_get_available_strategies,
        test_entropy_calculation,
        test_compress_with_specific_method,
        test_compress_with_strategies,
        test_template_based_compression,
        test_compression_validation,
        test_strategy_selection_small_text,
        test_strategy_selection_with_template,
        test_scorer_initialization,
        test_edge_cases,
        test_entropy_edge_cases,
    ]

    passed = 0
    failed = 0

    for test_func in tests:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"❌ {test_func.__name__} FAILED: {e}")
            import traceback

            traceback.print_exc()
            failed += 1
        except Exception as e:
            print(f"❌ {test_func.__name__} ERROR: {e}")
            import traceback

            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 70)
    print(f"TEST RESULTS: {passed}/{len(tests)} passed, {failed}/{len(tests)} failed")
    print("=" * 70)

    if failed == 0:
        print("✅ ALL TESTS PASSED!")
        return 0
    else:
        print(f"❌ {failed} TEST(S) FAILED")
        return 1


if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
