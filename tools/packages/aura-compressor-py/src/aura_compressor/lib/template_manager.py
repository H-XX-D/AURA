"""Template management utilities for the regenerated AURA compressor."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Dict, Iterable, List, Optional, Pattern, Tuple

from .template_store import TemplateStore
from .template_discovery import TemplateDiscovery


_SLOT_RE = re.compile(r"\{(\d+)\}")


@dataclass
class TemplateRecord:
    """In-memory representation of a single template pattern."""

    template_id: int
    pattern: str
    category: str = "general"
    confidence: float = 0.75
    description: str = ""
    _regex: Pattern[str] = field(init=False, repr=False)
    _slot_order: List[int] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        slot_numbers = [int(match) for match in _SLOT_RE.findall(self.pattern)]
        seen: List[int] = []
        for number in slot_numbers:
            if number not in seen:
                seen.append(number)
        self._slot_order = seen
        self._regex = re.compile(self._pattern_to_regex(self.pattern), re.IGNORECASE)

    @staticmethod
    def _pattern_to_regex(pattern: str) -> str:
        parts = _SLOT_RE.split(pattern)
        regex_parts: List[str] = []
        literal = True
        for part in parts:
            if literal:
                regex_parts.append(re.escape(part))
            else:
                regex_parts.append(r"(?P<slot_%s>.+?)" % part)
            literal = not literal
        regex_body = "".join(regex_parts)
        return rf"^{regex_body}[\.!?]*$"

    def match(self, text: str) -> Optional[List[str]]:
        match = self._regex.match(text.strip())
        if not match:
            return None
        if not self._slot_order:
            return []
        slots: List[str] = []
        for slot_number in self._slot_order:
            captured = match.group(f"slot_{slot_number}")
            slots.append(captured.strip() if captured else "")
        return slots


class TemplateManager:
    """Manage template definitions, discovery, and persistence."""

    DEFAULT_TEMPLATES: Tuple[TemplateRecord, ...] = (
        TemplateRecord(0, "I don't have access to {0}", "limitation", 0.9),
        TemplateRecord(1, "You can {0} by {1}", "instruction", 0.85),
        TemplateRecord(2, "Error: {0}", "error", 0.8),
        TemplateRecord(3, "As an AI, I cannot {0}", "limitation", 0.88),
        TemplateRecord(4, "I cannot {0} because {1}", "limitation", 0.9),
        TemplateRecord(5, "The {0} is {1}", "statement", 0.82),
        TemplateRecord(6, "Can you {0}?", "question", 0.83),
    )

    def __init__(
        self,
        auto_update: bool = True,
        max_templates: int = 255,
        buffer_max_size: int = 100,
        template_store: Optional[TemplateStore] = None,
        discovery: Optional[TemplateDiscovery] = None,
        dynamic_id_start: int = 200,
    ) -> None:
        self.auto_update = auto_update
        self.max_templates = max_templates
        self.buffer_max_size = buffer_max_size
        self.dynamic_id_start = dynamic_id_start

        self.template_store = template_store or TemplateStore()
        self.discovery = discovery or TemplateDiscovery()
        self._discovery_factory = lambda: TemplateDiscovery(
            min_occurrences=self.discovery.min_occurrences,
            min_compression_ratio=self.discovery.min_compression_ratio,
            min_confidence=self.discovery.min_confidence,
            max_examples=self.discovery.max_examples,
        )

        self.templates: Dict[int, TemplateRecord] = {
            template.template_id: template for template in self.DEFAULT_TEMPLATES
        }
        self.response_buffer: List[str] = []
        self._compression_stats = {
            "total_compressions": 0,
            "template_hits": 0,
            "template_misses": 0,
            "total_bytes_saved": 0,
        }

        for entry in self.template_store.load_all():
            template_id = int(entry.get("template_id", -1))
            pattern = entry.get("pattern")
            if template_id < self.dynamic_id_start or pattern is None:
                continue
            if template_id in self.templates or len(self.templates) >= self.max_templates:
                continue
            self.templates[template_id] = TemplateRecord(
                template_id=template_id,
                pattern=str(pattern),
                category=str(entry.get("category", "dynamic")),
                confidence=float(entry.get("confidence", 0.7)),
                description=str(entry.get("description", "")),
            )

    def match_template(self, text: str) -> Optional[Tuple[int, List[str]]]:
        for template_id, record in self.templates.items():
            slots = record.match(text)
            if slots is not None:
                return template_id, slots
        return None

    def add_template(
        self,
        template_id: int,
        pattern: str,
        category: str = "custom",
        confidence: float = 0.7,
        description: str = "",
    ) -> bool:
        if template_id in self.templates or len(self.templates) >= self.max_templates:
            return False
        self.templates[template_id] = TemplateRecord(
            template_id=template_id,
            pattern=pattern,
            category=category,
            confidence=confidence,
            description=description,
        )
        if template_id >= self.dynamic_id_start:
            self._persist_dynamic_templates()
        return True

    def add_generated_template(
        self,
        pattern: str,
        category: str = "dynamic",
        confidence: float = 0.7,
        description: str = "",
    ) -> Optional[int]:
        if self.find_template_by_pattern(pattern) is not None:
            return None
        template_id = self._allocate_template_id()
        if template_id is None:
            return None
        if self.add_template(template_id, pattern, category, confidence, description):
            return template_id
        return None

    def remove_template(self, template_id: int) -> bool:
        if template_id in self.templates:
            is_dynamic = template_id >= self.dynamic_id_start
            del self.templates[template_id]
            if is_dynamic:
                self._persist_dynamic_templates()
            return True
        return False

    def record_compression(
        self,
        template_id: Optional[int],
        original_size: int,
        compressed_size: int,
    ) -> None:
        stats = self._compression_stats
        stats["total_compressions"] += 1
        if template_id is None:
            stats["template_misses"] += 1
        else:
            stats["template_hits"] += 1
        saved = max(0, original_size - compressed_size)
        stats["total_bytes_saved"] += saved

    def record_response(self, response: str) -> None:
        self.response_buffer.append(response)
        if self.discovery:
            self.discovery.add_response(response)
        if not self.auto_update:
            return
        if len(self.response_buffer) >= self.buffer_max_size:
            self._run_auto_discovery()

    def extend_responses(self, responses: Iterable[str]) -> None:
        for response in responses:
            self.record_response(response)

    def get_statistics(self) -> Dict[str, object]:
        return {
            "template_count": len(self.templates),
            "compression_stats": dict(self._compression_stats),
            "buffer_size": len(self.response_buffer),
        }

    def clear_statistics(self) -> None:
        for key in self._compression_stats:
            self._compression_stats[key] = 0


    def run_discovery(self) -> int:
        """Force discovery on accumulated responses."""
        return self._run_auto_discovery()
    def find_template_by_pattern(self, pattern: str) -> Optional[int]:
        for template_id, record in self.templates.items():
            if record.pattern == pattern:
                return template_id
        return None

    def _allocate_template_id(self) -> Optional[int]:
        for candidate in range(self.dynamic_id_start, 256):
            if candidate not in self.templates:
                return candidate
        return None

    def _persist_dynamic_templates(self) -> None:
        dynamic_records = [
            record
            for record in self.templates.values()
            if record.template_id >= self.dynamic_id_start
        ]
        self.template_store.save(dynamic_records)

    def _run_auto_discovery(self) -> int:
        if not self.discovery:
            return 0
        added = self.discovery.promote_templates(self)
        if added:
            self._persist_dynamic_templates()
        self.response_buffer.clear()
        self.discovery = self._discovery_factory()
        return added
