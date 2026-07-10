"""Shared AIWire exceptions and immutable runtime result types."""

from __future__ import annotations

from dataclasses import dataclass


class AIWireNativeError(RuntimeError):
    """Raised when the native C++ AIWire backend reports an error."""


class AIWireFrameError(ValueError):
    """Raised when an AIWire data frame cannot be safely decoded."""


class AIWireFallbackError(ValueError):
    """Raised when an AIWire negotiated fallback frame is invalid."""


class AIWireHandshakeError(ValueError):
    """Raised when an AIWire protocol handshake cannot be negotiated."""


@dataclass(frozen=True)
class AIWireNativeStatus:
    """Runtime status for the optional native AIWire backend."""

    available: bool
    library_path: str | None
    version: str | None = None
    error: str | None = None
    dictionary_size: int | None = None
    dictionary_checksum: str | None = None
    dictionary_matches_python: bool | None = None
    supports_custom_dictionary: bool = False
    supports_token_codec: bool = False
    supports_token_aiwire: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "available": self.available,
            "library_path": self.library_path,
            "version": self.version,
            "error": self.error,
            "dictionary_size": self.dictionary_size,
            "dictionary_checksum": self.dictionary_checksum,
            "dictionary_matches_python": self.dictionary_matches_python,
            "supports_custom_dictionary": self.supports_custom_dictionary,
            "supports_token_codec": self.supports_token_codec,
            "supports_token_aiwire": self.supports_token_aiwire,
        }


@dataclass(frozen=True)
class AIWireStats:
    """Simple byte/frame counters for one wire-codec session."""

    frames: int
    bytes_in: int
    bytes_out: int

    @property
    def ratio(self) -> float:
        return self.bytes_in / self.bytes_out if self.bytes_out else 0.0

    @property
    def average_bytes_in(self) -> float:
        return self.bytes_in / self.frames if self.frames else 0.0

    @property
    def average_bytes_out(self) -> float:
        return self.bytes_out / self.frames if self.frames else 0.0

    def as_dict(self) -> dict[str, int | float]:
        """Return the stable benchmark serialization for AIWire counters."""

        return {
            "frames": self.frames,
            "bytes_in": self.bytes_in,
            "bytes_out": self.bytes_out,
            "ratio": self.ratio,
            "average_bytes_in": self.average_bytes_in,
            "average_bytes_out": self.average_bytes_out,
        }
