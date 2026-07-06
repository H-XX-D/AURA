"""CLI for the local AIWire proxy benchmark harness."""

from __future__ import annotations

import argparse
import json

from aura_compression.ai_wire import AI_WIRE_DEFAULT_LEVEL
from aura_compression.aiwire_proxy_benchmark import (
    DEFAULT_PROXY_FIXTURE_PATH,
    run_proxy_benchmark,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aura-proxy-benchmark",
        description="Run a local ingress -> AIWire tunnel -> egress sidecar benchmark.",
    )
    parser.add_argument("--fixture-corpus", default=str(DEFAULT_PROXY_FIXTURE_PATH))
    parser.add_argument("--seconds", type=float, default=60.0)
    parser.add_argument("--max-exchanges", type=int)
    parser.add_argument(
        "--backend",
        choices=("python", "native", "auto"),
        default="python",
    )
    parser.add_argument("--level", type=int, default=AI_WIRE_DEFAULT_LEVEL)
    parser.add_argument("--modeled-link-mbps", type=float, default=10.0)
    parser.add_argument("--output")
    parser.add_argument("--replay-log-output")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    result = run_proxy_benchmark(
        fixture_corpus_path=args.fixture_corpus,
        seconds=args.seconds,
        max_exchanges=args.max_exchanges,
        backend=args.backend,
        level=args.level,
        modeled_link_mbps=args.modeled_link_mbps,
        output=args.output,
        replay_log_output=args.replay_log_output,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
