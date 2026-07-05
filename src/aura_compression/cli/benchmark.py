"""Run a small local AIWire message benchmark."""

from __future__ import annotations

import argparse
import json
import time

from aura_compression.ai_wire import (
    AI_WIRE_DICTIONARY_SHA256,
    build_structured_ai_messages,
    compress_ai_wire_frames,
    decompress_ai_wire_frames,
    encode_ai_wire_message,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--messages", type=int, default=1024, help="Number of messages")
    parser.add_argument("--seed", type=int, default=1729, help="Synthetic corpus seed")
    parser.add_argument("--level", type=int, default=3, help="zlib compression level, 0-9")
    args = parser.parse_args(argv)

    messages = build_structured_ai_messages(args.messages, seed=args.seed)
    started = time.perf_counter()
    frames, encode_stats = compress_ai_wire_frames(messages, level=args.level, use_native=False)
    encoded_at = time.perf_counter()
    restored, decode_stats = decompress_ai_wire_frames(frames, use_native=False)
    finished = time.perf_counter()

    if [encode_ai_wire_message(item) for item in restored] != [
        encode_ai_wire_message(item) for item in messages
    ]:
        raise RuntimeError("AIWire benchmark round trip failed")

    result = {
        "messages": args.messages,
        "dictionary_sha256": AI_WIRE_DICTIONARY_SHA256,
        "encode_seconds": encoded_at - started,
        "decode_seconds": finished - encoded_at,
        "encode_stats": encode_stats.as_dict(),
        "decode_stats": decode_stats.as_dict(),
        "bytes_in": encode_stats.bytes_in,
        "bytes_out": encode_stats.bytes_out,
        "ratio": encode_stats.ratio,
        "decode_bytes_out": decode_stats.bytes_out,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
