"""Static dictionary support for the Brio prototype."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional

from .constants import MAX_DICTIONARY_SIZE


@dataclass(frozen=True)
class DictionaryEntry:
    token_id: int
    phrase: str
    phrase_bytes: bytes


_PHRASES: List[str] = [
    "I don't have access to ",
    "Please check ",
    "Yes, I can help with that.",
    "What specific ",
    "To ",
    "I recommend: ",
    "use ",
    "How do I ",
    "What's the ",
    "Please provide ",
    "Error: ",
    "install ",
    "configure ",
    "monitor ",
    "optimize ",
    "performance",
    "data",
    "system",
    "deployment",
    "API",
]

if len(_PHRASES) > MAX_DICTIONARY_SIZE:
    raise RuntimeError("Dictionary exceeds supported size")

DICTIONARY: List[DictionaryEntry] = [
    DictionaryEntry(idx + 1, phrase, phrase.encode("utf-8"))
    for idx, phrase in enumerate(_PHRASES)
]

_LOOKUP = {entry.phrase: entry for entry in DICTIONARY}
_LOOKUP_BYTES = {entry.phrase_bytes: entry for entry in DICTIONARY}
_ID_LOOKUP = {entry.token_id: entry for entry in DICTIONARY}


def longest_prefix_match(text: str, pos: int) -> Optional[DictionaryEntry]:
    """Return the longest dictionary entry matching text[pos:]."""

    remainder = text[pos:]
    best: Optional[DictionaryEntry] = None
    best_len = 0
    for phrase, entry in _LOOKUP.items():
        if remainder.startswith(phrase) and len(phrase) > best_len:
            best = entry
            best_len = len(phrase)
    return best


def longest_prefix_match_bytes(data: bytes, pos: int) -> Optional[DictionaryEntry]:
    remainder = data[pos:]
    best: Optional[DictionaryEntry] = None
    best_len = 0
    for phrase, entry in _LOOKUP_BYTES.items():
        if remainder.startswith(phrase) and len(phrase) > best_len:
            best = entry
            best_len = len(phrase)
    return best


def iter_entries() -> Iterable[DictionaryEntry]:
    return list(DICTIONARY)


def by_id(entry_id: int) -> DictionaryEntry:
    return _ID_LOOKUP[entry_id]


__all__ = [
    "DictionaryEntry",
    "DICTIONARY",
    "longest_prefix_match",
    "longest_prefix_match_bytes",
    "by_id",
    "iter_entries",
]
