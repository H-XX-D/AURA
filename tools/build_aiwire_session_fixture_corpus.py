#!/usr/bin/env python3
"""Generate the public AIWire session fixture corpus."""

from __future__ import annotations

import argparse
from pathlib import Path

from aura_compression.ai_wire_fixtures import (
    DEFAULT_EXCHANGES_PER_SESSION,
    DEFAULT_FIXTURE_SEED,
    DEFAULT_SESSION_COUNT,
    build_aiwire_session_fixture_corpus,
    write_aiwire_session_fixture_corpus,
)

DEFAULT_OUTPUT = Path("fixtures/aiwire_sessions/public_session_corpus_v1.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sessions",
        type=int,
        default=DEFAULT_SESSION_COUNT,
        help="number of sessions to generate",
    )
    parser.add_argument(
        "--exchanges-per-session",
        type=int,
        default=DEFAULT_EXCHANGES_PER_SESSION,
        help="request/response exchange pairs per session",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_FIXTURE_SEED,
        help="base deterministic seed",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="fixture JSON output path",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    corpus = build_aiwire_session_fixture_corpus(
        session_count=args.sessions,
        exchanges_per_session=args.exchanges_per_session,
        seed=args.seed,
    )
    output = write_aiwire_session_fixture_corpus(args.output, corpus)
    print(f"wrote {output}")


if __name__ == "__main__":
    main()
