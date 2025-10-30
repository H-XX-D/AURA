#!/usr/bin/env python3
"""
Performance Optimizer - Handles SIMD, GPU acceleration, and fuzzy matching
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


class PerformanceOptimizer:
    """
    Handles performance optimizations including SIMD, GPU acceleration, and fuzzy matching
    """

    def __init__(self,
                 enable_simd: bool = True,
                 enable_gpu: bool = True,
                 enable_fuzzy: bool = True,
                 fuzzy_threshold: float = 0.8):
        """
        Initialize performance optimizer
        """
        self.enable_simd = enable_simd
        self.enable_gpu = enable_gpu
        self.enable_fuzzy = enable_fuzzy
        self.fuzzy_threshold = fuzzy_threshold

        # Initialize accelerators
        self._simd_accelerator = None
        self._gpu_accelerator = None
        self._fuzzy_matcher = None

        self._load_accelerators()

    def _load_accelerators(self):
        """
        Load available accelerators
        """
        try:
            if self.enable_simd:
                from aura_compression.simd_accelerator import SimdAccelerator
                self._simd_accelerator = SimdAccelerator()
        except ImportError:
            self._simd_accelerator = None

        try:
            if self.enable_gpu:
                from aura_compression.gpu_accelerator_service import GpuAcceleratorService
                self._gpu_accelerator = GpuAcceleratorService()
        except ImportError:
            self._gpu_accelerator = None

        try:
            if self.enable_fuzzy:
                from aura_compression.fuzzy_matcher import FuzzyMatcher
                self._fuzzy_matcher = FuzzyMatcher(min_similarity=self.fuzzy_threshold)
        except ImportError:
            self._fuzzy_matcher = None

    def optimize_compression(self, text: str, method: CompressionMethod) -> str:
        """
        Apply performance optimizations to text before compression
        """
        optimized_text = text

        # Apply SIMD optimizations if available
        if self._simd_accelerator and method in [CompressionMethod.BRIO, CompressionMethod.AURA_HEAVY]:
            try:
                optimized_text = self._simd_accelerator.optimize_text(optimized_text)
            except Exception:
                pass  # Fall back to original text

        # Apply GPU optimizations if available
        if self._gpu_accelerator and method == CompressionMethod.AURA_HEAVY:
            try:
                optimized_text = self._gpu_accelerator.optimize_text(optimized_text)
            except Exception:
                pass  # Fall back to original text

        return optimized_text

    def find_similar_texts(self, text: str, candidates: List[str]) -> List[Tuple[str, float]]:
        """
        Find similar texts using fuzzy matching
        """
        if not self._fuzzy_matcher:
            return []

        try:
            return self._fuzzy_matcher.find_similar(text, candidates)
        except Exception:
            return []

    def get_performance_stats(self) -> dict:
        """
        Get performance statistics
        """
        stats = {
            'simd_enabled': self._simd_accelerator is not None,
            'gpu_enabled': self._gpu_accelerator is not None,
            'fuzzy_enabled': self._fuzzy_matcher is not None,
        }

        # Get accelerator-specific stats
        if self._simd_accelerator:
            try:
                stats.update(self._simd_accelerator.get_stats())
            except Exception:
                pass

        if self._gpu_accelerator:
            try:
                stats.update(self._gpu_accelerator.get_stats())
            except Exception:
                pass

        if self._fuzzy_matcher:
            try:
                stats.update(self._fuzzy_matcher.get_stats())
            except Exception:
                pass

        return stats

    def is_accelerated(self, method: CompressionMethod) -> bool:
        """
        Check if a compression method can be accelerated
        """
        if method in [CompressionMethod.BRIO, CompressionMethod.AURA_HEAVY]:
            return (self._simd_accelerator is not None or
                   self._gpu_accelerator is not None)
        return False

    def get_optimal_batch_size(self, method: CompressionMethod, text_length: int) -> int:
        """
        Get optimal batch size for the given method and text length
        """
        base_batch_size = 100  # Default

        # Adjust based on accelerators
        if self._gpu_accelerator and method == CompressionMethod.AURA_HEAVY:
            # GPU benefits from larger batches
            base_batch_size = 1000
        elif self._simd_accelerator and method in [CompressionMethod.BRIO, CompressionMethod.AURA_HEAVY]:
            # SIMD benefits from medium batches
            base_batch_size = 500

        # Adjust based on text length
        if text_length < 1000:
            batch_size = min(base_batch_size, 10)
        elif text_length < 10000:
            batch_size = min(base_batch_size, 50)
        else:
            batch_size = base_batch_size

        return batch_size

    def warmup_accelerators(self):
        """
        Warm up accelerators for better performance
        """
        if self._simd_accelerator:
            try:
                self._simd_accelerator.warmup()
            except Exception:
                pass

        if self._gpu_accelerator:
            try:
                self._gpu_accelerator.warmup()
            except Exception:
                pass

    def cleanup_accelerators(self):
        """
        Clean up accelerator resources
        """
        if self._simd_accelerator:
            try:
                self._simd_accelerator.cleanup()
            except Exception:
                pass

        if self._gpu_accelerator:
            try:
                self._gpu_accelerator.cleanup()
            except Exception:
                pass