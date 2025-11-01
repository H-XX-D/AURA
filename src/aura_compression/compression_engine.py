#!/usr/bin/env python3
"""
Compression Engine - Core compression and decompression logic
Extracted from the monolithic ProductionHybridCompressor
"""
import os
import re
import struct
import logging
from pathlib import Path
import json
from typing import Dict, List, Tuple, Optional, Any
from enum import Enum
from datetime import datetime
from collections import Counter

logger = logging.getLogger(__name__)

from aura_compression.enums import (
    CompressionMethod,
    TEMPLATE_METADATA_KIND,
    _SEMANTIC_PREVIEW_LIMIT,
    _SEMANTIC_TOKEN_LIMIT,
    _SEMANTIC_TOKEN_PATTERN,
)

from aura_compression.brio_full import BrioEncoder, BrioDecoder, BrioDecompressed
from aura_compression.brio_full.tokens import (
    LiteralToken as AuraLiteralToken,
    DictionaryToken as AuraDictionaryToken,
    MatchToken as AuraMatchToken,
    TemplateToken as AuraTemplateToken,
)
# TCP-optimized BRIO for small messages (using enhanced brio_full)
from aura_compression.brio_full import BrioEncoder as TcpBrioEncoder, BrioDecoder as TcpBrioDecoder
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
from aura_compression.pattern_semantic_large_file import PatternSemanticCompressor


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
                 pattern_semantic_compressor: Optional[PatternSemanticCompressor] = None,
                 cache_dir: str = ".aura_cache",
                 enable_sql_cache: bool = True):
        """
        Initialize compression engine with encoders/decoders and SQL-backed caching
        
        Args:
            template_library: Template library instance
            aura_encoder: BRIO encoder (auto-created if None)
            aura_decoder: BRIO decoder (auto-created if None)
            tcp_brio_encoder: TCP BRIO encoder (auto-created if None)
            tcp_brio_decoder: TCP BRIO decoder (auto-created if None)
            auralite_encoder: AuraLite encoder (auto-created if None)
            auralite_decoder: AuraLite decoder (auto-created if None)
            tcp_brio_threshold: Size threshold for TCP optimization
            pattern_semantic_compressor: AI semantic compressor (auto-created if None)
            cache_dir: Directory for SQL cache and pattern discovery
            enable_sql_cache: Enable SQL-backed persistent caching (default: True)
        """
        self.template_library = template_library
        self.tcp_brio_threshold = tcp_brio_threshold
        self.cache_dir = cache_dir
        self.enable_sql_cache = enable_sql_cache

        # Initialize SQL-backed persistent cache for pattern discovery
        from aura_compression.persistent_cache import PersistentTemplateCache
        self._persistent_cache = None
        if enable_sql_cache:
            try:
                self._persistent_cache = PersistentTemplateCache(
                    cache_dir=cache_dir,
                    max_size=10000,  # Large cache for aggressive performance
                    save_interval=30.0,  # Frequent saves for data persistence
                    compression_enabled=True  # Compress cache data
                )
                logger.info(f"SQL-backed persistent cache enabled in {cache_dir}")
            except Exception as e:
                logger.warning(f"Failed to initialize SQL cache: {e}, continuing without cache")
                self._persistent_cache = None

        # BRIO encoders/decoders - Create by default if not provided
        self._aura_encoder = aura_encoder or BrioEncoder()
        self._aura_decoder = aura_decoder or BrioDecoder()
        self._tcp_brio_encoder = tcp_brio_encoder or TcpBrioEncoder()
        self._tcp_brio_decoder = tcp_brio_decoder or TcpBrioDecoder()

        # Auralite encoders/decoders - Always created
        self._auralite_encoder = auralite_encoder or AuraLiteEncoder(template_library=template_library)
        self._auralite_decoder = auralite_decoder or AuraLiteDecoder(template_library=template_library)

        # AI Semantic compressor - Always created
        self._pattern_semantic_compressor = pattern_semantic_compressor or PatternSemanticCompressor()

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

    def _extract_template_usage(self, tokens: List[Any]) -> Tuple[List[int], List[Dict[str, Any]]]:
        """Collect template usage information from BRIO token streams."""
        template_ids: List[int] = []
        template_details: List[Dict[str, Any]] = []
        template_token_types = (AuraTemplateToken, TcpTemplateToken)

        for token in tokens:
            if isinstance(token, template_token_types):
                template_ids.append(token.template_id)
                template_details.append(
                    {
                        'template_id': token.template_id,
                        'slot_count': len(token.slots),
                    }
                )
        return template_ids, template_details

    def compress_brio(self, text: str, use_tcp: bool = True) -> Tuple[bytes, dict]:
        """Compress using BRIO (TCP-optimized or full)"""
        original_size = len(text.encode('utf-8'))

        if use_tcp and original_size < self.tcp_brio_threshold:
            # Use TCP-optimized BRIO
            if self._tcp_brio_encoder is None:
                raise ValueError("TCP BRIO encoder is not available")
            compressed = self._tcp_brio_encoder.compress(text)
            compressed_bytes = compressed.payload
            method = CompressionMethod.BRIO.name.lower()
        else:
            # Use full BRIO
            if self._aura_encoder is None:
                raise ValueError("BRIO encoder is not available")
            compressed = self._aura_encoder.compress(text)
            compressed_bytes = compressed.payload
            method = CompressionMethod.BRIO.name.lower()

        template_ids, template_details = self._extract_template_usage(getattr(compressed, "tokens", []))

        metadata = {
            'original_size': original_size,
            'compressed_size': len(compressed_bytes),
            'ratio': original_size / len(compressed_bytes),
            'method': method,
            'tcp_optimized': use_tcp and original_size < self.tcp_brio_threshold,
        }
        if template_ids:
            metadata['template_ids'] = template_ids
            metadata['template_usage'] = template_details

        return compressed_bytes, metadata

    def decompress_brio(self, data: bytes) -> Tuple[str, dict]:
        """Decompress BRIO (TCP-optimized or full)"""
        if len(data) < 1:
            raise ValueError("Invalid BRIO data: no method byte")

        # Skip method byte
        payload = data[1:]

        result: Optional[BrioDecompressed] = None
        tcp_optimized = False

        if self._tcp_brio_decoder is not None:
            try:
                result = self._tcp_brio_decoder.decompress(payload)
                tcp_optimized = True
            except (ValueError, RuntimeError):
                result = None

        if result is None:
            if self._aura_decoder is None:
                raise ValueError("BRIO decoder is not available")
            result = self._aura_decoder.decompress(payload)
            tcp_optimized = False

        text = result.text
        template_ids, template_details = self._extract_template_usage(getattr(result, "tokens", []))

        metadata = {
            'method': CompressionMethod.BRIO.name.lower(),
            'tcp_optimized': tcp_optimized,
        }
        if template_ids:
            metadata['template_ids'] = template_ids
            metadata['template_usage'] = template_details

        return text, metadata

    def compress_pattern_semantic(self, text: str) -> Tuple[bytes, dict]:
        """Compress using AI-powered semantic compression for large files"""
        compressed, stats = self._pattern_semantic_compressor.compress(text)

        metadata = {
            'original_size': stats.original_size,
            'compressed_size': stats.compressed_size,
            'ratio': stats.ratio,
            'method': CompressionMethod.PATTERN_SEMANTIC.name.lower(),
            'patterns_found': stats.patterns_found,
            'dictionary_size': stats.dictionary_size,
            'semantic_chunks': stats.semantic_chunks,
            'ai_optimizations': stats.ai_optimizations,
        }

        return compressed, metadata

    def decompress_pattern_semantic(self, data: bytes) -> Tuple[str, dict]:
        """Decompress AI-powered semantic compression"""
        if len(data) < 1:
            raise ValueError("Invalid AI semantic data: no method byte")

        # Skip method byte
        payload = data[1:]
        text = self._pattern_semantic_compressor.decompress(payload)

        metadata = {
            'method': CompressionMethod.PATTERN_SEMANTIC.name.lower(),
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
        elif method == CompressionMethod.PATTERN_SEMANTIC:
            return self.decompress_pattern_semantic(data)
        elif method == CompressionMethod.UNCOMPRESSED:
            return self.decompress_uncompressed(data)
        else:
            raise ValueError(f"Unsupported compression method: {method}")
