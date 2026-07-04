#!/usr/bin/env python3
"""Optional CUDA-native primitives for AURA.

The backend is deliberately loaded with ``ctypes`` instead of a Python extension
module so importing AURA remains safe on machines without CUDA.
"""

from __future__ import annotations

import ctypes
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


class CudaNativeError(RuntimeError):
    """Raised when the CUDA native backend reports an execution failure."""


@dataclass(frozen=True)
class CudaNativeStatus:
    """Runtime status for the CUDA native backend."""

    available: bool
    library_path: Optional[str]
    device_count: int = 0
    device_name: Optional[str] = None
    error: Optional[str] = None

    def as_dict(self) -> dict:
        return {
            "available": self.available,
            "library_path": self.library_path,
            "device_count": self.device_count,
            "device_name": self.device_name,
            "error": self.error,
        }


class CudaNativeBackend:
    """Thin Python wrapper around ``libaura_cuda.so``."""

    _LIB_NAME = "libaura_cuda.so"

    def __init__(self, library_path: Optional[str] = None):
        self._library_path = library_path or self._find_library()
        self._lib = None
        self._load_error: Optional[str] = None
        self._status: Optional[CudaNativeStatus] = None

        if self._library_path:
            self._load_library(self._library_path)
        else:
            self._load_error = "libaura_cuda.so not found"

    @classmethod
    def _candidate_paths(cls) -> Iterable[Path]:
        env_path = os.getenv("AURA_CUDA_LIBRARY")
        if env_path:
            yield Path(env_path).expanduser()

        package_dir = Path(__file__).resolve().parent
        yield package_dir / "native" / cls._LIB_NAME

        repo_root = package_dir.parents[1] if len(package_dir.parents) > 1 else package_dir
        yield repo_root / "native" / "cuda" / "build" / cls._LIB_NAME

    @classmethod
    def _find_library(cls) -> Optional[str]:
        for path in cls._candidate_paths():
            if path.exists():
                return str(path)
        return cls._LIB_NAME

    def _load_library(self, library_path: str) -> None:
        try:
            self._lib = ctypes.CDLL(library_path)
            self._configure_signatures()
        except (OSError, AttributeError) as exc:
            self._lib = None
            self._load_error = str(exc)

    def _configure_signatures(self) -> None:
        assert self._lib is not None
        self._lib.aura_cuda_last_error.argtypes = []
        self._lib.aura_cuda_last_error.restype = ctypes.c_char_p

        self._lib.aura_cuda_device_count.argtypes = [ctypes.POINTER(ctypes.c_int)]
        self._lib.aura_cuda_device_count.restype = ctypes.c_int

        self._lib.aura_cuda_get_device_name.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_size_t,
        ]
        self._lib.aura_cuda_get_device_name.restype = ctypes.c_int

        self._lib.aura_cuda_histogram_u8.argtypes = [
            ctypes.POINTER(ctypes.c_uint8),
            ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_uint32),
        ]
        self._lib.aura_cuda_histogram_u8.restype = ctypes.c_int

        self._lib.aura_cuda_shannon_entropy_u8.argtypes = [
            ctypes.POINTER(ctypes.c_uint8),
            ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_double),
        ]
        self._lib.aura_cuda_shannon_entropy_u8.restype = ctypes.c_int

        self._lib.aura_cuda_rolling_hash3_u8.argtypes = [
            ctypes.POINTER(ctypes.c_uint8),
            ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_uint32),
        ]
        self._lib.aura_cuda_rolling_hash3_u8.restype = ctypes.c_int

        self._lib.aura_cuda_lz_match_candidates_u8.argtypes = [
            ctypes.POINTER(ctypes.c_uint8),
            ctypes.c_size_t,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_uint32),
            ctypes.POINTER(ctypes.c_uint8),
        ]
        self._lib.aura_cuda_lz_match_candidates_u8.restype = ctypes.c_int

    def _last_error(self) -> str:
        if self._lib is None:
            return self._load_error or "CUDA library not loaded"
        raw = self._lib.aura_cuda_last_error()
        return raw.decode("utf-8", errors="replace") if raw else "unknown CUDA error"

    def _check_rc(self, rc: int) -> None:
        if rc != 0:
            raise CudaNativeError(self._last_error())

    @staticmethod
    def _as_u8_buffer(data: bytes):
        return (ctypes.c_uint8 * len(data)).from_buffer_copy(data)

    @staticmethod
    def _normalize_bytes(data: bytes | bytearray | memoryview | str) -> bytes:
        if isinstance(data, str):
            return data.encode("utf-8")
        return bytes(data)

    def status(self) -> CudaNativeStatus:
        if self._status is not None:
            return self._status

        if self._lib is None:
            self._status = CudaNativeStatus(
                available=False,
                library_path=self._library_path,
                error=self._load_error or "CUDA library not loaded",
            )
            return self._status

        try:
            count = ctypes.c_int(0)
            self._check_rc(self._lib.aura_cuda_device_count(ctypes.byref(count)))
            device_name = None
            if count.value > 0:
                buffer = ctypes.create_string_buffer(256)
                self._check_rc(self._lib.aura_cuda_get_device_name(0, buffer, len(buffer)))
                device_name = buffer.value.decode("utf-8", errors="replace")
            self._status = CudaNativeStatus(
                available=count.value > 0,
                library_path=self._library_path,
                device_count=count.value,
                device_name=device_name,
            )
        except CudaNativeError as exc:
            self._status = CudaNativeStatus(
                available=False,
                library_path=self._library_path,
                error=str(exc),
            )
        return self._status

    def is_available(self) -> bool:
        return self.status().available

    def byte_histogram(self, data: bytes | bytearray | memoryview | str) -> list[int]:
        payload = self._normalize_bytes(data)
        histogram = (ctypes.c_uint32 * 256)()
        if not payload:
            return [0] * 256

        if self._lib is None:
            raise CudaNativeError(self._last_error())

        buffer = self._as_u8_buffer(payload)
        self._check_rc(self._lib.aura_cuda_histogram_u8(buffer, len(payload), histogram))
        return [int(histogram[index]) for index in range(256)]

    def shannon_entropy(self, data: bytes | bytearray | memoryview | str) -> float:
        payload = self._normalize_bytes(data)
        if not payload:
            return 0.0

        if self._lib is None:
            raise CudaNativeError(self._last_error())

        buffer = self._as_u8_buffer(payload)
        entropy = ctypes.c_double(0.0)
        self._check_rc(
            self._lib.aura_cuda_shannon_entropy_u8(buffer, len(payload), ctypes.byref(entropy))
        )
        return float(entropy.value)

    def rolling_hash3(self, data: bytes | bytearray | memoryview | str) -> list[int]:
        """Return FNV-1a hashes for every 3-byte window in ``data``."""

        payload = self._normalize_bytes(data)
        hash_count = max(len(payload) - 2, 0)
        if hash_count == 0:
            return []

        if self._lib is None:
            raise CudaNativeError(self._last_error())

        buffer = self._as_u8_buffer(payload)
        hashes = (ctypes.c_uint32 * hash_count)()
        self._check_rc(self._lib.aura_cuda_rolling_hash3_u8(buffer, len(payload), hashes))
        return [int(hashes[index]) for index in range(hash_count)]

    def lz_match_candidates(
        self,
        data: bytes | bytearray | memoryview | str,
        *,
        window_size: int = 32768,
        min_match: int = 4,
        max_match: int = 255,
    ) -> list[tuple[int, int]]:
        """Return ``(distance, length)`` match candidates for each byte offset.

        Candidate lengths are capped at the distance so they remain compatible
        with BRIO's current non-overlapping match decoder.
        """

        payload = self._normalize_bytes(data)
        if not payload:
            return []

        if window_size <= 0 or min_match <= 0 or max_match < min_match:
            raise ValueError("invalid LZ match candidate parameters")
        max_match = min(int(max_match), 255)

        if self._lib is None:
            raise CudaNativeError(self._last_error())

        buffer = self._as_u8_buffer(payload)
        distances = (ctypes.c_uint32 * len(payload))()
        lengths = (ctypes.c_uint8 * len(payload))()
        self._check_rc(
            self._lib.aura_cuda_lz_match_candidates_u8(
                buffer,
                len(payload),
                int(window_size),
                int(min_match),
                int(max_match),
                distances,
                lengths,
            )
        )
        return [(int(distances[index]), int(lengths[index])) for index in range(len(payload))]


def cpu_shannon_entropy(data: bytes | bytearray | memoryview | str) -> float:
    """Reference byte entropy implementation used for tests and fallback checks."""

    if isinstance(data, str):
        payload = data.encode("utf-8")
    else:
        payload = bytes(data)

    if not payload:
        return 0.0

    counts = [0] * 256
    for byte in payload:
        counts[byte] += 1

    entropy = 0.0
    size = len(payload)
    for count in counts:
        if count:
            probability = count / size
            entropy -= probability * math.log2(probability)
    return entropy


def cpu_rolling_hash3(data: bytes | bytearray | memoryview | str) -> list[int]:
    """Reference implementation for ``CudaNativeBackend.rolling_hash3``."""

    payload = data.encode("utf-8") if isinstance(data, str) else bytes(data)
    hashes: list[int] = []
    for index in range(max(len(payload) - 2, 0)):
        value = 2166136261
        value = ((value ^ payload[index]) * 16777619) & 0xFFFFFFFF
        value = ((value ^ payload[index + 1]) * 16777619) & 0xFFFFFFFF
        value = ((value ^ payload[index + 2]) * 16777619) & 0xFFFFFFFF
        hashes.append(value)
    return hashes


def cpu_lz_match_candidates(
    data: bytes | bytearray | memoryview | str,
    *,
    window_size: int = 32768,
    min_match: int = 4,
    max_match: int = 255,
) -> list[tuple[int, int]]:
    """Reference implementation for ``CudaNativeBackend.lz_match_candidates``."""

    payload = data.encode("utf-8") if isinstance(data, str) else bytes(data)
    if window_size <= 0 or min_match <= 0 or max_match < min_match:
        raise ValueError("invalid LZ match candidate parameters")
    max_match = min(int(max_match), 255)

    candidates: list[tuple[int, int]] = []
    for pos in range(len(payload)):
        allowed = min(max_match, len(payload) - pos)
        best_distance = 0
        best_length = 0

        if allowed >= min_match:
            lookback = min(pos, window_size)
            for distance in range(1, lookback + 1):
                candidate_limit = min(allowed, distance)
                if candidate_limit < min_match:
                    continue

                candidate = pos - distance
                length = 0
                while (
                    length < candidate_limit
                    and payload[candidate + length] == payload[pos + length]
                ):
                    length += 1

                if length >= min_match and length > best_length:
                    best_distance = distance
                    best_length = length
                    if best_length == allowed:
                        break

        candidates.append((best_distance, best_length))
    return candidates
