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
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import nullcontext
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple, List, Union

ROOT = Path(__file__).resolve().parent.parent / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aura_compression.compressor_refactored import ProductionHybridCompressor
from aura_compression.enums import CompressionMethod

MAGIC = b"AURALF01"
CONTAINER_VERSION = 1
DEFAULT_CHUNK_SIZE = 64 * 1024  # 64 KiB
PROGRESS_BAR_WIDTH = 30
PROGRESS_MODES = {"auto", "bar", "percent", "none"}
DEFAULT_PROGRESS_MODE = "bar"


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


def _parse_chunk_size(value: Union[str, int]) -> int:
    """Parse chunk size from CLI, supporting suffixes like 64K or 4M."""
    if isinstance(value, int):
        if value <= 0:
            raise argparse.ArgumentTypeError("Chunk size must be positive")
        return value

    text = value.strip().lower()
    if not text:
        raise argparse.ArgumentTypeError("Chunk size cannot be empty")

    multipliers = {
        "k": 1024,
        "kb": 1024,
        "m": 1024 ** 2,
        "mb": 1024 ** 2,
        "g": 1024 ** 3,
        "gb": 1024 ** 3,
    }

    for suffix, multiplier in multipliers.items():
        if text.endswith(suffix):
            number_part = text[: -len(suffix)]
            try:
                base = float(number_part)
            except ValueError as exc:
                raise argparse.ArgumentTypeError(f"Invalid chunk size: {value}") from exc
            size = int(base * multiplier)
            if size <= 0:
                raise argparse.ArgumentTypeError("Chunk size must be positive")
            return size

    try:
        size = int(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid chunk size: {value}") from exc

    if size <= 0:
        raise argparse.ArgumentTypeError("Chunk size must be positive")
    return size


def _format_bytes(size: int) -> str:
    """Convert byte sizes to human readable strings."""
    if size < 1024:
        return f"{size} B"
    units = ["KB", "MB", "GB", "TB"]
    value = float(size)
    for unit in units:
        value /= 1024
        if value < 1024:
            return f"{value:.2f} {unit}"
    return f"{value:.2f} PB"


def _compress_chunk_worker(chunk_data: bytes, compressor_config: Dict[str, Any]) -> Tuple[bytes, Dict[str, Any]]:
    """Worker function for compressing a single chunk in a separate process."""
    # Create an aggressive compressor for this worker
    cache_dir = Path(compressor_config["cache_dir"])
    audit_dir = Path(compressor_config["audit_dir"])
    
    compressor = ProductionHybridCompressor(
        enable_aura=True,
        enable_audit_logging=False,  # Disable audit logging in workers for speed
        template_cache_dir=str(cache_dir),
        template_cache_size=512,  # Larger cache for better hit rates
        enable_fast_path=True,
        enable_sidechain=False,
        enable_scorer=False,  # Disable scorer in workers for speed
        enable_ml_selection=True,  # Enable ML for better compression decisions
        template_sync_interval_seconds=None,  # Disable sync in workers
    )
    
    # Decode and compress
    text_chunk = chunk_data.decode("utf-8", errors="surrogateescape")
    payload, method, metadata = compressor.compress(text_chunk)
    
    return payload, {
        "method": method,
        "metadata": metadata,
        "original_size": len(chunk_data),
        "compressed_size": len(payload)
    }


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


class ProgressTracker:
    def __init__(self, prefix: str, total: int, mode: str, start_time: float) -> None:
        self.prefix = prefix
        self.total = max(total, 0)
        self.mode = mode
        self.start_time = start_time
        self.last_percent = -1.0

    def update(self, completed: int) -> None:
        if self.mode == "none" or self.total <= 0:
            return

        ratio = min(max(completed / self.total, 0.0), 1.0)
        percent = ratio * 100

        if self.mode == "percent" and percent - self.last_percent < 1.0 and percent < 100.0:
            return

        elapsed = time.time() - self.start_time
        throughput = (completed / 1024 / 1024) / elapsed if elapsed > 0 else 0.0

        if self.mode == "bar":
            filled = int(ratio * PROGRESS_BAR_WIDTH)
            bar = "#" * filled + "-" * (PROGRESS_BAR_WIDTH - filled)
            sys.stdout.write(
                f"\r{self.prefix} [{bar}] {percent:6.2f}%  "
                f"{completed/1024/1024:7.2f}/{self.total/1024/1024:7.2f} MB  "
                f"{throughput:5.2f} MB/s"
            )
            sys.stdout.flush()
        elif self.mode == "percent":
            sys.stdout.write(
                f"{self.prefix} {percent:6.2f}%  "
                f"{completed/1024/1024:7.2f}/{self.total/1024/1024:7.2f} MB  "
                f"{throughput:5.2f} MB/s\n"
            )
            sys.stdout.flush()

        self.last_percent = percent

    def finish(self, completed: int) -> None:
        if self.mode == "none" or self.total <= 0:
            return

        if self.mode == "percent" and self.last_percent >= 100.0:
            return

        self.update(completed)
        if self.mode == "bar":
            sys.stdout.write("\n")
            sys.stdout.flush()


def _resolve_progress_mode(requested: str, interactive: bool, default_mode: str = "bar") -> str:
    if requested not in PROGRESS_MODES:
        raise ValueError(f"Invalid progress mode '{requested}'. Choose from {sorted(PROGRESS_MODES)}.")
    if requested == "auto":
        return default_mode if interactive else "none"
    return requested


def _render_stats(stats: Dict[str, object], *, fmt: str = "table") -> str:
    if fmt == "json":
        return json.dumps(stats, indent=2, default=str)

    lines = []
    for key in sorted(stats.keys()):
        value = stats[key]
        if isinstance(value, (int, float)) and "size" in key:
            display = f"{value:,} ({_format_bytes(int(value))})" if isinstance(value, (int, float)) else value
        elif isinstance(value, float):
            display = f"{value:,.3f}"
        else:
            display = value
        lines.append(f"{key:>20}: {display}")
    return "\n".join(lines)


def _output_stats(stats: Dict[str, object], fmt: str, stats_file: Optional[Path]) -> None:
    rendered = _render_stats(stats, fmt=fmt)
    print(rendered)
    if stats_file:
        stats_file.parent.mkdir(parents=True, exist_ok=True)
        with open(stats_file, "w", encoding="utf-8") as handle:
            if fmt == "json":
                handle.write(rendered)
                handle.write("\n")
            else:
                handle.write(rendered)
                handle.write("\n")


def _read_container_header(stream) -> Tuple[int, int, Dict[str, Any]]:
    magic = stream.read(len(MAGIC))
    if magic != MAGIC:
        raise ValueError("Invalid container magic header")

    version = struct.unpack(">I", stream.read(4))[0]
    chunk_count = struct.unpack(">Q", stream.read(8))[0]
    meta_len = struct.unpack(">I", stream.read(4))[0]
    meta_raw = stream.read(meta_len)
    meta = json.loads(meta_raw or b"{}")
    return version, chunk_count, meta


def compress_path(
    input_path: Path,
    output_path: Optional[Path] = None,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    cache_dir: Optional[Path] = None,
    audit_dir: Optional[Path] = None,
    sync_every: int = 50,
    workers: int = 1,
    show_progress: Optional[bool] = None,
    progress_mode: str = "auto",
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
    display_progress = show_progress if show_progress is not None else sys.stdout.isatty()
    total_size = input_path.stat().st_size
    progress_mode_resolved = _resolve_progress_mode(progress_mode, display_progress)
    tracker = ProgressTracker("Compressing", total_size, progress_mode_resolved, start_time)

    encoding = "utf-8-surrogateescape"
    template_ids_seen: set[int] = set()
    chunk_ratios: List[float] = []

    with open(input_path, "rb") as source, open(output_path, "wb") as sink:
        chunk_count_pos = _write_container_header(
            sink, chunk_size=chunk_size, encoding=encoding, input_path=input_path, start_time=start_time
        )

        # Read all chunks first
        chunks = []
        for index, raw_chunk in _chunk_iter(source, chunk_size):
            chunks.append((index, raw_chunk))
            total_input += len(raw_chunk)

        # Process chunks sequentially
        compressed_results = []
        bytes_processed = 0
        
        for index, raw_chunk in chunks:
            text_chunk = raw_chunk.decode("utf-8", errors="surrogateescape")
            payload, method, metadata = compressor.compress(text_chunk)
            compressed_results.append((payload, {
                "method": method,
                "metadata": metadata,
                "original_size": len(raw_chunk),
                "compressed_size": len(payload)
            }))
            bytes_processed += len(raw_chunk)
            tracker.update(bytes_processed)

        # Write results sequentially to maintain order
        for index, (payload, worker_meta) in enumerate(compressed_results):
            raw_chunk = chunks[index][1]
            
            # Use the metadata from compression
            method = worker_meta["method"]
            metadata = worker_meta["metadata"]

            chunk_meta: Dict[str, object] = {
                "index": index,
                "original_size": len(raw_chunk),
                "compressed_size": len(payload),
                "compression_method": method.name if hasattr(method, 'name') else str(method),
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

            if len(payload) > 0:
                chunk_ratios.append(len(raw_chunk) / len(payload))
            template_ids_seen.update(t["template_id"] for t in templates_meta if "template_id" in t)

        _update_chunk_count(sink, chunk_count_pos, chunk_count)

    compressor._template_service.sync_template_store()  # noqa: SLF001
    _shutdown_compressor(compressor)
    tracker.finish(total_input)

    elapsed = time.time() - start_time
    ratio = (total_input / total_compressed) if total_compressed else 1.0
    throughput = (total_input / 1024 / 1024) / elapsed if elapsed > 0 else 0.0

    return {
        "chunks": chunk_count,
        "input_size": total_input,
        "compressed_size": total_compressed,
        "compression_ratio": ratio,
        "elapsed_seconds": elapsed,
        "output_path": str(output_path),
        "chunk_size": chunk_size,
        "progress_mode": progress_mode_resolved,
        "throughput_mb_s": throughput,
        "template_ids": sorted(template_ids_seen),
        "average_chunk_ratio": float(sum(chunk_ratios) / len(chunk_ratios)) if chunk_ratios else None,
    }


def decompress_path(
    input_path: Path,
    output_path: Optional[Path] = None,
    *,
    cache_dir: Optional[Path] = None,
    audit_dir: Optional[Path] = None,
    show_progress: Optional[bool] = None,
    progress_mode: str = "auto",
    write_output: bool = True,
) -> Dict[str, object]:
    """Decompress an .aura container previously produced by this module."""
    target_output = output_path or input_path.with_suffix(".restored")

    cache_dir = cache_dir or Path(".aura_cache")
    audit_dir = audit_dir or Path("./audit_logs")
    compressor = _build_compressor(cache_dir, audit_dir)

    start_time = time.time()
    restored_bytes = 0
    chunk_count = 0
    display_progress = show_progress if show_progress is not None else sys.stdout.isatty()
    tracker: Optional[ProgressTracker] = None
    compressed_size = input_path.stat().st_size
    template_ids_seen: set[int] = set()

    sink_context = open(target_output, "wb") if write_output else nullcontext(None)

    with open(input_path, "rb") as source, sink_context as sink:
        version, chunk_count_recorded, container_meta = _read_container_header(source)
        if version != CONTAINER_VERSION:
            raise ValueError(f"Unsupported container version: {version}")

        encoding = container_meta.get("encoding", "utf-8-surrogateescape")
        progress_mode_resolved = _resolve_progress_mode(progress_mode, display_progress)
        tracker = ProgressTracker(
            "Decompressing", chunk_count_recorded or 0, progress_mode_resolved, start_time
        )

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
            restored_chunk = text.encode(
                "utf-8",
                errors="surrogateescape"
                if encoding.endswith("surrogateescape")
                else "strict",
            )
            if write_output and sink is not None:
                sink.write(restored_chunk)
            restored_bytes += len(restored_chunk)
            chunk_count += 1
            if tracker:
                tracker.update(chunk_count)

            templates = chunk_meta.get("templates") or []
            for template_info in templates:
                template_id = template_info.get("template_id")
                if template_id is not None:
                    template_ids_seen.add(int(template_id))

    _shutdown_compressor(compressor)
    if tracker:
        tracker.finish(chunk_count)

    elapsed = time.time() - start_time

    if chunk_count_recorded and chunk_count_recorded != chunk_count:
        raise ValueError(
            f"Chunk count mismatch (expected {chunk_count_recorded}, got {chunk_count})"
        )

    return {
        "chunks": chunk_count,
        "restored_size": restored_bytes,
        "elapsed_seconds": elapsed,
        "output_path": str(target_output) if write_output else None,
        "compressed_size": compressed_size,
        "progress_mode": progress_mode_resolved,
        "template_ids": sorted(template_ids_seen),
        "header": container_meta,
    }


def inspect_container(
    input_path: Path,
    *,
    max_chunks: int = 10,
) -> Dict[str, object]:
    """Inspect an .aura container without decompressing payloads."""
    if max_chunks <= 0:
        raise ValueError("max_chunks must be positive")

    info: Dict[str, object] = {}
    sample_chunks: List[Dict[str, object]] = []
    method_counts: Dict[str, int] = {}
    template_ids: set[int] = set()
    total_payload = 0

    with open(input_path, "rb") as source:
        version, chunk_count, meta = _read_container_header(source)

        info.update(
            {
                "path": str(input_path),
                "container_version": version,
                "chunk_count": chunk_count,
                "header": meta,
            }
        )

        for chunk_idx in range(chunk_count):
            len_bytes = source.read(4)
            if not len_bytes:
                break
            chunk_meta_len = struct.unpack(">I", len_bytes)[0]
            chunk_data_len = struct.unpack(">Q", source.read(8))[0]
            chunk_meta_bytes = source.read(chunk_meta_len)
            chunk_meta: Dict[str, object] = json.loads(chunk_meta_bytes or b"{}")

            total_payload += chunk_data_len
            method = chunk_meta.get("compression_method", "unknown")
            method_counts[method] = method_counts.get(method, 0) + 1

            templates = chunk_meta.get("templates") or []
            for template_info in templates:
                template_id = template_info.get("template_id")
                if template_id is not None:
                    template_ids.add(int(template_id))

            if len(sample_chunks) < max_chunks:
                sample_chunks.append(
                    {
                        "index": chunk_meta.get("index", chunk_idx),
                        "method": method,
                        "original_size": chunk_meta.get("original_size"),
                        "compressed_size": chunk_meta.get("compressed_size"),
                        "templates": [t.get("template_id") for t in templates],
                    }
                )

            # Skip over payload data quickly
            source.seek(chunk_data_len, 1)

    info["payload_bytes"] = total_payload
    info["method_counts"] = method_counts
    info["template_ids"] = sorted(template_ids)
    info["sample_chunks"] = sample_chunks
    info["file_size"] = input_path.stat().st_size

    return info


def verify_container(
    input_path: Path,
    *,
    cache_dir: Optional[Path] = None,
    audit_dir: Optional[Path] = None,
    show_progress: Optional[bool] = None,
    progress_mode: str = "auto",
) -> Dict[str, object]:
    """Decompress container without writing output to verify integrity."""
    stats = decompress_path(
        input_path,
        output_path=None,
        cache_dir=cache_dir,
        audit_dir=audit_dir,
        show_progress=show_progress,
        progress_mode=progress_mode,
        write_output=False,
    )
    stats["verified"] = True
    return stats


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compress or decompress large files with AURA.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    compress_parser = subparsers.add_parser("compress", help="Compress a file into .aura format")
    compress_parser.add_argument("--input", required=True, type=Path, help="Path to the input file")
    compress_parser.add_argument("--output", type=Path, help="Destination for the compressed artifact")
    compress_parser.add_argument(
        "--chunk-size",
        type=_parse_chunk_size,
        default=DEFAULT_CHUNK_SIZE,
        help="Chunk size per segment. Accepts raw bytes (65536) or suffixes like 64K, 4M.",
    )
    compress_parser.add_argument("--cache-dir", type=Path, help="Directory for template cache persistence")
    compress_parser.add_argument("--audit-dir", type=Path, help="Directory for audit logs")
    compress_parser.add_argument(
        "--sync-every",
        type=int,
        default=50,
        help="How often (in chunks) to force a template store sync (0 disables periodic sync)",
    )
    compress_parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of parallel worker processes for compression (default: 1)",
    )
    compress_parser.add_argument(
        "--progress",
        choices=sorted(PROGRESS_MODES),
        default="auto",
        help="Progress display style (auto, bar, percent, none). Default: auto.",
    )
    compress_parser.add_argument(
        "--stats-format",
        choices=["table", "json"],
        default="table",
        help="Presentation format for summary stats.",
    )
    compress_parser.add_argument(
        "--stats-file",
        type=Path,
        help="Optional path to save stats output (respects --stats-format).",
    )

    decompress_parser = subparsers.add_parser("decompress", help="Decompress a .aura file")
    decompress_parser.add_argument("--input", required=True, type=Path, help="Compressed .aura file")
    decompress_parser.add_argument("--output", type=Path, help="Destination for restored data")
    decompress_parser.add_argument("--cache-dir", type=Path, help="Directory for template cache persistence")
    decompress_parser.add_argument("--audit-dir", type=Path, help="Directory for audit logs")
    decompress_parser.add_argument(
        "--progress",
        choices=sorted(PROGRESS_MODES),
        default="auto",
        help="Progress display style (auto, bar, percent, none). Default: auto.",
    )
    decompress_parser.add_argument(
        "--stats-format",
        choices=["table", "json"],
        default="table",
        help="Presentation format for summary stats.",
    )
    decompress_parser.add_argument(
        "--stats-file",
        type=Path,
        help="Optional path to save stats output (respects --stats-format).",
    )

    info_parser = subparsers.add_parser("info", help="Inspect a compressed .aura file")
    info_parser.add_argument("--input", required=True, type=Path, help="Compressed .aura file")
    info_parser.add_argument(
        "--max-chunks",
        type=int,
        default=5,
        help="Number of sample chunks to include in the report (default: 5).",
    )
    info_parser.add_argument(
        "--stats-format",
        choices=["table", "json"],
        default="table",
        help="Output format for inspection details.",
    )
    info_parser.add_argument(
        "--stats-file",
        type=Path,
        help="Optional path to save inspection details.",
    )

    verify_parser = subparsers.add_parser("verify", help="Verify container integrity without writing output")
    verify_parser.add_argument("--input", required=True, type=Path, help="Compressed .aura file")
    verify_parser.add_argument("--cache-dir", type=Path, help="Directory for template cache persistence")
    verify_parser.add_argument("--audit-dir", type=Path, help="Directory for audit logs")
    verify_parser.add_argument(
        "--progress",
        choices=sorted(PROGRESS_MODES),
        default="auto",
        help="Progress display style (auto, bar, percent, none). Default: auto.",
    )
    verify_parser.add_argument(
        "--stats-format",
        choices=["table", "json"],
        default="table",
        help="Presentation format for verification stats.",
    )
    verify_parser.add_argument(
        "--stats-file",
        type=Path,
        help="Optional path to save verification stats.",
    )

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
            workers=1,  # Force single-threaded
            progress_mode=args.progress,
        )
        _output_stats(stats, args.stats_format, args.stats_file)
    elif args.command == "decompress":
        stats = decompress_path(
            args.input,
            args.output,
            cache_dir=args.cache_dir,
            audit_dir=args.audit_dir,
            progress_mode=args.progress,
        )
        _output_stats(stats, args.stats_format, args.stats_file)
    elif args.command == "info":
        stats = inspect_container(
            args.input,
            max_chunks=args.max_chunks,
        )
        _output_stats(stats, args.stats_format, args.stats_file)
    elif args.command == "verify":
        stats = verify_container(
            args.input,
            cache_dir=args.cache_dir,
            audit_dir=args.audit_dir,
            progress_mode=args.progress,
        )
        _output_stats(stats, args.stats_format, args.stats_file)
    else:
        parser.error(f"Unknown command: {args.command}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
