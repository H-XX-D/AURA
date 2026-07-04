#!/usr/bin/env python3
"""Benchmark AIWire fixture corpus bandwidth saturation across network profiles."""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
import zlib
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
TOOLS = ROOT / "tools"
for candidate in (SRC, TOOLS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from aiwire_network_profiles import profiles_as_dicts, resolve_network_profiles

from aura_compression.ai_wire import (
    AI_WIRE_DEFAULT_LEVEL,
    AIWireSessionDecoder,
    AIWireSessionEncoder,
    AIWireSessionTemplates,
    encode_ai_wire_message,
)
from aura_compression.ai_wire_fixtures import (
    DEFAULT_EXCHANGES_PER_SESSION,
    DEFAULT_SESSION_COUNT,
    load_aiwire_session_fixture_corpus,
)
from aura_compression.ai_wire_token import (
    AIWireTokenAIWireSessionDecoder,
    AIWireTokenAIWireSessionEncoder,
    AIWireTokenSessionDecoder,
    AIWireTokenSessionEncoder,
)

U32_SIZE = 4
DEFAULT_FIXTURE_PATH = ROOT / "fixtures" / "aiwire_sessions" / "public_session_corpus_v1.json"
AIWIRE_CODECS = {"aiwire", "aitoken_aiwire"}
SUPPORTED_CODECS = ("raw", "zlib", "aitoken", "aiwire", "aitoken_aiwire")
SIDE_CHANNEL_KEYS = (
    "client_handshake",
    "server_negotiation",
    "template_update",
    "dictionary_diff",
    "dictionary_ack",
)


@dataclass(frozen=True)
class DirectionMeasurement:
    frames: int
    raw_bytes: int
    wire_bytes: int
    encode_ms: float
    decode_ms: float
    backend: str


def _split_csv(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split(",") if part.strip())


def _split_ints(value: str) -> tuple[int, ...]:
    return tuple(int(part.strip()) for part in value.split(",") if part.strip())


def _use_native(backend: str) -> bool | None:
    if backend == "python":
        return False
    if backend == "native":
        return True
    if backend == "auto":
        return None
    raise ValueError("backend must be one of: python, native, auto")


def _templates_from_entries(entries: Iterable[Mapping[str, Any]]) -> dict[int, str]:
    return {int(entry["template_id"]): str(entry["pattern"]) for entry in entries}


def _session_side_channel_bytes(session: Mapping[str, Any]) -> int:
    return sum(len(encode_ai_wire_message(session[key])) + U32_SIZE for key in SIDE_CHANNEL_KEYS)


def _encode_decode_frames(
    codec: str,
    frames: list[bytes],
    *,
    session_templates: AIWireSessionTemplates | None = None,
    use_native: bool | None = False,
    level: int = AI_WIRE_DEFAULT_LEVEL,
) -> DirectionMeasurement:
    if not frames:
        return DirectionMeasurement(0, 0, 0, 0.0, 0.0, codec)

    encode_start = time.perf_counter_ns()
    backend = codec
    if codec == "raw":
        encoded = list(frames)
    elif codec == "zlib":
        encoded = [zlib.compress(frame, level) for frame in frames]
    elif codec == "aitoken":
        encoder = AIWireTokenSessionEncoder(use_native=use_native)
        try:
            encoded = [encoder.encode_frame(frame) for frame in frames]
            backend = encoder.backend
        finally:
            encoder.close()
    elif codec == "aiwire":
        encoder = AIWireSessionEncoder(
            level=level,
            session_templates=session_templates,
            use_native=use_native,
        )
        try:
            encoded = [encoder.compress_frame(frame) for frame in frames]
            backend = encoder.backend
        finally:
            encoder.close()
    elif codec == "aitoken_aiwire":
        encoder = AIWireTokenAIWireSessionEncoder(
            level=level,
            session_templates=session_templates,
            use_native=use_native,
        )
        try:
            encoded = [encoder.encode_frame(frame) for frame in frames]
            backend = encoder.backend
        finally:
            encoder.close()
    else:
        raise ValueError(f"unsupported codec: {codec}")
    encode_ms = (time.perf_counter_ns() - encode_start) / 1_000_000

    decode_start = time.perf_counter_ns()
    if codec == "raw":
        restored = list(encoded)
    elif codec == "zlib":
        restored = [zlib.decompress(frame) for frame in encoded]
    elif codec == "aitoken":
        decoder = AIWireTokenSessionDecoder(use_native=use_native)
        try:
            restored = [decoder.decode_frame(frame) for frame in encoded]
        finally:
            decoder.close()
    elif codec == "aiwire":
        decoder = AIWireSessionDecoder(
            session_templates=session_templates,
            use_native=use_native,
        )
        try:
            restored = [decoder.decompress_frame(frame) for frame in encoded]
        finally:
            decoder.close()
    elif codec == "aitoken_aiwire":
        decoder = AIWireTokenAIWireSessionDecoder(
            session_templates=session_templates,
            use_native=use_native,
        )
        try:
            restored = [decoder.decode_frame(frame) for frame in encoded]
        finally:
            decoder.close()
    decode_ms = (time.perf_counter_ns() - decode_start) / 1_000_000

    if restored != frames:
        raise RuntimeError(f"{codec} fixture saturation round trip failed")

    return DirectionMeasurement(
        frames=len(frames),
        raw_bytes=sum(len(frame) for frame in frames),
        wire_bytes=sum(len(frame) for frame in encoded),
        encode_ms=encode_ms,
        decode_ms=decode_ms,
        backend=backend,
    )


def _measure_direction(
    codec: str,
    events: list[Mapping[str, Any]],
    *,
    initial_templates: AIWireSessionTemplates,
    updated_templates: AIWireSessionTemplates,
    use_native: bool | None,
    level: int,
) -> DirectionMeasurement:
    if codec not in AIWIRE_CODECS:
        frames = [encode_ai_wire_message(event["message"]) for event in events]
        return _encode_decode_frames(codec, frames, use_native=use_native, level=level)

    totals = DirectionMeasurement(0, 0, 0, 0.0, 0.0, codec)
    backends: set[str] = set()
    for epoch, templates in ((0, initial_templates), (1, updated_templates)):
        frames = [
            encode_ai_wire_message(event["message"])
            for event in events
            if int(event["template_epoch"]) == epoch
        ]
        measured = _encode_decode_frames(
            codec,
            frames,
            session_templates=templates,
            use_native=use_native,
            level=level,
        )
        if measured.frames:
            backends.add(measured.backend)
        totals = DirectionMeasurement(
            frames=totals.frames + measured.frames,
            raw_bytes=totals.raw_bytes + measured.raw_bytes,
            wire_bytes=totals.wire_bytes + measured.wire_bytes,
            encode_ms=totals.encode_ms + measured.encode_ms,
            decode_ms=totals.decode_ms + measured.decode_ms,
            backend=codec,
        )
    return DirectionMeasurement(
        frames=totals.frames,
        raw_bytes=totals.raw_bytes,
        wire_bytes=totals.wire_bytes,
        encode_ms=totals.encode_ms,
        decode_ms=totals.decode_ms,
        backend="+".join(sorted(backends)) if backends else codec,
    )


def measure_fixture_codecs(
    corpus: Mapping[str, Any],
    *,
    codecs: Iterable[str],
    backend: str = "python",
    level: int = AI_WIRE_DEFAULT_LEVEL,
) -> list[dict[str, Any]]:
    """Measure hot-path fixture bytes for each codec."""

    use_native = _use_native(backend)
    codec_rows: list[dict[str, Any]] = []
    for codec in codecs:
        if codec not in SUPPORTED_CODECS:
            raise ValueError(f"unsupported codec {codec!r}; choices: {', '.join(SUPPORTED_CODECS)}")

        totals = {
            "exchanges": 0,
            "request_frames": 0,
            "response_frames": 0,
            "raw_request_bytes": 0,
            "raw_response_bytes": 0,
            "request_wire_bytes": 0,
            "response_wire_bytes": 0,
            "client_compress_ms": 0.0,
            "server_decompress_ms": 0.0,
            "server_compress_ms": 0.0,
            "client_decompress_ms": 0.0,
            "side_channel_framed_bytes": 0,
        }
        backends: set[str] = set()
        for session in corpus["sessions"]:
            initial_templates = _templates_from_entries(session["initial_session_templates"])
            updated_templates = _templates_from_entries(session["updated_session_templates"])
            request_events = [
                event for event in session["events"] if event["direction"] == "client_to_server"
            ]
            response_events = [
                event for event in session["events"] if event["direction"] == "server_to_client"
            ]
            requests = _measure_direction(
                codec,
                request_events,
                initial_templates=initial_templates,
                updated_templates=updated_templates,
                use_native=use_native,
                level=level,
            )
            responses = _measure_direction(
                codec,
                response_events,
                initial_templates=initial_templates,
                updated_templates=updated_templates,
                use_native=use_native,
                level=level,
            )
            if requests.frames != responses.frames:
                raise RuntimeError("fixture request/response frame counts differ")

            totals["exchanges"] += requests.frames
            totals["request_frames"] += requests.frames
            totals["response_frames"] += responses.frames
            totals["raw_request_bytes"] += requests.raw_bytes
            totals["raw_response_bytes"] += responses.raw_bytes
            totals["request_wire_bytes"] += requests.wire_bytes
            totals["response_wire_bytes"] += responses.wire_bytes
            totals["client_compress_ms"] += requests.encode_ms
            totals["server_decompress_ms"] += requests.decode_ms
            totals["server_compress_ms"] += responses.encode_ms
            totals["client_decompress_ms"] += responses.decode_ms
            if codec in AIWIRE_CODECS:
                totals["side_channel_framed_bytes"] += _session_side_channel_bytes(session)
            backends.add(requests.backend)
            backends.add(responses.backend)

        exchanges = max(1, int(totals["exchanges"]))
        framed_request = (
            int(totals["request_wire_bytes"]) + int(totals["request_frames"]) * U32_SIZE
        )
        framed_response = (
            int(totals["response_wire_bytes"]) + int(totals["response_frames"]) * U32_SIZE
        )
        raw_bytes = int(totals["raw_request_bytes"]) + int(totals["raw_response_bytes"])
        wire_bytes = int(totals["request_wire_bytes"]) + int(totals["response_wire_bytes"])
        framed_wire = framed_request + framed_response
        cpu_ms = (
            float(totals["client_compress_ms"])
            + float(totals["server_decompress_ms"])
            + float(totals["server_compress_ms"])
            + float(totals["client_decompress_ms"])
        )
        cpu_eps = exchanges / (cpu_ms / 1000.0) if cpu_ms > 0 else 0.0
        codec_rows.append(
            {
                "codec": codec,
                "backend": "+".join(sorted(backends)),
                "exchanges": exchanges,
                "request_frames": totals["request_frames"],
                "response_frames": totals["response_frames"],
                "raw_request_bytes": totals["raw_request_bytes"],
                "raw_response_bytes": totals["raw_response_bytes"],
                "raw_bytes": raw_bytes,
                "request_wire_bytes": totals["request_wire_bytes"],
                "response_wire_bytes": totals["response_wire_bytes"],
                "wire_bytes": wire_bytes,
                "framed_request_wire_bytes": framed_request,
                "framed_response_wire_bytes": framed_response,
                "framed_wire_bytes": framed_wire,
                "request_framed_bytes_per_exchange": framed_request / exchanges,
                "response_framed_bytes_per_exchange": framed_response / exchanges,
                "framed_bytes_per_exchange": framed_wire / exchanges,
                "raw_bytes_per_exchange": raw_bytes / exchanges,
                "side_channel_framed_bytes": totals["side_channel_framed_bytes"],
                "side_channel_bytes_per_exchange": totals["side_channel_framed_bytes"] / exchanges,
                "session_framed_bytes_per_exchange": (
                    framed_wire + int(totals["side_channel_framed_bytes"])
                )
                / exchanges,
                "ratio": raw_bytes / wire_bytes if wire_bytes else 0.0,
                "framed_ratio": raw_bytes / framed_wire if framed_wire else 0.0,
                "wire_saved_percent": (1 - wire_bytes / raw_bytes) * 100.0 if raw_bytes else 0.0,
                "framed_wire_saved_percent": (
                    (1 - framed_wire / raw_bytes) * 100.0 if raw_bytes else 0.0
                ),
                "client_compress_ms": totals["client_compress_ms"],
                "server_decompress_ms": totals["server_decompress_ms"],
                "server_compress_ms": totals["server_compress_ms"],
                "client_decompress_ms": totals["client_decompress_ms"],
                "codec_cpu_ms": cpu_ms,
                "codec_cpu_us_per_exchange": cpu_ms * 1000.0 / exchanges,
                "cpu_ceiling_exchanges_per_second": cpu_eps,
                "verified": True,
            }
        )
    return codec_rows


def _serialization_ms(byte_count: float, mbps: float) -> float:
    if byte_count <= 0 or mbps <= 0:
        return 0.0
    return byte_count * 8.0 / (mbps * 1000.0)


def _tail_p95_ms(probability: float, tail_pause_ms: float) -> float:
    probability = max(0.0, min(1.0, probability))
    if probability <= 0.0 or tail_pause_ms <= 0.0:
        return 0.0
    if 0.95 <= 1.0 - probability:
        return 0.0
    conditional_quantile = (0.95 - (1.0 - probability)) / probability
    return max(0.0, min(1.0, conditional_quantile)) * tail_pause_ms


def _profile_tail_p95_ms(profile: Any) -> float:
    return _tail_p95_ms(
        profile.client_tail_pause_probability,
        profile.client_tail_pause_ms,
    ) + _tail_p95_ms(
        profile.server_tail_pause_probability,
        profile.server_tail_pause_ms,
    )


def _profile_jitter_p95_ms(profile: Any) -> float:
    return 0.9 * (profile.client_jitter_ms + profile.server_jitter_ms)


def _profile_p95_ms(profile: Any, row: Mapping[str, Any]) -> float:
    return (
        profile.rtt_ms
        + _serialization_ms(row["request_framed_bytes_per_exchange"], profile.client_link_mbps)
        + _serialization_ms(row["response_framed_bytes_per_exchange"], profile.server_link_mbps)
        + _profile_jitter_p95_ms(profile)
        + _profile_tail_p95_ms(profile)
        + float(row["codec_cpu_us_per_exchange"]) / 1000.0
    )


def _capacity(row: Mapping[str, Any], profile: Any) -> tuple[float, float, float, str]:
    request_capacity = 0.0
    response_capacity = 0.0
    if profile.client_link_mbps > 0:
        request_capacity = (
            profile.client_link_mbps
            * 1_000_000.0
            / 8.0
            / float(row["request_framed_bytes_per_exchange"])
        )
    if profile.server_link_mbps > 0:
        response_capacity = (
            profile.server_link_mbps
            * 1_000_000.0
            / 8.0
            / float(row["response_framed_bytes_per_exchange"])
        )
    if request_capacity and response_capacity:
        if request_capacity <= response_capacity:
            return request_capacity, request_capacity, response_capacity, "request"
        return response_capacity, request_capacity, response_capacity, "response"
    capacity = (
        request_capacity or response_capacity or float(row["cpu_ceiling_exchanges_per_second"])
    )
    return (
        capacity,
        request_capacity,
        response_capacity,
        "cpu" if not request_capacity else "request",
    )


def saturation_rows(
    codec_measurements: list[dict[str, Any]],
    *,
    profiles: Iterable[Any],
    agent_counts: Iterable[int],
    per_agent_window: int,
) -> list[dict[str, Any]]:
    """Project fixture benchmark rows across profiles and agent counts."""

    profile_list = list(profiles)
    raw_by_profile: dict[str, dict[str, Any]] = {}
    rows_without_gains: list[dict[str, Any]] = []
    for profile in profile_list:
        for measured in codec_measurements:
            bandwidth_capacity, request_capacity, response_capacity, bottleneck = _capacity(
                measured, profile
            )
            projected_p95_ms = _profile_p95_ms(profile, measured)
            required_inflight_window = (
                math.ceil(bandwidth_capacity * projected_p95_ms / 1000.0)
                if bandwidth_capacity and projected_p95_ms
                else 0
            )
            for agent_count in agent_counts:
                agent_count = max(1, int(agent_count))
                aggregate_window = agent_count * max(1, per_agent_window)
                latency_capacity = (
                    aggregate_window / (projected_p95_ms / 1000.0)
                    if projected_p95_ms > 0
                    else bandwidth_capacity
                )
                cpu_capacity = float(measured["cpu_ceiling_exchanges_per_second"])
                candidates = [
                    ("bandwidth", bandwidth_capacity),
                    ("latency_window", latency_capacity),
                ]
                if cpu_capacity:
                    candidates.append(("cpu", cpu_capacity))
                limiting_factor, effective_capacity = min(candidates, key=lambda item: item[1])
                raw_bpe = float(measured["raw_bytes_per_exchange"])
                framed_bpe = float(measured["framed_bytes_per_exchange"])
                row = {
                    **measured,
                    "network_profile": profile.name,
                    "network_description": profile.description,
                    "profile_rtt_ms": profile.rtt_ms,
                    "profile_pipeline_window": profile.pipeline_window,
                    "client_link_mbps": profile.client_link_mbps,
                    "server_link_mbps": profile.server_link_mbps,
                    "client_one_way_delay_ms": profile.client_one_way_delay_ms,
                    "server_one_way_delay_ms": profile.server_one_way_delay_ms,
                    "client_jitter_ms": profile.client_jitter_ms,
                    "server_jitter_ms": profile.server_jitter_ms,
                    "client_tail_pause_probability": profile.client_tail_pause_probability,
                    "server_tail_pause_probability": profile.server_tail_pause_probability,
                    "client_tail_pause_ms": profile.client_tail_pause_ms,
                    "server_tail_pause_ms": profile.server_tail_pause_ms,
                    "agent_count": agent_count,
                    "per_agent_pipeline_window": max(1, per_agent_window),
                    "pipeline_window": aggregate_window,
                    "aggregate_pipeline_window": aggregate_window,
                    "required_inflight_window": required_inflight_window,
                    "required_agent_count": (
                        math.ceil(required_inflight_window / max(1, per_agent_window))
                        if required_inflight_window
                        else 0
                    ),
                    "roundtrip_ms_p95": projected_p95_ms,
                    "roundtrip_ms_avg": projected_p95_ms,
                    "roundtrip_ms_p50": projected_p95_ms,
                    "roundtrip_ms_p99": projected_p95_ms
                    + _profile_tail_p95_ms(profile)
                    + 0.1 * (profile.client_jitter_ms + profile.server_jitter_ms),
                    "projected_p95_ms": projected_p95_ms,
                    "profile_jitter_p95_ms": _profile_jitter_p95_ms(profile),
                    "profile_tail_p95_ms": _profile_tail_p95_ms(profile),
                    "projected_request_serialization_ms": _serialization_ms(
                        measured["request_framed_bytes_per_exchange"],
                        profile.client_link_mbps,
                    ),
                    "projected_response_serialization_ms": _serialization_ms(
                        measured["response_framed_bytes_per_exchange"],
                        profile.server_link_mbps,
                    ),
                    "request_capacity_exchanges_per_second": request_capacity,
                    "response_capacity_exchanges_per_second": response_capacity,
                    "bandwidth_capacity_exchanges_per_second": bandwidth_capacity,
                    "bandwidth_bottleneck_direction": bottleneck,
                    "latency_window_capacity_exchanges_per_second": latency_capacity,
                    "effective_capacity_exchanges_per_second": effective_capacity,
                    "effective_messages_per_second": effective_capacity * 2.0,
                    "effective_capacity_exchanges_per_minute": effective_capacity * 60.0,
                    "effective_capacity_exchanges_per_hour": effective_capacity * 3600.0,
                    "bandwidth_utilization_percent": (
                        min(effective_capacity, bandwidth_capacity) / bandwidth_capacity * 100.0
                        if bandwidth_capacity
                        else 0.0
                    ),
                    "bandwidth_fill_percent": (
                        min(effective_capacity, bandwidth_capacity) / bandwidth_capacity * 100.0
                        if bandwidth_capacity
                        else 0.0
                    ),
                    "limiting_factor": limiting_factor,
                    "semantic_mib_per_second": raw_bpe * bandwidth_capacity / 1024.0 / 1024.0,
                    "wire_mib_per_second": framed_bpe * bandwidth_capacity / 1024.0 / 1024.0,
                    "effective_semantic_mib_per_second": raw_bpe
                    * effective_capacity
                    / 1024.0
                    / 1024.0,
                    "effective_wire_mib_per_second": framed_bpe
                    * effective_capacity
                    / 1024.0
                    / 1024.0,
                    "wire_total_mbps": framed_bpe * bandwidth_capacity * 8.0 / 1_000_000.0,
                    "effective_wire_total_mbps": framed_bpe
                    * effective_capacity
                    * 8.0
                    / 1_000_000.0,
                    "duration_mode": False,
                    "target_seconds": 0,
                    "sent_exchanges": measured["exchanges"],
                    "deadline_completed_exchanges": measured["exchanges"],
                    "deadline_exchanges_per_second": effective_capacity,
                    "exchanges_per_second": effective_capacity,
                }
                rows_without_gains.append(row)
                if measured["codec"] == "raw":
                    raw_by_profile[f"{profile.name}:{agent_count}"] = row

    rows: list[dict[str, Any]] = []
    for row in rows_without_gains:
        raw = raw_by_profile.get(f"{row['network_profile']}:{row['agent_count']}")
        if raw:
            row["capacity_gain_vs_raw"] = (
                row["bandwidth_capacity_exchanges_per_second"]
                / raw["bandwidth_capacity_exchanges_per_second"]
                if raw["bandwidth_capacity_exchanges_per_second"]
                else 0.0
            )
            row["effective_gain_vs_raw"] = (
                row["effective_capacity_exchanges_per_second"]
                / raw["effective_capacity_exchanges_per_second"]
                if raw["effective_capacity_exchanges_per_second"]
                else 0.0
            )
            row["wire_saved_vs_raw_percent"] = (
                1
                - float(row["framed_bytes_per_exchange"]) / float(raw["framed_bytes_per_exchange"])
            ) * 100.0
            row["raw_required_total_mbps"] = (
                float(raw["framed_bytes_per_exchange"])
                * row["bandwidth_capacity_exchanges_per_second"]
                * 8.0
                / 1_000_000.0
            )
            row["effective_raw_required_total_mbps"] = (
                float(raw["framed_bytes_per_exchange"])
                * row["effective_capacity_exchanges_per_second"]
                * 8.0
                / 1_000_000.0
            )
        else:
            row["capacity_gain_vs_raw"] = 0.0
            row["effective_gain_vs_raw"] = 0.0
            row["wire_saved_vs_raw_percent"] = 0.0
            row["raw_required_total_mbps"] = 0.0
            row["effective_raw_required_total_mbps"] = 0.0
        rows.append(row)
    return rows


def build_fixture_saturation_report(
    *,
    fixture_path: Path = DEFAULT_FIXTURE_PATH,
    profiles: str = "lan_10m,wifi_busy,lte_good,edge_mesh",
    codecs: Iterable[str] = ("raw", "zlib", "aiwire", "aitoken_aiwire"),
    agent_counts: Iterable[int] = (1, 2, 4, 8, 16, 32),
    per_agent_window: int = 1,
    backend: str = "python",
    level: int = AI_WIRE_DEFAULT_LEVEL,
) -> dict[str, Any]:
    corpus = load_aiwire_session_fixture_corpus(fixture_path)
    resolved_profiles = resolve_network_profiles(profiles)
    measured = measure_fixture_codecs(
        corpus,
        codecs=codecs,
        backend=backend,
        level=level,
    )
    rows = saturation_rows(
        measured,
        profiles=resolved_profiles,
        agent_counts=agent_counts,
        per_agent_window=per_agent_window,
    )
    return {
        "suite": "aura-aiwire-fixture-saturation",
        "fixture_corpus": str(fixture_path),
        "fixture_schema": corpus.get("schema"),
        "session_count": corpus.get("session_count", DEFAULT_SESSION_COUNT),
        "exchanges_per_session": corpus.get(
            "exchanges_per_session",
            DEFAULT_EXCHANGES_PER_SESSION,
        ),
        "exchanges": sum(int(session["exchange_count"]) for session in corpus["sessions"]),
        "message_count": corpus.get("message_count"),
        "backend_mode": backend,
        "aiwire_level": level,
        "codecs": list(codecs),
        "agent_counts": list(agent_counts),
        "per_agent_window": per_agent_window,
        "profiles": profiles_as_dicts(resolved_profiles),
        "codec_measurements": measured,
        "results": rows,
    }


def _fmt(value: float, digits: int = 1) -> str:
    return f"{value:.{digits}f}"


def render_markdown(report: Mapping[str, Any]) -> str:
    rows = list(report["results"])
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["network_profile"])].append(row)

    lines = [
        "# AIWire Fixture Bandwidth Saturation",
        "",
        "This report uses the committed public AIWire session fixture corpus. It measures "
        "hot-path bytes for each codec, then projects how many concurrent logical "
        "agents are needed to fill realistic network profiles.",
        "",
        f"- Fixture: `{report['fixture_corpus']}`",
        f"- Exchanges: `{report['exchanges']}` request/response pairs",
        f"- Backend mode: `{report['backend_mode']}`",
        f"- Per-agent in-flight window: `{report['per_agent_window']}`",
        "",
        "The effective capacity is the minimum of bandwidth capacity, latency-window "
        "capacity, and measured local codec CPU ceiling.",
        "",
        "| Profile | Agents | Codec | B/ex | BW ex/s | Eff ex/s | Msg/s | Fill | "
        "Need agents | p95 ms | Limit | vs raw | Saved | Raw Mbps equiv |",
        "|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|",
    ]
    for profile in sorted(grouped):
        for row in sorted(grouped[profile], key=lambda item: (item["agent_count"], item["codec"])):
            lines.append(
                "| {profile} | {agents} | {codec} | {bpe} | {bw} | {eff} | {msg} | "
                "{fill}% | {need} | {p95} | {limit} | {gain}x | {saved}% | {raw_mbps} |".format(
                    profile=profile,
                    agents=row["agent_count"],
                    codec=row["codec"],
                    bpe=_fmt(float(row["framed_bytes_per_exchange"]), 1),
                    bw=_fmt(float(row["bandwidth_capacity_exchanges_per_second"]), 1),
                    eff=_fmt(float(row["effective_capacity_exchanges_per_second"]), 1),
                    msg=_fmt(float(row["effective_messages_per_second"]), 1),
                    fill=_fmt(float(row["bandwidth_fill_percent"]), 1),
                    need=row["required_agent_count"],
                    p95=_fmt(float(row["projected_p95_ms"]), 1),
                    limit=row["limiting_factor"],
                    gain=_fmt(float(row["effective_gain_vs_raw"]), 2),
                    saved=_fmt(float(row["wire_saved_vs_raw_percent"]), 1),
                    raw_mbps=_fmt(float(row["effective_raw_required_total_mbps"]), 2),
                )
            )
    lines.extend(
        [
            "",
            "Readout:",
            "",
            "- `B/ex` is framed hot-path bytes per request/response exchange.",
            "- `BW ex/s` is the pure bandwidth capacity for that profile.",
            "- `Eff ex/s` is capped by bandwidth, p95 latency window, and measured codec CPU.",
            "- `Need agents` is `ceil(BW ex/s * projected_p95_seconds / per_agent_window)`.",
            "- `Raw Mbps equiv` is the bandwidth raw JSON would need to carry the same "
            "effective semantic exchange rate.",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture-corpus", type=Path, default=DEFAULT_FIXTURE_PATH)
    parser.add_argument(
        "--profiles",
        default="lan_10m,wifi_busy,lte_good,edge_mesh",
        help="comma-separated profile names, 'default', or 'all'",
    )
    parser.add_argument("--codecs", default="raw,zlib,aiwire,aitoken_aiwire")
    parser.add_argument(
        "--agent-counts",
        default="1,2,4,8,16,32",
        help="comma-separated logical agent counts",
    )
    parser.add_argument("--per-agent-window", type=int, default=1)
    parser.add_argument("--backend", choices=("python", "native", "auto"), default="python")
    parser.add_argument("--aiwire-level", type=int, default=AI_WIRE_DEFAULT_LEVEL)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_fixture_saturation_report(
        fixture_path=args.fixture_corpus,
        profiles=args.profiles,
        codecs=_split_csv(args.codecs),
        agent_counts=_split_ints(args.agent_counts),
        per_agent_window=args.per_agent_window,
        backend=args.backend,
        level=args.aiwire_level,
    )
    json_payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    markdown = render_markdown(report)
    if args.output:
        args.output.write_text(json_payload, encoding="utf-8")
    if args.markdown_output:
        args.markdown_output.write_text(markdown + "\n", encoding="utf-8")
    print(markdown if args.format == "markdown" else json_payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
