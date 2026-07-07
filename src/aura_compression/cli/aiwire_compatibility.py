"""Emit and compare AIWire dictionary compatibility manifests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from aura_compression.ai_wire import (
    AIWireHandshakeError,
    aiwire_compatibility_manifest_sha256,
    build_aiwire_compatibility_manifest,
    verify_aiwire_compatibility_manifest,
)


def _load_json(path: str | None) -> Any:
    if path is None:
        return None
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _manifest_payload(value: Any) -> Any:
    if isinstance(value, dict) and "manifest" in value:
        return value["manifest"]
    return value


def _write_json(payload: dict[str, object], output: str | None) -> None:
    rendered = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if output:
        Path(output).write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Emit or compare AIWire compatibility manifests.",
    )
    parser.add_argument(
        "--session-templates",
        help="Optional JSON mapping/list of session templates to include in the manifest.",
    )
    parser.add_argument("--session-template-epoch", type=int, default=0)
    parser.add_argument("--session-dictionary-epoch", type=int)
    parser.add_argument(
        "--control-lut",
        help="Optional JSON list of routine control LUT entries.",
    )
    parser.add_argument("--control-lut-epoch", type=int, default=0)
    parser.add_argument(
        "--fallback-codecs",
        default="zlib,raw",
        help="Comma-separated fallback codecs to advertise.",
    )
    parser.add_argument(
        "--peer-manifest",
        help="Optional peer manifest JSON. When set, output is a compatibility check.",
    )
    parser.add_argument(
        "--require-session-templates",
        action="store_true",
        help="Reject AIWire when session-template state is absent or mismatched.",
    )
    parser.add_argument(
        "--no-require-session-dictionary",
        action="store_true",
        help="Do not compare session dictionary state hashes.",
    )
    parser.add_argument(
        "--require-control-lut",
        action="store_true",
        help="Reject AIWire when routine-control LUT state is absent or mismatched.",
    )
    parser.add_argument(
        "--no-fallback",
        action="store_true",
        help="Reject instead of selecting raw/zlib fallback on mismatch.",
    )
    parser.add_argument("--output", help="Optional JSON output path.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        fallback_codecs = tuple(
            codec.strip() for codec in args.fallback_codecs.split(",") if codec.strip()
        )
        manifest = build_aiwire_compatibility_manifest(
            fallback_codecs=fallback_codecs,
            session_templates=_load_json(args.session_templates),
            session_template_epoch=args.session_template_epoch,
            session_dictionary_epoch=args.session_dictionary_epoch,
            control_lut=_load_json(args.control_lut),
            control_lut_epoch=args.control_lut_epoch,
        )
        manifest_dict = manifest.to_dict()
        manifest_dict["manifest_sha256"] = aiwire_compatibility_manifest_sha256(manifest)

        peer_payload = _load_json(args.peer_manifest)
        if peer_payload is None:
            _write_json(manifest_dict, args.output)
            return 0

        check = verify_aiwire_compatibility_manifest(
            _manifest_payload(peer_payload),
            local_manifest=manifest,
            require_session_templates=args.require_session_templates,
            require_session_dictionary=not args.no_require_session_dictionary,
            require_control_lut=args.require_control_lut,
            allow_fallback=not args.no_fallback,
        )
        _write_json(check.to_dict(), args.output)
        return 0 if check.accepted else 2
    except (OSError, json.JSONDecodeError, AIWireHandshakeError, ValueError) as exc:
        parser.error(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
