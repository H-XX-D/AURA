#!/usr/bin/env python3
"""
Fuzzy String Matching for AURA Compression
Implements Levenshtein distance and similarity algorithms for compressing similar messages.

This module provides fuzzy matching capabilities to identify messages that are similar
but not identical, enabling compression of messages that differ by small variations
like timestamps, counters, or minor text differences.
"""

import difflib
from typing import List, Tuple, Dict, Any, Optional
from dataclasses import dataclass
from functools import lru_cache


@dataclass
class FuzzyMatch:
    """Result of a fuzzy string match."""
    similarity: float  # 0.0 to 1.0, where 1.0 is identical
    distance: int  # Levenshtein distance
    matched_text: str
    template_pattern: str
    differences: List[Tuple[str, str]]  # List of (original, replacement) pairs


class FuzzyMatcher:
    """Fuzzy string matching for similar message compression."""

    def __init__(self,
                 min_similarity: float = 0.85,
                 max_distance: int = 50,
                 enable_caching: bool = True,
                 cache_size: int = 1000):
        """
        Initialize fuzzy matcher.

        Args:
            min_similarity: Minimum similarity ratio (0.0-1.0) to consider a match
            max_distance: Maximum Levenshtein distance to consider
            enable_caching: Enable LRU caching for performance
            cache_size: Maximum cache size for similarity calculations
        """
        self.min_similarity = min_similarity
        self.max_distance = max_distance
        self.enable_caching = enable_caching
        self.cache_size = cache_size

        if enable_caching:
            self._similarity_cache = {}
            self._distance_cache = {}

    @lru_cache(maxsize=1000)
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity ratio between two strings."""
        return difflib.SequenceMatcher(None, text1, text2).ratio()

    def _calculate_distance(self, text1: str, text2: str) -> int:
        """Calculate Levenshtein distance between two strings."""
        cache_key = (min(text1, text2), max(text1, text2))
        if self.enable_caching and cache_key in self._distance_cache:
            return self._distance_cache[cache_key]

        # Simple Levenshtein distance implementation
        if len(text1) < len(text2):
            return self._calculate_distance(text2, text1)

        if len(text2) == 0:
            return len(text1)

        previous_row = list(range(len(text2) + 1))
        for i, c1 in enumerate(text1):
            current_row = [i + 1]
            for j, c2 in enumerate(text2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row

        distance = previous_row[-1]
        if self.enable_caching:
            self._distance_cache[cache_key] = distance
        return distance

    def find_similar_patterns(self, text: str, patterns: List[str]) -> List[FuzzyMatch]:
        """
        Find patterns that are similar to the input text.

        Args:
            text: Input text to match against
            patterns: List of pattern strings to compare against

        Returns:
            List of FuzzyMatch objects for matches above threshold
        """
        matches = []

        for pattern in patterns:
            similarity = self._calculate_similarity(text, pattern)
            distance = self._calculate_distance(text, pattern)

            if similarity >= self.min_similarity and distance <= self.max_distance:
                # Find differences using difflib
                diff = list(difflib.unified_diff(
                    pattern.splitlines(keepends=True),
                    text.splitlines(keepends=True),
                    fromfile='pattern',
                    tofile='text',
                    lineterm=''
                ))

                differences = []
                if diff:
                    # Extract actual differences (skip header lines)
                    for line in diff[2:]:
                        if line.startswith('-'):
                            differences.append((line[1:].strip(), ''))
                        elif line.startswith('+'):
                            differences.append(('', line[1:].strip()))

                matches.append(FuzzyMatch(
                    similarity=similarity,
                    distance=distance,
                    matched_text=text,
                    template_pattern=pattern,
                    differences=differences
                ))

        # Sort by similarity (highest first)
        matches.sort(key=lambda x: x.similarity, reverse=True)
        return matches

    def compress_similar_message(self, text: str, template_patterns: List[str]) -> Optional[Dict[str, Any]]:
        """
        Attempt to compress a message using fuzzy matching against templates.

        Args:
            text: Message to compress
            template_patterns: List of template patterns to match against

        Returns:
            Compression result dict if successful, None otherwise
        """
        matches = self.find_similar_patterns(text, template_patterns)

        if not matches:
            return None

        # Use the best match
        best_match = matches[0]

        # Create a template from the differences
        template = best_match.template_pattern
        compressed_data = {
            'template_id': f"fuzzy_{hash(best_match.template_pattern) % 10000}",
            'similarity': best_match.similarity,
            'distance': best_match.distance,
            'differences': best_match.differences,
            'original_length': len(text),
            'compressed_length': len(str(best_match.differences)) + 100  # Estimate
        }

        return compressed_data

    def get_similarity_stats(self) -> Dict[str, Any]:
        """Get statistics about fuzzy matching performance."""
        return {
            'min_similarity_threshold': self.min_similarity,
            'max_distance_threshold': self.max_distance,
            'caching_enabled': self.enable_caching,
            'cache_size': self.cache_size,
            'similarity_cache_size': len(self._similarity_cache) if self.enable_caching else 0,
            'distance_cache_size': len(self._distance_cache) if self.enable_caching else 0,
        }


def create_fuzzy_matcher(min_similarity: float = 0.85,
                         max_distance: int = 50,
                         enable_caching: bool = True) -> FuzzyMatcher:
    """
    Factory function to create a FuzzyMatcher instance.

    Args:
        min_similarity: Minimum similarity ratio for matches
        max_distance: Maximum Levenshtein distance for matches
        enable_caching: Enable caching for performance

    Returns:
        Configured FuzzyMatcher instance
    """
    return FuzzyMatcher(
        min_similarity=min_similarity,
        max_distance=max_distance,
        enable_caching=enable_caching
    )


# Example usage and testing
if __name__ == "__main__":
    # Test the fuzzy matcher
    matcher = FuzzyMatcher(min_similarity=0.8, max_distance=10)

    test_text = "User john.doe logged in at 2023-10-29 14:30:25"
    test_patterns = [
        "User {username} logged in at {timestamp}",
        "User john.doe logged in at 2023-10-29 14:30:26",  # Very similar
        "User jane.smith logged out at 2023-10-29 14:30:25",  # Different user
        "System startup completed successfully",  # Completely different
    ]

    matches = matcher.find_similar_patterns(test_text, test_patterns)

    print(f"Found {len(matches)} fuzzy matches for: {test_text}")
    for match in matches:
        print(f"  Similarity: {match.similarity:.2f}, Distance: {match.distance}")
        print(f"  Pattern: {match.template_pattern}")
        print(f"  Differences: {match.differences}")
        print()