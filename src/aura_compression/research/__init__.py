"""Experimental AURA research surfaces.

These APIs are useful for evaluation and local experiments, but they do not
carry the compatibility promise of :mod:`aura_compression.aiwire`.
"""

from ..ai_wire_token import (
    AIWireTokenAIWireSessionDecoder,
    AIWireTokenAIWireSessionEncoder,
    AIWireTokenSessionDecoder,
    AIWireTokenSessionEncoder,
)
from ..brio import BrioDecoder, BrioEncoder
from ..brio_full import BrioDecoder as BrioFullDecoder
from ..brio_full import BrioEncoder as BrioFullEncoder
from ..compressor import ProductionHybridCompressor
from ..cuda_native import CudaNativeBackend
from ..discovery import TemplateDiscoveryEngine
from ..metadata_sidechannel import MetadataSideChannel
from ..ml_algorithm_selector import MLAlgorithmSelector

RESEARCH_API_STABILITY = "experimental"

__all__ = [
    "AIWireTokenAIWireSessionDecoder",
    "AIWireTokenAIWireSessionEncoder",
    "AIWireTokenSessionDecoder",
    "AIWireTokenSessionEncoder",
    "BrioDecoder",
    "BrioEncoder",
    "BrioFullDecoder",
    "BrioFullEncoder",
    "CudaNativeBackend",
    "MetadataSideChannel",
    "MLAlgorithmSelector",
    "ProductionHybridCompressor",
    "RESEARCH_API_STABILITY",
    "TemplateDiscoveryEngine",
]
