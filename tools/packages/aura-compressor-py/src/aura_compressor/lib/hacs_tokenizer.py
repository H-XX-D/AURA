"""Simplified HACs tokenizer implementation.

The original tokenizer implemented frequency-aware tokenisation. For the
purposes of the regenerated code we provide a deterministic word-level
encoder/decoder that maintains compatibility with demos that exercise the
interface.
"""

from __future__ import annotations

import re
from typing import Dict, List, Sequence, Tuple


_WORD_RE = re.compile(r"\w+|[^\w\s]", re.UNICODE)


class HACSTokenizer:
    """Minimal tokenizer compatible with the original interface."""

    def __init__(self, max_word_length: int = 32) -> None:
        self.max_word_length = max_word_length
        self._dictionary: Dict[str, int] = {}
        self._reverse_dictionary: Dict[int, str] = {}
        self._next_token_id = 1  # Reserve 0 for padding in potential future use.

    def _lookup_token(self, token: str) -> int:
        if token in self._dictionary:
            return self._dictionary[token]
        token_id = self._next_token_id
        self._next_token_id += 1
        self._dictionary[token] = token_id
        self._reverse_dictionary[token_id] = token
        return token_id

    def tokenize(self, text: str) -> List[int]:
        tokens: List[int] = []
        for part in _WORD_RE.findall(text):
            trimmed = part if len(part) <= self.max_word_length else part[: self.max_word_length]
            tokens.append(self._lookup_token(trimmed))
        return tokens

    def tokenize_text_with_map(self, text: str) -> Tuple[List[int], Dict[int, str]]:
        tokens = self.tokenize(text)
        return tokens, dict(self._reverse_dictionary)

    def detokenize(self, tokens: Sequence[int]) -> str:
        words: List[str] = []
        for token_id in tokens:
            word = self._reverse_dictionary.get(token_id, "")
            words.append(word)
        # Simple join with spaces, followed by punctuation fix-ups.
        text = " ".join(words)
        text = re.sub(r"\s+([,.;!?])", r"\1", text)
        return text.strip()

    def detokenize_to_text(self, tokens: Sequence[int]) -> str:
        return self.detokenize(tokens)

    def reset(self) -> None:
        self._dictionary.clear()
        self._reverse_dictionary.clear()
        self._next_token_id = 1
