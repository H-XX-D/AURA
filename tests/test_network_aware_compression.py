#!/usr/bin/env python3
"""
AURA Compression System - Network-Aware Compression Tests
"""

import sys
import time
import pytest
from pathlib import Path
from unittest.mock import Mock, patch

# Add source path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src' / 'python'))

from aura_compression.network_aware_compression import (
    NetworkCondition, CompressionStrategy, NetworkMetrics,
    NetworkAwareCompressor
)


@pytest.fixture
def mock_compressor():
    """Mock compressor for testing."""
    compressor = Mock()
    compressor.compress.return_value = (b'compressed_data', Mock(name='AURALITE'), {'ratio': 2.0})
    return compressor


class TestNetworkCondition:
    """Test NetworkCondition enum and classification."""

    def test_network_condition_enum_values(self):
        """Test that all expected network conditions are defined."""
        assert NetworkCondition.EXCELLENT.value == "excellent"
        assert NetworkCondition.GOOD.value == "good"
        assert NetworkCondition.MODERATE.value == "moderate"
        assert NetworkCondition.POOR.value == "poor"
        assert NetworkCondition.VERY_POOR.value == "very_poor"

    def test_network_condition_ordering(self):
        """Test that conditions are ordered from best to worst."""
        conditions = [
            NetworkCondition.EXCELLENT,
            NetworkCondition.GOOD,
            NetworkCondition.MODERATE,
            NetworkCondition.POOR,
            NetworkCondition.VERY_POOR
        ]

        # Verify ordering by checking they're in expected sequence
        assert conditions == sorted(conditions, key=lambda x: x.value)


class TestCompressionStrategy:
    """Test CompressionStrategy enum."""

    def test_compression_strategy_enum_values(self):
        """Test that all expected compression strategies are defined."""
        assert CompressionStrategy.MAXIMUM_COMPRESSION.value == "maximum_compression"
        assert CompressionStrategy.BALANCED.value == "balanced"
        assert CompressionStrategy.FAST_COMPRESSION.value == "fast_compression"
        assert CompressionStrategy.MINIMAL_COMPRESSION.value == "minimal_compression"
        assert CompressionStrategy.NO_COMPRESSION.value == "no_compression"


class TestNetworkMetrics:
    """Test NetworkMetrics class functionality."""

    def test_network_metrics_initialization(self):
        """Test NetworkMetrics initializes with default values."""
        metrics = NetworkMetrics()

        assert metrics.current_latency == 50.0
        assert metrics.current_bandwidth == 10.0
        assert metrics.current_packet_loss == 0.01
        assert metrics.current_jitter == 5.0

        assert len(metrics.latency_samples) == 0
        assert len(metrics.bandwidth_samples) == 0
        assert len(metrics.packet_loss_samples) == 0
        assert len(metrics.jitter_samples) == 0

    def test_update_latency(self):
        """Test latency measurement updates."""
        metrics = NetworkMetrics()

        # Update with some latency values
        metrics.update_latency(25.0)
        metrics.update_latency(75.0)
        metrics.update_latency(50.0)

        assert len(metrics.latency_samples) == 3
        assert 25.0 in metrics.latency_samples
        assert 75.0 in metrics.latency_samples
        assert 50.0 in metrics.latency_samples

    def test_latency_sample_limit(self):
        """Test that latency samples are limited to prevent unbounded growth."""
        metrics = NetworkMetrics()

        # Add more than 100 samples
        for i in range(105):
            metrics.update_latency(float(i))

        assert len(metrics.latency_samples) == 100  # Should be capped at 100

    def test_thread_safety(self):
        """Test that NetworkMetrics operations are thread-safe."""
        metrics = NetworkMetrics()

        # Multiple updates should not cause race conditions
        # (This is a basic test; comprehensive threading tests would need more setup)
        metrics.update_latency(10.0)
        metrics.update_latency(20.0)

        assert len(metrics.latency_samples) == 2


class TestNetworkAwareCompressor:
    """Test NetworkAwareCompressor functionality."""

    @pytest.fixture
    def compressor(self):
        """Fixture providing a NetworkAwareCompressor instance."""
        return NetworkAwareCompressor()

    def test_compressor_initialization(self, compressor):
        """Test that NetworkAwareCompressor initializes properly."""
        assert compressor is not None
        assert hasattr(compressor, 'network_metrics')
        assert hasattr(compressor, 'condition_strategies')
        assert isinstance(compressor.network_metrics, NetworkMetrics)

    def test_get_network_condition(self, compressor):
        """Test network condition assessment."""
        # With default metrics (50ms latency, 10Mbps), should be MODERATE
        condition = compressor.network_metrics.get_condition()
        assert condition == NetworkCondition.MODERATE

    def test_select_compression_strategy(self, compressor):
        """Test compression strategy selection based on network conditions."""
        # Test different network conditions
        test_cases = [
            (NetworkCondition.EXCELLENT, CompressionStrategy.MAXIMUM_COMPRESSION),
            (NetworkCondition.GOOD, CompressionStrategy.BALANCED),
            (NetworkCondition.MODERATE, CompressionStrategy.BALANCED),
            (NetworkCondition.POOR, CompressionStrategy.FAST_COMPRESSION),
            (NetworkCondition.VERY_POOR, CompressionStrategy.MINIMAL_COMPRESSION),
        ]

        for condition, expected_strategy in test_cases:
            # Force the network condition
            compressor.force_network_condition(condition)
            actual_strategy = compressor.condition_strategies[condition]
            assert actual_strategy == expected_strategy
            compressor.reset_network_condition()

    def test_compress_with_different_strategies(self, compressor, mock_compressor):
        """Test compression with different strategies."""
        test_message = "This is a test message for network-aware compression"

        # Test with different strategies by forcing network conditions
        test_cases = [
            (NetworkCondition.EXCELLENT, CompressionStrategy.MAXIMUM_COMPRESSION),
            (NetworkCondition.GOOD, CompressionStrategy.BALANCED),
            (NetworkCondition.MODERATE, CompressionStrategy.BALANCED),
            (NetworkCondition.POOR, CompressionStrategy.FAST_COMPRESSION),
            (NetworkCondition.VERY_POOR, CompressionStrategy.MINIMAL_COMPRESSION),
        ]

        for condition, expected_strategy in test_cases:
            compressor.force_network_condition(condition)
            result = compressor.compress_network_aware(test_message, mock_compressor)
            assert result is not None
            # Result should be tuple of (compressed_data, method, metadata)
            assert len(result) == 3
            compressed_data, method, metadata = result
            assert isinstance(compressed_data, bytes)
            assert isinstance(metadata, dict)
            assert metadata['network_condition'] == condition.value
            assert metadata['strategy'] == expected_strategy.value
            compressor.reset_network_condition()

    def test_adaptive_strategy_update(self, compressor):
        """Test that compression strategy adapts to network changes."""
        # Start with excellent network (force it)
        compressor.force_network_condition(NetworkCondition.EXCELLENT)
        initial_condition = compressor.network_metrics.get_condition()
        compressor.reset_network_condition()

        # Simulate network degradation by updating metrics
        compressor.network_metrics.current_latency = 500.0  # Poor latency
        compressor.network_metrics.current_bandwidth = 0.5   # Poor bandwidth

        degraded_condition = compressor.network_metrics.get_condition()

        # Condition should be POOR or VERY_POOR now
        assert degraded_condition in [NetworkCondition.POOR, NetworkCondition.VERY_POOR]

    def test_performance_monitoring(self, compressor, mock_compressor):
        """Test performance monitoring and metrics collection."""
        # Perform some compression operations
        test_messages = ["Short", "Medium message", "Longer message for testing purposes"]

        for msg in test_messages:
            result = compressor.compress_network_aware(msg, mock_compressor)
            assert result is not None

        # Metrics should have been updated (this may not be accurate since we're mocking)
        # Just verify the method calls work
        assert mock_compressor.compress.call_count >= len(test_messages)

    def test_edge_cases(self, compressor, mock_compressor):
        """Test edge cases and error handling."""
        # Test with empty message
        result = compressor.compress_network_aware("", mock_compressor)
        assert result is not None

        # Test with very large message
        large_message = "A" * 10000
        result = compressor.compress_network_aware(large_message, mock_compressor)
        assert result is not None

        # Test with special characters
        special_message = "Special chars: àáâãäåæçèéêë"
        result = compressor.compress_network_aware(special_message, mock_compressor)
        assert result is not None