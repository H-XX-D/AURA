"""Static dictionary support for the Brio prototype."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional

from .constants import MAX_DICTIONARY_SIZE
from .trie import DictionaryTrie
from .common_words import COMMON_WORDS


@dataclass(frozen=True)
class DictionaryEntry:
    token_id: int
    phrase: str
    phrase_bytes: bytes


_PHRASES: List[str] = [
    # Original support phrases (IDs 1-20)
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

    # Original long phrases (IDs 21-40)
    "I can walk you through the validation checklist so no step gets missed.",
    "Let me outline the diagnostics flow so you have a concrete sequence to follow.",
    "I'll summarize the likely root causes and the quick checks you can run right away.",
    "Here is a compact troubleshooting matrix so you can triage without waiting on logs.",
    "I'll include the policy reminders so you stay compliant with security guidance.",
    "I'll expand each SLA dimension so the expectations stay crystal clear.",
    "I'll reference the knowledge base article so you can share it with the requester if needed.",
    "Let me spell out the reasoning so you can trace every step without guessing.",
    "I'll include a short checklist you can keep handy for similar requests.",
    "I'll add context and guardrails so anyone picking this up later has everything they need.",
    "I'll provide a concise action plan plus a quick rollback path just in case.",
    "I'll map each configuration lever to the operational impact so you can explain it quickly.",
    "I can list the qualifying criteria for each tier so you choose the right one.",
    "I'll log the context and next actions so observers know the state.",
    "I'll add the alert thresholds we typically use so you can compare them with your targets.",
    "I'll walk through the reset wizard steps so you can prep the user ahead of time.",
    "I'll point out the rollback command in case you need to revert fast.",
    "I can share the changelog summary so you have extra background ready.",
    "I'll highlight the pre-deployment checks so you can confirm cluster health first.",
    "I will call out each security setting so you can confirm it before committing the change.",

    # Common articles, conjunctions, prepositions (IDs 41-60)
    "the ",
    " the ",
    "and ",
    " and ",
    "or ",
    " or ",
    "but ",
    " but ",
    "if ",
    " if ",
    "when ",
    " when ",
    "where ",
    " where ",
    "what ",
    " what ",
    "how ",
    " how ",
    "with ",
    " with ",

    # Common verbs (IDs 61-90)
    "is ",
    " is ",
    "are ",
    " are ",
    "was ",
    " was ",
    "were ",
    " were ",
    "have ",
    " have ",
    "has ",
    " has ",
    "had ",
    " had ",
    "do ",
    " do ",
    "does ",
    " does ",
    "can ",
    " can ",
    "could ",
    " could ",
    "should ",
    " should ",
    "would ",
    " would ",
    "will ",
    " will ",
    "must ",
    " must ",
    "may ",
    " may ",

    # Programming keywords (IDs 91-120)
    "function ",
    "method ",
    "class ",
    "variable ",
    "return ",
    "import ",
    "from ",
    "def ",
    "for ",
    "while ",
    "else ",
    "try ",
    "except ",
    "async ",
    "await ",
    "const ",
    "let ",
    "var ",
    "export ",
    "default ",
    "public ",
    "private ",
    "static ",
    "void ",
    "int ",
    "string ",
    "boolean ",
    "true",
    "false",
    "null",

    # Web/API terms (IDs 121-150)
    "request ",
    "response ",
    "status ",
    "error ",
    "success ",
    "GET ",
    "POST ",
    "PUT ",
    "DELETE ",
    "PATCH ",
    "JSON",
    "XML",
    "REST",
    "GraphQL",
    "endpoint ",
    "authentication ",
    "authorization ",
    "token ",
    "bearer ",
    "header ",
    "body ",
    "query ",
    "params ",
    "route ",
    "middleware ",
    "controller ",
    "service ",
    "repository ",
    "model ",
    "view ",

    # Time/date terms (IDs 151-170)
    "now",
    "today",
    "yesterday",
    "tomorrow",
    "minute ",
    "hour ",
    "day ",
    "week ",
    "month ",
    "year ",
    "time ",
    "date ",
    "timestamp ",
    "duration ",
    "interval ",
    "schedule ",
    "cron ",
    "UTC",
    "timezone ",
    "epoch ",

    # Numbers and quantities (IDs 171-190)
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "first ",
    "second ",
    "third ",
    "hundred ",
    "thousand ",
    "million ",
    "billion ",
    "count ",
    "total ",

    # Technical infrastructure (IDs 191-220)
    "database ",
    "server ",
    "client ",
    "network ",
    "security ",
    "cache ",
    "memory ",
    "CPU ",
    "disk ",
    "file ",
    "directory ",
    "process ",
    "thread ",
    "container ",
    "docker ",
    "kubernetes ",
    "pod ",
    "service ",
    "cluster ",
    "node ",
    "load balancer ",
    "proxy ",
    "gateway ",
    "firewall ",
    "VPN ",
    "SSH ",
    "TLS ",
    "SSL ",
    "certificate ",
    "encryption ",

    # Common phrases (IDs 221-254)
    "Please ",
    "Thank you",
    "You're welcome",
    "I understand",
    "Let me ",
    "Here is ",
    "There is ",
    "This is ",
    "That is ",
    "It is ",
    "You can ",
    "We can ",
    "They can ",
    "I will ",
    "You should ",
    "We should ",
    "in the ",
    "on the ",
    "at the ",
    "to the ",
    "for the ",
]

# Add 1200 common words with trailing space for efficient mid-sentence matching
# The trie will handle efficient O(m) lookup for all entries
# We prioritize words with trailing space as they're most common in natural text
for word in COMMON_WORDS:
    _PHRASES.append(word + " ")

if len(_PHRASES) > MAX_DICTIONARY_SIZE:
    raise RuntimeError("Dictionary exceeds supported size")

DICTIONARY: List[DictionaryEntry] = [
    DictionaryEntry(idx + 1, phrase, phrase.encode("utf-8"))
    for idx, phrase in enumerate(_PHRASES)
]

_LOOKUP = {entry.phrase: entry for entry in DICTIONARY}
_LOOKUP_BYTES = {entry.phrase_bytes: entry for entry in DICTIONARY}
_ID_LOOKUP = {entry.token_id: entry for entry in DICTIONARY}

# Build trie for O(m) lookup
_TRIE = DictionaryTrie()
for entry in DICTIONARY:
    _TRIE.insert(entry.phrase, entry.token_id)


def longest_prefix_match(text: str, pos: int) -> Optional[DictionaryEntry]:
    """
    Return the longest dictionary entry matching text[pos:].

    Uses trie for O(m) lookup where m is the word length.
    Old implementation was O(n*m) where n is dictionary size.
    """
    result = _TRIE.longest_prefix_match(text, pos)
    if result:
        phrase, token_id = result
        return _ID_LOOKUP[token_id]
    return None


def longest_prefix_match_bytes(data: bytes, pos: int) -> Optional[DictionaryEntry]:
    """
    Return the longest dictionary entry matching data[pos:].

    Uses trie for O(m) lookup where m is the word length.
    """
    result = _TRIE.longest_prefix_match_bytes(data, pos)
    if result:
        phrase_bytes, token_id = result
        return _ID_LOOKUP[token_id]
    return None


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
