#!/usr/bin/env python3
"""Simulate sidechain usage with network-style payloads and streaming logs.

This script creates synthetic payloads, compresses them with sidechain
write-back enabled, then "streams" the payloads to a client by running the
hybrid decompressor and printing ingress logs.

Usage:
    python scripts/sidechain_network_sim.py [output_dir]

Use --count and --total-bytes to control payload volume. --retrieve-bytes stops
the client replay once the requested amount of data has been read back. If no
output directory is provided, ./sidechain_demo is used.
"""

from __future__ import annotations

import os
import random
import string
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from aura_compression.compressor import ProductionHybridCompressor
from aura_compression.sidechain import SidechainConfig

DEFAULT_COUNT = 22
DEFAULT_TOTAL_BYTES = 1 << 20  # ~1 MiB
DEFAULT_DIR = Path("./sidechain_demo")
RANDOM_SEED = 1337


def _make_payload_text(index: int, target_size: int) -> str:
    """Return a deterministic text payload of approximately target_size bytes."""
    header = f"Payload {index:02d}: synthetic telemetry stream. "
    random.seed(RANDOM_SEED + index)
    chunks: List[str] = [header]
    charset = string.ascii_letters + string.digits + " _-:,."  # safe ASCII
    while sum(len(chunk) for chunk in chunks) < target_size:
        chunk_len = min(80, target_size - sum(len(c) for c in chunks))
        chunk = "".join(random.choice(charset) for _ in range(chunk_len))
        chunks.append(chunk)
    text = "".join(chunks)
    return text[:target_size]


def _prepare_payloads(base_dir: Path, count: int, total_bytes: int) -> Iterable[Tuple[Path, str]]:
    payload_dir = base_dir / "payloads"
    payload_dir.mkdir(parents=True, exist_ok=True)

    base_size = total_bytes // count
    remainder = total_bytes % count
    for i in range(count):
        size = base_size + (1 if i < remainder else 0)
        text = _make_payload_text(i, size)
        path = payload_dir / f"payload_{i:02d}.txt"
        path.write_text(text, encoding="utf-8")
        yield path, text


def _log(message: str) -> None:
    print(message)


def main(
    output_dir: Path,
    payload_count: int,
    total_bytes: int,
    retrieve_bytes: Optional[int],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    db_path = output_dir / "sidechain.db"
    blob_dir = output_dir / "blobs"

    _log(f"Preparing synthetic payloads in {output_dir.resolve()}")
    payloads = list(_prepare_payloads(output_dir, payload_count, total_bytes))

    config = SidechainConfig(
        enabled=True,
        db_path=str(db_path),
        blob_dir=str(blob_dir),
        inline_threshold=4 * 1024,
        blob_threshold=64 * 1024,
    )

    compressor = ProductionHybridCompressor(
        min_compression_size=0,
        enable_audit_logging=False,
        enable_sidechain=True,
        sidechain_config={
            "db_path": config.db_path,
            "blob_dir": config.blob_dir,
            "inline_threshold": config.inline_threshold,
            "blob_threshold": config.blob_threshold,
        },
    )

    _log("Compressing payloads with sidechain enabled...")
    compressed_records: List[Tuple[bytes, dict]] = []
    for path, text in payloads:
        data, method, metadata = compressor.compress(text)
        compressed_records.append((data, metadata))
        _log(
            f"  - {path.name}: method={method.name} ratio={metadata.get('ratio', 0):.2f}:1"
            f" sidechain_ref={metadata.get('sidechain_ref', 'n/a')}"
        )

    _log("\nStreaming back to client and logging ingress...")
    retrieved_bytes = 0
    for idx, (payload, metadata) in enumerate(compressed_records, start=1):
        plaintext, stream_meta = compressor.decompress(payload, return_metadata=True)
        sideref = metadata.get("sidechain_ref", "n/a")
        _log(
            f"[client] message={idx:02d} length={len(plaintext)} method={stream_meta['method']}"
            f" sidechain_ref={sideref}"
        )
        sketch = metadata.get("semantic_sketch", {})
        preview = sketch.get("preview")
        if preview:
            tokens = sketch.get("top_tokens") or []
            token_view = ",".join(tokens[:3])
            _log(
                f"         sketch.preview=\"{preview}\" tokens={token_view if token_view else 'n/a'}"
            )
        retrieved_bytes += len(plaintext)
        if retrieve_bytes is not None and retrieved_bytes >= retrieve_bytes:
            _log(
                f"Reached retrieval goal ({retrieve_bytes} bytes)."
            )
            break

    sidechain = compressor._sidechain  # type: ignore[attr-defined]
    if sidechain.is_enabled:
        records = sidechain.fetch_recent(limit=payload_count)
        inline = sum(1 for r in records if r["storage_kind"] == "inline")
        blob = sum(1 for r in records if r["storage_kind"] == "blob")
        external = sum(1 for r in records if r["storage_kind"] == "external")
        _log(
            "\nSidechain summary: "
            f"inline={inline} blob={blob} external={external} total={len(records)}"
        )
        _log(f"Sidechain DB located at {db_path.resolve()}")
        if records:
            latest = records[0]["metadata"].get("semantic_sketch", {})
            preview = latest.get("preview")
            if preview:
                tokens = latest.get("top_tokens") or []
                token_view = ",".join(tokens[:3])
                _log(
                    f"Latest semantic sketch preview=\"{preview}\" tokens={token_view if token_view else 'n/a'}"
                )
    else:
        _log("Sidechain disabled; nothing stored.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Sidechain network simulation")
    parser.add_argument("output", nargs="?", default=str(DEFAULT_DIR), help="Output directory for demo artifacts")
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT, help="Number of payloads to generate (default: 22)")
    parser.add_argument(
        "--total-bytes",
        type=int,
        default=DEFAULT_TOTAL_BYTES,
        help="Total bytes distributed across payloads (default: 1 MiB)",
    )
    parser.add_argument(
        "--retrieve-bytes",
        type=int,
        default=None,
        help="Stop streaming after retrieving this many bytes (default: all)",
    )
    args = parser.parse_args()

    main(
        Path(args.output),
        payload_count=max(1, args.count),
        total_bytes=max(args.total_bytes, 1),
        retrieve_bytes=args.retrieve_bytes,
    )
