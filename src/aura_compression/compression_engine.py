#!/usr/bin/env python3
"""
Compression Engine - Core compression and decompression logic
Extracted from the monolithic ProductionHybridCompressor
"""
import os
import re
import struct
from pathlib import Path
import json
from typing import Dict, List, Tuple, Optional, Any
from enum import Enum
from datetime import datetime
from collections import Counter

from aura_compression.enums import (
    CompressionMethod,
    TEMPLATE_METADATA_KIND,
    _SEMANTIC_PREVIEW_LIMIT,
    _SEMANTIC_TOKEN_LIMIT,
    _SEMANTIC_TOKEN_PATTERN,
)

from aura_compression.brio_full import (
    BrioEncoder,
    BrioDecoder,
    BrioCompressed,
    BrioDecompressed,
)
from aura_compression.brio_full.tokens import (
    LiteralToken as AuraLiteralToken,
    DictionaryToken as AuraDictionaryToken,
    MatchToken as AuraMatchToken,
    TemplateToken as AuraTemplateToken,
)
# TCP-optimized BRIO for small messages (using enhanced brio_full)
from aura_compression.brio_full import (
    BrioEncoder as TcpBrioEncoder,
    BrioDecoder as TcpBrioDecoder,
    BrioCompressed as TcpBrioCompressed,
)
from aura_compression.brio_full.tokens import (
    LiteralToken as TcpLiteralToken,
    MatchToken as TcpMatchToken,
    TemplateToken as TcpTemplateToken,
    MetadataEntry as TcpMetadataEntry,
    Token as TcpToken,
)
from aura_compression.auralite import (
    AuraLiteEncoder,
    AuraLiteDecoder,
    AuraLiteEncoded,
)
from aura_compression.templates import TemplateMatch
from aura_compression.ai_large_file import AILargeFileCompressor


class CompressionEngine:
    """
    Core compression and decompression engine
    Handles the actual compression/decompression logic
    """

    def __init__(self,
                 template_library: Any,
                 aura_encoder: Optional[BrioEncoder] = None,
                 aura_decoder: Optional[BrioDecoder] = None,
                 tcp_brio_encoder: Optional[TcpBrioEncoder] = None,
                 tcp_brio_decoder: Optional[TcpBrioDecoder] = None,
                 auralite_encoder: Optional[AuraLiteEncoder] = None,
                 auralite_decoder: Optional[AuraLiteDecoder] = None,
                 tcp_brio_threshold: int = 1000,
                 ai_semantic_compressor: Optional[AILargeFileCompressor] = None):
        """
        Initialize compression engine with encoders/decoders
        """
        self.template_library = template_library
        self.tcp_brio_threshold = tcp_brio_threshold

        # BRIO encoders/decoders
        self._aura_encoder = aura_encoder
        self._aura_decoder = aura_decoder
        self._tcp_brio_encoder = tcp_brio_encoder
        self._tcp_brio_decoder = tcp_brio_decoder

        # Auralite encoders/decoders
        self._auralite_encoder = auralite_encoder or AuraLiteEncoder(template_library=template_library)
        self._auralite_decoder = auralite_decoder or AuraLiteDecoder(template_library=template_library)

        # AI Semantic compressor
        self._ai_semantic_compressor = ai_semantic_compressor or AILargeFileCompressor()

    def compress_binary_semantic(self, text: str, template_match: TemplateMatch) -> Tuple[bytes, dict]:
        """Compress using binary semantic compression"""
        template_id = template_match.template_id
        slots = template_match.slots

        # Get template
        entry = self.template_library.get_entry(template_id)
        if entry is None:
            raise ValueError(f"Unknown template ID: {template_id}")

        # Validate slots
        if entry.slot_count != len(slots):
            raise ValueError(
                f"Template {template_id} expects {entry.slot_count} slots, got {len(slots)}"
            )

        # Reconstruct and verify
        reconstructed = self.template_library.format_template(template_id, slots)
        if reconstructed != text:
            raise ValueError("Template slots do not reproduce original text")

        # Create compressed format
        # Format: [method_byte][template_id][slot_count][slot_lengths][slot_data]
        method_byte = CompressionMethod.BINARY_SEMANTIC.value

        # Encode template_id as 2 bytes
        template_bytes = struct.pack(">H", template_id)

        # Encode slot count as 1 byte
        slot_count_byte = bytes([len(slots)])

        # Encode slot data
        slot_data = []
        slot_lengths = []
        for slot in slots:
            slot_bytes = slot.encode('utf-8')
            slot_lengths.append(len(slot_bytes))
            slot_data.append(slot_bytes)

        # Pack slot lengths
        slot_lengths_bytes = b''.join(struct.pack(">H", length) for length in slot_lengths)

        # Combine all slot data
        slots_bytes = b''.join(slot_data)

        # Create final compressed data
        compressed = (
            bytes([method_byte]) +
            template_bytes +
            slot_count_byte +
            slot_lengths_bytes +
            slots_bytes
        )

        metadata = {
            'original_size': len(text.encode('utf-8')),
            'compressed_size': len(compressed),
            'ratio': len(text.encode('utf-8')) / len(compressed),
            'method': CompressionMethod.BINARY_SEMANTIC.name.lower(),
            'template_id': template_id,
            'slot_count': len(slots),
        }

        return compressed, metadata

    def decompress_binary_semantic(self, data: bytes) -> Tuple[str, dict]:
        """Decompress binary semantic compression"""
        if len(data) < 4:  # Minimum: method + template_id + slot_count
            raise ValueError("Invalid binary semantic data: too short")

        # Skip method byte (already validated)
        view = memoryview(data)[1:]

        # Read template_id (2 bytes)
        template_id = struct.unpack(">H", view[:2].tobytes())[0]
        view = view[2:]

        # Read slot count (1 byte)
        slot_count = view[0]
        view = view[1:]

        # Read slot lengths (2 bytes each)
        if len(view) < slot_count * 2:
            raise ValueError("Invalid binary semantic data: truncated slot lengths")
        slot_lengths = []
        for i in range(slot_count):
            length = struct.unpack(">H", view[i*2:(i+1)*2].tobytes())[0]
            slot_lengths.append(length)
        view = view[slot_count * 2:]

        # Read slot data
        slots = []
        for length in slot_lengths:
            if len(view) < length:
                raise ValueError("Invalid binary semantic data: truncated slot data")
            slot_bytes = view[:length].tobytes()
            slot_text = slot_bytes.decode('utf-8')
            slots.append(slot_text)
            view = view[length:]

        # Reconstruct text
        text = self.template_library.format_template(template_id, slots)

        metadata = {
            'method': CompressionMethod.BINARY_SEMANTIC.name.lower(),
            'template_id': template_id,
            'slot_count': len(slots),
        }

        return text, metadata

    def compress_auralite(self, text: str) -> Tuple[bytes, dict]:
        """Compress using Auralite"""
        compressed = self._auralite_encoder.encode(text)
        compressed_bytes = compressed.payload

        metadata = {
            'original_size': len(text.encode('utf-8')),
            'compressed_size': len(compressed_bytes),
            'ratio': len(text.encode('utf-8')) / len(compressed_bytes),
            'method': CompressionMethod.AURALITE.name.lower(),
        }

        return compressed_bytes, metadata

    def decompress_auralite(self, data: bytes) -> Tuple[str, dict]:
        """Decompress Auralite"""
        if len(data) < 1:
            raise ValueError("Invalid Auralite data: no method byte")

        # Skip method byte
        payload = data[1:]
        decoded = self._auralite_decoder.decode(payload)
        text = decoded.text

        metadata = {
            'method': CompressionMethod.AURALITE.name.lower(),
        }

        return text, metadata

    def compress_brio(self, text: str, use_tcp: bool = True) -> Tuple[bytes, dict]:
        """Compress using BRIO (TCP-optimized or full)"""
        original_size = len(text.encode('utf-8'))

        if use_tcp and original_size < self.tcp_brio_threshold:
            # Use TCP-optimized BRIO
            compressed = self._tcp_brio_encoder.compress(text)
            compressed_bytes = compressed.to_bytes()
            method = CompressionMethod.BRIO.name.lower()
        else:
            # Use full BRIO
            compressed = self._aura_encoder.compress(text)
            compressed_bytes = compressed.to_bytes()
            method = CompressionMethod.BRIO.name.lower()

        metadata = {
            'original_size': original_size,
            'compressed_size': len(compressed_bytes),
            'ratio': original_size / len(compressed_bytes),
            'method': method,
            'tcp_optimized': use_tcp and original_size < self.tcp_brio_threshold,
        }

        return compressed_bytes, metadata

    def decompress_brio(self, data: bytes) -> Tuple[str, dict]:
        """Decompress BRIO (TCP-optimized or full)"""
        if len(data) < 1:
            raise ValueError("Invalid BRIO data: no method byte")

        # Skip method byte
        payload = data[1:]
        try:
            # Try TCP-optimized first
            compressed = TcpBrioCompressed.from_bytes(payload)
            text = self._tcp_brio_decoder.decompress(compressed)
            tcp_optimized = True
        except (ValueError, struct.error, AttributeError):
            # Fall back to full BRIO
            compressed = BrioCompressed.from_bytes(payload)
            text = self._aura_decoder.decompress(compressed)
            tcp_optimized = False

        metadata = {
            'method': CompressionMethod.BRIO.name.lower(),
            'tcp_optimized': tcp_optimized,
        }

        return text, metadata

    def compress_ai_semantic(self, text: str) -> Tuple[bytes, dict]:
        """Compress using AI-powered semantic compression for large files"""
        compressed, stats = self._ai_semantic_compressor.compress(text)

        metadata = {
            'original_size': stats.original_size,
            'compressed_size': stats.compressed_size,
            'ratio': stats.ratio,
            'method': CompressionMethod.AI_SEMANTIC.name.lower(),
            'patterns_found': stats.patterns_found,
            'dictionary_size': stats.dictionary_size,
            'semantic_chunks': stats.semantic_chunks,
            'ai_optimizations': stats.ai_optimizations,
        }

        return compressed, metadata

    def decompress_ai_semantic(self, data: bytes) -> Tuple[str, dict]:
        """Decompress AI-powered semantic compression"""
        if len(data) < 1:
            raise ValueError("Invalid AI semantic data: no method byte")

        # Skip method byte
        payload = data[1:]
        text = self._ai_semantic_compressor.decompress(payload)

        metadata = {
            'method': CompressionMethod.AI_SEMANTIC.name.lower(),
        }

        return text, metadata

    def compress_uncompressed(self, text: str) -> Tuple[bytes, dict]:
        """Return uncompressed data with method marker"""
        text_bytes = text.encode('utf-8')
        compressed = bytes([CompressionMethod.UNCOMPRESSED.value]) + text_bytes

        compressed_size = len(compressed)
        effective_size = max(compressed_size - 1, 1)
        metadata = {
            'original_size': len(text_bytes),
            'compressed_size': compressed_size,
            'ratio': len(text_bytes) / effective_size,
            'ratio_actual': len(text_bytes) / compressed_size if compressed_size else 1.0,
            'method': CompressionMethod.UNCOMPRESSED.name.lower(),
        }

        return compressed, metadata

    def decompress_uncompressed(self, data: bytes) -> Tuple[str, dict]:
        """Decompress uncompressed data"""
        if len(data) < 1:
            raise ValueError("Invalid uncompressed data: no method byte")

        # Skip method byte
        text_bytes = data[1:]
        text = text_bytes.decode('utf-8')

        metadata = {
            'method': CompressionMethod.UNCOMPRESSED.name.lower(),
        }

        return text, metadata

    def get_compression_method(self, data: bytes) -> CompressionMethod:
        """Extract compression method from compressed data"""
        if len(data) == 0:
            raise ValueError("Empty data")

        method_byte = data[0]
        if method_byte == 0x03:
            # Legacy Aura_Lite payloads are treated as Auralite
            return CompressionMethod.AURALITE
        try:
            return CompressionMethod(method_byte)
        except ValueError:
            raise ValueError(f"Unknown compression method: {method_byte}")

    def decompress(self, data: bytes) -> Tuple[str, dict]:
        """Main decompression method"""
        method = self.get_compression_method(data)

        if method == CompressionMethod.BINARY_SEMANTIC:
            return self.decompress_binary_semantic(data)
        elif method == CompressionMethod.AURALITE:
            return self.decompress_auralite(data)
        elif method == CompressionMethod.BRIO:
            return self.decompress_brio(data)
        elif method == CompressionMethod.AI_SEMANTIC:
            return self.decompress_ai_semantic(data)
        elif method == CompressionMethod.UNCOMPRESSED:
            return self.decompress_uncompressed(data)
        else:
            raise ValueError(f"Unsupported compression method: {method}")