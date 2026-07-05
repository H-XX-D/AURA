#!/usr/bin/env python3
"""Build and verify the optional native AIWire backend."""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from aura_compression.ai_wire import (  # noqa: E402
    AI_WIRE_DEFAULT_LEVEL,
    AI_WIRE_DICTIONARY_FNV1A64,
    AI_WIRE_STATIC_DICTIONARY,
    AIWireNativeError,
    AIWireSessionDecoder,
    AIWireSessionEncoder,
    aiwire_native_status,
    build_ai_wire_messages,
    discover_ai_wire_session_templates,
)
from aura_compression.ai_wire_token import (  # noqa: E402
    AIWireTokenAIWireSessionDecoder,
    AIWireTokenAIWireSessionEncoder,
    AIWireTokenSessionDecoder,
    AIWireTokenSessionEncoder,
)

SCHEMA = "aura.aiwire.native_check.v1"


def _status_dict() -> dict[str, object]:
    return aiwire_native_status().as_dict()


def _platform_info() -> dict[str, str]:
    return {
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "python": platform.python_version(),
    }


def _tail(value: str, limit: int = 4000) -> str:
    return value[-limit:] if len(value) > limit else value


def _run_build(args: argparse.Namespace) -> dict[str, object]:
    command = [
        args.make,
        "-C",
        str(ROOT / "native" / "aiwire"),
        "install",
    ]
    env = os.environ.copy()
    if args.cxx:
        env["CXX"] = args.cxx

    started = time.perf_counter()
    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    elapsed_ms = (time.perf_counter() - started) * 1000
    return {
        "ran": True,
        "command": command,
        "returncode": completed.returncode,
        "elapsed_ms": elapsed_ms,
        "stdout": _tail(completed.stdout),
        "stderr": _tail(completed.stderr),
        "ok": completed.returncode == 0,
    }


def _check_static_dictionary() -> dict[str, object]:
    status = aiwire_native_status()
    expected_checksum = f"{AI_WIRE_DICTIONARY_FNV1A64:016x}"
    if status.dictionary_size != len(AI_WIRE_STATIC_DICTIONARY):
        raise AssertionError(
            f"native dictionary size {status.dictionary_size} != "
            f"{len(AI_WIRE_STATIC_DICTIONARY)}"
        )
    if status.dictionary_checksum != expected_checksum:
        raise AssertionError(
            f"native dictionary checksum {status.dictionary_checksum} != {expected_checksum}"
        )
    if status.dictionary_matches_python is not True:
        raise AssertionError("native dictionary does not match Python dictionary")
    return {
        "dictionary_size": status.dictionary_size,
        "dictionary_checksum": status.dictionary_checksum,
        "dictionary_matches_python": status.dictionary_matches_python,
    }


def _frames_and_templates(args: argparse.Namespace) -> tuple[list[bytes], dict[int, str]]:
    frames = build_ai_wire_messages(args.messages, args.seed)
    templates = discover_ai_wire_session_templates(
        frames,
        max_templates=args.session_template_limit,
        min_frequency=2,
    )
    return frames, templates


def _check_native_aiwire_roundtrip(args: argparse.Namespace) -> dict[str, object]:
    frames, templates = _frames_and_templates(args)
    encoder = AIWireSessionEncoder(
        level=args.level,
        session_templates=templates,
        use_native=True,
    )
    decoder = AIWireSessionDecoder(session_templates=templates, use_native=True)
    try:
        encoded = [encoder.compress_frame(frame) for frame in frames]
        restored = [decoder.decompress_frame(frame) for frame in encoded]
    finally:
        encoder.close()
        decoder.close()

    if restored != frames:
        raise AssertionError("native AIWire round trip changed payloads")
    return {
        "frames": len(frames),
        "session_template_count": len(templates),
        "encode_backend": encoder.backend,
        "decode_backend": decoder.backend,
        "raw_bytes": sum(len(frame) for frame in frames),
        "wire_bytes": sum(len(frame) for frame in encoded),
        "ratio": sum(len(frame) for frame in frames) / sum(len(frame) for frame in encoded),
    }


def _check_python_native_interop(args: argparse.Namespace) -> dict[str, object]:
    frames, templates = _frames_and_templates(args)

    native_encoder = AIWireSessionEncoder(
        level=args.level,
        session_templates=templates,
        use_native=True,
    )
    python_decoder = AIWireSessionDecoder(session_templates=templates, use_native=False)
    try:
        native_payloads = [native_encoder.compress_frame(frame) for frame in frames]
        restored_from_native = [python_decoder.decompress_frame(frame) for frame in native_payloads]
    finally:
        native_encoder.close()
        python_decoder.close()

    python_encoder = AIWireSessionEncoder(
        level=args.level,
        session_templates=templates,
        use_native=False,
    )
    native_decoder = AIWireSessionDecoder(session_templates=templates, use_native=True)
    try:
        python_payloads = [python_encoder.compress_frame(frame) for frame in frames]
        restored_from_python = [native_decoder.decompress_frame(frame) for frame in python_payloads]
    finally:
        python_encoder.close()
        native_decoder.close()

    if restored_from_native != frames:
        raise AssertionError("Python decoder could not read native AIWire frames")
    if restored_from_python != frames:
        raise AssertionError("native decoder could not read Python AIWire frames")
    return {
        "frames": len(frames),
        "session_template_count": len(templates),
        "native_to_python_frames": len(native_payloads),
        "python_to_native_frames": len(python_payloads),
    }


def _check_native_token_roundtrip(args: argparse.Namespace) -> dict[str, object]:
    status = aiwire_native_status()
    if not status.supports_token_codec:
        raise AssertionError("native AIWire backend lacks token codec support")

    frames, _templates = _frames_and_templates(args)
    encoder = AIWireTokenSessionEncoder(use_native=True)
    decoder = AIWireTokenSessionDecoder(use_native=True)
    try:
        encoded = [encoder.encode_frame(frame) for frame in frames]
        restored = [decoder.decode_frame(frame) for frame in encoded]
    finally:
        encoder.close()
        decoder.close()

    if restored != frames:
        raise AssertionError("native AIToken round trip changed payloads")
    return {
        "frames": len(frames),
        "encode_backend": encoder.backend,
        "decode_backend": decoder.backend,
        "raw_bytes": sum(len(frame) for frame in frames),
        "token_bytes": sum(len(frame) for frame in encoded),
    }


def _check_native_token_aiwire_roundtrip(args: argparse.Namespace) -> dict[str, object]:
    status = aiwire_native_status()
    if not status.supports_token_aiwire:
        raise AssertionError("native AIWire backend lacks token+AIWire support")

    frames, templates = _frames_and_templates(args)
    encoder = AIWireTokenAIWireSessionEncoder(
        level=args.level,
        session_templates=templates,
        use_native=True,
    )
    decoder = AIWireTokenAIWireSessionDecoder(
        session_templates=templates,
        use_native=True,
    )
    try:
        encoded = [encoder.encode_frame(frame) for frame in frames]
        restored = [decoder.decode_frame(frame) for frame in encoded]
    finally:
        encoder.close()
        decoder.close()

    if restored != frames:
        raise AssertionError("native AIToken+AIWire round trip changed payloads")
    return {
        "frames": len(frames),
        "session_template_count": len(templates),
        "encode_backend": encoder.backend,
        "decode_backend": decoder.backend,
        "raw_bytes": sum(len(frame) for frame in frames),
        "wire_bytes": sum(len(frame) for frame in encoded),
    }


def _run_check(
    name: str,
    check: Callable[[argparse.Namespace], dict[str, object]],
    args: argparse.Namespace,
) -> dict[str, object]:
    started = time.perf_counter()
    try:
        details = check(args)
        return {
            "name": name,
            "ok": True,
            "elapsed_ms": (time.perf_counter() - started) * 1000,
            **details,
        }
    except Exception as exc:
        return {
            "name": name,
            "ok": False,
            "elapsed_ms": (time.perf_counter() - started) * 1000,
            "error": str(exc),
            "error_type": type(exc).__name__,
        }


def run_checks(args: argparse.Namespace) -> dict[str, Any]:
    build: dict[str, object] = {"ran": False, "ok": True}
    if args.build:
        build = _run_build(args)

    status = _status_dict()
    report: dict[str, Any] = {
        "schema": SCHEMA,
        "ok": True,
        "platform": _platform_info(),
        "build": build,
        "native_status": status,
        "messages": args.messages,
        "seed": args.seed,
        "level": args.level,
        "checks": [],
    }

    if not build.get("ok", False):
        report["ok"] = False
        return report

    if args.status_only:
        return report

    if not status["available"]:
        report["checks"].append(
            {
                "name": "native_available",
                "ok": bool(args.allow_missing),
                "skipped": bool(args.allow_missing),
                "error": status.get("error"),
            }
        )
        report["ok"] = bool(args.allow_missing)
        return report

    checks: list[tuple[str, Callable[[argparse.Namespace], dict[str, object]]]] = [
        ("static_dictionary", lambda _args: _check_static_dictionary()),
        ("native_aiwire_roundtrip", _check_native_aiwire_roundtrip),
        ("python_native_interop", _check_python_native_interop),
    ]
    if not args.skip_token_checks:
        checks.extend(
            [
                ("native_aitoken_roundtrip", _check_native_token_roundtrip),
                ("native_aitoken_aiwire_roundtrip", _check_native_token_aiwire_roundtrip),
            ]
        )

    report["checks"] = [_run_check(name, check, args) for name, check in checks]
    report["ok"] = all(bool(check["ok"]) for check in report["checks"])
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--build",
        action="store_true",
        help="run native/aiwire make install before checking",
    )
    parser.add_argument("--make", default="make", help="make executable to use with --build")
    parser.add_argument("--cxx", help="C++ compiler to pass to make as CXX")
    parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="exit successfully when the native library is unavailable",
    )
    parser.add_argument(
        "--require-native",
        action="store_true",
        help="explicitly require native availability; default unless --allow-missing is set",
    )
    parser.add_argument(
        "--status-only",
        action="store_true",
        help="print build/status JSON without running round-trip checks",
    )
    parser.add_argument("--messages", type=int, default=32)
    parser.add_argument("--seed", type=int, default=1729)
    parser.add_argument("--level", type=int, default=AI_WIRE_DEFAULT_LEVEL)
    parser.add_argument("--session-template-limit", type=int, default=8)
    parser.add_argument(
        "--skip-token-checks",
        action="store_true",
        help="skip native AIToken and AIToken+AIWire checks",
    )
    parser.add_argument("--output", type=Path, help="write the JSON report to this path")
    args = parser.parse_args(argv)
    if args.messages <= 0:
        parser.error("--messages must be positive")
    if args.session_template_limit < 0:
        parser.error("--session-template-limit must be non-negative")
    if args.allow_missing and args.require_native:
        parser.error("--allow-missing and --require-native are mutually exclusive")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = run_checks(args)
    except AIWireNativeError as exc:
        report = {
            "schema": SCHEMA,
            "ok": False,
            "platform": _platform_info(),
            "build": {"ran": bool(args.build), "ok": False},
            "native_status": _status_dict(),
            "checks": [
                {
                    "name": "native_exception",
                    "ok": False,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                }
            ],
        }
    rendered = json.dumps(report, indent=2, sort_keys=True)
    print(rendered)
    if args.output:
        args.output.write_text(rendered + "\n")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
