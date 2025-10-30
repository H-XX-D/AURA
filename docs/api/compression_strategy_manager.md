# Compression Strategy Manager API Reference

## Overview

The `compression_strategy_manager.py` module implements the strategy pattern for AURA compression, providing intelligent algorithm selection and execution orchestration.

## Classes

### CompressionStrategyManager

Manages multiple compression strategies and selects the optimal one based on content analysis.

#### Constructor

```python
CompressionStrategyManager(
    compression_engine: CompressionEngine,
    performance_optimizer: Optional[PerformanceOptimizer] = None,
    enable_ml_selection: bool = True
)
```

**Parameters:**
- `compression_engine`: Core compression engine instance
- `performance_optimizer`: ML-based performance optimizer (optional)
- `enable_ml_selection`: Enable ML-based algorithm selection (default: True)

## Methods

### compress(text, context=None)

Compress text using the optimal strategy.

```python
def compress(self, text: str, context: Optional[Dict[str, Any]] = None) -> Tuple[bytes, dict]:
```

**Parameters:**
- `text`: Input text to compress
- `context`: Optional context information (network conditions, message type, etc.)

**Returns:**
- `Tuple[bytes, dict]`: (compressed_data, metadata)

### decompress(data)

Decompress data using the appropriate strategy.

```python
def decompress(self, data: bytes) -> Tuple[str, dict]:
```

**Parameters:**
- `data`: Compressed data with method marker

**Returns:**
- `Tuple[str, dict]`: (decompressed_text, metadata)

### get_available_strategies()

Get list of available compression strategies.

```python
def get_available_strategies(self) -> List[str]:
```

**Returns:**
- `List[str]`: List of strategy names

### select_strategy(text, context=None)

Select the optimal compression strategy for given text.

```python
def select_strategy(self, text: str, context: Optional[Dict[str, Any]] = None) -> str:
```

**Parameters:**
- `text`: Input text for analysis
- `context`: Optional context information

**Returns:**
- `str`: Selected strategy name

## Strategy Selection Logic

### 1. Template Matching Priority
```python
# Highest priority: Template-based compression
if template_match := self._find_template_match(text):
    return "binary_semantic"
```

### 2. ML-Based Selection (if enabled)
```python
# Use performance optimizer for intelligent selection
if self.enable_ml_selection and self.performance_optimizer:
    return self.performance_optimizer.predict_optimal_method(text, context)
```

### 3. Size-Based Selection
```python
# Size-based strategy selection
if len(text) < 100:
    return "uncompressed"  # Too small to benefit
elif len(text) < 1000:
    return "aura_lite"     # Small messages
else:
    return "brio"          # Large messages
```

### 4. Context-Aware Selection
```python
# Network condition adaptation
if context.get('network') == 'poor':
    return "aura_lite"  # Faster compression for poor networks
elif context.get('priority') == 'speed':
    return "uncompressed"  # Maximum speed
```

## Usage Examples

### Basic Strategy Manager Setup

```python
from aura_compression.compression_strategy_manager import CompressionStrategyManager
from aura_compression.compression_engine import CompressionEngine

# Initialize components
engine = CompressionEngine(template_library=template_lib)
manager = CompressionStrategyManager(
    compression_engine=engine,
    enable_ml_selection=True
)

# Compress with automatic strategy selection
compressed, metadata = manager.compress("Hello World")
print(f"Selected strategy: {metadata['method']}")
print(f"Compression ratio: {metadata['ratio']:.2f}x")
```

### Context-Aware Compression

```python
# Compress with network context
context = {
    'network': 'poor',      # poor, moderate, good, excellent
    'message_type': 'chat', # chat, code, json, etc.
    'priority': 'balanced'  # speed, ratio, balanced
}

compressed, metadata = manager.compress(text, context=context)
```

### Manual Strategy Selection

```python
# Get available strategies
strategies = manager.get_available_strategies()
print("Available strategies:", strategies)

# Select specific strategy
best_strategy = manager.select_strategy(text, context)
print(f"Recommended strategy: {best_strategy}")
```

## Performance Characteristics

### Strategy Performance Matrix

| Strategy | Best For | Typical Ratio | Speed | Use Case |
|----------|----------|---------------|-------|----------|
| binary_semantic | Repetitive text | 5-6:1 | Fast | Logs, structured data |
| aura_lite | General text | 2-4:1 | Fast | Chat, documents |
| brio_tcp | Small messages | 3-5:1 | Fast | < 2KB messages |
| brio_full | Large messages | 10-37:1+ | Slower | Files, large content |
| aura_heavy | Maximum ratio | 20-55:1+ | Slowest | Archive compression |
| uncompressed | Speed priority | 1:1 | Instant | Real-time, incompressible |

### Selection Performance

- **Template matching**: ~0.01ms (hash-based lookup)
- **ML prediction**: ~0.1ms (lightweight model)
- **Size-based**: ~0.001ms (instant)
- **Context analysis**: ~0.05ms (rule-based)

## Error Handling

The strategy manager provides graceful fallbacks:

```python
try:
    compressed, metadata = manager.compress(text, context)
except Exception as e:
    # Automatic fallback to uncompressed
    logger.warning(f"Compression failed, using uncompressed: {e}")
    compressed, metadata = engine.compress_uncompressed(text)
```

## Dependencies

- `aura_compression.compression_engine`: Core compression logic
- `aura_compression.performance_optimizer`: ML-based selection
- `aura_compression.templates`: Template matching
- `typing`: Type hints
- `logging`: Error logging