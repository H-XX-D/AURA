"""Generate AIWire static-dictionary candidates from fixture corpora."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from aura_compression.aiwire_dictionary_generation import (
    DEFAULT_MAX_DICTIONARY_BYTES,
    DEFAULT_PUBLIC_FIXTURE_CORPUS,
    build_aiwire_dictionary_candidate_report,
    write_aiwire_candidate_dictionary,
    write_aiwire_dictionary_candidate_report,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate deterministic AIWire dictionary candidate artifacts.",
    )
    parser.add_argument(
        "--fixture-corpus",
        default=str(DEFAULT_PUBLIC_FIXTURE_CORPUS),
        help="AIWire fixture corpus JSON path.",
    )
    parser.add_argument("--min-frequency", type=int, default=2)
    parser.add_argument("--min-length", type=int, default=6)
    parser.add_argument("--max-length", type=int, default=160)
    parser.add_argument("--max-entries", type=int, default=128)
    parser.add_argument("--max-dictionary-bytes", type=int, default=DEFAULT_MAX_DICTIONARY_BYTES)
    parser.add_argument("--output", help="Optional JSON report output path.")
    parser.add_argument(
        "--dictionary-output",
        help="Optional raw zlib dictionary candidate bytes output path.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        report = build_aiwire_dictionary_candidate_report(
            fixture_corpus=args.fixture_corpus,
            min_frequency=args.min_frequency,
            min_length=args.min_length,
            max_length=args.max_length,
            max_entries=args.max_entries,
            max_dictionary_bytes=args.max_dictionary_bytes,
        )
        if args.dictionary_output:
            write_aiwire_candidate_dictionary(args.dictionary_output, report)
            report["dictionary_output"] = str(Path(args.dictionary_output))
        if args.output:
            write_aiwire_dictionary_candidate_report(args.output, report)
        else:
            print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
