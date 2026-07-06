from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import run_aiwire_network_suite as network_suite  # noqa: E402
from aiwire_network_profiles import (  # noqa: E402
    NETWORK_PROFILES,
    get_network_profile,
    network_profile_names,
    profiles_as_dicts,
    resolve_network_profiles,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "fixtures" / "aiwire_sessions" / "public_session_corpus_v1.json"


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


def test_network_suite_parses_backend_and_coordinator() -> None:
    args = network_suite.parse_args([])

    assert args.backend == "python"
    assert args.coordinator == "threaded"

    native_args = network_suite.parse_args(["--backend", "native", "--coordinator", "asyncio"])

    assert native_args.backend == "native"
    assert native_args.coordinator == "asyncio"


def test_network_suite_passes_backend_coordinator_and_fixture_variation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, list[str]] = {}

    class DummyServer:
        returncode = 0

        def communicate(self, timeout: float | None = None) -> tuple[str, str]:
            return "{}", ""

        def terminate(self) -> None:  # pragma: no cover - only used on failures.
            return None

        def wait(self, timeout: float | None = None) -> int:  # pragma: no cover.
            return 0

        def kill(self) -> None:  # pragma: no cover - only used on failures.
            return None

    def fake_popen(
        cmd: list[str],
        *,
        cwd: Path,
        stdout: object,
        stderr: object,
        text: bool,
    ) -> DummyServer:
        captured["server"] = cmd
        return DummyServer()

    def fake_run(
        cmd: list[str],
        *,
        cwd: Path,
        check: bool,
        capture_output: bool,
        text: bool,
        timeout: float,
    ) -> SimpleNamespace:
        captured["client"] = cmd
        return SimpleNamespace(
            stdout=json.dumps(
                {
                    "results": [
                        {
                            "codec": "aiwire",
                            "pipeline_window": 2,
                            "per_agent_pipeline_window": 2,
                        }
                    ]
                }
            )
        )

    monkeypatch.setattr(network_suite.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(network_suite.subprocess, "run", fake_run)
    monkeypatch.setattr(network_suite.time, "sleep", lambda _: None)

    args = network_suite.parse_args(
        [
            "--profiles",
            "lan_10m",
            "--backend",
            "native",
            "--coordinator",
            "asyncio",
            "--fixture-corpus",
            str(FIXTURE_PATH),
            "--fixture-session-templates",
            "updated",
            "--fixture-variation-profile",
            "cluster",
            "--force-session-templates",
        ]
    )
    rows = network_suite._run_profile(get_network_profile("lan_10m"), args, 9910)

    assert captured["server"][captured["server"].index("--backend") + 1] == "native"
    assert captured["client"][captured["client"].index("--backend") + 1] == "native"
    assert captured["client"][captured["client"].index("--coordinator") + 1] == "asyncio"
    assert (
        captured["client"][captured["client"].index("--fixture-variation-profile") + 1] == "cluster"
    )
    assert captured["client"][captured["client"].index("--fixture-peer-label") + 1] == "lan_10m"
    assert rows[0]["network_profile"] == "lan_10m"
