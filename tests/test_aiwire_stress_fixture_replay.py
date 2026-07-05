from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from stress_ai_wire_roundtrip_z6 import _load_fixture_replay_corpus  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
STRESS_TOOL = ROOT / "tools" / "stress_ai_wire_roundtrip_z6.py"
FIXTURE_PATH = ROOT / "fixtures" / "aiwire_sessions" / "public_session_corpus_v1.json"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def test_fixture_replay_corpus_loader_prepares_verified_stream() -> None:
    replay = _load_fixture_replay_corpus(FIXTURE_PATH, session_template_mode="updated")

    assert replay.schema == "aura.aiwire.fixture_corpus.v1"
    assert replay.session_count == 2
    assert replay.exchange_count == 36
    assert len(replay.request_frames) == len(replay.response_frames) == 36
    assert len(replay.session_templates) == 8
    assert len(replay.request_sha256) == len(replay.response_sha256) == 64


def test_stress_tool_replays_public_fixture_over_tcp() -> None:
    port = _free_port()
    server_cmd = [
        sys.executable,
        str(STRESS_TOOL),
        "server",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--runs",
        "2",
        "--fixture-corpus",
        str(FIXTURE_PATH),
        "--fixture-session-templates",
        "updated",
    ]
    client_cmd = [
        sys.executable,
        str(STRESS_TOOL),
        "client",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--seconds",
        "0",
        "--exchanges",
        "6",
        "--codecs",
        "raw,aiwire",
        "--fixture-corpus",
        str(FIXTURE_PATH),
        "--fixture-session-templates",
        "updated",
        "--fixture-variation-profile",
        "cluster",
        "--force-session-templates",
        "--pipeline-window",
        "2",
        "--agent-count",
        "2",
        "--timeout",
        "20",
    ]
    server = subprocess.Popen(
        server_cmd,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    time.sleep(0.35)
    try:
        completed = subprocess.run(
            client_cmd,
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=40,
        )
        server_stdout, server_stderr = server.communicate(timeout=10)
    except BaseException as exc:
        server.terminate()
        try:
            server_stdout, server_stderr = server.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
            server_stdout, server_stderr = server.communicate()
        raise AssertionError(
            f"fixture replay failed: {exc!r}\nserver stdout:\n{server_stdout}\n"
            f"server stderr:\n{server_stderr}"
        ) from exc

    assert server.returncode == 0, server_stderr
    payload = json.loads(completed.stdout)
    rows = payload["results"]
    by_codec = {row["codec"]: row for row in rows}

    assert payload["fixture_replay"]["fixture_exchange_count"] == 36
    assert set(by_codec) == {"raw", "aiwire"}
    for row in rows:
        assert row["verified"] is True
        assert row["fixture_replay"] is True
        assert row["fixture_exchange_count"] == 36
        assert row["response_verification"] == "fixture_sha256"
        assert row["exchanges"] == 6
        assert row["raw_request_bytes"] > 0
        assert row["raw_response_bytes"] > 0

    assert by_codec["raw"]["session_template_count"] == 0
    assert by_codec["aiwire"]["session_template_count"] == 8
    assert by_codec["aiwire"]["aiwire_negotiation"]["accepted"] is True


def test_nary_client_replays_public_fixture_across_two_peers() -> None:
    ports = [_free_port(), _free_port()]
    server_cmds = [
        [
            sys.executable,
            str(STRESS_TOOL),
            "server",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--runs",
            "3",
            "--fixture-corpus",
            str(FIXTURE_PATH),
            "--fixture-session-templates",
            "updated",
        ]
        for port in ports
    ]
    servers = [
        subprocess.Popen(
            cmd,
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for cmd in server_cmds
    ]
    client_cmd = [
        sys.executable,
        str(STRESS_TOOL),
        "nary-client",
        "--target",
        f"edge-a=127.0.0.1:{ports[0]}",
        "--target",
        f"edge-b=127.0.0.1:{ports[1]}",
        "--seconds",
        "0",
        "--exchanges",
        "4",
        "--codecs",
        "raw,aiwire",
        "--fixture-corpus",
        str(FIXTURE_PATH),
        "--fixture-session-templates",
        "updated",
        "--fixture-variation-profile",
        "cluster",
        "--force-session-templates",
        "--pipeline-window",
        "2",
        "--agent-count",
        "2",
        "--target-parallelism",
        "2",
        "--timeout",
        "20",
    ]
    time.sleep(0.35)
    try:
        completed = subprocess.run(
            client_cmd,
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=50,
        )
        server_outputs = [server.communicate(timeout=10) for server in servers]
    except BaseException as exc:
        for server in servers:
            server.terminate()
        server_outputs = []
        for server in servers:
            try:
                server_outputs.append(server.communicate(timeout=5))
            except subprocess.TimeoutExpired:
                server.kill()
                server_outputs.append(server.communicate())
        details = "\n".join(
            f"server {index} stdout:\n{stdout}\nserver {index} stderr:\n{stderr}"
            for index, (stdout, stderr) in enumerate(server_outputs, start=1)
        )
        raise AssertionError(f"n-ary fixture replay failed: {exc!r}\n{details}") from exc

    for server, (_stdout, stderr) in zip(servers, server_outputs):
        assert server.returncode == 0, stderr

    payload = json.loads(completed.stdout)
    rows = payload["results"]
    aggregate = {row["codec"]: row for row in payload["aggregate"]}

    assert payload["mode"] == "nary_client"
    assert payload["participant_count"] == 3
    assert payload["remote_peer_count"] == 2
    assert payload["nary_negotiation"]["accepted"] is True
    assert payload["nary_negotiation"]["peer_count"] == 2
    assert len(payload["nary_peer_probes"]) == 2
    assert {probe["target"] for probe in payload["nary_peer_probes"]} == {
        "edge-a",
        "edge-b",
    }
    assert len(rows) == 4
    assert {row["target"] for row in rows} == {"edge-a", "edge-b"}
    assert {row["codec"] for row in rows} == {"raw", "aiwire"}
    for row in rows:
        assert row["verified"] is True
        assert row["fixture_replay"] is True
        assert row["fixture_exchange_count"] == 36
        assert row["fixture_variation_profile"] == "cluster"
        assert row["fixture_peer_label"] in {"edge-a", "edge-b"}
        assert row["response_verification"] == "fixture_sha256"
        assert row["exchanges"] == 4

    assert aggregate["raw"]["deadline_completed_exchanges"] == 8
    assert aggregate["aiwire"]["deadline_completed_exchanges"] == 8
    assert aggregate["aiwire"]["verified"] is True


def test_nary_client_replays_public_fixture_with_session_shards() -> None:
    ports = [_free_port(), _free_port()]
    server_cmds = [
        [
            sys.executable,
            str(STRESS_TOOL),
            "server",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--runs",
            "3",
            "--connection-workers",
            "2",
            "--fixture-corpus",
            str(FIXTURE_PATH),
            "--fixture-session-templates",
            "updated",
            "--link-mbps",
            "10",
        ]
        for port in ports
    ]
    servers = [
        subprocess.Popen(
            cmd,
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for cmd in server_cmds
    ]
    client_cmd = [
        sys.executable,
        str(STRESS_TOOL),
        "nary-client",
        "--target",
        f"edge-a=127.0.0.1:{ports[0]}",
        "--target",
        f"edge-b=127.0.0.1:{ports[1]}",
        "--seconds",
        "0",
        "--exchanges",
        "3",
        "--codecs",
        "aiwire",
        "--fixture-corpus",
        str(FIXTURE_PATH),
        "--fixture-session-templates",
        "updated",
        "--fixture-variation-profile",
        "cluster",
        "--force-session-templates",
        "--pipeline-window",
        "2",
        "--agent-count",
        "2",
        "--session-shards",
        "2",
        "--link-mbps",
        "10",
        "--target-parallelism",
        "4",
        "--timeout",
        "20",
    ]
    time.sleep(0.35)
    try:
        completed = subprocess.run(
            client_cmd,
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=50,
        )
        server_outputs = [server.communicate(timeout=10) for server in servers]
    except BaseException as exc:
        for server in servers:
            server.terminate()
        server_outputs = []
        for server in servers:
            try:
                server_outputs.append(server.communicate(timeout=5))
            except subprocess.TimeoutExpired:
                server.kill()
                server_outputs.append(server.communicate())
        details = "\n".join(
            f"server {index} stdout:\n{stdout}\nserver {index} stderr:\n{stderr}"
            for index, (stdout, stderr) in enumerate(server_outputs, start=1)
        )
        raise AssertionError(f"n-ary sharded fixture replay failed: {exc!r}\n{details}") from exc

    for server, (_stdout, stderr) in zip(servers, server_outputs):
        assert server.returncode == 0, stderr

    payload = json.loads(completed.stdout)
    rows = payload["results"]
    aggregate = payload["aggregate"][0]

    assert payload["mode"] == "nary_client"
    assert payload["participant_count"] == 3
    assert payload["remote_peer_count"] == 2
    assert payload["session_shards_per_target"] == 2
    assert payload["total_replay_sessions"] == 4
    assert payload["nary_negotiation"]["accepted"] is True
    assert len(rows) == 4
    assert {row["target"] for row in rows} == {"edge-a", "edge-b"}
    assert {row["session_shard"] for row in rows} == {1, 2}
    assert {row["fixture_peer_label"] for row in rows} == {
        "edge-a-shard-1",
        "edge-a-shard-2",
        "edge-b-shard-1",
        "edge-b-shard-2",
    }
    for row in rows:
        assert row["codec"] == "aiwire"
        assert row["verified"] is True
        assert row["fixture_replay"] is True
        assert row["fixture_variation_profile"] == "cluster"
        assert row["response_verification"] == "fixture_sha256"
        assert row["session_shards"] == 2
        assert row["server_session_shards"] == 2
        assert row["client_link_mbps"] == 5
        assert row["server_link_mbps"] == 5
        assert row["exchanges"] == 3

    assert aggregate["codec"] == "aiwire"
    assert aggregate["target_count"] == 2
    assert aggregate["session_count"] == 4
    assert aggregate["session_shards_per_target"] == 2
    assert aggregate["deadline_completed_exchanges"] == 12
    assert aggregate["verified"] is True
