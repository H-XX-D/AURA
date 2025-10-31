# ML Algorithm Selector

## Overview

The ML Algorithm Selector is a lightweight machine learning component that predicts the optimal compression method for each message based on extracted features. It uses heuristic-based scoring and online learning to adapt to workload patterns without requiring external ML libraries.

## Location

**File:** `src/aura_compression/ml_algorithm_selector.py`

## Key Components

### Classes

#### `CompressionResult`
Result of a compression operation with performance metrics.

**Fields:**
- `method` (str): Compression method used
- `original_size` (int): Original message size in bytes
- `compressed_size` (float): Compressed size in bytes
- `compression_time` (float): Time taken to compress in seconds
- `ratio` (float): Compression ratio achieved

#### `MessageFeatures`
Features extracted from a message for ML prediction.

**Fields:**
- `length` (int): Message length in bytes
- `entropy` (float): Shannon entropy (0-8 bits)
- `has_numbers` (bool): Contains numeric characters
- `has_special_chars` (bool): Contains special characters
- `word_count` (int): Number of words
- `avg_word_length` (float): Average word length
- `compression_potential` (float): Estimated compressibility (0-1)
- `pattern_score` (float): Pattern matching score (0-1)
- `fast_path_potential` (float): Likelihood of fast-path routing (0-1)
- `metadata_size_estimate` (int): Estimated metadata size
- `template_match_score` (float): Template matching score (0-1)
- `ai_semantic_score` (float): AI semantic understanding (0-1)
- `semantic_chunks` (int): Number of semantic chunks
- `ai_patterns_found` (int): AI-discovered patterns
- `semantic_complexity` (float): Semantic complexity (0-1)
- `binary_semantic_potential` (float): Binary semantic compression potential (0-1)
- `structured_data_score` (float): How structured the data appears (0-1)
- `repetitive_pattern_score` (float): Repetitive pattern score (0-1)

#### `AlgorithmPrediction`
ML prediction result with confidence and reasoning.

**Fields:**
- `method` (str): Recommended compression method
- `confidence` (float): Prediction confidence (0-1)
- `expected_ratio` (float): Expected compression ratio
- `reasoning` (str): Human-readable explanation

### Main Class: `MLAlgorithmSelector`

Machine learning selector that chooses optimal compression algorithms based on message characteristics.

#### Key Methods

##### `__init__(model_path: str = None, enable_training: bool = True)`
Initialize the ML algorithm selector.

**Parameters:**
- `model_path`: Path to save/load trained model (default: `.aura_cache/ml_model.json`)
- `enable_training`: Enable online learning from compression results

##### `extract_features(text: str) -> MessageFeatures`
Extract ML features from a text message.

**Parameters:**
- `text`: Input message text

**Returns:**
- `MessageFeatures`: Extracted feature vector

**Features Extracted:**
- Length, entropy, character types
- Word statistics
- Compression potential estimate
- Pattern matching scores
- Template compatibility
- AI semantic analysis (if available)

##### `predict(text: str) -> AlgorithmPrediction`
Predict the optimal compression method for a message.

**Parameters:**
- `text`: Input message text

**Returns:**
- `AlgorithmPrediction`: Method recommendation with confidence

**Decision Process:**
1. Extract message features
2. Calculate heuristic scores for each method
3. Select highest-scoring method
4. Return prediction with reasoning

##### `record_result(text: str, result: CompressionResult)`
Record compression result for online learning.

**Parameters:**
- `text`: Original message text
- `result`: Compression result with performance metrics

**Updates:**
- Method-specific statistics
- Feature-ratio correlations
- Model weights (if training enabled)

##### `save_model(path: str = None)`
Save trained model to disk.

**Parameters:**
- `path`: Output file path (defaults to `model_path`)

**Saves:**
- Method statistics
- Feature importance weights
- Historical performance data

##### `load_model(path: str = None) -> bool`
Load trained model from disk.

**Parameters:**
- `path`: Input file path (defaults to `model_path`)

**Returns:**
- `bool`: True if model loaded successfully

## Compression Methods

The selector chooses between:

- **BINARY_SEMANTIC**: Template-based compression for structured messages
- **AURALITE**: Hybrid compression for general text
- **BRIO**: High-compression method with rANS encoding
- **AI_SEMANTIC**: AI-powered semantic compression for large files (>10KB)
- **UNCOMPRESSED**: Fallback for incompressible data
- **FAST_PATH**: Metadata-only routing (no decompression needed)
- **SLOW_PATH**: Full decompression required
- **CACHED**: Serve from cache

## Selection Heuristics

### Binary Semantic (Template-based)
Selected when:
- `template_match_score > 0.7` (high template match)
- `structured_data_score > 0.6` (structured data)
- Message length 100-2048 bytes
- Expected ratio: 2.0-3.0x

### AI Semantic
Selected when:
- Message length > 10,000 bytes
- `ai_semantic_score > 0.6`
- Complex semantic patterns
- Expected ratio: 1.5-2.5x

### AURALITE (Default)
Selected when:
- General text compression needed
- No strong template match
- Medium message sizes (200-5000 bytes)
- Expected ratio: 1.2-1.8x

### UNCOMPRESSED
Selected when:
- High entropy (> 7.5 bits)
- Binary data detected
- Very small messages (< 50 bytes)
- Expected ratio: 1.0x (no compression)

## Performance Characteristics

### Accuracy
- Template detection: ~80% precision (when templates available)
- Method selection: ~75% optimal choice rate
- Confidence calibration: ±0.15 typical deviation

### Latency
- Feature extraction: ~0.05ms
- Prediction: ~0.02ms
- Total overhead: ~0.07ms per message

### Memory Usage
- Model size: ~50KB (cached features)
- Runtime memory: ~5MB (statistics + history)
- Scales linearly with unique feature patterns

## Online Learning

The selector continuously improves through:

1. **Result Recording**: Track actual compression ratios
2. **Feature Correlation**: Learn which features predict good compression
3. **Method Statistics**: Update per-method performance averages
4. **Weight Adjustment**: Gradually adjust scoring weights

**Learning Rate:**
- Adapts over first 1,000 messages
- Converges to stable performance
- Periodic model saving (every 100 results)

## Integration Example

```python
from aura_compression.ml_algorithm_selector import MLAlgorithmSelector

# Initialize selector
selector = MLAlgorithmSelector(
    model_path=".aura_cache/ml_model.json",
    enable_training=True
)

# Predict best method
prediction = selector.predict(message_text)
print(f"Use {prediction.method} (confidence: {prediction.confidence:.2f})")
print(f"Expected ratio: {prediction.expected_ratio:.2f}x")
print(f"Reasoning: {prediction.reasoning}")

# Record actual result
selector.record_result(message_text, compression_result)

# Save learned model
selector.save_model()
```

## Configuration

### Model Persistence
- **Location**: `.aura_cache/ml_model.json`
- **Format**: JSON with statistics and weights
- **Auto-save**: Every 100 compression results

### Training Control
- `enable_training=True`: Online learning enabled
- `enable_training=False`: Use fixed model only

## Limitations

1. **No External ML Libraries**: Uses heuristic scoring, not neural networks
2. **Limited to Message Features**: Can't learn complex patterns
3. **Cold Start**: Needs ~100 messages to calibrate
4. **Single-threaded Training**: Lock contention on model updates

## Future Improvements

- Integration with actual ML models (scikit-learn, TensorFlow)
- Multi-armed bandit approach for exploration
- Feature engineering from compression results
- Workload-specific model adaptation

## Related Components

- [compression_strategy_manager.md](compression_strategy_manager.md) - Uses predictions for method selection
- [metadata_sidechannel.md](../perf/metadata_sidechannel.md) - Fast-path routing decisions
- [strategy_scorer.md](../perf/strategy_scorer.md) - Lightweight scorer for borderline payloads
- [templates.md](templates.md) - Template matching for binary semantic

## References

- [Task 11](../../ai_collaboration.md#task-11) - Scorer performance benchmarks
- Network simulation validation: 1,758 messages, 75% optimal selection rate
