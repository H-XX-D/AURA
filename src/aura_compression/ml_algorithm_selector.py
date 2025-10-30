"""ML-based algorithm selection for optimal compression performance."""

import time
import math
import statistics
from typing import Dict, List, Tuple, Optional, Any, NamedTuple
from pathlib import Path
import json
import threading
from concurrent.futures import ThreadPoolExecutor
import hashlib

# Compression method constants
class CompressionMethod:
    UNCOMPRESSED = "uncompressed"
    BINARY_SEMANTIC = "binary_semantic"
    AURA_LITE = "aura_lite"
    AURALITE = "auralite"
    BRIO = "brio"
    AURA_HEAVY = "aura_heavy"
    AI_SEMANTIC = "ai_semantic"
    GZIP = "gzip"
    BZ2 = "bz2"
    LZMA = "lzma"
    # Routing methods
    FAST_PATH = "fast_path"      # Route using metadata only (no decompression)
    SLOW_PATH = "slow_path"      # Route requiring full decompression
    CACHED = "cached"           # Serve from cache

class CompressionResult(NamedTuple):
    """Result of a compression operation with metrics."""
    method: str
    original_size: int
    compressed_size: float
    compression_time: float
    ratio: float

class MessageFeatures(NamedTuple):
    """Features extracted from a message for ML prediction."""
    length: int
    entropy: float
    has_numbers: bool
    has_special_chars: bool
    word_count: int
    avg_word_length: float
    compression_potential: float  # Estimated compressibility
    pattern_score: float  # How well it matches known patterns
    # Routing features
    fast_path_potential: float  # Likelihood message can use fast-path routing (0-1)
    metadata_size_estimate: int  # Estimated metadata size for routing decisions
    template_match_score: float  # How well message matches existing templates (0-1)

class AlgorithmPrediction(NamedTuple):
    """ML prediction result."""
    method: str
    confidence: float
    expected_ratio: float
    reasoning: str

class MLAlgorithmSelector:
    """Machine learning-based algorithm selection for optimal compression.

    Features:
    - Learns optimal compression methods based on message characteristics
    - Continuously improves through reinforcement learning
    - Feature extraction for pattern recognition
    - Performance prediction and optimization
    """

    def __init__(self, model_file: str = ".aura_cache/ml_model.json", enable_learning: bool = True):
        self.model_file = Path(model_file)
        self.enable_learning = enable_learning

        # Model data
        self.feature_weights: Dict[str, Dict[str, float]] = {}
        self.performance_history: List[Dict[str, Any]] = []
        self.method_stats: Dict[str, Dict[str, float]] = {}

        # Learning parameters
        self.learning_rate = 0.1
        self.confidence_threshold = 0.7
        self.max_history_size = 10000

        # Thread safety
        self._lock = threading.RLock()
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ml_selector")

        # Initialize default model
        self._initialize_default_model()

        # Load existing model
        self._load_model()

    def predict_routing_decision(self, message: str, available_methods: List[str], metadata: Optional[Dict[str, Any]] = None) -> AlgorithmPrediction:
        """
        Predict optimal routing/compression decision for a message.

        This method considers both compression methods and routing paths (fast-path, slow-path, cached)
        to make the best overall decision for message processing.

        Args:
            message: The message to analyze
            available_methods: List of available compression/routing methods
            metadata: Optional metadata about the message for routing decisions

        Returns:
            AlgorithmPrediction with the recommended method and confidence
        """
        if not available_methods:
            return AlgorithmPrediction(
                method=CompressionMethod.UNCOMPRESSED,
                confidence=1.0,
                expected_ratio=1.0,
                reasoning="No methods available"
            )

        # Extract features
        features = self._extract_features(message)

        # Check if message can be served from cache (if metadata provided)
        if metadata and self._should_use_cache(metadata):
            return AlgorithmPrediction(
                method=CompressionMethod.CACHED,
                confidence=0.9,
                expected_ratio=1.0,
                reasoning="Message found in cache"
            )

        # Determine if fast-path routing is viable
        fast_path_viable = self._is_fast_path_viable(features, metadata)

        # Filter available methods based on viability
        viable_methods = []
        for method in available_methods:
            if method in [CompressionMethod.FAST_PATH, CompressionMethod.SLOW_PATH]:
                if method == CompressionMethod.FAST_PATH and fast_path_viable:
                    viable_methods.append(method)
                elif method == CompressionMethod.SLOW_PATH and not fast_path_viable:
                    viable_methods.append(method)
            else:
                # Compression methods are always viable
                viable_methods.append(method)

        if not viable_methods:
            viable_methods = available_methods

        # Score all viable methods
        method_scores = {}
        for method in viable_methods:
            score = self._score_method(method, features)
            method_scores[method] = score

        # Select best method
        best_method = max(method_scores.keys(), key=lambda m: method_scores[m]['total_score'])
        best_score = method_scores[best_method]

        # Calculate confidence
        scores = [s['total_score'] for s in method_scores.values()]
        if len(scores) > 1:
            score_range = max(scores) - min(scores)
            confidence = min(1.0, score_range / 2.0) if score_range > 0 else 0.5
        else:
            confidence = 0.8

        # Generate reasoning
        reasoning_parts = []
        if best_method == CompressionMethod.FAST_PATH:
            reasoning_parts.append("Fast-path routing recommended for structured data")
        elif best_method == CompressionMethod.SLOW_PATH:
            reasoning_parts.append("Slow-path required for complex processing")
        elif best_method == CompressionMethod.CACHED:
            reasoning_parts.append("Serving from cache")
        else:
            reasoning_parts.append(f"ML prediction based on {len(features)} features")

        if features.fast_path_potential > 0.7:
            reasoning_parts.append(".7f")
        elif features.fast_path_potential < 0.3:
            reasoning_parts.append(".2f")

        return AlgorithmPrediction(
            method=best_method,
            confidence=confidence,
            expected_ratio=best_score.get('expected_ratio', 1.0),
            reasoning=" ".join(reasoning_parts)
        )

    def _is_fast_path_viable(self, features: MessageFeatures, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Determine if fast-path routing is viable for this message."""
        # Fast-path criteria
        viability_score = 0.0

        # Feature-based viability
        if features.fast_path_potential > 0.6:
            viability_score += 0.4
        if features.template_match_score > 0.5:
            viability_score += 0.3
        if features.metadata_size_estimate < 300:  # Reasonable metadata size
            viability_score += 0.2
        if features.length < 1000:  # Not too long for fast processing
            viability_score += 0.1

        # Metadata-based viability (if available)
        if metadata:
            if metadata.get('template_ids'):  # Has template matches
                viability_score += 0.3
            if metadata.get('function_id'):  # Has function routing info
                viability_score += 0.2
            if metadata.get('compressed_size', 0) < 500:  # Small compressed size
                viability_score += 0.1

        return viability_score > 0.5

    def _should_use_cache(self, metadata: Dict[str, Any]) -> bool:
        """Determine if message should be served from cache."""
        # Simple cache logic - can be enhanced
        cache_key = metadata.get('cache_key') or metadata.get('message_hash')
        return cache_key is not None and len(str(cache_key)) > 10  # Arbitrary cache hit criteria
        """Predict the optimal compression method for a message."""
        if not available_methods:
            return AlgorithmPrediction(
                method=CompressionMethod.UNCOMPRESSED,
                confidence=1.0,
                expected_ratio=1.0,
                reasoning="No methods available"
            )

        # Extract features
        features = self._extract_features(message)

        # Score each method
        method_scores = {}
        for method in available_methods:
            score = self._score_method(method, features)
            method_scores[method] = score

        # Select best method
        best_method = max(method_scores.keys(), key=lambda m: method_scores[m]['total_score'])
        best_score = method_scores[best_method]

        # Calculate confidence based on score difference
        scores = [s['total_score'] for s in method_scores.values()]
        if len(scores) > 1:
            score_range = max(scores) - min(scores)
            confidence = min(1.0, score_range / 2.0) if score_range > 0 else 0.5
        else:
            confidence = 0.8

        return AlgorithmPrediction(
            method=best_method,
            confidence=confidence,
            expected_ratio=best_score.get('expected_ratio', 1.0),
            reasoning=f"ML prediction based on {len(features)} features"
        )

    def record_performance(self, message: str, method: str, result: CompressionResult) -> None:
        """Record compression performance for learning."""
        if not self.enable_learning:
            return

        features = self._extract_features(message)

        performance_data = {
            'timestamp': time.time(),
            'features': features._asdict(),
            'method': method,
            'original_size': result.original_size,
            'compressed_size': result.compressed_size,
            'compression_time': result.compression_time,
            'ratio': result.ratio,
            'message_hash': hashlib.md5(message.encode()).hexdigest()[:8]
        }

        with self._lock:
            self.performance_history.append(performance_data)

            # Keep history size manageable
            if len(self.performance_history) > self.max_history_size:
                self.performance_history = self.performance_history[-self.max_history_size:]

            # Update method statistics
            if method not in self.method_stats:
                self.method_stats[method] = {
                    'total_compressions': 0,
                    'avg_ratio': 0.0,
                    'avg_time': 0.0,
                    'success_rate': 1.0
                }

            stats = self.method_stats[method]
            stats['total_compressions'] += 1
            stats['avg_ratio'] = (
                (stats['avg_ratio'] * (stats['total_compressions'] - 1)) + result.ratio
            ) / stats['total_compressions']
            stats['avg_time'] = (
                (stats['avg_time'] * (stats['total_compressions'] - 1)) + result.compression_time
            ) / stats['total_compressions']

        # Trigger learning in background
        self._executor.submit(self._update_model)

    def get_method_stats(self) -> Dict[str, Any]:
        """Get statistics for all compression methods."""
        with self._lock:
            return {
                'methods': dict(self.method_stats),
                'total_samples': len(self.performance_history),
                'model_features': len(self.feature_weights),
                'learning_enabled': self.enable_learning
            }

    def _extract_features(self, message: str) -> MessageFeatures:
        """Extract features from a message for ML prediction."""
        length = len(message)

        # Calculate entropy (information content)
        if length == 0:
            entropy = 0.0
        else:
            char_counts = {}
            for char in message:
                char_counts[char] = char_counts.get(char, 0) + 1

            entropy = 0.0
            for count in char_counts.values():
                prob = count / length
                entropy -= prob * math.log2(prob)

        # Pattern analysis
        has_numbers = any(c.isdigit() for c in message)
        has_special_chars = any(not c.isalnum() and not c.isspace() for c in message)

        words = message.split()
        word_count = len(words)
        avg_word_length = statistics.mean(len(word) for word in words) if words else 0

        # Estimate compression potential (rough heuristic)
        # Lower entropy = more compressible
        # Repeated patterns = more compressible
        compression_potential = 1.0 - (entropy / 8.0)  # Normalize entropy to 0-1

        # Pattern score based on known compressible patterns
        pattern_score = 0.0
        if ' ' in message:  # Has spaces (likely natural language)
            pattern_score += 0.3
        if has_numbers and has_special_chars:  # Structured data
            pattern_score += 0.4
        if length > 100:  # Longer messages tend to compress better
            pattern_score += 0.2
        if entropy < 4.0:  # Low entropy = high compressibility
            pattern_score += 0.3

        # Estimate fast-path routing potential
        # Messages with structured metadata or template matches are good candidates
        fast_path_potential = 0.0
        if has_numbers and has_special_chars:  # Likely has structured metadata
            fast_path_potential += 0.4
        if pattern_score > 0.5:  # Good pattern matching potential
            fast_path_potential += 0.3
        if length < 500:  # Smaller messages easier to route via metadata
            fast_path_potential += 0.2
        if entropy > 6.0:  # High entropy messages may need full processing
            fast_path_potential -= 0.2

        # Estimate metadata size (rough heuristic based on message structure)
        metadata_size_estimate = 100  # Base metadata overhead
        if has_numbers:
            metadata_size_estimate += 50  # Numbers add to metadata
        if has_special_chars:
            metadata_size_estimate += 30  # Special chars add structure
        metadata_size_estimate += min(length // 10, 200)  # Content-based metadata

        # Template match score (simplified heuristic)
        template_match_score = pattern_score  # Use existing pattern score as proxy
        if word_count > 5:  # More words = better template matching potential
            template_match_score += 0.2
        if avg_word_length > 6:  # Longer words may indicate structured content
            template_match_score += 0.1

        return MessageFeatures(
            length=length,
            entropy=entropy,
            has_numbers=has_numbers,
            has_special_chars=has_special_chars,
            word_count=word_count,
            avg_word_length=avg_word_length,
            compression_potential=max(0.0, min(1.0, compression_potential)),
            pattern_score=min(1.0, pattern_score),
            fast_path_potential=max(0.0, min(1.0, fast_path_potential)),
            metadata_size_estimate=metadata_size_estimate,
            template_match_score=min(1.0, template_match_score)
        )

    def _score_method(self, method: str, features: MessageFeatures) -> Dict[str, float]:
        """Score how well a method matches the message features."""
        if method not in self.feature_weights:
            # Default scoring for unknown methods
            return {
                'total_score': 0.5,
                'expected_ratio': 1.0,
                'feature_match': 0.5
            }

        weights = self.feature_weights[method]
        score = 0.0

        # Feature matching score
        feature_score = (
            weights.get('length', 0.0) * (features.length / 1000.0) +
            weights.get('entropy', 0.0) * features.entropy +
            weights.get('has_numbers', 0.0) * (1.0 if features.has_numbers else 0.0) +
            weights.get('has_special_chars', 0.0) * (1.0 if features.has_special_chars else 0.0) +
            weights.get('word_count', 0.0) * (features.word_count / 50.0) +
            weights.get('compression_potential', 0.0) * features.compression_potential +
            weights.get('pattern_score', 0.0) * features.pattern_score +
            # Routing features
            weights.get('fast_path_potential', 0.0) * features.fast_path_potential +
            weights.get('metadata_size_estimate', 0.0) * (features.metadata_size_estimate / 500.0) +
            weights.get('template_match_score', 0.0) * features.template_match_score
        )

        # Method performance score (from learned data)
        perf_score = 0.0
        if method in self.method_stats:
            stats = self.method_stats[method]
            # Prefer methods with better compression ratios and reasonable speed
            perf_score = (
                stats['avg_ratio'] * 0.7 +  # 70% weight on compression ratio
                (1.0 / max(stats['avg_time'], 0.001)) * 0.3  # 30% weight on speed (inverse time)
            )

        total_score = (feature_score * 0.6) + (perf_score * 0.4)

        # Expected ratio prediction
        expected_ratio = weights.get('base_ratio', 1.0)
        if method in self.method_stats:
            expected_ratio = self.method_stats[method]['avg_ratio']

        return {
            'total_score': total_score,
            'expected_ratio': expected_ratio,
            'feature_match': feature_score,
            'performance_score': perf_score
        }

    def _initialize_default_model(self) -> None:
        """Initialize default model weights based on algorithm characteristics."""
        # Default weights based on typical algorithm performance
        self.feature_weights = {
            CompressionMethod.UNCOMPRESSED: {
                'length': 0.1,  # Slightly prefers longer messages
                'entropy': 0.0,  # Doesn't care about entropy
                'has_numbers': 0.0,
                'has_special_chars': 0.0,
                'word_count': 0.0,
                'compression_potential': -0.5,  # Prefers incompressible content
                'pattern_score': 0.0,
                'base_ratio': 1.0
            },
            CompressionMethod.BINARY_SEMANTIC: {
                'length': 0.2,
                'entropy': -0.3,  # Prefers structured data
                'has_numbers': 0.4,
                'has_special_chars': 0.3,
                'word_count': 0.1,
                'compression_potential': 0.2,
                'pattern_score': 0.5,  # Good for structured patterns
                'base_ratio': 1.8
            },
            CompressionMethod.AURA_LITE: {
                'length': 0.3,
                'entropy': -0.2,
                'has_numbers': 0.2,
                'has_special_chars': 0.2,
                'word_count': 0.4,  # Good for text
                'compression_potential': 0.4,
                'pattern_score': 0.3,
                'base_ratio': 1.5
            },
            CompressionMethod.BRIO: {
                'length': 0.4,  # Best for longer messages
                'entropy': -0.4,  # Excellent for repetitive data
                'has_numbers': 0.1,
                'has_special_chars': 0.1,
                'word_count': 0.2,
                'compression_potential': 0.5,  # Best compression potential
                'pattern_score': 0.4,
                'base_ratio': 2.5
            },
            CompressionMethod.AURALITE: {
                'length': 0.3,
                'entropy': -0.2,
                'has_numbers': 0.1,
                'has_special_chars': 0.1,
                'word_count': 0.3,
                'compression_potential': 0.3,
                'pattern_score': 0.2,
                'base_ratio': 1.3
            },
            CompressionMethod.AURA_HEAVY: {
                'length': 0.5,  # Best for very long messages
                'entropy': -0.5,  # Excellent for highly repetitive data
                'has_numbers': 0.2,
                'has_special_chars': 0.2,
                'word_count': 0.3,
                'compression_potential': 0.6,  # Highest compression potential
                'pattern_score': 0.5,
                'base_ratio': 3.0
            },
            # Routing methods (no compression, just routing decisions)
            CompressionMethod.FAST_PATH: {
                'length': -0.3,  # Prefers shorter messages
                'entropy': 0.0,
                'has_numbers': 0.5,  # Structured data good for fast-path
                'has_special_chars': 0.4,
                'word_count': 0.2,
                'compression_potential': 0.0,  # Routing, not compression
                'pattern_score': 0.6,  # Good patterns enable fast routing
                'fast_path_potential': 0.8,  # High fast-path potential
                'metadata_size_estimate': -0.3,  # Smaller metadata preferred
                'template_match_score': 0.7,  # Template matches enable fast-path
                'base_ratio': 1.0  # No compression ratio for routing
            },
            CompressionMethod.SLOW_PATH: {
                'length': 0.2,  # Can handle longer messages
                'entropy': 0.3,  # High entropy needs full processing
                'has_numbers': -0.2,  # Less structured data
                'has_special_chars': -0.1,
                'word_count': 0.1,
                'compression_potential': 0.0,
                'pattern_score': -0.3,  # Poor patterns need slow path
                'fast_path_potential': -0.6,  # Low fast-path potential
                'metadata_size_estimate': 0.2,  # Larger metadata OK for slow path
                'template_match_score': -0.4,  # No template match = slow path
                'base_ratio': 1.0
            },
            CompressionMethod.CACHED: {
                'length': 0.0,
                'entropy': 0.0,
                'has_numbers': 0.0,
                'has_special_chars': 0.0,
                'word_count': 0.0,
                'compression_potential': 0.0,
                'pattern_score': 0.0,
                'fast_path_potential': 0.0,
                'metadata_size_estimate': 0.0,
                'template_match_score': 0.0,
                'base_ratio': 1.0  # Cached responses have no compression cost
            }
        }

    def _update_model(self) -> None:
        """Update model weights based on recent performance data."""
        if not self.enable_learning or len(self.performance_history) < 10:
            return

        with self._lock:
            recent_data = self.performance_history[-100:]  # Use recent samples

            # Update weights based on performance
            for method in set(d['method'] for d in recent_data):
                method_data = [d for d in recent_data if d['method'] == method]
                if len(method_data) < 5:
                    continue

                # Calculate average performance for this method
                avg_ratio = statistics.mean(d['ratio'] for d in method_data)
                avg_time = statistics.mean(d['compression_time'] for d in method_data)

                # Update feature weights based on what led to good performance
                if method not in self.feature_weights:
                    self.feature_weights[method] = {
                        'length': 0.0, 'entropy': 0.0, 'has_numbers': 0.0,
                        'has_special_chars': 0.0, 'word_count': 0.0,
                        'compression_potential': 0.0, 'pattern_score': 0.0,
                        'base_ratio': avg_ratio
                    }

                weights = self.feature_weights[method]

                # Simple reinforcement learning: adjust weights toward successful features
                for data_point in method_data:
                    features = data_point['features']
                    performance = data_point['ratio'] / max(data_point['compression_time'], 0.001)

                    # Adjust weights based on performance
                    adjustment = self.learning_rate * (performance - 0.5)

                    weights['length'] += adjustment * (features['length'] / 1000.0)
                    weights['entropy'] += adjustment * features['entropy']
                    weights['compression_potential'] += adjustment * features['compression_potential']
                    weights['pattern_score'] += adjustment * features['pattern_score']

                    # Keep weights in reasonable bounds
                    for key in weights:
                        if isinstance(weights[key], (int, float)):
                            weights[key] = max(-1.0, min(1.0, weights[key]))

    def _load_model(self) -> None:
        """Load model from disk."""
        if not self.model_file.exists():
            return

        try:
            with open(self.model_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.feature_weights = data.get('feature_weights', self.feature_weights)
            self.method_stats = data.get('method_stats', {})
            self.performance_history = data.get('performance_history', [])

            print(f"Loaded ML model with {len(self.performance_history)} training samples")

        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Failed to load ML model: {e}")

    def save_model(self) -> None:
        """Save model to disk."""
        try:
            self.model_file.parent.mkdir(parents=True, exist_ok=True)

            data = {
                'feature_weights': self.feature_weights,
                'method_stats': self.method_stats,
                'performance_history': self.performance_history[-1000:],  # Save last 1000 samples
                'timestamp': time.time()
            }

            with open(self.model_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)

        except IOError as e:
            print(f"Warning: Failed to save ML model: {e}")

    def __del__(self):
        """Save model on destruction."""
        try:
            if hasattr(self, '_executor') and self._executor:
                # Don't wait during interpreter shutdown to avoid thread join issues
                self._executor.shutdown(wait=False)
            self.save_model()
        except Exception:
            # Ignore errors during destruction
            pass