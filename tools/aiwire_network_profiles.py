#!/usr/bin/env python3
"""Realistic network profiles for AURA AIWire stress benchmarks."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable


@dataclass(frozen=True)
class AIWireNetworkProfile:
    """One bidirectional network impairment profile.

    Client fields model client-to-server egress.  Server fields model
    server-to-client egress.  Tail pauses approximate queue spikes or TCP
    retransmit recovery without dropping application frames.
    """

    name: str
    description: str
    client_link_mbps: float
    server_link_mbps: float
    client_one_way_delay_ms: float
    server_one_way_delay_ms: float
    client_jitter_ms: float
    server_jitter_ms: float
    client_tail_pause_probability: float
    server_tail_pause_probability: float
    client_tail_pause_ms: float
    server_tail_pause_ms: float
    pipeline_window: int

    @property
    def rtt_ms(self) -> float:
        return self.client_one_way_delay_ms + self.server_one_way_delay_ms

    def as_dict(self) -> dict[str, object]:
        return asdict(self) | {"rtt_ms": self.rtt_ms}


NETWORK_PROFILES: tuple[AIWireNetworkProfile, ...] = (
    AIWireNetworkProfile(
        name="loopback_cpu",
        description="Local CPU ceiling with no modeled bandwidth bottleneck.",
        client_link_mbps=0.0,
        server_link_mbps=0.0,
        client_one_way_delay_ms=0.0,
        server_one_way_delay_ms=0.0,
        client_jitter_ms=0.0,
        server_jitter_ms=0.0,
        client_tail_pause_probability=0.0,
        server_tail_pause_probability=0.0,
        client_tail_pause_ms=0.0,
        server_tail_pause_ms=0.0,
        pipeline_window=64,
    ),
    AIWireNetworkProfile(
        name="lan_1g",
        description="Clean wired LAN, roughly gigabit-class effective throughput.",
        client_link_mbps=940.0,
        server_link_mbps=940.0,
        client_one_way_delay_ms=0.25,
        server_one_way_delay_ms=0.25,
        client_jitter_ms=0.05,
        server_jitter_ms=0.05,
        client_tail_pause_probability=0.001,
        server_tail_pause_probability=0.001,
        client_tail_pause_ms=1.0,
        server_tail_pause_ms=1.0,
        pipeline_window=128,
    ),
    AIWireNetworkProfile(
        name="lan_10m",
        description="Constrained local lab link used for bandwidth-proportional tests.",
        client_link_mbps=10.0,
        server_link_mbps=10.0,
        client_one_way_delay_ms=2.0,
        server_one_way_delay_ms=2.0,
        client_jitter_ms=1.0,
        server_jitter_ms=1.0,
        client_tail_pause_probability=0.002,
        server_tail_pause_probability=0.002,
        client_tail_pause_ms=8.0,
        server_tail_pause_ms=8.0,
        pipeline_window=16,
    ),
    AIWireNetworkProfile(
        name="wifi_good",
        description="Good Wi-Fi with moderate jitter and asymmetric real throughput.",
        client_link_mbps=80.0,
        server_link_mbps=160.0,
        client_one_way_delay_ms=4.0,
        server_one_way_delay_ms=4.0,
        client_jitter_ms=2.0,
        server_jitter_ms=2.0,
        client_tail_pause_probability=0.01,
        server_tail_pause_probability=0.01,
        client_tail_pause_ms=25.0,
        server_tail_pause_ms=25.0,
        pipeline_window=64,
    ),
    AIWireNetworkProfile(
        name="wifi_busy",
        description="Congested Wi-Fi with queue spikes and asymmetric airtime.",
        client_link_mbps=12.0,
        server_link_mbps=45.0,
        client_one_way_delay_ms=9.0,
        server_one_way_delay_ms=9.0,
        client_jitter_ms=7.0,
        server_jitter_ms=7.0,
        client_tail_pause_probability=0.03,
        server_tail_pause_probability=0.03,
        client_tail_pause_ms=80.0,
        server_tail_pause_ms=80.0,
        pipeline_window=64,
    ),
    AIWireNetworkProfile(
        name="wan_regional",
        description="Regional cloud or office WAN path.",
        client_link_mbps=50.0,
        server_link_mbps=100.0,
        client_one_way_delay_ms=18.0,
        server_one_way_delay_ms=18.0,
        client_jitter_ms=4.0,
        server_jitter_ms=4.0,
        client_tail_pause_probability=0.005,
        server_tail_pause_probability=0.005,
        client_tail_pause_ms=50.0,
        server_tail_pause_ms=50.0,
        pipeline_window=96,
    ),
    AIWireNetworkProfile(
        name="lte_good",
        description="Healthy LTE/5G-style mobile uplink with stronger downlink.",
        client_link_mbps=10.0,
        server_link_mbps=50.0,
        client_one_way_delay_ms=28.0,
        server_one_way_delay_ms=28.0,
        client_jitter_ms=12.0,
        server_jitter_ms=12.0,
        client_tail_pause_probability=0.02,
        server_tail_pause_probability=0.015,
        client_tail_pause_ms=120.0,
        server_tail_pause_ms=100.0,
        pipeline_window=96,
    ),
    AIWireNetworkProfile(
        name="lte_poor",
        description="Weak cellular path with low uplink and frequent queue stalls.",
        client_link_mbps=1.5,
        server_link_mbps=8.0,
        client_one_way_delay_ms=65.0,
        server_one_way_delay_ms=65.0,
        client_jitter_ms=35.0,
        server_jitter_ms=35.0,
        client_tail_pause_probability=0.06,
        server_tail_pause_probability=0.04,
        client_tail_pause_ms=350.0,
        server_tail_pause_ms=300.0,
        pipeline_window=128,
    ),
    AIWireNetworkProfile(
        name="satellite",
        description="High-latency satellite-style path with constrained uplink.",
        client_link_mbps=5.0,
        server_link_mbps=25.0,
        client_one_way_delay_ms=310.0,
        server_one_way_delay_ms=310.0,
        client_jitter_ms=55.0,
        server_jitter_ms=55.0,
        client_tail_pause_probability=0.025,
        server_tail_pause_probability=0.02,
        client_tail_pause_ms=600.0,
        server_tail_pause_ms=500.0,
        pipeline_window=192,
    ),
    AIWireNetworkProfile(
        name="edge_mesh",
        description="Small edge mesh or Nano-class LAN segment under contention.",
        client_link_mbps=6.0,
        server_link_mbps=6.0,
        client_one_way_delay_ms=12.0,
        server_one_way_delay_ms=12.0,
        client_jitter_ms=8.0,
        server_jitter_ms=8.0,
        client_tail_pause_probability=0.025,
        server_tail_pause_probability=0.025,
        client_tail_pause_ms=120.0,
        server_tail_pause_ms=120.0,
        pipeline_window=48,
    ),
)

_PROFILE_BY_NAME = {profile.name: profile for profile in NETWORK_PROFILES}


def network_profile_names() -> tuple[str, ...]:
    return tuple(_PROFILE_BY_NAME)


def get_network_profile(name: str) -> AIWireNetworkProfile:
    try:
        return _PROFILE_BY_NAME[name]
    except KeyError as exc:
        choices = ", ".join(network_profile_names())
        raise KeyError(f"unknown AIWire network profile {name!r}; choices: {choices}") from exc


def resolve_network_profiles(names: str | Iterable[str]) -> tuple[AIWireNetworkProfile, ...]:
    if isinstance(names, str):
        requested = [name.strip() for name in names.split(",") if name.strip()]
    else:
        requested = [str(name).strip() for name in names if str(name).strip()]
    if not requested or requested == ["default"]:
        requested = ["lan_10m", "wifi_busy", "lte_good", "edge_mesh"]
    if requested == ["all"]:
        return NETWORK_PROFILES
    return tuple(get_network_profile(name) for name in requested)


def profiles_as_dicts(profiles: Iterable[AIWireNetworkProfile]) -> list[dict[str, object]]:
    return [profile.as_dict() for profile in profiles]
