#!/usr/bin/env python3
"""
Compression Strategy Manager - Manages compression strategies and method selection
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

from aura_compression.templates import TemplateMatch
from aura_compression.compression_engine import CompressionEngine


class CompressionStrategyManager:
    """
    Manages compression strategies and method selection
    """

    def __init__(self,
                 compression_engine: CompressionEngine,
                 algorithm_selector: Any,
                 template_manager: Any,
                 performance_optimizer: Any):
        """
        Initialize strategy manager
        """
        self.compression_engine = compression_engine
        self.algorithm_selector = algorithm_selector
        self.template_manager = template_manager
        self.performance_optimizer = performance_optimizer

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
                    if template_match is None:
                        continue
                    compressed, metadata = self.compression_engine.compress_binary_semantic(text, template_match)
                elif strategy == CompressionMethod.AURA_LITE:
                    compressed, metadata = self.compression_engine.compress_aura_lite(text)
                elif strategy == CompressionMethod.AURALITE:
                    compressed, metadata = self.compression_engine.compress_auralite(text)
                elif strategy == CompressionMethod.BRIO:
                    compressed, metadata = self.compression_engine.compress_brio(text)
                elif strategy == CompressionMethod.AI_SEMANTIC:
                    compressed, metadata = self.compression_engine.compress_ai_semantic(text)
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

        return best_result

    def compress_with_method(self,
                            text: str,
                            method: CompressionMethod,
                            template_match: Optional[TemplateMatch] = None) -> Tuple[bytes, dict]:
        """
        Compress using a specific method
        """
        if method == CompressionMethod.BINARY_SEMANTIC:
            if template_match is None:
                raise ValueError("Template match required for BINARY_SEMANTIC")
            return self.compression_engine.compress_binary_semantic(text, template_match)
        elif method == CompressionMethod.AURA_LITE:
            return self.compression_engine.compress_aura_lite(text)
        elif method == CompressionMethod.AURALITE:
            return self.compression_engine.compress_auralite(text)
        elif method == CompressionMethod.BRIO:
            return self.compression_engine.compress_brio(text)
        elif method == CompressionMethod.AI_SEMANTIC:
            return self.compression_engine.compress_ai_semantic(text)
        elif method == CompressionMethod.UNCOMPRESSED:
            return self.compression_engine.compress_uncompressed(text)
        else:
            raise ValueError(f"Unsupported compression method: {method}")

    def select_optimal_strategy(self,
                               text: str,
                               available_strategies: List[CompressionMethod],
                               template_match: Optional[TemplateMatch] = None) -> CompressionMethod:
        """
        Select the optimal compression strategy for the given text
        """
        if not available_strategies:
            return CompressionMethod.UNCOMPRESSED

        # Use ML algorithm selector if available
        if self.algorithm_selector:
            try:
                selected = self.algorithm_selector.select_algorithm(text, available_strategies)
                if selected in available_strategies:
                    return selected
            except Exception:
                pass

        # Fallback: try strategies in order and pick the best
        best_method = CompressionMethod.UNCOMPRESSED
        best_ratio = 0.0

        for method in available_strategies:
            try:
                _, metadata = self.compress_with_method(text, method, template_match)
                ratio = metadata.get('ratio', 0.0)
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_method = method
            except Exception:
                continue

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
        except:
            pass

        try:
            # AURA_LITE requires AuraLite encoder
            if hasattr(self.compression_engine, '_aura_lite_encoder') and self.compression_engine._aura_lite_encoder:
                strategies.append(CompressionMethod.AURA_LITE)
                strategies.append(CompressionMethod.AURALITE)
        except:
            pass

        try:
            # BRIO requires BRIO encoder
            if hasattr(self.compression_engine, '_aura_encoder') and self.compression_engine._aura_encoder:
                strategies.append(CompressionMethod.BRIO)
        except:
            pass

        try:
            # AI_SEMANTIC requires AI semantic compressor
            if hasattr(self.compression_engine, '_ai_semantic_compressor') and self.compression_engine._ai_semantic_compressor:
                strategies.append(CompressionMethod.AI_SEMANTIC)
        except:
            pass

        return strategies

    def validate_compression_result(self, original: str, compressed: bytes, metadata: dict) -> bool:
        """
        Validate that compressed data can be decompressed correctly
        """
        try:
            decompressed, _ = self.compression_engine.decompress(compressed)
            return decompressed == original
        except Exception:
            return False