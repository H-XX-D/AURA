#!/usr/bin/env python3
"""Replay audit logs into the template discovery pipeline."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable
import sys

SCRIPT_ROOT = Path(__file__).resolve().parent.parent
PACKAGE_SRC = SCRIPT_ROOT / "packages" / "aura-compressor-py" / "src"
if str(PACKAGE_SRC) not in sys.path:
    sys.path.insert(0, str(PACKAGE_SRC))

from aura_compressor.lib.template_manager import TemplateManager, TemplateStore


def iter_messages(paths: Iterable[Path]) -> Iterable[str]:
    for path in paths:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if line.startswith("Message:"):
                yield line.partition("Message:")[2].strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--store",
        type=Path,
        default=Path("logs/discovered_templates.json"),
        help="Path to template store file (default: logs/discovered_templates.json)",
    )
    parser.add_argument(
        "source",
        nargs="*",
        type=Path,
        default=list(Path("audit").glob("*.log")),
        help="Explicit log files to ingest (defaults to all audit/*.log)",
    )
    args = parser.parse_args()

    store = TemplateStore(args.store)
    manager = TemplateManager(template_store=store)

    count = 0
    for message in iter_messages(args.source):
        manager.record_response(message)
        count += 1

    added = manager.run_discovery()
    print(f"Recorded {count} messages; promoted {added} new template(s).")


if __name__ == "__main__":
    main()
