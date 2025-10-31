"""ML-based algorithm selection for optimal compression performance."""

import time
import math
import statistics
import re
import logging
import json
import threading
import hashlib
from typing import Dict, List, Tuple, Optional, Any, NamedTuple
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

# Import AI and template components for enhanced feature extraction
try:
    from aura_compression.pattern_semantic_large_file import PatternSemanticCompressor
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False

try:
    from aura_compression.template_service import TemplateService
    TEMPLATE_AVAILABLE = True
except ImportError:
    TEMPLATE_AVAILABLE = False

# Compression method constants
class CompressionMethod:
    UNCOMPRESSED = "uncompressed"
    BINARY_SEMANTIC = "binary_semantic"
    AURALITE = "auralite"
    BRIO = "brio"
    AURA_HEAVY = "aura_heavy"
    GZIP = "gzip"
    BZ2 = "bz2"
    LZMA = "lzma"
    PATTERN_SEMANTIC = "pattern_semantic"  # AI-powered semantic compression
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
    # AI semantic features
    pattern_semantic_score: float  # AI semantic understanding score (0-1)
    semantic_chunks: int  # Number of semantic chunks identified
    ai_patterns_found: int  # Number of AI-discovered patterns
    semantic_complexity: float  # Semantic complexity score (0-1)
    # Semantic binary features
    binary_semantic_potential: float  # Potential for semantic binary compression (0-1)
    structured_data_score: float  # How structured the data appears (0-1)
    repetitive_pattern_score: float  # Score for repetitive patterns (0-1)

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
    - AI semantic analysis integration
    - Template discovery integration
    - Semantic binary compression analysis
    """

    def __init__(self,
                 model_file: str = "./ml_model.json",
                 enable_learning: bool = True,
                 ai_compressor: Optional[Any] = None,
                 template_service: Optional[Any] = None,
                 enable_expensive_features: bool = True):
        self.model_file = Path(model_file)
        self.enable_learning = enable_learning

        # AI and template service integration
        self.ai_compressor = ai_compressor if ai_compressor else (PatternSemanticCompressor() if AI_AVAILABLE else None)
        self.template_service = template_service if template_service else (TemplateService() if TEMPLATE_AVAILABLE else None)
        self.enable_expensive_features = enable_expensive_features

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

        # Feature extraction cache
        self._feature_cache: Dict[str, Tuple[MessageFeatures, float]] = {}
        self._cache_max_size = 1000
        
        # Track analyzed messages to avoid re-analysis
        self._analyzed_messages: set = set()

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
        message_bytes = len(message.encode('utf-8'))

        if message_bytes < 25:
            return AlgorithmPrediction(
                method=CompressionMethod.UNCOMPRESSED,
                confidence=1.0,
                expected_ratio=1.0,
                reasoning="Fast-pass for payloads under 25 bytes"
            )

        # Check if we've already analyzed this exact message
        message_hash = hashlib.md5(message.encode()).hexdigest()
        if message_hash not in self._analyzed_messages:
            self._analyzed_messages.add(message_hash)
            if len(self._analyzed_messages) > 10000:
                self._analyzed_messages = set(list(self._analyzed_messages)[-5000:])

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

        if message_bytes < 1_048_576:
            viable_methods = [m for m in viable_methods if m != CompressionMethod.PATTERN_SEMANTIC]

        if not viable_methods:
            viable_methods = [CompressionMethod.UNCOMPRESSED] if CompressionMethod.UNCOMPRESSED in available_methods else available_methods

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

        if best_method not in available_methods:
            fallback_method = available_methods[0] if available_methods else CompressionMethod.UNCOMPRESSED
            best_method = fallback_method
            best_score = method_scores.get(best_method, {'expected_ratio': 1.0})

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

    def select_algorithm(self, message: str, available_methods: List[str]) -> str:
        """
        Select the best compression algorithm for a message.
        
        Args:
            message: The message to compress
            available_methods: List of available compression methods
            
        Returns:
            The selected compression method name
        """
        prediction = self.predict_routing_decision(message, available_methods)
        return prediction.method

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
        # Check cache first
        import hashlib
        import time
        message_hash = hashlib.md5(message.encode()).hexdigest()
        
        with self._lock:
            if message_hash in self._feature_cache:
                cached_features, cache_time = self._feature_cache[message_hash]
                # Cache for 5 minutes
                if time.time() - cache_time < 300:
                    return cached_features
            
            # Extract features
            features = self._extract_features_uncached(message)
            
            # Cache the result
            if len(self._feature_cache) >= self._cache_max_size:
                # Remove oldest entries (simple FIFO)
                oldest_key = next(iter(self._feature_cache))
                del self._feature_cache[oldest_key]
            
            self._feature_cache[message_hash] = (features, time.time())
            return features

    def _extract_features_uncached(self, message: str) -> MessageFeatures:
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

        # Template match score (use real template service if available)
        template_match_score = pattern_score  # Use existing pattern score as proxy
        if self.template_service and self.enable_expensive_features:
            try:
                # Only sync template store occasionally (not on every feature extraction)
                import time
                current_time = time.time()
                if not hasattr(self, '_last_template_sync') or current_time - self._last_template_sync > 60:  # Sync every 60 seconds
                    self.template_service.sync_template_store()
                    self._last_template_sync = current_time
                
                template_match = self.template_service.find_template_match(message)
                if template_match:
                    # Calculate real template match score based on match quality
                    match_ratio = len(template_match.matched_text) / len(message) if message else 0
                    template_match_score = min(1.0, match_ratio * 2.0)  # Boost score for good matches
                else:
                    template_match_score = pattern_score * 0.5  # Reduce if no template match
            except Exception:
                # Fallback to heuristic if template service fails
                template_match_score = pattern_score
        else:
            # Fast heuristic when template features are disabled
            if word_count > 5:  # More words = better template matching potential
                template_match_score += 0.2
            if avg_word_length > 6:  # Longer words may indicate structured content
                template_match_score += 0.1

        # AI semantic analysis features
        pattern_semantic_score = 0.0
        semantic_chunks = 0
        ai_patterns_found = 0
        semantic_complexity = 0.5  # Default medium complexity

        if self.ai_compressor and self.enable_expensive_features:
            try:
                # Use AI compressor to analyze semantic patterns
                patterns = self.ai_compressor._mine_patterns(message)
                chunks = self.ai_compressor._semantic_chunk(message)

                ai_patterns_found = len(patterns)
                semantic_chunks = len(chunks)

                # Calculate AI semantic score based on pattern discovery
                pattern_semantic_score = min(1.0, ai_patterns_found / 10.0)  # Normalize to 0-1

                # Estimate semantic complexity
                if semantic_chunks > 0:
                    avg_chunk_size = length / semantic_chunks
                    semantic_complexity = min(1.0, avg_chunk_size / 1000.0)  # Larger chunks = simpler
                else:
                    semantic_complexity = 0.8  # High complexity if no chunks found
            except Exception:
                # Fallback if AI analysis fails
                pattern_semantic_score = pattern_score * 0.7
                semantic_chunks = max(1, word_count // 5)
                ai_patterns_found = max(0, word_count // 10)
        else:
            # Fast heuristic when AI features are disabled
            pattern_semantic_score = pattern_score * 0.6
            semantic_chunks = max(1, word_count // 6)
            ai_patterns_found = max(0, word_count // 12)
            semantic_complexity = 0.5

        # Semantic binary compression potential
        binary_semantic_potential = 0.0
        structured_data_score = 0.0
        repetitive_pattern_score = 0.0

        # Analyze for semantic binary potential
        if has_numbers and has_special_chars:
            structured_data_score += 0.5  # Likely structured data

        # Look for repetitive patterns that semantic binary can exploit
        if length > 50:
            # Check for repeated sequences
            repeated_sequences = self._find_repeated_sequences(message)
            repetitive_pattern_score = min(1.0, len(repeated_sequences) / 5.0)

            # JSON/XML like structures get high binary semantic potential
            if self._looks_like_structured_data(message):
                binary_semantic_potential += 0.6
                structured_data_score += 0.4

        # Combine factors for binary semantic potential
        binary_semantic_potential = min(1.0,
            binary_semantic_potential +
            (structured_data_score * 0.3) +
            (repetitive_pattern_score * 0.4) +
            (template_match_score * 0.3)
        )

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
            template_match_score=min(1.0, template_match_score),
            pattern_semantic_score=min(1.0, pattern_semantic_score),
            semantic_chunks=semantic_chunks,
            ai_patterns_found=ai_patterns_found,
            semantic_complexity=max(0.0, min(1.0, semantic_complexity)),
            binary_semantic_potential=max(0.0, min(1.0, binary_semantic_potential)),
            structured_data_score=max(0.0, min(1.0, structured_data_score)),
            repetitive_pattern_score=max(0.0, min(1.0, repetitive_pattern_score))
        )

    def _find_repeated_sequences(self, message: str, min_length: int = 4, max_length: int = 20) -> List[str]:
        """Find repeated sequences in the message for semantic binary analysis."""
        if len(message) < min_length * 2:
            return []

        sequences = set()
        msg_len = len(message)

        # Look for repeated substrings of various lengths
        for length in range(min_length, min(max_length + 1, msg_len // 2 + 1)):
            for i in range(msg_len - length * 2 + 1):
                substring = message[i:i + length]
                # Count occurrences of this substring
                count = message.count(substring)
                if count > 1:
                    sequences.add(substring)

        return list(sequences)

    def _looks_like_structured_data(self, message: str) -> bool:
        """Determine if message looks like structured data (JSON, XML, etc.)."""
        if len(message) < 10:
            return False

        # JSON-like patterns
        json_indicators = ['{', '}', '[', ']', '"', ':', ',']
        json_score = sum(1 for char in json_indicators if char in message) / len(json_indicators)

        # XML-like patterns
        xml_indicators = ['<', '>', '/', '=', '"']
        xml_score = sum(1 for char in xml_indicators if char in message) / len(xml_indicators)

        # Key-value patterns (like config files)
        kv_patterns = [r'\w+\s*=\s*\w+', r'\w+\s*:\s*\w+']
        kv_score = 0
        for pattern in kv_patterns:
            if re.search(pattern, message):
                kv_score += 0.5

        # CSV-like patterns
        csv_score = 0
        if ',' in message and '\n' in message:
            lines = message.split('\n')[:5]  # Check first few lines
            if len(lines) > 1:
                # Check if lines have similar comma counts
                comma_counts = [line.count(',') for line in lines if line.strip()]
                if len(set(comma_counts)) == 1 and comma_counts[0] > 0:
                    csv_score = 0.8

        # Overall structured score
        structured_score = (json_score * 0.4) + (xml_score * 0.3) + (kv_score * 0.2) + (csv_score * 0.1)

        return structured_score > 0.3

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
            weights.get('template_match_score', 0.0) * features.template_match_score +
            # AI semantic features
            weights.get('pattern_semantic_score', 0.0) * features.pattern_semantic_score +
            weights.get('semantic_chunks', 0.0) * (features.semantic_chunks / 10.0) +
            weights.get('ai_patterns_found', 0.0) * (features.ai_patterns_found / 5.0) +
            weights.get('semantic_complexity', 0.0) * features.semantic_complexity +
            # Semantic binary features
            weights.get('binary_semantic_potential', 0.0) * features.binary_semantic_potential +
            weights.get('structured_data_score', 0.0) * features.structured_data_score +
            weights.get('repetitive_pattern_score', 0.0) * features.repetitive_pattern_score
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
        self.feature_weights = {
            CompressionMethod.UNCOMPRESSED: {
                'length': 0.1,  # Slightly prefers longer messages
                'entropy': 0.0,  # Doesn't care about entropy
                'has_numbers': 0.0,
                'has_special_chars': 0.0,
                'word_count': 0.0,
                'compression_potential': -0.5,  # Prefers incompressible content
                'pattern_score': 0.0,
                'pattern_semantic_score': 0.0,
                'semantic_chunks': 0.0,
                'ai_patterns_found': 0.0,
                'semantic_complexity': 0.0,
                'binary_semantic_potential': 0.0,
                'structured_data_score': 0.0,
                'repetitive_pattern_score': 0.0,
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
                'fast_path_potential': 0.6,
                'metadata_size_estimate': -0.2,
                'template_match_score': 0.8,  # Excellent for template matching
                'pattern_semantic_score': 0.2,
                'semantic_chunks': 0.3,
                'ai_patterns_found': 0.2,
                'semantic_complexity': -0.2,  # Prefers less complex structures
                'binary_semantic_potential': 0.8,  # Excellent for binary semantic
                'structured_data_score': 0.7,
                'repetitive_pattern_score': 0.4,
                'base_ratio': 1.8
            },
            CompressionMethod.PATTERN_SEMANTIC: {
                'length': 0.4,  # Good for longer files
                'entropy': -0.4,  # Prefers patterned data
                'has_numbers': 0.3,
                'has_special_chars': 0.3,
                'word_count': 0.2,
                'compression_potential': 0.6,  # High compression potential
                'pattern_score': 0.6,
                'fast_path_potential': 0.3,
                'metadata_size_estimate': 0.1,
                'template_match_score': 0.5,
                'pattern_semantic_score': 0.9,  # Requires high AI semantic understanding
                'semantic_chunks': 0.8,  # Benefits from semantic chunking
                'ai_patterns_found': 0.9,  # Loves AI-discovered patterns
                'semantic_complexity': -0.3,  # Prefers simpler semantic structures
                'binary_semantic_potential': 0.5,
                'structured_data_score': 0.4,
                'repetitive_pattern_score': 0.6,
                'base_ratio': 4.0  # Best compression ratios
            },
            CompressionMethod.BRIO: {
                'length': 0.4,  # Best for longer messages
                'entropy': -0.4,  # Excellent for repetitive data
                'has_numbers': 0.1,
                'has_special_chars': 0.1,
                'word_count': 0.2,
                'compression_potential': 0.5,  # Best compression potential
                'pattern_score': 0.4,
                'fast_path_potential': 0.2,
                'metadata_size_estimate': -0.1,
                'template_match_score': 0.3,
                'pattern_semantic_score': 0.4,
                'semantic_chunks': 0.5,
                'ai_patterns_found': 0.6,  # Good for pattern-based compression
                'semantic_complexity': 0.0,
                'binary_semantic_potential': 0.3,
                'structured_data_score': 0.2,
                'repetitive_pattern_score': 0.8,  # Excellent for repetitive patterns
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
                'fast_path_potential': 0.1,
                'metadata_size_estimate': -0.1,
                'template_match_score': 0.2,
                'pattern_semantic_score': 0.2,
                'semantic_chunks': 0.3,
                'ai_patterns_found': 0.2,
                'semantic_complexity': 0.0,
                'binary_semantic_potential': 0.1,
                'structured_data_score': 0.1,
                'repetitive_pattern_score': 0.2,
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
                'fast_path_potential': 0.3,
                'metadata_size_estimate': -0.2,
                'template_match_score': 0.4,
                'pattern_semantic_score': 0.5,
                'semantic_chunks': 0.6,
                'ai_patterns_found': 0.7,
                'semantic_complexity': -0.1,
                'binary_semantic_potential': 0.4,
                'structured_data_score': 0.3,
                'repetitive_pattern_score': 0.9,  # Best for repetitive patterns
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
                'pattern_semantic_score': 0.3,
                'semantic_chunks': 0.2,
                'ai_patterns_found': 0.2,
                'semantic_complexity': -0.2,  # Simpler structures route faster
                'binary_semantic_potential': 0.4,
                'structured_data_score': 0.6,
                'repetitive_pattern_score': 0.3,
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
                'pattern_semantic_score': 0.1,
                'semantic_chunks': 0.0,
                'ai_patterns_found': -0.1,
                'semantic_complexity': 0.4,  # Complex structures need slow path
                'binary_semantic_potential': -0.2,
                'structured_data_score': -0.3,
                'repetitive_pattern_score': -0.2,
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
                'pattern_semantic_score': 0.0,
                'semantic_chunks': 0.0,
                'ai_patterns_found': 0.0,
                'semantic_complexity': 0.0,
                'binary_semantic_potential': 0.0,
                'structured_data_score': 0.0,
                'repetitive_pattern_score': 0.0,
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
                        'fast_path_potential': 0.0, 'metadata_size_estimate': 0.0,
                        'template_match_score': 0.0, 'pattern_semantic_score': 0.0,
                        'semantic_chunks': 0.0, 'ai_patterns_found': 0.0,
                        'semantic_complexity': 0.0, 'binary_semantic_potential': 0.0,
                        'structured_data_score': 0.0, 'repetitive_pattern_score': 0.0,
                        'base_ratio': avg_ratio
                    }

                weights = self.feature_weights[method]

                # Simple reinforcement learning: adjust weights toward successful features
                for data_point in method_data:
                    features = data_point['features']
                    
                    # Ensure all new feature keys exist in old data (backward compatibility)
                    if 'fast_path_potential' not in features:
                        features['fast_path_potential'] = 0.0
                    if 'template_match_score' not in features:
                        features['template_match_score'] = 0.0
                    if 'pattern_semantic_score' not in features:
                        features['pattern_semantic_score'] = 0.0
                    if 'semantic_chunks' not in features:
                        features['semantic_chunks'] = 0
                    if 'ai_patterns_found' not in features:
                        features['ai_patterns_found'] = 0
                    if 'semantic_complexity' not in features:
                        features['semantic_complexity'] = 0.5
                    if 'binary_semantic_potential' not in features:
                        features['binary_semantic_potential'] = 0.0
                    if 'structured_data_score' not in features:
                        features['structured_data_score'] = 0.0
                    if 'repetitive_pattern_score' not in features:
                        features['repetitive_pattern_score'] = 0.0
                    
                    performance = data_point['ratio'] / max(data_point['compression_time'], 0.001)

                    # Adjust weights based on performance
                    adjustment = self.learning_rate * (performance - 0.5)

                    weights['length'] += adjustment * (features.get('length', 0) / 1000.0)
                    weights['entropy'] += adjustment * features.get('entropy', 0)
                    weights['compression_potential'] += adjustment * features.get('compression_potential', 0)
                    weights['pattern_score'] += adjustment * features.get('pattern_score', 0)
                    weights['fast_path_potential'] += adjustment * features.get('fast_path_potential', 0.0)
                    weights['template_match_score'] += adjustment * features.get('template_match_score', 0.0)
                    weights['pattern_semantic_score'] += adjustment * features.get('pattern_semantic_score', 0.0)
                    weights['semantic_chunks'] += adjustment * (features.get('semantic_chunks', 0) / 10.0)
                    weights['ai_patterns_found'] += adjustment * (features.get('ai_patterns_found', 0) / 5.0)
                    weights['semantic_complexity'] += adjustment * features.get('semantic_complexity', 0.0)
                    weights['binary_semantic_potential'] += adjustment * features.get('binary_semantic_potential', 0.0)
                    weights['structured_data_score'] += adjustment * features.get('structured_data_score', 0.0)
                    weights['repetitive_pattern_score'] += adjustment * features.get('repetitive_pattern_score', 0.0)

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

            logger.info(f"Loaded ML model with {len(self.performance_history)} training samples")

        except (json.JSONDecodeError, IOError) as e:
            logger.info(f"Warning: Failed to load ML model: {e}")

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
            logger.info(f"Warning: Failed to save ML model: {e}")

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
