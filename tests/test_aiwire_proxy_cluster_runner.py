from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import run_aiwire_proxy_cluster as proxy_cluster  # noqa: E402


def test_proxy_cluster_target_parser_supports_public_labels() -> None:
    target = proxy_cluster.parse_target(
        (
            "edge-1=edge-host.local,proxy_host=10.0.0.10,egress_port=9510,"
            "upstream_port=9610,remote_root=/srv/aura,ssh_public_key=/keys/edge-1.pub"
        ),
        index=2,
        default_egress_port=9200,
        default_upstream_port=9300,
    )

    assert target.label == "edge-1"
    assert target.ssh_host == "edge-host.local"
    assert target.proxy_host == "10.0.0.10"
    assert target.egress_port == 9510
    assert target.upstream_port == 9610
    assert target.remote_root == "/srv/aura"
    assert target.ssh_public_key == "/keys/edge-1.pub"


def test_proxy_cluster_dry_run_outputs_plan_and_summary(tmp_path: Path, capsys) -> None:
    output = tmp_path / "plan.json"
    summary = tmp_path / "plan.md"

    assert (
        proxy_cluster.main(
            [
                "--target",
                "edge-1=edge-host.local",
                "--seconds",
                "60",
                "--backend",
                "python",
                "--tunnel-codec",
                "zlib",
                "--connections",
                "3",
                "--tunnel-bandwidth-mbps",
                "8",
                "--tunnel-one-way-delay-ms",
                "18",
                "--tunnel-jitter-ms",
                "6",
                "--tunnel-tail-pause-probability",
                "0.02",
                "--tunnel-tail-pause-ms",
                "80",
                "--impairment-seed",
                "99",
                "--run-id",
                "test-run",
                "--output-dir",
                str(tmp_path / "artifacts"),
                "--output",
                str(output),
                "--summary-output",
                str(summary),
            ]
        )
        == 0
    )

    rendered = json.loads(capsys.readouterr().out)
    written = json.loads(output.read_text())

    assert rendered["schema"] == proxy_cluster.PROXY_CLUSTER_SCHEMA
    assert rendered == written
    assert rendered["dry_run"] is True
    assert rendered["connections"] == 3
    assert rendered["tunnel_codec"] == "zlib"
    assert rendered["tunnel_impairment"] == {
        "bandwidth_mbps": 8.0,
        "one_way_delay_ms": 18.0,
        "jitter_ms": 6.0,
        "tail_pause_probability": 0.02,
        "tail_pause_ms": 80.0,
        "seed": 99,
    }
    assert rendered["fixture_variation_profile"] == "cluster"
    assert rendered["targets"][0]["target"]["label"] == "edge-1"
    start_fixture = rendered["targets"][0]["commands"]["start_fixture"]
    assert "aura_compression.cli.proxy_fixture_server" in start_fixture
    assert "--connections 3" in start_fixture
    assert "cd $HOME/AURA" in start_fixture
    assert "&& (nohup sh -lc" in start_fixture
    assert "& echo $! >" in start_fixture
    start_egress = rendered["targets"][0]["commands"]["start_egress"]
    assert "aura_compression.cli.proxy" in start_egress
    assert "--connections 3" in start_egress
    assert "--tunnel-codec zlib" in start_egress
    assert "--tunnel-bandwidth-mbps 8.0" in start_egress
    assert "--tunnel-one-way-delay-ms 18.0" in start_egress
    summary_text = summary.read_text()
    assert "Connections per target: `3`" in summary_text
    assert "Tunnel codec: `zlib`" in summary_text
    assert "Tunnel impairment:" in summary_text
    assert "Run again with `--run`" in summary_text


def test_proxy_cluster_dry_run_supports_inline_upstream_fixture(
    tmp_path: Path,
    capsys,
) -> None:
    output = tmp_path / "plan.json"
    summary = tmp_path / "plan.md"

    assert (
        proxy_cluster.main(
            [
                "--target",
                "edge-1=edge-host.local",
                "--inline-upstream-fixture",
                "--seconds",
                "60",
                "--backend",
                "python",
                "--connections",
                "3",
                "--run-id",
                "test-run",
                "--output-dir",
                str(tmp_path / "artifacts"),
                "--output",
                str(output),
                "--summary-output",
                str(summary),
            ]
        )
        == 0
    )

    rendered = json.loads(capsys.readouterr().out)
    commands = rendered["targets"][0]["commands"]
    start_egress = commands["start_egress"]
    summary_text = summary.read_text()

    assert rendered["inline_upstream_fixture"] is True
    assert "start_fixture" not in commands
    assert "fetch_fixture_metrics" not in commands
    assert rendered["targets"][0]["artifacts"]["remote_fixture_metrics"] is None
    assert "--inline-fixture-corpus" in start_egress
    assert "--inline-fixture-variation-profile cluster" in start_egress
    assert "--inline-fixture-peer-label edge-1" in start_egress
    assert "--upstream-host" not in start_egress
    assert "--upstream-port" not in start_egress
    assert "Inline upstream fixture: `True`" in summary_text
    assert "| edge-1 | `edge-host.local` | `edge-host.local` | 9200 | inline |" in summary_text


def test_proxy_cluster_connection_sweep_dry_run_outputs_plans(
    tmp_path: Path,
    capsys,
) -> None:
    output = tmp_path / "sweep.json"
    summary = tmp_path / "sweep.md"

    assert (
        proxy_cluster.main(
            [
                "--target",
                "edge-1=edge-host.local",
                "--connections-sweep",
                "2,4",
                "--seconds",
                "60",
                "--backend",
                "python",
                "--run-id",
                "sweep-test",
                "--output-dir",
                str(tmp_path / "artifacts"),
                "--output",
                str(output),
                "--summary-output",
                str(summary),
            ]
        )
        == 0
    )

    rendered = json.loads(capsys.readouterr().out)
    written = json.loads(output.read_text())
    summary_text = summary.read_text()

    assert rendered == written
    assert rendered["schema"] == proxy_cluster.PROXY_CLUSTER_CONNECTION_SWEEP_SCHEMA
    assert rendered["connections_sweep"] == [2, 4]
    assert [run["connections_per_target"] for run in rendered["runs"]] == [2, 4]
    assert rendered["runs"][0]["report"]["run_id"] == "sweep-test-2x"
    assert rendered["runs"][1]["report"]["run_id"] == "sweep-test-4x"
    first_output_dir = Path(rendered["runs"][0]["report"]["output_dir"])
    second_output_dir = Path(rendered["runs"][1]["report"]["output_dir"])
    assert first_output_dir.parts[-2:] == ("artifacts", "2x")
    assert second_output_dir.parts[-2:] == ("artifacts", "4x")
    assert "| 2 | 2 | `sweep-test-2x` | planned |" in summary_text
    assert "| 4 | 4 | `sweep-test-4x` | planned |" in summary_text


def test_connection_sweep_markdown_renders_aggregate_rows() -> None:
    report = {
        "run_id": "sweep-test",
        "fixture_variation_profile": "cluster",
        "backend": "native",
        "seconds": 60.0,
        "connections_sweep": [2, 4],
        "aggregate": [
            {
                "connections_per_target": 2,
                "total_sessions": 6,
                "verified_targets": 3,
                "targets": 3,
                "exchanges": 8150,
                "exchanges_per_second_group": 135.8,
                "relative_to_baseline": 1.0,
                "raw_framed_bytes_per_exchange": 2348.0,
                "tunnel_semantic_framed_bytes_per_exchange": 366.7,
                "tunnel_saved_percent": 84.4,
                "bandwidth_capacity_gain": 6.4,
                "roundtrip_ms_p95_max": 47.92,
            },
            {
                "connections_per_target": 4,
                "total_sessions": 12,
                "verified_targets": 3,
                "targets": 3,
                "exchanges": 16283,
                "exchanges_per_second_group": 271.2,
                "relative_to_baseline": 1.997,
                "raw_framed_bytes_per_exchange": 2348.1,
                "tunnel_semantic_framed_bytes_per_exchange": 366.7,
                "tunnel_saved_percent": 84.4,
                "bandwidth_capacity_gain": 6.4,
                "roundtrip_ms_p95_max": 47.92,
            },
        ],
    }

    rendered = proxy_cluster.render_connection_sweep_markdown(report)

    assert "| 2 | 6 | 3/3 | 8,150 | 135.8 | 1.00x |" in rendered
    assert "| 4 | 12 | 3/3 | 16,283 | 271.2 | 2.00x |" in rendered


def test_proxy_cluster_codec_sweep_dry_run_outputs_plans(
    tmp_path: Path,
    capsys,
) -> None:
    output = tmp_path / "codec-sweep.json"
    summary = tmp_path / "codec-sweep.md"

    assert (
        proxy_cluster.main(
            [
                "--target",
                "edge-1=edge-host.local",
                "--tunnel-codec-sweep",
                "raw,zlib,aiwire",
                "--connections",
                "4",
                "--seconds",
                "60",
                "--backend",
                "python",
                "--run-id",
                "codec-sweep-test",
                "--output-dir",
                str(tmp_path / "artifacts"),
                "--output",
                str(output),
                "--summary-output",
                str(summary),
            ]
        )
        == 0
    )

    rendered = json.loads(capsys.readouterr().out)
    written = json.loads(output.read_text())
    summary_text = summary.read_text()

    assert rendered == written
    assert rendered["schema"] == proxy_cluster.PROXY_CLUSTER_CODEC_SWEEP_SCHEMA
    assert rendered["tunnel_codec_sweep"] == ["raw", "zlib", "aiwire"]
    assert [run["tunnel_codec"] for run in rendered["runs"]] == ["raw", "zlib", "aiwire"]
    assert rendered["runs"][0]["report"]["run_id"] == "codec-sweep-test-raw"
    assert rendered["runs"][1]["report"]["run_id"] == "codec-sweep-test-zlib"
    assert rendered["runs"][2]["report"]["run_id"] == "codec-sweep-test-aiwire"
    assert rendered["runs"][0]["report"]["tunnel_codec"] == "raw"
    assert rendered["runs"][1]["report"]["tunnel_codec"] == "zlib"
    assert rendered["runs"][2]["report"]["tunnel_codec"] == "aiwire"
    assert "| `raw` | 4 | `codec-sweep-test-raw` | planned |" in summary_text
    assert "| `zlib` | 4 | `codec-sweep-test-zlib` | planned |" in summary_text
    assert "| `aiwire` | 4 | `codec-sweep-test-aiwire` | planned |" in summary_text


def test_codec_sweep_markdown_renders_aggregate_rows() -> None:
    report = {
        "run_id": "codec-sweep-test",
        "fixture_variation_profile": "cluster",
        "backend": "native",
        "seconds": 60.0,
        "connections": 64,
        "tunnel_codec_sweep": ["raw", "zlib", "aiwire"],
        "aggregate": [
            {
                "tunnel_codec": "raw",
                "total_sessions": 192,
                "verified_targets": 3,
                "targets": 3,
                "exchanges": 48000,
                "exchanges_per_second_group": 800.0,
                "relative_to_raw": 1.0,
                "raw_framed_bytes_per_exchange": 2348.0,
                "tunnel_semantic_framed_bytes_per_exchange": 2350.0,
                "tunnel_saved_percent": -0.1,
                "bandwidth_capacity_gain": 1.0,
                "roundtrip_ms_p95_max": 95.0,
            },
            {
                "tunnel_codec": "zlib",
                "total_sessions": 192,
                "verified_targets": 3,
                "targets": 3,
                "exchanges": 96000,
                "exchanges_per_second_group": 1600.0,
                "relative_to_raw": 2.0,
                "raw_framed_bytes_per_exchange": 2348.0,
                "tunnel_semantic_framed_bytes_per_exchange": 760.0,
                "tunnel_saved_percent": 67.6,
                "bandwidth_capacity_gain": 3.09,
                "roundtrip_ms_p95_max": 88.0,
            },
            {
                "tunnel_codec": "aiwire",
                "total_sessions": 192,
                "verified_targets": 3,
                "targets": 3,
                "exchanges": 164000,
                "exchanges_per_second_group": 2730.0,
                "relative_to_raw": 3.41,
                "raw_framed_bytes_per_exchange": 2348.0,
                "tunnel_semantic_framed_bytes_per_exchange": 367.0,
                "tunnel_saved_percent": 84.4,
                "bandwidth_capacity_gain": 6.40,
                "roundtrip_ms_p95_max": 86.1,
                "stage_profile": [
                    {
                        "role": "ingress",
                        "stage": "tunnel_response_read",
                        "calls": 164000,
                        "total_seconds": 42.5,
                        "mean_ms": 0.259,
                    },
                    {
                        "role": "egress",
                        "stage": "response_encode",
                        "calls": 164000,
                        "total_seconds": 3.2,
                        "mean_ms": 0.020,
                    },
                ],
            },
        ],
    }

    rendered = proxy_cluster.render_codec_sweep_markdown(report)

    assert "| `raw` | 192 | 3/3 | 48,000 | 800.0 | 1.00x |" in rendered
    assert "| `zlib` | 192 | 3/3 | 96,000 | 1,600.0 | 2.00x |" in rendered
    assert "| `aiwire` | 192 | 3/3 | 164,000 | 2,730.0 | 3.41x |" in rendered
    assert "| `aiwire` | ingress | `tunnel_response_read` | 164,000 | 42.500 | 0.259 |" in rendered


def test_connections_sweep_parser_rejects_invalid_values() -> None:
    assert proxy_cluster.parse_connections_sweep("1,2,4") == [1, 2, 4]

    for value in ["", "0", "-1", "2,2", "fast"]:
        try:
            proxy_cluster.parse_connections_sweep(value)
        except argparse.ArgumentTypeError:
            pass
        else:
            raise AssertionError(f"expected invalid sweep value: {value}")


def test_tunnel_codec_sweep_parser_rejects_invalid_values() -> None:
    assert proxy_cluster.parse_tunnel_codec_sweep("raw,zlib,aiwire") == [
        "raw",
        "zlib",
        "aiwire",
    ]

    for value in ["", "gzip", "raw,raw"]:
        try:
            proxy_cluster.parse_tunnel_codec_sweep(value)
        except argparse.ArgumentTypeError:
            pass
        else:
            raise AssertionError(f"expected invalid codec sweep value: {value}")


def test_proxy_cluster_target_remote_root_overrides_global_default(
    tmp_path: Path,
    capsys,
) -> None:
    output = tmp_path / "plan.json"

    assert (
        proxy_cluster.main(
            [
                "--target",
                "edge-1=edge-host.local,remote_root=/home/edge/AURA",
                "--remote-root",
                "/wrong/global/AURA",
                "--run-id",
                "test-run",
                "--output-dir",
                str(tmp_path / "artifacts"),
                "--output",
                str(output),
            ]
        )
        == 0
    )

    rendered = json.loads(capsys.readouterr().out)
    start_fixture = rendered["targets"][0]["commands"]["start_fixture"]
    start_egress = rendered["targets"][0]["commands"]["start_egress"]

    assert rendered["targets"][0]["target"]["remote_root"] == "/home/edge/AURA"
    assert "cd /home/edge/AURA" in start_fixture
    assert "cd /home/edge/AURA" in start_egress
    assert "/wrong/global/AURA" not in start_fixture
    assert "/wrong/global/AURA" not in start_egress


def test_proxy_cluster_ssh_bootstrap_outputs_dry_run_commands(
    tmp_path: Path,
    capsys,
) -> None:
    public_key = tmp_path / "id_test.pub"
    public_key.write_text("ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAITestKey aura-test\n")
    output = tmp_path / "bootstrap.json"
    summary = tmp_path / "bootstrap.md"

    assert (
        proxy_cluster.main(
            [
                "--target",
                "edge-1=agent@192.0.2.10,ssh_port=2222",
                "--ssh-bootstrap",
                "--ssh-public-key",
                str(public_key),
                "--output",
                str(output),
                "--summary-output",
                str(summary),
            ]
        )
        == 0
    )

    rendered = json.loads(capsys.readouterr().out)
    written = json.loads(output.read_text())
    bootstrap = rendered["ssh_bootstrap"]
    target = bootstrap["targets"][0]
    summary_text = summary.read_text()

    assert rendered == written
    assert rendered["dry_run"] is True
    assert rendered["mode"] == "ssh_bootstrap"
    assert bootstrap["public_key_path"] == str(public_key)
    assert bootstrap["public_key_sha256"]
    assert target["ssh_copy_id_command"] == proxy_cluster._shell_command(
        ["ssh-copy-id", "-i", str(public_key), "-p", "2222", "agent@192.0.2.10"]
    )
    assert "authorized_keys" in target["console_authorized_keys_command"]
    assert "ssh -o BatchMode=yes -o ConnectTimeout=5 -p 2222" in target["post_check_command"]
    assert "## SSH Bootstrap" in summary_text
    assert "Target console path" in summary_text


def test_proxy_cluster_ssh_bootstrap_supports_per_target_public_keys(
    tmp_path: Path,
    capsys,
) -> None:
    default_key = tmp_path / "id_default.pub"
    first_key = tmp_path / "id_first.pub"
    second_key = tmp_path / "id_second.pub"
    default_key.write_text("ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAADefault aura-default\n")
    first_key.write_text("ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIFirstKey aura-first\n")
    second_key.write_text("ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAISecondKey aura-second\n")
    output = tmp_path / "bootstrap.json"
    summary = tmp_path / "bootstrap.md"

    assert (
        proxy_cluster.main(
            [
                "--target",
                f"edge-1=agent@192.0.2.10,ssh_public_key={first_key}",
                "--target",
                f"edge-2=agent@192.0.2.11,ssh_public_key={second_key}",
                "--ssh-bootstrap",
                "--ssh-public-key",
                str(default_key),
                "--output",
                str(output),
                "--summary-output",
                str(summary),
            ]
        )
        == 0
    )

    rendered = json.loads(capsys.readouterr().out)
    targets = rendered["ssh_bootstrap"]["targets"]
    summary_text = summary.read_text()

    assert rendered == json.loads(output.read_text())
    assert rendered["ssh_bootstrap"]["public_key_path"] == str(default_key)
    assert targets[0]["public_key_path"] == str(first_key)
    assert targets[1]["public_key_path"] == str(second_key)
    assert targets[0]["ssh_copy_id_command"] == proxy_cluster._shell_command(
        ["ssh-copy-id", "-i", str(first_key), "agent@192.0.2.10"]
    )
    assert targets[1]["ssh_copy_id_command"] == proxy_cluster._shell_command(
        ["ssh-copy-id", "-i", str(second_key), "agent@192.0.2.11"]
    )
    assert "aura-first" in targets[0]["console_authorized_keys_command"]
    assert "aura-second" in targets[1]["console_authorized_keys_command"]
    assert f"Public key path: `{first_key}`" in summary_text
    assert f"Public key path: `{second_key}`" in summary_text


def test_proxy_cluster_preflight_reports_ssh_auth_failure(monkeypatch, tmp_path: Path) -> None:
    output = tmp_path / "preflight.json"

    def fake_run_capture(
        command: list[str],
        *,
        timeout: float,
        check: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        del timeout, check
        if "-G" in command:
            return subprocess.CompletedProcess(
                command,
                0,
                stdout="hostname 192.0.2.10\nport 22\nuser agent\n",
                stderr="",
            )
        if command[-1] == "printf AURA_PROXY_PREFLIGHT_OK":
            return subprocess.CompletedProcess(
                command,
                255,
                stdout="",
                stderr="Permission denied (publickey).",
            )
        raise AssertionError(f"unexpected command: {command!r}")

    monkeypatch.setattr(proxy_cluster, "_run_capture", fake_run_capture)
    monkeypatch.setattr(
        proxy_cluster,
        "_tcp_probe",
        lambda host, port, timeout: {
            "ok": True,
            "host": host,
            "port": port,
            "elapsed_ms": 1.0,
        },
    )

    assert (
        proxy_cluster.main(
            [
                "--target",
                "edge-1=agent@192.0.2.10",
                "--preflight",
                "--output",
                str(output),
            ]
        )
        == 0
    )

    rendered = json.loads(output.read_text())
    target = rendered["preflight"]["targets"][0]

    assert rendered["mode"] == "preflight"
    assert rendered["preflight"]["ok"] is False
    assert target["tcp"]["ok"] is True
    assert target["ssh_auth"]["ok"] is False
    assert target["remote_environment"]["skipped"] == "ssh auth did not pass"
    assert target["errors"] == ["ssh batch authentication failed"]


def test_proxy_cluster_preflight_writes_ready_targets_output(
    monkeypatch,
    tmp_path: Path,
) -> None:
    output = tmp_path / "preflight.json"
    summary = tmp_path / "preflight.md"
    ready_targets = tmp_path / "ready.targets"

    def fake_run_preflight(plan: dict, args) -> dict:
        del args
        ready = plan["targets"][0]["target"]
        blocked = plan["targets"][1]["target"]
        return {
            "ok": False,
            "checked_at_utc": "2026-07-07T00:00:00Z",
            "targets": [
                {
                    "target": ready,
                    "ok": True,
                    "errors": [],
                    "tcp": {"ok": True},
                    "ssh_auth": {"ok": True},
                    "remote_environment": {"ok": True},
                },
                {
                    "target": blocked,
                    "ok": False,
                    "errors": ["ssh batch authentication failed"],
                    "tcp": {"ok": True},
                    "ssh_auth": {"ok": False},
                    "remote_environment": {"ok": False},
                },
            ],
        }

    monkeypatch.setattr(proxy_cluster, "run_preflight", fake_run_preflight)

    assert (
        proxy_cluster.main(
            [
                "--target",
                (
                    "edge-ready=agent@192.0.2.10,proxy_host=10.0.0.10,"
                    "egress_port=9510,upstream_port=9610,"
                    "remote_root=/home/edge/AURA,ssh_public_key=/keys/edge.pub"
                ),
                "--target",
                "edge-blocked=agent@192.0.2.11,proxy_host=10.0.0.11",
                "--preflight",
                "--ready-targets-output",
                str(ready_targets),
                "--output",
                str(output),
                "--summary-output",
                str(summary),
            ]
        )
        == 0
    )

    rendered = json.loads(output.read_text())
    ready_text = ready_targets.read_text()
    summary_text = summary.read_text()

    assert rendered["preflight"]["ok"] is False
    assert rendered["ready_targets_output"]["ready_targets"] == 1
    assert rendered["ready_targets_output"]["total_targets"] == 2
    assert "edge-ready=agent@192.0.2.10" in ready_text
    assert "proxy_host=10.0.0.10" in ready_text
    assert "egress_port=9510" in ready_text
    assert "upstream_port=9610" in ready_text
    assert "remote_root=/home/edge/AURA" in ready_text
    assert "ssh_public_key=/keys/edge.pub" in ready_text
    assert "edge-blocked" not in ready_text
    assert str(ready_targets) in summary_text
    assert "Wrote 1 of 2 targets" in summary_text


def test_proxy_cluster_preflight_blocks_run_on_failure(monkeypatch, tmp_path: Path) -> None:
    output = tmp_path / "preflight-run.json"

    monkeypatch.setattr(
        proxy_cluster,
        "_ssh_config_probe",
        lambda target, args: {"ok": True, "hostname": "192.0.2.10", "port": 22},
    )
    monkeypatch.setattr(
        proxy_cluster,
        "_tcp_probe",
        lambda host, port, timeout: {
            "ok": False,
            "host": host,
            "port": port,
            "elapsed_ms": 1.0,
            "error": "timed out",
        },
    )
    monkeypatch.setattr(
        proxy_cluster,
        "run_plan",
        lambda plan, args: (_ for _ in ()).throw(AssertionError("run should be blocked")),
    )

    assert (
        proxy_cluster.main(
            [
                "--target",
                "edge-1=agent@192.0.2.10",
                "--preflight",
                "--run",
                "--output",
                str(output),
            ]
        )
        == 2
    )

    rendered = json.loads(output.read_text())
    assert rendered["dry_run"] is True
    assert rendered["preflight"]["ok"] is False
