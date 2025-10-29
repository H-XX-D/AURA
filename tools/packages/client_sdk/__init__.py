"""Minimal client SDK for decoding sanitized AURA payloads."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Tuple

from aura_compression import ProductionHybridCompressor
from aura_compression.experimental.auralite.decoder import AuraLiteDecoder
from aura_compression.experimental.brio.decoder import BrioDecoder
from aura_compression.experimental.brio.tokens import TemplateToken
from aura_compression.metadata import MetadataKind
from aura_compression.templates import TemplateLibrary

_BINARY_METHOD = 0x00
_AURALITE_METHOD = 0x01  # AuraLite fallback (replaces Brotli)
_BRIO_METHOD = 0x02
_AURA_LITE_METHOD = 0x03
_UNCOMPRESSED_METHOD = 0xFF


class ClientSDK:
    """Client-side decoder aware of template metadata.

    The client only needs the template patterns to rebuild plaintext. When the
    server ships a sanitized payload (binary template or template-aware BRIO),
    the client uses this helper to render the original message without server
    metadata.
    """

    def __init__(
        self,
        *,
        template_store_path: Optional[Path | str] = None,
        extra_templates: Optional[Mapping[int, str]] = None,
    ) -> None:
        self._compressor = ProductionHybridCompressor(
            enable_aura=True,
            aura_preference_margin=-1.0,
            template_store_path=template_store_path,
            enable_audit_logging=False,
        )
        self._library = self._compressor.template_library
        self._brio_decoder = BrioDecoder(template_library=self._library)
        self._auralite_decoder = AuraLiteDecoder(template_library=self._library)

        if template_store_path:
            self.load_templates_from_store(template_store_path)

        if extra_templates:
            for template_id, pattern in extra_templates.items():
                self.register_template(template_id, pattern)

    # ------------------------------------------------------------------ template management

    def load_templates_from_store(self, store_path: Path | str) -> None:
        data = json.loads(Path(store_path).read_text(encoding="utf-8"))
        raw = data.get("templates") or data.get("platform_templates") or {}
        if not isinstance(raw, Mapping):
            return
        dynamic: Dict[int, str] = {}
        for key, info in raw.items():
            try:
                template_id = int(key)
            except (TypeError, ValueError):
                continue
            if not isinstance(info, Mapping):
                continue
            pattern = info.get("pattern")
            if isinstance(pattern, str) and pattern.strip():
                dynamic[template_id] = pattern
        if dynamic:
            self._library.sync_dynamic_templates(dynamic)
            self._compressor.template_library.sync_dynamic_templates(dynamic)

    def register_template(self, template_id: int, pattern: str) -> None:
        self._library.add(template_id, pattern)

    # ------------------------------------------------------------------ decoding entrypoints

    def decode_payload(self, payload: bytes, *, return_metadata: bool = False) -> Tuple[str, Dict[str, object]] | str:
        if not payload:
            raise ValueError("Payload is empty")
        method = payload[0]
        if method == _BINARY_METHOD:
            text, meta = self._decode_binary(payload)
        elif method == _BRIO_METHOD:
            text, meta = self._decode_brio(payload)
        elif method == _AURA_LITE_METHOD:
            text, meta = self._decode_aura_lite(payload)
        elif method == _AURALITE_METHOD:
            text, meta = self._decode_aura_lite(payload)  # AuraLite fallback uses same decoder
        elif method == _UNCOMPRESSED_METHOD:
            text = payload[1:].decode("utf-8")
            meta = {"method": "uncompressed"}
        else:
            raise ValueError(f"Unknown payload method: 0x{method:02x}")
        if return_metadata:
            return text, meta
        return text

    # ------------------------------------------------------------------ helpers

    def _decode_binary(self, payload: bytes) -> Tuple[str, Dict[str, object]]:
        view = memoryview(payload)
        template_id = view[1]
        slot_count = view[2]
        offset = 3
        slots: List[str] = []
        for _ in range(slot_count):
            if offset + 2 > len(view):
                raise ValueError("Malformed binary payload")
            slot_len = int.from_bytes(view[offset:offset + 2], "big")
            offset += 2
            if offset + slot_len > len(view):
                raise ValueError("Malformed binary payload")
            slots.append(view[offset:offset + slot_len].tobytes().decode("utf-8"))
            offset += slot_len
        text = self._library.format_template(template_id, slots)
        meta = {
            "method": "binary_semantic",
            "template_id": template_id,
            "template_ids": [template_id],
        }
        return text, meta

    def _decode_brio(self, payload: bytes) -> Tuple[str, Dict[str, object]]:
        result = self._brio_decoder.decompress(payload[1:])
        text = result.text
        template_ids = [
            entry.value
            for entry in result.metadata
            if entry.kind == MetadataKind.TEMPLATE.value and entry.flags
        ]
        if not template_ids:
            template_ids = [
                token.template_id
                for token in result.tokens
                if isinstance(token, TemplateToken)
            ]
        meta = {
            "method": "brio",
            "template_ids": template_ids,
            "metadata_entries": [
                {
                    "token_index": entry.token_index,
                    "kind": entry.kind,
                    "value": entry.value,
                    "flags": entry.flags,
                }
                for entry in result.metadata
            ],
        }
        return text, meta

    def _decode_aura_lite(self, payload: bytes) -> Tuple[str, Dict[str, object]]:
        decoded = self._auralite_decoder.decode(payload[1:])
        meta = {
            "method": "aura_lite",
            "template_ids": list(decoded.template_ids),
        }
        return decoded.text, meta

    def list_templates(self) -> Dict[int, str]:
        return self._library.list_templates()

    # ------------------------------------------------------------------ compression helpers

    def compress(
        self,
        text: str,
        *,
        template_id: Optional[int] = None,
        slots: Optional[Iterable[str]] = None,
    ):
        """Compress user input, preserving full metadata for server auditing."""
        slot_list = list(slots) if slots is not None else None
        return self._compressor.compress(text, template_id=template_id, slots=slot_list)


__all__ = ["ClientSDK"]
