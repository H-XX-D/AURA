#!/usr/bin/env python3
"""Compatibility wrapper for the production hybrid compressor."""

from aura_compression.compressor import (
    ProductionHybridCompressor,
    AuditLogger,
    CompressionMethod,
    test_production_system,
)


if __name__ == "__main__":
    test_production_system()
