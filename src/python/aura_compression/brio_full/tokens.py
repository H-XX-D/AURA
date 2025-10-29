"""Token definitions for the Brio prototype."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Union


@dataclass
class LiteralToken:
    value: int  # single byte


@dataclass
class DictionaryToken:
    entry_id: int


@dataclass
class MatchToken:
    distance: int
    length: int


@dataclass
class TemplateToken:
    template_id: int
    slots: List[str]


Token = Union[LiteralToken, DictionaryToken, MatchToken, TemplateToken]


@dataclass
class MetadataEntry:
    token_index: int
    kind: int
    value: int
    flags: int = 0


__all__ = [
    "LiteralToken",
    "DictionaryToken",
    "MatchToken",
    "TemplateToken",
    "Token",
    "MetadataEntry",
]
