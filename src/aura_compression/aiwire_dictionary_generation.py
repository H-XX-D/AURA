"""Corpus-driven AIWire dictionary candidate generation."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from .ai_wire import (
    AI_WIRE_DELTA_VERSION,
    AI_WIRE_DICTIONARY_FNV1A64,
    AI_WIRE_DICTIONARY_SHA256,
    AI_WIRE_PROTOCOL,
    AI_WIRE_STATIC_DICTIONARY,
    AI_WIRE_VERSION,
)
from .ai_wire_fixtures import load_aiwire_session_fixture_corpus
from .ai_wire_messages import encode_ai_wire_message, summarize_ai_wire_corpus

AIWIRE_DICTIONARY_CANDIDATES_SCHEMA = "aura.aiwire.dictionary_candidates.v1"
DEFAULT_PUBLIC_FIXTURE_CORPUS = Path("fixtures/aiwire_sessions/public_session_corpus_v1.json")
DEFAULT_MAX_DICTIONARY_BYTES = 32768

_JSON_FIELD_RE = re.compile(r'"(?:\\.|[^"\\]){2,96}":')
_JSON_STRING_PAIR_RE = re.compile(r'"(?:\\.|[^"\\]){2,96}":"(?:\\.|[^"\\]){2,160}"')
_JSON_SCALAR_PAIR_RE = re.compile(r'"(?:\\.|[^"\\]){2,96}":(?:true|false|null|-?\d+)')


def _canonical_json_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _fnv1a64(data: bytes) -> int:
    value = 0xCBF29CE484222325
    for byte in data:
        value ^= byte
        value = (value * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return value


def _source_add(target: dict[str, set[str]], term: str, source: str) -> None:
    target.setdefault(term, set()).add(source)


def _walk_json_terms(value: Any, sources: dict[str, set[str]], source: str) -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            key_text = _canonical_json_string(str(key))
            _source_add(sources, f"{key_text}:", source)
            if isinstance(nested, str):
                _source_add(sources, f"{key_text}:{_canonical_json_string(nested)}", source)
            elif isinstance(nested, bool):
                _source_add(sources, f"{key_text}:{str(nested).lower()}", source)
            elif nested is None:
                _source_add(sources, f"{key_text}:null", source)
            elif isinstance(nested, int) and not isinstance(nested, bool):
                _source_add(sources, f"{key_text}:{nested}", source)
            _walk_json_terms(nested, sources, source)
    elif isinstance(value, list):
        for nested in value:
            _walk_json_terms(nested, sources, source)


def _add_regex_terms(raw_text: str, sources: dict[str, set[str]], source: str) -> None:
    for pattern in (_JSON_STRING_PAIR_RE, _JSON_SCALAR_PAIR_RE, _JSON_FIELD_RE):
        for match in pattern.finditer(raw_text):
            _source_add(sources, match.group(0), source)


def _fixture_messages(corpus: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    messages: list[Mapping[str, Any]] = []
    sessions = corpus.get("sessions", [])
    if not isinstance(sessions, list):
        raise ValueError("AIWire fixture corpus sessions must be a list")
    for session in sessions:
        if not isinstance(session, Mapping):
            continue
        events = session.get("events", [])
        if not isinstance(events, list):
            continue
        for event in events:
            if not isinstance(event, Mapping) or event.get("kind") != "message":
                continue
            message = event.get("message")
            if isinstance(message, Mapping):
                messages.append(message)
    return messages


def _fixture_template_terms(corpus: Mapping[str, Any]) -> dict[str, set[str]]:
    sources: dict[str, set[str]] = {}
    for session in corpus.get("sessions", []):
        if not isinstance(session, Mapping):
            continue
        for key in ("initial_session_templates", "updated_session_templates"):
            entries = session.get(key, [])
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if isinstance(entry, Mapping) and entry.get("pattern"):
                    _source_add(sources, str(entry["pattern"]), key)
        diff = session.get("dictionary_diff", {})
        additions = diff.get("additions", []) if isinstance(diff, Mapping) else []
        if isinstance(additions, list):
            for entry in additions:
                if isinstance(entry, Mapping) and entry.get("pattern"):
                    _source_add(sources, str(entry["pattern"]), "dictionary_diff")
    return sources


@dataclass(frozen=True)
class AIWireDictionaryCandidate:
    """One deterministic corpus-derived dictionary term candidate."""

    term: str
    occurrences: int
    frame_count: int
    byte_length: int
    estimated_saved_bytes: int
    in_static_dictionary: bool
    sources: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        term_bytes = self.term.encode("utf-8")
        return {
            "term": self.term,
            "term_sha256": _sha256_hex(term_bytes),
            "byte_length": self.byte_length,
            "occurrences": self.occurrences,
            "frame_count": self.frame_count,
            "estimated_saved_bytes": self.estimated_saved_bytes,
            "in_static_dictionary": self.in_static_dictionary,
            "sources": list(self.sources),
        }


def _rank_candidates(
    candidates: Iterable[AIWireDictionaryCandidate],
) -> list[AIWireDictionaryCandidate]:
    return sorted(
        candidates,
        key=lambda candidate: (
            candidate.estimated_saved_bytes,
            candidate.occurrences,
            candidate.byte_length,
            candidate.term,
        ),
        reverse=True,
    )


def discover_aiwire_dictionary_candidates(
    messages: Iterable[Mapping[str, Any]],
    *,
    extra_terms: Mapping[str, Iterable[str]] | None = None,
    min_frequency: int = 2,
    min_length: int = 6,
    max_length: int = 160,
    max_entries: int = 128,
) -> list[AIWireDictionaryCandidate]:
    """Rank deterministic static-dictionary candidates from canonical messages."""

    if min_frequency <= 0:
        raise ValueError("min_frequency must be positive")
    if min_length <= 0:
        raise ValueError("min_length must be positive")
    if max_length < min_length:
        raise ValueError("max_length must be greater than or equal to min_length")
    if max_entries <= 0:
        raise ValueError("max_entries must be positive")

    raw_frames = [encode_ai_wire_message(message) for message in messages]
    term_sources: dict[str, set[str]] = {}
    for index, raw in enumerate(raw_frames, start=1):
        source = f"message:{index}"
        raw_text = raw.decode("utf-8", errors="replace")
        _add_regex_terms(raw_text, term_sources, source)
        try:
            decoded = json.loads(raw_text)
        except json.JSONDecodeError:
            decoded = None
        if decoded is not None:
            _walk_json_terms(decoded, term_sources, source)

    if extra_terms:
        for term, sources in extra_terms.items():
            for source in sources:
                _source_add(term_sources, term, source)

    occurrences_by_term: Counter[str] = Counter()
    frames_by_term: dict[str, int] = defaultdict(int)
    static_dictionary = AI_WIRE_STATIC_DICTIONARY
    candidates: list[AIWireDictionaryCandidate] = []
    for term in sorted(term_sources):
        term_bytes = term.encode("utf-8")
        byte_length = len(term_bytes)
        if byte_length < min_length or byte_length > max_length:
            continue
        frame_count = 0
        occurrences = 0
        for raw in raw_frames:
            count = raw.count(term_bytes)
            if count:
                frame_count += 1
                occurrences += count
        if occurrences < min_frequency:
            continue
        occurrences_by_term[term] = occurrences
        frames_by_term[term] = frame_count
        estimated_saved_bytes = max(0, occurrences * max(1, byte_length - 3))
        candidates.append(
            AIWireDictionaryCandidate(
                term=term,
                occurrences=occurrences_by_term[term],
                frame_count=frames_by_term[term],
                byte_length=byte_length,
                estimated_saved_bytes=estimated_saved_bytes,
                in_static_dictionary=term_bytes in static_dictionary,
                sources=tuple(sorted(term_sources[term])),
            )
        )

    return _rank_candidates(candidates)[:max_entries]


def build_aiwire_candidate_dictionary_bytes(
    candidates: Iterable[AIWireDictionaryCandidate],
    *,
    max_bytes: int = DEFAULT_MAX_DICTIONARY_BYTES,
) -> bytes:
    """Build zlib dictionary bytes from ranked candidates with best terms last."""

    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")
    ranked = _rank_candidates(candidates)
    payload = ("\n".join(candidate.term for candidate in reversed(ranked)) + "\n").encode("utf-8")
    return payload[-max_bytes:]


def build_aiwire_dictionary_candidate_report(
    *,
    fixture_corpus: str | Path = DEFAULT_PUBLIC_FIXTURE_CORPUS,
    min_frequency: int = 2,
    min_length: int = 6,
    max_length: int = 160,
    max_entries: int = 128,
    max_dictionary_bytes: int = DEFAULT_MAX_DICTIONARY_BYTES,
) -> dict[str, object]:
    """Build a deterministic AIWire dictionary candidate artifact from a fixture corpus."""

    corpus_path = Path(fixture_corpus)
    corpus = load_aiwire_session_fixture_corpus(corpus_path)
    messages = _fixture_messages(corpus)
    template_terms = _fixture_template_terms(corpus)
    candidates = discover_aiwire_dictionary_candidates(
        messages,
        extra_terms=template_terms,
        min_frequency=min_frequency,
        min_length=min_length,
        max_length=max_length,
        max_entries=max_entries,
    )
    dictionary_bytes = build_aiwire_candidate_dictionary_bytes(
        candidates,
        max_bytes=max_dictionary_bytes,
    )

    return {
        "schema": AIWIRE_DICTIONARY_CANDIDATES_SCHEMA,
        "protocol": AI_WIRE_PROTOCOL,
        "aiwire_version": AI_WIRE_VERSION,
        "delta_version": AI_WIRE_DELTA_VERSION,
        "source": {
            "fixture_corpus": str(corpus_path),
            "fixture_schema": corpus.get("schema"),
            "session_count": corpus.get("session_count"),
            "message_count": len(messages),
        },
        "parameters": {
            "min_frequency": min_frequency,
            "min_length": min_length,
            "max_length": max_length,
            "max_entries": max_entries,
            "max_dictionary_bytes": max_dictionary_bytes,
        },
        "baseline_static_dictionary": {
            "sha256": AI_WIRE_DICTIONARY_SHA256,
            "fnv1a64": f"{AI_WIRE_DICTIONARY_FNV1A64:016x}",
            "bytes": len(AI_WIRE_STATIC_DICTIONARY),
        },
        "corpus_summary": summarize_ai_wire_corpus(messages),
        "candidate_count": len(candidates),
        "candidate_terms": [candidate.to_dict() for candidate in candidates],
        "candidate_dictionary": {
            "bytes": len(dictionary_bytes),
            "sha256": _sha256_hex(dictionary_bytes),
            "fnv1a64": f"{_fnv1a64(dictionary_bytes):016x}",
            "term_count": len(candidates),
        },
    }


def write_aiwire_dictionary_candidate_report(
    output: str | Path,
    report: Mapping[str, Any],
) -> Path:
    """Write a stable JSON dictionary candidate artifact."""

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return output_path


def write_aiwire_candidate_dictionary(
    output: str | Path,
    report: Mapping[str, Any],
) -> Path:
    """Write candidate dictionary bytes from an existing report."""

    candidates = [
        AIWireDictionaryCandidate(
            term=str(candidate["term"]),
            occurrences=int(candidate["occurrences"]),
            frame_count=int(candidate["frame_count"]),
            byte_length=int(candidate["byte_length"]),
            estimated_saved_bytes=int(candidate["estimated_saved_bytes"]),
            in_static_dictionary=bool(candidate["in_static_dictionary"]),
            sources=tuple(str(source) for source in candidate.get("sources", [])),
        )
        for candidate in report.get("candidate_terms", [])
        if isinstance(candidate, Mapping)
    ]
    max_bytes = int(
        (report.get("parameters") or {}).get("max_dictionary_bytes", DEFAULT_MAX_DICTIONARY_BYTES)
        if isinstance(report.get("parameters"), Mapping)
        else DEFAULT_MAX_DICTIONARY_BYTES
    )
    dictionary = build_aiwire_candidate_dictionary_bytes(candidates, max_bytes=max_bytes)
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(dictionary)
    return output_path
