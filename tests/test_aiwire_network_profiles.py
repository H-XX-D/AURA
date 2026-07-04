from __future__ import annotations

import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from aiwire_network_profiles import (  # noqa: E402
    NETWORK_PROFILES,
    get_network_profile,
    network_profile_names,
    profiles_as_dicts,
    resolve_network_profiles,
)


def test_network_profiles_are_named_and_bounded() -> None:
    names = network_profile_names()

    assert "lan_10m" in names
    assert "wifi_busy" in names
    assert "lte_poor" in names
    assert len(names) == len(set(names))

    for profile in NETWORK_PROFILES:
        assert profile.name
        assert profile.description
        assert profile.client_link_mbps >= 0
        assert profile.server_link_mbps >= 0
        assert profile.rtt_ms >= 0
        assert 0 <= profile.client_tail_pause_probability <= 1
        assert 0 <= profile.server_tail_pause_probability <= 1
        assert profile.pipeline_window >= 1


def test_resolve_network_profiles_supports_default_all_and_explicit_names() -> None:
    assert [profile.name for profile in resolve_network_profiles("default")] == [
        "lan_10m",
        "wifi_busy",
        "lte_good",
        "edge_mesh",
    ]
    assert len(resolve_network_profiles("all")) == len(NETWORK_PROFILES)
    assert [profile.name for profile in resolve_network_profiles("lan_10m,lte_poor")] == [
        "lan_10m",
        "lte_poor",
    ]


def test_profile_dicts_include_rtt() -> None:
    profile = get_network_profile("lte_good")
    [payload] = profiles_as_dicts([profile])

    assert payload["name"] == "lte_good"
    assert payload["rtt_ms"] == profile.rtt_ms
