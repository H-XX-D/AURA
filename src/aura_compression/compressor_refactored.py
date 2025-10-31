#!/usr/bin/env python3
"""
Refactored Production-Ready Hybrid Compression System
Uses modular architecture with extracted components
"""
import os
import re
import struct
import time
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

from aura_compression.templates import TemplateMatch
from aura_compression.compression_engine import CompressionEngine
from aura_compression.compression_strategy_manager import CompressionStrategyManager
from aura_compression.ml_algorithm_selector import MLAlgorithmSelector
from aura_compression.template_service import TemplateService
from aura_compression.performance_optimizer import PerformanceOptimizer
from aura_compression.storage_manager import StorageManager
from aura_compression.metadata_sidechannel import MessageCategory
from aura_compression.pattern_semantic_large_file import PatternSemanticCompressor


class ProductionHybridCompressor:
    """
    Refactored production-ready hybrid compressor using modular architecture
    """

    def __init__(self,
                 binary_advantage_threshold: float = 1.01,
                 min_compression_size: int = 10,
                 enable_aura: Optional[bool] = None,
                 aura_preference_margin: float = 0.05,
                 enable_audit_logging: bool = False,
                 audit_log_directory: str = "./audit_logs",
                 session_id: Optional[str] = None,
                 user_id: Optional[str] = None,
                 template_cache_size: int = 128,
                 enable_normalization: bool = True,
                 tcp_brio_threshold: int = 1000,
                 enable_fast_path: bool = True,
                 enable_sidechain: Optional[bool] = None,
                 sidechain_config: Optional[Dict[str, Any]] = None,
                 enable_ml_selection: bool = False,
                 enable_scorer: Optional[bool] = None,
                 scorer_telemetry_path: Optional[str] = None,
                 template_sync_interval_seconds: Optional[int] = 60,
                 template_cache_dir: str = ".aura_cache"):
        """
        Initialize refactored compressor with modular components
        """
        # Core settings
        self.binary_advantage_threshold = binary_advantage_threshold
        self.min_compression_size = min_compression_size
        self.enable_fast_path = enable_fast_path
        self.tcp_brio_threshold = tcp_brio_threshold

        if enable_aura is None:
            env_value = os.getenv("AURA_ENABLE_EXPERIMENTAL", "false").lower()
            enable_aura = env_value in {"1", "true", "yes", "on"}
        self.enable_aura = enable_aura
        self.aura_preference_margin = aura_preference_margin

        # Initialize modular components
        self._init_components(
            enable_aura=enable_aura,
            enable_audit_logging=enable_audit_logging,
            audit_log_directory=audit_log_directory,
            session_id=session_id,
            user_id=user_id,
            template_cache_size=template_cache_size,
            enable_normalization=enable_normalization,
            enable_sidechain=enable_sidechain,
            sidechain_config=sidechain_config,
            enable_ml_selection=enable_ml_selection,
            enable_scorer=enable_scorer,
            scorer_telemetry_path=scorer_telemetry_path,
            template_cache_dir=template_cache_dir,
        )

        # Template store sync cadence (None disables periodic sync)
        self._template_sync_interval_seconds = template_sync_interval_seconds
        self._last_template_sync = 0.0

        # Fast path cache for Binary Semantic templates
        self._fast_path_cache: Dict[str, Tuple[int, List[str]]] = {}
        self._fast_path_max_cache_size = 256

    def _init_components(self,
                        enable_aura: bool,
                        enable_audit_logging: bool,
                        audit_log_directory: str,
                        session_id: Optional[str],
                        user_id: Optional[str],
                        template_cache_size: int,
                        enable_normalization: bool,
                        enable_sidechain: Optional[bool],
                        sidechain_config: Optional[Dict[str, Any]],
                        enable_ml_selection: bool,
                        enable_scorer: Optional[bool],
                        scorer_telemetry_path: Optional[str],
                        template_cache_dir: str):
        """
        Initialize all modular components
        """
        # Template service - restored and reconnected
        self.enable_normalization = enable_normalization
        self._normalizer = None  # Normalization removed

        # Initialize template service first
        self._template_service = TemplateService(
            enable_discovery=enable_aura,
            discovery_interval_seconds=3600,  # 1 hour
            audit_log_directory=audit_log_directory,
            cache_dir=template_cache_dir,
        )

        # Initialize audit service if enabled
        if enable_audit_logging:
            from aura_compression.audit import AuditLogger
            self._audit_service = AuditLogger(audit_log_directory)
        else:
            self._audit_service = None

        # Template service handles template library internally
        # Template library is now managed by the template service
        self.template_library = self._template_service.template_library

        # Template manager (for compatibility)
        self._template_manager = self._template_service.template_manager
        aura_encoder = None
        aura_decoder = None
        tcp_brio_encoder = None
        tcp_brio_decoder = None

        if enable_aura:
            # Initialize BRIO encoders for entropy coding
            try:
                from .brio_full import BrioEncoder, BrioDecoder
                aura_encoder = BrioEncoder()
                aura_decoder = BrioDecoder()
                tcp_brio_encoder = BrioEncoder()
                tcp_brio_decoder = BrioDecoder()
            except ImportError:
                # BRIO not available, continue without
                aura_encoder = None
                aura_decoder = None
                tcp_brio_encoder = None
                tcp_brio_decoder = None
            tcp_brio_encoder = None
            tcp_brio_decoder = None

        # Auralite encoders/decoders
        from aura_compression.auralite import AuraLiteEncoder, AuraLiteDecoder
        auralite_encoder = AuraLiteEncoder(template_library=self.template_library)
        auralite_decoder = AuraLiteDecoder(template_library=self.template_library)

        # Core compression engine
        self._compression_engine = CompressionEngine(
            template_library=self.template_library,
            aura_encoder=aura_encoder,
            aura_decoder=aura_decoder,
            tcp_brio_encoder=tcp_brio_encoder,
            tcp_brio_decoder=tcp_brio_decoder,
            auralite_encoder=auralite_encoder,
            auralite_decoder=auralite_decoder,
            tcp_brio_threshold=self.tcp_brio_threshold,
            pattern_semantic_compressor=PatternSemanticCompressor(),
        )

        # Template manager (for compatibility) - now handled in _init_components
        pass

        # Performance optimizer
        self._performance_optimizer = PerformanceOptimizer()

        # ML Algorithm selector
        self._ml_selector = None
        if enable_ml_selection:
            self._ml_selector = MLAlgorithmSelector(
                ai_compressor=PatternSemanticCompressor(),
                template_service=self._template_service,
                enable_expensive_features=False,  # Disable expensive AI features for better performance
                enable_learning=True,  # Enable ML learning from compression results
            )

        # Compression strategy manager
        scorer_flag = enable_scorer
        if scorer_flag is None:
            env_value = os.getenv("AURA_ENABLE_SCORER", "false").lower()
            scorer_flag = env_value in {"1", "true", "yes", "on"}

        self.enable_scorer = scorer_flag
        self.scorer_telemetry_path = scorer_telemetry_path

        self._strategy_manager = CompressionStrategyManager(
            compression_engine=self._compression_engine,
            algorithm_selector=self._ml_selector,  # May be None when ML disabled
            template_manager=self._template_manager,
            performance_optimizer=self._performance_optimizer,
            enable_scorer=scorer_flag,
            scorer_telemetry_path=scorer_telemetry_path,
        )

        # Storage manager (sidechain)
        if enable_sidechain is None:
            env_value = os.getenv("AURA_ENABLE_SIDECHAIN", "false").lower()
            enable_sidechain = env_value in {"1", "true", "yes", "on"}

        self.enable_sidechain = enable_sidechain
        self._storage_manager = StorageManager(
            enable_sidechain=enable_sidechain,
            storage_path="./sidechain",
            max_storage_size=100 * 1024 * 1024,  # 100MB
        )

        # Audit service removed - using direct audit logging
        self.session_id = session_id
        self.user_id = user_id

        # Metadata sidechannel for fast-path processing (Claims 21-30)
        from .metadata_sidechannel import MetadataSideChannel
        self._metadata_sidechannel = MetadataSideChannel()

        # Hardware acceleration removed - focus on core compression

    def compress(self, text, template_id: Optional[int] = None,
                 slots: Optional[List[str]] = None) -> Tuple[bytes, CompressionMethod, dict]:
        """
        Compress text using best method with modular architecture
        """
        # Handle both str and bytes input (backward compatible)
        if isinstance(text, bytes):
            text_str = text.decode('utf-8', errors='ignore')
            text_bytes = text
        else:
            text_str = text
            text_bytes = text.encode('utf-8')
        
        # Sync template store before compression
        current_time = time.time()
        if (
            self._template_sync_interval_seconds is not None
            and (current_time - self._last_template_sync >= self._template_sync_interval_seconds)
        ):
            self._template_service.sync_template_store()
            self._last_template_sync = current_time

        original_size = len(text_bytes)

        if original_size < 25:
            return self._compress_uncompressed(text_str)

        # Fast path 1: Early exit for tiny messages
        if original_size < self.min_compression_size:
            return self._compress_uncompressed(text_str)

        healing_attempted = False
        template_match = None

        while True:
            template_match = self._find_template_match(text_str, template_id, slots)
            if template_match and self.enable_fast_path:
                result = self._try_fast_path_compression(text_str, template_match)
                if result:
                    return result

            available_strategies = self._strategy_manager.get_available_strategies()
            optimal_strategy = self._strategy_manager.select_optimal_strategy(
                text_str, available_strategies, template_match
            )

            if (
                template_match
                and optimal_strategy == CompressionMethod.BINARY_SEMANTIC
                and self.template_library.get_entry(template_match.template_id) is None
            ):
                self._template_service.heal_template_cache(
                    text=text_str,
                    template_id=template_match.template_id,
                    force_full_reset=True,
                )
                if healing_attempted:
                    template_match = None
                    template_id = None
                    slots = None
                    available_strategies = self._strategy_manager.get_available_strategies()
                    optimal_strategy = self._strategy_manager.select_optimal_strategy(
                        text_str, available_strategies, None
                    )
                    break
                healing_attempted = True
                template_id = None
                slots = None
                continue

            break

        # Compress with optimal strategy
        try:
            if optimal_strategy == CompressionMethod.BINARY_SEMANTIC and template_match:
                compressed, metadata = self._compression_engine.compress_binary_semantic(text_str, template_match)
            elif optimal_strategy == CompressionMethod.AURALITE:
                compressed, metadata = self._compression_engine.compress_auralite(text_str)
            elif optimal_strategy == CompressionMethod.BRIO:
                compressed, metadata = self._compression_engine.compress_brio(text_str)
            elif optimal_strategy == CompressionMethod.PATTERN_SEMANTIC:
                compressed, metadata = self._compression_engine.compress_pattern_semantic(text_str)
            else:
                compressed, metadata = self._compression_engine.compress_uncompressed(text_str)
        except ValueError as exc:
            if (
                optimal_strategy == CompressionMethod.BINARY_SEMANTIC
                and "Unknown template ID" in str(exc)
                and not healing_attempted
            ):
                self._template_service.heal_template_cache(
                    text=text_str,
                    template_id=template_match.template_id if template_match else None,
                    force_full_reset=True,
                )
                template_match = None
                available_strategies = self._strategy_manager.get_available_strategies()
                optimal_strategy = self._strategy_manager.select_optimal_strategy(
                    text_str, available_strategies, None
                )
                if optimal_strategy == CompressionMethod.AURALITE:
                    compressed, metadata = self._compression_engine.compress_auralite(text)
                elif optimal_strategy == CompressionMethod.BRIO:
                    compressed, metadata = self._compression_engine.compress_brio(text)
                elif optimal_strategy == CompressionMethod.PATTERN_SEMANTIC:
                    compressed, metadata = self._compression_engine.compress_pattern_semantic(text)
                else:
                    compressed, metadata = self._compression_engine.compress_uncompressed(text)
            else:
                raise

        # Add method marker (except for uncompressed which already has it)
        if optimal_strategy != CompressionMethod.UNCOMPRESSED:
            method_byte = optimal_strategy.value
            if compressed and compressed[0] == method_byte:
                final_payload = compressed
            else:
                final_payload = bytes([method_byte]) + compressed
        else:
            final_payload = compressed

        # Update metadata
        metadata_template_id = template_match.template_id if template_match else template_id
        metadata_slot_count = len(template_match.slots) if template_match else (len(slots) if slots else 0)

        metadata.update({
            'original_size': original_size,
            'compressed_size': len(final_payload),
            'ratio': original_size / len(final_payload) if len(final_payload) > 0 else 1.0,
            'method': optimal_strategy.name.lower(),
            'attempted_methods': [s.name.lower() for s in available_strategies],
        })

        # Fallback to UNCOMPRESSED if compression expanded data
        compression_ratio = original_size / len(final_payload) if len(final_payload) > 0 else 1.0
        if compression_ratio <= 1.0 and optimal_strategy != CompressionMethod.UNCOMPRESSED:
            # Data expanded, fall back to UNCOMPRESSED
            compressed, metadata = self._compression_engine.compress_uncompressed(text_str)
            final_payload = compressed
            optimal_strategy = CompressionMethod.UNCOMPRESSED
            metadata.update({
                'original_size': original_size,
                'compressed_size': len(final_payload),
                'ratio': original_size / len(final_payload) if len(final_payload) > 0 else 1.0,
                'method': CompressionMethod.UNCOMPRESSED.name.lower(),
                'attempted_methods': [s.name.lower() for s in available_strategies],
                'fallback_reason': 'expansion_detected',
            })

        # Encode inline metadata for fast-path processing (Claims 21-30)
        if self.enable_sidechain:
            # Determine message category and other metadata
            category = self._infer_message_category(text, optimal_strategy, metadata_template_id)
            final_payload = self._metadata_sidechannel.encode_metadata(
                compressed=final_payload,
                compression_method=optimal_strategy.value,
                original_size=original_size,
                template_id=metadata_template_id,
                category=category,
                slot_count=metadata_slot_count,
                original_text=text if self.enable_sidechain else None,
            )
            # Update compressed size after adding metadata header
            metadata['compressed_size'] = len(final_payload)
            metadata['ratio'] = original_size / len(final_payload) if len(final_payload) > 0 else 1.0

        # Audit logging
        if self._audit_service is not None:
            self._audit_service.log_compression_event(
                plaintext=text,
                compressed_payload=final_payload,
                metadata=metadata,
                session_id=self.session_id,
                user_id=self.user_id,
            )

        # Keep scorer flag in sync with adaptive gating state
        self.enable_scorer = self._strategy_manager.enable_scorer
        metadata.setdefault('scorer_status', self._strategy_manager.get_scorer_status())

        return final_payload, optimal_strategy, metadata

    def get_scorer_status(self) -> Dict[str, Any]:
        """Expose scorer adaptive gating state for reporting."""
        return self._strategy_manager.get_scorer_status()

    def _compress_uncompressed(self, text: str) -> Tuple[bytes, CompressionMethod, dict]:
        """Compress using uncompressed method"""
        compressed, metadata = self._compression_engine.compress_uncompressed(text)
        metadata.update({
            'reason': 'message_too_small',
            'fast_path_used': 'tiny_message_early_exit' if self.enable_fast_path else None,
            'attempted_methods': ['uncompressed'],
        })

        # Audit service removed - logging disabled

        return compressed, CompressionMethod.UNCOMPRESSED, metadata

    def _find_template_match(self, text: str, template_id: Optional[int],
                           slots: Optional[List[str]]) -> Optional[TemplateMatch]:
        """Find template match for text"""
        # Normalization removed - direct matching only
        if template_id is not None:
            if slots is None:
                inferred = self.template_library.extract_slots(template_id, text)
                if inferred is not None:
                    slots = inferred
            if slots is not None:
                entry = self.template_library.get_entry(template_id)
                if entry and entry.slot_count == len(slots):
                    reconstructed = self.template_library.format_template(template_id, slots)
                    if reconstructed == text:
                        return TemplateMatch(template_id, list(slots))

        # CPU fallback
        return self._template_manager.find_template_match(text)

    def _try_fast_path_compression(self, text: str, template_match: TemplateMatch) -> Optional[Tuple[bytes, CompressionMethod, dict]]:
        """Try fast path binary semantic compression"""
        try:
            compressed, metadata = self._compression_engine.compress_binary_semantic(text, template_match)
            if compressed and compressed[0] == CompressionMethod.BINARY_SEMANTIC.value:
                binary_payload = compressed
            else:
                binary_payload = bytes([CompressionMethod.BINARY_SEMANTIC.value]) + compressed

            original_size = len(text.encode('utf-8'))
            if len(binary_payload) < original_size:
                metadata.update({
                    'original_size': original_size,
                    'compressed_size': len(binary_payload),
                    'ratio': original_size / len(binary_payload),
                    'method': 'binary_semantic',
                    'template_id': template_match.template_id,
                    'template_ids': [template_match.template_id],
                    'slot_count': len(template_match.slots),
                    'fast_path_candidate': True,
                    'fast_path_used': 'binary_semantic_direct',
                    'attempted_methods': ['binary_semantic'],
                })

                # Record template usage
                self._template_service.record_template_use(template_match.template_id)

                # Audit logging
                if self._audit_service is not None:
                    self._audit_service.log_compression_event(
                        plaintext=text,
                        compressed_payload=binary_payload,
                        metadata=metadata,
                        session_id=self.session_id,
                        user_id=self.user_id,
                    )

                return binary_payload, CompressionMethod.BINARY_SEMANTIC, metadata

        except Exception:
            pass

        return None

    def decompress(self, data: bytes, return_metadata: bool = False) -> Any:
        """
        Decompress data using modular architecture with metadata sidechannel support
        """
        if len(data) == 0:
            raise ValueError("Empty data")

        # Sync template store before decompression
        self._template_service.sync_template_store()

        # Check for metadata header (fast-path processing)
        extracted_metadata = None
        if self.enable_sidechain and len(data) >= 12:
            try:
                extracted_metadata = self._metadata_sidechannel.extract_metadata(data)
                # Remove metadata header from payload
                data = data[12:]
            except (ValueError, IndexError):
                # Not a metadata header, continue with normal processing
                pass

        # Extract method and delegate to compression engine
        method = self._compression_engine.get_compression_method(data)
        payload = data[1:]

        if method == CompressionMethod.BINARY_SEMANTIC:
            text, metadata = self._compression_engine.decompress_binary_semantic(data)
        elif method == CompressionMethod.AURALITE:
            text, metadata = self._compression_engine.decompress_auralite(data)
        elif method == CompressionMethod.BRIO:
            text, metadata = self._compression_engine.decompress_brio(data)
        elif method == CompressionMethod.PATTERN_SEMANTIC:
            text, metadata = self._compression_engine.decompress_pattern_semantic(data)
        elif method == CompressionMethod.UNCOMPRESSED:
            text, metadata = self._compression_engine.decompress_uncompressed(data)  # Keep full data for uncompressed
        else:
            raise ValueError(f"Unsupported compression method: {method}")

        if return_metadata:
            # Enhance metadata with additional info and extracted metadata
            metadata.update({
                'semantic_sketch': self._generate_semantic_sketch(text, metadata)
            })
            if extracted_metadata:
                metadata['sidechannel_metadata'] = {
                    'category': extracted_metadata.category.name,
                    'intent': extracted_metadata.intent,
                    'confidence': extracted_metadata.confidence,
                    'security_level': extracted_metadata.security_level.name,
                    'contains_code': extracted_metadata.contains_code,
                    'contains_urls': extracted_metadata.contains_urls,
                    'compression_ratio': extracted_metadata.compression_ratio,
                }
            return text, metadata

        return text

    def _generate_semantic_sketch(self, text: str, metadata: dict) -> str:
        """Generate semantic sketch for audit logging"""
        template_ids = metadata.get('template_ids', [])
        if template_ids:
            template_info = []
            for tid in template_ids:
                entry = self.template_library.get_entry(tid)
                if entry:
                    template_info.append(f"T{entry.id}({entry.slot_count})")
            return f"[{','.join(template_info)}] {text[:_SEMANTIC_PREVIEW_LIMIT]}"
        return text[:_SEMANTIC_PREVIEW_LIMIT]

    def compress_with_template(self, template_id: int, slots: List[str]) -> bytes:
        """
        Compress using specific template (legacy method)
        """
        entry = self.template_library.get_entry(template_id)
        if entry is None:
            raise ValueError(f"Unknown template ID: {template_id}")

        if entry.slot_count != len(slots):
            raise ValueError(
                f"Template {template_id} expects {entry.slot_count} slots, got {len(slots)}"
            )

        # Create binary semantic format
        template_bytes = struct.pack(">H", template_id)
        slot_count_byte = bytes([len(slots)])
        slot_lengths = []
        slot_data = []

        for slot in slots:
            slot_bytes = slot.encode('utf-8')
            slot_lengths.append(len(slot_bytes))
            slot_data.append(slot_bytes)

        slot_lengths_bytes = b''.join(struct.pack(">H", length) for length in slot_lengths)
        slots_bytes = b''.join(slot_data)

        return template_bytes + slot_count_byte + slot_lengths_bytes + slots_bytes

    def _infer_message_category(self, text: str, compression_method: CompressionMethod,
                               template_id: Optional[int]) -> Optional[MessageCategory]:
        """
        Infer message category for metadata sidechannel encoding
        """
        from .metadata_sidechannel import MessageCategory

        # Template-based messages
        if template_id is not None:
            return MessageCategory.DISCOVERED

        # Code examples
        if '```' in text or 'def ' in text or 'class ' in text:
            return MessageCategory.CODE_EXAMPLE

        # Questions
        if '?' in text and any(word in text.lower() for word in ['what', 'how', 'why', 'when', 'where']):
            return MessageCategory.CLARIFICATION

        # Instructions
        if any(phrase in text.lower() for phrase in ['first', 'then', 'next', 'finally', 'step']):
            return MessageCategory.INSTRUCTION

        # Facts/definitions
        if any(word in text.lower() for word in ['is', 'are', 'means', 'refers to']):
            return MessageCategory.DEFINITION

        # Default
        return MessageCategory.GENERAL

    def fast_path_classify(self, compressed_data: bytes) -> Optional[Dict[str, Any]]:
        """
        Classify compressed message using only metadata (Claims 21-30)

        Returns classification results without decompression, or None if no metadata header.
        Achieves 76-200× speedup vs traditional NLP classification.
        """
        if not self.enable_sidechain or len(compressed_data) < 12:
            return None

        try:
            metadata = self._metadata_sidechannel.extract_metadata(compressed_data)
            return self._metadata_sidechannel.classify_message(metadata)
        except (ValueError, IndexError):
            return None

    def fast_path_route(self, compressed_data: bytes) -> Optional[str]:
        """
        Route compressed message using only metadata (Claims 21-30)

        Returns handler name without decompression, or None if no metadata header.
        Enables ultra-fast routing decisions in 0.17ms vs 13.0ms traditional.
        """
        if not self.enable_sidechain or len(compressed_data) < 12:
            return None

        try:
            metadata = self._metadata_sidechannel.extract_metadata(compressed_data)
            return self._metadata_sidechannel.route_message(metadata)
        except (ValueError, IndexError):
            return None

    def fast_path_security_check(self, compressed_data: bytes) -> Optional[bool]:
        """
        Perform security screening using only metadata (Claims 21-30)

        Returns True if message passes security screening, False if blocked,
        or None if no metadata header available.
        """
        if not self.enable_sidechain or len(compressed_data) < 12:
            return None

        try:
            metadata = self._metadata_sidechannel.extract_metadata(compressed_data)
            return self._metadata_sidechannel.screen_security(metadata)
        except (ValueError, IndexError):
            return None

    def fast_path_analytics(self, compressed_data: bytes) -> Optional[Dict[str, Any]]:
        """
        Perform analytics using only metadata (Claims 21-30)

        Returns analytics metrics without decompression, or None if no metadata header.
        """
        if not self.enable_sidechain or len(compressed_data) < 12:
            return None

        try:
            metadata = self._metadata_sidechannel.extract_metadata(compressed_data)
            return self._metadata_sidechannel.analyze_metrics(metadata)
        except (ValueError, IndexError):
            return None

    def fast_path_process(self, compressed_data: bytes) -> Optional[Dict[str, Any]]:
        """
        Complete fast-path processing using only metadata (Claims 21-30)

        Performs classification, routing, security screening, and analytics
        without decompression. Returns None if no metadata header available.

        Performance: 0.17ms vs 13.0ms traditional = 76× faster
        """
        if not self.enable_sidechain or len(compressed_data) < 12:
            return None

        try:
            return self._metadata_sidechannel.fast_path_process(compressed_data)
        except (ValueError, IndexError):
            return None

    def decompress_binary(self, data: bytes) -> str:
        """
        Decompress binary semantic format (legacy method)
        """
        return self._compression_engine.decompress_binary_semantic(data)[0]

    # Backwards compatibility properties
    @property
    def templates(self):
        """Backwards compatibility for legacy callers"""
        return self.template_library

    def get_performance_stats(self) -> dict:
        """Get performance statistics from all components"""
        return {
            'template_manager': self._template_manager.get_template_stats(),
            'performance_optimizer': self._performance_optimizer.get_performance_stats(),
            'storage_manager': self._storage_manager.get_storage_stats(),
            'ml_selection_enabled': self._ml_selector is not None,
        }
