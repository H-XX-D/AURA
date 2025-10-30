"""End-to-end scenarios covering human→AI and AI→AI style messages."""

import pytest
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'src' / 'python'))

from aura_compression.compressor import ProductionHybridCompressor


def test_human_to_ai_message_compression():
    """Test that human-to-AI messages can be compressed and decompressed."""
    compressor = ProductionHybridCompressor(enable_aura=True)
    message = "Can you help me debug this issue?"

    compressed, method, metadata = compressor.compress(message)
    decompressed = compressor.decompress(compressed)

    assert decompressed == message
    assert len(compressed) > 0


def test_ai_to_ai_message_compression():
    """Test that AI-to-AI messages can be compressed and decompressed."""
    compressor = ProductionHybridCompressor(enable_aura=True)
    message = "I don't have access to your calendar."

    compressed, method, metadata = compressor.compress(message)
    decompressed = compressor.decompress(compressed)

    assert decompressed == message
    assert len(compressed) > 0
