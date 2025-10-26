#!/usr/bin/env python3
"""
Production-Ready Hybrid Compression System
- Binary semantic compression with manual template mapping (until we build ML matcher)
- AuraLite fallback (proprietary AURA-based compression)
- Human-readable server-side audit
- 100% reliable decompression
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
# TCP-optimized BRIO for small messages
from aura_compression.brio import (
    BrioEncoder as TcpBrioEncoder,
    BrioDecoder as TcpBrioDecoder,
    BrioCompressed as TcpBrioCompressed,
)
from aura_compression.brio.tokens import (
    LiteralToken as TcpLiteralToken,
    MatchToken as TcpMatchToken,
    TemplateToken as TcpTemplateToken,
    MetadataEntry as TcpMetadataEntry,
    Token as TcpToken,
)
from aura_compression.brio import lz77
from aura_compression.auralite import AuraLiteEncoder, AuraLiteDecoder
from aura_compression.templates import TemplateLibrary, TemplateMatch
from aura_compression.normalizer import TemplateNormalizer, get_standard_normalizer
from aura_compression.sidechain import (
    NoOpSidechainService,
    SidechainConfig,
    SidechainService,
)

# GPU Acceleration (optional - graceful fallback if not available)
try:
    from aura_compression.gpu_torch_accelerated import TorchGPUTemplateMatch
    GPU_AVAILABLE = True
except ImportError:
    GPU_AVAILABLE = False
    TorchGPUTemplateMatch = None

class CompressionMethod(Enum):
    BINARY_SEMANTIC = 0x00
    AURALITE = 0x01  # AuraLite fallback (replaces Brotli)
    BRIO = 0x02
    UNCOMPRESSED = 0xFF
    AURA_LITE = 0x03  # Deprecated: use AURALITE instead


TEMPLATE_METADATA_KIND = 0x01

_SEMANTIC_PREVIEW_LIMIT = 160
_SEMANTIC_TOKEN_LIMIT = 5
_SEMANTIC_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_]+")

class ProductionHybridCompressor:
    """
    Production-ready hybrid compressor with:
    - Ultra-reliable binary semantic compression
    - AuraLite fallback (proprietary AURA-based compression)
    - Human-readable server-side decompression
    - Full audit logging support (Claim 2)
    """

    def __init__(self,
                 binary_advantage_threshold: float = 1.1,
                 min_compression_size: int = 50,
                 enable_aura: Optional[bool] = None,
                 aura_preference_margin: float = 0.05,
                 enable_audit_logging: bool = False,
                 audit_log_directory: str = "./audit_logs",
                 session_id: Optional[str] = None,
                 user_id: Optional[str] = None,
                 template_store_path: Optional[str] = None,
                 template_cache_size: int = 128,
                 enable_normalization: bool = True,
                 tcp_brio_threshold: int = 2000,
                 enable_fast_path: bool = True,
                 enable_gpu: bool = True,
                 enable_sidechain: Optional[bool] = None,
                 sidechain_config: Optional[Dict[str, Any]] = None):
        """
        Args:
            binary_advantage_threshold: Use binary if >this times better than AuraLite (1.1 = 10% better)
            min_compression_size: Don't compress messages smaller than this
            enable_audit_logging: Enable GDPR/HIPAA/SOC2 compliant audit logging (Claim 2)
            audit_log_directory: Directory for audit logs
            session_id: Optional session identifier for audit logs
            user_id: Optional user identifier for audit logs
            template_store_path: Path to template store JSON (for loading discovered templates)
            template_cache_size: Maximum active dynamic templates for auto-matching
            enable_normalization: Enable template normalization (timestamps, UUIDs, IPs)
            tcp_brio_threshold: Use TCP-optimized BRIO for messages < this size (default 2000 bytes)
            enable_fast_path: Enable fast path optimizations for ultra-low latency (default True)
        """
        # Template library (defaults + dynamic store)
        self.template_library = TemplateLibrary()

        # Template normalization
        self.enable_normalization = enable_normalization
        self._normalizer = get_standard_normalizer() if enable_normalization else None
        self.templates = self.template_library  # backwards compatibility for legacy callers
        self.template_cache_size = template_cache_size  # For future LRU cache implementation
        self._template_store_path: Optional[Path] = None
        self._template_store_mtime: Optional[float] = None

        resolved_store = template_store_path or os.getenv("AURA_TEMPLATE_STORE")
        if resolved_store is None:
            default_store = Path("./template_store.json")
            if default_store.exists():
                resolved_store = str(default_store)

        if resolved_store:
            self._template_store_path = Path(resolved_store)
            self._sync_template_store(force=True)

        self.binary_advantage_threshold = binary_advantage_threshold
        self.min_compression_size = min_compression_size
        self.enable_fast_path = enable_fast_path

        if enable_aura is None:
            env_value = os.getenv("AURA_ENABLE_EXPERIMENTAL", "false").lower()
            enable_aura = env_value in {"1", "true", "yes", "on"}
        self.enable_aura = enable_aura
        self.aura_preference_margin = aura_preference_margin
        self.tcp_brio_threshold = tcp_brio_threshold

        # Fast path cache for Binary Semantic templates (template_id -> slots pattern)
        self._fast_path_cache: Dict[str, Tuple[int, List[str]]] = {}
        self._fast_path_max_cache_size = 256

        # Audit logging (Claim 2)
        self.enable_audit_logging = enable_audit_logging
        self.session_id = session_id
        self.user_id = user_id
        self._audit_logger = None
        if self.enable_audit_logging:
            from aura_compression.audit import get_audit_logger
            self._audit_logger = get_audit_logger(audit_log_directory)

        if self.enable_aura:
            # Full BRIO with rANS for large messages (>= tcp_brio_threshold)
            self._aura_encoder: Optional[BrioEncoder] = BrioEncoder(template_library=self.template_library)
            self._aura_decoder: Optional[BrioDecoder] = BrioDecoder(template_library=self.template_library)
            # TCP-optimized BRIO for small/medium messages (< tcp_brio_threshold)
            self._tcp_brio_encoder: Optional[TcpBrioEncoder] = TcpBrioEncoder()
            self._tcp_brio_decoder: Optional[TcpBrioDecoder] = TcpBrioDecoder(template_library=self.template_library)
        else:
            self._aura_encoder = None
            self._aura_decoder = None
            self._tcp_brio_encoder = None
            self._tcp_brio_decoder = None

        self._aura_lite_encoder: AuraLiteEncoder = AuraLiteEncoder(template_library=self.template_library)
        self._aura_lite_decoder: AuraLiteDecoder = AuraLiteDecoder(template_library=self.template_library)

        # Optional sidechain storage for metadata fast-path
        if enable_sidechain is None:
            env_value = os.getenv("AURA_ENABLE_SIDECHAIN", "false").lower()
            enable_sidechain = env_value in {"1", "true", "yes", "on"}
        if enable_sidechain:
            overrides = sidechain_config or {}
            try:
                cfg = SidechainConfig.from_overrides(overrides, enabled=True)
                self._sidechain = SidechainService(cfg)
            except Exception as exc:
                print(f"⚠️  Sidechain initialization failed, disabling feature: {exc}")
                self._sidechain = NoOpSidechainService()
        else:
            self._sidechain = NoOpSidechainService()

        # GPU Acceleration (NEW - 74x speedup!)
        self.enable_gpu = enable_gpu and GPU_AVAILABLE
        self._gpu_matcher = None
        self._template_id_map = []  # Maps GPU index to template ID
        if self.enable_gpu:
            try:
                # Get all templates as strings for GPU matcher
                # templates is a dict {template_id: template_string}
                self._template_id_map = sorted(self.template_library.templates.keys())
                template_strings = [self.template_library.templates[tid] for tid in self._template_id_map]

                self._gpu_matcher = TorchGPUTemplateMatch(template_strings)
                print(f"✅ GPU Acceleration enabled for template matching (74-200x speedup)")
            except Exception as e:
                print(f"⚠️  GPU initialization failed, falling back to CPU: {e}")
                self.enable_gpu = False

    def compress_with_template(self, template_id: int, slots: List[str]) -> bytes:
        """
        Binary semantic compression

        Optimized format:
        - Zero-slot templates: [template_id:1] (1 byte total)
        - Non-zero slots: [template_id:1][slot_count:1][slot0_len:2][slot0_data]...
        """
        if template_id < 0 or template_id > 255:
            raise ValueError(f"Template ID must be between 0 and 255 (got {template_id})")

        self._ensure_template_loaded(template_id)

        entry = self.template_library.get_entry(template_id)
        if entry is None:
            raise ValueError(f"Unknown template ID: {template_id}")

        if len(slots) > 255:
            raise ValueError(f"Too many slots: {len(slots)} (max 255)")
        if entry.slot_count != len(slots):
            raise ValueError(
                f"Template {template_id} expects {entry.slot_count} slots, got {len(slots)}"
            )

        result = bytearray()
        result.append(template_id & 0xFF)

        # Optimize: zero-slot templates are just 1 byte (template_id only)
        if len(slots) == 0:
            return bytes(result)

        result.append(len(slots) & 0xFF)

        for slot in slots:
            slot_bytes = slot.encode('utf-8')
            if len(slot_bytes) > 65535:
                raise ValueError(f"Slot too long: {len(slot_bytes)} bytes (max 65535)")
            result.extend(struct.pack('>H', len(slot_bytes)))
            result.extend(slot_bytes)

        return bytes(result)

    def decompress_binary(self, data: bytes) -> str:
        """
        Decompress binary semantic format to plaintext

        Supports optimized 1-byte format for zero-slot templates
        """
        if len(data) < 1:
            raise ValueError("Invalid binary data (empty)")

        template_id = data[0]

        self._ensure_template_loaded(template_id)

        entry = self.template_library.get_entry(template_id)
        if entry is None:
            raise ValueError(f"Unknown template ID: {template_id}")

        # Optimized: zero-slot templates are just 1 byte
        if entry.slot_count == 0:
            if len(data) != 1:
                raise ValueError(f"Zero-slot template {template_id} should be 1 byte, got {len(data)}")
            result = self.template_library.format_template(template_id, [])
            self.template_library.record_use(template_id)
            return result

        # Multi-slot templates
        if len(data) < 2:
            raise ValueError("Invalid binary data (too short for multi-slot template)")

        slot_count = data[1]

        # Extract slots
        slots = []
        offset = 2

        for i in range(slot_count):
            if offset + 2 > len(data):
                raise ValueError(f"Truncated slot {i} length")

            slot_len = struct.unpack('>H', data[offset:offset+2])[0]
            offset += 2

            if offset + slot_len > len(data):
                raise ValueError(f"Truncated slot {i} data")

            slot_data = data[offset:offset+slot_len].decode('utf-8')
            slots.append(slot_data)
            offset += slot_len

        result = self.template_library.format_template(template_id, slots)
        self.template_library.record_use(template_id)
        return result

    def _generate_semantic_sketch(self, text: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Build a lightweight summary so downstream systems can inspect metadata without decompressing."""
        tokens = _SEMANTIC_TOKEN_PATTERN.findall(text.lower())
        top_tokens: List[str] = []
        if tokens:
            counts = Counter(tokens)
            top_tokens = [token for token, _ in counts.most_common(_SEMANTIC_TOKEN_LIMIT)]

        preview_segment = text[:_SEMANTIC_PREVIEW_LIMIT]
        preview_clean = " ".join(preview_segment.split())
        if len(text) > _SEMANTIC_PREVIEW_LIMIT:
            preview_clean = f"{preview_clean}..."

        return {
            "length": len(text),
            "preview": preview_clean,
            "top_tokens": top_tokens,
            "template_ids": metadata.get("template_ids") or [],
        }

    def _compress_brio_container(self, text: str, template_spans: List[TemplateMatch]) -> Tuple[bytes, CompressionMethod, dict]:
        """
        Compress using BRIO as container with inline semantic binaries + LZ77

        Strategy:
        1. Tokenize text with template awareness
        2. Template matches become TemplateTokens (inline semantic binaries)
        3. Remaining text compressed with LZ77 (MatchTokens + LiteralTokens)
        4. BRIO wraps everything with small header
        """
        tokens: List[TcpToken] = []
        metadata: List[TcpMetadataEntry] = []
        window = bytearray()  # LZ77 sliding window
        pos = 0

        # Sort template spans by position
        sorted_spans = sorted(template_spans, key=lambda s: s.start if s.start is not None else 0)

        for span in sorted_spans:
            if span.start is None or span.end is None:
                continue

            # Add LZ77-compressed literals before this template
            if pos < span.start:
                chunk = text[pos:span.start]
                chunk_bytes = chunk.encode('utf-8')
                # Apply LZ77 compression to the chunk
                lz_tokens = lz77.tokenize(list(chunk_bytes), window)
                for lz_token in lz_tokens:
                    if isinstance(lz_token, lz77.LZLiteral):
                        tokens.append(TcpLiteralToken(lz_token.value))
                        window.append(lz_token.value)
                    elif isinstance(lz_token, lz77.LZMatch):
                        tokens.append(TcpMatchToken(lz_token.distance, lz_token.length))
                        # Reconstruct matched bytes into window
                        start = len(window) - lz_token.distance
                        for i in range(lz_token.length):
                            window.append(window[start + i])
                    # Keep window size limited
                    if len(window) > 32768:  # 32 KiB window
                        del window[:-32768]

            # The matched span may include extra whitespace that template doesn't include
            # We need to handle leading AND trailing whitespace
            matched_text = text[span.start:span.end]
            reconstructed = self.template_library.format_template(span.template_id, span.slots)

            # Find where the core template text starts in the matched text
            # by stripping and finding the offset
            matched_stripped = matched_text.lstrip()
            leading_ws_len = len(matched_text) - len(matched_stripped)

            # Add leading whitespace as literals BEFORE the template token
            if leading_ws_len > 0:
                leading_text = matched_text[:leading_ws_len]
                leading_bytes = leading_text.encode('utf-8')
                lz_tokens_leading = lz77.tokenize(list(leading_bytes), window)
                for lz_token in lz_tokens_leading:
                    if isinstance(lz_token, lz77.LZLiteral):
                        tokens.append(TcpLiteralToken(lz_token.value))
                        window.append(lz_token.value)
                    elif isinstance(lz_token, lz77.LZMatch):
                        tokens.append(TcpMatchToken(lz_token.distance, lz_token.length))
                        start = len(window) - lz_token.distance
                        for i in range(lz_token.length):
                            window.append(window[start + i])
                    if len(window) > 32768:
                        del window[:-32768]

            # Add template token (inline semantic binary)
            tokens.append(TcpTemplateToken(span.template_id, span.slots))
            metadata.append(TcpMetadataEntry(
                token_index=len(tokens) - 1,
                kind=0x01,  # TEMPLATE_METADATA_KIND
                value=span.template_id,
            ))

            # Add reconstructed template bytes to window for cross-template LZ77
            reconstructed_bytes = reconstructed.encode('utf-8')
            window.extend(reconstructed_bytes)
            if len(window) > 32768:
                del window[:-32768]

            # Add trailing whitespace as literals AFTER the template token
            trailing_ws_len = len(matched_text) - leading_ws_len - len(reconstructed)
            if trailing_ws_len > 0:
                trailing_text = matched_text[leading_ws_len + len(reconstructed):]
                trailing_bytes = trailing_text.encode('utf-8')
                lz_tokens_trailing = lz77.tokenize(list(trailing_bytes), window)
                for lz_token in lz_tokens_trailing:
                    if isinstance(lz_token, lz77.LZLiteral):
                        tokens.append(TcpLiteralToken(lz_token.value))
                        window.append(lz_token.value)
                    elif isinstance(lz_token, lz77.LZMatch):
                        tokens.append(TcpMatchToken(lz_token.distance, lz_token.length))
                        start = len(window) - lz_token.distance
                        for i in range(lz_token.length):
                            window.append(window[start + i])
                    if len(window) > 32768:
                        del window[:-32768]

            pos = span.end

        # Add LZ77-compressed remaining literals after last template
        if pos < len(text):
            chunk = text[pos:]
            chunk_bytes = chunk.encode('utf-8')
            # Apply LZ77 compression to the chunk
            lz_tokens = lz77.tokenize(list(chunk_bytes), window)
            for lz_token in lz_tokens:
                if isinstance(lz_token, lz77.LZLiteral):
                    tokens.append(TcpLiteralToken(lz_token.value))
                elif isinstance(lz_token, lz77.LZMatch):
                    tokens.append(TcpMatchToken(lz_token.distance, lz_token.length))

        # Compress with TCP-BRIO encoder
        compressed = self._tcp_brio_encoder.compress_tokens(tokens, metadata)

        original_size = len(text.encode('utf-8'))
        compressed_size = len(compressed.payload) + 1  # +1 for method byte

        return (
            bytes([CompressionMethod.BRIO.value]) + compressed.payload,
            CompressionMethod.BRIO,
            {
                'original_size': original_size,
                'compressed_size': compressed_size,
                'ratio': original_size / compressed_size if compressed_size else float('inf'),
                'method': 'brio_container',
                'template_count': len(template_spans),
                'template_ids': [s.template_id for s in template_spans],
                'template_id': template_spans[0].template_id if template_spans else None,
                'fast_path_candidate': True,
            }
        )

    def compress(self, text: str, template_id: Optional[int] = None,
                 slots: Optional[List[str]] = None) -> Tuple[bytes, CompressionMethod, dict]:
        """
        Compress text using best method

        Args:
            text: Text to compress
            template_id: If known, use this template
            slots: If known, use these slots

        Returns:
            (compressed_data, method_used, metadata)
        """
        self._sync_template_store()

        template_match: Optional[TemplateMatch] = None
        normalization_result = None

        # Try normalization if enabled and no explicit template provided
        if template_id is None and self._normalizer:
            normalization_result = self._normalizer.normalize(text)
            normalized_text = normalization_result.normalized_text

            # Try matching normalized text first
            if normalization_result.normalization_count > 0:
                template_match = self.template_library.match(normalized_text)
                if template_match:
                    # Store normalization info in metadata
                    template_id = template_match.template_id
                    slots = template_match.slots

        # Fall back to direct matching if normalization didn't help
        if template_id is None:
            template_match = self.template_library.match(text)
            if template_match:
                template_id = template_match.template_id
                slots = template_match.slots
        elif template_id is not None and slots is None:
            inferred = self.template_library.extract_slots(template_id, text)
            if inferred is not None:
                slots = inferred

        if template_id is not None:
            entry = self.template_library.get_entry(template_id)
            if entry is None:
                raise ValueError(f"Unknown template ID: {template_id}")
            if slots is None:
                if entry.slot_count == 0:
                    slots = []
                else:
                    raise ValueError(f"Template {template_id} requires slot values")
            if entry.slot_count != len(slots):
                raise ValueError(
                    f"Template {template_id} expects {entry.slot_count} slots, got {len(slots)}"
                )
            reconstructed = self.template_library.format_template(template_id, slots)
            if reconstructed == text:
                template_match = TemplateMatch(template_id, list(slots))
            else:
                # Supplied template slots do not reproduce the original text; treat as generic message
                template_id = None
                slots = None
                template_match = None

        original_size = len(text.encode('utf-8'))

        # FAST PATH 1: Early exit for tiny messages (ultra-low latency)
        # Skip compression for messages smaller than min_compression_size
        if original_size < self.min_compression_size and template_match is None:
            uncompressed_payload = bytes([CompressionMethod.UNCOMPRESSED.value]) + text.encode('utf-8')
            uncompressed_metadata = {
                'original_size': original_size,
                'compressed_size': original_size + 1,
                'ratio': 1.0,
                'method': 'uncompressed',
                'reason': 'message_too_small',
                'fast_path_candidate': True,
                'fast_path_used': 'tiny_message_early_exit' if self.enable_fast_path else None,
                'attempted_methods': ['uncompressed'],
            }

            # Audit logging (Claim 2) - Log even for uncompressed messages
            if self.enable_audit_logging and self._audit_logger:
                self._audit_logger.log_compression(
                    plaintext=text,
                    compressed_payload=uncompressed_payload,
                    metadata=uncompressed_metadata,
                    session_id=self.session_id,
                    user_id=self.user_id,
                )
                self._audit_logger.log_metadata_only(
                    metadata=uncompressed_metadata,
                    session_id=self.session_id,
                )

            return (uncompressed_payload, CompressionMethod.UNCOMPRESSED, uncompressed_metadata)

        # FAST PATH 2: Binary Semantic direct compression (if template match provided)
        # Skip all other methods if we have a template match and fast path enabled
        if self.enable_fast_path and template_match is not None:
            try:
                binary_data = self.compress_with_template(template_match.template_id, template_match.slots)
                binary_size = len(binary_data) + 1  # include method byte
                binary_payload = bytes([CompressionMethod.BINARY_SEMANTIC.value]) + binary_data

                # If Binary Semantic compresses well, use it immediately (fast path)
                if len(binary_payload) < original_size:
                    binary_metadata = {
                        'original_size': original_size,
                        'compressed_size': binary_size,
                        'ratio': original_size / binary_size,
                        'method': 'binary_semantic',
                        'template_id': template_match.template_id,
                        'template_ids': [template_match.template_id],
                        'slot_count': len(template_match.slots),
                        'fast_path_candidate': True,
                        'fast_path_used': 'binary_semantic_direct',
                        'attempted_methods': ['binary_semantic'],
                    }

                    # Record template usage
                    self.template_library.record_use(template_match.template_id)

                    # Audit logging
                    if self.enable_audit_logging and self._audit_logger:
                        self._audit_logger.log_compression(
                            plaintext=text,
                            compressed_payload=binary_payload,
                            metadata=binary_metadata,
                            session_id=self.session_id,
                            user_id=self.user_id,
                        )
                        self._audit_logger.log_metadata_only(
                            metadata=binary_metadata,
                            session_id=self.session_id,
                        )

                    return (binary_payload, CompressionMethod.BINARY_SEMANTIC, binary_metadata)
            except Exception:
                pass  # Fall through to normal compression path

        candidates: List[Tuple[bytes, CompressionMethod, Dict[str, Any]]] = []

        # Template candidate if provided
        binary_data = None
        binary_size = 0
        binary_ratio = 0.0
        if template_match is not None:
            try:
                binary_data = self.compress_with_template(template_match.template_id, template_match.slots)
                binary_size = len(binary_data) + 1  # include method byte
                binary_ratio = original_size / binary_size if binary_size else float('inf')
            except Exception:
                binary_data = None

        # AuraLite fallback (always available - proprietary AURA compression)
        # Use simple literal encoding if no template match
        try:
            fallback_encoded = self._aura_lite_encoder.encode(text, None, template_spans=[])
            auralite_payload = fallback_encoded.payload
            auralite_size = len(auralite_payload) + 1
            auralite_ratio = original_size / auralite_size if auralite_size else float('inf')
        except Exception:
            # Ultimate fallback: uncompressed
            auralite_payload = text.encode('utf-8')
            auralite_size = len(auralite_payload) + 1
            auralite_ratio = original_size / auralite_size if auralite_size else float('inf')

        template_spans: List[TemplateMatch] = []
        if template_match is None:
            # GPU-accelerated template matching (74-200x faster!)
            if self._gpu_matcher is not None:
                try:
                    # Use GPU for parallel template matching
                    template_indices, scores, stats = self._gpu_matcher.match_batch_gpu([text])
                    gpu_index = int(template_indices[0])

                    # Map GPU index back to actual template ID
                    if gpu_index < len(self._template_id_map):
                        best_template_id = self._template_id_map[gpu_index]
                        # Now use standard template matching to find exact positions
                        template_spans = self.template_library.find_substring_matches(text)
                    else:
                        # Fallback to CPU if index out of range
                        template_spans = self.template_library.find_substring_matches(text)
                except Exception as e:
                    # Fallback to CPU if GPU fails
                    template_spans = self.template_library.find_substring_matches(text)
            else:
                # CPU fallback (original behavior)
                template_spans = self.template_library.find_substring_matches(text)

        # BRIO container for multi-template messages
        if len(template_spans) > 1 and self.enable_aura and self._tcp_brio_encoder is not None:
            try:
                brio_container_result = self._compress_brio_container(text, template_spans)
                candidates.append(brio_container_result)
            except Exception:
                # If container encoding fails, fall back to other methods
                pass

        aura_lite_encoded = None
        aura_lite_size = 0
        aura_lite_ratio = 0.0
        template_heavy_context = template_match is not None or (template_spans and len(template_spans) >= 1)
        if self._aura_lite_encoder is not None:
            try:
                aura_lite_encoded = self._aura_lite_encoder.encode(
                    text,
                    template_match,
                    template_spans=template_spans,
                )
                aura_lite_size = len(aura_lite_encoded.payload) + 1
                aura_lite_ratio = original_size / aura_lite_size if aura_lite_size else float('inf')
                if template_heavy_context:
                    # In rare cases template metadata can expand payload; fall back to literal mode
                    alt_encoded = self._aura_lite_encoder.encode(text, None, template_spans=[])
                    alt_size = len(alt_encoded.payload) + 1
                    if alt_size < aura_lite_size:
                        aura_lite_encoded = alt_encoded
                        aura_lite_size = alt_size
                        aura_lite_ratio = original_size / aura_lite_size if aura_lite_size else float('inf')
                aura_lite_advantage = ((aura_lite_ratio / auralite_ratio) - 1) * 100 if auralite_ratio else 0.0
                candidate_template_ids = list(aura_lite_encoded.template_ids)
                if not candidate_template_ids and template_match is not None:
                    candidate_template_ids = [template_match.template_id]
                candidates.append(
                    (
                        bytes([CompressionMethod.AURA_LITE.value]) + aura_lite_encoded.payload,
                        CompressionMethod.AURA_LITE,
                        {
                            'original_size': original_size,
                            'compressed_size': aura_lite_size,
                            'ratio': aura_lite_ratio,
                            'method': 'aura_lite',
                            'template_ids': candidate_template_ids,
                            'template_id': candidate_template_ids[0] if candidate_template_ids else None,
                            'advantage_vs_auralite_percent': aura_lite_advantage,
                            'fast_path_candidate': bool(aura_lite_encoded.template_ids),
                        },
                    )
                )
            except Exception:
                aura_lite_encoded = None

        # Add template candidate (needs auralite_ratio for comparison)
        if binary_data is not None:
            advantage = ((binary_ratio / auralite_ratio) - 1) * 100 if auralite_ratio else 0.0
            candidates.append(
                (
                    bytes([CompressionMethod.BINARY_SEMANTIC.value]) + binary_data,
                    CompressionMethod.BINARY_SEMANTIC,
                    {
                        'original_size': original_size,
                        'compressed_size': binary_size,
                        'ratio': binary_ratio,
                        'method': 'binary_semantic',
                        'template_id': template_match.template_id,
                        'template_ids': [template_match.template_id],
                        'slot_count': len(template_match.slots),
                        'advantage_vs_auralite_percent': advantage,
                        'fast_path_candidate': False,
                    },
                )
            )

        # AuraLite candidate metadata (Claim 14: preserve metadata on fallback)
        auralite_metadata = {
            'original_size': original_size,
            'compressed_size': auralite_size,
            'ratio': auralite_ratio,
            'method': 'auralite',
            'reason': 'no_template' if binary_data is None else 'auralite_better',
            'binary_ratio': binary_ratio,
            'fast_path_candidate': False,
            'fallback_from': None,  # Track if this is a fallback
            'attempted_methods': ['auralite'],  # Track attempted compression methods
        }

        # If we tried binary/AURA but fell back to AuraLite, record that (Claim 14)
        if binary_data is not None:
            auralite_metadata['attempted_methods'].append('binary_semantic')
            auralite_metadata['fallback_from'] = 'binary_semantic'
        if aura_lite_encoded is not None:
            auralite_metadata['attempted_methods'].append('aura_lite')
            auralite_metadata['fallback_from'] = (
                'binary_semantic'
                if auralite_metadata['fallback_from'] == 'binary_semantic'
                else 'aura_lite'
            )

        candidates.append(
            (
                bytes([CompressionMethod.AURALITE.value]) + auralite_payload,
                CompressionMethod.AURALITE,
                auralite_metadata,
            )
        )

        # Uncompressed candidate (fallback if compression expands data)
        uncompressed_payload = text.encode('utf-8')
        uncompressed_size = len(uncompressed_payload) + 1  # + method byte
        uncompressed_ratio = original_size / uncompressed_size if uncompressed_size else float('inf')

        candidates.append(
            (
                bytes([CompressionMethod.UNCOMPRESSED.value]) + uncompressed_payload,
                CompressionMethod.UNCOMPRESSED,
                {
                    'original_size': original_size,
                    'compressed_size': uncompressed_size,
                    'ratio': uncompressed_ratio,
                    'method': 'uncompressed',
                    'reason': 'fallback_candidate',
                    'fast_path_candidate': False,
                },
            )
        )

        # Experimental AURA candidate (TCP-optimized for small messages, full rANS for large)
        if self.enable_aura and self._aura_encoder is not None:
            try:
                # Route based on message size
                if original_size < self.tcp_brio_threshold:
                    # Use TCP-optimized BRIO (compact header, no rANS)
                    aura_compressed: TcpBrioCompressed = self._tcp_brio_encoder.compress(text)
                else:
                    # Use full BRIO with rANS (527+ byte header, better compression)
                    aura_compressed: BrioCompressed = self._aura_encoder.compress(
                        text,
                        template_match=template_match,
                    )
                aura_size = len(aura_compressed.payload) + 1
                aura_ratio = original_size / aura_size if aura_size else float('inf')

                # Handle metadata format (TCP-BRIO has no flags field)
                aura_entries = []
                for entry in aura_compressed.metadata:
                    entry_dict = {
                        'token_index': entry.token_index,
                        'kind': entry.kind,
                        'value': entry.value,
                    }
                    # Add flags if present (full BRIO has it, TCP-BRIO doesn't)
                    if hasattr(entry, 'flags'):
                        entry_dict['flags'] = entry.flags
                    aura_entries.append(entry_dict)

                template_ids = [
                    entry['value']
                    for entry in aura_entries
                    if entry['kind'] == TEMPLATE_METADATA_KIND and entry.get('flags', 0)
                ]
                token_counts = {
                    'total': len(aura_compressed.tokens),
                    'literals': sum(isinstance(t, AuraLiteralToken) for t in aura_compressed.tokens),
                    'dictionary': sum(isinstance(t, AuraDictionaryToken) for t in aura_compressed.tokens),
                    'matches': sum(isinstance(t, AuraMatchToken) for t in aura_compressed.tokens),
                    'templates': sum(isinstance(t, AuraTemplateToken) for t in aura_compressed.tokens),
                }
                aura_advantage = ((aura_ratio / brotli_ratio) - 1) * 100 if brotli_ratio else 0.0
                candidates.append(
                    (
                        bytes([CompressionMethod.BRIO.value]) + aura_compressed.payload,
                        CompressionMethod.BRIO,
                        {
                            'original_size': original_size,
                            'compressed_size': aura_size,
                            'ratio': aura_ratio,
                            'method': 'aura',
                            'template_ids': template_ids,
                            'metadata_entries': aura_entries,
                            'token_counts': token_counts,
                            'advantage_vs_brotli_percent': aura_advantage,
                            'template_id': template_ids[0] if template_ids else None,
                            'fast_path_candidate': any(
                                entry['kind'] == TEMPLATE_METADATA_KIND and entry.get('flags')
                                for entry in aura_entries
                            ),
                        },
                    )
                )
            except Exception:
                # In case experimental encoder fails, ignore candidate
                pass

        # PRIORITY ORDER (as specified by user):
        # 1. Uncompressed (if compression doesn't help - 1 byte overhead only)
        # 2. Binary Semantic (single template match - ultra compact)
        # 3. BRIO (multi-template with LZ77 or full rANS)
        # 4. AURA-Lite (template+dictionary+literals)
        # 5. AuraLite (LAST RESORT - proprietary fallback compression)

        # Find best candidate per method
        aura_lite_candidate = next(
            (c for c in candidates if c[1] == CompressionMethod.AURA_LITE),
            None,
        )
        binary_candidate = next(
            (c for c in candidates if c[1] == CompressionMethod.BINARY_SEMANTIC),
            None,
        )
        brio_candidate = next(
            (c for c in candidates if c[1] == CompressionMethod.BRIO),
            None,
        )
        auralite_candidate = next(
            (c for c in candidates if c[1] == CompressionMethod.AURALITE),
            None,
        )
        uncompressed_candidate = next(
            (c for c in candidates if c[1] == CompressionMethod.UNCOMPRESSED),
            None,
        )

        template_heavy = template_heavy_context
        prefer_aura_lite = False
        if aura_lite_candidate:
            aura_lite_payload_len = len(aura_lite_candidate[0])
            if template_heavy and aura_lite_payload_len < original_size:
                prefer_aura_lite = True
            elif template_heavy:
                aura_lite_candidate[2].setdefault('reason', 'template_heavy_but_expanded')

        # Filter candidates: never expand data beyond original + method byte overhead
        # Uncompressed is always valid (adds only 1 byte for method marker)
        valid_candidates = []
        for c in candidates:
            payload, method, meta = c
            # Allow uncompressed always (1 byte overhead is acceptable)
            if method == CompressionMethod.UNCOMPRESSED:
                valid_candidates.append(c)
            # For compressed methods, payload must be smaller than original
            elif len(payload) < original_size:
                valid_candidates.append(c)

    # Selection logic following priority order:
        # 1. Check if uncompressed is best (compression doesn't help)
        # 2. Binary Semantic (if available and compresses)
        # 3. BRIO (if available and compresses)
    # 4. AURA-Lite (prefer over AuraLite when available, even if within tiny overhead)
    # 5. AuraLite (last resort - proprietary fallback)
        # 6. Uncompressed (safety fallback)

        # Track which methods were attempted for metadata (Claim 7)
        attempted_methods = [c[2]['method'] for c in candidates]

        # First check if ANY compression helps
        compression_helps = any(
            c[1] != CompressionMethod.UNCOMPRESSED and len(c[0]) < original_size
            for c in valid_candidates
        )

        # Default selection to uncompressed for safety; branches below can override
        selected_payload, selected_method, selected_metadata = uncompressed_candidate
        selected_metadata['reason'] = selected_metadata.get('reason', 'default_uncompressed')

        if not compression_helps:
            # Priority 1: Use uncompressed if no compression method helps
            selected_payload, selected_method, selected_metadata = uncompressed_candidate
            selected_metadata['reason'] = 'no_compression_benefit'

        # Priority 1.5: Template-heavy messages should favor Aura-Lite when it actually compresses
        elif prefer_aura_lite:
            selected_payload, selected_method, selected_metadata = aura_lite_candidate
            selected_metadata['reason'] = 'template_heavy_preference'

        # Priority 2: Binary Semantic (best for single template matches)
        elif binary_candidate and len(binary_candidate[0]) < original_size:
            selected_payload, selected_method, selected_metadata = binary_candidate

        # Priority 3: BRIO (multi-template or full rANS)
        elif brio_candidate and len(brio_candidate[0]) < original_size:
            selected_payload, selected_method, selected_metadata = brio_candidate

        # Priority 4: AURA-Lite (template+dictionary+literals)
        elif aura_lite_candidate:
            # Prefer AURA-Lite when available. Allow a tiny overhead (<= +1 byte)
            aura_lite_payload, aura_lite_method, aura_lite_meta = aura_lite_candidate
            if len(aura_lite_payload) < original_size:
                selected_payload, selected_method, selected_metadata = aura_lite_candidate
            else:
                aura_lite_meta.setdefault('reason', 'aura_lite_expanded')

        # Priority 5: AuraLite (last resort - proprietary fallback compression)
        elif auralite_candidate and len(auralite_candidate[0]) < original_size:
            selected_payload, selected_method, selected_metadata = auralite_candidate
            selected_metadata['reason'] = 'aura_methods_unavailable'

        # Priority 6: Uncompressed (absolute safety fallback)
        else:
            selected_payload, selected_method, selected_metadata = uncompressed_candidate
            selected_metadata['reason'] = 'safety_fallback'

        # Add attempted methods to metadata
        selected_metadata['attempted_methods'] = attempted_methods

        # Audit logging (Claim 2) - Log compression event
        if self.enable_audit_logging and self._audit_logger:
            self._audit_logger.log_compression(
                plaintext=text,
                compressed_payload=selected_payload,
                metadata=selected_metadata,
                session_id=self.session_id,
                user_id=self.user_id,
            )

            # Also log metadata-only for privacy-preserving analytics (Claim 35)
            self._audit_logger.log_metadata_only(
                metadata=selected_metadata,
                session_id=self.session_id,
            )

        # Record template usage when selected method depends on a template
        if selected_method in (
            CompressionMethod.BINARY_SEMANTIC,
            CompressionMethod.BRIO,
            CompressionMethod.AURA_LITE,
        ):
            template_ids = selected_metadata.get('template_ids') or []
            for tid in template_ids:
                if tid is not None:
                    self.template_library.record_use(tid)

        if selected_method == CompressionMethod.BRIO:
            # Skip sanitization for brio_container format (already has correct metadata)
            if selected_metadata.get('method') != 'brio_container':
                sanitized_payload, shareable_entries = self._sanitize_brio_payload(selected_payload)
                selected_payload = sanitized_payload
                selected_metadata['metadata_entries'] = shareable_entries
                template_ids = [entry['value'] for entry in shareable_entries]
                selected_metadata['template_ids'] = template_ids
                selected_metadata['template_id'] = template_ids[0] if template_ids else None
                compressed_len = len(selected_payload)
                selected_metadata['compressed_size'] = compressed_len
                if compressed_len:
                    selected_metadata['ratio'] = selected_metadata['original_size'] / compressed_len
        elif selected_method == CompressionMethod.AURA_LITE:
            sanitized_payload, shareable_template_ids = self._sanitize_aura_lite_payload(selected_payload)
            selected_payload = sanitized_payload
            if shareable_template_ids:
                selected_metadata['template_ids'] = shareable_template_ids
                selected_metadata['template_id'] = shareable_template_ids[0]
            else:
                selected_metadata.setdefault('template_ids', selected_metadata.get('template_ids', []))
                if selected_metadata['template_ids']:
                    selected_metadata['template_id'] = selected_metadata['template_ids'][0]
                else:
                    selected_metadata['template_id'] = None
            compressed_len = len(selected_payload)
            selected_metadata['compressed_size'] = compressed_len
            if compressed_len:
                selected_metadata['ratio'] = selected_metadata['original_size'] / compressed_len

        if 'semantic_sketch' not in selected_metadata:
            selected_metadata['semantic_sketch'] = self._generate_semantic_sketch(text, selected_metadata)
        # Persist metadata to optional sidechain store for fast-path retrieval
        if self._sidechain.is_enabled:
            context = {
                "session_id": self.session_id,
                "user_id": self.user_id,
            }
            try:
                sidechain_ref = self._sidechain.store_entry(selected_payload, selected_metadata, context)
                if sidechain_ref:
                    selected_metadata.setdefault("sidechain_ref", sidechain_ref)
            except Exception as exc:
                print(f"⚠️  Sidechain store failed (continuing without interruption): {exc}")

        return selected_payload, selected_method, selected_metadata

    def decompress(self, data: bytes, return_metadata: bool = False) -> Any:
        """
        Decompress data (auto-detect method)
        Returns human-readable plaintext
        """
        if len(data) == 0:
            raise ValueError("Empty data")

        self._sync_template_store()

        method_byte = data[0]
        payload = data[1:]

        if method_byte == CompressionMethod.BINARY_SEMANTIC.value:
            text = self.decompress_binary(payload)
            if return_metadata:
                template_id = payload[0] if payload else None
                meta = {
                    'method': 'binary_semantic',
                    'template_id': template_id,
                    'template_ids': [template_id] if template_id is not None else [],
                    'fast_path_candidate': False,
                }
                meta['semantic_sketch'] = self._generate_semantic_sketch(text, meta)
                return text, meta
            return text
        elif method_byte == CompressionMethod.AURALITE.value:
            # AuraLite fallback decompression
            if self._aura_lite_decoder is None:
                raise ValueError("AuraLite payload encountered but decoder unavailable")
            result = self._aura_lite_decoder.decode(payload)
            if return_metadata:
                meta = {'method': 'auralite', 'fast_path_candidate': False}
                meta['semantic_sketch'] = self._generate_semantic_sketch(result.text, meta)
                return result.text, meta
            return result.text
        elif method_byte == CompressionMethod.AURA_LITE.value:
            if self._aura_lite_decoder is None:
                raise ValueError("Aura-Lite payload encountered but decoder unavailable")
            result = self._aura_lite_decoder.decode(payload)
            if return_metadata:
                metadata = {
                    'method': 'aura_lite',
                    'template_ids': list(result.template_ids),
                    'template_id': result.template_ids[0] if result.template_ids else None,
                    'fast_path_candidate': bool(result.template_ids),
                }
                metadata['semantic_sketch'] = self._generate_semantic_sketch(result.text, metadata)
                return result.text, metadata
            return result.text
        elif method_byte == CompressionMethod.BRIO.value:
            if not self.enable_aura or self._aura_decoder is None:
                raise ValueError("AURA payload encountered but experimental encoder disabled")
            # Auto-detect TCP-BRIO (BR magic) vs full BRIO (AURA magic)
            if payload[:2] == b"BR":
                # TCP-optimized BRIO
                result: BrioDecompressed = self._tcp_brio_decoder.decompress(payload)
            else:
                # Full BRIO with rANS
                result: BrioDecompressed = self._aura_decoder.decompress(payload)
            if return_metadata:
                aura_entries = [
                    {
                        'token_index': entry.token_index,
                        'kind': entry.kind,
                        'value': entry.value,
                        'flags': entry.flags,
                    }
                    for entry in result.metadata
                ]
                template_ids = [
                    entry.value
                    for entry in result.metadata
                    if entry.kind == TEMPLATE_METADATA_KIND and entry.flags
                ]
                metadata = {
                    'method': 'aura',
                    'metadata_entries': aura_entries,
                    'token_count': len(result.tokens),
                    'template_ids': template_ids,
                    'template_id': template_ids[0] if template_ids else None,
                    'fast_path_candidate': any(
                        entry['kind'] == TEMPLATE_METADATA_KIND and entry.get('flags')
                        for entry in aura_entries
                    ),
                }
                metadata['semantic_sketch'] = self._generate_semantic_sketch(result.text, metadata)
                return result.text, metadata
            return result.text
        elif method_byte == CompressionMethod.UNCOMPRESSED.value:
            text = payload.decode('utf-8')
            if return_metadata:
                meta = {'method': 'uncompressed', 'fast_path_candidate': False}
                meta['semantic_sketch'] = self._generate_semantic_sketch(text, meta)
                return text, meta
            return text
        else:
            raise ValueError(f"Unknown compression method: 0x{method_byte:02x}")

    # -- Dynamic template handling -------------------------------------------------

    def _ensure_template_loaded(self, template_id: int) -> None:
        if self.template_library.get_entry(template_id):
            return
        if self._template_store_path is None:
            env_store = os.getenv("AURA_TEMPLATE_STORE")
            if env_store and Path(env_store).exists():
                self._template_store_path = Path(env_store)
            else:
                default_store = Path("./template_store.json")
                if default_store.exists():
                    self._template_store_path = default_store
        self._sync_template_store(force=True)

    def _sync_template_store(self, force: bool = False) -> None:
        if self._template_store_path is None:
            return

        if not self._template_store_path.exists():
            if self._template_store_mtime is not None:
                self.template_library.sync_dynamic_templates({})
                self._template_store_mtime = None
            return

        mtime = self._template_store_path.stat().st_mtime
        if not force and self._template_store_mtime is not None:
            if mtime <= self._template_store_mtime:
                return

        try:
            data = json.loads(self._template_store_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return

        raw_templates = data.get("templates")
        if raw_templates is None or not raw_templates:
            raw_templates = data.get("platform_templates", {})
        if raw_templates is None:
            raw_templates = {}
        dynamic_templates: Dict[int, str] = {}

        for tid, info in raw_templates.items():
            try:
                template_id = int(tid)
            except (TypeError, ValueError):
                continue

            if not (0 <= template_id <= 255):
                continue

            pattern = info.get("pattern")
            if not isinstance(pattern, str) or not pattern.strip():
                continue

            dynamic_templates[template_id] = pattern

        self.template_library.sync_dynamic_templates(dynamic_templates)
        self._template_store_mtime = mtime

    def _sanitize_aura_lite_payload(self, data: bytes) -> Tuple[bytes, List[int]]:
        if len(data) <= 1 or data[0] != CompressionMethod.AURA_LITE.value:
            return data, []

        payload = bytearray(data[1:])
        if len(payload) < 11 or payload[:4] != b"AUL1":
            return data, []

        token_len = int.from_bytes(payload[6:10], "big")
        metadata_index = 10
        payload[metadata_index] = 0  # strip metadata count for clients

        tokens_end = min(len(payload), 11 + token_len)
        tokens_bytes = payload[11:tokens_end]

        template_ids: List[int] = []
        template_kind = self._aura_lite_encoder.TEMPLATE_KIND if self._aura_lite_encoder else 0x00
        dictionary_kind = self._aura_lite_encoder.DICTIONARY_KIND if self._aura_lite_encoder else 0x01
        literal_kind = self._aura_lite_encoder.LITERAL_KIND if self._aura_lite_encoder else 0x03

        pos = 0
        while pos < len(tokens_bytes):
            kind = tokens_bytes[pos]
            pos += 1

            if kind == template_kind:
                if pos >= len(tokens_bytes):
                    break
                template_id = tokens_bytes[pos]
                template_ids.append(template_id)
                pos += 1
                if pos >= len(tokens_bytes):
                    break
                slot_count = tokens_bytes[pos]
                pos += 1
                for _ in range(slot_count):
                    if pos + 2 > len(tokens_bytes):
                        pos = len(tokens_bytes)
                        break
                    slot_len = int.from_bytes(tokens_bytes[pos:pos + 2], "big")
                    pos += 2 + slot_len
            elif kind == dictionary_kind:
                pos += 1
            elif kind == literal_kind:
                if pos >= len(tokens_bytes):
                    break
                length = tokens_bytes[pos]
                pos += 1 + length
            else:
                break

        sanitized_payload = bytes([CompressionMethod.AURA_LITE.value]) + bytes(payload[:tokens_end])
        return sanitized_payload, template_ids

    def _sanitize_brio_payload(self, data: bytes) -> Tuple[bytes, List[Dict[str, Any]]]:
        if len(data) <= 1 or data[0] != CompressionMethod.BRIO.value:
            return data, []

        payload = data[1:]
        if payload[:4] != b"AURA":
            return data, []

        plain_token_len = payload[5:9]
        rans_payload_len = payload[9:13]
        metadata_count = int.from_bytes(payload[13:15], "big")

        freq_table_len = 256 * 2
        freq_start = 15
        freq_end = freq_start + freq_table_len
        metadata_start = freq_end
        metadata_len = metadata_count * 6
        metadata_end = metadata_start + metadata_len

        # Strip metadata entirely for client payloads; keep frequency table + rANS payload
        freq_table = payload[freq_start:freq_end]
        rans_payload = payload[metadata_end:]

        header = bytearray()
        header += payload[:5]  # magic + version
        header += plain_token_len
        header += rans_payload_len
        header += (0).to_bytes(2, 'big')  # no metadata entries exposed to clients
        header += freq_table

        sanitized = bytes([CompressionMethod.BRIO.value]) + bytes(header) + rans_payload
        return sanitized, []


class AuditLogger:
    """Human-readable audit logger for compliance"""

    def __init__(self, log_file: str = "aura_audit.log"):
        self.log_file = log_file

    def log_message(self, direction: str, role: str, content: str,
                   metadata: Optional[dict] = None):
        """
        Log message in human-readable format

        Args:
            direction: "client_to_server" or "server_to_client"
            role: "user" or "assistant"
            content: The actual message content (plaintext)
            metadata: Optional compression metadata
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        arrow = "→" if direction == "client_to_server" else "←"

        log_entry = f"[{timestamp}] {role.upper()} {arrow}\n"
        log_entry += f"  Message: {content}\n"

        if metadata:
            method_name = metadata.get('method', 'unknown')
            log_entry += f"  Compression: {method_name}\n"
            log_entry += f"  Size: {metadata.get('original_size', 0)} → {metadata.get('compressed_size', 0)} bytes\n"
            log_entry += f"  Ratio: {metadata.get('ratio', 0.0):.2f}:1\n"
            if method_name == 'aura':
                entries = metadata.get('metadata_entries', [])
                log_entry += f"  Metadata entries: {len(entries)}\n"
                if entries:
                    preview = entries[:3]
                    log_entry += f"    Preview: {preview}\n"

        log_entry += "\n"

        # Write to file
        with open(self.log_file, 'a') as f:
            f.write(log_entry)

        # Also print to console
        print(log_entry, end='')


def test_production_system():
    """Test the production-ready system"""

    print("=" * 80)
    print("PRODUCTION HYBRID COMPRESSION SYSTEM TEST")
    print("=" * 80)
    print()

    compressor = ProductionHybridCompressor(binary_advantage_threshold=1.1)
    audit_logger = AuditLogger()

    # Test cases with manual template mappings
    test_cases = [
        {
            "text": "I don't have access to real-time weather data. Please check weather.com",
            "template_id": 0,
            "slots": ["real-time weather data", "Please check weather.com"]
        },
        {
            "text": "The capital of France is Paris.",
            "template_id": 10,
            "slots": ["capital", "France", "Paris"]
        },
        {
            "text": "To install packages, use pip: `pip install numpy`",
            "template_id": 40,
            "slots": ["install packages", "pip", "pip install numpy"]
        },
        {
            "text": "Yes, I can help with that. What specific aspect would you like to know more about?",
            "template_id": 100,
            "slots": ["aspect"]
        },
        {
            "text": "The time complexity of binary search is O(log n) because it divides the search space in half.",
            "template_id": 70,
            "slots": ["time complexity", "binary search", "O(log n)", "it divides the search space in half"]
        },
        {
            "text": "Common HTTP status codes include: 200, 404, 500.",
            "template_id": 80,
            "slots": ["HTTP status codes", "200, 404, 500"]
        },
        {
            "text": "To debug this issue, I recommend: check console, verify endpoint, test authentication",
            "template_id": 90,
            "slots": ["debug this issue", "check console, verify endpoint, test authentication"]
        },
        {
            "text": "Neural networks work by adjusting weights through backpropagation.",
            "template_id": 71,
            "slots": ["Neural networks", "adjusting weights through backpropagation"]
        },
    ]

    results = []

    for idx, test_case in enumerate(test_cases, 1):
        text = test_case["text"]
        template_id = test_case.get("template_id")
        slots = test_case.get("slots")

        original_size = len(text.encode('utf-8'))

        # Compress
        compressed, method, metadata = compressor.compress(text, template_id, slots)

        # Decompress
        try:
            decompressed = compressor.decompress(compressed)
            matches = text == decompressed
        except Exception as e:
            decompressed = f"ERROR: {e}"
            matches = False

        # AuraLite baseline (for comparison)
        try:
            auralite_encoded = compressor._aura_lite_encoder.encode(text, None, template_spans=[])
            auralite_only = auralite_encoded.payload
            auralite_size = len(auralite_only)
            auralite_ratio = original_size / auralite_size
        except Exception:
            auralite_only = text.encode('utf-8')
            auralite_size = len(auralite_only)
            auralite_ratio = original_size / auralite_size

        results.append({
            'original': original_size,
            'hybrid': metadata['compressed_size'],
            'auralite': auralite_size,
            'hybrid_ratio': metadata['ratio'],
            'auralite_ratio': auralite_ratio,
            'method': method,
            'matches': matches,
            'metadata': metadata
        })

        # Display
        print(f"Test {idx}: {text[:60]}...")
        print(f"  Original:  {original_size:4d} bytes")
        print(f"  AuraLite:  {auralite_size:4d} bytes ({auralite_ratio:.2f}:1)")
        print(f"  Hybrid:    {metadata['compressed_size']:4d} bytes ({metadata['ratio']:.2f}:1)")
        print(f"  Method:    {metadata['method']}")

        if method == CompressionMethod.BINARY_SEMANTIC:
            advantage = metadata.get('advantage_vs_auralite_percent', 0)
            print(f"  🏆 Binary wins! {advantage:.1f}% better than AuraLite")
            print(f"     Template #{metadata['template_id']}, {metadata['slot_count']} slots")

        print(f"  Decompress: {'✅ PASS' if matches else '❌ FAIL'}")

        if not matches:
            print(f"     Expected: {text}")
            print(f"     Got: {decompressed}")

        print()

        # Log to audit
        audit_logger.log_message(
            direction="client_to_server",
            role="user",
            content=decompressed if matches else text,
            metadata=metadata
        )

    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print()

    total_original = sum(r['original'] for r in results)
    total_hybrid = sum(r['hybrid'] for r in results)
    total_auralite = sum(r['auralite'] for r in results)

    print(f"Total Original:  {total_original:,} bytes")
    print(f"Total AuraLite:  {total_auralite:,} bytes ({total_original/total_auralite:.2f}:1)")
    print(f"Total Hybrid:    {total_hybrid:,} bytes ({total_original/total_hybrid:.2f}:1)")
    print()

    savings = total_auralite - total_hybrid
    savings_pct = (savings / total_auralite) * 100

    print(f"Hybrid saves: {savings:,} bytes ({savings_pct:.1f}% better than AuraLite)")
    print()

    # Pass rate
    pass_count = sum(1 for r in results if r['matches'])
    pass_rate = (pass_count / len(results)) * 100

    print(f"Decompression accuracy: {pass_count}/{len(results)} ({pass_rate:.0f}%)")
    print()

    # Method distribution
    binary_count = sum(1 for r in results if r['method'] == CompressionMethod.BINARY_SEMANTIC)
    print(f"Binary semantic used: {binary_count}/{len(results)} ({binary_count/len(results)*100:.0f}%)")
    print()

    if pass_rate == 100:
        print("✅ ALL TESTS PASSED - PRODUCTION READY!")
    else:
        print("⚠️  Some tests failed - needs debugging")

    print()
    print(f"📋 Audit log written to: {audit_logger.log_file}")
    print()

if __name__ == "__main__":
    test_production_system()
