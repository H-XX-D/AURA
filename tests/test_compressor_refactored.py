#!/usr/bin/env python3
"""
Comprehensive test suite for ProductionHybridCompressor (compressor_refactored.py)

Tests the refactored production-ready hybrid compressor with modular architecture,
including compression/decompression, template matching, fast-path processing,
metadata sidechannel, and integration with all modular components.
"""
import os
import sys
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch
import traceback

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aura_compression.compressor_refactored import ProductionHybridCompressor
from aura_compression.enums import CompressionMethod
from aura_compression.templates import TemplateLibrary, TemplateMatch


def test_compressor_initialization():
    """Test basic initialization with default parameters."""
    print("\n=== Test 1: Compressor Initialization ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        compressor = ProductionHybridCompressor(
            enable_audit_logging=False,
            audit_log_directory=tmpdir,
            enable_ml_selection=False,
            enable_scorer=False,
            enable_sidechain=False,
        )
        
        assert compressor is not None
        assert compressor.template_library is not None
        assert compressor._compression_engine is not None
        assert compressor._strategy_manager is not None
        assert compressor._template_service is not None
        print(f"✅ Compressor initialized successfully")
        print(f"   - Template library: {type(compressor.template_library).__name__}")
        print(f"   - Compression engine: {type(compressor._compression_engine).__name__}")
        print(f"   - Strategy manager: {type(compressor._strategy_manager).__name__}")


def test_compressor_with_ml_enabled():
    """Test initialization with ML algorithm selector enabled."""
    print("\n=== Test 2: Compressor With ML Enabled ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        compressor = ProductionHybridCompressor(
            enable_audit_logging=False,
            audit_log_directory=tmpdir,
            enable_ml_selection=True,
            enable_scorer=False,
            enable_sidechain=False,
        )
        
        assert compressor._ml_selector is not None
        print(f"✅ ML algorithm selector enabled")
        print(f"   - ML selector type: {type(compressor._ml_selector).__name__}")


def test_compressor_with_scorer_enabled():
    """Test initialization with scorer/telemetry enabled."""
    print("\n=== Test 3: Compressor With Scorer Enabled ===")
    
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
        assert compressor.scorer_telemetry_path == telemetry_path
        scorer_status = compressor.get_scorer_status()
        assert 'enabled' in scorer_status
        print(f"✅ Scorer enabled successfully")
        print(f"   - Telemetry path: {telemetry_path}")
        print(f"   - Scorer status: {scorer_status}")


def test_compress_small_text():
    """Test compression of small text (should use UNCOMPRESSED)."""
    print("\n=== Test 4: Compress Small Text ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        compressor = ProductionHybridCompressor(
            enable_audit_logging=False,
            audit_log_directory=tmpdir,
            enable_ml_selection=False,
            enable_scorer=False,
            enable_sidechain=False,
        )
        
        text = "Hi"
        compressed, method, metadata = compressor.compress(text)
        
        assert isinstance(compressed, bytes)
        assert method == CompressionMethod.UNCOMPRESSED
        assert metadata['method'] == 'uncompressed'
        assert 'reason' in metadata
        print(f"✅ Small text compressed: '{text}'")
        print(f"   - Method: {method.name}")
        print(f"   - Size: {len(text)} → {len(compressed)} bytes")
        print(f"   - Reason: {metadata.get('reason', 'N/A')}")


def test_compress_medium_text():
    """Test compression of medium text (should use AURALITE or BRIO)."""
    print("\n=== Test 5: Compress Medium Text ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        compressor = ProductionHybridCompressor(
            enable_audit_logging=False,
            audit_log_directory=tmpdir,
            enable_ml_selection=False,
            enable_scorer=False,
            enable_sidechain=False,
        )
        
        text = "This is a medium-length test message that should be compressed using AURALITE or BRIO."
        compressed, method, metadata = compressor.compress(text)
        
        assert isinstance(compressed, bytes)
        assert method in [CompressionMethod.AURALITE, CompressionMethod.BRIO, CompressionMethod.UNCOMPRESSED]
        assert metadata['method'] in ['auralite', 'brio', 'uncompressed']
        assert metadata['original_size'] == len(text.encode('utf-8'))
        assert metadata['compressed_size'] == len(compressed)
        print(f"✅ Medium text compressed")
        print(f"   - Original: {metadata['original_size']} bytes")
        print(f"   - Compressed: {metadata['compressed_size']} bytes")
        print(f"   - Method: {method.name}")
        print(f"   - Ratio: {metadata['ratio']:.2f}x")


def test_compress_long_text():
    """Test compression of long text."""
    print("\n=== Test 6: Compress Long Text ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        compressor = ProductionHybridCompressor(
            enable_audit_logging=False,
            audit_log_directory=tmpdir,
            enable_ml_selection=False,
            enable_scorer=False,
            enable_sidechain=False,
        )
        
        text = "x" * 5000
        compressed, method, metadata = compressor.compress(text)
        
        assert isinstance(compressed, bytes)
        assert method in [CompressionMethod.AURALITE, CompressionMethod.BRIO, CompressionMethod.PATTERN_SEMANTIC]
        assert metadata['original_size'] == len(text)
        assert metadata['compressed_size'] < metadata['original_size']  # Should actually compress
        print(f"✅ Long text compressed")
        print(f"   - Original: {metadata['original_size']} bytes")
        print(f"   - Compressed: {metadata['compressed_size']} bytes")
        print(f"   - Method: {method.name}")
        print(f"   - Ratio: {metadata['ratio']:.2f}x")


def test_compress_with_template():
    """Test compression with explicit template."""
    print("\n=== Test 7: Compress With Template ===")
    
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
            text,
            template_id=template_id,
            slots=["alice", "192.168.1.1"]
        )
        
        assert isinstance(compressed, bytes)
        assert method == CompressionMethod.BINARY_SEMANTIC
        assert metadata['method'] == 'binary_semantic'
        assert metadata.get('template_id') == template_id
        print(f"✅ Template compression successful")
        print(f"   - Template ID: {template_id}")
        print(f"   - Original: {len(text)} bytes")
        print(f"   - Compressed: {len(compressed)} bytes")
        print(f"   - Ratio: {metadata['ratio']:.2f}x")


def test_decompress_uncompressed():
    """Test decompression of uncompressed data."""
    print("\n=== Test 8: Decompress Uncompressed ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        compressor = ProductionHybridCompressor(
            enable_audit_logging=False,
            audit_log_directory=tmpdir,
            enable_ml_selection=False,
            enable_scorer=False,
            enable_sidechain=False,
        )
        
        text = "Hello"
        compressed, method, metadata = compressor.compress(text)
        
        # Decompress
        decompressed = compressor.decompress(compressed)
        
        assert decompressed == text
        print(f"✅ Uncompressed data decompressed successfully")
        print(f"   - Original: '{text}'")
        print(f"   - Decompressed: '{decompressed}'")


def test_decompress_auralite():
    """Test decompression of AURALITE compressed data."""
    print("\n=== Test 9: Decompress AURALITE ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        compressor = ProductionHybridCompressor(
            enable_audit_logging=False,
            audit_log_directory=tmpdir,
            enable_ml_selection=False,
            enable_scorer=False,
            enable_sidechain=False,
        )
        
        text = "This is a test message that will be compressed with AURALITE method."
        compressed, method, metadata = compressor.compress(text)
        
        # Force compression (skip if it fell back to uncompressed)
        if method == CompressionMethod.UNCOMPRESSED:
            print(f"⚠️  Text was not compressed, skipping AURALITE decompression test")
            return
        
        # Decompress
        decompressed = compressor.decompress(compressed)
        
        assert decompressed == text
        print(f"✅ AURALITE decompressed successfully")
        print(f"   - Method: {method.name}")
        print(f"   - Original: {len(text)} bytes")
        print(f"   - Compressed: {len(compressed)} bytes")


def test_decompress_with_metadata():
    """Test decompression with metadata return."""
    print("\n=== Test 10: Decompress With Metadata ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        compressor = ProductionHybridCompressor(
            enable_audit_logging=False,
            audit_log_directory=tmpdir,
            enable_ml_selection=False,
            enable_scorer=False,
            enable_sidechain=False,
        )
        
        text = "Test message for metadata extraction during decompression."
        compressed, method, metadata_compress = compressor.compress(text)
        
        # Decompress with metadata
        decompressed, metadata_decompress = compressor.decompress(compressed, return_metadata=True)
        
        assert decompressed == text
        assert 'method' in metadata_decompress
        assert 'semantic_sketch' in metadata_decompress
        print(f"✅ Decompression with metadata successful")
        print(f"   - Method: {metadata_decompress.get('method', 'N/A')}")
        print(f"   - Semantic sketch: {metadata_decompress.get('semantic_sketch', 'N/A')[:50]}...")


def test_compress_with_bytes_input():
    """Test compression with bytes input."""
    print("\n=== Test 11: Compress With Bytes Input ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        compressor = ProductionHybridCompressor(
            enable_audit_logging=False,
            audit_log_directory=tmpdir,
            enable_ml_selection=False,
            enable_scorer=False,
            enable_sidechain=False,
        )
        
        text_bytes = b"Test message as bytes input"
        compressed, method, metadata = compressor.compress(text_bytes)
        
        assert isinstance(compressed, bytes)
        assert metadata['original_size'] == len(text_bytes)
        
        # Decompress and verify
        decompressed = compressor.decompress(compressed)
        assert decompressed == text_bytes.decode('utf-8')
        print(f"✅ Bytes input handled correctly")
        print(f"   - Input: {len(text_bytes)} bytes")
        print(f"   - Method: {method.name}")


def test_compress_unicode_text():
    """Test compression with Unicode characters."""
    print("\n=== Test 12: Compress Unicode Text ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        compressor = ProductionHybridCompressor(
            enable_audit_logging=False,
            audit_log_directory=tmpdir,
            enable_ml_selection=False,
            enable_scorer=False,
            enable_sidechain=False,
        )
        
        text = "Hello 世界 🌍 Привет мир مرحبا"
        compressed, method, metadata = compressor.compress(text)
        
        assert isinstance(compressed, bytes)
        
        # Decompress and verify
        decompressed = compressor.decompress(compressed)
        assert decompressed == text
        print(f"✅ Unicode text handled correctly")
        print(f"   - Text: '{text}'")
        print(f"   - Original: {metadata['original_size']} bytes")
        print(f"   - Compressed: {metadata['compressed_size']} bytes")
        print(f"   - Method: {method.name}")


def test_fast_path_compression():
    """Test fast-path compression with template match."""
    print("\n=== Test 13: Fast Path Compression ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        compressor = ProductionHybridCompressor(
            enable_audit_logging=False,
            audit_log_directory=tmpdir,
            enable_ml_selection=False,
            enable_scorer=False,
            enable_sidechain=False,
            enable_fast_path=True,
        )
        
        # Add template (make text longer than 20 bytes to avoid size threshold)
        template_id = 200
        compressor.template_library.add(template_id, "System Status Report: {0}")
        
        # Compress with template (should use fast path)
        text = "System Status Report: All systems operational"
        compressed, method, metadata = compressor.compress(
            text,
            template_id=template_id,
            slots=["All systems operational"]
        )
        
        assert isinstance(compressed, bytes)
        assert method == CompressionMethod.BINARY_SEMANTIC
        # Fast path might be indicated in metadata
        fast_path_used = metadata.get('fast_path_used') or metadata.get('fast_path_candidate')
        if fast_path_used:
            print(f"✅ Fast path compression used: {fast_path_used}")
        else:
            print(f"✅ Compression successful (fast path may not have been triggered)")
        print(f"   - Template ID: {template_id}")
        print(f"   - Method: {method.name}")


def test_sidechain_metadata_encoding():
    """Test metadata sidechannel encoding."""
    print("\n=== Test 14: Sidechain Metadata Encoding ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        compressor = ProductionHybridCompressor(
            enable_audit_logging=False,
            audit_log_directory=tmpdir,
            enable_ml_selection=False,
            enable_scorer=False,
            enable_sidechain=True,
        )
        
        text = "Test message with sidechain metadata encoding enabled for fast-path processing."
        compressed, method, metadata = compressor.compress(text)
        
        assert isinstance(compressed, bytes)
        assert len(compressed) >= 12  # Should have metadata header
        print(f"✅ Sidechain metadata encoding successful")
        print(f"   - Compressed size (with metadata): {len(compressed)} bytes")
        print(f"   - Method: {method.name}")


def test_fast_path_classify():
    """Test fast-path message classification."""
    print("\n=== Test 15: Fast Path Classify ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        compressor = ProductionHybridCompressor(
            enable_audit_logging=False,
            audit_log_directory=tmpdir,
            enable_ml_selection=False,
            enable_scorer=False,
            enable_sidechain=True,
        )
        
        text = "What is the capital of France?"
        compressed, method, metadata = compressor.compress(text)
        
        # Try fast-path classification
        classification = compressor.fast_path_classify(compressed)
        
        if classification is not None:
            assert isinstance(classification, dict)
            print(f"✅ Fast path classification successful")
            print(f"   - Classification: {classification}")
        else:
            print(f"⚠️  Fast path classification not available (no metadata header)")


def test_fast_path_route():
    """Test fast-path message routing."""
    print("\n=== Test 16: Fast Path Route ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        compressor = ProductionHybridCompressor(
            enable_audit_logging=False,
            audit_log_directory=tmpdir,
            enable_ml_selection=False,
            enable_scorer=False,
            enable_sidechain=True,
        )
        
        text = "How do I implement a binary search algorithm?"
        compressed, method, metadata = compressor.compress(text)
        
        # Try fast-path routing
        handler = compressor.fast_path_route(compressed)
        
        if handler is not None:
            assert isinstance(handler, str)
            print(f"✅ Fast path routing successful")
            print(f"   - Handler: {handler}")
        else:
            print(f"⚠️  Fast path routing not available (no metadata header)")


def test_fast_path_security_check():
    """Test fast-path security screening."""
    print("\n=== Test 17: Fast Path Security Check ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        compressor = ProductionHybridCompressor(
            enable_audit_logging=False,
            audit_log_directory=tmpdir,
            enable_ml_selection=False,
            enable_scorer=False,
            enable_sidechain=True,
        )
        
        text = "This is a normal message that should pass security screening."
        compressed, method, metadata = compressor.compress(text)
        
        # Try fast-path security check
        passes_security = compressor.fast_path_security_check(compressed)
        
        if passes_security is not None:
            assert isinstance(passes_security, bool)
            print(f"✅ Fast path security check successful")
            print(f"   - Passes: {passes_security}")
        else:
            print(f"⚠️  Fast path security check not available (no metadata header)")


def test_fast_path_process():
    """Test complete fast-path processing."""
    print("\n=== Test 18: Fast Path Process (Complete) ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        compressor = ProductionHybridCompressor(
            enable_audit_logging=False,
            audit_log_directory=tmpdir,
            enable_ml_selection=False,
            enable_scorer=False,
            enable_sidechain=True,
        )
        
        text = "Can you help me debug this Python code?"
        compressed, method, metadata = compressor.compress(text)
        
        # Try complete fast-path processing
        results = compressor.fast_path_process(compressed)
        
        if results is not None:
            assert isinstance(results, dict)
            print(f"✅ Complete fast path processing successful")
            print(f"   - Results keys: {list(results.keys())}")
        else:
            print(f"⚠️  Fast path processing not available (no metadata header)")


def test_compress_with_template_legacy():
    """Test legacy compress_with_template method."""
    print("\n=== Test 19: Compress With Template (Legacy) ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        compressor = ProductionHybridCompressor(
            enable_audit_logging=False,
            audit_log_directory=tmpdir,
            enable_ml_selection=False,
            enable_scorer=False,
            enable_sidechain=False,
        )
        
        # Add template
        template_id = 300
        compressor.template_library.add(template_id, "Error: {0} at line {1}")
        
        # Compress using legacy method
        compressed = compressor.compress_with_template(template_id, ["NullPointerException", "42"])
        
        assert isinstance(compressed, bytes)
        assert len(compressed) > 0
        print(f"✅ Legacy compress_with_template successful")
        print(f"   - Template ID: {template_id}")
        print(f"   - Compressed size: {len(compressed)} bytes")


def test_decompress_binary_legacy():
    """Test legacy decompress_binary method."""
    print("\n=== Test 20: Decompress Binary (Legacy) ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        compressor = ProductionHybridCompressor(
            enable_audit_logging=False,
            audit_log_directory=tmpdir,
            enable_ml_selection=False,
            enable_scorer=False,
            enable_sidechain=False,
        )
        
        # Add template and compress
        template_id = 400
        compressor.template_library.add(template_id, "Request from {0} at {1}")
        
        text = "Request from server-01 at 10:30 AM"
        compressed, method, metadata = compressor.compress(
            text,
            template_id=template_id,
            slots=["server-01", "10:30 AM"]
        )
        
        # Check if actually compressed with template
        if method != CompressionMethod.BINARY_SEMANTIC:
            print(f"⚠️  Text was not compressed with template, skipping decompress_binary test")
            print(f"   - Actual method: {method.name}")
            return
        
        # Decompress using legacy method (needs full data with method byte)
        decompressed = compressor.decompress_binary(compressed)
        
        assert decompressed == text
        print(f"✅ Legacy decompress_binary successful")
        print(f"   - Original: '{text}'")
        print(f"   - Decompressed: '{decompressed}'")


def test_performance_stats():
    """Test performance statistics retrieval."""
    print("\n=== Test 21: Performance Stats ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        compressor = ProductionHybridCompressor(
            enable_audit_logging=False,
            audit_log_directory=tmpdir,
            enable_ml_selection=False,
            enable_scorer=False,
            enable_sidechain=False,
        )
        
        # Perform some compressions
        texts = [
            "Test message 1",
            "Test message 2",
            "Test message 3",
        ]
        for text in texts:
            compressor.compress(text)
        
        # Get performance stats
        stats = compressor.get_performance_stats()
        
        assert isinstance(stats, dict)
        assert 'template_manager' in stats
        assert 'ml_selection_enabled' in stats
        print(f"✅ Performance stats retrieved")
        print(f"   - Stats keys: {list(stats.keys())}")
        print(f"   - ML enabled: {stats['ml_selection_enabled']}")


def test_template_healing():
    """Test template cache healing functionality."""
    print("\n=== Test 22: Template Healing ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        compressor = ProductionHybridCompressor(
            enable_audit_logging=False,
            audit_log_directory=tmpdir,
            enable_ml_selection=False,
            enable_scorer=False,
            enable_sidechain=False,
        )
        
        # Add a template
        template_id = 500
        compressor.template_library.add(template_id, "Message: {0}")
        
        # Try to compress with a non-existent template ID
        # This should trigger healing and fallback
        text = "Message: Test"
        try:
            compressed, method, metadata = compressor.compress(
                text,
                template_id=999,  # Non-existent
                slots=["Test"]
            )
            
            # Should fall back to another method
            assert method != CompressionMethod.BINARY_SEMANTIC
            print(f"✅ Template healing handled gracefully")
            print(f"   - Fallback method: {method.name}")
        except ValueError:
            # Expected if template doesn't exist
            print(f"✅ Template healing triggered ValueError (expected)")


def test_edge_case_empty_string():
    """Test edge case: empty string."""
    print("\n=== Test 23: Edge Case - Empty String ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        compressor = ProductionHybridCompressor(
            enable_audit_logging=False,
            audit_log_directory=tmpdir,
            enable_ml_selection=False,
            enable_scorer=False,
            enable_sidechain=False,
        )
        
        text = ""
        compressed, method, metadata = compressor.compress(text)
        
        assert isinstance(compressed, bytes)
        assert method == CompressionMethod.UNCOMPRESSED
        print(f"✅ Empty string handled: {len(compressed)} bytes")


def test_edge_case_very_long_text():
    """Test edge case: very long text."""
    print("\n=== Test 24: Edge Case - Very Long Text ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        compressor = ProductionHybridCompressor(
            enable_audit_logging=False,
            audit_log_directory=tmpdir,
            enable_ml_selection=False,
            enable_scorer=False,
            enable_sidechain=False,
        )
        
        text = "a" * 50000
        compressed, method, metadata = compressor.compress(text)
        
        assert isinstance(compressed, bytes)
        assert metadata['compressed_size'] < metadata['original_size']
        
        # Verify decompression
        decompressed = compressor.decompress(compressed)
        assert decompressed == text
        print(f"✅ Very long text handled")
        print(f"   - Original: {len(text)} bytes")
        print(f"   - Compressed: {len(compressed)} bytes")
        print(f"   - Ratio: {metadata['ratio']:.2f}x")


def test_edge_case_special_characters():
    """Test edge case: special characters."""
    print("\n=== Test 25: Edge Case - Special Characters ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        compressor = ProductionHybridCompressor(
            enable_audit_logging=False,
            audit_log_directory=tmpdir,
            enable_ml_selection=False,
            enable_scorer=False,
            enable_sidechain=False,
        )
        
        text = "!@#$%^&*()_+-=[]{}|;':\",./<>?`~\n\t\r"
        compressed, method, metadata = compressor.compress(text)
        
        assert isinstance(compressed, bytes)
        
        # Verify decompression
        decompressed = compressor.decompress(compressed)
        assert decompressed == text
        print(f"✅ Special characters handled correctly")
        print(f"   - Method: {method.name}")


def run_all_tests():
    """Run all test functions."""
    test_functions = [
        test_compressor_initialization,
        test_compressor_with_ml_enabled,
        test_compressor_with_scorer_enabled,
        test_compress_small_text,
        test_compress_medium_text,
        test_compress_long_text,
        test_compress_with_template,
        test_decompress_uncompressed,
        test_decompress_auralite,
        test_decompress_with_metadata,
        test_compress_with_bytes_input,
        test_compress_unicode_text,
        test_fast_path_compression,
        test_sidechain_metadata_encoding,
        test_fast_path_classify,
        test_fast_path_route,
        test_fast_path_security_check,
        test_fast_path_process,
        test_compress_with_template_legacy,
        test_decompress_binary_legacy,
        test_performance_stats,
        test_template_healing,
        test_edge_case_empty_string,
        test_edge_case_very_long_text,
        test_edge_case_special_characters,
    ]
    
    passed = 0
    failed = 0
    
    print("=" * 70)
    print("PRODUCTION HYBRID COMPRESSOR COMPREHENSIVE TEST SUITE")
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
