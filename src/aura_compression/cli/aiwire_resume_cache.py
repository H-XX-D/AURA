"""Manage persistent AIWire session-resume cache entries."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from aura_compression.ai_wire import AIWireHandshakeError
from aura_compression.aiwire_resume_cache import (
    AIWireResumeCache,
    AIWireResumeCacheEntry,
    default_aiwire_resume_cache_path,
)


def _load_json(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_json(payload: dict[str, object], output: str | None) -> None:
    rendered = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if output:
        Path(output).write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


def _entry_payload(entry: AIWireResumeCacheEntry) -> dict[str, object]:
    payload = entry.to_dict()
    payload["session_template_count"] = len(entry.session_templates)
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manage persistent AIWire session-resume cache entries.",
    )
    parser.add_argument(
        "--cache",
        default=str(default_aiwire_resume_cache_path()),
        help="Resume-cache JSON path. Defaults to AURA_AIWIRE_RESUME_CACHE or XDG cache.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    put = subparsers.add_parser("put", help="Persist a known peer session dictionary state.")
    put.add_argument("--peer-id", required=True)
    put.add_argument("--app-namespace", default="default")
    put.add_argument("--session-templates", required=True, help="JSON mapping/list of templates.")
    put.add_argument("--epoch", type=int, required=True)
    put.add_argument("--label")
    put.add_argument("--output")

    list_cmd = subparsers.add_parser("list", help="List cached resume states.")
    list_cmd.add_argument("--peer-id")
    list_cmd.add_argument("--app-namespace")
    list_cmd.add_argument("--output")

    hello = subparsers.add_parser("hello", help="Build a resume hello from cached states.")
    hello.add_argument("--peer-id", required=True)
    hello.add_argument("--app-namespace", default="default")
    hello.add_argument("--nonce")
    hello.add_argument("--output")

    negotiate = subparsers.add_parser(
        "negotiate",
        help="Negotiate a resume response for an incoming hello.",
    )
    negotiate.add_argument("--hello", required=True)
    negotiate.add_argument("--nonce")
    negotiate.add_argument("--output")

    verify = subparsers.add_parser("verify", help="Verify a resume response against the cache.")
    verify.add_argument("--hello", required=True)
    verify.add_argument("--response", required=True)
    verify.add_argument("--output")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        cache = AIWireResumeCache(args.cache)

        if args.command == "put":
            entry = cache.put_state(
                peer_id=args.peer_id,
                app_namespace=args.app_namespace,
                session_templates=_load_json(args.session_templates),
                epoch=args.epoch,
                label=args.label,
            )
            _write_json(_entry_payload(entry), args.output)
            return 0

        if args.command == "list":
            entries = cache.entries
            if args.peer_id is not None:
                entries = tuple(entry for entry in entries if entry.peer_id == args.peer_id)
            if args.app_namespace is not None:
                entries = tuple(
                    entry for entry in entries if entry.app_namespace == args.app_namespace
                )
            _write_json(
                {
                    "schema": "aura.aiwire.resume_cache.list.v1",
                    "cache": str(cache.path),
                    "entries": [_entry_payload(entry) for entry in entries],
                },
                args.output,
            )
            return 0

        if args.command == "hello":
            hello = cache.build_resume_hello(
                peer_id=args.peer_id,
                app_namespace=args.app_namespace,
                nonce=args.nonce,
            )
            _write_json(hello.to_dict(), args.output)
            return 0

        if args.command == "negotiate":
            response = cache.negotiate_resume(_load_json(args.hello), nonce=args.nonce)
            _write_json(response.to_dict(), args.output)
            return 0 if response.accepted else 2

        if args.command == "verify":
            entry = cache.verify_resume_response(
                _load_json(args.hello),
                _load_json(args.response),
            )
            _write_json(
                {
                    "schema": "aura.aiwire.resume_cache.verify.v1",
                    "accepted": True,
                    "entry": _entry_payload(entry),
                },
                args.output,
            )
            return 0

        parser.error(f"unsupported command: {args.command}")
        return 2
    except (OSError, json.JSONDecodeError, AIWireHandshakeError, ValueError) as exc:
        parser.error(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
