"""Run a small local AIWire message benchmark."""

from __future__ import annotations

import argparse
import copy
import json
import time
from typing import Any

from aura_compression.ai_wire import (
    AI_WIRE_DICTIONARY_SHA256,
    build_delta_structured_ai_messages,
    build_structured_ai_messages,
    compress_ai_wire_frames,
    decompress_ai_wire_frames,
    encode_ai_wire_message,
    summarize_ai_wire_corpus,
)


DEFAULT_MESSAGE_COUNT = 1024
BENCHMARK_PROFILES: dict[str, dict[str, Any]] = {
    "custom": {
        "messages": DEFAULT_MESSAGE_COUNT,
        "description": "Caller-selected message count.",
    },
    "small": {
        "messages": 128,
        "description": "Short local smoke run for quick regressions.",
    },
    "medium": {
        "messages": DEFAULT_MESSAGE_COUNT,
        "description": "Default protocol-shaped corpus size.",
    },
    "bursty": {
        "messages": 2048,
        "description": "Mixed message sizes with periodic large synthetic payloads.",
    },
}


def _build_base_messages(corpus: str, count: int, seed: int) -> list[dict[str, Any]]:
    if corpus == "delta":
        return build_delta_structured_ai_messages(count, seed=seed)
    if corpus == "structured":
        return build_structured_ai_messages(count, seed=seed)
    raise ValueError(f"unsupported benchmark corpus: {corpus}")


def _build_bursty_messages(corpus: str, count: int, seed: int) -> list[dict[str, Any]]:
    messages = _build_base_messages(corpus, count, seed)
    bursty: list[dict[str, Any]] = []

    for index, message in enumerate(messages):
        payload = copy.deepcopy(message)
        if index % 16 == 0:
            size_class = "large"
            payload["burst_payload"] = {
                "kind": "synthetic.large_result",
                "chunks": [
                    {
                        "index": chunk_index,
                        "text": (
                            f"burst segment {chunk_index} for message {index}: "
                            "verified evidence, route hints, tool output, and "
                            "status deltas remain public-safe synthetic data."
                        ),
                    }
                    for chunk_index in range(8)
                ],
            }
        elif index % 4 == 0:
            size_class = "medium"
            payload["burst_payload"] = {
                "kind": "synthetic.medium_result",
                "summary": f"medium burst payload for message {index}",
            }
        else:
            size_class = "small"

        payload["benchmark_profile"] = {
            "profile": "bursty",
            "corpus": corpus,
            "size_class": size_class,
            "synthetic": True,
        }
        bursty.append(payload)

    return bursty


def _build_benchmark_messages(
    *,
    corpus: str,
    profile: str,
    count: int,
    seed: int,
) -> list[dict[str, Any]]:
    if profile == "bursty":
        return _build_bursty_messages(corpus, count, seed)
    return _build_base_messages(corpus, count, seed)


def run_benchmark(
    *,
    profile: str = "custom",
    corpus: str = "structured",
    messages: int | None = None,
    seed: int = 1729,
    level: int = 3,
) -> dict[str, Any]:
    """Run the local AIWire benchmark and return stable JSON-compatible results."""

    if profile not in BENCHMARK_PROFILES:
        choices = ", ".join(sorted(BENCHMARK_PROFILES))
        raise ValueError(f"unsupported benchmark profile {profile!r}; choices: {choices}")
    if corpus not in {"structured", "delta"}:
        raise ValueError("unsupported benchmark corpus; choices: structured, delta")

    profile_info = BENCHMARK_PROFILES[profile]
    message_count = messages if messages is not None else int(profile_info["messages"])
    if message_count <= 0:
        raise ValueError("messages must be positive")

    benchmark_messages = _build_benchmark_messages(
        corpus=corpus,
        profile=profile,
        count=message_count,
        seed=seed,
    )
    started = time.perf_counter()
    frames, encode_stats = compress_ai_wire_frames(
        benchmark_messages,
        level=level,
        use_native=False,
    )
    encoded_at = time.perf_counter()
    restored, decode_stats = decompress_ai_wire_frames(frames, use_native=False)
    finished = time.perf_counter()

    if [encode_ai_wire_message(item) for item in restored] != [
        encode_ai_wire_message(item) for item in benchmark_messages
    ]:
        raise RuntimeError("AIWire benchmark round trip failed")

    return {
        "messages": message_count,
        "benchmark_profile": profile,
        "benchmark_profile_description": profile_info["description"],
        "corpus": corpus,
        "dictionary_sha256": AI_WIRE_DICTIONARY_SHA256,
        "corpus_summary": summarize_ai_wire_corpus(benchmark_messages),
        "encode_seconds": encoded_at - started,
        "decode_seconds": finished - encoded_at,
        "encode_stats": encode_stats.as_dict(),
        "decode_stats": decode_stats.as_dict(),
        "bytes_in": encode_stats.bytes_in,
        "bytes_out": encode_stats.bytes_out,
        "ratio": encode_stats.ratio,
        "decode_bytes_out": decode_stats.bytes_out,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile",
        choices=tuple(BENCHMARK_PROFILES),
        default="custom",
        help="Benchmark size profile. --messages overrides the profile count.",
    )
    parser.add_argument(
        "--corpus",
        choices=("structured", "delta"),
        default="structured",
        help="Synthetic corpus family to benchmark.",
    )
    parser.add_argument("--messages", type=int, default=None, help="Number of messages")
    parser.add_argument("--seed", type=int, default=1729, help="Synthetic corpus seed")
    parser.add_argument("--level", type=int, default=3, help="zlib compression level, 0-9")
    args = parser.parse_args(argv)

    try:
        result = run_benchmark(
            profile=args.profile,
            corpus=args.corpus,
            messages=args.messages,
            seed=args.seed,
            level=args.level,
        )
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
