"""Persist discovered templates to disk for reuse across sessions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, List, Dict, Optional


class TemplateStore:
    """File-backed storage for dynamically discovered templates."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path) if path is not None else Path("logs") / "discovered_templates.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load_all(self) -> List[Dict[str, object]]:
        if not self.path.exists():
            return []
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
        if not isinstance(raw, list):
            return []
        templates: List[Dict[str, object]] = []
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            if "template_id" not in entry or "pattern" not in entry:
                continue
            templates.append(entry)
        return templates

    def save(self, records: Iterable[object]) -> None:
        serialisable: List[Dict[str, object]] = []
        for record in records:
            serialisable.append(
                {
                    "template_id": getattr(record, "template_id"),
                    "pattern": getattr(record, "pattern"),
                    "category": getattr(record, "category", "dynamic"),
                    "confidence": getattr(record, "confidence", 0.7),
                    "description": getattr(record, "description", ""),
                }
            )
        self.path.write_text(json.dumps(serialisable, ensure_ascii=False, indent=2), encoding="utf-8")

    def delete(self, template_id: int) -> None:
        remaining = [entry for entry in self.load_all() if entry.get("template_id") != template_id]
        self.path.write_text(json.dumps(remaining, ensure_ascii=False, indent=2), encoding="utf-8")
