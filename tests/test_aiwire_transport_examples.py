from __future__ import annotations

import importlib.util
import json
from collections.abc import Iterable

import pytest

from aura_compression import AIWireHandshakeError, build_aiwire_compatibility_manifest
from examples import (
    aiwire_http_streaming_transport,
    aiwire_local_broker,
    aiwire_tcp_transport,
    aiwire_websocket_transport,
)
from examples.aiwire_transport_common import (
    CONTROL_LANE,
    TransportCarrierFrame,
    b64,
    decode_demo_control_frame,
    encode_route_status_control,
    encode_transport_compatibility_control,
    route_status_payload,
    unb64,
    verify_transport_compatibility_control,
)


def _assert_demo_result(result, transport: str, count: int) -> None:
    assert result.transport == transport
    assert result.messages_sent == count
    assert result.messages_received == count
    assert result.replies_received == count
    assert result.control_frames_sent == count * 2 + 2
    assert result.control_frames_received == count * 2 + 2
    assert result.compatibility_checks == 2
    assert result.compatibility_codec == "aiwire"
    assert result.raw_bytes > 0
    assert result.wire_bytes > 0


class _FragmentedSocket:
    def __init__(self, chunks: Iterable[bytes]) -> None:
        self._chunks = list(chunks)

    def recv(self, size: int) -> bytes:
        if not self._chunks:
            return b""
        chunk = self._chunks.pop(0)
        if len(chunk) > size:
            self._chunks.insert(0, chunk[size:])
            return chunk[:size]
        return chunk


def test_transport_carrier_frame_round_trips_control_lane() -> None:
    payload = route_status_payload(
        transport="unit",
        sequence=7,
        direction="client_to_server",
        status="ready",
        trace_id="trace-7",
    )
    control_frame = encode_route_status_control(payload)
    carrier = TransportCarrierFrame(CONTROL_LANE, control_frame)
    restored = TransportCarrierFrame.from_bytes(carrier.to_bytes())
    decoded = decode_demo_control_frame(restored.payload)

    assert restored.lane == CONTROL_LANE
    assert decoded["meaning"] == "route_status"
    assert decoded["payload"] == payload


def test_transport_compatibility_preflight_rejects_catalog_version_mismatch() -> None:
    session_templates = {128: "agent {0} calls tool {1}"}
    peer_manifest = build_aiwire_compatibility_manifest(
        fallback_codecs=(),
        session_templates=session_templates,
        session_template_catalog_version="tenant-alpha-templates-v1",
    )
    local_manifest = build_aiwire_compatibility_manifest(
        fallback_codecs=(),
        session_templates=session_templates,
        session_template_catalog_version="tenant-beta-templates-v1",
    )
    frame = encode_transport_compatibility_control("client", manifest=peer_manifest)

    with pytest.raises(ValueError, match="session_template_catalog_version_mismatch"):
        verify_transport_compatibility_control(
            frame,
            expected_role="client",
            local_manifest=local_manifest,
        )


def test_transport_compatibility_preflight_rejects_empty_manifest_overrides() -> None:
    with pytest.raises(
        AIWireHandshakeError,
        match="unsupported AIWire compatibility manifest schema",
    ):
        encode_transport_compatibility_control("client", manifest={})

    frame = encode_transport_compatibility_control("client")
    with pytest.raises(
        ValueError,
        match="unsupported AIWire compatibility manifest schema",
    ):
        verify_transport_compatibility_control(
            frame,
            expected_role="client",
            local_manifest={},
        )


def test_transport_compatibility_preflight_accepts_matching_mapping_overrides() -> None:
    manifest = build_aiwire_compatibility_manifest(
        fallback_codecs=(),
        session_templates={128: "agent {0} calls tool {1}"},
        session_template_catalog_version="tenant-alpha-templates-v1",
    ).to_dict()
    frame = encode_transport_compatibility_control("client", manifest=manifest)

    check = verify_transport_compatibility_control(
        frame,
        expected_role="client",
        local_manifest=manifest,
    )

    assert check["accepted"] is True
    assert check["codec"] == "aiwire"


def test_transport_compatibility_preflight_rejects_tampered_manifest() -> None:
    frame = encode_transport_compatibility_control("client")
    payload = json.loads(frame)
    payload["manifest"]["session_template_catalog_version"] = "tampered-catalog"
    tampered_frame = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")

    with pytest.raises(ValueError, match="transport compatibility manifest hash mismatch"):
        verify_transport_compatibility_control(
            tampered_frame,
            expected_role="client",
        )


@pytest.mark.parametrize(
    ("frame", "error"),
    [
        (b"not-json", "transport compatibility control must be JSON"),
        (b"[]", "transport compatibility control must be an object"),
        (
            b'{"schema":"aura.aiwire.transport.compatibility.unsupported"}',
            "unsupported transport compatibility control schema",
        ),
        (
            b'{"role":"client","schema":"aura.aiwire.transport_compatibility.v1"}',
            "transport compatibility control is missing manifest",
        ),
    ],
)
def test_transport_compatibility_preflight_rejects_invalid_envelopes(
    frame: bytes,
    error: str,
) -> None:
    with pytest.raises(ValueError, match=error):
        verify_transport_compatibility_control(
            frame,
            expected_role="client",
        )


def test_transport_compatibility_preflight_rejects_unexpected_role() -> None:
    frame = encode_transport_compatibility_control("server")

    with pytest.raises(ValueError, match="expected compatibility role 'client', got 'server'"):
        verify_transport_compatibility_control(
            frame,
            expected_role="client",
        )


@pytest.mark.parametrize("encoded", ["YWJj$", "\N{SNOWMAN}"])
def test_transport_base64_rejects_invalid_payload(encoded: str) -> None:
    with pytest.raises(ValueError, match="transport payload must be valid base64"):
        unb64(encoded)


def test_transport_base64_round_trips_binary_payload() -> None:
    payload = b"\x00aiwire\xff\x10"

    assert unb64(b64(payload)) == payload


def test_tcp_transport_frame_reader_handles_fragmented_reads() -> None:
    payload = route_status_payload(
        transport="tcp",
        sequence=3,
        direction="client_to_server",
        status="ready",
        trace_id="trace-fragmented",
    )
    carrier = TransportCarrierFrame(CONTROL_LANE, encode_route_status_control(payload))
    encoded = carrier.to_bytes()
    frame = aiwire_tcp_transport.U32.pack(len(encoded)) + encoded
    fragmented = _FragmentedSocket(
        [
            frame[:1],
            frame[1:3],
            frame[3:4],
            frame[4:6],
            frame[6:9],
            frame[9:],
        ]
    )

    restored = aiwire_tcp_transport._read_frame(fragmented)  # type: ignore[arg-type]
    decoded = decode_demo_control_frame(restored.payload)

    assert restored.lane == CONTROL_LANE
    assert decoded["payload"] == payload


def test_tcp_transport_frame_reader_rejects_interrupted_partial_frame() -> None:
    payload = route_status_payload(
        transport="tcp",
        sequence=4,
        direction="client_to_server",
        status="ready",
        trace_id="trace-interrupted",
    )
    carrier = TransportCarrierFrame(CONTROL_LANE, encode_route_status_control(payload))
    encoded = carrier.to_bytes()
    frame = aiwire_tcp_transport.U32.pack(len(encoded)) + encoded
    fragmented = _FragmentedSocket([frame[:2], frame[2:5], frame[5:8]])

    with pytest.raises(EOFError, match="socket closed"):
        aiwire_tcp_transport._read_frame(fragmented)  # type: ignore[arg-type]


def test_tcp_transport_example_round_trips_aiwire_frames() -> None:
    _assert_demo_result(aiwire_tcp_transport.run_demo(count=4), "tcp", 4)


def test_http_streaming_transport_example_round_trips_aiwire_frames() -> None:
    _assert_demo_result(aiwire_http_streaming_transport.run_demo(count=4), "http-sse", 4)


def test_local_broker_example_round_trips_aiwire_frames() -> None:
    _assert_demo_result(aiwire_local_broker.run_demo(count=4), "local-broker", 4)


def test_websocket_transport_example_is_import_safe() -> None:
    if importlib.util.find_spec("websockets") is None:
        with pytest.raises(RuntimeError, match="websocket extra"):
            aiwire_websocket_transport.run_demo(count=1)
    else:
        _assert_demo_result(aiwire_websocket_transport.run_demo(count=2), "websocket", 2)
