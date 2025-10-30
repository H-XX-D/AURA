# AURA Compression Engine API Reference

## Overview

The `compression_engine.py` module provides the core compression and decompression logic for the AURA system. It implements multiple compression strategies and handles the orchestration between different compression methods.

## Classes

### CompressionEngine

The main compression engine that coordinates all compression operations.

#### Constructor

```python
CompressionEngine(
    template_library: Any,
    aura_encoder: Optional[BrioEncoder] = None,
    aura_decoder: Optional[BrioDecoder] = None,
    tcp_brio_encoder: Optional[TcpBrioEncoder] = None,
    tcp_brio_decoder: Optional[TcpBrioDecoder] = None,
    aura_lite_encoder: Optional[AuraLiteEncoder] = None,
    aura_lite_decoder: Optional[AuraLiteDecoder] = None,
    tcp_brio_threshold: int = 1000
)
```

**Parameters:**
- `template_library`: Template library instance for pattern matching
- `aura_encoder`: BRIO encoder for full compression
- `aura_decoder`: BRIO decoder for full decompression
- `tcp_brio_encoder`: TCP-optimized BRIO encoder
- `tcp_brio_decoder`: TCP-optimized BRIO decoder
- `aura_lite_encoder`: AURA-Lite encoder
- `aura_lite_decoder`: AURA-Lite decoder
- `tcp_brio_threshold`: Size threshold for TCP vs full BRIO (default: 1000 bytes)

## Methods

### compress_binary_semantic(text, template_match)

Compress using binary semantic compression with templates.

```python
def compress_binary_semantic(self, text: str, template_match: TemplateMatch) -> Tuple[bytes, dict]:
```

**Parameters:**
- `text`: Input text to compress
- `template_match`: TemplateMatch object with template ID and slots

**Returns:**
- `Tuple[bytes, dict]`: (compressed_data, metadata)

**Raises:**
- `ValueError`: If template slots don't match the original text

### decompress_binary_semantic(data)

Decompress binary semantic compression.

```python
def decompress_binary_semantic(self, data: bytes) -> Tuple[str, dict]:
```

**Parameters:**
- `data`: Compressed binary semantic data

**Returns:**
- `Tuple[str, dict]`: (decompressed_text, metadata)

### compress_aura_lite(text)

Compress using AURA-Lite method.

```python
def compress_aura_lite(self, text: str) -> Tuple[bytes, dict]:
```

**Parameters:**
- `text`: Input text to compress

**Returns:**
- `Tuple[bytes, dict]`: (compressed_data, metadata)

### decompress_aura_lite(data)

Decompress AURA-Lite compression.

```python
def decompress_aura_lite(self, data: bytes) -> Tuple[str, dict]:
```

**Parameters:**
- `data`: Compressed AURA-Lite data

**Returns:**
- `Tuple[str, dict]`: (decompressed_text, metadata)

### compress_brio(text, use_tcp=True)

Compress using BRIO (TCP-optimized or full).

```python
def compress_brio(self, text: str, use_tcp: bool = True) -> Tuple[bytes, dict]:
```

**Parameters:**
- `text`: Input text to compress
- `use_tcp`: Use TCP-optimized BRIO for messages < tcp_brio_threshold (default: True)

**Returns:**
- `Tuple[bytes, dict]`: (compressed_data, metadata)

### decompress_brio(data)

Decompress BRIO (automatically detects TCP vs full format).

```python
def decompress_brio(self, data: bytes) -> Tuple[str, dict]:
```

**Parameters:**
- `data`: Compressed BRIO data

**Returns:**
- `Tuple[str, dict]`: (decompressed_text, metadata)

### compress_uncompressed(text)

Return uncompressed data with method marker.

```python
def compress_uncompressed(self, text: str) -> Tuple[bytes, dict]:
```

**Parameters:**
- `text`: Input text (returned as-is with method marker)

**Returns:**
- `Tuple[bytes, dict]`: (data_with_marker, metadata)

## Usage Examples

### Basic Compression Engine Setup

```python
from aura_compression.compression_engine import CompressionEngine
from aura_compression.templates import TemplateLibrary

# Initialize with template library
template_lib = TemplateLibrary()
engine = CompressionEngine(template_library=template_lib)

# Compress text
compressed, metadata = engine.compress_brio("Hello World")
print(f"Ratio: {metadata['ratio']:.2f}x")

# Decompress
original, meta = engine.decompress_brio(compressed)
print(f"Original: {original}")
```

### Template-Based Compression

```python
from aura_compression.templates import TemplateMatch

# Create template match
match = TemplateMatch(
    template_id=0,
    slots=["real-time data", "network timeout"],
    confidence=0.95
)

# Compress with template
compressed, metadata = engine.compress_binary_semantic(
    "I don't have access to real-time data. network timeout",
    match
)
```

## Performance Characteristics

- **Binary Semantic**: Best for repetitive, structured text (5-6:1 ratios)
- **AURA-Lite**: Balanced compression for general text
- **BRIO Full**: Maximum compression for large messages (37:1+ demonstrated)
- **BRIO TCP**: Optimized for small/medium messages (< 2KB threshold)
- **Uncompressed**: Fallback for incompressible content

## Error Handling

All compression methods may raise:
- `ValueError`: Invalid input data or template mismatches
- `TypeError`: Incorrect parameter types

Decompression methods may raise:
- `ValueError`: Corrupted or invalid compressed data
- `UnicodeDecodeError`: Invalid UTF-8 in decompressed data

## Dependencies

- `aura_compression.templates`: Template library
- `aura_compression.brio_full`: BRIO compression
- `aura_compression.auralite`: AURA-Lite compression
- `struct`: Binary data packing/unpacking