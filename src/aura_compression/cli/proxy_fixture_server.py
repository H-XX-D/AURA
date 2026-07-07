"""CLI for the raw upstream fixture responder used by proxy benchmarks."""

from __future__ import annotations

import argparse
import json

from aura_compression.aiwire_proxy import DEFAULT_MAX_FRAME_BYTES
from aura_compression.aiwire_proxy_benchmark import (
    DEFAULT_PROXY_FIXTURE_PATH,
    FIXTURE_VARIATION_PROFILES,
    UPSTREAM_AGENT_PROFILES,
    run_proxy_fixture_server,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aura-proxy-fixture-server",
        description=(
            "Serve deterministic uint32 length-prefixed fixture responses for "
            "AIWire proxy benchmarks."
        ),
    )
    parser.add_argument("--listen-host", default="127.0.0.1")
    parser.add_argument("--listen-port", type=int, default=8765)
    parser.add_argument("--fixture-corpus", default=str(DEFAULT_PROXY_FIXTURE_PATH))
    parser.add_argument(
        "--fixture-variation-profile",
        choices=FIXTURE_VARIATION_PROFILES,
        default="none",
    )
    parser.add_argument("--fixture-peer-label", default="proxy-fixture")
    parser.add_argument(
        "--upstream-agent-profile",
        choices=UPSTREAM_AGENT_PROFILES,
        default="none",
        help="deterministic benchmark-only local-agent work profile before responses",
    )
    parser.add_argument("--upstream-agent-seed", type=int, default=1729)
    parser.add_argument(
        "--connections",
        type=int,
        default=1,
        help="stop after this many upstream connections",
    )
    parser.add_argument(
        "--max-frame-bytes",
        type=int,
        default=DEFAULT_MAX_FRAME_BYTES,
        help="reject raw frames larger than this many bytes",
    )
    parser.add_argument("--metrics-output")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    metrics = run_proxy_fixture_server(
        listen_host=args.listen_host,
        listen_port=args.listen_port,
        fixture_corpus_path=args.fixture_corpus,
        fixture_variation_profile=args.fixture_variation_profile,
        fixture_peer_label=args.fixture_peer_label,
        upstream_agent_profile=args.upstream_agent_profile,
        upstream_agent_seed=args.upstream_agent_seed,
        max_connections=args.connections,
        max_frame_bytes=args.max_frame_bytes,
        metrics_output=args.metrics_output,
    )
    print(json.dumps(metrics.__dict__, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
