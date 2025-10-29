#!/usr/bin/env python3
"""
Unit tests for compression strategy pattern implementation
Tests all compression strategies and their interactions
"""
import unittest
from unittest.mock import Mock, MagicMock
from typing import Dict, Any

from .compression_strategy import (
    CompressionStrategy,
    UncompressedStrategy,
    BinarySemanticStrategy,
    BrioStrategy,
    AuraLiteStrategy,
    AuraliteStrategy,
    CompressionContext,
    CompressionResult,
    create_compression_strategies,
)
from .compressor import CompressionMethod


class TestCompressionResult(unittest.TestCase):
    """Test CompressionResult class"""

    def test_compression_result_creation(self):
        """Test basic CompressionResult creation"""
        payload = b"test_payload"
        method = CompressionMethod.UNCOMPRESSED
        metadata = {"ratio": 2.0}

        result = CompressionResult(payload, method, metadata)

        self.assertEqual(result.payload, payload)
        self.assertEqual(result.method, method)
        self.assertEqual(result.metadata, metadata)
        self.assertTrue(result.can_compress)

    def test_compression_ratio_calculation(self):
        """Test compression ratio calculation"""
        payload = b"short"
        metadata = {"original_size": 10, "compressed_size": 5}

        result = CompressionResult(payload, CompressionMethod.UNCOMPRESSED, metadata)

        # Should calculate ratio from metadata if available
        self.assertEqual(result.compression_ratio, 2.0)

    def test_compression_ratio_fallback(self):
        """Test compression ratio fallback to payload length"""
        payload = b"short_payload"
        metadata = {"original_size": 20}

        result = CompressionResult(payload, CompressionMethod.UNCOMPRESSED, metadata)

        # Should use payload length as compressed_size
        self.assertEqual(result.compression_ratio, 20 / len(payload))


class TestCompressionContext(unittest.TestCase):
    """Test CompressionContext class"""

    def test_context_creation_basic(self):
        """Test basic context creation"""
        text = "test text"
        original_size = 9

        context = CompressionContext(text, original_size)

        self.assertEqual(context.text, text)
        self.assertEqual(context.original_size, original_size)
        self.assertIsNone(context.template_match)
        self.assertEqual(context.template_spans, [])
        self.assertTrue(context.enable_aura)
        self.assertEqual(context.tcp_brio_threshold, 2000)

    def test_context_creation_with_options(self):
        """Test context creation with all options"""
        text = "test text"
        original_size = 9
        template_match = Mock()
        template_spans = [Mock()]
        enable_aura = False
        tcp_threshold = 1000

        context = CompressionContext(
            text, original_size, template_match, template_spans,
            enable_aura, tcp_threshold
        )

        self.assertEqual(context.text, text)
        self.assertEqual(context.original_size, original_size)
        self.assertEqual(context.template_match, template_match)
        self.assertEqual(context.template_spans, template_spans)
        self.assertFalse(context.enable_aura)
        self.assertEqual(context.tcp_brio_threshold, tcp_threshold)


class TestUncompressedStrategy(unittest.TestCase):
    """Test UncompressedStrategy"""

    def setUp(self):
        self.strategy = UncompressedStrategy()

    def test_get_method(self):
        """Test method getter"""
        self.assertEqual(self.strategy.get_method(), CompressionMethod.UNCOMPRESSED)

    def test_can_compress_always_true(self):
        """Test that uncompressed can always compress"""
        context = CompressionContext("test", 4)
        self.assertTrue(self.strategy.can_compress(context))

    def test_compress_basic(self):
        """Test basic compression"""
        text = "hello"
        context = CompressionContext(text, len(text))

        result = self.strategy.compress(context)

        self.assertEqual(result.method, CompressionMethod.UNCOMPRESSED)
        self.assertTrue(result.can_compress)
        self.assertEqual(result.payload[0], CompressionMethod.UNCOMPRESSED.value)
        self.assertEqual(result.payload[1:], text.encode('utf-8'))

        # Check metadata
        self.assertEqual(result.metadata['original_size'], len(text))
        self.assertEqual(result.metadata['method'], 'uncompressed')
        self.assertEqual(result.metadata['reason'], 'fallback_candidate')
        self.assertFalse(result.metadata['fast_path_candidate'])


class TestBinarySemanticStrategy(unittest.TestCase):
    """Test BinarySemanticStrategy"""

    def setUp(self):
        self.template_service = Mock()
        self.strategy = BinarySemanticStrategy(self.template_service)

    def test_get_method(self):
        """Test method getter"""
        self.assertEqual(self.strategy.get_method(), CompressionMethod.BINARY_SEMANTIC)

    def test_can_compress_with_template(self):
        """Test can compress when template match exists"""
        template_match = Mock()
        context = CompressionContext("test", 4, template_match=template_match)

        self.assertTrue(self.strategy.can_compress(context))

    def test_can_compress_without_template(self):
        """Test cannot compress without template match"""
        context = CompressionContext("test", 4)

        self.assertFalse(self.strategy.can_compress(context))

    def test_compress_successful(self):
        """Test successful compression"""
        template_match = Mock()
        template_match.template_id = "test_template"
        template_match.slots = {"key": "value"}

        context = CompressionContext("test text", 9, template_match=template_match)

        # Mock template service - return smaller data than original
        binary_data = b"comp"  # 4 bytes vs 9 original
        self.template_service.compress_with_template.return_value = binary_data

        result = self.strategy.compress(context)

        self.assertEqual(result.method, CompressionMethod.BINARY_SEMANTIC)
        self.assertTrue(result.can_compress)
        self.assertEqual(result.payload[0], CompressionMethod.BINARY_SEMANTIC.value)
        self.assertEqual(result.payload[1:], binary_data)

        # Check metadata
        self.assertEqual(result.metadata['template_id'], "test_template")
        self.assertEqual(result.metadata['template_ids'], ["test_template"])
        self.assertEqual(result.metadata['slot_count'], 1)

    def test_compress_failure_fallback(self):
        """Test compression failure falls back to uncompressed"""
        template_match = Mock()
        context = CompressionContext("test", 4, template_match=template_match)

        # Mock template service to raise exception
        self.template_service.compress_with_template.side_effect = Exception("Compression failed")

        result = self.strategy.compress(context)

        # Should fallback to uncompressed
        self.assertEqual(result.method, CompressionMethod.UNCOMPRESSED)
        self.assertEqual(result.payload[0], CompressionMethod.UNCOMPRESSED.value)


class TestBrioStrategy(unittest.TestCase):
    """Test BrioStrategy"""

    def setUp(self):
        self.aura_encoder = Mock()
        self.tcp_brio_encoder = Mock()
        self.strategy = BrioStrategy(self.aura_encoder, self.tcp_brio_encoder)

    def test_get_method(self):
        """Test method getter"""
        self.assertEqual(self.strategy.get_method(), CompressionMethod.BRIO)

    def test_can_compress_with_encoders(self):
        """Test can compress when encoders are available"""
        context = CompressionContext("test", 4)
        self.assertTrue(self.strategy.can_compress(context))

    def test_can_compress_without_encoders(self):
        """Test cannot compress without encoders"""
        strategy = BrioStrategy()
        context = CompressionContext("test", 4)
        self.assertFalse(strategy.can_compress(context))

    def test_can_compress_aura_disabled(self):
        """Test cannot compress when AURA is disabled"""
        context = CompressionContext("test", 4, enable_aura=False)
        self.assertFalse(self.strategy.can_compress(context))

    def test_compress_tcp_brio_small_message(self):
        """Test compression using TCP BRIO for small messages"""
        context = CompressionContext("small message", 13, tcp_brio_threshold=20)

        # Mock TCP BRIO encoder
        compressed = Mock()
        compressed.payload = b"tcp_compressed"
        compressed.metadata = []
        compressed.tokens = []
        self.tcp_brio_encoder.compress.return_value = compressed

        result = self.strategy.compress(context)

        self.assertEqual(result.method, CompressionMethod.BRIO)
        self.assertEqual(result.payload[0], CompressionMethod.BRIO.value)
        self.assertEqual(result.payload[1:], b"tcp_compressed")

    def test_compress_aura_large_message(self):
        """Test compression using full AURA for large messages"""
        context = CompressionContext("large message that exceeds threshold", 35, tcp_brio_threshold=20)

        # Mock AURA encoder
        compressed = Mock()
        compressed.payload = b"aura_compressed"
        compressed.metadata = []
        compressed.tokens = []
        self.aura_encoder.compress.return_value = compressed

        result = self.strategy.compress(context)

        self.assertEqual(result.method, CompressionMethod.BRIO)
        self.assertEqual(result.payload[0], CompressionMethod.BRIO.value)
        self.assertEqual(result.payload[1:], b"aura_compressed")

    def test_compress_failure_fallback(self):
        """Test compression failure falls back to uncompressed"""
        context = CompressionContext("test", 4)

        # Mock encoder to raise exception
        self.tcp_brio_encoder.compress.side_effect = Exception("Compression failed")

        result = self.strategy.compress(context)

        # Should fallback to uncompressed
        self.assertEqual(result.method, CompressionMethod.UNCOMPRESSED)


class TestAuraLiteStrategy(unittest.TestCase):
    """Test AuraLiteStrategy"""

    def setUp(self):
        self.encoder = Mock()
        self.strategy = AuraLiteStrategy(self.encoder)

    def test_get_method(self):
        """Test method getter"""
        self.assertEqual(self.strategy.get_method(), CompressionMethod.AURA_LITE)

    def test_can_compress_with_encoder(self):
        """Test can compress when encoder is available"""
        context = CompressionContext("test", 4)
        self.assertTrue(self.strategy.can_compress(context))

    def test_can_compress_without_encoder(self):
        """Test cannot compress without encoder"""
        strategy = AuraLiteStrategy()
        context = CompressionContext("test", 4)
        self.assertFalse(strategy.can_compress(context))

    def test_compress_successful(self):
        """Test successful compression"""
        context = CompressionContext("test text", 9)

        # Mock encoder
        encoded = Mock()
        encoded.payload = b"encoded_data"
        encoded.template_ids = ["template1", "template2"]
        self.encoder.encode.return_value = encoded

        result = self.strategy.compress(context)

        self.assertEqual(result.method, CompressionMethod.AURA_LITE)
        self.assertEqual(result.payload[0], CompressionMethod.AURA_LITE.value)
        self.assertEqual(result.payload[1:], b"encoded_data")

        # Check metadata
        self.assertEqual(result.metadata['template_ids'], ["template1", "template2"])
        self.assertEqual(result.metadata['template_id'], "template1")
        self.assertTrue(result.metadata['fast_path_candidate'])

    def test_compress_template_optimization(self):
        """Test template heavy optimization"""
        template_match = Mock()
        template_match.template_id = "heavy_template"
        context = CompressionContext("test text", 9, template_match=template_match)

        # Mock encoder - first call returns large payload, second returns smaller
        encoded_with_template = Mock()
        encoded_with_template.payload = b"very_long_encoded_data_with_template"
        encoded_with_template.template_ids = ["heavy_template"]

        encoded_without_template = Mock()
        encoded_without_template.payload = b"short_encoded"
        encoded_without_template.template_ids = []

        self.encoder.encode.side_effect = [encoded_with_template, encoded_without_template]

        result = self.strategy.compress(context)

        # Should use the optimized version without template
        self.assertEqual(result.payload[1:], b"short_encoded")
        self.assertEqual(result.metadata['template_ids'], [])

    def test_compress_failure_fallback(self):
        """Test compression failure falls back to uncompressed"""
        context = CompressionContext("test", 4)

        # Mock encoder to raise exception
        self.encoder.encode.side_effect = Exception("Encoding failed")

        result = self.strategy.compress(context)

        # Should fallback to uncompressed
        self.assertEqual(result.method, CompressionMethod.UNCOMPRESSED)


class TestAuraliteStrategy(unittest.TestCase):
    """Test AuraliteStrategy"""

    def setUp(self):
        self.encoder = Mock()
        self.strategy = AuraliteStrategy(self.encoder)

    def test_get_method(self):
        """Test method getter"""
        self.assertEqual(self.strategy.get_method(), CompressionMethod.AURALITE)

    def test_can_compress_with_encoder(self):
        """Test can compress when encoder is available"""
        context = CompressionContext("test", 4)
        self.assertTrue(self.strategy.can_compress(context))

    def test_can_compress_without_encoder(self):
        """Test cannot compress without encoder"""
        strategy = AuraliteStrategy()
        context = CompressionContext("test", 4)
        self.assertFalse(strategy.can_compress(context))

    def test_compress_successful(self):
        """Test successful compression"""
        context = CompressionContext("test text", 9)

        # Mock encoder
        encoded = Mock()
        encoded.payload = b"encoded_data"
        encoded.template_ids = []
        self.encoder.encode.return_value = encoded

        result = self.strategy.compress(context)

        self.assertEqual(result.method, CompressionMethod.AURALITE)
        self.assertEqual(result.payload[0], CompressionMethod.AURALITE.value)
        self.assertEqual(result.payload[1:], b"encoded_data")

        # Check metadata
        self.assertEqual(result.metadata['method'], 'auralite')
        self.assertEqual(result.metadata['reason'], 'no_template')
        self.assertFalse(result.metadata['fast_path_candidate'])

    def test_compress_failure_fallback(self):
        """Test compression failure falls back to uncompressed"""
        context = CompressionContext("test", 4)

        # Mock encoder to raise exception
        self.encoder.encode.side_effect = Exception("Encoding failed")

        result = self.strategy.compress(context)

        # Should fallback to uncompressed
        self.assertEqual(result.method, CompressionMethod.UNCOMPRESSED)


class TestCreateCompressionStrategies(unittest.TestCase):
    """Test create_compression_strategies factory function"""

    def test_create_all_strategies(self):
        """Test creating all strategies with all dependencies"""
        template_service = Mock()
        aura_lite_encoder = Mock()
        aura_encoder = Mock()
        tcp_brio_encoder = Mock()

        strategies = create_compression_strategies(
            template_service=template_service,
            aura_lite_encoder=aura_lite_encoder,
            aura_encoder=aura_encoder,
            tcp_brio_encoder=tcp_brio_encoder,
            enable_aura=True,
        )

        # Should have 5 strategies
        self.assertEqual(len(strategies), 5)

        # Check order and types
        self.assertIsInstance(strategies[0], UncompressedStrategy)
        self.assertIsInstance(strategies[1], BinarySemanticStrategy)
        self.assertIsInstance(strategies[2], BrioStrategy)
        self.assertIsInstance(strategies[3], AuraLiteStrategy)
        self.assertIsInstance(strategies[4], AuraliteStrategy)

    def test_create_minimal_strategies(self):
        """Test creating strategies with minimal dependencies"""
        strategies = create_compression_strategies(
            template_service=None,
            aura_lite_encoder=None,
            aura_encoder=None,
            tcp_brio_encoder=None,
            enable_aura=False,
        )

        # Should only have uncompressed
        self.assertEqual(len(strategies), 1)
        self.assertIsInstance(strategies[0], UncompressedStrategy)

    def test_create_partial_strategies(self):
        """Test creating strategies with some dependencies"""
        template_service = Mock()
        aura_lite_encoder = Mock()

        strategies = create_compression_strategies(
            template_service=template_service,
            aura_lite_encoder=aura_lite_encoder,
            aura_encoder=None,
            tcp_brio_encoder=None,
            enable_aura=False,
        )

        # Should have uncompressed, binary semantic, aura lite, auralite
        self.assertEqual(len(strategies), 4)
        self.assertIsInstance(strategies[0], UncompressedStrategy)
        self.assertIsInstance(strategies[1], BinarySemanticStrategy)
        self.assertIsInstance(strategies[2], AuraLiteStrategy)
        self.assertIsInstance(strategies[3], AuraliteStrategy)


if __name__ == '__main__':
    unittest.main()