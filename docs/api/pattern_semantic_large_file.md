# Pattern Semantic Large File Compressor API Reference

## Overview

The `pattern_semantic_large_file.py` module provides pattern-based semantic compression optimized for large files (>1MB) with repeating structures. It uses regex pattern recognition, frequency-based dictionary building, and context-aware encoding to achieve high compression ratios on structured data.

**Note**: Despite the filename's historical reference to "AI", this module uses deterministic pattern matching (regex + dictionary + zlib), not machine learning.

## Use Cases

Best suited for:
- **Source code files** - Identifies function signatures, imports, common structures
- **Log files** - Recognizes timestamps, log levels, repeating messages
- **Large JSON/XML** - Compresses nested structures and repeated keys
- **Configuration files** - Captures repeated key-value patterns

**Not recommended for**:
- Binary files (images, videos)
- Already compressed files
- Files < 1MB (overhead not worth it)
- Real-time streaming (requires full file in memory)

## Classes

### PatternSemanticCompressor

Main compression engine for large files with semantic understanding.

#### Constructor

```python
PatternSemanticCompressor(aggressive: bool = False)
```

**Parameters:**
- `aggressive` (bool): Use aggressive optimization (slower but better compression, default: False)
  - Normal mode: Patterns up to 50 characters, top 200 patterns
  - Aggressive mode: Patterns up to 100 characters, more thorough analysis

**Example:**
```python
from aura_compression.pattern_semantic_large_file import PatternSemanticCompressor

# Standard mode (recommended)
compressor = PatternSemanticCompressor()

# Aggressive mode (maximum compression)
compressor = PatternSemanticCompressor(aggressive=True)
```

#### Attributes

- `aggressive` (bool): Whether aggressive optimization is enabled
- `dictionary` (Dict[int, AIDictEntry]): Pattern dictionary built during compression
- `next_token_id` (int): Next available token ID (starts at 256)
- `file_type` (str): Detected file type ('code', 'log', 'data', 'generic')

---

## Methods

### compress(data)

Compress data using pattern-based semantic compression.

```python
def compress(self, data: str) -> Tuple[bytes, CompressionStats]:
```

**Algorithm**:
1. Detect file type (code, log, data, generic)
2. Mine patterns specific to detected type
3. Build adaptive frequency-based dictionary
4. Encode data using pattern references
5. Apply zlib compression on encoded result

**Parameters:**
- `data` (str): Input text to compress

**Returns:**
- `Tuple[bytes, CompressionStats]`:
  - `bytes`: Compressed data with header `[4 bytes: dict_size][compressed_data]`
  - `CompressionStats`: Detailed compression statistics

**Example:**
```python
compressor = PatternSemanticCompressor()

with open('large_file.py', 'r') as f:
    data = f.read()

compressed, stats = compressor.compress(data)

print(f"Original size: {stats.original_size} bytes")
print(f"Compressed size: {stats.compressed_size} bytes")
print(f"Compression ratio: {stats.ratio:.2f}:1")
print(f"Patterns found: {stats.patterns_found}")
```

**Performance:**
- **Speed**: ~5-15 MB/s depending on pattern complexity
- **Memory**: ~2-3x file size during compression
- **Ratio**: 5:1 to 50:1+ (highly data-dependent)

---

### decompress(compressed)

Decompress pattern-semantic compressed data.

```python
def decompress(self, compressed: bytes) -> str:
```

**Parameters:**
- `compressed` (bytes): Compressed data from `compress()`

**Returns:**
- `str`: Original decompressed text

**Raises:**
- `struct.error`: If compressed data is corrupted or invalid
- `zlib.error`: If zlib decompression fails

**Example:**
```python
compressor = PatternSemanticCompressor()

# Compress
compressed, stats = compressor.compress(original_data)

# Decompress
decompressed = compressor.decompress(compressed)

assert decompressed == original_data  # Lossless compression
```

**Performance:**
- **Speed**: ~20-50 MB/s (2-5x faster than compression)
- **Memory**: ~2x file size during decompression

---

## Supporting Classes

### AIDictEntry

Represents a single pattern in the compression dictionary.

**Attributes:**
- `pattern` (str): The text pattern
- `token_id` (int): Unique token ID (256+)
- `frequency` (int): Number of occurrences in data
- `context` (str): Domain context ('code', 'log', 'data', etc.)
- `savings` (int): Bytes saved per use (pattern length - 2)

**Example:**
```python
entry = AIDictEntry(
    pattern="function ",
    token_id=256,
    frequency=47,
    context="code"
)
print(f"Savings: {entry.savings * entry.frequency} bytes")
```

---

### CompressionStats

Detailed statistics about compression operation.

**Attributes:**
- `original_size` (int): Original data size in bytes
- `compressed_size` (int): Compressed data size in bytes
- `ratio` (float): Compression ratio (original / compressed)
- `patterns_found` (int): Number of patterns in dictionary
- `dictionary_size` (int): Dictionary size in bytes
- `method` (str): Compression method ('PATTERN_SEMANTIC')
- `semantic_chunks` (int): Number of semantic chunks (currently always 1)
- `ai_optimizations` (int): Number of pattern optimizations applied

**Example:**
```python
compressed, stats = compressor.compress(data)

print(f"Ratio: {stats.ratio:.2f}:1")
print(f"Space saved: {stats.original_size - stats.compressed_size} bytes")
print(f"Patterns: {stats.patterns_found}")
print(f"Dictionary overhead: {stats.dictionary_size} bytes")
```

---

## Internal Methods

### _detect_file_type(data)

Automatically detect file type using pattern matching.

```python
def _detect_file_type(self, data: str) -> str:
```

**Detection Patterns:**
- **Code**: Looks for `function`, `class`, `import`, `def`, `const`, `var`
- **Log**: Looks for timestamps `2024-01-01 12:00:00`, log levels `[INFO]`
- **Data**: Looks for JSON objects `{...}`, XML tags `<...>`, YAML keys `key:`

**Returns:**
- `str`: One of 'code', 'log', 'data', 'generic'

**Example:**
```python
compressor = PatternSemanticCompressor()
file_type = compressor._detect_file_type("function main() { ... }")
# Returns: 'code'
```

---

### _mine_patterns(data)

Discover repeating patterns in data using n-gram analysis.

```python
def _mine_patterns(self, data: str) -> List[Tuple[str, int]]:
```

**Algorithm:**
1. Extract all substrings (n-grams) from MIN_PATTERN_LENGTH to max_len
2. Count frequency of each n-gram
3. Calculate compression value: `(pattern_length - 2) * frequency`
4. Rank by compression value
5. Select top patterns avoiding overlaps
6. Return up to 200 best patterns

**Parameters:**
- `data` (str): Input text to analyze

**Returns:**
- `List[Tuple[str, int]]`: List of (pattern, frequency) tuples

**Configuration Constants:**
- `MIN_PATTERN_LENGTH` = 8 characters
- `MIN_PATTERN_FREQUENCY` = 3 occurrences
- `max_len` = 50 (normal) or 100 (aggressive)
- Max dictionary = 200 patterns

---

### _build_dictionary(patterns)

Build compression dictionary from discovered patterns.

```python
def _build_dictionary(self, patterns: List[Tuple[str, int]]) -> None:
```

**Parameters:**
- `patterns` (List[Tuple[str, int]]): Output from `_mine_patterns()`

**Side Effects:**
- Populates `self.dictionary` with AIDictEntry objects
- Assigns unique token IDs starting from 256

---

### _encode_semantic(data)

Encode data using pattern dictionary.

```python
def _encode_semantic(self, data: str) -> bytes:
```

**Encoding Format:**
- Patterns replaced with: `[0xFF][token_id_high][token_id_low]`
- Literal bytes: `[byte]` (if byte < 0xFF) or `[0xFF][0xFF][byte]` (if byte == 0xFF)

**Parameters:**
- `data` (str): Text to encode

**Returns:**
- `bytes`: Encoded data with pattern references

---

### _decode_semantic(data)

Decode pattern-encoded data.

```python
def _decode_semantic(self, data: bytes) -> str:
```

**Parameters:**
- `data` (bytes): Encoded data from `_encode_semantic()`

**Returns:**
- `str`: Decoded text with patterns expanded

---

### _serialize_dictionary() / _deserialize_dictionary(data)

Serialize/deserialize compression dictionary for storage.

```python
def _serialize_dictionary(self) -> bytes:
def _deserialize_dictionary(self, data: bytes) -> None:
```

**Format:** JSON encoded as UTF-8 bytes
```json
{
  "256": "pattern1",
  "257": "pattern2",
  ...
}
```

---

## Compression Format

### File Header
```
[4 bytes: dictionary_size (uint32 big-endian)]
[N bytes: zlib compressed (encoded_data + dictionary)]
```

### Encoded Data Format
```
For each byte/pattern:
  - If literal byte < 0xFF: [byte]
  - If literal byte == 0xFF: [0xFF][0xFF][byte]
  - If pattern reference: [0xFF][token_high][token_low]
```

### Dictionary Format (appended to encoded data)
```json
{
  "token_id": "pattern_text",
  ...
}
```

---

## Performance Characteristics

### Compression Speed
- **Normal mode**: ~10-15 MB/s
- **Aggressive mode**: ~5-10 MB/s
- **Pattern mining**: O(n * m) where n=data length, m=max pattern length

### Memory Usage
- **Compression**: ~2-3x file size
  - Original data in memory
  - Pattern dictionary
  - Encoded output buffer
- **Decompression**: ~2x file size
  - Compressed data
  - Decompressed output

### Compression Ratios (Typical)
- **Source code**: 5:1 to 10:1
- **Log files**: 10:1 to 20:1
- **JSON/XML**: 8:1 to 15:1
- **Highly repetitive**: 50:1 to 300:1+
- **Random data**: ~1:1 (no benefit)

---

## Limitations

1. **Memory constraints**: Entire file must fit in memory (2-3x)
2. **Not streaming**: Cannot compress in chunks (requires full file)
3. **Overhead for small files**: Dictionary overhead not worth it for <1MB
4. **Pattern-dependent**: Performance varies wildly based on data structure
5. **Single-threaded**: No parallel processing

---

## Best Practices

### When to Use
✅ **Use for:**
- Large structured files (>1MB)
- Repetitive patterns (code, logs, config)
- Long-term storage (compression time acceptable)
- Known structured formats

❌ **Avoid for:**
- Small files (<1MB)
- Binary data (images, videos)
- Already compressed data
- Real-time streaming
- Memory-constrained environments

### Optimization Tips

1. **Choose aggressive mode for maximum compression**:
```python
compressor = PatternSemanticCompressor(aggressive=True)
```

2. **Batch process multiple files** to amortize initialization:
```python
compressor = PatternSemanticCompressor()
for file_path in file_list:
    data = read_file(file_path)
    compressed, stats = compressor.compress(data)
    save_compressed(file_path + '.aura', compressed)
```

3. **Monitor compression stats** to validate effectiveness:
```python
compressed, stats = compressor.compress(data)
if stats.ratio < 2.0:
    # Low ratio, consider using different method
    use_traditional_compression(data)
else:
    save_compressed(compressed)
```

---

## Integration with AURA System

The Pattern Semantic Compressor is automatically used by the main AURA system for large files:

```python
from aura_compression import ProductionHybridCompressor

compressor = ProductionHybridCompressor()

# For large files (>1MB), PATTERN_SEMANTIC is automatically selected
large_data = read_large_file('big_file.json')
compressed, method, metadata = compressor.compress(large_data)

print(f"Method: {method.name}")  # PATTERN_SEMANTIC
print(f"Ratio: {metadata['ratio']:.2f}:1")
```

**Selection Criteria** in `CompressionStrategyManager`:
- File size > 1MB
- Structured content detected
- Pattern repetition likelihood > 30%

---

## Examples

### Example 1: Compress Python Source Code

```python
from aura_compression.pattern_semantic_large_file import PatternSemanticCompressor

# Read Python file
with open('large_module.py', 'r') as f:
    source_code = f.read()

# Compress
compressor = PatternSemanticCompressor()
compressed, stats = compressor.compress(source_code)

# Save
with open('large_module.py.aura', 'wb') as f:
    f.write(compressed)

print(f"Original: {stats.original_size:,} bytes")
print(f"Compressed: {stats.compressed_size:,} bytes")
print(f"Ratio: {stats.ratio:.2f}:1")
print(f"Patterns found: {stats.patterns_found}")

# Patterns detected will include:
# - "import "
# - "def "
# - "    " (indentation)
# - Common variable names
# - Function signatures
```

### Example 2: Compress Log Files

```python
# Read log file
with open('app.log', 'r') as f:
    logs = f.read()

# Aggressive compression for maximum ratio
compressor = PatternSemanticCompressor(aggressive=True)
compressed, stats = compressor.compress(logs)

print(f"Detected type: {compressor.file_type}")  # 'log'
print(f"Compression: {stats.ratio:.2f}:1")

# Patterns detected will include:
# - Timestamps: "2024-10-31 12:34:56"
# - Log levels: "[INFO]", "[ERROR]"
# - Common messages
# - Stack trace patterns
```

### Example 3: Batch Compression with Error Handling

```python
import os
from pathlib import Path

compressor = PatternSemanticCompressor()
results = []

for file_path in Path('data/').glob('*.json'):
    try:
        with open(file_path, 'r') as f:
            data = f.read()

        # Skip small files
        if len(data) < 100000:  # < 100KB
            print(f"Skipping small file: {file_path}")
            continue

        compressed, stats = compressor.compress(data)

        # Only save if compression is worthwhile
        if stats.ratio > 2.0:
            output_path = file_path.with_suffix('.json.aura')
            with open(output_path, 'wb') as f:
                f.write(compressed)

            results.append({
                'file': file_path.name,
                'ratio': stats.ratio,
                'saved': stats.original_size - stats.compressed_size
            })
        else:
            print(f"Poor compression for {file_path}: {stats.ratio:.2f}:1")

    except Exception as e:
        print(f"Error processing {file_path}: {e}")

# Summary
total_saved = sum(r['saved'] for r in results)
avg_ratio = sum(r['ratio'] for r in results) / len(results)
print(f"\nProcessed {len(results)} files")
print(f"Average ratio: {avg_ratio:.2f}:1")
print(f"Total space saved: {total_saved:,} bytes")
```

---

## See Also

- [Compression Engine API](compression_engine.md) - Low-level compression methods
- [Compression Strategy Manager API](compression_strategy_manager.md) - Method selection
- [Architecture](../architecture.md) - System overview

---

**Last Updated**: 2025-10-31
**Module**: `src/aura_compression/pattern_semantic_large_file.py`
**Status**: Production-ready for large file compression
