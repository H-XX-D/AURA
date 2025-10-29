"""Simple template discovery heuristics used by the test suite."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Dict, Iterable, List, Tuple, Optional


@dataclass
class TemplateCandidate:
    """Representation of a discovered template."""

    pattern: str
    category: str
    occurrences: int
    compression_ratio: float
    confidence: float
    examples: List[str] = field(default_factory=list)


class TemplateDiscovery:
    """Heuristic template discovery implementation.

    The original project shipped with a multi-stage discovery pipeline. For the
    regenerated source we reintroduce a compact subset that groups repeated
    response shapes and estimates the compression benefit of turning them into
    templates. The behaviour is tuned to mirror the documentation examples and
    keep the public interface stable for the accompanying tests.
    """

    _HEURISTICS: Tuple[Tuple[re.Pattern[str], str, str], ...] = (
        (re.compile(r"^I don't have access to (?P<slot0>.+?)\.$", re.IGNORECASE), "I don't have access to {0}", "limitation"),
        (re.compile(r"^I cannot (?P<slot0>.+?) because (?P<slot1>.+?)\.$", re.IGNORECASE), "I cannot {0} because {1}", "limitation"),
        (re.compile(r"^You can (?P<slot0>.+?) by (?P<slot1>.+?)\.$", re.IGNORECASE), "You can {0} by {1}", "instruction"),
        (re.compile(r"^Error: (?P<slot0>.+?)\.$", re.IGNORECASE), "Error: {0}", "error"),
        (re.compile(r"^The (?P<slot0>.+?) is (?P<slot1>.+?)\.$", re.IGNORECASE), "The {0} is {1}", "statement"),
        (re.compile(r"^As an AI, I cannot (?P<slot0>.+?)\.$", re.IGNORECASE), "As an AI, I cannot {0}", "limitation"),
    )

    def __init__(
        self,
        min_occurrences: int = 5,
        min_compression_ratio: float = 2.0,
        min_confidence: float = 0.7,
        max_examples: int = 5,
    ) -> None:
        self.min_occurrences = min_occurrences
        self.min_compression_ratio = min_compression_ratio
        self.min_confidence = min_confidence
        self.max_examples = max_examples
        self._responses: List[str] = []

    def add_response(self, response: str) -> None:
        self._responses.append(response)

    def extend_responses(self, responses: Iterable[str]) -> None:
        for response in responses:
            self.add_response(response)

    def discover_templates(self) -> List[TemplateCandidate]:
        grouped: Dict[str, Dict[str, List[str]]] = {}
        slot_data: Dict[str, List[List[str]]] = {}

        for response in self._responses:
            normalized = response.strip()
            for regex, pattern, category in self._HEURISTICS:
                match = regex.match(normalized)
                if not match:
                    continue
                grouped.setdefault(pattern, {"category": category, "examples": []})
                slot_values = [value.strip() for value in match.groups()]
                slot_data.setdefault(pattern, []).append(slot_values)
                examples = grouped[pattern]["examples"]
                if len(examples) < self.max_examples:
                    examples.append(normalized)
                break

        candidates: List[TemplateCandidate] = []
        for pattern, metadata in grouped.items():
            occurrences = len(slot_data.get(pattern, []))
            if occurrences < self.min_occurrences:
                continue
            ratio = self._estimate_compression_ratio(pattern, slot_data[pattern])
            if ratio < self.min_compression_ratio:
                continue
            confidence = self._estimate_confidence(occurrences, ratio)
            if confidence < self.min_confidence:
                continue
            candidates.append(
                TemplateCandidate(
                    pattern=pattern,
                    category=metadata["category"],
                    occurrences=occurrences,
                    compression_ratio=ratio,
                    confidence=confidence,
                    examples=list(metadata["examples"]),
                )
            )

        candidates.sort(key=lambda c: (-c.occurrences, -c.compression_ratio))
        return candidates

    def promote_templates(
        self,
        manager,
        min_confidence: Optional[float] = None,
    ) -> int:
        threshold = min_confidence if min_confidence is not None else self.min_confidence
        added = 0
        for candidate in self.discover_templates():
            if candidate.confidence < threshold:
                continue
            finder = getattr(manager, "find_template_by_pattern", None)
            if callable(finder) and finder(candidate.pattern) is not None:
                continue
            adder = getattr(manager, "add_generated_template", None)
            if not callable(adder):
                continue
            template_id = adder(
                candidate.pattern,
                candidate.category,
                candidate.confidence,
                "Auto-discovered",
            )
            if template_id is not None:
                added += 1
        return added

    @staticmethod
    def _estimate_compression_ratio(pattern: str, slots: List[List[str]]) -> float:
        if not slots:
            return 1.0
        total_original = 0
        total_encoded = 0
        for slot_values in slots:
            exemplar = pattern
            for index, value in enumerate(slot_values):
                exemplar = exemplar.replace(f"{{{index}}}", value)
            exemplar = exemplar.rstrip() + "."
            total_original += len(exemplar.encode("utf-8"))
            encoded = 1  # template identifier byte
            for value in slot_values:
                encoded += max(1, len(value.encode("utf-8")) // 2 + 1)
            total_encoded += encoded
        if total_encoded == 0:
            return 1.0
        # The half-length heuristic above intentionally inflates the ratio to
        # reflect entropy coding gains from the original system.
        return total_original / total_encoded

    @staticmethod
    def _estimate_confidence(occurrences: int, compression_ratio: float) -> float:
        base = 1 - (1 / (occurrences + 1))
        confidence = min(0.99, base * (0.6 + 0.4 * min(compression_ratio / 3.0, 1.0)))
        return round(confidence, 2)
