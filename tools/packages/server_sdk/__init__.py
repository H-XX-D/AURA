"""Server SDK convenience layer for the AURA production stack."""

from __future__ import annotations

from typing import Callable, Dict, Optional

from aura_compression import (
    ProductionHybridCompressor,
    MetadataExtractor,
    FastPathClassifier,
    SecurityScreener,
    ConversationAccelerator,
)
from aura_compression.router import ProductionRouter


class ServerSDK:
    """Bundle of server-side components used in production."""

    def __init__(
        self,
        *,
        enable_aura: bool = True,
        aura_preference_margin: float = 0.0,
        template_store_path: Optional[str] = None,
        enable_audit_logging: bool = False,
        audit_log_directory: str = "./audit_logs",
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> None:
        self.compressor = ProductionHybridCompressor(
            enable_aura=enable_aura,
            aura_preference_margin=aura_preference_margin,
            template_store_path=template_store_path,
            enable_audit_logging=enable_audit_logging,
            audit_log_directory=audit_log_directory,
            session_id=session_id,
            user_id=user_id,
        )
        self.extractor = MetadataExtractor()
        self.classifier = FastPathClassifier()
        self.screener = SecurityScreener()
        self.accelerator = ConversationAccelerator()
        self.router = ProductionRouter()

    # ------------------------------------------------------------------ compression helpers

    def compress(self, text: str, **kwargs) -> tuple[bytes, object, Dict[str, object]]:
        return self.compressor.compress(text, **kwargs)

    def decompress(self, payload: bytes) -> str:
        return self.compressor.decompress(payload)

    def extract_metadata(self, payload: bytes) -> Dict[str, object]:
        return self.extractor.extract(payload).to_dict()

    def classify_intent(self, payload: bytes) -> Optional[str]:
        return self.classifier.classify(payload)

    def screen_fast_path(self, payload: bytes) -> bool:
        return self.screener.is_safe_fast_path(payload)

    def try_cache(self, metadata: Dict[str, object]) -> Optional[str]:
        return self.accelerator.try_fast_path(metadata)

    def cache_response(self, metadata: Dict[str, object], response: str) -> None:
        self.accelerator.cache_response(metadata, response)

    # ------------------------------------------------------------------ routing helpers

    def register_route(self, template_ids: list[int], handler: Callable[[Dict[str, object]], str]) -> None:
        self.router.register_route(
            handler_name=handler.__name__,
            handler_function=handler,
            template_ids=template_ids,
            requires_decompression=False,
        )

    def route(self, metadata: Dict[str, object], payload: bytes) -> str:
        return self.router.route(
            metadata=metadata,
            compressed_data=payload,
            decompressor=self.compressor.decompress,
        )


__all__ = ["ServerSDK"]
