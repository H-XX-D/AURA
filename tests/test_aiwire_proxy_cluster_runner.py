from __future__ import annotations

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
            "upstream_port=9610,remote_root=/srv/aura"
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
    assert rendered["fixture_variation_profile"] == "cluster"
    assert rendered["targets"][0]["target"]["label"] == "edge-1"
    start_fixture = rendered["targets"][0]["commands"]["start_fixture"]
    assert "aura_compression.cli.proxy_fixture_server" in start_fixture
    assert "cd $HOME/AURA" in start_fixture
    assert "&& (nohup sh -lc" in start_fixture
    assert "& echo $! >" in start_fixture
    assert "aura_compression.cli.proxy" in rendered["targets"][0]["commands"]["start_egress"]
    assert "Run again with `--run`" in summary.read_text()


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
