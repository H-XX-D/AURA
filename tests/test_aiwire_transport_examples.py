from __future__ import annotations

import importlib.util

import pytest

from examples.aiwire_transport_common import (
    CONTROL_LANE,
    TransportCarrierFrame,
    decode_demo_control_frame,
    encode_route_status_control,
    route_status_payload,
)
from examples import (
    aiwire_http_streaming_transport,
    aiwire_local_broker,
    aiwire_tcp_transport,
    aiwire_websocket_transport,
)


def _assert_demo_result(result, transport: str, count: int) -> None:
    assert result.transport == transport
    assert result.messages_sent == count
    assert result.messages_received == count
    assert result.replies_received == count
    assert result.control_frames_sent == count * 2
    assert result.control_frames_received == count * 2
    assert result.raw_bytes > 0
    assert result.wire_bytes > 0


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
