"""Offline AIWire dictionary comparison and compatibility matrix helpers."""

from __future__ import annotations

import hashlib
import json
import zlib
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

from .ai_wire import (
    AI_WIRE_DEFAULT_LEVEL,
    AI_WIRE_DELTA_VERSION,
    AI_WIRE_DICTIONARY_FNV1A64,
    AI_WIRE_DICTIONARY_SHA256,
    AI_WIRE_PROTOCOL,
    AI_WIRE_STATIC_DICTIONARY,
    AI_WIRE_VERSION,
)
from .ai_wire_messages import encode_ai_wire_message, summarize_ai_wire_corpus
from .aiwire_dictionary_generation import (
    DEFAULT_MAX_DICTIONARY_BYTES,
    DEFAULT_PUBLIC_FIXTURE_CORPUS,
    AIWireDictionaryCandidate,
    build_aiwire_candidate_dictionary_bytes,
    build_aiwire_dictionary_candidate_report,
    discover_aiwire_dictionary_candidates,
    load_aiwire_fixture_messages,
)

AIWIRE_DICTIONARY_COMPARISON_SCHEMA = "aura.aiwire.dictionary_comparison.v1"


def _sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _fnv1a64(data: bytes) -> int:
    value = 0xCBF29CE484222325
    for byte in data:
        value ^= byte
        value = (value * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return value


def _saved_percent(raw_bytes: float, wire_bytes: float) -> float:
    return (1.0 - wire_bytes / raw_bytes) * 100.0 if raw_bytes else 0.0


def _zlib_stream_round_trip(
    frames: Iterable[bytes],
    *,
    dictionary: bytes,
    level: int,
) -> tuple[list[bytes], list[bytes]]:
    raw_frames = list(frames)
    compress_kwargs: dict[str, Any] = {}
    decompress_kwargs: dict[str, Any] = {}
    if dictionary:
        compress_kwargs["zdict"] = dictionary
        decompress_kwargs["zdict"] = dictionary

    compressor = zlib.compressobj(
        level=level,
        method=zlib.DEFLATED,
        wbits=-15,
        memLevel=8,
        strategy=zlib.Z_DEFAULT_STRATEGY,
        **compress_kwargs,
    )
    compressed = [
        compressor.compress(frame) + compressor.flush(zlib.Z_SYNC_FLUSH) for frame in raw_frames
    ]

    decompressor = zlib.decompressobj(wbits=-15, **decompress_kwargs)
    restored = [decompressor.decompress(frame) for frame in compressed]
    return compressed, restored


def _protocol_mix(messages: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    return dict(
        sorted(Counter(str(message.get("protocol", "unknown")) for message in messages).items())
    )


def _candidate_from_dict(value: Mapping[str, Any]) -> AIWireDictionaryCandidate:
    return AIWireDictionaryCandidate(
        term=str(value["term"]),
        occurrences=int(value["occurrences"]),
        frame_count=int(value["frame_count"]),
        byte_length=int(value["byte_length"]),
        estimated_saved_bytes=int(value["estimated_saved_bytes"]),
        in_static_dictionary=bool(value["in_static_dictionary"]),
        sources=tuple(str(source) for source in value.get("sources", [])),
    )


def _dictionary_identity(
    *,
    name: str,
    kind: str,
    protocol_scope: str,
    dictionary: bytes,
    candidate_term_count: int,
) -> dict[str, object]:
    return {
        "name": name,
        "kind": kind,
        "protocol_scope": protocol_scope,
        "bytes": len(dictionary),
        "sha256": _sha256_hex(dictionary) if dictionary else "",
        "fnv1a64": f"{_fnv1a64(dictionary):016x}" if dictionary else "",
        "candidate_term_count": candidate_term_count,
    }


def _measure_dictionary(
    *,
    dictionary: Mapping[str, Any],
    messages: list[Mapping[str, Any]],
    message_scope: str,
    level: int,
) -> dict[str, object]:
    raw_frames = [encode_ai_wire_message(message) for message in messages]
    compressed, restored = _zlib_stream_round_trip(
        raw_frames,
        dictionary=bytes(dictionary["bytes_payload"]),
        level=level,
    )
    verified = restored == raw_frames
    raw_bytes = sum(len(frame) for frame in raw_frames)
    wire_bytes = sum(len(frame) for frame in compressed)
    frame_count = len(raw_frames)
    return {
        "dictionary": dictionary["name"],
        "dictionary_kind": dictionary["kind"],
        "dictionary_protocol_scope": dictionary["protocol_scope"],
        "message_scope": message_scope,
        "frame_count": frame_count,
        "raw_bytes": raw_bytes,
        "wire_bytes": wire_bytes,
        "wire_bytes_per_frame": wire_bytes / frame_count if frame_count else 0.0,
        "ratio": raw_bytes / wire_bytes if wire_bytes else 0.0,
        "saved_percent": _saved_percent(raw_bytes, wire_bytes),
        "round_trip_verified": verified,
    }


def _compatibility_row(dictionary: Mapping[str, Any]) -> dict[str, object]:
    is_current = dictionary["kind"] == "current_static"
    is_no_dictionary = dictionary["kind"] == "zlib_no_dictionary"
    return {
        "dictionary": dictionary["name"],
        "kind": dictionary["kind"],
        "protocol_scope": dictionary["protocol_scope"],
        "aiwire_protocol_version": AI_WIRE_VERSION,
        "delta_version": AI_WIRE_DELTA_VERSION,
        "sha256": dictionary["sha256"],
        "fnv1a64": dictionary["fnv1a64"],
        "bytes": dictionary["bytes"],
        "manifest_status": (
            "current_compatible"
            if is_current
            else "fallback_baseline" if is_no_dictionary else "candidate_only"
        ),
        "deployment_rule": (
            "already pinned by AIWire v1 compatibility manifests"
            if is_current
            else (
                "stateless zlib baseline, not an AIWire static dictionary"
                if is_no_dictionary
                else "requires a new dictionary version/hash in compatibility manifests"
            )
        ),
    }


def _protocol_messages(
    messages: Iterable[Mapping[str, Any]],
    protocol: str,
) -> list[Mapping[str, Any]]:
    return [message for message in messages if str(message.get("protocol", "unknown")) == protocol]


def build_aiwire_dictionary_comparison_report(
    *,
    fixture_corpus: str | Path = DEFAULT_PUBLIC_FIXTURE_CORPUS,
    min_frequency: int = 2,
    min_length: int = 6,
    max_length: int = 160,
    max_entries: int = 128,
    max_dictionary_bytes: int = DEFAULT_MAX_DICTIONARY_BYTES,
    level: int = AI_WIRE_DEFAULT_LEVEL,
) -> dict[str, object]:
    """Compare current and generated AIWire dictionaries against fixture messages."""

    corpus_path = Path(fixture_corpus)
    corpus, messages = load_aiwire_fixture_messages(corpus_path)
    if not messages:
        raise ValueError("fixture corpus did not contain message events")

    candidate_report = build_aiwire_dictionary_candidate_report(
        fixture_corpus=corpus_path,
        min_frequency=min_frequency,
        min_length=min_length,
        max_length=max_length,
        max_entries=max_entries,
        max_dictionary_bytes=max_dictionary_bytes,
    )
    combined_candidates = [
        _candidate_from_dict(candidate)
        for candidate in candidate_report["candidate_terms"]
        if isinstance(candidate, Mapping)
    ]
    combined_dictionary = build_aiwire_candidate_dictionary_bytes(
        combined_candidates,
        max_bytes=max_dictionary_bytes,
    )

    dictionaries: list[dict[str, Any]] = []
    dictionary_payloads = [
        {
            **_dictionary_identity(
                name="no_dictionary",
                kind="zlib_no_dictionary",
                protocol_scope="all",
                dictionary=b"",
                candidate_term_count=0,
            ),
            "bytes_payload": b"",
        },
        {
            **_dictionary_identity(
                name="aiwire_v1_static",
                kind="current_static",
                protocol_scope="all",
                dictionary=AI_WIRE_STATIC_DICTIONARY,
                candidate_term_count=0,
            ),
            "sha256": AI_WIRE_DICTIONARY_SHA256,
            "fnv1a64": f"{AI_WIRE_DICTIONARY_FNV1A64:016x}",
            "bytes_payload": AI_WIRE_STATIC_DICTIONARY,
        },
        {
            **_dictionary_identity(
                name="generated_combined",
                kind="generated_combined",
                protocol_scope="all",
                dictionary=combined_dictionary,
                candidate_term_count=len(combined_candidates),
            ),
            "bytes_payload": combined_dictionary,
        },
    ]

    protocol_counts = _protocol_mix(messages)
    for protocol, count in protocol_counts.items():
        if protocol == "unknown" or count < min_frequency:
            continue
        protocol_subset = _protocol_messages(messages, protocol)
        candidates = discover_aiwire_dictionary_candidates(
            protocol_subset,
            min_frequency=min_frequency,
            min_length=min_length,
            max_length=max_length,
            max_entries=max_entries,
        )
        dictionary = build_aiwire_candidate_dictionary_bytes(
            candidates,
            max_bytes=max_dictionary_bytes,
        )
        safe_protocol = protocol.replace(".", "_").replace("-", "_")
        dictionary_payloads.append(
            {
                **_dictionary_identity(
                    name=f"generated_{safe_protocol}",
                    kind="generated_protocol_specific",
                    protocol_scope=protocol,
                    dictionary=dictionary,
                    candidate_term_count=len(candidates),
                ),
                "bytes_payload": dictionary,
            }
        )

    measurements: list[dict[str, object]] = []
    for dictionary in dictionary_payloads:
        dictionaries.append(
            {key: value for key, value in dictionary.items() if key != "bytes_payload"}
        )
        if dictionary["protocol_scope"] == "all":
            measurements.append(
                _measure_dictionary(
                    dictionary=dictionary,
                    messages=messages,
                    message_scope="all",
                    level=level,
                )
            )
            for protocol in protocol_counts:
                protocol_subset = _protocol_messages(messages, protocol)
                if protocol_subset:
                    measurements.append(
                        _measure_dictionary(
                            dictionary=dictionary,
                            messages=protocol_subset,
                            message_scope=protocol,
                            level=level,
                        )
                    )
        else:
            protocol_subset = _protocol_messages(messages, str(dictionary["protocol_scope"]))
            if protocol_subset:
                measurements.append(
                    _measure_dictionary(
                        dictionary=dictionary,
                        messages=protocol_subset,
                        message_scope=str(dictionary["protocol_scope"]),
                        level=level,
                    )
                )

    return {
        "schema": AIWIRE_DICTIONARY_COMPARISON_SCHEMA,
        "protocol": AI_WIRE_PROTOCOL,
        "aiwire_version": AI_WIRE_VERSION,
        "delta_version": AI_WIRE_DELTA_VERSION,
        "source": {
            "fixture_corpus": str(corpus_path),
            "fixture_schema": corpus.get("schema"),
            "session_count": corpus.get("session_count"),
            "message_count": len(messages),
        },
        "parameters": {
            "min_frequency": min_frequency,
            "min_length": min_length,
            "max_length": max_length,
            "max_entries": max_entries,
            "max_dictionary_bytes": max_dictionary_bytes,
            "zlib_level": level,
        },
        "corpus_summary": summarize_ai_wire_corpus(messages),
        "protocol_mix": protocol_counts,
        "candidate_report": {
            "schema": candidate_report["schema"],
            "candidate_count": candidate_report["candidate_count"],
            "candidate_dictionary": candidate_report["candidate_dictionary"],
        },
        "dictionaries": dictionaries,
        "compatibility_matrix": [_compatibility_row(dictionary) for dictionary in dictionaries],
        "measurements": measurements,
    }


def _fmt(value: Any, digits: int = 2) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, int):
        return f"{value:,}"
    return f"{float(value):,.{digits}f}"


def render_aiwire_dictionary_comparison_markdown(report: Mapping[str, Any]) -> str:
    """Render a concise Markdown dictionary comparison report."""

    parameters = report["parameters"]
    source = report["source"]
    lines = [
        "# AIWire Dictionary Comparison Matrix",
        "",
        "This report compares the pinned AIWire v1 static dictionary with corpus-derived "
        "candidate dictionaries. Generated dictionaries are measurement artifacts only; "
        "using one in a deployed peer would require a new compatibility-manifest hash.",
        "",
        "## Run Shape",
        "",
        f"- Fixture corpus: `{source['fixture_corpus']}`",
        f"- Sessions: `{source['session_count']}`",
        f"- Messages: `{source['message_count']}`",
        f"- zlib level: `{parameters['zlib_level']}`",
        f"- Max entries per generated dictionary: `{parameters['max_entries']}`",
        f"- Max dictionary bytes: `{parameters['max_dictionary_bytes']}`",
        "",
        "## Dictionary Matrix",
        "",
        "| Dictionary | Kind | Scope | Bytes | SHA-256 | FNV-1a64 | Manifest status |",
        "|---|---|---|---:|---|---|---|",
    ]
    compatibility_by_name = {
        row["dictionary"]: row for row in report["compatibility_matrix"]  # type: ignore[index]
    }
    for dictionary in report["dictionaries"]:
        compatibility = compatibility_by_name[dictionary["name"]]
        lines.append(
            "| {name} | {kind} | {scope} | {bytes} | `{sha}` | `{fnv}` | {status} |".format(
                name=dictionary["name"],
                kind=dictionary["kind"],
                scope=dictionary["protocol_scope"],
                bytes=_fmt(dictionary["bytes"], 0),
                sha=dictionary["sha256"] or "none",
                fnv=dictionary["fnv1a64"] or "none",
                status=compatibility["manifest_status"],
            )
        )

    lines.extend(
        [
            "",
            "## All-Message Measurements",
            "",
            "| Dictionary | Raw B | Wire B | B/frame | Ratio | Saved | Verified |",
            "|---|---:|---:|---:|---:|---:|---|",
        ]
    )
    for row in report["measurements"]:
        if row["message_scope"] != "all":
            continue
        lines.append(
            "| {dictionary} | {raw} | {wire} | {bpf} | {ratio}x | {saved}% | `{verified}` |".format(
                dictionary=row["dictionary"],
                raw=_fmt(row["raw_bytes"], 0),
                wire=_fmt(row["wire_bytes"], 0),
                bpf=_fmt(row["wire_bytes_per_frame"], 1),
                ratio=_fmt(row["ratio"], 2),
                saved=_fmt(row["saved_percent"], 1),
                verified=row["round_trip_verified"],
            )
        )

    lines.extend(
        [
            "",
            "## Protocol-Scope Measurements",
            "",
            "| Dictionary | Message scope | Frames | Wire B | B/frame | Ratio | Saved |",
            "|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in report["measurements"]:
        if row["message_scope"] == "all":
            continue
        if row["dictionary_kind"] == "zlib_no_dictionary":
            continue
        lines.append(
            "| {dictionary} | {scope} | {frames} | {wire} | {bpf} | {ratio}x | {saved}% |".format(
                dictionary=row["dictionary"],
                scope=row["message_scope"],
                frames=_fmt(row["frame_count"], 0),
                wire=_fmt(row["wire_bytes"], 0),
                bpf=_fmt(row["wire_bytes_per_frame"], 1),
                ratio=_fmt(row["ratio"], 2),
                saved=_fmt(row["saved_percent"], 1),
            )
        )
    lines.append("")
    return "\n".join(lines)


def write_aiwire_dictionary_comparison_report(
    output: str | Path,
    report: Mapping[str, Any],
) -> Path:
    """Write a stable JSON dictionary comparison report."""

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return output_path


def write_aiwire_dictionary_comparison_markdown(
    output: str | Path,
    report: Mapping[str, Any],
) -> Path:
    """Write a Markdown dictionary comparison report."""

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        render_aiwire_dictionary_comparison_markdown(report),
        encoding="utf-8",
    )
    return output_path
