"""
AURA Compression - AI-Optimized Hybrid Compression Protocol

Patent Claims Implementation:
- Claims 1-20: Core compression (hybrid templates + LZ77 + rANS)
- Claims 21-30: Metadata side-channel (fast-path processing)
- Claims 31-31E: Conversation acceleration (pattern caching)
- Claims 32-35: Compliance architecture (4-log system)

Copyright (c) 2025 Todd Hendricks
Licensed under Apache License 2.0
Patent Pending - Application No. 19/366,538
"""

__version__ = "1.0.0"
__author__ = "Todd Hendricks"
__license__ = "Apache 2.0"
__patent__ = "US Patent Application No. 19/366,538"

from .compressor import ProductionHybridCompressor, CompressionMethod
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

__all__ = [
    # Core compression (Claims 1-20)
    "ProductionHybridCompressor",
    "CompressionMethod",
    "TemplateLibrary",

    # Audit logging (Claims 2, 11, 32-35)
    "AuditLogger",
    "AuditLogType",
    "get_audit_logger",
    "reset_audit_logger",

    # Metadata fast-path (Claims 21-30)
    "MetadataExtractor",
    "FastPathClassifier",
    "SecurityScreener",
    "MetadataRouter",

    # Template discovery (Claims 3, 15-18)
    "TemplateDiscoveryEngine",
    "TemplateCandidate",
    "TemplateDiscoveryWorker",
    "TemplateSyncService",
    "start_discovery_worker",
    "stop_discovery_worker",

    # Conversation acceleration (Claims 31-31E)
    "ConversationAccelerator",
    "ConversationSession",
    "PlatformWideAccelerator",

    # AI-to-AI function parsing (Claim 19)
    "FunctionCallParser",
    "FunctionCall",
    "AItoAIOrchestrator",

    # Production routing (Claims 20, 26, 28)
    "ProductionRouter",
    "LoadBalancer",
    "RoutingMetrics",
    "StreamingHarness",
]
