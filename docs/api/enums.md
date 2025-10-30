# Compression Enums and Constants

Core enumerations and constants used throughout the AURA compression system.

## CompressionMethod Enum

Defines the available compression methods in the AURA system.

```python
class CompressionMethod(Enum):
    BINARY_SEMANTIC = 0x00  # Template-based compression
    AURALITE = 0x01        # AuraLite compression
    BRIO = 0x02           # BRIO entropy coding
    AURA_LITE = 0x03      # Legacy: use AURALITE instead
    AURA_HEAVY = 0x04     # Hybrid high-compression
    UNCOMPRESSED = 0xFF   # No compression applied
```

### Method Descriptions

#### `BINARY_SEMANTIC` (0x00)
**Template-based compression** for ultra-compact storage of repetitive data.

- **Use Case**: AI assistant responses, log messages, structured data
- **Compression Ratio**: 5.38-6.00:1 on log data
- **Performance**: Fast encoding/decoding with template matching
- **Format**: `[method_byte][template_id][slot_count][slot_data...]`

**Example:**
```python
# Template 200: "Error: Connection timeout after {0} seconds"
# Compress: "Error: Connection timeout after 120 seconds"
# Result: 0x00 0xC8 0x01 [2 bytes length] [data]
```

#### `AURALITE` (0x01)
**Proprietary AURA-based compression** optimized for AI communications.

- **Use Case**: General-purpose compression for AI chat, code, and text
- **Compression Ratio**: 1.01-1.02:1 (minimal expansion for incompressible data)
- **Performance**: Balanced speed and ratio
- **Features**: Template awareness, dictionary compression

#### `BRIO` (0x02)
**BRIO entropy coding** with rANS (range Asymmetric Numeral Systems).

- **Use Case**: Large messages requiring high compression ratios
- **Compression Ratio**: Up to 55:1+ on large semantic data
- **Performance**: Higher computational cost, excellent for large data
- **Features**: rANS entropy coding, LZ77 tokenization, template awareness

#### `AURA_LITE` (0x03) - *Legacy*
**Deprecated**: Use `AURALITE` instead.

Legacy template + dictionary + literals compression method.

#### `AURA_HEAVY` (0x04)
**Hybrid semantic + traditional compression** for maximum ratios.

- **Use Case**: Maximum compression regardless of computational cost
- **Compression Ratio**: 37.39:1 demonstrated on large text
- **Performance**: Highest computational cost
- **Features**: Combines multiple techniques for optimal compression

#### `UNCOMPRESSED` (0xFF)
**No compression applied** - data stored as-is.

- **Use Case**: Messages below minimum size threshold or incompressible data
- **Compression Ratio**: 1.0:1 (no change)
- **Performance**: Minimal overhead
- **Format**: `[method_byte][original_data]`

## Constants

### Metadata Constants

#### `TEMPLATE_METADATA_KIND = 0x01`
Metadata kind identifier for template-based compression in the wire format.

Used in the 6-byte metadata header to indicate template substitution.

### Semantic Processing Constants

#### `_SEMANTIC_PREVIEW_LIMIT = 160`
Maximum characters to preview for semantic analysis.

Limits the text preview used for semantic token extraction and classification.

#### `_SEMANTIC_TOKEN_LIMIT = 5`
Maximum number of semantic tokens to extract from text.

Controls how many significant tokens are extracted for semantic processing.

#### `_SEMANTIC_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_]+")`
Regular expression pattern for extracting semantic tokens.

Matches alphanumeric characters and underscores for token identification.

## Usage Examples

### Method Detection
```python
from aura_compression.enums import CompressionMethod

def get_method_name(data: bytes) -> str:
    method_byte = data[0]
    try:
        method = CompressionMethod(method_byte)
        return method.name
    except ValueError:
        return f"UNKNOWN_0x{method_byte:02X}"

# Example usage
compressed_data = b'\x00\xC8\x01...'  # BINARY_SEMANTIC
print(get_method_name(compressed_data))  # "BINARY_SEMANTIC"
```

### Method Selection Logic
```python
from aura_compression.enums import CompressionMethod

def select_compression_method(text: str, size_threshold: int = 1000) -> CompressionMethod:
    if len(text) < 50:
        return CompressionMethod.UNCOMPRESSED
    elif len(text) < size_threshold:
        return CompressionMethod.AURALITE
    else:
        return CompressionMethod.BRIO

# Example usage
method = select_compression_method("Hello World", 1000)
print(f"Selected: {method.name}")  # "UNCOMPRESSED"
```

### Wire Format Parsing
```python
from aura_compression.enums import CompressionMethod, TEMPLATE_METADATA_KIND

def parse_wire_format(data: bytes) -> dict:
    """Parse AURA wire format"""
    if len(data) < 6:
        raise ValueError("Invalid wire format: too short")

    # Parse metadata header (6 bytes)
    metadata_kind = data[0]
    metadata_payload = data[1:6]
    payload = data[6:]

    result = {
        'metadata_kind': metadata_kind,
        'metadata_payload': metadata_payload,
        'payload': payload
    }

    # Parse method if it's a compression result
    if metadata_kind == TEMPLATE_METADATA_KIND:
        template_id = int.from_bytes(metadata_payload, 'big')
        result['template_id'] = template_id
    else:
        # It's compressed data, method is in payload
        if payload:
            method_byte = payload[0]
            try:
                method = CompressionMethod(method_byte)
                result['method'] = method
            except ValueError:
                result['method'] = f"UNKNOWN_0x{method_byte:02X}"

    return result

# Example usage
wire_data = bytes([0x01, 0x00, 0x00, 0x00, 0xC8]) + compressed_payload
parsed = parse_wire_format(wire_data)
print(f"Template ID: {parsed.get('template_id')}")
```

## Method Characteristics

| Method | Ratio Range | Speed | Use Case | Overhead |
|--------|-------------|-------|----------|----------|
| BINARY_SEMANTIC | 5.38-6.00:1 | Fast | Repetitive data | Low |
| AURALITE | 1.01-1.02:1 | Medium | General AI text | Medium |
| BRIO | 4.3-55:1+ | Slow | Large messages | High |
| AURA_HEAVY | 37.39:1+ | Slowest | Maximum compression | Highest |
| UNCOMPRESSED | 1.0:1 | Fastest | Small/incompressible | Minimal |

## Migration Notes

### From AURA_LITE to AURALITE
```python
# Old code (deprecated)
method = CompressionMethod.AURA_LITE

# New code (recommended)
method = CompressionMethod.AURALITE
```

### AURA-Only Philosophy
The system follows **AURA-only compression** with no standard compression fallbacks:

- ✅ **AURA methods only** (no GZIP/BZ2/LZMA fallbacks)
- ✅ **Guaranteed no expansion** (ratios ≥ 1.0)
- ✅ **Semantic awareness** in all compression methods
- ✅ **Template integration** across all methods

## Error Handling

```python
from aura_compression.enums import CompressionMethod

def safe_method_from_byte(byte_value: int) -> CompressionMethod:
    """Safely convert byte to CompressionMethod with fallback"""
    try:
        return CompressionMethod(byte_value)
    except ValueError:
        # Unknown method, treat as uncompressed
        return CompressionMethod.UNCOMPRESSED

# Example usage
method_byte = 0x99  # Unknown method
safe_method = safe_method_from_byte(method_byte)
print(f"Safe method: {safe_method.name}")  # "UNCOMPRESSED"
```

---

**Module**: `aura_compression.enums`  
**Version**: 2.0.0  
**Last Updated**: October 30, 2025