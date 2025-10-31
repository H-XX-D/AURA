#!/usr/bin/env python3
"""Synthetic network traffic smoke test for the hybrid compressor."""

from __future__ import annotations

import random
from pathlib import Path
from typing import Generator

from aura_compression.compressor_refactored import ProductionHybridCompressor


def _message_stream(seed: int = 1337, count: int = 150) -> Generator[str, None, None]:
    """Generate synthetic network-style messages."""
    rng = random.Random(seed)

    users = [f"user{idx}@example.com" for idx in range(1, 8)]
    endpoints = ["/api/users", "/api/orders", "/api/login", "/api/settings"]
    ip_blocks = [f"10.0.{i}.{j}" for i in range(1, 4) for j in range(1, 4)]
    topics = ["compression", "security", "latency", "reinforcement learning"]

    for idx in range(count):
        msg_type = rng.choice(["api", "log", "chat", "binary"])
        if msg_type == "api":
            yield (
                f'{{"method": "{rng.choice(["GET", "POST", "PUT"])}", '
                f'"endpoint": "{rng.choice(endpoints)}/{rng.randint(1, 9999)}", '
                f'"headers": {{"Authorization": "Bearer TOKEN{rng.randint(1, 99999)}", '
                f'"Content-Type": "application/json"}}, '
                f'"body": {{"user": "{rng.choice(users)}", "value": {rng.random():.3f}}}}}'
            )
        elif msg_type == "log":
            yield (
                f"[2025-04-01T12:{rng.randint(0,59):02d}:00Z] "
                f"INFO ip={rng.choice(ip_blocks)} "
                f"user={rng.choice(users)} latency={rng.randint(20,200)}ms "
                f"status={rng.choice([200, 202, 500, 503])}"
            )
        elif msg_type == "chat":
            yield (
                f"User feedback: I think we should focus on {rng.choice(topics)} "
                f"because throughput dropped to {rng.uniform(0.1, 1.5):.2f} MB/s yesterday."
            )
        else:  # binary placeholder
            payload = "".join(rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789") for _ in range(48))
            yield f"data:image/png;base64,{payload}"


def _build_compressor(tmp_path: Path) -> ProductionHybridCompressor:
    cache_dir = tmp_path / "network_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return ProductionHybridCompressor(
        enable_aura=False,
        enable_audit_logging=False,
        template_cache_dir=str(cache_dir),
        template_sync_interval_seconds=None,
        enable_fast_path=True,
    )


def test_synthetic_network_simulation(tmp_path: Path):
    compressor = _build_compressor(tmp_path)

    methods = set()
    ratios = []
    binary_semantic_hits = 0

    for message in _message_stream(count=120):
        payload, method, metadata = compressor.compress(message)
        restored = compressor.decompress(payload)
        assert restored == message

        methods.add(method.name)
        ratios.append(metadata.get("ratio", 1.0))
        if method.name == "BINARY_SEMANTIC":
            binary_semantic_hits += 1

    compressor.template_library.shutdown()

    assert len(methods) >= 2
    assert binary_semantic_hits >= 1
    assert sum(ratios) / len(ratios) > 0.5
