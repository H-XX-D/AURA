"""
Comprehensive test suite for compression_engine.py module.

Tests cover:
1. CompressionEngine initialization with SQL cache
2. Binary Semantic compression/decompression
3. AuraLite compression/decompression
4. BRIO compression/decompression (TCP and full)
5. Pattern Semantic (AI) compression/decompression
6. Uncompressed format with UTF-8 and surrogate handling
7. Compression method detection
8. Template usage extraction
9. Round-trip testing (compress → decompress → verify)
10. Error handling and edge cases
"""

import os
import sys
import tempfile
import struct
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aura_compression.compression_engine import CompressionEngine
from aura_compression.enums import CompressionMethod
from aura_compression.templates import TemplateLibrary, TemplateMatch


def test_engine_initialization():
    """Test CompressionEngine initialization with SQL cache."""
    print("\n=== Test 1: Engine Initialization ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_dir = os.path.join(tmpdir, ".aura_cache")
        template_lib = TemplateLibrary()
        
        # Initialize with SQL cache enabled
        engine = CompressionEngine(
            template_library=template_lib,
            cache_dir=cache_dir,
            enable_sql_cache=True,
        )
        
        assert engine.template_library is template_lib
        assert engine.cache_dir == cache_dir
        assert engine.enable_sql_cache is True
        assert engine._aura_encoder is not None
        assert engine._aura_decoder is not None
        assert engine._tcp_brio_encoder is not None
        assert engine._tcp_brio_decoder is not None
        assert engine._auralite_encoder is not None
        assert engine._auralite_decoder is not None
        assert engine._pattern_semantic_compressor is not None
        
        print(f"✅ Engine initialized successfully")
        print(f"   - Cache dir: {cache_dir}")
        print(f"   - SQL cache enabled: {engine.enable_sql_cache}")
        print(f"   - TCP BRIO threshold: {engine.tcp_brio_threshold} bytes")


def test_binary_semantic_compression():
    """Test Binary Semantic compression and decompression."""
    print("\n=== Test 2: Binary Semantic Compression ===")
    
    template_lib = TemplateLibrary()
    engine = CompressionEngine(template_library=template_lib, enable_sql_cache=False)
    
    # Add a template
    template_id = 100
    pattern = "Hello, {0}!"
    template_lib.add(template_id, pattern)
    
    # Create template match
    text = "Hello, World!"
    slots = ["World"]
    template_match = TemplateMatch(
        template_id=template_id,
        slots=slots,
    )
    
    # Compress
    compressed, metadata = engine.compress_binary_semantic(text, template_match)
    
    assert isinstance(compressed, bytes)
    assert len(compressed) > 0
    assert compressed[0] == CompressionMethod.BINARY_SEMANTIC.value
    assert metadata['method'] == 'binary_semantic'
    assert metadata['template_id'] == template_id
    assert metadata['slot_count'] == 1
    assert metadata['compressed_size'] < metadata['original_size']
    
    print(f"✅ Compressed: {len(text)} → {len(compressed)} bytes")
    print(f"   - Ratio: {metadata['ratio']:.2f}x")
    print(f"   - Template ID: {metadata['template_id']}")
    
    # Decompress
    decompressed, meta = engine.decompress_binary_semantic(compressed)
    
    assert decompressed == text
    assert meta['method'] == 'binary_semantic'
    assert meta['template_id'] == template_id
    assert meta['slot_count'] == 1
    
    print(f"✅ Decompressed successfully: '{decompressed}'")


def test_auralite_compression():
    """Test AuraLite compression and decompression."""
    print("\n=== Test 3: AuraLite Compression ===")
    
    template_lib = TemplateLibrary()
    engine = CompressionEngine(template_library=template_lib, enable_sql_cache=False)
    
    # Test with various texts
    test_cases = [
        "Hello, World!",
        "Status: OK",
        "Error code 404: Not Found",
        "The quick brown fox jumps over the lazy dog",
    ]
    
    for text in test_cases:
        # Compress
        compressed, metadata = engine.compress_auralite(text)
        
        assert isinstance(compressed, bytes)
        assert len(compressed) > 0
        assert metadata['method'] == 'auralite'
        assert metadata['original_size'] == len(text.encode('utf-8'))
        assert metadata['compressed_size'] == len(compressed)
        
        print(f"✅ Compressed '{text[:30]}...' → {len(compressed)} bytes (ratio: {metadata['ratio']:.2f}x)")
        
        # Decompress
        full_compressed = bytes([CompressionMethod.AURALITE.value]) + compressed
        decompressed, meta = engine.decompress_auralite(full_compressed)
        
        assert decompressed == text
        assert meta['method'] == 'auralite'
        
        print(f"   ✓ Decompressed successfully")


def test_brio_compression():
    """Test BRIO compression (both TCP and full)."""
    print("\n=== Test 4: BRIO Compression ===")
    
    template_lib = TemplateLibrary()
    engine = CompressionEngine(template_library=template_lib, enable_sql_cache=False)
    
    # Test small message (TCP-optimized)
    small_text = "Status: OK"
    compressed_small, meta_small = engine.compress_brio(small_text, use_tcp=True)
    
    assert isinstance(compressed_small, bytes)
    assert len(compressed_small) > 0
    assert meta_small['method'] == 'brio'
    assert meta_small['tcp_optimized'] is True
    
    print(f"✅ TCP BRIO compressed '{small_text}' → {len(compressed_small)} bytes")
    print(f"   - Ratio: {meta_small['ratio']:.2f}x")
    
    # Decompress
    full_small = bytes([CompressionMethod.BRIO.value]) + compressed_small
    decompressed_small, meta_dec_small = engine.decompress_brio(full_small)
    
    assert decompressed_small == small_text
    print(f"   ✓ Decompressed: '{decompressed_small}'")
    
    # Test larger message (full BRIO)
    large_text = "This is a longer message that exceeds the TCP threshold. " * 20
    compressed_large, meta_large = engine.compress_brio(large_text, use_tcp=True)
    
    assert isinstance(compressed_large, bytes)
    assert len(compressed_large) > 0
    assert meta_large['method'] == 'brio'
    
    print(f"✅ Full BRIO compressed {len(large_text)} → {len(compressed_large)} bytes")
    print(f"   - Ratio: {meta_large['ratio']:.2f}x")
    
    # Decompress
    full_large = bytes([CompressionMethod.BRIO.value]) + compressed_large
    decompressed_large, meta_dec_large = engine.decompress_brio(full_large)
    
    assert decompressed_large == large_text
    print(f"   ✓ Decompressed successfully ({len(decompressed_large)} chars)")


def test_pattern_semantic_compression():
    """Test Pattern Semantic (AI) compression."""
    print("\n=== Test 5: Pattern Semantic (AI) Compression ===")
    
    template_lib = TemplateLibrary()
    engine = CompressionEngine(template_library=template_lib, enable_sql_cache=False)
    
    # Test with repetitive text (good for AI pattern detection)
    text = """
    User alice logged in at 10:30
    User bob logged in at 11:00
    User charlie logged in at 11:30
    User diana logged in at 12:00
    Status: OK
    Status: OK
    Status: OK
    Error code 404
    Error code 500
    """
    
    # Compress
    compressed, metadata = engine.compress_pattern_semantic(text)
    
    assert isinstance(compressed, bytes)
    assert len(compressed) > 0
    assert metadata['method'] == 'pattern_semantic'
    assert 'patterns_found' in metadata
    assert 'dictionary_size' in metadata
    
    print(f"✅ Pattern Semantic compressed {metadata['original_size']} → {metadata['compressed_size']} bytes")
    print(f"   - Ratio: {metadata['ratio']:.2f}x")
    print(f"   - Patterns found: {metadata['patterns_found']}")
    print(f"   - Dictionary size: {metadata['dictionary_size']}")
    
    # Decompress
    full_compressed = bytes([CompressionMethod.PATTERN_SEMANTIC.value]) + compressed
    decompressed, meta = engine.decompress_pattern_semantic(full_compressed)
    
    assert decompressed == text
    assert meta['method'] == 'pattern_semantic'
    
    print(f"   ✓ Decompressed successfully ({len(decompressed)} chars)")


def test_uncompressed_format():
    """Test uncompressed format with UTF-8 handling."""
    print("\n=== Test 6: Uncompressed Format ===")
    
    template_lib = TemplateLibrary()
    engine = CompressionEngine(template_library=template_lib, enable_sql_cache=False)
    
    # Test normal UTF-8
    text = "Hello, World! 你好世界 🌍"
    compressed, metadata = engine.compress_uncompressed(text)
    
    assert isinstance(compressed, bytes)
    assert compressed[0] == CompressionMethod.UNCOMPRESSED.value
    assert metadata['method'] == 'uncompressed'
    assert metadata['original_size'] == len(text.encode('utf-8'))
    
    print(f"✅ Uncompressed format: {len(text.encode('utf-8'))} → {len(compressed)} bytes")
    
    # Decompress
    decompressed, meta = engine.decompress_uncompressed(compressed)
    
    assert decompressed == text
    assert meta['method'] == 'uncompressed'
    
    print(f"   ✓ Decompressed: '{decompressed}'")
    
    # Test with surrogate escape handling
    # Create data with invalid UTF-8 bytes
    invalid_bytes = bytes([CompressionMethod.UNCOMPRESSED.value, 0x80, 0x81, 0x82])
    decompressed_surr, meta_surr = engine.decompress_uncompressed(invalid_bytes)
    
    # Should handle gracefully with surrogateescape
    assert isinstance(decompressed_surr, str)
    print(f"   ✓ Surrogate handling works: {len(decompressed_surr)} chars")


def test_compression_method_detection():
    """Test compression method detection from compressed data."""
    print("\n=== Test 7: Compression Method Detection ===")
    
    template_lib = TemplateLibrary()
    engine = CompressionEngine(template_library=template_lib, enable_sql_cache=False)
    
    # Test each compression method
    test_cases = [
        (bytes([CompressionMethod.BINARY_SEMANTIC.value, 0x00, 0x01]), CompressionMethod.BINARY_SEMANTIC),
        (bytes([CompressionMethod.AURALITE.value, 0x00, 0x01]), CompressionMethod.AURALITE),
        (bytes([CompressionMethod.BRIO.value, 0x00, 0x01]), CompressionMethod.BRIO),
        (bytes([CompressionMethod.PATTERN_SEMANTIC.value, 0x00, 0x01]), CompressionMethod.PATTERN_SEMANTIC),
        (bytes([CompressionMethod.UNCOMPRESSED.value, 0x00, 0x01]), CompressionMethod.UNCOMPRESSED),
        (bytes([0x03, 0x00, 0x01]), CompressionMethod.AURALITE),  # Legacy Aura_Lite
    ]
    
    for data, expected_method in test_cases:
        detected = engine.get_compression_method(data)
        assert detected == expected_method
        print(f"✅ Detected {expected_method.name} from byte {data[0]:02x}")
    
    # Test invalid method
    try:
        engine.get_compression_method(bytes([0x99, 0x00, 0x01]))
        assert False, "Should have raised ValueError"
    except ValueError as e:
        print(f"✅ Invalid method raises error: {e}")
    
    # Test empty data
    try:
        engine.get_compression_method(bytes())
        assert False, "Should have raised ValueError"
    except ValueError as e:
        print(f"✅ Empty data raises error: {e}")


def test_round_trip_all_methods():
    """Test round-trip compression/decompression for all methods."""
    print("\n=== Test 8: Round-Trip All Methods ===")
    
    template_lib = TemplateLibrary()
    engine = CompressionEngine(template_library=template_lib, enable_sql_cache=False)
    
    test_text = "The quick brown fox jumps over the lazy dog. 快速的棕色狐狸跳过懒狗。"
    
    # AuraLite
    compressed_al, _ = engine.compress_auralite(test_text)
    full_al = bytes([CompressionMethod.AURALITE.value]) + compressed_al
    decompressed_al, _ = engine.decompress(full_al)
    assert decompressed_al == test_text
    print(f"✅ AuraLite round-trip successful")
    
    # BRIO
    compressed_br, _ = engine.compress_brio(test_text)
    full_br = bytes([CompressionMethod.BRIO.value]) + compressed_br
    decompressed_br, _ = engine.decompress(full_br)
    assert decompressed_br == test_text
    print(f"✅ BRIO round-trip successful")
    
    # Pattern Semantic
    compressed_ps, _ = engine.compress_pattern_semantic(test_text)
    full_ps = bytes([CompressionMethod.PATTERN_SEMANTIC.value]) + compressed_ps
    decompressed_ps, _ = engine.decompress(full_ps)
    assert decompressed_ps == test_text
    print(f"✅ Pattern Semantic round-trip successful")
    
    # Uncompressed
    compressed_uc, _ = engine.compress_uncompressed(test_text)
    decompressed_uc, _ = engine.decompress(compressed_uc)
    assert decompressed_uc == test_text
    print(f"✅ Uncompressed round-trip successful")


def test_template_usage_extraction():
    """Test template usage extraction from BRIO tokens."""
    print("\n=== Test 9: Template Usage Extraction ===")
    
    template_lib = TemplateLibrary()
    
    # Add some templates
    template_lib.add(100, "Hello, {0}!")
    template_lib.add(101, "Status: {0}")
    
    engine = CompressionEngine(template_library=template_lib, enable_sql_cache=False)
    
    # Compress text that might use templates
    text = "Hello, Alice! Hello, Bob! Status: OK"
    compressed, metadata = engine.compress_brio(text)
    
    # Check if template usage is recorded
    if 'template_ids' in metadata:
        print(f"✅ Template usage detected: {metadata['template_ids']}")
        print(f"   - Template details: {metadata['template_usage']}")
    else:
        print(f"✅ No templates used in this compression")
    
    # Decompress and check metadata
    full_compressed = bytes([CompressionMethod.BRIO.value]) + compressed
    decompressed, dec_meta = engine.decompress_brio(full_compressed)
    
    assert decompressed == text
    if 'template_ids' in dec_meta:
        print(f"✅ Template usage preserved in decompression: {dec_meta['template_ids']}")


def test_error_handling():
    """Test error handling for invalid inputs."""
    print("\n=== Test 10: Error Handling ===")
    
    template_lib = TemplateLibrary()
    engine = CompressionEngine(template_library=template_lib, enable_sql_cache=False)
    
    # Test binary semantic with invalid template
    try:
        template_match = TemplateMatch(
            template_id=999999,  # Non-existent
            slots=["test"],
        )
        engine.compress_binary_semantic("test", template_match)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        print(f"✅ Invalid template ID raises error: {e}")
    
    # Test binary semantic with wrong slot count
    template_id = 100
    template_lib.add(template_id, "Hello, {0}!")
    try:
        template_match = TemplateMatch(
            template_id=template_id,
            slots=["a", "b"],  # Wrong count - expects 1, got 2
        )
        engine.compress_binary_semantic("Hello, a!", template_match)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        print(f"✅ Wrong slot count raises error: {e}")
    
    # Test binary semantic with mismatched reconstruction
    try:
        template_match = TemplateMatch(
            template_id=template_id,
            slots=["World"],
        )
        engine.compress_binary_semantic("Different text", template_match)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        print(f"✅ Mismatched reconstruction raises error: {e}")
    
    # Test decompression with truncated data
    try:
        engine.decompress_binary_semantic(bytes([CompressionMethod.BINARY_SEMANTIC.value]))
        assert False, "Should have raised ValueError"
    except ValueError as e:
        print(f"✅ Truncated data raises error: {e}")
    
    # Test decompression with empty data
    try:
        engine.decompress_auralite(bytes())
        assert False, "Should have raised ValueError"
    except ValueError as e:
        print(f"✅ Empty data raises error: {e}")


def test_sql_cache_integration():
    """Test SQL cache integration."""
    print("\n=== Test 11: SQL Cache Integration ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_dir = os.path.join(tmpdir, ".aura_cache")
        template_lib = TemplateLibrary()
        
        # Initialize with SQL cache
        engine = CompressionEngine(
            template_library=template_lib,
            cache_dir=cache_dir,
            enable_sql_cache=True,
        )
        
        # Verify cache is initialized
        assert engine._persistent_cache is not None
        print(f"✅ SQL cache initialized")
        
        # Check cache directory exists
        cache_path = Path(cache_dir)
        assert cache_path.exists()
        print(f"✅ Cache directory created: {cache_dir}")
        
        # Test with cache disabled
        engine2 = CompressionEngine(
            template_library=template_lib,
            enable_sql_cache=False,
        )
        
        assert engine2._persistent_cache is None
        print(f"✅ Cache disabled works correctly")


def test_metadata_completeness():
    """Test that all compression methods return complete metadata."""
    print("\n=== Test 12: Metadata Completeness ===")
    
    template_lib = TemplateLibrary()
    template_lib.add(100, "Test {0}")
    engine = CompressionEngine(template_library=template_lib, enable_sql_cache=False)
    
    test_text = "Hello, World!"
    
    # Check AuraLite metadata
    _, meta_al = engine.compress_auralite(test_text)
    assert 'method' in meta_al
    assert 'original_size' in meta_al
    assert 'compressed_size' in meta_al
    assert 'ratio' in meta_al
    print(f"✅ AuraLite metadata complete: {list(meta_al.keys())}")
    
    # Check BRIO metadata
    _, meta_br = engine.compress_brio(test_text)
    assert 'method' in meta_br
    assert 'original_size' in meta_br
    assert 'compressed_size' in meta_br
    assert 'ratio' in meta_br
    assert 'tcp_optimized' in meta_br
    print(f"✅ BRIO metadata complete: {list(meta_br.keys())}")
    
    # Check Uncompressed metadata
    _, meta_uc = engine.compress_uncompressed(test_text)
    assert 'method' in meta_uc
    assert 'original_size' in meta_uc
    assert 'compressed_size' in meta_uc
    assert 'ratio' in meta_uc
    print(f"✅ Uncompressed metadata complete: {list(meta_uc.keys())}")


def run_all_tests():
    """Run all test functions."""
    print("=" * 70)
    print("COMPRESSION ENGINE COMPREHENSIVE TEST SUITE")
    print("=" * 70)
    
    tests = [
        test_engine_initialization,
        test_binary_semantic_compression,
        test_auralite_compression,
        test_brio_compression,
        test_pattern_semantic_compression,
        test_uncompressed_format,
        test_compression_method_detection,
        test_round_trip_all_methods,
        test_template_usage_extraction,
        test_error_handling,
        test_sql_cache_integration,
        test_metadata_completeness,
    ]
    
    passed = 0
    failed = 0
    
    for test_func in tests:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"❌ {test_func.__name__} FAILED: {e}")
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
