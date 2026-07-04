#!/usr/bin/env python3
"""
Performance Optimizer - Handles SIMD, GPU acceleration
Extracted from the monolithic ProductionHybridCompressor
"""

import json
import os
import re
import struct
from collections import Counter
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from aura_compression.enums import (
    _SEMANTIC_PREVIEW_LIMIT,
    _SEMANTIC_TOKEN_LIMIT,
    _SEMANTIC_TOKEN_PATTERN,
    TEMPLATE_METADATA_KIND,
    CompressionMethod,
)


class PerformanceOptimizer:
    """
    Handles performance optimizations for compression
    """

    def __init__(self):
        """
        Initialize performance optimizer
        """
        self._cuda_backend = None
        self._cuda_status = {
            "available": False,
            "library_path": None,
            "device_count": 0,
            "device_name": None,
            "error": "not loaded",
        }
        self._cuda_min_bytes = int(os.getenv("AURA_CUDA_MIN_BYTES", "512"))
        # Initialize accelerators
        self._load_accelerators()

    def _load_accelerators(self):
        """
        Load available accelerators
        """
        if os.getenv("AURA_DISABLE_CUDA", "").lower() in {"1", "true", "yes", "on"}:
            self._cuda_status = {
                **self._cuda_status,
                "error": "disabled by AURA_DISABLE_CUDA",
            }
            return

        try:
            from aura_compression.cuda_native import CudaNativeBackend

            backend = CudaNativeBackend()
            status = backend.status()
            self._cuda_status = status.as_dict()
            if status.available:
                self._cuda_backend = backend
        except Exception as exc:
            self._cuda_backend = None
            self._cuda_status = {
                **self._cuda_status,
                "error": str(exc),
            }

    def optimize_compression(self, text: str, method: CompressionMethod) -> str:
        """
        Apply performance optimizations to text before compression
        """
        # Hardware acceleration removed - return text as-is
        return text

    def get_performance_stats(self) -> dict:
        """
        Get performance statistics
        """
        return {
            "hardware_acceleration": self._cuda_backend is not None,
            "cuda": self._cuda_status,
            "entropy_acceleration": self._cuda_backend is not None,
        }

    def is_accelerated(self, method: CompressionMethod) -> bool:
        """
        Check if a compression method can be accelerated
        """
        return self._cuda_backend is not None and method in {
            CompressionMethod.UNCOMPRESSED,
            CompressionMethod.AURALITE,
            CompressionMethod.BRIO,
            CompressionMethod.PATTERN_SEMANTIC,
        }

    def calculate_entropy_text(self, text: str) -> Optional[float]:
        """
        Calculate byte-level Shannon entropy through CUDA when available.

        Returns None when CUDA is unavailable or not worth dispatching so callers
        can use their existing CPU implementation without changing semantics.
        """
        if self._cuda_backend is None or not text:
            return None

        payload = text.encode("utf-8")
        if len(payload) < self._cuda_min_bytes:
            return None

        try:
            return self._cuda_backend.shannon_entropy(payload)
        except Exception as exc:
            self._cuda_status = {
                **self._cuda_status,
                "available": False,
                "error": str(exc),
            }
            self._cuda_backend = None
            return None

    def get_optimal_batch_size(self, method: CompressionMethod, text_length: int) -> int:
        """
        Get optimal batch size for the given method and text length
        """
        # Hardware acceleration removed - use simple batch sizing
        if text_length < 1000:
            return 10
        elif text_length < 10000:
            return 50
        else:
            return 100

    def warmup_accelerators(self):
        """
        Warm up accelerators for better performance
        """
        # Hardware acceleration removed - no warmup needed
        pass

    def cleanup_accelerators(self):
        """
        Clean up accelerator resources
        """
        # CUDA runtime resources are owned by the native library process context.
        pass
