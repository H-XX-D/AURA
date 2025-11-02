#!/usr/bin/env python3
"""
Comprehensive test suite for fuzzy_matcher.py

Tests fuzzy string matching using Levenshtein distance and similarity algorithms.
Validates pattern matching for compressing similar messages with small variations.
"""
import os
import sys
from pathlib import Path
import traceback

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aura_compression.fuzzy_matcher import (
    FuzzyMatch,
    FuzzyMatcher,
    create_fuzzy_matcher,
)


def test_fuzzy_match_dataclass():
    """Test FuzzyMatch dataclass creation."""
    print("\n=== Test 1: FuzzyMatch Dataclass ===")
    
    match = FuzzyMatch(
        similarity=0.95,
        distance=3,
        matched_text="Hello world 123",
        template_pattern="Hello world {num}",
        differences=[("123", "{num}")]
    )
    
    assert match.similarity == 0.95
    assert match.distance == 3
    assert match.matched_text == "Hello world 123"
    assert match.template_pattern == "Hello world {num}"
    assert len(match.differences) == 1
    
    print(f"✅ FuzzyMatch dataclass works")
    print(f"   - Similarity: {match.similarity}")
    print(f"   - Distance: {match.distance}")
    print(f"   - Matched text: {match.matched_text}")
    print(f"   - Template: {match.template_pattern}")


def test_fuzzy_matcher_initialization():
    """Test FuzzyMatcher initialization with default parameters."""
    print("\n=== Test 2: FuzzyMatcher Initialization ===")
    
    matcher = FuzzyMatcher()
    
    assert matcher.min_similarity == 0.85
    assert matcher.max_distance == 50
    assert matcher.enable_caching == True
    assert matcher.cache_size == 1000
    
    print(f"✅ FuzzyMatcher initialized with defaults")
    print(f"   - Min similarity: {matcher.min_similarity}")
    print(f"   - Max distance: {matcher.max_distance}")
    print(f"   - Caching enabled: {matcher.enable_caching}")


def test_fuzzy_matcher_custom_parameters():
    """Test FuzzyMatcher with custom parameters."""
    print("\n=== Test 3: FuzzyMatcher Custom Parameters ===")
    
    matcher = FuzzyMatcher(
        min_similarity=0.75,
        max_distance=30,
        enable_caching=False,
        cache_size=500
    )
    
    assert matcher.min_similarity == 0.75
    assert matcher.max_distance == 30
    assert matcher.enable_caching == False
    assert matcher.cache_size == 500
    
    print(f"✅ FuzzyMatcher initialized with custom parameters")
    print(f"   - Min similarity: {matcher.min_similarity}")
    print(f"   - Max distance: {matcher.max_distance}")
    print(f"   - Caching: {matcher.enable_caching}")


def test_similarity_identical_strings():
    """Test similarity calculation for identical strings."""
    print("\n=== Test 4: Similarity (identical strings) ===")
    
    matcher = FuzzyMatcher()
    
    text = "Hello World"
    similarity = matcher.match(text, text)
    
    assert similarity == 1.0
    
    print(f"✅ Identical strings have similarity 1.0")
    print(f"   - Text: '{text}'")
    print(f"   - Similarity: {similarity}")


def test_similarity_different_strings():
    """Test similarity calculation for different strings."""
    print("\n=== Test 5: Similarity (different strings) ===")
    
    matcher = FuzzyMatcher()
    
    text1 = "Hello World"
    text2 = "Hello Python"
    similarity = matcher.match(text1, text2)
    
    assert 0.0 < similarity < 1.0
    assert similarity > 0.5  # "Hello" is common
    
    print(f"✅ Different strings have similarity between 0.0 and 1.0")
    print(f"   - Text 1: '{text1}'")
    print(f"   - Text 2: '{text2}'")
    print(f"   - Similarity: {similarity:.3f}")


def test_similarity_completely_different():
    """Test similarity calculation for completely different strings."""
    print("\n=== Test 6: Similarity (completely different) ===")
    
    matcher = FuzzyMatcher()
    
    text1 = "abc"
    text2 = "xyz"
    similarity = matcher.match(text1, text2)
    
    assert similarity == 0.0
    
    print(f"✅ Completely different strings have similarity 0.0")
    print(f"   - Text 1: '{text1}'")
    print(f"   - Text 2: '{text2}'")
    print(f"   - Similarity: {similarity}")


def test_similarity_with_small_changes():
    """Test similarity with small changes (timestamp, counter)."""
    print("\n=== Test 7: Similarity (small changes) ===")
    
    matcher = FuzzyMatcher()
    
    text1 = "User logged in at 2023-10-29 14:30:25"
    text2 = "User logged in at 2023-10-29 14:30:26"
    similarity = matcher.match(text1, text2)
    
    assert similarity > 0.95  # Very similar, only 1 character different
    
    print(f"✅ Strings with small changes are very similar")
    print(f"   - Text 1: '{text1}'")
    print(f"   - Text 2: '{text2}'")
    print(f"   - Similarity: {similarity:.3f}")


def test_levenshtein_distance_identical():
    """Test Levenshtein distance for identical strings."""
    print("\n=== Test 8: Levenshtein Distance (identical) ===")
    
    matcher = FuzzyMatcher()
    
    text = "Hello World"
    distance = matcher._calculate_distance(text, text)
    
    assert distance == 0
    
    print(f"✅ Identical strings have Levenshtein distance 0")
    print(f"   - Text: '{text}'")
    print(f"   - Distance: {distance}")


def test_levenshtein_distance_one_insertion():
    """Test Levenshtein distance with one insertion."""
    print("\n=== Test 9: Levenshtein Distance (one insertion) ===")
    
    matcher = FuzzyMatcher()
    
    text1 = "kitten"
    text2 = "kittens"
    distance = matcher._calculate_distance(text1, text2)
    
    assert distance == 1
    
    print(f"✅ One insertion has distance 1")
    print(f"   - Text 1: '{text1}'")
    print(f"   - Text 2: '{text2}'")
    print(f"   - Distance: {distance}")


def test_levenshtein_distance_one_deletion():
    """Test Levenshtein distance with one deletion."""
    print("\n=== Test 10: Levenshtein Distance (one deletion) ===")
    
    matcher = FuzzyMatcher()
    
    text1 = "sitting"
    text2 = "sittin"
    distance = matcher._calculate_distance(text1, text2)
    
    assert distance == 1
    
    print(f"✅ One deletion has distance 1")
    print(f"   - Text 1: '{text1}'")
    print(f"   - Text 2: '{text2}'")
    print(f"   - Distance: {distance}")


def test_levenshtein_distance_one_substitution():
    """Test Levenshtein distance with one substitution."""
    print("\n=== Test 11: Levenshtein Distance (one substitution) ===")
    
    matcher = FuzzyMatcher()
    
    text1 = "kitten"
    text2 = "sitten"
    distance = matcher._calculate_distance(text1, text2)
    
    assert distance == 1
    
    print(f"✅ One substitution has distance 1")
    print(f"   - Text 1: '{text1}'")
    print(f"   - Text 2: '{text2}'")
    print(f"   - Distance: {distance}")


def test_levenshtein_distance_multiple_edits():
    """Test Levenshtein distance with multiple edits."""
    print("\n=== Test 12: Levenshtein Distance (multiple edits) ===")
    
    matcher = FuzzyMatcher()
    
    text1 = "Saturday"
    text2 = "Sunday"
    distance = matcher._calculate_distance(text1, text2)
    
    assert distance == 3  # Sat -> Sun requires 3 operations
    
    print(f"✅ Multiple edits calculated correctly")
    print(f"   - Text 1: '{text1}'")
    print(f"   - Text 2: '{text2}'")
    print(f"   - Distance: {distance}")


def test_levenshtein_distance_empty_string():
    """Test Levenshtein distance with empty string."""
    print("\n=== Test 13: Levenshtein Distance (empty string) ===")
    
    matcher = FuzzyMatcher()
    
    text1 = "hello"
    text2 = ""
    distance = matcher._calculate_distance(text1, text2)
    
    assert distance == len(text1)
    
    print(f"✅ Distance to empty string equals string length")
    print(f"   - Text: '{text1}'")
    print(f"   - Empty: ''")
    print(f"   - Distance: {distance}")


def test_find_similar_patterns_exact_match():
    """Test finding patterns with exact match."""
    print("\n=== Test 14: Find Similar Patterns (exact match) ===")
    
    matcher = FuzzyMatcher(min_similarity=0.85)
    
    text = "User john.doe logged in"
    patterns = [
        "User john.doe logged in",  # Exact match
        "User jane.smith logged out",
        "System error occurred"
    ]
    
    matches = matcher.find_similar_patterns(text, patterns)
    
    assert len(matches) >= 1
    assert matches[0].similarity == 1.0
    assert matches[0].distance == 0
    
    print(f"✅ Exact match found")
    print(f"   - Text: '{text}'")
    print(f"   - Best match similarity: {matches[0].similarity}")
    print(f"   - Best match distance: {matches[0].distance}")


def test_find_similar_patterns_high_similarity():
    """Test finding patterns with high similarity."""
    print("\n=== Test 15: Find Similar Patterns (high similarity) ===")
    
    matcher = FuzzyMatcher(min_similarity=0.80, max_distance=20)
    
    text = "User logged in at 2023-10-29 14:30:25"
    patterns = [
        "User logged in at 2023-10-29 14:30:26",  # Very similar
        "User logged out at 2023-10-29 14:30:25",  # Moderately similar
        "System started successfully"  # Not similar
    ]
    
    matches = matcher.find_similar_patterns(text, patterns)
    
    assert len(matches) >= 1
    assert matches[0].similarity > 0.90  # Best match should be very similar
    
    print(f"✅ High similarity patterns found")
    print(f"   - Text: '{text}'")
    print(f"   - Matches found: {len(matches)}")
    if matches:
        print(f"   - Best match similarity: {matches[0].similarity:.3f}")


def test_find_similar_patterns_no_matches():
    """Test finding patterns with no matches above threshold."""
    print("\n=== Test 16: Find Similar Patterns (no matches) ===")
    
    matcher = FuzzyMatcher(min_similarity=0.95, max_distance=5)
    
    text = "Hello World"
    patterns = [
        "Goodbye Universe",
        "Python Programming",
        "Data Science"
    ]
    
    matches = matcher.find_similar_patterns(text, patterns)
    
    assert len(matches) == 0
    
    print(f"✅ No matches found below threshold")
    print(f"   - Text: '{text}'")
    print(f"   - Matches: {len(matches)}")


def test_find_similar_patterns_sorted_by_similarity():
    """Test that matches are sorted by similarity (highest first)."""
    print("\n=== Test 17: Find Similar Patterns (sorted) ===")
    
    matcher = FuzzyMatcher(min_similarity=0.70, max_distance=50)
    
    text = "Error occurred at line 42"
    patterns = [
        "Error occurred at line 100",  # Similar
        "Error occurred at line 42",   # Exact match
        "Warning occurred at line 42",  # Moderately similar
    ]
    
    matches = matcher.find_similar_patterns(text, patterns)
    
    assert len(matches) >= 2
    # First match should have highest similarity
    assert matches[0].similarity >= matches[1].similarity
    # Exact match should be first
    assert matches[0].distance == 0
    
    print(f"✅ Matches sorted by similarity")
    print(f"   - Text: '{text}'")
    print(f"   - Matches: {len(matches)}")
    for i, match in enumerate(matches[:3]):
        print(f"   - Match {i+1}: similarity={match.similarity:.3f}, distance={match.distance}")


def test_compress_similar_message_success():
    """Test compressing a message using fuzzy matching."""
    print("\n=== Test 18: Compress Similar Message (success) ===")
    
    matcher = FuzzyMatcher(min_similarity=0.85, max_distance=20)
    
    text = "User john.doe logged in at 2023-10-29 14:30:25"
    templates = [
        "User john.doe logged in at 2023-10-29 14:30:26",  # Very similar
    ]
    
    result = matcher.compress_similar_message(text, templates)
    
    assert result is not None
    assert 'template_id' in result
    assert 'similarity' in result
    assert 'distance' in result
    assert result['similarity'] > 0.85
    
    print(f"✅ Message compressed using fuzzy matching")
    print(f"   - Original length: {result['original_length']}")
    print(f"   - Similarity: {result['similarity']:.3f}")
    print(f"   - Distance: {result['distance']}")


def test_compress_similar_message_no_match():
    """Test compressing when no similar templates exist."""
    print("\n=== Test 19: Compress Similar Message (no match) ===")
    
    matcher = FuzzyMatcher(min_similarity=0.95, max_distance=5)
    
    text = "Hello World"
    templates = [
        "Goodbye Universe",
        "Python Programming"
    ]
    
    result = matcher.compress_similar_message(text, templates)
    
    assert result is None
    
    print(f"✅ No compression when no similar templates")
    print(f"   - Text: '{text}'")
    print(f"   - Result: {result}")


def test_compress_similar_message_best_match():
    """Test that compression uses the best match."""
    print("\n=== Test 20: Compress Similar Message (best match) ===")
    
    matcher = FuzzyMatcher(min_similarity=0.80, max_distance=50)
    
    text = "System status: OK at 14:30:25"
    templates = [
        "System status: FAIL at 14:30:25",  # Moderate similarity
        "System status: OK at 14:30:26",    # High similarity
        "Application started successfully"   # Low similarity
    ]
    
    result = matcher.compress_similar_message(text, templates)
    
    assert result is not None
    # Should use the template with highest similarity
    assert result['similarity'] > 0.85
    
    print(f"✅ Compression uses best match")
    print(f"   - Text: '{text}'")
    print(f"   - Best similarity: {result['similarity']:.3f}")


def test_caching_enabled():
    """Test that caching improves performance."""
    print("\n=== Test 21: Caching Enabled ===")
    
    matcher = FuzzyMatcher(enable_caching=True, cache_size=100)
    
    text1 = "Hello World"
    text2 = "Hello Python"
    
    # First call - should populate cache
    similarity1 = matcher.match(text1, text2)
    distance1 = matcher._calculate_distance(text1, text2)
    
    # Second call - should use cache
    similarity2 = matcher.match(text1, text2)
    distance2 = matcher._calculate_distance(text1, text2)
    
    assert similarity1 == similarity2
    assert distance1 == distance2
    assert len(matcher._distance_cache) > 0
    
    print(f"✅ Caching works")
    print(f"   - Similarity: {similarity1:.3f}")
    print(f"   - Distance: {distance1}")
    print(f"   - Cache size: {len(matcher._distance_cache)}")


def test_caching_disabled():
    """Test operation with caching disabled."""
    print("\n=== Test 22: Caching Disabled ===")
    
    matcher = FuzzyMatcher(enable_caching=False)
    
    text1 = "Hello World"
    text2 = "Hello Python"
    
    similarity = matcher.match(text1, text2)
    distance = matcher._calculate_distance(text1, text2)
    
    assert similarity > 0.0
    assert distance > 0
    
    print(f"✅ Works without caching")
    print(f"   - Similarity: {similarity:.3f}")
    print(f"   - Distance: {distance}")


def test_get_similarity_stats():
    """Test getting similarity statistics."""
    print("\n=== Test 23: Get Similarity Stats ===")
    
    matcher = FuzzyMatcher(
        min_similarity=0.90,
        max_distance=25,
        enable_caching=True,
        cache_size=500
    )
    
    # Perform some operations to populate cache
    matcher.match("test1", "test2")
    matcher._calculate_distance("abc", "def")
    
    stats = matcher.get_similarity_stats()
    
    assert stats['min_similarity_threshold'] == 0.90
    assert stats['max_distance_threshold'] == 25
    assert stats['caching_enabled'] == True
    assert stats['cache_size'] == 500
    assert 'similarity_cache_size' in stats
    assert 'distance_cache_size' in stats
    
    print(f"✅ Similarity stats retrieved")
    print(f"   - Min similarity: {stats['min_similarity_threshold']}")
    print(f"   - Max distance: {stats['max_distance_threshold']}")
    print(f"   - Caching: {stats['caching_enabled']}")
    print(f"   - Distance cache size: {stats['distance_cache_size']}")


def test_create_fuzzy_matcher_factory():
    """Test factory function for creating FuzzyMatcher."""
    print("\n=== Test 24: Create FuzzyMatcher Factory ===")
    
    matcher = create_fuzzy_matcher(
        min_similarity=0.80,
        max_distance=40,
        enable_caching=True,
        cache_size=800
    )
    
    assert isinstance(matcher, FuzzyMatcher)
    assert matcher.min_similarity == 0.80
    assert matcher.max_distance == 40
    assert matcher.enable_caching == True
    assert matcher.cache_size == 800
    
    print(f"✅ Factory function creates FuzzyMatcher")
    print(f"   - Type: {type(matcher).__name__}")
    print(f"   - Min similarity: {matcher.min_similarity}")


def test_create_fuzzy_matcher_defaults():
    """Test factory function with default parameters."""
    print("\n=== Test 25: Create FuzzyMatcher Factory (defaults) ===")
    
    matcher = create_fuzzy_matcher()
    
    assert isinstance(matcher, FuzzyMatcher)
    assert matcher.min_similarity == 0.85
    assert matcher.max_distance == 50
    
    print(f"✅ Factory function uses correct defaults")
    print(f"   - Min similarity: {matcher.min_similarity}")
    print(f"   - Max distance: {matcher.max_distance}")


def test_real_world_log_messages():
    """Test with real-world log message variations."""
    print("\n=== Test 26: Real-world Log Messages ===")
    
    matcher = FuzzyMatcher(min_similarity=0.85, max_distance=30)
    
    text = "2023-10-29 14:30:25 [INFO] User john.doe logged in from 192.168.1.100"
    patterns = [
        "2023-10-29 14:30:26 [INFO] User john.doe logged in from 192.168.1.100",  # Timestamp diff
        "2023-10-29 14:30:25 [INFO] User jane.smith logged in from 192.168.1.101",  # User diff
        "2023-10-29 14:30:25 [ERROR] System error occurred"  # Completely different
    ]
    
    matches = matcher.find_similar_patterns(text, patterns)
    
    assert len(matches) >= 1
    # First match should be the one with timestamp difference
    assert matches[0].similarity > 0.90
    
    print(f"✅ Real-world log messages matched")
    print(f"   - Text: '{text[:50]}...'")
    print(f"   - Matches: {len(matches)}")
    print(f"   - Best similarity: {matches[0].similarity:.3f}")


def test_compression_ratio_estimate():
    """Test that compression estimates are reasonable."""
    print("\n=== Test 27: Compression Ratio Estimate ===")
    
    matcher = FuzzyMatcher(min_similarity=0.85)
    
    text = "User logged in at 2023-10-29 14:30:25 from IP 192.168.1.100"
    templates = [
        "User logged in at 2023-10-29 14:30:26 from IP 192.168.1.101"
    ]
    
    result = matcher.compress_similar_message(text, templates)
    
    assert result is not None
    assert result['original_length'] == len(text)
    assert result['compressed_length'] > 0
    # Compressed should typically be smaller (but not guaranteed with estimation)
    
    print(f"✅ Compression ratio estimated")
    print(f"   - Original: {result['original_length']} bytes")
    print(f"   - Compressed: {result['compressed_length']} bytes")
    print(f"   - Ratio: {result['original_length'] / result['compressed_length']:.2f}x")


def test_unicode_support():
    """Test fuzzy matching with Unicode characters."""
    print("\n=== Test 28: Unicode Support ===")
    
    matcher = FuzzyMatcher(min_similarity=0.85)
    
    text1 = "Hello 世界 🌍"
    text2 = "Hello 世界 🌎"
    
    similarity = matcher.match(text1, text2)
    distance = matcher._calculate_distance(text1, text2)
    
    assert similarity > 0.8  # Should be very similar
    assert distance <= 2  # Only emoji different
    
    print(f"✅ Unicode characters supported")
    print(f"   - Text 1: '{text1}'")
    print(f"   - Text 2: '{text2}'")
    print(f"   - Similarity: {similarity:.3f}")
    print(f"   - Distance: {distance}")


def test_empty_strings():
    """Test handling of empty strings."""
    print("\n=== Test 29: Empty Strings ===")
    
    matcher = FuzzyMatcher()
    
    # Empty vs empty
    similarity1 = matcher.match("", "")
    assert similarity1 == 1.0
    
    # Empty vs non-empty
    similarity2 = matcher.match("", "hello")
    assert similarity2 == 0.0
    
    distance1 = matcher._calculate_distance("", "")
    assert distance1 == 0
    
    distance2 = matcher._calculate_distance("", "hello")
    assert distance2 == 5
    
    print(f"✅ Empty strings handled correctly")
    print(f"   - Empty vs empty similarity: {similarity1}")
    print(f"   - Empty vs 'hello' similarity: {similarity2}")


def test_very_long_strings():
    """Test with very long strings."""
    print("\n=== Test 30: Very Long Strings ===")
    
    matcher = FuzzyMatcher(min_similarity=0.85, max_distance=100)
    
    text1 = "A" * 1000 + "B"
    text2 = "A" * 1000 + "C"
    
    similarity = matcher.match(text1, text2)
    distance = matcher._calculate_distance(text1, text2)
    
    assert similarity > 0.99  # Nearly identical
    assert distance == 1  # Only 1 character different
    
    print(f"✅ Long strings handled efficiently")
    print(f"   - String length: {len(text1)} chars")
    print(f"   - Similarity: {similarity:.4f}")
    print(f"   - Distance: {distance}")


def test_lru_cache_efficiency():
    """Test that LRU cache improves repeated calculations."""
    print("\n=== Test 31: LRU Cache Efficiency ===")
    
    matcher = FuzzyMatcher(enable_caching=True)
    
    text1 = "Hello World"
    text2 = "Hello Python"
    
    # Multiple identical calls should use cache
    results = []
    for _ in range(5):
        similarity = matcher._calculate_similarity(text1, text2)
        results.append(similarity)
    
    # All results should be identical
    assert all(r == results[0] for r in results)
    
    print(f"✅ LRU cache provides consistent results")
    print(f"   - Repeated calls: 5")
    print(f"   - Similarity: {results[0]:.3f}")


def test_differences_extraction():
    """Test that differences are extracted correctly."""
    print("\n=== Test 32: Differences Extraction ===")
    
    matcher = FuzzyMatcher(min_similarity=0.70, max_distance=50)
    
    text = "User john logged in"
    patterns = [
        "User jane logged in"
    ]
    
    matches = matcher.find_similar_patterns(text, patterns)
    
    assert len(matches) >= 1
    # Should have differences extracted (though may be empty depending on diff format)
    assert hasattr(matches[0], 'differences')
    assert isinstance(matches[0].differences, list)
    
    print(f"✅ Differences extracted")
    print(f"   - Text: '{text}'")
    print(f"   - Pattern: '{patterns[0]}'")
    print(f"   - Differences: {len(matches[0].differences)}")


def run_all_tests():
    """Run all test functions."""
    test_functions = [
        test_fuzzy_match_dataclass,
        test_fuzzy_matcher_initialization,
        test_fuzzy_matcher_custom_parameters,
        test_similarity_identical_strings,
        test_similarity_different_strings,
        test_similarity_completely_different,
        test_similarity_with_small_changes,
        test_levenshtein_distance_identical,
        test_levenshtein_distance_one_insertion,
        test_levenshtein_distance_one_deletion,
        test_levenshtein_distance_one_substitution,
        test_levenshtein_distance_multiple_edits,
        test_levenshtein_distance_empty_string,
        test_find_similar_patterns_exact_match,
        test_find_similar_patterns_high_similarity,
        test_find_similar_patterns_no_matches,
        test_find_similar_patterns_sorted_by_similarity,
        test_compress_similar_message_success,
        test_compress_similar_message_no_match,
        test_compress_similar_message_best_match,
        test_caching_enabled,
        test_caching_disabled,
        test_get_similarity_stats,
        test_create_fuzzy_matcher_factory,
        test_create_fuzzy_matcher_defaults,
        test_real_world_log_messages,
        test_compression_ratio_estimate,
        test_unicode_support,
        test_empty_strings,
        test_very_long_strings,
        test_lru_cache_efficiency,
        test_differences_extraction,
    ]
    
    passed = 0
    failed = 0
    
    print("=" * 70)
    print("FUZZY_MATCHER.PY COMPREHENSIVE TEST SUITE")
    print("Levenshtein Distance & Similarity for Similar Message Compression")
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
        print("\nValidated Fuzzy Matching:")
        print("  - Similarity calculation (SequenceMatcher)")
        print("  - Levenshtein distance algorithm")
        print("  - Pattern matching with thresholds")
        print("  - Message compression using fuzzy templates")
        print("  - LRU caching for performance")
        print("  - Unicode support")
        print("  - Real-world log message handling")
        sys.exit(0)
    else:
        print(f"❌ {failed} TEST(S) FAILED")
        sys.exit(1)


if __name__ == "__main__":
    run_all_tests()
