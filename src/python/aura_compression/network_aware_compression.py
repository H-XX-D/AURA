"""Network-aware compression that balances latency vs bandwidth trade-offs."""

import time
import threading
import statistics
from typing import Dict, List, Tuple, Optional, Any, Callable
from enum import Enum
import socket
import struct
import os

class NetworkCondition(Enum):
    """Network condition classifications."""
    EXCELLENT = "excellent"      # < 10ms latency, > 100 Mbps
    GOOD = "good"               # < 50ms latency, > 10 Mbps
    MODERATE = "moderate"       # < 200ms latency, > 1 Mbps
    POOR = "poor"               # < 1000ms latency, > 100 Kbps
    VERY_POOR = "very_poor"     # > 1000ms latency or < 100 Kbps

class CompressionStrategy(Enum):
    """Compression strategies based on network conditions."""
    MAXIMUM_COMPRESSION = "maximum_compression"  # Best ratio, higher latency
    BALANCED = "balanced"                        # Good ratio, reasonable latency
    FAST_COMPRESSION = "fast_compression"        # Fast, moderate compression
    MINIMAL_COMPRESSION = "minimal_compression" # Very fast, minimal compression
    NO_COMPRESSION = "no_compression"           # No compression overhead

class NetworkMetrics:
    """Real-time network performance metrics."""

    def __init__(self):
        self.latency_samples: List[float] = []
        self.bandwidth_samples: List[float] = []
        self.packet_loss_samples: List[float] = []
        self.jitter_samples: List[float] = []

        # Current estimates
        self.current_latency = 50.0  # ms
        self.current_bandwidth = 10.0  # Mbps
        self.current_packet_loss = 0.01  # 1%
        self.current_jitter = 5.0  # ms

        # Thread safety
        self._lock = threading.RLock()

    def update_latency(self, latency_ms: float) -> None:
        """Update latency measurement."""
        with self._lock:
            self.latency_samples.append(latency_ms)
            if len(self.latency_samples) > 100:
                self.latency_samples = self.latency_samples[-100:]
            self.current_latency = statistics.mean(self.latency_samples)

    def update_bandwidth(self, bandwidth_mbps: float) -> None:
        """Update bandwidth measurement."""
        with self._lock:
            self.bandwidth_samples.append(bandwidth_mbps)
            if len(self.bandwidth_samples) > 50:
                self.bandwidth_samples = self.bandwidth_samples[-50:]
            self.current_bandwidth = statistics.mean(self.bandwidth_samples)

    def get_condition(self) -> NetworkCondition:
        """Determine current network condition."""
        with self._lock:
            latency = self.current_latency
            bandwidth = self.current_bandwidth

            if latency < 10 and bandwidth > 100:
                return NetworkCondition.EXCELLENT
            elif latency < 50 and bandwidth > 10:
                return NetworkCondition.GOOD
            elif latency < 200 and bandwidth > 1:
                return NetworkCondition.MODERATE
            elif latency < 1000 and bandwidth > 0.1:
                return NetworkCondition.POOR
            else:
                return NetworkCondition.VERY_POOR

class NetworkAwareCompressor:
    """Compression system that adapts to network conditions.

    Features:
    - Real-time network condition monitoring
    - Adaptive compression strategies
    - Latency vs bandwidth optimization
    - Automatic fallback for poor connections
    """

    def __init__(self, enable_network_monitoring: bool = True):
        self.enable_network_monitoring = enable_network_monitoring
        self.network_metrics = NetworkMetrics()

        # Strategy mappings for different network conditions
        self.condition_strategies = {
            NetworkCondition.EXCELLENT: CompressionStrategy.MAXIMUM_COMPRESSION,
            NetworkCondition.GOOD: CompressionStrategy.BALANCED,
            NetworkCondition.MODERATE: CompressionStrategy.BALANCED,
            NetworkCondition.POOR: CompressionStrategy.FAST_COMPRESSION,
            NetworkCondition.VERY_POOR: CompressionStrategy.MINIMAL_COMPRESSION
        }

        # Compression parameters for each strategy
        self.strategy_configs = {
            CompressionStrategy.MAXIMUM_COMPRESSION: {
                'target_ratio': 3.0,
                'max_latency': 100.0,  # ms
                'algorithms': ['brio', 'aura_lite', 'binary_semantic'],
                'description': 'Maximum compression for excellent networks'
            },
            CompressionStrategy.BALANCED: {
                'target_ratio': 2.0,
                'max_latency': 50.0,
                'algorithms': ['aura_lite', 'binary_semantic'],
                'description': 'Balanced compression for good networks'
            },
            CompressionStrategy.FAST_COMPRESSION: {
                'target_ratio': 1.5,
                'max_latency': 20.0,
                'algorithms': ['binary_semantic', 'aura_lite'],
                'description': 'Fast compression for moderate networks'
            },
            CompressionStrategy.MINIMAL_COMPRESSION: {
                'target_ratio': 1.2,
                'max_latency': 5.0,
                'algorithms': ['binary_semantic'],
                'description': 'Minimal compression for poor networks'
            },
            CompressionStrategy.NO_COMPRESSION: {
                'target_ratio': 1.0,
                'max_latency': 0.0,
                'algorithms': ['uncompressed'],
                'description': 'No compression for very poor networks'
            }
        }

        # Network monitoring
        if enable_network_monitoring:
            self._start_network_monitoring()

        # Statistics
        self.compression_stats = {
            'total_compressions': 0,
            'network_adaptations': 0,
            'strategy_changes': 0,
            'latency_improvements': 0,
            'bandwidth_savings': 0.0
        }

    def compress_network_aware(self, message: str, compressor: Any) -> Tuple[bytes, str, Dict[str, Any]]:
        """Compress message with network-aware strategy selection.

        Args:
            message: Message to compress
            compressor: Base compressor instance (ProductionHybridCompressor)

        Returns:
            (compressed_data, method, metadata)
        """
        start_time = time.time()

        # Determine current network condition
        network_condition = self.network_metrics.get_condition()
        strategy = self.condition_strategies[network_condition]

        # Get strategy configuration
        config = self.strategy_configs[strategy]

        # Apply network-aware compression
        if strategy == CompressionStrategy.NO_COMPRESSION:
            # No compression for very poor networks
            compressed = message.encode('utf-8')
            method = "uncompressed"
            metadata = {
                'original_size': len(message.encode('utf-8')),
                'compressed_size': len(compressed),
                'ratio': 1.0,
                'method': method,
                'network_condition': network_condition.value,
                'strategy': strategy.value,
                'compression_time': (time.time() - start_time) * 1000,
                'network_aware': True
            }

        elif strategy == CompressionStrategy.MINIMAL_COMPRESSION:
            # Minimal compression - prefer fastest method
            compressed, method, metadata = compressor.compress(message)

            # Override to use only binary_semantic if available
            if method.name.lower() not in ['binary_semantic', 'uncompressed']:
                # Force uncompressed for minimal compression
                compressed = message.encode('utf-8')
                method = type('MockMethod', (), {'name': 'UNCOMPRESSED'})()
                metadata = {
                    'original_size': len(message.encode('utf-8')),
                    'compressed_size': len(compressed),
                    'ratio': 1.0,
                    'method': 'uncompressed'
                }

        else:
            # Use full compression with strategy constraints
            compressed, method, metadata = self._compress_with_strategy(
                message, compressor, config
            )

        # Add network awareness metadata
        metadata.update({
            'network_condition': network_condition.value,
            'strategy': strategy.value,
            'network_aware': True,
            'target_ratio': config['target_ratio'],
            'max_latency': config['max_latency']
        })

        # Update statistics
        self.compression_stats['total_compressions'] += 1

        compression_time = (time.time() - start_time) * 1000
        if compression_time > config['max_latency']:
            self.compression_stats['latency_improvements'] += 1

        if metadata.get('ratio', 1.0) >= config['target_ratio'] * 0.8:
            self.compression_stats['bandwidth_savings'] += metadata.get('ratio', 1.0) - 1.0

        return compressed, method.name if hasattr(method, 'name') else str(method), metadata

    def _compress_with_strategy(self, message: str, compressor: Any,
                               config: Dict[str, Any]) -> Tuple[bytes, Any, Dict[str, Any]]:
        """Compress using strategy-specific constraints."""
        # Temporarily modify compressor settings based on strategy
        original_settings = {}

        try:
            # Apply strategy constraints
            if config['max_latency'] < 50:
                # For fast compression, disable slow algorithms
                if hasattr(compressor, 'enable_aura'):
                    original_settings['enable_aura'] = compressor.enable_aura
                    compressor.enable_aura = False

            # Compress with modified settings
            compressed, method, metadata = compressor.compress(message)

            # Check if result meets strategy requirements
            compression_time = metadata.get('compression_time', 0)
            ratio = metadata.get('ratio', 1.0)

            # If too slow for the strategy, fall back to faster method
            if compression_time > config['max_latency'] and ratio < config['target_ratio'] * 0.5:
                # Force uncompressed
                compressed = message.encode('utf-8')
                method = type('MockMethod', (), {'name': 'UNCOMPRESSED'})()
                metadata = {
                    'original_size': len(message.encode('utf-8')),
                    'compressed_size': len(compressed),
                    'ratio': 1.0,
                    'method': 'uncompressed',
                    'strategy_fallback': True
                }

        finally:
            # Restore original settings
            for key, value in original_settings.items():
                setattr(compressor, key, value)

        return compressed, method, metadata

    def _start_network_monitoring(self) -> None:
        """Start background network condition monitoring."""
        def monitor_network():
            while True:
                try:
                    # Simple latency test (ping-like)
                    latency = self._measure_latency()
                    if latency:
                        self.network_metrics.update_latency(latency)

                    # Estimate bandwidth (rough approximation)
                    bandwidth = self._estimate_bandwidth()
                    if bandwidth:
                        self.network_metrics.update_bandwidth(bandwidth)

                except Exception:
                    pass  # Ignore monitoring errors

                time.sleep(30)  # Check every 30 seconds

        thread = threading.Thread(target=monitor_network, daemon=True, name="network_monitor")
        thread.start()

    def _measure_latency(self) -> Optional[float]:
        """Measure network latency to a common endpoint."""
        try:
            # Use a simple socket connection to measure latency
            start_time = time.time()

            # Try to connect to a reliable endpoint (Google DNS)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5.0)
            sock.connect(("8.8.8.8", 53))
            sock.close()

            latency = (time.time() - start_time) * 1000  # Convert to ms
            return latency

        except (socket.error, socket.timeout):
            return None

    def _estimate_bandwidth(self) -> Optional[float]:
        """Estimate available bandwidth."""
        # Simple bandwidth estimation based on connection type
        # This is a rough approximation - real implementation would need more sophisticated testing
        try:
            # Check if we're on WiFi vs Ethernet (rough heuristic)
            import subprocess
            result = subprocess.run(['networksetup', '-getinfo', 'Wi-Fi'],
                                  capture_output=True, text=True, timeout=5)

            if result.returncode == 0 and 'IP address:' in result.stdout:
                # WiFi connection - estimate 50-200 Mbps
                return 100.0
            else:
                # Assume Ethernet or other - estimate 500-1000 Mbps
                return 750.0

        except Exception:
            # Fallback estimate
            return 50.0

    def get_network_stats(self) -> Dict[str, Any]:
        """Get network condition and compression statistics."""
        condition = self.network_metrics.get_condition()
        strategy = self.condition_strategies[condition]

        return {
            'network_condition': condition.value,
            'current_strategy': strategy.value,
            'network_metrics': {
                'latency_ms': self.network_metrics.current_latency,
                'bandwidth_mbps': self.network_metrics.current_bandwidth,
                'packet_loss_percent': self.network_metrics.current_packet_loss * 100,
                'jitter_ms': self.network_metrics.current_jitter
            },
            'compression_stats': self.compression_stats,
            'strategy_config': self.strategy_configs[strategy]
        }

    def force_network_condition(self, condition: NetworkCondition) -> None:
        """Force a specific network condition for testing."""
        # Override the condition detection for testing
        original_get_condition = self.network_metrics.get_condition
        self.network_metrics.get_condition = lambda: condition

        # Store original method for restoration
        self._original_get_condition = original_get_condition

    def reset_network_condition(self) -> None:
        """Reset forced network condition."""
        if hasattr(self, '_original_get_condition'):
            self.network_metrics.get_condition = self._original_get_condition