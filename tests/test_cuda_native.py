#!/usr/bin/env python3
"""Tests for AURA's optional CUDA-native backend."""

from __future__ import annotations

import math

import pytest

from aura_compression.brio_full import BrioDecoder, BrioEncoder
from aura_compression.compression_engine import CompressionEngine
from aura_compression.compression_strategy_manager import CompressionStrategyManager
from aura_compression.cuda_native import (
    CudaNativeBackend,
    cpu_lz_match_candidates,
    cpu_rolling_hash3,
    cpu_shannon_entropy,
)
from aura_compression.performance_optimizer import PerformanceOptimizer
from aura_compression.templates import TemplateLibrary


def test_cpu_entropy_reference_known_values():
    assert cpu_shannon_entropy(b"") == 0.0
    assert cpu_shannon_entropy(b"aaaaaaaa") == 0.0
    assert math.isclose(cpu_shannon_entropy(b"01010101"), 1.0)


def test_cuda_backend_status_is_safe_without_cuda_library():
    status = CudaNativeBackend(library_path="/definitely/missing/libaura_cuda.so").status()
    assert status.available is False
    assert status.error


def test_cuda_entropy_matches_cpu_reference_when_available():
    backend = CudaNativeBackend()
    if not backend.is_available():
        pytest.skip(f"CUDA native backend unavailable: {backend.status().error}")

    payload = (b"AURA CUDA native entropy path " * 256) + bytes(range(256))
    assert sum(backend.byte_histogram(payload)) == len(payload)
    assert math.isclose(
        backend.shannon_entropy(payload),
        cpu_shannon_entropy(payload),
        rel_tol=1e-9,
        abs_tol=1e-9,
    )


def test_cpu_rolling_hash_and_lz_candidate_references():
    assert cpu_rolling_hash3(b"") == []
    assert cpu_rolling_hash3(b"ab") == []
    assert len(cpu_rolling_hash3(b"abcd")) == 2

    payload = b"ABCDEFGH" + b"ABCDEFGH" + b"ABCD"
    candidates = cpu_lz_match_candidates(payload, window_size=32, min_match=4, max_match=8)
    assert candidates[8] == (8, 8)
    assert candidates[16] == (8, 4)


def test_cuda_rolling_hash_and_lz_candidates_match_cpu_when_available():
    backend = CudaNativeBackend()
    if not backend.is_available():
        pytest.skip(f"CUDA native backend unavailable: {backend.status().error}")

    payload = (b"AURA-CUDA-LZ77:" * 8) + b"tail" + (b"AURA-CUDA-LZ77:" * 4)
    assert backend.rolling_hash3(payload) == cpu_rolling_hash3(payload)
    assert backend.lz_match_candidates(
        payload,
        window_size=64,
        min_match=4,
        max_match=32,
    ) == cpu_lz_match_candidates(
        payload,
        window_size=64,
        min_match=4,
        max_match=32,
    )


def test_cuda_brio_lz_fast_path_roundtrips_when_enabled(monkeypatch):
    backend = CudaNativeBackend()
    if not backend.is_available():
        pytest.skip(f"CUDA native backend unavailable: {backend.status().error}")

    monkeypatch.setenv("AURA_ENABLE_CUDA_BRIO", "1")
    monkeypatch.setenv("AURA_CUDA_BRIO_MIN_BYTES", "1")
    text = ("sensor=alpha value=42 status=ok\n" * 512) + "done"

    compressed = BrioEncoder().compress(text)
    decoded = BrioDecoder().decompress(compressed.payload)

    assert decoded.text == text
    assert any(token.__class__.__name__ == "MatchToken" for token in compressed.tokens)


def test_performance_optimizer_reports_cuda_status():
    optimizer = PerformanceOptimizer()
    stats = optimizer.get_performance_stats()
    assert "hardware_acceleration" in stats
    assert "cuda" in stats
    assert "entropy_acceleration" in stats


def test_strategy_manager_accepts_accelerated_entropy_path():
    class FakeOptimizer:
        def calculate_entropy_text(self, text: str) -> float:
            return 3.25

    template_library = TemplateLibrary()
    engine = CompressionEngine(template_library=template_library, enable_sql_cache=False)
    manager = CompressionStrategyManager(
        compression_engine=engine,
        algorithm_selector=None,
        template_manager=type("TemplateManager", (), {"template_library": template_library})(),
        performance_optimizer=FakeOptimizer(),
    )

    assert manager._calculate_entropy("x" * 1024) == 3.25
