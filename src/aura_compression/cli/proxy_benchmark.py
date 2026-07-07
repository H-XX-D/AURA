"""CLI for the local AIWire proxy benchmark harness."""

from __future__ import annotations

import argparse
import json

from aura_compression.ai_wire import AI_WIRE_DEFAULT_LEVEL
from aura_compression.aiwire_proxy_benchmark import (
    DEFAULT_PROXY_FIXTURE_PATH,
    FIXTURE_VARIATION_PROFILES,
    run_proxy_benchmark,
    run_proxy_ingress_benchmark,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aura-proxy-benchmark",
        description=(
            "Run an AIWire proxy benchmark. By default the harness starts local "
            "fixture, egress, ingress, and client components. Provide "
            "--egress-host/--egress-port to benchmark a local ingress/client "
            "against an already running remote egress sidecar."
        ),
    )
    parser.add_argument("--fixture-corpus", default=str(DEFAULT_PROXY_FIXTURE_PATH))
    parser.add_argument(
        "--fixture-variation-profile",
        choices=FIXTURE_VARIATION_PROFILES,
        default="none",
    )
    parser.add_argument("--fixture-peer-label", default="proxy-fixture")
    parser.add_argument("--seconds", type=float, default=60.0)
    parser.add_argument("--max-exchanges", type=int)
    parser.add_argument(
        "--connections",
        type=int,
        default=1,
        help="parallel client/ingress/egress/fixture connections to use",
    )
    parser.add_argument(
        "--backend",
        choices=("python", "native", "auto"),
        default="python",
    )
    parser.add_argument("--level", type=int, default=AI_WIRE_DEFAULT_LEVEL)
    parser.add_argument("--modeled-link-mbps", type=float, default=10.0)
    parser.add_argument(
        "--tunnel-bandwidth-mbps",
        type=float,
        default=0.0,
        help="Optional aggregate AIWire tunnel bandwidth cap. Zero disables the cap.",
    )
    parser.add_argument(
        "--tunnel-one-way-delay-ms",
        type=float,
        default=0.0,
        help="Optional one-way propagation delay applied to tunnel writes.",
    )
    parser.add_argument(
        "--tunnel-jitter-ms",
        type=float,
        default=0.0,
        help="Optional uniform +/- jitter applied to tunnel writes.",
    )
    parser.add_argument(
        "--tunnel-tail-pause-probability",
        type=float,
        default=0.0,
        help="Probability that a tunnel frame receives an extra tail pause.",
    )
    parser.add_argument(
        "--tunnel-tail-pause-ms",
        type=float,
        default=0.0,
        help="Maximum extra tail-pause delay in milliseconds.",
    )
    parser.add_argument("--impairment-seed", type=int, default=1729)
    parser.add_argument("--egress-host")
    parser.add_argument("--egress-port", type=int)
    parser.add_argument(
        "--ingress-metrics-output",
        help="optional metrics JSON path for the local ingress sidecar in remote-egress mode",
    )
    parser.add_argument("--output")
    parser.add_argument("--replay-log-output")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if bool(args.egress_host) != bool(args.egress_port):
        parser.error("--egress-host and --egress-port must be provided together")
    if args.ingress_metrics_output and not args.egress_host:
        parser.error("--ingress-metrics-output only applies with --egress-host/--egress-port")
    if args.connections <= 0:
        parser.error("--connections must be positive")
    common = {
        "fixture_corpus_path": args.fixture_corpus,
        "fixture_variation_profile": args.fixture_variation_profile,
        "fixture_peer_label": args.fixture_peer_label,
        "seconds": args.seconds,
        "max_exchanges": args.max_exchanges,
        "connections": args.connections,
        "backend": args.backend,
        "level": args.level,
        "modeled_link_mbps": args.modeled_link_mbps,
        "tunnel_bandwidth_mbps": args.tunnel_bandwidth_mbps,
        "tunnel_one_way_delay_ms": args.tunnel_one_way_delay_ms,
        "tunnel_jitter_ms": args.tunnel_jitter_ms,
        "tunnel_tail_pause_probability": args.tunnel_tail_pause_probability,
        "tunnel_tail_pause_ms": args.tunnel_tail_pause_ms,
        "impairment_seed": args.impairment_seed,
        "output": args.output,
        "replay_log_output": args.replay_log_output,
    }
    if args.egress_host:
        result = run_proxy_ingress_benchmark(
            egress_host=args.egress_host,
            egress_port=args.egress_port,
            ingress_metrics_output=args.ingress_metrics_output,
            **common,
        )
    else:
        result = run_proxy_benchmark(**common)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
