from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECK_TOOL = ROOT / "tools" / "check_aiwire_native_backend.py"


def _run_check_tool(*args: str) -> dict[str, object]:
    completed = subprocess.run(
        [sys.executable, str(CHECK_TOOL), *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return json.loads(completed.stdout)


def test_native_check_tool_status_only_allows_missing_backend() -> None:
    payload = _run_check_tool("--status-only", "--allow-missing")

    assert payload["schema"] == "aura.aiwire.native_check.v1"
    assert payload["ok"] is True
    assert payload["build"] == {"ok": True, "ran": False}
    assert "platform" in payload
    assert "native_status" in payload
    assert payload["checks"] == []


def test_native_check_tool_runs_or_skips_with_allow_missing() -> None:
    payload = _run_check_tool("--allow-missing", "--messages", "3")

    assert payload["schema"] == "aura.aiwire.native_check.v1"
    assert payload["ok"] is True
    assert payload["messages"] == 3
    status = payload["native_status"]
    assert isinstance(status, dict)
    checks = payload["checks"]
    assert isinstance(checks, list)

    if status["available"]:
        check_names = {str(check["name"]) for check in checks}
        assert "static_dictionary" in check_names
        assert "native_aiwire_roundtrip" in check_names
        assert "python_native_interop" in check_names
        assert all(bool(check["ok"]) for check in checks)
    else:
        assert checks == [
            {
                "name": "native_available",
                "ok": True,
                "skipped": True,
                "error": status["error"],
            }
        ]
