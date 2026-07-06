from __future__ import annotations

import socket
import sys
from argparse import Namespace
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from compare_aiwire_coordinators import (  # noqa: E402
    DEFAULT_FIXTURE_CORPUS,
    SCHEMA,
    render_markdown,
    run_coordinator_comparison,
)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _free_contiguous_ports(count: int) -> int:
    for _attempt in range(50):
        base = _free_port()
        sockets = []
        try:
            for offset in range(count):
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.bind(("127.0.0.1", base + offset))
                sockets.append(sock)
            return base
        except OSError:
            for sock in sockets:
                sock.close()
        finally:
            for sock in sockets:
                sock.close()
    raise RuntimeError(f"could not find {count} contiguous free local ports")


def _comparison_args(port_base: int) -> Namespace:
    return Namespace(
        coordinators="threaded,asyncio",
        host="127.0.0.1",
        port_base=port_base,
        target_count=1,
        seconds=0.0,
        exchanges=2,
        codecs="raw,aiwire",
        backend="python",
        agent_count=1,
        pipeline_window=1,
        session_shards=1,
        target_parallelism=1,
        server_connection_workers=1,
        timeout=30.0,
        server_start_delay=0.35,
        link_mbps=10.0,
        one_way_delay_ms=0.0,
        jitter_ms=0.0,
        tail_pause_probability=0.0,
        tail_pause_ms=0.0,
        impairment_seed=1729,
        fixture_corpus=DEFAULT_FIXTURE_CORPUS,
        fixture_session_templates="updated",
        fixture_variation_profile="cluster",
    )


def test_coordinator_comparison_runs_threaded_and_asyncio() -> None:
    report = run_coordinator_comparison(_comparison_args(_free_contiguous_ports(2)))

    assert report["schema"] == SCHEMA
    assert report["ok"] is True
    assert report["settings"]["coordinators"] == ["threaded", "asyncio"]
    assert len(report["summaries"]) == 2
    assert {summary["coordinator"] for summary in report["summaries"]} == {
        "threaded",
        "asyncio",
    }

    for summary in report["summaries"]:
        assert summary["nary_negotiation_accepted"] is True
        assert summary["verified"] is True
        assert {row["codec"] for row in summary["aggregate"]} == {"raw", "aiwire"}
        for row in summary["aggregate"]:
            assert row["deadline_completed_exchanges"] == 2
            assert row["observed_exchanges_per_second"] > 0
            assert row["verified"] is True

    assert {delta["candidate_coordinator"] for delta in report["deltas"]} == {"asyncio"}
    assert {delta["codec"] for delta in report["deltas"]} == {"raw", "aiwire"}


def test_coordinator_comparison_markdown_summarizes_results() -> None:
    report = run_coordinator_comparison(_comparison_args(_free_contiguous_ports(2)))
    markdown = render_markdown(report)

    assert "AIWire Coordinator Comparison" in markdown
    assert "| threaded | raw |" in markdown
    assert "| asyncio | aiwire |" in markdown
    assert "| threaded | asyncio | aiwire |" in markdown
