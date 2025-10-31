#!/usr/bin/env python3
"""
High-capacity file compressor with AURA hybrid compression.

Features:
- Streams large inputs in fixed-size chunks to avoid excessive memory usage.
- Keeps template discovery and binary semantic compression enabled.
- Persists chunk metadata (including dynamic template patterns) inside the
  resulting container so decompression works on a fresh machine.

Usage:
    python tools/compress_large_file.py compress --input /path/to/enwik8
    python tools/compress_large_file.py decompress --input enwik8.aura
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aura_compression.compressor_refactored import ProductionHybridCompressor
from aura_compression.enums import CompressionMethod

MAGIC = b"AURALF01"
CONTAINER_VERSION = 1
DEFAULT_CHUNK_SIZE = 64 * 1024  # 64 KiB


def _build_compressor(cache_dir: Path, audit_dir: Path) -> ProductionHybridCompressor:
    """Instantiate a ProductionHybridCompressor with discovery enabled."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    audit_dir.mkdir(parents=True, exist_ok=True)

    return ProductionHybridCompressor(
        enable_aura=True,
        enable_audit_logging=True,
        audit_log_directory=str(audit_dir),
        template_cache_dir=str(cache_dir),
        template_cache_size=512,
        template_sync_interval_seconds=120,
        enable_fast_path=True,
        enable_sidechain=False,
        enable_scorer=True,
    )


def _shutdown_compressor(compressor: ProductionHybridCompressor) -> None:
    """Ensure background workers and caches terminate cleanly."""
    template_service = compressor._template_service  # noqa: SLF001 - intentional internal cleanup
    worker = getattr(template_service, "discovery_worker", None)
    if worker:
        worker.stop()
    compressor.template_library.shutdown()


def _write_container_header(
    sink, chunk_size: int, encoding: str, input_path: Path, start_time: float
) -> int:
    """Write the container header and return the offset of the chunk-count field."""
    sink.write(MAGIC)
    sink.write(struct.pack(">I", CONTAINER_VERSION))
    chunk_count_pos = sink.tell()
    sink.write(struct.pack(">Q", 0))  # Placeholder for chunk count

    container_meta = {
        "source": str(input_path),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(start_time)),
        "chunk_size": chunk_size,
        "encoding": encoding,
        "version": CONTAINER_VERSION,
    }
    meta_bytes = json.dumps(container_meta, separators=(",", ":"), default=str).encode("utf-8")
    sink.write(struct.pack(">I", len(meta_bytes)))
    sink.write(meta_bytes)
    return chunk_count_pos


def _update_chunk_count(sink, chunk_count_pos: int, chunk_count: int) -> None:
    """Backfill the chunk-count field once compression finishes."""
    sink.flush()
    sink.seek(chunk_count_pos)
    sink.write(struct.pack(">Q", chunk_count))
    sink.flush()


def _register_template_for_chunk(
    compressor: ProductionHybridCompressor, chunk_meta: Dict[str, object]
) -> None:
    """Ensure dynamic templates embedded in metadata exist before decompressing."""
    templates = chunk_meta.get("templates")

    # Backward compatibility: legacy format stored a single template_id/pattern pair.
    if not templates and chunk_meta.get("template_id") is not None:
        templates = [
            {
                "template_id": chunk_meta.get("template_id"),
                "pattern": chunk_meta.get("template_pattern"),
            }
        ]

    if not templates:
        return

    for template_info in templates:
        template_id = template_info.get("template_id")
        pattern = template_info.get("pattern")
        if template_id is None or pattern is None:
            continue

        existing = compressor.template_library.get(int(template_id))  # type: ignore[arg-type]
        if existing == pattern:
            continue

        compressor.template_library.add(int(template_id), pattern)  # type: ignore[arg-type]


def _chunk_iter(stream, chunk_size: int) -> Iterable[Tuple[int, bytes]]:
    """Yield (index, bytes) for each chunk of data."""
    index = 0
    while True:
        data = stream.read(chunk_size)
        if not data:
            break
        yield index, data
        index += 1


def compress_path(
    input_path: Path,
    output_path: Optional[Path] = None,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    cache_dir: Optional[Path] = None,
    audit_dir: Optional[Path] = None,
    sync_every: int = 50,
) -> Dict[str, object]:
    """
    Compress a large file into an .aura container.

    Returns basic statistics for logging or testing.
    """
    if output_path is None:
        output_path = input_path.with_suffix(input_path.suffix + ".aura")

    cache_dir = cache_dir or Path(".aura_cache")
    audit_dir = audit_dir or Path("./audit_logs")
    compressor = _build_compressor(cache_dir, audit_dir)

    start_time = time.time()
    chunk_count = 0
    total_input = 0
    total_compressed = 0

    encoding = "utf-8-surrogateescape"

    with open(input_path, "rb") as source, open(output_path, "wb") as sink:
        chunk_count_pos = _write_container_header(
            sink, chunk_size=chunk_size, encoding=encoding, input_path=input_path, start_time=start_time
        )

        for index, raw_chunk in _chunk_iter(source, chunk_size):
            total_input += len(raw_chunk)
            text_chunk = raw_chunk.decode("utf-8", errors="surrogateescape")
            payload, method, metadata = compressor.compress(text_chunk)

            chunk_meta: Dict[str, object] = {
                "index": index,
                "original_size": len(raw_chunk),
                "compressed_size": len(payload),
                "compression_method": method.name,
                "metadata": metadata,
            }

            templates_meta: List[Dict[str, object]] = []

            if metadata.get("template_id") is not None:
                template_id = int(metadata["template_id"])
                template_pattern = compressor.template_library.get(template_id)
                if template_pattern:
                    chunk_meta["template_id"] = template_id  # Backwards compatibility
                    chunk_meta["template_pattern"] = template_pattern
                    templates_meta.append(
                        {
                            "template_id": template_id,
                            "pattern": template_pattern,
                        }
                    )

            template_ids = metadata.get("template_ids") or []
            for template_id in template_ids:
                template_pattern = compressor.template_library.get(int(template_id))
                if not template_pattern:
                    continue
                if not any(t["template_id"] == template_id for t in templates_meta):
                    templates_meta.append(
                        {
                            "template_id": int(template_id),
                            "pattern": template_pattern,
                        }
                    )

            if templates_meta:
                chunk_meta["templates"] = templates_meta

            chunk_meta_bytes = json.dumps(chunk_meta, separators=(",", ":"), default=str).encode("utf-8")

            sink.write(struct.pack(">I", len(chunk_meta_bytes)))
            sink.write(struct.pack(">Q", len(payload)))
            sink.write(chunk_meta_bytes)
            sink.write(payload)

            total_compressed += len(payload)
            chunk_count = index + 1

            if sync_every > 0 and chunk_count % sync_every == 0:
                compressor._template_service.sync_template_store()  # noqa: SLF001

        _update_chunk_count(sink, chunk_count_pos, chunk_count)

    compressor._template_service.sync_template_store()  # noqa: SLF001
    _shutdown_compressor(compressor)

    elapsed = time.time() - start_time
    ratio = (total_input / total_compressed) if total_compressed else 1.0

    return {
        "chunks": chunk_count,
        "input_size": total_input,
        "compressed_size": total_compressed,
        "compression_ratio": ratio,
        "elapsed_seconds": elapsed,
        "output_path": str(output_path),
    }


def decompress_path(
    input_path: Path,
    output_path: Optional[Path] = None,
    *,
    cache_dir: Optional[Path] = None,
    audit_dir: Optional[Path] = None,
) -> Dict[str, object]:
    """Decompress an .aura container previously produced by this module."""
    if output_path is None:
        output_path = input_path.with_suffix(".restored")

    cache_dir = cache_dir or Path(".aura_cache")
    audit_dir = audit_dir or Path("./audit_logs")
    compressor = _build_compressor(cache_dir, audit_dir)

    start_time = time.time()
    restored_bytes = 0
    chunk_count = 0

    with open(input_path, "rb") as source, open(output_path, "wb") as sink:
        magic = source.read(len(MAGIC))
        if magic != MAGIC:
            raise ValueError("Invalid container magic header")

        version = struct.unpack(">I", source.read(4))[0]
        if version != CONTAINER_VERSION:
            raise ValueError(f"Unsupported container version: {version}")

        chunk_count_recorded = struct.unpack(">Q", source.read(8))[0]
        meta_len = struct.unpack(">I", source.read(4))[0]
        meta = json.loads(source.read(meta_len) or b"{}")
        encoding = meta.get("encoding", "utf-8-surrogateescape")

        while True:
            len_bytes = source.read(4)
            if not len_bytes:
                break

            chunk_meta_len = struct.unpack(">I", len_bytes)[0]
            chunk_data_len = struct.unpack(">Q", source.read(8))[0]

            chunk_meta_bytes = source.read(chunk_meta_len)
            chunk_meta: Dict[str, object] = json.loads(chunk_meta_bytes or b"{}")

            compressed_chunk = source.read(chunk_data_len)
            _register_template_for_chunk(compressor, chunk_meta)

            text = compressor.decompress(compressed_chunk)
            restored_chunk = text.encode("utf-8", errors="surrogateescape" if encoding.endswith("surrogateescape") else "strict")
            sink.write(restored_chunk)
            restored_bytes += len(restored_chunk)
            chunk_count += 1

    _shutdown_compressor(compressor)
    elapsed = time.time() - start_time

    if chunk_count_recorded and chunk_count_recorded != chunk_count:
        raise ValueError(
            f"Chunk count mismatch (expected {chunk_count_recorded}, got {chunk_count})"
        )

    return {
        "chunks": chunk_count,
        "restored_size": restored_bytes,
        "elapsed_seconds": elapsed,
        "output_path": str(output_path),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compress or decompress large files with AURA.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    compress_parser = subparsers.add_parser("compress", help="Compress a file into .aura format")
    compress_parser.add_argument("--input", required=True, type=Path, help="Path to the input file")
    compress_parser.add_argument("--output", type=Path, help="Destination for the compressed artifact")
    compress_parser.add_argument(
        "--chunk-size",
        type=int,
        default=DEFAULT_CHUNK_SIZE,
        help=f"Chunk size in bytes (default: {DEFAULT_CHUNK_SIZE})",
    )
    compress_parser.add_argument("--cache-dir", type=Path, help="Directory for template cache persistence")
    compress_parser.add_argument("--audit-dir", type=Path, help="Directory for audit logs")
    compress_parser.add_argument(
        "--sync-every",
        type=int,
        default=50,
        help="How often (in chunks) to force a template store sync (0 disables periodic sync)",
    )

    decompress_parser = subparsers.add_parser("decompress", help="Decompress a .aura file")
    decompress_parser.add_argument("--input", required=True, type=Path, help="Compressed .aura file")
    decompress_parser.add_argument("--output", type=Path, help="Destination for restored data")
    decompress_parser.add_argument("--cache-dir", type=Path, help="Directory for template cache persistence")
    decompress_parser.add_argument("--audit-dir", type=Path, help="Directory for audit logs")

    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "compress":
        stats = compress_path(
            args.input,
            args.output,
            chunk_size=args.chunk_size,
            cache_dir=args.cache_dir,
            audit_dir=args.audit_dir,
            sync_every=args.sync_every,
        )
        print(
            f"Compressed {stats['input_size']:,} bytes into {stats['compressed_size']:,} bytes "
            f"in {stats['elapsed_seconds']:.2f}s "
            f"(ratio {stats['compression_ratio']:.3f}:1) -> {stats['output_path']}"
        )
    elif args.command == "decompress":
        stats = decompress_path(
            args.input,
            args.output,
            cache_dir=args.cache_dir,
            audit_dir=args.audit_dir,
        )
        print(
            f"Decompressed {stats['chunks']} chunks ({stats['restored_size']:,} bytes) "
            f"in {stats['elapsed_seconds']:.2f}s -> {stats['output_path']}"
        )
    else:
        parser.error(f"Unknown command: {args.command}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
