# ProductionHybridCompressor

The main compression orchestration system for the AURA compression framework.

## Overview

`ProductionHybridCompressor` is the primary interface for compressing and decompressing data using the AURA compression system. It provides intelligent algorithm selection, template matching, and performance optimization through a modular architecture.

## Class Signature

```python
class ProductionHybridCompressor:
    def __init__(self,
                 binary_advantage_threshold: float = 1.01,
                 min_compression_size: int = 10,
                 enable_aura: Optional[bool] = None,
                 aura_preference_margin: float = 0.05,
                 enable_audit_logging: bool = False,
                 audit_log_directory: str = "./audit_logs",
                 session_id: Optional[str] = None,
                 user_id: Optional[str] = None,
                 template_store_path: Optional[str] = None,
                 template_cache_size: int = 128,
                 enable_normalization: bool = True,
                 tcp_brio_threshold: int = 1000,
                 enable_fast_path: bool = True,
                 enable_sidechain: Optional[bool] = None,
                 sidechain_config: Optional[Dict[str, Any]] = None,
                 enable_ml_selection: bool = False,
                 enable_scorer: Optional[bool] = None,
                 scorer_telemetry_path: Optional[str] = None,
                 template_sync_interval_seconds: Optional[int] = 60,
                 template_cache_dir: str = ".aura_cache")
```

## Parameters

### Core Settings
- **`binary_advantage_threshold`** *(float, default=1.01)*: Minimum compression ratio required for binary semantic compression
- **`min_compression_size`** *(int, default=10)*: Minimum message size for compression (smaller messages remain uncompressed)
- **`enable_aura`** *(Optional[bool])*: Enable AURA-only compression methods (auto-detected from `AURA_ENABLE_EXPERIMENTAL` env var)
- **`aura_preference_margin`** *(float, default=0.05)*: Preference margin for AURA methods over standard compression

### Audit & Logging
- **`enable_audit_logging`** *(bool, default=False)*: Enable GDPR/HIPAA/SOC2 compliant audit logging
- **`audit_log_directory`** *(str, default="./audit_logs")*: Directory for audit log files
- **`session_id`** *(Optional[str])*: Session identifier for audit trails
- **`user_id`** *(Optional[str])*: User identifier for audit trails

### Template System
- **`template_store_path`** *(Optional[str])*: Path to persistent template storage
- **`template_cache_size`** *(int, default=128)*: Maximum number of templates to cache in memory
- **`enable_normalization`** *(bool, default=True)*: Enable text normalization for better template matching
- **`template_sync_interval_seconds`** *(Optional[int], default=60)*: Period between automatic template store syncs (`None` disables periodic sync)
- **`template_cache_dir`** *(str, default=".aura_cache")*: Directory used for persistent template cache storage

### Performance & Acceleration
- **`tcp_brio_threshold`** *(int, default=1000)*: Size threshold for TCP-optimized BRIO vs full BRIO
- **`enable_fast_path`** *(bool, default=True)*: Enable fast-path template matching cache
- **`enable_sidechain`** *(Optional[bool])*: Enable metadata sidechannel routing (auto-detected from `AURA_ENABLE_SIDECHAIN` env var)

### Learning & Telemetry
- **`enable_ml_selection`** *(bool, default=False)*: Enable ML-based algorithm selection for borderline payloads
- **`enable_scorer`** *(Optional[bool])*: Force-enable or disable the lightweight scorer (defaults to env/config)
- **`scorer_telemetry_path`** *(Optional[str])*: Custom file path for scorer telemetry CSV output

## Methods

### Core Compression

#### `compress(text: str) -> Tuple[bytes, CompressionMethod, Dict[str, Any]]`
Compress text using the best available algorithm.

**Parameters:**
- `text` *(str)*: Text to compress

**Returns:**
- `compressed_data` *(bytes)*: Compressed binary data
- `method` *(CompressionMethod)*: Compression method used
- `metadata` *(Dict)*: Compression metadata including ratio, size, etc.

**Example:**
```python
compressor = ProductionHybridCompressor(enable_aura=True)
compressed, method, metadata = compressor.compress("Hello World")

print(f"Method: {method.name}")
print(f"Ratio: {metadata['ratio']:.2f}x")
print(f"Original size: {metadata['original_size']} bytes")
print(f"Compressed size: {metadata['compressed_size']} bytes")
```

#### `decompress(data: bytes) -> str`
Decompress binary data back to original text.

**Parameters:**
- `data` *(bytes)*: Compressed binary data

**Returns:**
- `text` *(str)*: Decompressed original text

**Example:**
```python
original = compressor.decompress(compressed)
print(f"Decompressed: {original}")
```

### Template Operations

#### `compress_with_template(template_id: int, slots: List[str]) -> Tuple[bytes, CompressionMethod, Dict[str, Any]]`
Compress text using a specific template with provided slot values.

**Parameters:**
- `template_id` *(int)*: Template identifier
- `slots` *(List[str])*: Values for template slots

**Returns:**
- Same as `compress()` method

**Example:**
```python
# Template 0: "I don't have access to {0}. {1}"
compressed, method, metadata = compressor.compress_with_template(
    0, ["real-time data", "some reason"]
)
```

### Template Management

#### `add_template(template_id: int, pattern: str, description: str = "", slots: int = 0)`
Add a custom template to the library.

**Parameters:**
- `template_id` *(int)*: Unique template identifier
- `pattern` *(str)*: Template pattern with {0}, {1}, etc. placeholders
- `description` *(str, optional)*: Human-readable description
- `slots` *(int, default=0)*: Number of slots in the template

**Example:**
```python
compressor.add_template(
    1001,
    "The weather in {city} is {condition}",
    "Weather information template",
    2
)
```

#### `get_template(template_id: int) -> Optional[Dict[str, Any]]`
Retrieve template information by ID.

**Parameters:**
- `template_id` *(int)*: Template identifier

**Returns:**
- Template information or None if not found

### Performance & Statistics

#### `get_compression_stats() -> Dict[str, Any]`
Get compression performance statistics.

**Returns:**
- Dictionary with compression statistics including ratios, speeds, method usage, etc.

**Example:**
```python
stats = compressor.get_compression_stats()
print(f"Average ratio: {stats['avg_ratio']:.2f}x")
print(f"Total messages: {stats['total_messages']}")
print(f"Cache hit rate: {stats['cache_hit_rate']:.1%}")
```

#### `reset_stats()`
Reset compression statistics counters.

### Audit & Compliance

#### `enable_audit_logging(enable: bool, directory: Optional[str] = None)`
Enable or disable audit logging.

**Parameters:**
- `enable` *(bool)*: Whether to enable audit logging
- `directory` *(Optional[str])*: Directory for audit logs

### Advanced Configuration

#### `set_performance_mode(mode: str)`
Set performance optimization mode.

**Parameters:**
- `mode` *(str)*: Performance mode ("speed", "ratio", "balanced")

#### `enable_accelerator(accelerator_type: str, enable: bool)`
Enable or disable specific accelerators.

**Parameters:**
- `accelerator_type` *(str)*: Accelerator type ("simd", "gpu", "hardware")
- `enable` *(bool)*: Whether to enable the accelerator

## Architecture

The compressor uses a modular architecture with the following components:

```
ProductionHybridCompressor
├── CompressionEngine (core compression logic)
├── CompressionStrategyManager (algorithm selection)
├── TemplateManager (template lifecycle)
├── PerformanceOptimizer (hardware acceleration)
├── MLAlgorithmSelector (intelligent selection)
├── StorageManager (sidechannel persistence)
├── AuditService (compliance logging)
└── MetadataSidechannel (fast-path routing)
```

## Compression Methods

The system supports multiple AURA-only compression methods:

1. **BINARY_SEMANTIC**: Template-based compression (ultra-compact for repetitive data)
2. **AURALITE**: Proprietary AURA-based compression (primary method)
3. **AURA_LITE**: Template + dictionary + literals compression (legacy support)
4. **BRIO_FULL**: Full semantic compression with rANS entropy coding (large messages)
5. **BRIO_TCP**: TCP-optimized BRIO for small/medium messages (< 2KB threshold)
6. **AURA_HEAVY**: Hybrid semantic + traditional compression for maximum ratios

## Performance Characteristics

### Latency
- **Small Messages (< 50 bytes)**: 0.03-0.12ms
- **Medium Messages (50-500 bytes)**: 0.18-0.35ms
- **Large Messages (> 500 bytes)**: 0.50-2.0ms

### Compression Ratios
- **AI Conversations**: 4.3:1 average (up to 8.7:1)
- **Code Snippets**: 5.2:1 average (up to 12.1:1)
- **Log Data**: 5.38-6.00:1 with binary semantic compression

### Memory Usage
- **Template Library**: ~50KB (68 default templates)
- **Cache**: 1MB LRU cache for match results
- **ML Model**: 1000 training samples loaded

## Error Handling

The compressor provides robust error handling:

```python
try:
    compressed, method, metadata = compressor.compress(text)
except CompressionError as e:
    logger.error(f"Compression failed: {e}")
    # Fallback to uncompressed
    compressed, method, metadata = compressor.compress_uncompressed(text)
```

## Environment Variables

- **`AURA_ENABLE_EXPERIMENTAL`**: Enable AURA-only compression (default: false)
- **`AURA_ENABLE_SIDECHAIN`**: Enable metadata sidechannel (default: false)
- **`AURA_ENABLE_ML_SELECTION`**: Enable ML-based algorithm selection (default: true)

## Examples

### Basic Usage
```python
from aura_compression import ProductionHybridCompressor

compressor = ProductionHybridCompressor(enable_aura=True)

# Compress
compressed, method, metadata = compressor.compress("Hello World")
print(f"Compressed with {method.name}: {metadata['ratio']:.2f}x")

# Decompress
original = compressor.decompress(compressed)
assert original == "Hello World"
```

### Advanced Configuration
```python
compressor = ProductionHybridCompressor(
    enable_aura=True,
    enable_audit_logging=True,
    audit_log_directory="/var/log/aura",
    enable_gpu=True,
    template_cache_size=256,
    binary_advantage_threshold=1.1
)
```

### Template-Based Compression
```python
# Add custom template
compressor.add_template(
    1001,
    "Error: {message} at {timestamp}",
    "Error message template",
    2
)

# Use template
compressed, method, metadata = compressor.compress_with_template(
    1001, ["Connection timeout", "2025-10-30 15:00:00"]
)
```

---

**Module**: `aura_compression.compressor`  
**Version**: 2.0.0  
**Last Updated**: October 30, 2025
