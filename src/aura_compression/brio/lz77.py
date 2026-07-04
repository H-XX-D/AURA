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
    data_bytes = bytes(data)
    window = bytearray(initial_window) if initial_window is not None else bytearray()
    if len(window) > WINDOW_SIZE:
        del window[: len(window) - WINDOW_SIZE]
    tokens: List[Token] = []
    pos = 0
    size = len(data_bytes)
    data_view = memoryview(data_bytes)

    while pos < size:
        match = _find_match(window, data_view, pos)
        if match is None:
            literal = data_bytes[pos]
            tokens.append(LZLiteral(literal))
            window.append(literal)
            if len(window) > WINDOW_SIZE:
                del window[: len(window) - WINDOW_SIZE]
            pos += 1
        else:
            distance, length = match
            tokens.append(LZMatch(distance, length))
            for i in range(length):
                byte = data_bytes[pos + i]
                window.append(byte)
                if len(window) > WINDOW_SIZE:
                    del window[: len(window) - WINDOW_SIZE]
            pos += length

    return tokens


def _find_match(window: bytearray, data: memoryview, pos: int) -> Tuple[int, int] | None:
    if not window:
        return None

    max_len = min(MAX_MATCH, len(data) - pos)
    if max_len < MIN_MATCH:
        return None

    best_distance = 0
    best_length = 0

    window_len = len(window)
    segment_view = data[pos : pos + max_len]
    prefix = segment_view[:MIN_MATCH].tobytes()
    window_bytes = bytes(window)

    idx = window_bytes.rfind(prefix)
    while idx != -1:
        distance = window_len - idx
        if distance <= 0 or distance > WINDOW_SIZE:
            idx = window_bytes.rfind(prefix, 0, idx)
            continue
        length = MIN_MATCH
        # Extend match while bytes continue to align
        while (
            length < max_len
            and idx + length < window_len
            and window_bytes[idx + length] == segment_view[length]
        ):
            length += 1
            if length == max_len:
                break
        if length > best_length:
            best_distance = distance
            best_length = length
            if best_length == max_len:
                break
        idx = window_bytes.rfind(prefix, 0, idx)

    if best_length >= MIN_MATCH:
        return best_distance, best_length
    return None


__all__ = ["LZLiteral", "LZMatch", "Token", "tokenize"]
