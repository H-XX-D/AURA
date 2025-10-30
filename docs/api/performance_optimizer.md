# Performance Optimizer API Reference

## Overview

The `performance_optimizer.py` module provides ML-based algorithm selection and performance optimization for the AURA compression system. It uses machine learning to predict optimal compression methods based on content characteristics and runtime conditions.

## Classes

### PerformanceOptimizer

ML-powered performance optimization and algorithm selection.

#### Constructor

```python
PerformanceOptimizer(
    enable_gpu: bool = False,
    enable_simd: bool = True,
    model_path: Optional[str] = None,
    learning_rate: float = 0.001
)
```

**Parameters:**
- `enable_gpu`: Enable GPU acceleration for ML models (default: False)
- `enable_simd`: Enable SIMD acceleration (default: True)
- `model_path`: Path to pre-trained model (optional)
- `learning_rate`: Learning rate for online learning (default: 0.001)

## Methods

### predict_optimal_method(text, context=None)

Predict the optimal compression method for given text.

```python
def predict_optimal_method(self, text: str, context: Optional[Dict[str, Any]] = None) -> str:
```

**Parameters:**
- `text`: Input text for analysis
- `context`: Optional context (network conditions, message type, etc.)

**Returns:**
- `str`: Optimal compression method name

### analyze_content(text)

Analyze text content characteristics for compression optimization.

```python
def analyze_content(self, text: str) -> Dict[str, Any]:
```

**Parameters:**
- `text`: Text to analyze

**Returns:**
- `Dict[str, Any]`: Content analysis results

**Analysis Features:**
- Text entropy and complexity
- Pattern repetition analysis
- Language detection
- Structural analysis (JSON, code, natural language)
- Compression potential estimation

### optimize_for_network(network_conditions)

Optimize compression strategy for network conditions.

```python
def optimize_for_network(self, network_conditions: Dict[str, Any]) -> Dict[str, Any]:
```

**Parameters:**
- `network_conditions`: Network metrics (latency, bandwidth, packet loss)

**Returns:**
- `Dict[str, Any]`: Optimized compression parameters

### update_model(performance_data)

Update ML model with performance feedback.

```python
def update_model(self, performance_data: Dict[str, Any]) -> None:
```

**Parameters:**
- `performance_data`: Performance metrics from compression operations

### get_performance_metrics()

Get current performance statistics.

```python
def get_performance_metrics(self) -> Dict[str, Any]:
```

**Returns:**
- `Dict[str, Any]`: Performance metrics and statistics

## Content Analysis Features

### Text Characteristics Analysis

```python
analysis = optimizer.analyze_content(text)

# Returns features like:
{
    'entropy': 4.2,           # Text randomness (0-8)
    'pattern_density': 0.15,  # Repeated pattern ratio
    'language': 'en',         # Detected language
    'structure': 'natural',   # natural, code, json, etc.
    'compressibility': 0.75,  # Estimated compression potential (0-1)
    'length_category': 'medium' # tiny, small, medium, large, huge
}
```

### ML-Based Method Selection

The optimizer uses multiple ML models:

1. **Content Classification**: Predicts text type and characteristics
2. **Compression Prediction**: Estimates compression ratios for each method
3. **Performance Modeling**: Predicts compression/decompression speed
4. **Network Adaptation**: Optimizes for network conditions

## Usage Examples

### Basic Performance Optimization

```python
from aura_compression.performance_optimizer import PerformanceOptimizer

# Initialize optimizer
optimizer = PerformanceOptimizer(enable_simd=True)

# Analyze content
analysis = optimizer.analyze_content("Hello world, this is a test message")
print(f"Content type: {analysis['structure']}")
print(f"Compressibility: {analysis['compressibility']:.2f}")

# Get optimal method
method = optimizer.predict_optimal_method("Hello world...", {'network': 'good'})
print(f"Optimal method: {method}")
```

### Network-Aware Optimization

```python
# Network conditions
network = {
    'latency_ms': 50,
    'bandwidth_mbps': 100,
    'packet_loss': 0.001,
    'connection_type': 'wifi'
}

# Get network-optimized settings
optimized = optimizer.optimize_for_network(network)
print(f"Recommended method: {optimized['method']}")
print(f"Chunk size: {optimized['chunk_size']}")
print(f"Priority: {optimized['priority']}")  # speed/ratio/balanced
```

### Performance Feedback Loop

```python
# After compression operation
performance_data = {
    'method': 'brio',
    'original_size': 1000,
    'compressed_size': 300,
    'compression_time_ms': 5.2,
    'decompression_time_ms': 3.1,
    'text_characteristics': analysis,
    'network_conditions': network,
    'success': True
}

# Update model with feedback
optimizer.update_model(performance_data)
```

## Performance Characteristics

### Analysis Speed
- **Content analysis**: ~0.1-0.5ms (depends on text length)
- **Method prediction**: ~0.05ms (ML inference)
- **Network optimization**: ~0.01ms (rule-based)

### Accuracy
- **Method selection**: 85-95% accuracy (based on content features)
- **Ratio prediction**: ±15% accuracy for compression ratio estimates
- **Performance prediction**: ±20% accuracy for timing estimates

### Memory Usage
- **Base model**: ~50MB (lightweight ML models)
- **GPU acceleration**: Additional 100-500MB VRAM (optional)
- **Feature cache**: ~10MB for recent analyses

## ML Models Used

### 1. Content Classifier
- **Input**: Text features (entropy, patterns, structure)
- **Output**: Content type and compressibility score
- **Architecture**: Lightweight neural network or gradient boosting

### 2. Performance Predictor
- **Input**: Content features + network conditions
- **Output**: Predicted compression ratio and speed for each method
- **Architecture**: Ensemble of regression models

### 3. Strategy Optimizer
- **Input**: Performance predictions + constraints
- **Output**: Optimal compression strategy
- **Architecture**: Rule-based with ML refinement

## Hardware Acceleration

### SIMD Acceleration
```python
# Automatic SIMD detection and usage
if optimizer.simd_available():
    # Use SIMD-accelerated feature extraction
    features = optimizer.extract_features_simd(text)
```

### GPU Acceleration
```python
# GPU-accelerated ML inference (optional)
optimizer.enable_gpu_acceleration()
predictions = optimizer.predict_gpu(text_features)
```

## Error Handling

The optimizer provides graceful degradation:

```python
try:
    method = optimizer.predict_optimal_method(text, context)
except Exception as e:
    logger.warning(f"ML prediction failed, using fallback: {e}")
    method = "aura_lite"  # Conservative fallback
```

## Dependencies

- `numpy`: Numerical computations
- `scikit-learn`: ML algorithms (optional)
- `torch`: GPU acceleration (optional)
- `psutil`: System information
- `typing`: Type hints