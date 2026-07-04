"""
AURA Compression - AI-Optimized Hybrid Compression Protocol

Copyright (c) 2025 Todd Hendricks
Licensed under Apache License 2.0
"""

__version__ = "2.0.1"
__author__ = "Todd Hendricks"
__license__ = "Apache 2.0"

from .acceleration import ConversationAccelerator, ConversationSession, PlatformWideAccelerator
from .ai_wire import (
    AI_WIRE_DEFAULT_LEVEL,
    AI_WIRE_DICTIONARY_FNV1A64,
    AI_WIRE_DICTIONARY_SHA256,
    AI_WIRE_FLUSH_MODE,
    AI_WIRE_HANDSHAKE_SCHEMA,
    AI_WIRE_NEGOTIATION_SCHEMA,
    AI_WIRE_PROTOCOL,
    AI_WIRE_STATIC_DICTIONARY,
    AI_WIRE_SUPPORTED_VERSIONS,
    AI_WIRE_VERSION,
    AIWireFrame,
    AIWireHandshake,
    AIWireHandshakeError,
    AIWireNativeError,
    AIWireNativeStatus,
    AIWireNegotiation,
    AIWireSessionDecoder,
    AIWireSessionEncoder,
    AIWireStats,
    aiwire_native_status,
    build_ai_wire_messages,
    build_aiwire_handshake,
    build_structured_ai_messages,
    compress_ai_wire_frames,
    decode_ai_wire_message,
    decompress_ai_wire_frames,
    encode_ai_wire_message,
    negotiate_aiwire_handshake,
)
from .audit import AuditLogger, AuditLogType, get_audit_logger, reset_audit_logger
from .background_workers import (
    TemplateDiscoveryWorker,
    start_discovery_worker,
    stop_discovery_worker,
)
from .brio import BrioCompressed, BrioDecoder, BrioDecompressed, BrioEncoder
from .brio_full import BrioCompressed as BrioFullCompressed
from .brio_full import BrioDecoder as BrioFullDecoder
from .brio_full import BrioDecompressed as BrioFullDecompressed
from .brio_full import BrioEncoder as BrioFullEncoder
from .compressor import ProductionHybridCompressor
from .cuda_native import (
    CudaNativeBackend,
    CudaNativeStatus,
    cpu_lz_match_candidates,
    cpu_rolling_hash3,
    cpu_shannon_entropy,
)
from .discovery import TemplateCandidate, TemplateDiscoveryEngine
from .enums import CompressionMethod
from .function_parser import AItoAIOrchestrator, FunctionCall, FunctionCallParser
from .metadata import FastPathClassifier, MetadataExtractor, MetadataRouter, SecurityScreener
from .metadata_sidechannel import (
    MessageCategory,
    MessageMetadata,
    MetadataSideChannel,
    SecurityLevel,
)
from .ml_algorithm_selector import MLAlgorithmSelector
from .router import LoadBalancer, ProductionRouter, RoutingMetrics
from .streaming_harness import StreamingHarness
from .templates import TemplateLibrary

__all__ = [
    # Core compression
    "ProductionHybridCompressor",
    "CompressionMethod",
    "TemplateLibrary",
    # Audit logging
    "AuditLogger",
    "AuditLogType",
    "get_audit_logger",
    "reset_audit_logger",
    # Metadata fast-path
    "MetadataExtractor",
    "FastPathClassifier",
    "SecurityScreener",
    "MetadataRouter",
    # Template discovery
    "TemplateDiscoveryEngine",
    "TemplateCandidate",
    "TemplateDiscoveryWorker",
    "start_discovery_worker",
    "stop_discovery_worker",
    # Conversation acceleration
    "ConversationAccelerator",
    "ConversationSession",
    "PlatformWideAccelerator",
    # AI-to-AI function parsing
    "FunctionCallParser",
    "FunctionCall",
    "AItoAIOrchestrator",
    # Production routing
    "ProductionRouter",
    "LoadBalancer",
    "RoutingMetrics",
    "StreamingHarness",
    # Metadata sidechannel
    "MetadataSideChannel",
    "MessageCategory",
    "MessageMetadata",
    "SecurityLevel",
    # BRIO entropy coding
    "BrioEncoder",
    "BrioCompressed",
    "BrioDecoder",
    "BrioDecompressed",
    "BrioFullEncoder",
    "BrioFullCompressed",
    "BrioFullDecoder",
    "BrioFullDecompressed",
    # Machine learning algorithm selection
    "MLAlgorithmSelector",
    # Optional native CUDA backend
    "CudaNativeBackend",
    "CudaNativeStatus",
    "cpu_lz_match_candidates",
    "cpu_rolling_hash3",
    "cpu_shannon_entropy",
    # AI-to-AI wire codec
    "AI_WIRE_DEFAULT_LEVEL",
    "AI_WIRE_DICTIONARY_FNV1A64",
    "AI_WIRE_DICTIONARY_SHA256",
    "AI_WIRE_FLUSH_MODE",
    "AI_WIRE_HANDSHAKE_SCHEMA",
    "AI_WIRE_NEGOTIATION_SCHEMA",
    "AI_WIRE_PROTOCOL",
    "AI_WIRE_STATIC_DICTIONARY",
    "AI_WIRE_SUPPORTED_VERSIONS",
    "AI_WIRE_VERSION",
    "AIWireFrame",
    "AIWireHandshake",
    "AIWireHandshakeError",
    "AIWireNativeError",
    "AIWireNativeStatus",
    "AIWireNegotiation",
    "AIWireSessionDecoder",
    "AIWireSessionEncoder",
    "AIWireStats",
    "aiwire_native_status",
    "build_ai_wire_messages",
    "build_structured_ai_messages",
    "build_aiwire_handshake",
    "compress_ai_wire_frames",
    "decode_ai_wire_message",
    "decompress_ai_wire_frames",
    "encode_ai_wire_message",
    "negotiate_aiwire_handshake",
]
