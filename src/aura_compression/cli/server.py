"""Print transport guidance for AIWire server examples."""

from __future__ import annotations


def main(argv: list[str] | None = None) -> int:
    print(
        "AURA bundles an explicit AIWire sidecar as `aura-proxy`. Use "
        "`aura-proxy ingress --help` and `aura-proxy egress --help` for the "
        "raw-frame-to-AIWire tunnel. The transport examples for TCP, WebSocket, "
        "HTTP streaming, and local broker sessions remain in "
        "https://github.com/H-XX-D/AURA/tree/main/examples"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
