"""Lightweight LZ77 tokeniser for the Brio prototype."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence, Tuple, Union

from .constants import MAX_MATCH, MIN_MATCH, WINDOW_SIZE


@dataclass
class LZLiteral:
    value: int  # single byte literal


@dataclass
class LZMatch:
    distance: int
    length: int


Token = Union[LZLiteral, LZMatch]


def tokenize(data: Sequence[int], initial_window: bytearray | None = None) -> List[Token]:
    window = bytearray(initial_window) if initial_window is not None else bytearray()
    tokens: List[Token] = []
    pos = 0
    size = len(data)

    while pos < size:
        match = _find_match(window, data, pos)
        if match is None:
            literal = data[pos]
            tokens.append(LZLiteral(literal))
            window.append(literal)
            if len(window) > WINDOW_SIZE:
                del window[0]
            pos += 1
        else:
            distance, length = match
            tokens.append(LZMatch(distance, length))
            for i in range(length):
                byte = data[pos + i]
                window.append(byte)
                if len(window) > WINDOW_SIZE:
                    del window[0]
            pos += length

    return tokens


def _find_match(window: bytearray, data: Sequence[int], pos: int) -> Tuple[int, int] | None:
    if not window:
        return None

    max_len = min(MAX_MATCH, len(data) - pos)
    if max_len < MIN_MATCH:
        return None

    best_distance = 0
    best_length = 0

    window_len = len(window)
    lookback = min(window_len, WINDOW_SIZE)
    segment = data[pos : pos + max_len]

    for distance in range(1, lookback + 1):
        start = window_len - distance
        if start < 0:
            break
        length = 0
        while length < max_len and window[start + length] == segment[length]:
            length += 1
            if start + length >= window_len:
                break
        if length >= MIN_MATCH and length > best_length:
            best_distance = distance
            best_length = length
            if length == max_len:
                break

    if best_length >= MIN_MATCH:
        return best_distance, best_length
    return None


__all__ = ["LZLiteral", "LZMatch", "Token", "tokenize"]
