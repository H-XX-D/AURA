#!/usr/bin/env python3
"""Convert an AIWire benchmark JSON artifact to a replay-log JSONL artifact."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from aura_compression.aiwire_replay_log import (  # noqa: E402
    dumps_replay_log,
    sha256_hex,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("benchmark_json", type=Path)
    parser.add_argument("--source-name", default="")
    parser.add_argument("--output", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    source_bytes = args.benchmark_json.read_bytes()
    benchmark = json.loads(source_bytes)
    source_name = args.source_name or str(args.benchmark_json)
    rendered = dumps_replay_log(
        benchmark,
        source=source_name,
        source_sha256=sha256_hex(source_bytes),
    )
    if args.output:
        args.output.write_text(rendered)
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
