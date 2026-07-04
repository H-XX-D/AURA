"""Compress one payload with a single AIWire frame."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from aura_compression.ai_wire import AIWireSessionEncoder


def _read_input(path: str | None) -> bytes:
    if path is None or path == "-":
        return sys.stdin.buffer.read()
    return Path(path).read_bytes()


def _write_output(path: str | None, payload: bytes) -> None:
    if path is None or path == "-":
        sys.stdout.buffer.write(payload)
        return
    Path(path).write_bytes(payload)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", help="Input file, or stdin when omitted or '-'")
    parser.add_argument("-o", "--output", help="Output frame path, or stdout when omitted")
    parser.add_argument("--level", type=int, default=3, help="zlib compression level, 0-9")
    parser.add_argument(
        "--no-static-dictionary",
        action="store_true",
        help="Disable the AIWire static dictionary",
    )
    args = parser.parse_args(argv)

    raw = _read_input(args.input)
    encoder = AIWireSessionEncoder(
        level=args.level,
        use_static_dictionary=not args.no_static_dictionary,
        use_native=False,
    )
    frame = encoder.compress_frame(raw)
    _write_output(args.output, frame)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
