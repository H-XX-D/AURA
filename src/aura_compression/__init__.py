"""
AURA Compression - AI-Optimized Hybrid Compression Protocol

Copyright (c) 2025 Todd Hendricks
Licensed under Apache License 2.0
"""

__version__ = "2.0.1"
__author__ = "Todd Hendricks"
__license__ = "Apache 2.0"

from .compressor import ProductionHybridCompressor
from .enums import CompressionMethod
from .templates import TemplateLibrary
from .audit import AuditLogger, AuditLogType, get_audit_logger, reset_audit_logger
from .metadata import MetadataExtractor, FastPathClassifier, SecurityScreener, MetadataRouter
from .discovery import TemplateDiscoveryEngine, TemplateCandidate
from .acceleration import ConversationAccelerator, ConversationSession, PlatformWideAccelerator
from .background_workers import (
    TemplateDiscoveryWorker,
    TemplateSyncService,
    start_discovery_worker,
    stop_discovery_worker,
)
from .function_parser import FunctionCallParser, FunctionCall, AItoAIOrchestrator
from .router import ProductionRouter, LoadBalancer, RoutingMetrics
from .streaming_harness import StreamingHarness
from .metadata_sidechannel import MetadataSideChannel, MessageCategory, MessageMetadata, SecurityLevel
from .brio import BrioEncoder, BrioCompressed, BrioDecoder, BrioDecompressed
from .brio_full import BrioEncoder as BrioFullEncoder, BrioCompressed as BrioFullCompressed, BrioDecoder as BrioFullDecoder, BrioDecompressed as BrioFullDecompressed
from .ml_algorithm_selector import MLAlgorithmSelector

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
    "TemplateSyncService",
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
]
