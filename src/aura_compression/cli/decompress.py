"""Decompress one payload produced by ``aura-compress``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from aura_compression.ai_wire import AIWireSessionDecoder


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
    parser.add_argument("input", nargs="?", help="Input frame, or stdin when omitted or '-'")
    parser.add_argument("-o", "--output", help="Output payload path, or stdout when omitted")
    parser.add_argument(
        "--no-static-dictionary",
        action="store_true",
        help="Disable the AIWire static dictionary",
    )
    args = parser.parse_args(argv)

    frame = _read_input(args.input)
    decoder = AIWireSessionDecoder(
        use_static_dictionary=not args.no_static_dictionary,
        use_native=False,
    )
    payload = decoder.decompress_frame(frame)
    _write_output(args.output, payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
