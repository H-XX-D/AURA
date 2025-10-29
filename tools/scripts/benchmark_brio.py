#!/usr/bin/env python3
"""Benchmark AURA experimental compression against plain Brotli."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Iterable

import brotli

ROOT = Path(__file__).resolve().parent.parent

import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aura_compression.compressor import ProductionHybridCompressor


def iter_messages(paths: Iterable[Path]) -> Iterable[str]:
    for path in paths:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            stripped = line.strip()
            if stripped.startswith("Message:"):
                yield stripped.partition("Message:")[2].strip()


def benchmark(messages: list[str]) -> dict:
    compressor = ProductionHybridCompressor(enable_aura=True, aura_preference_margin=-1)

    stats = {
        "samples": len(messages),
        "brotli": {"encode_ms": 0.0, "decode_ms": 0.0, "sizes": []},
        "aura": {
            "encode_ms": 0.0,
            "decode_ms": 0.0,
            "metadata_iter_ms": 0.0,
            "sizes": [],
            "metadata_entries": [],
            "fast_path_candidates": 0,
        },
    }

    for message in messages:
        raw = message.encode("utf-8")

        start = time.perf_counter()
        brotli_payload = brotli.compress(raw)
        stats["brotli"]["encode_ms"] += (time.perf_counter() - start) * 1000

        start = time.perf_counter()
        _ = brotli.decompress(brotli_payload)
        stats["brotli"]["decode_ms"] += (time.perf_counter() - start) * 1000
        stats["brotli"]["sizes"].append(len(brotli_payload))

        start = time.perf_counter()
        payload, method_enum, metadata = compressor.compress(message)
        stats["aura"]["encode_ms"] += (time.perf_counter() - start) * 1000
        stats["aura"]["sizes"].append(len(payload))
        stats["aura"]["metadata_entries"].append(len(metadata.get("metadata_entries", [])))
        if metadata.get("fast_path_candidate"):
            stats["aura"]["fast_path_candidates"] += 1

        start = time.perf_counter()
        _, decoded_meta = compressor.decompress(payload, return_metadata=True)
        stats["aura"]["decode_ms"] += (time.perf_counter() - start) * 1000

        start = time.perf_counter()
        _ = sum(1 for _ in decoded_meta.get("metadata_entries", []))
        stats["aura"]["metadata_iter_ms"] += (time.perf_counter() - start) * 1000

    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--messages",
        type=int,
        default=200,
        help="Number of messages sampled from audit logs",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("logs/benchmark_brio.json"),
        help="Where to write aggregated metrics",
    )
    args = parser.parse_args()

    audit_logs = list((ROOT / "audit").glob("*.log"))
    if not audit_logs:
        print("No audit logs found; run streaming integration first.")
        return
    messages = list(iter_messages(audit_logs))[: args.messages]
    if not messages:
        print("No messages extracted from audit logs.")
        return
    stats = benchmark(messages)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print(f"Wrote benchmark results to {args.output}")


if __name__ == "__main__":
    main()
