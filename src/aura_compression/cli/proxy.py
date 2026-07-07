"""CLI for the explicit AIWire TCP sidecar proxy."""

from __future__ import annotations

import argparse
import json

from aura_compression.ai_wire import AI_WIRE_DEFAULT_LEVEL
from aura_compression.aiwire_proxy import (
    DEFAULT_MAX_FRAME_BYTES,
    TUNNEL_CODECS,
    BackendName,
    TunnelCodec,
    TunnelImpairmentConfig,
    run_egress_proxy,
    run_ingress_proxy,
)
from aura_compression.aiwire_proxy_benchmark import (
    DEFAULT_PROXY_FIXTURE_PATH,
    FIXTURE_VARIATION_PROFILES,
    build_proxy_fixture_responder,
    load_proxy_fixture_pairs,
)


def _add_common_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--listen-host", default="127.0.0.1")
    parser.add_argument("--listen-port", type=int, required=True)
    parser.add_argument(
        "--backend",
        choices=("python", "native", "auto"),
        default="auto",
        help="AIWire backend request for this sidecar.",
    )
    parser.add_argument(
        "--tunnel-codec",
        choices=TUNNEL_CODECS,
        default="aiwire",
        help="Semantic payload codec used inside the sidecar tunnel.",
    )
    parser.add_argument("--level", type=int, default=AI_WIRE_DEFAULT_LEVEL)
    parser.add_argument(
        "--max-frame-bytes",
        type=int,
        default=DEFAULT_MAX_FRAME_BYTES,
        help="Reject raw or tunnel frames larger than this many bytes.",
    )
    parser.add_argument(
        "--connections",
        type=int,
        default=None,
        help="Stop after this many accepted connections. Omit for long-running service mode.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Stop after one accepted connection. Useful for tests and smoke runs.",
    )
    parser.add_argument("--connect-timeout", type=float, default=5.0)
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
    parser.add_argument("--metrics-output")
    parser.add_argument("--replay-log-output")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aura-proxy",
        description=(
            "Run an explicit AIWire sidecar proxy. Client/upstream sockets use "
            "uint32 length-prefixed raw frames; the inter-sidecar hop uses AIWire."
        ),
    )
    subparsers = parser.add_subparsers(dest="mode", required=True)

    ingress = subparsers.add_parser(
        "ingress",
        help="Accept local raw frames and tunnel them to an AIWire egress sidecar.",
    )
    _add_common_options(ingress)
    ingress.add_argument("--egress-host", required=True)
    ingress.add_argument("--egress-port", type=int, required=True)

    egress = subparsers.add_parser(
        "egress",
        help="Accept an AIWire tunnel and forward raw frames to an upstream service.",
    )
    _add_common_options(egress)
    egress.add_argument("--upstream-host")
    egress.add_argument("--upstream-port", type=int)
    egress.add_argument(
        "--inline-fixture-corpus",
        default=None,
        help=(
            "Benchmark-only: answer upstream requests in-process from this fixture "
            "corpus instead of opening an upstream TCP socket."
        ),
    )
    egress.add_argument(
        "--inline-fixture-variation-profile",
        choices=FIXTURE_VARIATION_PROFILES,
        default="none",
    )
    egress.add_argument("--inline-fixture-peer-label", default="proxy-fixture")

    return parser


def _max_connections(args: argparse.Namespace) -> int | None:
    if args.once:
        return 1
    connections = args.connections
    return int(connections) if connections is not None else None


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    backend: BackendName = args.backend
    tunnel_codec: TunnelCodec = args.tunnel_codec
    tunnel_impairment_config = TunnelImpairmentConfig(
        bandwidth_mbps=args.tunnel_bandwidth_mbps,
        one_way_delay_ms=args.tunnel_one_way_delay_ms,
        jitter_ms=args.tunnel_jitter_ms,
        tail_pause_probability=args.tunnel_tail_pause_probability,
        tail_pause_ms=args.tunnel_tail_pause_ms,
        seed=args.impairment_seed,
    )

    try:
        if args.mode == "ingress":
            metrics = run_ingress_proxy(
                listen_host=args.listen_host,
                listen_port=args.listen_port,
                egress_host=args.egress_host,
                egress_port=args.egress_port,
                level=args.level,
                backend=backend,
                tunnel_codec=tunnel_codec,
                max_frame_bytes=args.max_frame_bytes,
                max_connections=_max_connections(args),
                connect_timeout=args.connect_timeout,
                tunnel_impairment_config=tunnel_impairment_config,
                metrics_output=args.metrics_output,
                replay_log_output=args.replay_log_output,
            )
        else:
            upstream_responder = None
            upstream_host = args.upstream_host or ""
            upstream_port = int(args.upstream_port or 0)
            if args.inline_fixture_corpus:
                pairs, _fixture_path, _fixture_source = load_proxy_fixture_pairs(
                    args.inline_fixture_corpus or DEFAULT_PROXY_FIXTURE_PATH,
                    fixture_variation_profile=args.inline_fixture_variation_profile,
                    fixture_peer_label=args.inline_fixture_peer_label,
                )
                upstream_responder = build_proxy_fixture_responder(pairs)
            elif not args.upstream_host or args.upstream_port is None:
                parser.error(
                    "egress requires --upstream-host/--upstream-port unless "
                    "--inline-fixture-corpus is set"
                )
            metrics = run_egress_proxy(
                listen_host=args.listen_host,
                listen_port=args.listen_port,
                upstream_host=upstream_host,
                upstream_port=upstream_port,
                upstream_responder=upstream_responder,
                level=args.level,
                backend=backend,
                tunnel_codec=tunnel_codec,
                max_frame_bytes=args.max_frame_bytes,
                max_connections=_max_connections(args),
                connect_timeout=args.connect_timeout,
                tunnel_impairment_config=tunnel_impairment_config,
                metrics_output=args.metrics_output,
                replay_log_output=args.replay_log_output,
            )
    except KeyboardInterrupt:
        return 130

    print(json.dumps(metrics.to_dict(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
