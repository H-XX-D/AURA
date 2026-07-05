"""Run a small local AIWire message benchmark."""

from __future__ import annotations

import argparse
import copy
import json
import os
import time
from typing import Any

from aura_compression.ai_wire import (
    AI_WIRE_DICTIONARY_SHA256,
    AIWireNativeError,
    AIWireSessionDecoder,
    AIWireSessionEncoder,
    aiwire_native_status,
    aiwire_session_templates_sha256,
    build_aiwire_handshake,
    build_aiwire_session_template_update,
    build_delta_structured_ai_messages,
    build_structured_ai_messages,
    discover_ai_wire_session_templates,
    encode_ai_wire_message,
    negotiate_aiwire_nary_handshake,
    summarize_ai_wire_corpus,
)

DEFAULT_MESSAGE_COUNT = 1024
LENGTH_PREFIX_BYTES = 4
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
BENCHMARK_BACKENDS = ("python", "native", "auto")


def _build_base_messages(corpus: str, count: int, seed: int) -> list[dict[str, Any]]:
    if corpus == "delta":
        return build_delta_structured_ai_messages(
            count,
            seed=seed,
            include_corpus_metadata=True,
        )
    if corpus == "structured":
        return build_structured_ai_messages(
            count,
            seed=seed,
            include_corpus_metadata=True,
        )
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


def _use_native_for_backend(backend: str) -> bool | None:
    if backend == "python":
        return False
    if backend == "native":
        return True
    if backend == "auto":
        return None
    choices = ", ".join(BENCHMARK_BACKENDS)
    raise ValueError(f"unsupported benchmark backend {backend!r}; choices: {choices}")


def _native_library_origin(library_path: str | None) -> str | None:
    if library_path is None:
        return None
    if library_path == os.getenv("AURA_AIWIRE_LIBRARY"):
        return "env"
    if "aura_compression/native" in library_path:
        return "packaged"
    if "native/aiwire/build" in library_path:
        return "local-build"
    return "dynamic-loader"


def _benchmark_native_status() -> dict[str, object]:
    status = aiwire_native_status()
    return {
        "available": status.available,
        "library_origin": _native_library_origin(status.library_path),
        "version": status.version,
        "error": None if status.available else "native AIWire library not available",
        "dictionary_size": status.dictionary_size,
        "dictionary_checksum": status.dictionary_checksum,
        "dictionary_matches_python": status.dictionary_matches_python,
        "supports_custom_dictionary": status.supports_custom_dictionary,
        "supports_token_codec": status.supports_token_codec,
        "supports_token_aiwire": status.supports_token_aiwire,
    }


def _frame_bytes(message: dict[str, Any]) -> int:
    return len(encode_ai_wire_message(message))


def _build_sustained_session_model(
    *,
    messages: list[dict[str, Any]],
    session_templates: dict[int, str],
    use_native: bool | None,
    level: int,
    encode_stats: Any,
    peer_count: int,
) -> dict[str, object]:
    remote_peer_count = max(1, peer_count - 1)
    peer_handshakes = [
        build_aiwire_handshake(
            level=level,
            use_native=use_native,
            require_session_templates=False,
        )
        for _ in range(remote_peer_count)
    ]
    nary_negotiation = negotiate_aiwire_nary_handshake(
        [handshake.to_dict() for handshake in peer_handshakes],
        level=level,
        use_native=use_native,
        allow_fallback=False,
    )
    if not nary_negotiation.accepted:
        raise RuntimeError(
            f"AIWire sustained-session n-ary handshake failed: {nary_negotiation.reason}"
        )

    template_update = build_aiwire_session_template_update(
        {},
        session_templates,
        epoch=1,
    )
    setup_messages = [handshake.to_dict() for handshake in peer_handshakes]
    setup_messages.extend([nary_negotiation.to_dict(), template_update.to_dict()])
    setup_raw_bytes = sum(_frame_bytes(message) for message in setup_messages)
    setup_framed_bytes = setup_raw_bytes + len(setup_messages) * LENGTH_PREFIX_BYTES
    steady_state_wire_bytes = encode_stats.bytes_out
    steady_state_raw_delta_bytes = encode_stats.bytes_in
    total_wire_with_setup = steady_state_wire_bytes + setup_framed_bytes
    message_count = max(1, len(messages))

    return {
        "mode": "sustained_delta_after_handshake",
        "description": (
            "Handshake and session-template setup are counted once; steady-state "
            "measurements are the delta message stream after peers share shape."
        ),
        "setup_frame_count": len(setup_messages),
        "participant_count": peer_count,
        "remote_peer_count": remote_peer_count,
        "setup_raw_bytes": setup_raw_bytes,
        "setup_framed_bytes": setup_framed_bytes,
        "template_count": len(session_templates),
        "session_template_sha256": aiwire_session_templates_sha256(session_templates),
        "steady_state_messages": len(messages),
        "steady_state_raw_delta_bytes": steady_state_raw_delta_bytes,
        "steady_state_wire_delta_bytes": steady_state_wire_bytes,
        "steady_state_wire_bytes_per_message": steady_state_wire_bytes / message_count,
        "steady_state_raw_delta_bytes_per_message": steady_state_raw_delta_bytes / message_count,
        "amortized_setup_bytes_per_message": setup_framed_bytes / message_count,
        "amortized_wire_bytes_per_message": total_wire_with_setup / message_count,
        "total_wire_bytes_with_setup": total_wire_with_setup,
        "setup_share_percent": (
            setup_framed_bytes / total_wire_with_setup * 100.0 if total_wire_with_setup else 0.0
        ),
        "steady_state_ratio": encode_stats.ratio,
        "amortized_ratio_with_setup": (
            steady_state_raw_delta_bytes / total_wire_with_setup if total_wire_with_setup else 0.0
        ),
        "steady_state_saved_percent": (
            (1 - steady_state_wire_bytes / steady_state_raw_delta_bytes) * 100.0
            if steady_state_raw_delta_bytes
            else 0.0
        ),
        "amortized_saved_percent": (
            (1 - total_wire_with_setup / steady_state_raw_delta_bytes) * 100.0
            if steady_state_raw_delta_bytes
            else 0.0
        ),
    }


def run_benchmark(
    *,
    profile: str = "custom",
    corpus: str = "structured",
    messages: int | None = None,
    seed: int = 1729,
    level: int = 3,
    backend: str = "python",
    sustained_session: bool = False,
    peers: int = 2,
) -> dict[str, Any]:
    """Run the local AIWire benchmark and return stable JSON-compatible results."""

    if profile not in BENCHMARK_PROFILES:
        choices = ", ".join(sorted(BENCHMARK_PROFILES))
        raise ValueError(f"unsupported benchmark profile {profile!r}; choices: {choices}")
    if corpus not in {"structured", "delta"}:
        raise ValueError("unsupported benchmark corpus; choices: structured, delta")
    if sustained_session and corpus != "delta":
        raise ValueError("sustained session benchmark requires corpus='delta'")
    if peers < 2:
        raise ValueError("peers must be at least 2")
    use_native = _use_native_for_backend(backend)

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
    session_templates = (
        discover_ai_wire_session_templates(
            benchmark_messages,
            max_templates=8,
            min_frequency=2,
            starting_template_id=128,
        )
        if sustained_session
        else None
    )
    started = time.perf_counter()
    encoder = AIWireSessionEncoder(
        level=level,
        session_templates=session_templates,
        use_native=use_native,
    )
    try:
        frames = encoder.compress_messages(benchmark_messages)
        encode_stats = encoder.stats
        encode_backend = encoder.backend
    finally:
        encoder.close()
    encoded_at = time.perf_counter()
    decoder = AIWireSessionDecoder(
        session_templates=session_templates,
        use_native=use_native,
    )
    try:
        restored = decoder.decompress_frames(frames)
        decode_stats = decoder.stats
        decode_backend = decoder.backend
    finally:
        decoder.close()
    finished = time.perf_counter()

    if [encode_ai_wire_message(item) for item in restored] != [
        encode_ai_wire_message(item) for item in benchmark_messages
    ]:
        raise RuntimeError("AIWire benchmark round trip failed")

    result: dict[str, Any] = {
        "messages": message_count,
        "benchmark_profile": profile,
        "benchmark_profile_description": profile_info["description"],
        "benchmark_mode": "sustained_session" if sustained_session else "frame_stream",
        "corpus": corpus,
        "dictionary_sha256": AI_WIRE_DICTIONARY_SHA256,
        "requested_backend": backend,
        "encode_backend": encode_backend,
        "decode_backend": decode_backend,
        "native_status": _benchmark_native_status(),
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
    if sustained_session:
        assert session_templates is not None
        result["session_model"] = _build_sustained_session_model(
            messages=benchmark_messages,
            session_templates=session_templates,
            use_native=use_native,
            level=level,
            encode_stats=encode_stats,
            peer_count=peers,
        )
    return result


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
    parser.add_argument(
        "--backend",
        choices=BENCHMARK_BACKENDS,
        default="python",
        help=(
            "AIWire backend to use. python is the stable default; native requires "
            "libaura_aiwire; auto uses native when available and falls back to Python."
        ),
    )
    parser.add_argument(
        "--sustained-session",
        action="store_true",
        help=(
            "Model the main AIWire benefit: one handshake/template setup followed "
            "by steady-state delta traffic. Requires --corpus delta."
        ),
    )
    parser.add_argument(
        "--peers",
        type=int,
        default=2,
        help="Total participants for sustained-session n-ary handshake modeling.",
    )
    args = parser.parse_args(argv)

    try:
        result = run_benchmark(
            profile=args.profile,
            corpus=args.corpus,
            messages=args.messages,
            seed=args.seed,
            level=args.level,
            backend=args.backend,
            sustained_session=args.sustained_session,
            peers=args.peers,
        )
    except (AIWireNativeError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
