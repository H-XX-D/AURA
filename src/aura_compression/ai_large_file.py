"""Compatibility wrapper for legacy imports.

The AI large-file compressor module was renamed to
``pattern_semantic_large_file``. This shim preserves backward
compatibility for code that still imports ``aura_compression.ai_large_file``.
"""

from .pattern_semantic_large_file import PatternSemanticCompressor

# Backwards-compatible alias kept for callers that expected the old name.
AILargeFileCompressor = PatternSemanticCompressor

__all__ = ["PatternSemanticCompressor", "AILargeFileCompressor"]
