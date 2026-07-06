from __future__ import annotations

import json
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import run_aiwire_proxy_cluster as proxy_cluster  # noqa: E402


def test_proxy_cluster_target_parser_supports_public_labels() -> None:
    target = proxy_cluster.parse_target(
        "edge-1=edge-host.local,proxy_host=10.0.0.10,egress_port=9510,upstream_port=9610",
        index=2,
        default_egress_port=9200,
        default_upstream_port=9300,
    )

    assert target.label == "edge-1"
    assert target.ssh_host == "edge-host.local"
    assert target.proxy_host == "10.0.0.10"
    assert target.egress_port == 9510
    assert target.upstream_port == 9610


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
    assert (
        "aura_compression.cli.proxy_fixture_server"
        in rendered["targets"][0]["commands"]["start_fixture"]
    )
    assert "aura_compression.cli.proxy" in rendered["targets"][0]["commands"]["start_egress"]
    assert "Run again with `--run`" in summary.read_text()
