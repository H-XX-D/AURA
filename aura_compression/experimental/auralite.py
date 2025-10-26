# Compatibility shim: expose AuraLite under experimental namespace used by tests
from aura_compression.auralite import AuraLiteEncoder, AuraLiteDecoder

__all__ = ["AuraLiteEncoder", "AuraLiteDecoder"]
