"""Trie data structure for efficient dictionary prefix matching."""

from __future__ import annotations

from typing import Optional, Dict
from dataclasses import dataclass


@dataclass
class TrieNode:
    """Node in the trie data structure."""
    children: Dict[str, TrieNode]
    is_end: bool
    token_id: Optional[int]
    phrase: Optional[str]

    def __init__(self):
        self.children = {}
        self.is_end = False
        self.token_id = None
        self.phrase = None


class DictionaryTrie:
    """
    Trie data structure for O(m) dictionary prefix matching.

    This replaces the linear O(n*m) search in longest_prefix_match()
    with an O(m) trie traversal, where m is the word length.
    """

    def __init__(self):
        self.root = TrieNode()
        self._size = 0

    def insert(self, phrase: str, token_id: int) -> None:
        """Insert a phrase into the trie with its token ID."""
        node = self.root
        for char in phrase:
            if char not in node.children:
                node.children[char] = TrieNode()
            node = node.children[char]

        node.is_end = True
        node.token_id = token_id
        node.phrase = phrase
        self._size += 1

    def longest_prefix_match(self, text: str, pos: int) -> Optional[tuple[str, int]]:
        """
        Find the longest dictionary phrase that matches text[pos:].

        Returns:
            (phrase, token_id) if match found, None otherwise

        Time Complexity: O(m) where m is the length of the matched phrase
        Space Complexity: O(1)
        """
        node = self.root
        best_phrase = None
        best_token_id = None

        # Traverse the trie as long as we have matching characters
        for i in range(pos, len(text)):
            char = text[i]
            if char not in node.children:
                break

            node = node.children[char]

            # If this node marks the end of a dictionary entry, remember it
            if node.is_end:
                best_phrase = node.phrase
                best_token_id = node.token_id

        return (best_phrase, best_token_id) if best_phrase else None

    def longest_prefix_match_bytes(self, data: bytes, pos: int) -> Optional[tuple[bytes, int]]:
        """
        Find the longest dictionary phrase that matches data[pos:].

        Returns:
            (phrase_bytes, token_id) if match found, None otherwise

        Time Complexity: O(m) where m is the length of the matched phrase
        """
        # Convert bytes to string for trie traversal
        try:
            text = data[pos:].decode('utf-8', errors='ignore')
        except UnicodeDecodeError:
            return None

        result = self.longest_prefix_match(text, 0)
        if result:
            phrase, token_id = result
            return (phrase.encode('utf-8'), token_id)
        return None

    def __len__(self) -> int:
        """Return the number of phrases in the trie."""
        return self._size

    def __repr__(self) -> str:
        return f"DictionaryTrie(size={self._size})"


__all__ = ["DictionaryTrie", "TrieNode"]
