#!/usr/bin/env python3
"""
Test ML Algorithm Selector functionality
Tests the machine learning-based algorithm selection for optimal compression performance.
"""

import unittest
import tempfile
import os
import time
from pathlib import Path
from unittest.mock import Mock, patch

from aura_compression.ml_algorithm_selector import (
    MLAlgorithmSelector,
    CompressionMethod,
    CompressionResult,
    MessageFeatures,
    AlgorithmPrediction
)


class TestMLAlgorithmSelector(unittest.TestCase):
    """Test cases for ML Algorithm Selector."""

    def setUp(self):
        """Set up test fixtures."""
        # Create temporary directory for model files
        self.temp_dir = tempfile.mkdtemp()
        self.model_file = Path(self.temp_dir) / "test_ml_model.json"

        # Create selector with learning enabled
        self.selector = MLAlgorithmSelector(
            model_file=str(self.model_file),
            enable_learning=True
        )

    def tearDown(self):
        """Clean up test fixtures."""
        # Clean up temporary files
        if self.model_file.exists():
            self.model_file.unlink()
        os.rmdir(self.temp_dir)

    def test_initialization(self):
        """Test ML selector initialization."""
        self.assertIsNotNone(self.selector.feature_weights)
        self.assertIsNotNone(self.selector.method_stats)
        self.assertIsNotNone(self.selector.performance_history)
        self.assertTrue(self.selector.enable_learning)
        self.assertEqual(self.selector.learning_rate, 0.1)
        self.assertEqual(self.selector.confidence_threshold, 0.7)

    def test_feature_extraction(self):
        """Test feature extraction from messages."""
        # Test with simple text
        message = "Hello world"
        features = self.selector._extract_features(message)

        self.assertIsInstance(features, MessageFeatures)
        self.assertEqual(features.length, len(message))
        self.assertGreaterEqual(features.entropy, 0.0)
        self.assertLessEqual(features.entropy, 8.0)  # Max entropy for ASCII
        self.assertFalse(features.has_numbers)
        self.assertFalse(features.has_special_chars)  # Space is not considered special

        # Test with numbers and special chars
        message2 = "User123@example.com: 42 items"
        features2 = self.selector._extract_features(message2)

        self.assertTrue(features2.has_numbers)
        self.assertTrue(features2.has_special_chars)
        self.assertEqual(features2.word_count, 3)

        # Test with empty message
        features3 = self.selector._extract_features("")
        self.assertEqual(features3.length, 0)
        self.assertEqual(features3.entropy, 0.0)
        self.assertEqual(features3.word_count, 0)

    def test_algorithm_prediction(self):
        """Test algorithm prediction for different message types."""
        # Test with no available methods
        prediction = self.selector.predict_routing_decision("", [])
        self.assertEqual(prediction.method, CompressionMethod.UNCOMPRESSED)
        self.assertEqual(prediction.confidence, 1.0)
        self.assertEqual(prediction.expected_ratio, 1.0)

        # Test with available methods
        methods = [CompressionMethod.BRIO, CompressionMethod.AURALITE, CompressionMethod.UNCOMPRESSED]
        message = "This is a test message with some repetitive text for compression testing."

        prediction = self.selector.predict_routing_decision(message, methods)

        self.assertIn(prediction.method, methods)
        self.assertGreaterEqual(prediction.confidence, 0.0)
        self.assertLessEqual(prediction.confidence, 1.0)
        self.assertGreater(prediction.expected_ratio, 0.0)
        self.assertIsInstance(prediction.reasoning, str)

    def test_routing_decisions(self):
        """Test routing decision predictions."""
        # Test fast-path routing
        structured_message = '{"user_id": 123, "action": "login", "timestamp": 1234567890}'
        methods = [CompressionMethod.FAST_PATH, CompressionMethod.SLOW_PATH]

        prediction = self.selector.predict_routing_decision(structured_message, methods)
        self.assertIn(prediction.method, [CompressionMethod.FAST_PATH, CompressionMethod.SLOW_PATH])

        # Test with metadata
        metadata = {"template_ids": ["login_template"], "function_id": "auth"}
        prediction_with_metadata = self.selector.predict_routing_decision(
            structured_message, methods, metadata
        )
        self.assertIn(prediction_with_metadata.method, methods)

    def test_performance_recording(self):
        """Test recording compression performance for learning."""
        message = "Test message for performance recording"
        method = CompressionMethod.BRIO
        result = CompressionResult(
            method=method,
            original_size=len(message),
            compressed_size=len(message) * 0.6,  # 60% of original size
            compression_time=0.05,
            ratio=1.67
        )

        # Record performance
        initial_history_len = len(self.selector.performance_history)
        self.selector.record_performance(message, method, result)

        # Check that performance was recorded
        self.assertEqual(len(self.selector.performance_history), initial_history_len + 1)

        # Check method stats were updated
        self.assertIn(method, self.selector.method_stats)
        stats = self.selector.method_stats[method]
        self.assertEqual(stats['total_compressions'], 1)
        self.assertAlmostEqual(stats['avg_ratio'], result.ratio)
        self.assertAlmostEqual(stats['avg_time'], result.compression_time)

    def test_method_stats(self):
        """Test getting method statistics."""
        stats = self.selector.get_method_stats()

        self.assertIn('methods', stats)
        self.assertIn('total_samples', stats)
        self.assertIn('model_features', stats)
        self.assertIn('learning_enabled', stats)
        self.assertTrue(stats['learning_enabled'])
        self.assertEqual(stats['total_samples'], len(self.selector.performance_history))

    def test_model_persistence(self):
        """Test saving and loading model."""
        # Add some performance data
        message = "Test message"
        result = CompressionResult(
            method=CompressionMethod.BRIO,
            original_size=len(message),
            compressed_size=50,
            compression_time=0.1,
            ratio=2.0
        )
        self.selector.record_performance(message, CompressionMethod.BRIO, result)

        # Save model
        self.selector.save_model()
        self.assertTrue(self.model_file.exists())

        # Create new selector and load model
        new_selector = MLAlgorithmSelector(
            model_file=str(self.model_file),
            enable_learning=True
        )

        # Check that data was loaded
        self.assertEqual(len(new_selector.performance_history), 1)
        self.assertIn(CompressionMethod.BRIO, new_selector.method_stats)

    def test_learning_disabled(self):
        """Test behavior when learning is disabled."""
        selector_no_learning = MLAlgorithmSelector(
            model_file=str(self.model_file),
            enable_learning=False
        )

        # Record performance - should not update history
        message = "Test message"
        result = CompressionResult(
            method=CompressionMethod.BRIO,
            original_size=len(message),
            compressed_size=50,
            compression_time=0.1,
            ratio=2.0
        )

        initial_history_len = len(selector_no_learning.performance_history)
        selector_no_learning.record_performance(message, CompressionMethod.BRIO, result)

        # History should not change when learning is disabled
        self.assertEqual(len(selector_no_learning.performance_history), initial_history_len)

    def test_method_scoring(self):
        """Test method scoring based on features."""
        # Use features that should be favorable for BRIO (low entropy, good compression potential)
        features = MessageFeatures(
            length=100,
            entropy=2.0,  # Lower entropy is better for BRIO
            has_numbers=True,
            has_special_chars=True,
            word_count=10,
            avg_word_length=8.0,
            compression_potential=0.8,  # High compression potential
            pattern_score=0.9,  # Good pattern score
            fast_path_potential=0.6,
            metadata_size_estimate=150,
            template_match_score=0.5,
            pattern_semantic_score=0.7,
            semantic_chunks=8,
            ai_patterns_found=5,
            semantic_complexity=0.3,
            binary_semantic_potential=0.6,
            structured_data_score=0.8,
            repetitive_pattern_score=0.7
        )

        # Test scoring for BRIO (should be good for this type of content)
        score = self.selector._score_method(CompressionMethod.BRIO, features)

        self.assertIn('total_score', score)
        self.assertIn('expected_ratio', score)
        self.assertIn('feature_match', score)
        self.assertIn('performance_score', score)

        # Scores should be reasonable (BRIO should score well for low-entropy content)
        self.assertGreaterEqual(score['total_score'], 0.0)
        self.assertGreater(score['expected_ratio'], 0.0)

    def test_fast_path_viability(self):
        """Test fast-path routing viability assessment."""
        # Test with structured data (should be viable)
        features = MessageFeatures(
            length=200,
            entropy=3.0,
            has_numbers=True,
            has_special_chars=True,
            word_count=5,
            avg_word_length=6.0,
            compression_potential=0.8,
            pattern_score=0.9,
            fast_path_potential=0.8,
            metadata_size_estimate=120,
            template_match_score=0.7,
            pattern_semantic_score=0.6,
            semantic_chunks=12,
            ai_patterns_found=4,
            semantic_complexity=0.4,
            binary_semantic_potential=0.7,
            structured_data_score=0.9,
            repetitive_pattern_score=0.5
        )

        viable = self.selector._is_fast_path_viable(features)
        self.assertTrue(viable)

        # Test with unstructured data (should not be viable)
        features2 = MessageFeatures(
            length=1000,
            entropy=7.0,
            has_numbers=False,
            has_special_chars=False,
            word_count=200,
            avg_word_length=4.0,
            compression_potential=0.2,
            pattern_score=0.1,
            fast_path_potential=0.1,
            metadata_size_estimate=400,
            template_match_score=0.0,
            pattern_semantic_score=0.1,
            semantic_chunks=50,
            ai_patterns_found=1,
            semantic_complexity=0.9,
            binary_semantic_potential=0.1,
            structured_data_score=0.1,
            repetitive_pattern_score=0.1
        )

        viable2 = self.selector._is_fast_path_viable(features2)
        self.assertFalse(viable2)

    def test_cache_detection(self):
        """Test cache usage detection."""
        # Test with cache key (should use cache)
        metadata = {"cache_key": "abcdefghijk123", "message_hash": "def456"}  # Longer than 10 chars
        should_cache = self.selector._should_use_cache(metadata)
        self.assertTrue(should_cache)

        # Test without cache key (should not use cache)
        metadata2 = {"some_other_field": "value"}
        should_cache2 = self.selector._should_use_cache(metadata2)
        self.assertFalse(should_cache2)

    def test_thread_safety(self):
        """Test thread-safe operations."""
        import threading
        import concurrent.futures

        # Test concurrent performance recording
        def record_performance(worker_id):
            message = f"Worker {worker_id} message"
            result = CompressionResult(
                method=CompressionMethod.BRIO,
                original_size=len(message),
                compressed_size=len(message) * 0.5,
                compression_time=0.01 * worker_id,
                ratio=2.0
            )
            self.selector.record_performance(message, CompressionMethod.BRIO, result)

        # Run multiple threads
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(record_performance, i) for i in range(10)]
            concurrent.futures.wait(futures)

        # Check that all recordings were captured
        self.assertEqual(len(self.selector.performance_history), 10)

    def test_model_update(self):
        """Test model weight updates based on performance."""
        # Add multiple performance records
        for i in range(20):
            message = f"Test message {i} with some repetitive content for learning"
            result = CompressionResult(
                method=CompressionMethod.BRIO,
                original_size=len(message),
                compressed_size=len(message) * 0.6,
                compression_time=0.05,
                ratio=1.67
            )
            self.selector.record_performance(message, CompressionMethod.BRIO, result)

        # Force model update
        self.selector._update_model()

        # Check that weights were updated (should have some non-zero values)
        weights = self.selector.feature_weights.get(CompressionMethod.BRIO, {})
        self.assertTrue(any(abs(v) > 0.01 for v in weights.values() if isinstance(v, (int, float))))


if __name__ == '__main__':
    unittest.main()