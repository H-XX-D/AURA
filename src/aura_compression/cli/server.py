"""Print transport guidance for AIWire server examples."""

from __future__ import annotations


def main(argv: list[str] | None = None) -> int:
    print(
        "AURA does not bundle a production server. Use the transport examples in "
        "the GitHub repo for TCP, WebSocket, HTTP streaming, and local broker "
        "AIWire sessions: https://github.com/H-XX-D/AURA/tree/main/examples"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
