#!/usr/bin/env python3
"""
Compression Strategy Manager - Manages compression strategies and method selection
Extracted from the monolithic ProductionHybridCompressor
"""
import csv
import logging
import math
import os
import struct
from pathlib import Path
import json
from typing import Dict, List, Tuple, Optional, Any
from enum import Enum
from datetime import datetime, timezone
from collections import Counter, OrderedDict

from aura_compression.enums import (
    CompressionMethod,
    TEMPLATE_METADATA_KIND,
    _SEMANTIC_PREVIEW_LIMIT,
    _SEMANTIC_TOKEN_LIMIT,
    _SEMANTIC_TOKEN_PATTERN,
)

from aura_compression.templates import TemplateMatch
from aura_compression.compression_engine import CompressionEngine
from aura_compression.ml_algorithm_selector import CompressionResult


# Common tiny tokens that are frequently compressible despite short length
_SHORT_COMPRESSIBLE_TOKENS = {
    "ok",
    "yes",
    "no",
    "error",
    "warn",
    "info",
    "true",
    "false",
    "null",
    "pass",
    "fail",
    "ready",
    "status",
    "success",
    "failed",
}


class CompressionStrategyManager:
    """
    Manages compression strategies and method selection
    """
    _METRIC_CACHE_LIMIT = 256
    _PARTIAL_UNCOMPRESSED_THRESHOLD = 16  # bytes

    def __init__(self,
                 compression_engine: CompressionEngine,
                 algorithm_selector: Any,
                 template_manager: Any,
                 performance_optimizer: Any,
                 enable_scorer: bool = False,
                 scorer_telemetry_path: Optional[str] = None,
                 enable_validation: bool = False):
        """
        Initialize strategy manager

        Args:
            compression_engine: Engine for compression operations
            algorithm_selector: ML-based algorithm selector (optional)
            template_manager: Template manager for pattern matching
            performance_optimizer: Performance optimization utilities
            enable_scorer: Enable lightweight ML assist scorer for borderline payloads
            scorer_telemetry_path: Optional CSV path for scorer telemetry (defaults to ./audit_logs/)
            enable_validation: Enable post-compression validation hook (logs mismatches without blocking)
        """
        self.compression_engine = compression_engine
        self.algorithm_selector = algorithm_selector
        self.template_manager = template_manager
        self.performance_optimizer = performance_optimizer
        self.enable_scorer = enable_scorer
        self.enable_validation = enable_validation
        telemetry_path = scorer_telemetry_path or os.getenv("AURA_SCORER_TELEMETRY_PATH")
        if telemetry_path:
            self.scorer_telemetry_path = Path(telemetry_path)
        else:
            self.scorer_telemetry_path = Path("./audit_logs/scorer_telemetry.csv")
        if self.scorer_telemetry_path.exists() and self.scorer_telemetry_path.stat().st_size > 0:
            self._scorer_header_written = True
        else:
            self._scorer_header_written = False

        # Metric caches for entropy/dictionary computations
        self._entropy_cache: "OrderedDict[Any, float]" = OrderedDict()
        self._dict_hit_cache: "OrderedDict[Any, float]" = OrderedDict()

        # Logger for validation mismatches
        self._logger = logging.getLogger(__name__)
        self._validation_mismatch_count = 0

        # Scorer adaptive gating state
        self._scorer_requested = bool(enable_scorer)
        self._scorer_auto_disabled = False
        self._scorer_disabled_reason: Optional[str] = None
        self._scorer_status_recommendation: Optional[str] = None
        self._scorer_last_window_ratio: Optional[float] = None
        self._scorer_last_window_total: int = 0

        self._messages_seen = 0
        self._borderline_messages = 0
        self._scorer_window_total = 0
        self._scorer_window_borderline = 0

        self._scorer_eval_window = self._read_int_env("AURA_SCORER_EVAL_WINDOW", default=500, min_value=1)
        self._scorer_min_borderline_ratio = self._read_float_env(
            "AURA_SCORER_MIN_BORDERLINE_RATIO",
            default=0.15,
            min_value=0.0,
            max_value=1.0,
        )

        self._hydrate_scorer_stats()

    def _compress_with_strategies(self,
                                  text: str,
                                  strategies: List[CompressionMethod],
                                  template_match: Optional[TemplateMatch] = None) -> Tuple[bytes, dict]:
        """
        Compress using multiple strategies and return the best result
        """
        best_result = None
        best_ratio = 0.0

        for strategy in strategies:
            try:
                if strategy == CompressionMethod.BINARY_SEMANTIC:
                    # Try full template match first
                    if template_match is None:
                        # Fallback: Try partial template matching
                        partial_matches = self.template_manager.template_library.find_substring_matches(text)
                        if partial_matches:
                            # Use partial matching compression (best match or hybrid)
                            compressed, metadata = self._compress_with_partial_templates(
                                text,
                                partial_matches,
                                strategy,
                            )
                        else:
                            continue
                    else:
                        compressed, metadata = self.compression_engine.compress_binary_semantic(text, template_match)

                elif strategy == CompressionMethod.AURALITE:
                    # Try partial template matching first for AURALITE too
                    if template_match is None:
                        partial_matches = self.template_manager.template_library.find_substring_matches(text)
                        if partial_matches:
                            # Use partial matching compression
                            compressed, metadata = self._compress_with_partial_templates(
                                text,
                                partial_matches,
                                strategy,
                            )
                        else:
                            # No template match, use standard AURALITE
                            compressed, metadata = self.compression_engine.compress_auralite(text)
                    else:
                        # Full template match available
                        compressed, metadata = self.compression_engine.compress_binary_semantic(text, template_match)

                elif strategy == CompressionMethod.BRIO:
                    # Try partial template matching first for BRIO too
                    if template_match is None:
                        partial_matches = self.template_manager.template_library.find_substring_matches(text)
                        if partial_matches:
                            # Use partial matching compression
                            compressed, metadata = self._compress_with_partial_templates(
                                text,
                                partial_matches,
                                strategy,
                            )
                        else:
                            # No template match, use standard BRIO
                            compressed, metadata = self.compression_engine.compress_brio(text)
                    else:
                        # Full template match available
                        compressed, metadata = self.compression_engine.compress_binary_semantic(text, template_match)

                elif strategy == CompressionMethod.PATTERN_SEMANTIC:
                    # PATTERN_SEMANTIC does NOT use partial template matching (as requested)
                    compressed, metadata = self.compression_engine.compress_pattern_semantic(text)

                else:
                    continue

                ratio = metadata.get('ratio', 0.0)
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_result = (compressed, metadata)

            except Exception as e:
                # Skip failed strategies
                continue

        if best_result is None:
            # Fallback to uncompressed
            return self.compression_engine.compress_uncompressed(text)

        # If the best ratio does not beat the uncompressed baseline, prefer raw text.
        if best_ratio <= 1.0:
            compressed, metadata = best_result
            if metadata.get('method') == CompressionMethod.UNCOMPRESSED.name.lower():
                return best_result
            return self.compression_engine.compress_uncompressed(text)

        # Validate compression result if enabled (post-compression validation hook)
        if self.enable_validation and best_result is not None:
            compressed, metadata = best_result
            is_valid = self.validate_compression_result(text, compressed, metadata)
            if not is_valid:
                self._validation_mismatch_count += 1
                self._logger.warning(
                    f"Validation mismatch detected (count: {self._validation_mismatch_count}): "
                    f"method={metadata.get('method', 'unknown')}, "
                    f"original_size={len(text)}, "
                    f"compressed_size={len(compressed)}, "
                    f"ratio={metadata.get('ratio', 0.0):.3f}x"
                )

        return best_result

    def compress_with_method(self,
                            text: str,
                            method: CompressionMethod,
                            template_match: Optional[TemplateMatch] = None) -> Tuple[bytes, dict]:
        """
        Compress using a specific method
        All methods (except PATTERN_SEMANTIC) now try partial template matching first
        """
        import time

        start_time = time.time()

        if method == CompressionMethod.BINARY_SEMANTIC:
            if template_match is None:
                # Try partial template matching
                partial_matches = self.template_manager.template_library.find_substring_matches(text)
                if partial_matches:
                    result = self._compress_with_partial_templates(text, partial_matches, method)
                else:
                    raise ValueError("No template match found for BINARY_SEMANTIC")
            else:
                result = self.compression_engine.compress_binary_semantic(text, template_match)

        elif method == CompressionMethod.AURALITE:
            # Try partial template matching first
            if template_match is None:
                partial_matches = self.template_manager.template_library.find_substring_matches(text)
                if partial_matches:
                    result = self._compress_with_partial_templates(text, partial_matches, method)
                else:
                    result = self.compression_engine.compress_auralite(text)
            else:
                result = self.compression_engine.compress_binary_semantic(text, template_match)

        elif method == CompressionMethod.BRIO:
            # Try partial template matching first
            if template_match is None:
                partial_matches = self.template_manager.template_library.find_substring_matches(text)
                if partial_matches:
                    result = self._compress_with_partial_templates(text, partial_matches, method)
                else:
                    result = self.compression_engine.compress_brio(text)
            else:
                result = self.compression_engine.compress_binary_semantic(text, template_match)

        elif method == CompressionMethod.PATTERN_SEMANTIC:
            # PATTERN_SEMANTIC does NOT use partial template matching (as requested)
            result = self.compression_engine.compress_pattern_semantic(text)

        elif method == CompressionMethod.UNCOMPRESSED:
            result = self.compression_engine.compress_uncompressed(text)

        else:
            raise ValueError(f"Unsupported compression method: {method}")
        
        # Record performance for ML learning
        if hasattr(self, 'algorithm_selector') and self.algorithm_selector and self.algorithm_selector.enable_learning:
            compressed_data, metadata = result
            compression_time = time.time() - start_time
            original_size = len(text.encode('utf-8'))
            compressed_size = len(compressed_data)
            ratio = original_size / compressed_size if compressed_size > 0 else 1.0
            
            # Map CompressionMethod enum to string for ML selector
            method_str = {
                CompressionMethod.BINARY_SEMANTIC: "binary_semantic",
                CompressionMethod.AURALITE: "auralite",
                CompressionMethod.BRIO: "brio",
                CompressionMethod.PATTERN_SEMANTIC: "pattern_semantic",
                CompressionMethod.UNCOMPRESSED: "uncompressed"
            }.get(method, str(method))
            
            perf_result = CompressionResult(
                method=method_str,
                original_size=original_size,
                compressed_size=compressed_size,
                compression_time=compression_time,
                ratio=ratio
            )
            
            try:
                self.algorithm_selector.record_performance(text, method_str, perf_result)
            except Exception:
                # Don't fail compression if ML learning fails
                pass
        
        return result

    def select_optimal_strategy(self,
                               text: str,
                               available_strategies: List[CompressionMethod],
                               template_match: Optional[TemplateMatch] = None) -> CompressionMethod:
        """
        Select the optimal compression strategy for the given text
        """
        if not available_strategies:
            return CompressionMethod.UNCOMPRESSED

        # Filter strategies based on requirements
        filtered_strategies = []
        for strategy in available_strategies:
            if strategy == CompressionMethod.BINARY_SEMANTIC and template_match is None:
                continue  # Skip BINARY_SEMANTIC if no template match
            filtered_strategies.append(strategy)

        message_byte_length = len(text.encode('utf-8'))
        self._record_message_statistics(message_byte_length)
        if message_byte_length < 1_048_576:
            filtered_strategies = [s for s in filtered_strategies if s != CompressionMethod.PATTERN_SEMANTIC]

        if not filtered_strategies:
            return CompressionMethod.UNCOMPRESSED

        # Quick heuristic for incompressible data
        if self._is_likely_incompressible(text):
            return CompressionMethod.UNCOMPRESSED

        entropy = self._calculate_entropy(text)
        dict_hit_potential = self._estimate_dictionary_hit_rate(text)

        # Use intelligent method selection based on message characteristics
        best_method, scorer_score = self._select_best_method_by_heuristic(
            text,
            filtered_strategies,
            template_match,
            byte_length=message_byte_length,
            entropy=entropy,
            dict_hit_potential=dict_hit_potential,
        )

        if self.enable_scorer and scorer_score is not None:
            self._persist_scorer_telemetry(
                payload_size=message_byte_length,
                entropy=entropy,
                dict_hit_rate=dict_hit_potential,
                score=scorer_score,
                selected_method=best_method,
            )
        return best_method

    def get_available_strategies(self) -> List[CompressionMethod]:
        """
        Get list of available compression strategies
        """
        strategies = [CompressionMethod.UNCOMPRESSED]  # Always available

        # Check if encoders are available
        try:
            # BINARY_SEMANTIC requires template library
            if hasattr(self.compression_engine, 'template_library') and self.compression_engine.template_library:
                strategies.append(CompressionMethod.BINARY_SEMANTIC)
        except (AttributeError, TypeError):
            pass

        try:
            # Auralite requires encoder
            if hasattr(self.compression_engine, '_auralite_encoder') and self.compression_engine._auralite_encoder:
                strategies.append(CompressionMethod.AURALITE)
        except (AttributeError, TypeError):
            pass

        try:
            # BRIO requires BRIO encoder
            if hasattr(self.compression_engine, '_aura_encoder') and self.compression_engine._aura_encoder:
                strategies.append(CompressionMethod.BRIO)
        except (AttributeError, TypeError):
            pass

        try:
            # PATTERN_SEMANTIC requires AI semantic compressor
            if hasattr(self.compression_engine, '_pattern_semantic_compressor') and self.compression_engine._pattern_semantic_compressor:
                strategies.append(CompressionMethod.PATTERN_SEMANTIC)
        except (AttributeError, TypeError):
            pass

        return strategies

    def _select_best_method_by_heuristic(self,
                                         text: str,
                                         available_strategies: List[CompressionMethod],
                                         template_match: Optional[TemplateMatch],
                                         byte_length: Optional[int] = None,
                                         entropy: Optional[float] = None,
                                         dict_hit_potential: Optional[float] = None) -> Tuple[CompressionMethod, Optional[float]]:
        """
        Select the best compression method using intelligent heuristics
        Tuned to prefer Auralite/BRIO for medium payloads based on entropy and dictionary hit rate
        """
        # Quick message analysis
        if byte_length is None:
            byte_length = len(text.encode('utf-8'))

        if entropy is None:
            entropy = self._calculate_entropy(text)

        if dict_hit_potential is None:
            dict_hit_potential = self._estimate_dictionary_hit_rate(text)

        scorer_score: Optional[float] = None

        # Very small payloads never compress well
        if byte_length < 20:
            return CompressionMethod.UNCOMPRESSED, scorer_score

        # Always favor template compression when we already have a match
        if template_match is not None and CompressionMethod.BINARY_SEMANTIC in available_strategies:
            return CompressionMethod.BINARY_SEMANTIC, scorer_score

        # Adjusted size-based thresholds with entropy consideration
        if byte_length < 80:
            # Very small messages: only compress if low entropy
            if entropy < 4.0 and CompressionMethod.AURALITE in available_strategies:
                return CompressionMethod.AURALITE, scorer_score
            return CompressionMethod.UNCOMPRESSED, scorer_score

        if byte_length < 400:
            # Small messages: prefer Auralite if compressible
            if entropy < 5.5 and CompressionMethod.AURALITE in available_strategies:
                return CompressionMethod.AURALITE, scorer_score
            return CompressionMethod.UNCOMPRESSED, scorer_score

        if byte_length < 2048:
            # Medium messages: prefer Auralite with dictionary hits, else BRIO
            # Use scorer if enabled for borderline cases
            if self.enable_scorer and 400 <= byte_length <= 2048:
                scorer_score = self._score_compression_potential(text, byte_length, entropy, dict_hit_potential)
                # Score > 0.6: prefer Auralite, Score < 0.4: prefer BRIO, else use dict hits
                if scorer_score > 0.6 and CompressionMethod.AURALITE in available_strategies:
                    return CompressionMethod.AURALITE, scorer_score
                elif scorer_score < 0.4 and CompressionMethod.BRIO in available_strategies:
                    return CompressionMethod.BRIO, scorer_score
                # Fall through to standard logic for middle scores

            if dict_hit_potential > 0.15 and CompressionMethod.AURALITE in available_strategies:
                return CompressionMethod.AURALITE, scorer_score
            if entropy < 6.0 and CompressionMethod.BRIO in available_strategies:
                return CompressionMethod.BRIO, scorer_score
            if CompressionMethod.AURALITE in available_strategies:
                return CompressionMethod.AURALITE, scorer_score
            return CompressionMethod.UNCOMPRESSED, scorer_score

        if byte_length < 8192:
            # Large messages: prefer BRIO with fallback to Auralite
            if entropy < 6.5 and CompressionMethod.BRIO in available_strategies:
                return CompressionMethod.BRIO, scorer_score
            if CompressionMethod.AURALITE in available_strategies:
                return CompressionMethod.AURALITE, scorer_score
            if CompressionMethod.BRIO in available_strategies:
                return CompressionMethod.BRIO, scorer_score
            return CompressionMethod.UNCOMPRESSED, scorer_score

        if byte_length < 1_048_576:
            # Very large messages: strongly prefer BRIO
            if CompressionMethod.BRIO in available_strategies:
                return CompressionMethod.BRIO, scorer_score
            if CompressionMethod.AURALITE in available_strategies:
                return CompressionMethod.AURALITE, scorer_score
            return CompressionMethod.UNCOMPRESSED, scorer_score

        # Only consider AI semantic for truly large payloads
        if CompressionMethod.PATTERN_SEMANTIC in available_strategies:
            return CompressionMethod.PATTERN_SEMANTIC, scorer_score

        if CompressionMethod.BRIO in available_strategies:
            return CompressionMethod.BRIO, scorer_score

        return CompressionMethod.UNCOMPRESSED, scorer_score

    def _persist_scorer_telemetry(self,
                                  payload_size: int,
                                  entropy: float,
                                  dict_hit_rate: float,
                                  score: float,
                                  selected_method: CompressionMethod) -> None:
        """
        Persist scorer telemetry to CSV for offline analysis.
        """
        if score is None:
            return

        try:
            telemetry_path = self.scorer_telemetry_path
            telemetry_path.parent.mkdir(parents=True, exist_ok=True)

            write_header = (not self._scorer_header_written) or not telemetry_path.exists() or telemetry_path.stat().st_size == 0
            with telemetry_path.open("a", newline="", encoding="utf-8") as csvfile:
                writer = csv.writer(csvfile)
                if write_header:
                    writer.writerow([
                        "timestamp",
                        "payload_bytes",
                        "entropy",
                        "dictionary_hit_rate",
                        "score",
                        "selected_method",
                        "messages_seen",
                        "borderline_messages",
                        "global_borderline_ratio",
                        "window_borderline_ratio",
                        "scorer_enabled",
                        "auto_disabled",
                    ])
                    self._scorer_header_written = True
                global_ratio = (self._borderline_messages / self._messages_seen) if self._messages_seen else 0.0
                window_ratio = self._scorer_last_window_ratio
                writer.writerow([
                    datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z"),
                    payload_size,
                    f"{entropy:.6f}",
                    f"{dict_hit_rate:.6f}",
                    f"{score:.6f}",
                    selected_method.name if isinstance(selected_method, CompressionMethod) else str(selected_method),
                    self._messages_seen,
                    self._borderline_messages,
                    f"{global_ratio:.6f}",
                    f"{window_ratio:.6f}" if window_ratio is not None else "",
                    "1" if self.enable_scorer else "0",
                    "1" if self._scorer_auto_disabled else "0",
                ])
        except Exception:
            # Telemetry should never break compression logic
            pass

    def _record_message_statistics(self, byte_length: int) -> None:
        """Track overall vs borderline message mix for adaptive scorer gating."""
        self._messages_seen += 1
        self._scorer_window_total += 1

        if 400 <= byte_length <= 2048:
            self._borderline_messages += 1
            self._scorer_window_borderline += 1

        self._evaluate_scorer_gate()

    def _evaluate_scorer_gate(self) -> None:
        """Evaluate whether the scorer should remain enabled based on recent telemetry."""
        if not self._scorer_requested:
            return
        if not self.enable_scorer:
            return
        if self._scorer_window_total < self._scorer_eval_window:
            return

        total = self._scorer_window_total
        borderline = self._scorer_window_borderline
        ratio = borderline / total if total else 0.0
        self._scorer_last_window_ratio = ratio
        self._scorer_last_window_total = total

        if ratio < self._scorer_min_borderline_ratio:
            self.enable_scorer = False
            self._scorer_auto_disabled = True
            self._scorer_disabled_reason = (
                f"Borderline share {ratio:.1%} below threshold {self._scorer_min_borderline_ratio:.1%} "
                f"over last {total} messages; scorer auto-disabled."
            )
            self._scorer_status_recommendation = (
                "Workload rarely enters the 400-2048 byte borderline range. Keep the scorer disabled "
                "until traffic contains more medium-sized payloads or run targeted regression corpora."
            )
        else:
            self._scorer_status_recommendation = (
                f"Borderline share {ratio:.1%} meets threshold {self._scorer_min_borderline_ratio:.1%}; scorer remains enabled."
            )

        self._scorer_window_total = 0
        self._scorer_window_borderline = 0

    def get_scorer_status(self) -> Dict[str, Any]:
        """Expose current scorer status and adaptive gating metrics."""
        global_ratio = (self._borderline_messages / self._messages_seen) if self._messages_seen else 0.0
        return {
            "requested": self._scorer_requested,
            "enabled": bool(self.enable_scorer),
            "auto_disabled": self._scorer_auto_disabled,
            "disabled_reason": self._scorer_disabled_reason,
            "messages_seen": self._messages_seen,
            "borderline_messages": self._borderline_messages,
            "global_borderline_ratio": global_ratio,
            "evaluation_window": self._scorer_eval_window,
            "window_threshold": self._scorer_min_borderline_ratio,
            "last_window_ratio": self._scorer_last_window_ratio,
            "last_window_sample": self._scorer_last_window_total,
            "recommendation": self._scorer_status_recommendation,
        }

    def _hydrate_scorer_stats(self) -> None:
        """Load persisted scorer stats from telemetry CSV if available."""
        telemetry_path = self.scorer_telemetry_path
        if not telemetry_path.exists() or telemetry_path.stat().st_size == 0:
            return

        try:
            with telemetry_path.open("r", newline="", encoding="utf-8") as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    messages_val = row.get("messages_seen")
                    borderline_val = row.get("borderline_messages")
                    window_ratio_val = row.get("window_borderline_ratio")
                    auto_disabled_val = row.get("auto_disabled")

                    if messages_val:
                        try:
                            self._messages_seen = max(self._messages_seen, int(messages_val))
                        except ValueError:
                            pass
                    if borderline_val:
                        try:
                            self._borderline_messages = max(self._borderline_messages, int(borderline_val))
                        except ValueError:
                            pass
                    if window_ratio_val:
                        try:
                            self._scorer_last_window_ratio = float(window_ratio_val)
                        except ValueError:
                            pass
                    if auto_disabled_val in {"1", "true", "True"}:
                        self._scorer_auto_disabled = True
                        self._scorer_disabled_reason = (
                            self._scorer_disabled_reason
                            or "Scorer was auto-disabled in a previous run due to low borderline mix."
                        )
        except Exception:
            # Telemetry hydration is best-effort; ignore corrupt files
            pass

    @staticmethod
    def _read_int_env(name: str, default: int, min_value: int = 1) -> int:
        try:
            value = int(os.getenv(name, default))
            return max(value, min_value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _read_float_env(name: str, default: float, min_value: float = 0.0, max_value: float = 1.0) -> float:
        try:
            value = float(os.getenv(name, default))
            return max(min(value, max_value), min_value)
        except (TypeError, ValueError):
            return default

    def _calculate_entropy(self, text: str) -> float:
        """
        Calculate Shannon entropy of text (optimized)
        Returns value typically between 0 (no entropy) and 8 (max entropy for bytes)
        """
        if len(text) == 0:
            return 0.0

        sample = self._build_entropy_sample(text)
        cache_key = ("entropy", len(sample), sample)
        cached = self._metric_cache_get(self._entropy_cache, cache_key)
        if cached is not None:
            return cached

        char_counts = Counter(sample)

        entropy = 0.0
        length = len(sample)
        for count in char_counts.values():
            prob = count / length
            entropy -= prob * math.log2(prob)

        self._metric_cache_set(self._entropy_cache, cache_key, entropy)
        return entropy

    def _score_compression_potential(self, text: str, byte_length: int, entropy: float, dict_hit_rate: float) -> float:
        """
        Score compression potential for borderline payloads (lightweight ML assist)
        Returns score between 0.0 (prefer uncompressed) and 1.0 (prefer compression)

        This is a rules-backed scorer that provides intelligent method selection
        without the overhead of full ML model inference.

        Args:
            text: Message text
            byte_length: Message size in bytes
            entropy: Shannon entropy of the text
            dict_hit_rate: Dictionary hit rate potential

        Returns:
            Score between 0.0 and 1.0
        """
        score = 0.5  # neutral baseline

        # Factor 1: Size-based scoring (30% weight)
        # Messages in the 400-2048 byte range are borderline
        if 400 <= byte_length <= 2048:
            # Favor Auralite for medium-sized messages
            size_score = 0.7
        elif 2048 < byte_length <= 4096:
            # Transition zone - slightly favor BRIO
            size_score = 0.4
        elif byte_length > 4096:
            # Large messages strongly favor BRIO
            size_score = 0.2
        else:
            # Small messages
            size_score = 0.8

        score = score * 0.7 + size_score * 0.3

        # Factor 2: Entropy-based scoring (25% weight)
        # Lower entropy = more compressible
        if entropy < 4.0:
            entropy_score = 0.9  # Very compressible
        elif entropy < 5.5:
            entropy_score = 0.7  # Compressible
        elif entropy < 6.5:
            entropy_score = 0.5  # Moderately compressible
        else:
            entropy_score = 0.2  # Poorly compressible

        score = score * 0.75 + entropy_score * 0.25

        # Factor 3: Dictionary hit rate (25% weight)
        # Higher hit rate favors Auralite
        if dict_hit_rate > 0.25:
            dict_score = 0.9  # Strong dictionary potential
        elif dict_hit_rate > 0.15:
            dict_score = 0.7  # Good dictionary potential
        elif dict_hit_rate > 0.05:
            dict_score = 0.5  # Moderate dictionary potential
        else:
            dict_score = 0.3  # Low dictionary potential

        score = score * 0.75 + dict_score * 0.25

        # Factor 4: Repetition detection (20% weight)
        # Check for repeated patterns that compress well
        repetition_score = self._detect_repetition(text)
        score = score * 0.8 + repetition_score * 0.2

        return max(0.0, min(1.0, score))

    def _detect_repetition(self, text: str) -> float:
        """
        Detect repetitive patterns in text
        Returns score between 0.0 (no repetition) and 1.0 (high repetition)
        """
        if len(text) < 20:
            return 0.0

        # Sample for performance
        sample = text[:500] if len(text) > 500 else text

        # Count repeated 3-char sequences
        trigrams = {}
        for i in range(len(sample) - 2):
            trigram = sample[i:i+3]
            trigrams[trigram] = trigrams.get(trigram, 0) + 1

        if not trigrams:
            return 0.0

        # Calculate repetition ratio
        max_count = max(trigrams.values())
        total_trigrams = len(sample) - 2
        repetition_ratio = max_count / total_trigrams if total_trigrams > 0 else 0.0

        # Normalize to 0-1 range
        return min(1.0, repetition_ratio * 3.0)

    def _estimate_dictionary_hit_rate(self, text: str) -> float:
        """
        Estimate potential dictionary hit rate based on common patterns (optimized)
        Returns value between 0.0 (no hits) and 1.0 (all hits)
        """
        if len(text) < 10:
            return 0.0

        segments = self._build_dictionary_samples(text)
        total_length = sum(len(segment) for segment in segments)
        if total_length == 0:
            return 0.0

        cache_key = ("dict", total_length, tuple(segments))
        cached = self._metric_cache_get(self._dict_hit_cache, cache_key)
        if cached is not None:
            return cached

        json_chars = 0
        xml_chars = 0
        found_words = set()
        common_words = [
            'the ',
            ' and ',
            ' for ',
            ' that ',
            ' with ',
            'data',
            'message',
            'error',
            'request',
            'response',
            'status',
        ]

        for segment in segments:
            json_chars += sum(1 for c in segment if c in '{}[]":,')
            xml_chars += sum(1 for c in segment if c in '<>/=')

            lower_segment = segment.lower()
            for word in common_words:
                if word in lower_segment:
                    found_words.add(word)

        structural_ratio = (json_chars + xml_chars) / total_length
        word_ratio = len(found_words) * 0.05  # Each unique word adds 5%

        # Combine ratios (balanced structural + lexical weighting)
        total_ratio = (structural_ratio * 0.7) + (word_ratio * 0.3)

        total_ratio = min(1.0, total_ratio)
        self._metric_cache_set(self._dict_hit_cache, cache_key, total_ratio)
        return total_ratio

    def _build_entropy_sample(self, text: str) -> str:
        """Build text sample used for entropy calculation."""
        if len(text) <= 1000:
            return text
        sample_size = 333
        midpoint = len(text) // 2
        return (
            text[:sample_size]
            + text[midpoint - sample_size // 2: midpoint + sample_size // 2]
            + text[-sample_size:]
        )

    def _build_dictionary_samples(self, text: str) -> List[str]:
        """Build sampled segments used for dictionary hit estimation."""
        if len(text) <= 600:
            return [text]
        segment_size = min(300, max(60, len(text) // 10))
        mid_start = max(0, (len(text) // 2) - (segment_size // 2))
        return [
            text[:segment_size],
            text[mid_start:mid_start + segment_size],
            text[-segment_size:],
        ]

    def _metric_cache_get(self, cache: OrderedDict, key: Any) -> Optional[float]:
        """Retrieve cached metric and refresh LRU ordering."""
        value = cache.get(key)
        if value is not None:
            cache.move_to_end(key)
        return value

    def _metric_cache_set(self, cache: OrderedDict, key: Any, value: float) -> None:
        """Store metric with bounded cache size."""
        cache[key] = value
        cache.move_to_end(key)
        if len(cache) > self._METRIC_CACHE_LIMIT:
            cache.popitem(last=False)

    def _is_likely_incompressible(self, text: str) -> bool:
        """
        Quick heuristic to detect if text is likely incompressible.
        Treats short payloads as compressible when they are repetitive or
        match common telemetry tokens so Auralite can still be considered.
        """
        if not text:
            return True

        length = len(text)
        lower_text = text.lower()
        normalized_short = lower_text.strip(" .,;:-_")

        if length <= 3:
            # Repeat-heavy or known tokens ("ok", "yes") are compressible even if tiny
            if length > 1 and len(set(text)) == 1:
                return False
            if normalized_short in _SHORT_COMPRESSIBLE_TOKENS:
                return False
            return True

        entropy = self._calculate_entropy(text)

        if length < 10:
            char_counts = Counter(text)
            most_common_ratio = max(char_counts.values()) / length if char_counts else 0.0

            def has_repeating_unit(value: str) -> bool:
                limit = len(value)
                for unit in range(1, (limit // 2) + 1):
                    if limit % unit == 0 and value == value[:unit] * (limit // unit):
                        return True
                return False

            if (
                most_common_ratio >= 0.7
                or has_repeating_unit(lower_text)
                or normalized_short in _SHORT_COMPRESSIBLE_TOKENS
                or entropy <= 2.5
            ):
                return False
            return True

        # High entropy indicates random-like data that will not compress well
        return entropy > 7.0

    def validate_compression_result(self, original: str, compressed: bytes, metadata: dict) -> bool:
        """
        Validate that compressed data can be decompressed correctly
        """
        try:
            decompressed, _ = self.compression_engine.decompress(compressed)
            return decompressed == original
        except Exception:
            return False

    def _compress_with_partial_templates(
        self,
        text: str,
        partial_matches: List[TemplateMatch],
        target_method: CompressionMethod,
    ) -> Tuple[bytes, dict]:
        """
        Compress text using partial template matches.

        Strategy:
        1. Use the best partial match for template compression
        2. For leftover data (prefix/suffix), fall back to UNCOMPRESSED if too small
        3. Otherwise run the fallback encoder appropriate for ``target_method``
        4. Track match coverage and compression effectiveness in metadata

        Args:
            text: Original text to compress
            partial_matches: Partial template matches found for ``text``
            target_method: Compression method we are attempting (drives fallback)

        Returns:
            Tuple of (compressed_bytes, metadata_dict)
        """
        best_match = max(partial_matches, key=lambda m: m.end - m.start)

        start = best_match.start or 0
        end = best_match.end or start
        match_length = max(0, end - start)

        if match_length == 0:
            return self.compression_engine.compress_uncompressed(text)

        prefix = text[:start]
        suffix = text[end:]
        leftover_bytes = len(prefix.encode('utf-8')) + len(suffix.encode('utf-8'))
        match_coverage = match_length / len(text) if text else 0.0

        if leftover_bytes == 0:
            try:
                compressed, metadata = self.compression_engine.compress_binary_semantic(text, best_match)
                metadata.update({
                    'partial_match': True,
                    'match_coverage': match_coverage,
                    'leftover_bytes': leftover_bytes,
                    'leftover_strategy': 'exact_match',
                    'template_id': best_match.template_id,
                    'target_method': target_method.name.lower(),
                })
                return compressed, metadata
            except Exception:
                pass

        if leftover_bytes <= self._PARTIAL_UNCOMPRESSED_THRESHOLD:
            compressed, metadata = self.compression_engine.compress_uncompressed(text)
            metadata.update({
                'partial_match': True,
                'match_coverage': match_coverage,
                'leftover_bytes': leftover_bytes,
                'leftover_strategy': 'uncompressed_fallback',
                'template_id': best_match.template_id,
                'target_method': target_method.name.lower(),
            })
            return compressed, metadata

        if target_method == CompressionMethod.BRIO:
            compressed, metadata = self.compression_engine.compress_brio(text)
            fallback_strategy = 'brio_fallback'
        elif target_method == CompressionMethod.AURALITE:
            compressed, metadata = self.compression_engine.compress_auralite(text)
            fallback_strategy = 'auralite_fallback'
        elif target_method == CompressionMethod.BINARY_SEMANTIC:
            # No hybrid support yet; prefer auralite over binary partial payloads
            compressed, metadata = self.compression_engine.compress_auralite(text)
            fallback_strategy = 'auralite_fallback'
        else:
            compressed, metadata = self.compression_engine.compress_uncompressed(text)
            fallback_strategy = 'uncompressed_fallback'

        metadata.update({
            'partial_match': True,
            'match_coverage': match_coverage,
            'leftover_bytes': leftover_bytes,
            'leftover_strategy': fallback_strategy,
            'template_id': best_match.template_id,
            'target_method': target_method.name.lower(),
            'note': 'Partial match detected; hybrid compression not yet implemented',
        })
        return compressed, metadata
