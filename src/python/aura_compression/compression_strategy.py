#!/usr/bin/env python3
"""
Compression Strategy Pattern - Extracted compression algorithms from ProductionHybridCompressor
Implements strategy pattern for different compression methods with clean interfaces
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, Tuple, Protocol

from .templates import TemplateMatch
from .enums import CompressionMethod


class CompressionResult:
    """Result of a compression attempt"""

    def __init__(
        self,
        payload: bytes,
        method: CompressionMethod,
        metadata: Dict[str, Any],
        can_compress: bool = True,
    ):
        self.payload = payload
        self.method = method
        self.metadata = metadata
        self.can_compress = can_compress

    @property
    def compression_ratio(self) -> float:
        """Calculate compression ratio"""
        original_size = self.metadata.get('original_size', 0)
        compressed_size = self.metadata.get('compressed_size', len(self.payload))
        return original_size / compressed_size if compressed_size else float('inf')


class CompressionContext:
    """Context information for compression strategies"""

    def __init__(
        self,
        text: str,
        original_size: int,
        template_match: Optional[TemplateMatch] = None,
        template_spans: Optional[List[TemplateMatch]] = None,
        enable_aura: bool = True,
        tcp_brio_threshold: int = 2000,
    ):
        self.text = text
        self.original_size = original_size
        self.template_match = template_match
        self.template_spans = template_spans or []
        self.enable_aura = enable_aura
        self.tcp_brio_threshold = tcp_brio_threshold


class CompressionStrategyInterface(Protocol):
    """Protocol for compression strategy implementations"""

    def can_compress(self, context: CompressionContext) -> bool:
        """Check if this strategy can compress the given text"""
        ...

    def compress(self, context: CompressionContext) -> CompressionResult:
        """Compress the text using this strategy"""
        ...

    def get_method(self) -> CompressionMethod:
        """Get the compression method this strategy implements"""
        ...


class CompressionStrategy(ABC):
    """Abstract base class for compression strategies"""

    def __init__(self, method: CompressionMethod):
        self.method = method

    def get_method(self) -> CompressionMethod:
        return self.method

    @abstractmethod
    def can_compress(self, context: CompressionContext) -> bool:
        """Check if this strategy can compress the given text"""
        pass

    @abstractmethod
    def compress(self, context: CompressionContext) -> CompressionResult:
        """Compress the text using this strategy"""
        pass


class UncompressedStrategy(CompressionStrategy):
    """Strategy for uncompressed text (fallback)"""

    def __init__(self):
        super().__init__(CompressionMethod.UNCOMPRESSED)

    def can_compress(self, context: CompressionContext) -> bool:
        """Uncompressed can always be used as fallback"""
        return True

    def compress(self, context: CompressionContext) -> CompressionResult:
        """Return uncompressed text with method marker"""
        payload = bytes([self.method.value]) + context.text.encode('utf-8')
        compressed_size = len(payload)
        metadata = {
            'original_size': context.original_size,
            'compressed_size': compressed_size,
            'ratio': context.original_size / compressed_size if compressed_size else float('inf'),
            'method': 'uncompressed',
            'reason': 'fallback_candidate',
            'fast_path_candidate': False,
        }
        return CompressionResult(payload, self.method, metadata)


class BinarySemanticStrategy(CompressionStrategy):
    """Strategy for binary semantic compression using templates"""

    def __init__(self, template_service: Any):
        super().__init__(CompressionMethod.BINARY_SEMANTIC)
        self.template_service = template_service

    def can_compress(self, context: CompressionContext) -> bool:
        """Can compress if we have a template match"""
        return context.template_match is not None

    def compress(self, context: CompressionContext) -> CompressionResult:
        """Compress using binary semantic method"""
        if not context.template_match:
            # Return uncompressed as fallback
            uncompressed = UncompressedStrategy()
            return uncompressed.compress(context)

        try:
            binary_data = self.template_service.compress_with_template(
                context.template_match.template_id,
                context.template_match.slots
            )
            payload = bytes([self.method.value]) + binary_data
            compressed_size = len(payload)

            metadata = {
                'original_size': context.original_size,
                'compressed_size': compressed_size,
                'ratio': context.original_size / compressed_size if compressed_size else float('inf'),
                'method': 'binary_semantic',
                'template_id': context.template_match.template_id,
                'template_ids': [context.template_match.template_id],
                'slot_count': len(context.template_match.slots),
                'fast_path_candidate': False,
            }

            # Only consider it successful compression if we actually reduced size
            can_compress = compressed_size < context.original_size
            return CompressionResult(payload, self.method, metadata, can_compress)

        except Exception:
            # Fallback to uncompressed
            uncompressed = UncompressedStrategy()
            return uncompressed.compress(context)


class BrioStrategy(CompressionStrategy):
    """Strategy for BRIO compression (experimental AURA)"""

    def __init__(self, aura_encoder: Any = None, tcp_brio_encoder: Any = None):
        super().__init__(CompressionMethod.BRIO)
        self.aura_encoder = aura_encoder
        self.tcp_brio_encoder = tcp_brio_encoder

    def can_compress(self, context: CompressionContext) -> bool:
        """Can compress if AURA is enabled and encoders are available"""
        return (
            context.enable_aura and
            (self.aura_encoder is not None or self.tcp_brio_encoder is not None)
        )

    def compress(self, context: CompressionContext) -> CompressionResult:
        """Compress using BRIO method"""
        if not self.can_compress(context):
            uncompressed = UncompressedStrategy()
            return uncompressed.compress(context)

        try:
            compressed_results = []
            
            # Try TCP BRIO encoder if available
            if self.tcp_brio_encoder:
                try:
                    tcp_compressed = self.tcp_brio_encoder.compress(context.text)
                    # Validate magic bytes
                    if tcp_compressed.payload.startswith(b"BR"):
                        tcp_payload = bytes([self.method.value]) + tcp_compressed.payload
                        compressed_results.append(('tcp', tcp_compressed, tcp_payload))
                except Exception:
                    pass
            
            # Try full BRIO encoder if available
            if self.aura_encoder:
                try:
                    aura_compressed = self.aura_encoder.compress(
                        context.text,
                        template_match=context.template_match,
                    )
                    # Validate magic bytes
                    if aura_compressed.payload.startswith(b"AURA"):
                        aura_payload = bytes([self.method.value]) + aura_compressed.payload
                        compressed_results.append(('aura', aura_compressed, aura_payload))
                except Exception:
                    pass
            
            if not compressed_results:
                # BRIO compression failed, don't return a candidate
                raise ValueError("BRIO compression failed - no encoders available")
            
            # Choose the best compression (smallest payload)
            best_result = min(compressed_results, key=lambda x: len(x[2]))
            encoder_type, compressed, payload = best_result
            compressed_size = len(payload)

            # Handle metadata format
            metadata_entries = []
            for entry in compressed.metadata:
                entry_dict = {
                    'token_index': entry.token_index,
                    'kind': entry.kind,
                    'value': entry.value,
                }
                # Add flags if present
                if hasattr(entry, 'flags'):
                    entry_dict['flags'] = entry.flags
                metadata_entries.append(entry_dict)

            template_ids = [
                entry['value']
                for entry in metadata_entries
                if entry['kind'] == 0x01 and entry.get('flags', 0)
            ]

            token_counts = {
                'total': len(compressed.tokens),
                'literals': sum(getattr(t, '__class__.__name__', '').endswith('LiteralToken') for t in compressed.tokens),
                'dictionary': sum(getattr(t, '__class__.__name__', '').endswith('DictionaryToken') for t in compressed.tokens),
                'matches': sum(getattr(t, '__class__.__name__', '').endswith('MatchToken') for t in compressed.tokens),
                'templates': sum(getattr(t, '__class__.__name__', '').endswith('TemplateToken') for t in compressed.tokens),
            }

            metadata = {
                'original_size': context.original_size,
                'compressed_size': compressed_size,
                'ratio': context.original_size / compressed_size if compressed_size else float('inf'),
                'method': 'aura',
                'template_ids': template_ids,
                'metadata_entries': metadata_entries,
                'token_counts': token_counts,
                'template_id': template_ids[0] if template_ids else None,
                'fast_path_candidate': any(
                    entry['kind'] == 0x01 and entry.get('flags')
                    for entry in metadata_entries
                ),
            }

            can_compress = len(payload) < context.original_size
            return CompressionResult(payload, self.method, metadata, can_compress)

        except Exception:
            uncompressed = UncompressedStrategy()
            return uncompressed.compress(context)


class AuraLiteStrategy(CompressionStrategy):
    """Strategy for AURA-Lite compression"""

    def __init__(self, aura_lite_encoder: Any = None):
        super().__init__(CompressionMethod.AURA_LITE)
        self.aura_lite_encoder = aura_lite_encoder

    def can_compress(self, context: CompressionContext) -> bool:
        """Can compress if encoder is available"""
        return self.aura_lite_encoder is not None

    def compress(self, context: CompressionContext) -> CompressionResult:
        """Compress using AURA-Lite method"""
        if not self.can_compress(context):
            uncompressed = UncompressedStrategy()
            return uncompressed.compress(context)

        try:
            encoded = self.aura_lite_encoder.encode(
                context.text,
                context.template_match,
                template_spans=context.template_spans,
            )

            payload = bytes([self.method.value]) + encoded.payload
            compressed_size = len(payload)

            candidate_template_ids = list(encoded.template_ids)
            if not candidate_template_ids and context.template_match:
                candidate_template_ids = [context.template_match.template_id]

            # Check if template metadata expands payload too much
            template_heavy = context.template_match is not None or bool(context.template_spans)
            if template_heavy:
                alt_encoded = self.aura_lite_encoder.encode(context.text, None, template_spans=[])
                alt_size = len(alt_encoded.payload) + 1
                if alt_size < compressed_size:
                    encoded = alt_encoded
                    payload = bytes([self.method.value]) + encoded.payload
                    compressed_size = len(payload)
                    candidate_template_ids = list(alt_encoded.template_ids)

            metadata = {
                'original_size': context.original_size,
                'compressed_size': compressed_size,
                'ratio': context.original_size / compressed_size if compressed_size else float('inf'),
                'method': 'aura_lite',
                'template_ids': candidate_template_ids,
                'template_id': candidate_template_ids[0] if candidate_template_ids else None,
                'fast_path_candidate': bool(encoded.template_ids),
            }

            can_compress = len(payload) < context.original_size
            return CompressionResult(payload, self.method, metadata, can_compress)

        except Exception:
            uncompressed = UncompressedStrategy()
            return uncompressed.compress(context)


class AuraliteStrategy(CompressionStrategy):
    """Strategy for AuraLite compression (proprietary fallback)"""

    def __init__(self, aura_lite_encoder: Any = None):
        super().__init__(CompressionMethod.AURALITE)
        self.aura_lite_encoder = aura_lite_encoder

    def can_compress(self, context: CompressionContext) -> bool:
        """AuraLite can always be used as fallback"""
        return self.aura_lite_encoder is not None

    def compress(self, context: CompressionContext) -> CompressionResult:
        """Compress using AuraLite method"""
        if not self.can_compress(context):
            uncompressed = UncompressedStrategy()
            return uncompressed.compress(context)

        try:
            # Use simple literal encoding
            encoded = self.aura_lite_encoder.encode(context.text, None, template_spans=[])
            payload = bytes([self.method.value]) + encoded.payload
            compressed_size = len(payload)

            metadata = {
                'original_size': context.original_size,
                'compressed_size': compressed_size,
                'ratio': context.original_size / compressed_size if compressed_size else float('inf'),
                'method': 'auralite',
                'reason': 'no_template' if context.template_match is None else 'auralite_better',
                'fast_path_candidate': False,
                'fallback_from': None,
                'attempted_methods': ['auralite'],
            }

            can_compress = len(payload) < context.original_size
            return CompressionResult(payload, self.method, metadata, can_compress)

        except Exception:
            # Ultimate fallback to uncompressed
            uncompressed = UncompressedStrategy()
            return uncompressed.compress(context)


class AuraHeavyStrategy(CompressionStrategy):
    """Strategy for AURA Heavy compression (hybrid semantic + traditional)"""

    def __init__(self, aura_heavy_compressor: Any = None):
        super().__init__(CompressionMethod.AURA_HEAVY)  # Use AURA_HEAVY method enum
        self.aura_heavy_compressor = aura_heavy_compressor

    def can_compress(self, context: CompressionContext) -> bool:
        """Can compress if AURA Heavy compressor is available"""
        return self.aura_heavy_compressor is not None

    def compress(self, context: CompressionContext) -> CompressionResult:
        """Compress using AURA Heavy method"""
        if not self.can_compress(context):
            uncompressed = UncompressedStrategy()
            return uncompressed.compress(context)

        try:
            # AURA Heavy has different API - returns AuraHeavyResult
            result = self.aura_heavy_compressor.compress(context.text)

            # Determine the correct method based on AuraHeavy result
            if result.method == 0x00:
                compression_method = CompressionMethod.BINARY_SEMANTIC
            elif result.method == 0x01:
                compression_method = CompressionMethod.AURALITE
            elif result.method == 0x02:
                compression_method = CompressionMethod.BRIO
            elif result.method == 0x03:
                compression_method = CompressionMethod.AURA_LITE
            elif result.method == 0xFF:
                compression_method = CompressionMethod.UNCOMPRESSED
            else:
                # Unknown method, use uncompressed
                compression_method = CompressionMethod.UNCOMPRESSED

            payload = bytes([compression_method.value]) + result.compressed_data
            compressed_size = len(payload)

            # Map AURA Heavy method to our method name
            method_name = 'aura_heavy'
            if hasattr(result, 'method'):
                if result.method == 0x00:
                    method_name = 'binary_semantic'
                elif result.method == 0x01:
                    method_name = 'auralite'
                elif result.method == 0x02:
                    method_name = 'brio'
                elif result.method == 0x03:
                    method_name = 'aura_lite'
                elif result.method == 0xFF:
                    method_name = 'uncompressed'

            metadata = {
                'original_size': context.original_size,
                'compressed_size': compressed_size,
                'ratio': context.original_size / compressed_size if compressed_size else float('inf'),
                'method': method_name,
                'aura_heavy_method': result.method if hasattr(result, 'method') else 'unknown',
            }

            can_compress = len(payload) < context.original_size
            return CompressionResult(payload, compression_method, metadata, can_compress)

        except Exception as e:
            # Fallback to uncompressed
            uncompressed = UncompressedStrategy()
            return uncompressed.compress(context)


def create_compression_strategies(
    template_service: Any,
    aura_lite_encoder: Any = None,
    aura_encoder: Any = None,
    tcp_brio_encoder: Any = None,
    aura_heavy_compressor: Any = None,
    enable_aura: bool = True,
) -> List[CompressionStrategyInterface]:
    """
    Factory function to create all available compression strategies

    Args:
        template_service: Template service instance
        aura_lite_encoder: AURA-Lite encoder instance
        aura_encoder: Full BRIO encoder instance
        tcp_brio_encoder: TCP-optimized BRIO encoder instance
        enable_aura: Whether to enable AURA/BRIO methods

    Returns:
        List of compression strategies in priority order
    """
    strategies = []

    # Uncompressed is always available
    strategies.append(UncompressedStrategy())

    # Binary Semantic (requires template service)
    if template_service:
        strategies.append(BinarySemanticStrategy(template_service))

    # BRIO (experimental AURA)
    if enable_aura:
        strategies.append(BrioStrategy(aura_encoder, tcp_brio_encoder))

    # AURA Heavy (hybrid semantic + traditional compression)
    if aura_heavy_compressor:
        strategies.append(AuraHeavyStrategy(aura_heavy_compressor))

    # AURA-Lite
    if aura_lite_encoder:
        strategies.append(AuraLiteStrategy(aura_lite_encoder))

    # AuraLite (fallback)
    if aura_lite_encoder:
        strategies.append(AuraliteStrategy(aura_lite_encoder))

    # AURA-only compression - no standard methods
    # strategies.append(GzipStrategy())
    # strategies.append(Bz2Strategy())
    # strategies.append(LzmaStrategy())

    return strategies