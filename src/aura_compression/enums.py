#!/usr/bin/env python3
"""
Compression enums and constants
"""
import re
from enum import Enum


class CompressionMethod(Enum):
    BINARY_SEMANTIC = 0x00
    AURALITE = 0x01  # AuraLite implementation (primary)
    BRIO = 0x02      # BRIO compression
    AURA_HEAVY = 0x04  # High-compression AURA with rANS
    PATTERN_SEMANTIC = 0x20  # Pattern-based semantic compression for large files (regex + dictionary + zlib)
    UNCOMPRESSED = 0xFF


TEMPLATE_METADATA_KIND = 0x01

_SEMANTIC_PREVIEW_LIMIT = 160
_SEMANTIC_TOKEN_LIMIT = 5
_SEMANTIC_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_]+")