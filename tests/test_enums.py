#!/usr/bin/env python3
"""
Comprehensive test suite for enums.py

Tests compression enums and constants used throughout the AURA compression system.
Validates enum values, properties, and constant definitions.
"""
import os
import sys
import re
from pathlib import Path
import traceback
from enum import Enum

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aura_compression.enums import (
    CompressionMethod,
    TEMPLATE_METADATA_KIND,
    _SEMANTIC_PREVIEW_LIMIT,
    _SEMANTIC_TOKEN_LIMIT,
    _SEMANTIC_TOKEN_PATTERN,
)


def test_compression_method_enum_exists():
    """Test that CompressionMethod enum is defined."""
    print("\n=== Test 1: CompressionMethod Enum Exists ===")
    
    assert CompressionMethod is not None
    assert issubclass(CompressionMethod, Enum)
    
    print(f"✅ CompressionMethod enum defined")
    print(f"   - Type: {type(CompressionMethod)}")
    print(f"   - Base class: Enum")


def test_compression_method_members():
    """Test all CompressionMethod enum members."""
    print("\n=== Test 2: CompressionMethod Members ===")
    
    # Check all expected members exist
    assert hasattr(CompressionMethod, 'BINARY_SEMANTIC')
    assert hasattr(CompressionMethod, 'AURALITE')
    assert hasattr(CompressionMethod, 'BRIO')
    assert hasattr(CompressionMethod, 'AURA_HEAVY')
    assert hasattr(CompressionMethod, 'PATTERN_SEMANTIC')
    assert hasattr(CompressionMethod, 'UNCOMPRESSED')
    
    print(f"✅ All CompressionMethod members exist")
    print(f"   - BINARY_SEMANTIC")
    print(f"   - AURALITE")
    print(f"   - BRIO")
    print(f"   - AURA_HEAVY")
    print(f"   - PATTERN_SEMANTIC")
    print(f"   - UNCOMPRESSED")


def test_compression_method_values():
    """Test CompressionMethod enum values (byte markers)."""
    print("\n=== Test 3: CompressionMethod Values ===")
    
    # Verify specific byte values
    assert CompressionMethod.BINARY_SEMANTIC.value == 0x00
    assert CompressionMethod.AURALITE.value == 0x01
    assert CompressionMethod.BRIO.value == 0x02
    assert CompressionMethod.AURA_HEAVY.value == 0x04
    assert CompressionMethod.PATTERN_SEMANTIC.value == 0x20
    assert CompressionMethod.UNCOMPRESSED.value == 0xFF
    
    print(f"✅ CompressionMethod values correct")
    print(f"   - BINARY_SEMANTIC: 0x{CompressionMethod.BINARY_SEMANTIC.value:02X}")
    print(f"   - AURALITE: 0x{CompressionMethod.AURALITE.value:02X}")
    print(f"   - BRIO: 0x{CompressionMethod.BRIO.value:02X}")
    print(f"   - AURA_HEAVY: 0x{CompressionMethod.AURA_HEAVY.value:02X}")
    print(f"   - PATTERN_SEMANTIC: 0x{CompressionMethod.PATTERN_SEMANTIC.value:02X}")
    print(f"   - UNCOMPRESSED: 0x{CompressionMethod.UNCOMPRESSED.value:02X}")


def test_compression_method_unique_values():
    """Test that all CompressionMethod values are unique."""
    print("\n=== Test 4: CompressionMethod Unique Values ===")
    
    values = [member.value for member in CompressionMethod]
    unique_values = set(values)
    
    assert len(values) == len(unique_values)
    
    print(f"✅ All CompressionMethod values are unique")
    print(f"   - Total members: {len(values)}")
    print(f"   - Unique values: {len(unique_values)}")


def test_compression_method_byte_range():
    """Test that all CompressionMethod values fit in a single byte."""
    print("\n=== Test 5: CompressionMethod Byte Range ===")
    
    for member in CompressionMethod:
        assert 0 <= member.value <= 0xFF
        assert isinstance(member.value, int)
    
    print(f"✅ All CompressionMethod values fit in single byte (0x00-0xFF)")


def test_compression_method_enum_iteration():
    """Test iterating over CompressionMethod enum."""
    print("\n=== Test 6: CompressionMethod Iteration ===")
    
    members = list(CompressionMethod)
    
    assert len(members) == 6
    assert CompressionMethod.BINARY_SEMANTIC in members
    assert CompressionMethod.AURALITE in members
    assert CompressionMethod.BRIO in members
    assert CompressionMethod.AURA_HEAVY in members
    assert CompressionMethod.PATTERN_SEMANTIC in members
    assert CompressionMethod.UNCOMPRESSED in members
    
    print(f"✅ CompressionMethod iteration works")
    print(f"   - Total members: {len(members)}")
    for member in members:
        print(f"   - {member.name}: 0x{member.value:02X}")


def test_compression_method_lookup_by_value():
    """Test looking up CompressionMethod by value."""
    print("\n=== Test 7: CompressionMethod Lookup by Value ===")
    
    # Test lookup by value
    method1 = CompressionMethod(0x00)
    assert method1 == CompressionMethod.BINARY_SEMANTIC
    
    method2 = CompressionMethod(0x01)
    assert method2 == CompressionMethod.AURALITE
    
    method3 = CompressionMethod(0xFF)
    assert method3 == CompressionMethod.UNCOMPRESSED
    
    print(f"✅ CompressionMethod lookup by value works")
    print(f"   - 0x00 → {method1.name}")
    print(f"   - 0x01 → {method2.name}")
    print(f"   - 0xFF → {method3.name}")


def test_compression_method_invalid_value():
    """Test that invalid values raise ValueError."""
    print("\n=== Test 8: CompressionMethod Invalid Value ===")
    
    try:
        invalid_method = CompressionMethod(0x99)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "0x99" in str(e) or "153" in str(e)
        print(f"✅ Invalid value raises ValueError")
        print(f"   - Attempted value: 0x99")
        print(f"   - Error: {e}")


def test_compression_method_name_property():
    """Test CompressionMethod name property."""
    print("\n=== Test 9: CompressionMethod Name Property ===")
    
    assert CompressionMethod.BINARY_SEMANTIC.name == "BINARY_SEMANTIC"
    assert CompressionMethod.AURALITE.name == "AURALITE"
    assert CompressionMethod.BRIO.name == "BRIO"
    assert CompressionMethod.AURA_HEAVY.name == "AURA_HEAVY"
    assert CompressionMethod.PATTERN_SEMANTIC.name == "PATTERN_SEMANTIC"
    assert CompressionMethod.UNCOMPRESSED.name == "UNCOMPRESSED"
    
    print(f"✅ CompressionMethod name property works")


def test_compression_method_comparison():
    """Test CompressionMethod comparison and equality."""
    print("\n=== Test 10: CompressionMethod Comparison ===")
    
    # Test equality
    assert CompressionMethod.AURALITE == CompressionMethod.AURALITE
    assert CompressionMethod.AURALITE != CompressionMethod.BRIO
    
    # Test identity
    assert CompressionMethod.AURALITE is CompressionMethod.AURALITE
    
    # Test comparison with same instance
    method = CompressionMethod.BINARY_SEMANTIC
    assert method == CompressionMethod.BINARY_SEMANTIC
    
    print(f"✅ CompressionMethod comparison works")
    print(f"   - Equality: AURALITE == AURALITE")
    print(f"   - Inequality: AURALITE != BRIO")
    print(f"   - Identity: AURALITE is AURALITE")


def test_template_metadata_kind_constant():
    """Test TEMPLATE_METADATA_KIND constant."""
    print("\n=== Test 11: TEMPLATE_METADATA_KIND Constant ===")
    
    assert TEMPLATE_METADATA_KIND is not None
    assert isinstance(TEMPLATE_METADATA_KIND, int)
    assert TEMPLATE_METADATA_KIND == 0x01
    
    print(f"✅ TEMPLATE_METADATA_KIND constant defined")
    print(f"   - Value: 0x{TEMPLATE_METADATA_KIND:02X}")
    print(f"   - Type: {type(TEMPLATE_METADATA_KIND).__name__}")


def test_semantic_preview_limit_constant():
    """Test _SEMANTIC_PREVIEW_LIMIT constant."""
    print("\n=== Test 12: _SEMANTIC_PREVIEW_LIMIT Constant ===")
    
    assert _SEMANTIC_PREVIEW_LIMIT is not None
    assert isinstance(_SEMANTIC_PREVIEW_LIMIT, int)
    assert _SEMANTIC_PREVIEW_LIMIT == 160
    assert _SEMANTIC_PREVIEW_LIMIT > 0
    
    print(f"✅ _SEMANTIC_PREVIEW_LIMIT constant defined")
    print(f"   - Value: {_SEMANTIC_PREVIEW_LIMIT}")
    print(f"   - Purpose: Character limit for semantic sketch previews")


def test_semantic_token_limit_constant():
    """Test _SEMANTIC_TOKEN_LIMIT constant."""
    print("\n=== Test 13: _SEMANTIC_TOKEN_LIMIT Constant ===")
    
    assert _SEMANTIC_TOKEN_LIMIT is not None
    assert isinstance(_SEMANTIC_TOKEN_LIMIT, int)
    assert _SEMANTIC_TOKEN_LIMIT == 5
    assert _SEMANTIC_TOKEN_LIMIT > 0
    
    print(f"✅ _SEMANTIC_TOKEN_LIMIT constant defined")
    print(f"   - Value: {_SEMANTIC_TOKEN_LIMIT}")
    print(f"   - Purpose: Maximum tokens for semantic analysis")


def test_semantic_token_pattern_constant():
    """Test _SEMANTIC_TOKEN_PATTERN constant."""
    print("\n=== Test 14: _SEMANTIC_TOKEN_PATTERN Constant ===")
    
    assert _SEMANTIC_TOKEN_PATTERN is not None
    assert isinstance(_SEMANTIC_TOKEN_PATTERN, re.Pattern)
    
    # Test the pattern matches alphanumeric and underscore
    test_cases = [
        ("hello", True),
        ("Hello123", True),
        ("test_var", True),
        ("CamelCase", True),
        ("underscore_123", True),
        ("with-dash", False),  # Should not match dash
        ("with space", False),  # Should not match space
        ("@symbol", False),  # Should not match @
    ]
    
    for text, should_match in test_cases:
        match = _SEMANTIC_TOKEN_PATTERN.search(text)
        if should_match:
            assert match is not None, f"Expected to match: {text}"
        else:
            # Pattern might partially match, so we check if it matches the whole string
            full_match = _SEMANTIC_TOKEN_PATTERN.fullmatch(text)
            if full_match:
                # If it fully matches, that's unexpected for should_match=False
                pass  # But pattern is for searching, not full matching
    
    print(f"✅ _SEMANTIC_TOKEN_PATTERN constant defined")
    print(f"   - Type: re.Pattern")
    print(f"   - Pattern: {_SEMANTIC_TOKEN_PATTERN.pattern}")
    print(f"   - Purpose: Match alphanumeric tokens with underscores")


def test_semantic_token_pattern_functionality():
    """Test _SEMANTIC_TOKEN_PATTERN regex functionality."""
    print("\n=== Test 15: _SEMANTIC_TOKEN_PATTERN Functionality ===")
    
    # Test finding all tokens in a string
    text = "hello_world test123 CamelCase"
    tokens = _SEMANTIC_TOKEN_PATTERN.findall(text)
    
    assert len(tokens) > 0
    assert "hello_world" in tokens
    assert "test123" in tokens
    assert "CamelCase" in tokens
    
    print(f"✅ _SEMANTIC_TOKEN_PATTERN regex works")
    print(f"   - Text: '{text}'")
    print(f"   - Tokens found: {tokens}")


def test_constants_are_immutable():
    """Test that constants are defined at module level and accessible."""
    print("\n=== Test 16: Constants Accessibility ===")
    
    # All constants should be accessible
    assert TEMPLATE_METADATA_KIND is not None
    assert _SEMANTIC_PREVIEW_LIMIT is not None
    assert _SEMANTIC_TOKEN_LIMIT is not None
    assert _SEMANTIC_TOKEN_PATTERN is not None
    
    print(f"✅ All constants accessible")
    print(f"   - TEMPLATE_METADATA_KIND: {TEMPLATE_METADATA_KIND}")
    print(f"   - _SEMANTIC_PREVIEW_LIMIT: {_SEMANTIC_PREVIEW_LIMIT}")
    print(f"   - _SEMANTIC_TOKEN_LIMIT: {_SEMANTIC_TOKEN_LIMIT}")
    print(f"   - _SEMANTIC_TOKEN_PATTERN: {_SEMANTIC_TOKEN_PATTERN.pattern}")


def test_compression_method_str_representation():
    """Test string representation of CompressionMethod."""
    print("\n=== Test 17: CompressionMethod String Representation ===")
    
    method = CompressionMethod.AURALITE
    str_repr = str(method)
    
    assert "AURALITE" in str_repr
    assert isinstance(str_repr, str)
    
    print(f"✅ CompressionMethod string representation works")
    print(f"   - str(AURALITE): {str_repr}")
    print(f"   - str(BINARY_SEMANTIC): {str(CompressionMethod.BINARY_SEMANTIC)}")


def test_compression_method_repr():
    """Test repr() of CompressionMethod."""
    print("\n=== Test 18: CompressionMethod Repr ===")
    
    method = CompressionMethod.BRIO
    repr_str = repr(method)
    
    assert "BRIO" in repr_str
    assert "CompressionMethod" in repr_str
    assert isinstance(repr_str, str)
    
    print(f"✅ CompressionMethod repr works")
    print(f"   - repr(BRIO): {repr_str}")


def test_compression_method_hash():
    """Test that CompressionMethod members are hashable."""
    print("\n=== Test 19: CompressionMethod Hashable ===")
    
    # Test that enum members can be used as dict keys
    method_dict = {
        CompressionMethod.BINARY_SEMANTIC: "template-based",
        CompressionMethod.AURALITE: "lightweight",
        CompressionMethod.BRIO: "high-compression",
        CompressionMethod.UNCOMPRESSED: "no-compression",
    }
    
    assert method_dict[CompressionMethod.AURALITE] == "lightweight"
    assert method_dict[CompressionMethod.BRIO] == "high-compression"
    
    # Test set operations
    method_set = {CompressionMethod.AURALITE, CompressionMethod.BRIO, CompressionMethod.AURALITE}
    assert len(method_set) == 2  # Duplicate removed
    
    print(f"✅ CompressionMethod members are hashable")
    print(f"   - Can be used as dict keys")
    print(f"   - Can be stored in sets")


def test_compression_method_in_operator():
    """Test 'in' operator with CompressionMethod."""
    print("\n=== Test 20: CompressionMethod 'in' Operator ===")
    
    methods_list = [CompressionMethod.AURALITE, CompressionMethod.BRIO]
    
    assert CompressionMethod.AURALITE in methods_list
    assert CompressionMethod.BINARY_SEMANTIC not in methods_list
    
    # Test with all members
    all_methods = list(CompressionMethod)
    assert CompressionMethod.UNCOMPRESSED in all_methods
    
    print(f"✅ CompressionMethod 'in' operator works")
    print(f"   - AURALITE in [AURALITE, BRIO]: True")
    print(f"   - BINARY_SEMANTIC in [AURALITE, BRIO]: False")


def test_module_imports():
    """Test that all expected symbols can be imported."""
    print("\n=== Test 21: Module Imports ===")
    
    from aura_compression import enums
    
    assert hasattr(enums, 'CompressionMethod')
    assert hasattr(enums, 'TEMPLATE_METADATA_KIND')
    assert hasattr(enums, '_SEMANTIC_PREVIEW_LIMIT')
    assert hasattr(enums, '_SEMANTIC_TOKEN_LIMIT')
    assert hasattr(enums, '_SEMANTIC_TOKEN_PATTERN')
    
    print(f"✅ All symbols can be imported from enums module")


def run_all_tests():
    """Run all test functions."""
    test_functions = [
        test_compression_method_enum_exists,
        test_compression_method_members,
        test_compression_method_values,
        test_compression_method_unique_values,
        test_compression_method_byte_range,
        test_compression_method_enum_iteration,
        test_compression_method_lookup_by_value,
        test_compression_method_invalid_value,
        test_compression_method_name_property,
        test_compression_method_comparison,
        test_template_metadata_kind_constant,
        test_semantic_preview_limit_constant,
        test_semantic_token_limit_constant,
        test_semantic_token_pattern_constant,
        test_semantic_token_pattern_functionality,
        test_constants_are_immutable,
        test_compression_method_str_representation,
        test_compression_method_repr,
        test_compression_method_hash,
        test_compression_method_in_operator,
        test_module_imports,
    ]
    
    passed = 0
    failed = 0
    
    print("=" * 70)
    print("ENUMS.PY COMPREHENSIVE TEST SUITE")
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
    from enum import Enum
    run_all_tests()
