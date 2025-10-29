"""Streaming helpers for the regenerated AURA compressor."""

from __future__ import annotations

from dataclasses import dataclass
import struct
from typing import Dict, Optional, Sequence, Tuple

from .lib.hacs_tokenizer import HACSTokenizer
from .lib.template_manager import TemplateManager


@dataclass
class EncodedMessage:
    method: str
    payload: bytes
    metadata: Dict[str, str]


class AuraStreamSession:
    """High-level helper that mimics the behaviour of the legacy streamer.

    The session chooses between template compression and tokenised payloads
    using the regenerated :class:`TemplateManager`. Payloads now conform to the
    patent-described binary formats so messages can be transmitted without JSON
    overhead while still round-tripping through the simplified tokenizer.
    """

    def __init__(
        self,
        template_manager: Optional[TemplateManager] = None,
        tokenizer: Optional[HACSTokenizer] = None,
    ) -> None:
        self.template_manager = template_manager or TemplateManager()
        self.tokenizer = tokenizer or HACSTokenizer()
        self._session_vocab: Dict[int, str] = {}

    def encode_message(self, text: str) -> EncodedMessage:
        text_bytes = text.encode("utf-8")
        match = self.template_manager.match_template(text)
        if match:
            template_id, slots = match
            payload = self._encode_template_payload(template_id, slots)
            if len(payload) >= len(text_bytes):
                return self._build_plain_message(text_bytes)
            metadata = {"compression": "template", "template_id": str(template_id)}
            return EncodedMessage("template", payload, metadata)

        tokens, vocab = self.tokenizer.tokenize_text_with_map(text)
        new_entries = {token_id: token_text for token_id, token_text in vocab.items() if self._session_vocab.get(token_id) != token_text}
        payload = self._encode_tokenized_payload(tokens, new_entries)
        self._session_vocab.update(vocab)
        if len(payload) >= len(text_bytes):
            return self._build_plain_message(text_bytes)
        metadata = {"compression": "tokenized"}
        return EncodedMessage("tokenized", payload, metadata)

    def decode_message(self, message: EncodedMessage) -> str:
        if message.method == "template":
            template_id, slots = self._decode_template_payload(message.payload)
            template = self.template_manager.templates.get(template_id)
            if not template:
                raise ValueError(f"Unknown template ID {template_id}")
            formatted = template.pattern
            for index, slot in enumerate(slots):
                formatted = formatted.replace(f"{{{index}}}", slot)
            result = formatted.strip()
            if result.endswith((".", "!", "?")):
                return result
            return result + "."

        if message.method == "tokenized":
            tokens, new_vocab = self._decode_tokenized_payload(message.payload)
            self._session_vocab.update(new_vocab)
            self._restore_tokenizer(self._session_vocab)
            return self.tokenizer.detokenize(tokens)

        if message.method == "plain":
            return message.payload.decode("utf-8")

        raise ValueError(f"Unknown compression method '{message.method}'")

    @staticmethod
    def _encode_template_payload(template_id: int, slots: Sequence[str]) -> bytes:
        if template_id < 0 or template_id > 255:
            raise ValueError("Template ID must fit in one byte")
        if len(slots) > 255:
            raise ValueError("Too many slots to encode")

        payload = bytearray()
        payload.append(template_id & 0xFF)
        payload.append(len(slots) & 0xFF)

        for slot in slots:
            slot_bytes = slot.encode("utf-8")
            if len(slot_bytes) > 65535:
                raise ValueError("Slot value exceeds 65535 bytes")
            payload.extend(struct.pack(">H", len(slot_bytes)))
            payload.extend(slot_bytes)

        return bytes(payload)

    @staticmethod
    def _decode_template_payload(payload: bytes) -> Tuple[int, Tuple[str, ...]]:
        if len(payload) < 2:
            raise ValueError("Template payload too short")
        template_id = payload[0]
        slot_count = payload[1]
        offset = 2
        slots = []

        for index in range(slot_count):
            if offset + 2 > len(payload):
                raise ValueError(f"Missing length for slot {index}")
            slot_length = struct.unpack(">H", payload[offset : offset + 2])[0]
            offset += 2
            if offset + slot_length > len(payload):
                raise ValueError(f"Slot {index} truncated")
            slot_bytes = payload[offset : offset + slot_length]
            slots.append(slot_bytes.decode("utf-8"))
            offset += slot_length

        return template_id, tuple(slots)

    @staticmethod
    def _encode_tokenized_payload(tokens: Sequence[int], new_vocab: Dict[int, str]) -> bytes:
        if len(tokens) > 65535:
            raise ValueError("Token sequence too long to encode")

        payload = bytearray()
        payload.extend(struct.pack(">H", len(tokens)))
        for token in tokens:
            if token < 0 or token > 65535:
                raise ValueError("Token ID must fit in 16 bits")
            payload.extend(struct.pack(">H", token))

        vocab_items = sorted(new_vocab.items())
        if len(vocab_items) > 65535:
            raise ValueError("Vocabulary too large to encode")

        payload.extend(struct.pack(">H", len(vocab_items)))
        for token_id, token_text in vocab_items:
            if token_id < 0 or token_id > 65535:
                raise ValueError("Token ID must fit in 16 bits")
            token_bytes = token_text.encode("utf-8")
            if len(token_bytes) > 65535:
                raise ValueError("Token text exceeds 65535 bytes")
            payload.extend(struct.pack(">H", token_id))
            payload.extend(struct.pack(">H", len(token_bytes)))
            payload.extend(token_bytes)

        return bytes(payload)

    @staticmethod
    def _decode_tokenized_payload(payload: bytes) -> Tuple[Tuple[int, ...], Dict[int, str]]:
        view = memoryview(payload)
        offset = 0
        if len(view) < 2:
            raise ValueError("Token payload too short")

        token_count = struct.unpack_from(">H", view, offset)[0]
        offset += 2
        tokens = []
        for index in range(token_count):
            if offset + 2 > len(view):
                raise ValueError("Token list truncated")
            token_id = struct.unpack_from(">H", view, offset)[0]
            offset += 2
            tokens.append(token_id)

        if offset + 2 > len(view):
            raise ValueError("Missing vocabulary length")
        vocab_count = struct.unpack_from(">H", view, offset)[0]
        offset += 2
        vocab: Dict[int, str] = {}

        for index in range(vocab_count):
            if offset + 4 > len(view):
                raise ValueError("Vocabulary header truncated")
            token_id = struct.unpack_from(">H", view, offset)[0]
            offset += 2
            text_length = struct.unpack_from(">H", view, offset)[0]
            offset += 2
            if offset + text_length > len(view):
                raise ValueError("Vocabulary entry truncated")
            token_text = view[offset : offset + text_length].tobytes().decode("utf-8")
            offset += text_length
            vocab[token_id] = token_text

        return tuple(tokens), vocab

    def _restore_tokenizer(self, vocab: Dict[int, str]) -> None:
        for token_id, token_text in sorted(vocab.items()):
            self.tokenizer._dictionary[token_text] = token_id
            self.tokenizer._reverse_dictionary[token_id] = token_text
            self.tokenizer._next_token_id = max(self.tokenizer._next_token_id, token_id + 1)

    @staticmethod
    def _build_plain_message(text_bytes: bytes) -> EncodedMessage:
        return EncodedMessage("plain", text_bytes, {"compression": "none"})
