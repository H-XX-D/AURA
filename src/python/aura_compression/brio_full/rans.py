"""Minimal rANS encoder/decoder for the Brio prototype."""

from __future__ import annotations

from typing import Iterable, List, Sequence

from .constants import ANS_SCALE, ANS_SCALE_BITS

LOWER_BOUND = ANS_SCALE << 8  # keep plenty of headroom for renormalisation


def build_frequencies(data: Sequence[int]) -> List[int]:
    freqs = [1] * 256  # start with uniform smoothing to avoid zeros
    for b in data:
        freqs[b] += 1
    return freqs


def normalise_frequencies(freqs: Sequence[int]) -> List[int]:
    total = sum(freqs)
    if total == ANS_SCALE:
        return list(freqs)

    scaled = [max(1, (f * ANS_SCALE) // total) for f in freqs]
    adjust = ANS_SCALE - sum(scaled)
    # distribute adjustment across the most frequent symbols
    if adjust > 0:
        for idx in sorted(range(256), key=lambda i: freqs[i], reverse=True):
            scaled[idx] += 1
            adjust -= 1
            if adjust == 0:
                break
    elif adjust < 0:
        for idx in sorted(range(256), key=lambda i: freqs[i]):
            if scaled[idx] > 1:
                scaled[idx] -= 1
                adjust += 1
                if adjust == 0:
                    break
    return scaled


def cumulative(freqs: Sequence[int]) -> List[int]:
    cum = [0] * 257
    running = 0
    for i, f in enumerate(freqs):
        cum[i] = running
        running += f
    cum[256] = running
    return cum


def build_symbol_lookup(freqs: Sequence[int], cumfreq: Sequence[int]) -> List[int]:
    table = [0] * ANS_SCALE
    for sym in range(256):
        f = freqs[sym]
        if f == 0:
            continue
        start = cumfreq[sym]
        for x in range(f):
            table[start + x] = sym
    return table


def encode(data: Sequence[int], freqs: Sequence[int], cumfreq: Sequence[int]) -> bytes:
    state = LOWER_BOUND
    out = bytearray()
    for sym in reversed(data):
        f = freqs[sym]
        c = cumfreq[sym]
        while state >= (f << 16):
            out.append(state & 0xFF)
            state >>= 8
        state = ((state // f) << ANS_SCALE_BITS) + (state % f) + c

    # flush final state
    for _ in range(5):
        out.append(state & 0xFF)
        state >>= 8

    return bytes(out)


def decode(encoded: bytes, count: int, freqs: Sequence[int], cumfreq: Sequence[int], lookup: Sequence[int]) -> List[int]:
    stream = list(encoded)
    # Extract final state (last 5 bytes)
    state_bytes = stream[-5:]
    stream = stream[:-5]
    state = 0
    for shift, b in enumerate(state_bytes):
        state |= b << (shift * 8)

    out: List[int] = []
    stream_idx = len(stream) - 1  # Start from end of stream

    while len(out) < count:
        value = state & (ANS_SCALE - 1)
        sym = lookup[value]
        out.append(sym)

        f = freqs[sym]
        c = cumfreq[sym]
        state = f * (state >> ANS_SCALE_BITS) + (value - c)

        while state < LOWER_BOUND and stream_idx >= 0:
            state = (state << 8) | stream[stream_idx]
            stream_idx -= 1

    return out


__all__ = [
    "build_frequencies",
    "normalise_frequencies",
    "cumulative",
    "build_symbol_lookup",
    "encode",
    "decode",
]
