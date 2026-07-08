#!/usr/bin/env python3
"""Compare AIWire static and corpus-generated dictionary candidates."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from aura_compression.ai_wire import AI_WIRE_DEFAULT_LEVEL  # noqa: E402
from aura_compression.aiwire_dictionary_comparison import (  # noqa: E402
    build_aiwire_dictionary_comparison_report,
    render_aiwire_dictionary_comparison_markdown,
    write_aiwire_dictionary_comparison_markdown,
    write_aiwire_dictionary_comparison_report,
)
from aura_compression.aiwire_dictionary_generation import (  # noqa: E402
    DEFAULT_MAX_DICTIONARY_BYTES,
    DEFAULT_PUBLIC_FIXTURE_CORPUS,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture-corpus", type=Path, default=DEFAULT_PUBLIC_FIXTURE_CORPUS)
    parser.add_argument("--min-frequency", type=int, default=2)
    parser.add_argument("--min-length", type=int, default=6)
    parser.add_argument("--max-length", type=int, default=160)
    parser.add_argument("--max-entries", type=int, default=128)
    parser.add_argument("--max-dictionary-bytes", type=int, default=DEFAULT_MAX_DICTIONARY_BYTES)
    parser.add_argument("--aiwire-level", type=int, default=AI_WIRE_DEFAULT_LEVEL)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_aiwire_dictionary_comparison_report(
        fixture_corpus=args.fixture_corpus,
        min_frequency=args.min_frequency,
        min_length=args.min_length,
        max_length=args.max_length,
        max_entries=args.max_entries,
        max_dictionary_bytes=args.max_dictionary_bytes,
        level=args.aiwire_level,
    )
    if args.json_output:
        write_aiwire_dictionary_comparison_report(args.json_output, report)
    if args.markdown_output:
        write_aiwire_dictionary_comparison_markdown(args.markdown_output, report)
    if not args.json_output and not args.markdown_output:
        print(render_aiwire_dictionary_comparison_markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
