# SIMD Accelerator API Reference

## Overview

The `simd_accelerator.py` module provides hardware-accelerated compression using SIMD (Single Instruction, Multiple Data) instructions. It optimizes performance for small to medium-sized messages through parallel processing.

## Classes

### SIMDAccelerator

Hardware-accelerated compression using SIMD instructions.

#### Constructor

```python
SIMDAccelerator(
    enable_avx512: bool = True,
    enable_avx2: bool = True,
    enable_sse4: bool = True,
    enable_neon: bool = True,
    chunk_size: int = 64
)
```

**Parameters:**
- `enable_avx512`: Enable AVX-512 instructions (Intel/AMD) (default: True)
- `enable_avx2`: Enable AVX-2 instructions (default: True)
- `enable_sse4`: Enable SSE4 instructions (default: True)
- `enable_neon`: Enable NEON instructions (ARM) (default: True)
- `chunk_size`: SIMD processing chunk size (default: 64)

## Methods

### is_available()

Check if SIMD acceleration is available on this system.

```python
def is_available(self) -> bool:
```

**Returns:**
- `bool`: True if SIMD instructions are available

### get_supported_instructions()

Get list of supported SIMD instruction sets.

```python
def get_supported_instructions(self) -> List[str]:
```

**Returns:**
- `List[str]`: List of supported instruction sets (e.g., ['avx2', 'sse4', 'neon'])

### compress_simd(text)

Compress text using SIMD acceleration.

```python
def compress_simd(self, text: str) -> Tuple[bytes, dict]:
```

**Parameters:**
- `text`: Input text to compress

**Returns:**
- `Tuple[bytes, dict]`: (compressed_data, metadata)

### accelerate_feature_extraction(text)

Accelerate feature extraction for ML optimization.

```python
def accelerate_feature_extraction(self, text: str) -> Dict[str, float]:
```

**Parameters:**
- `text`: Text to analyze

**Returns:**
- `Dict[str, float]`: Accelerated feature extraction results

### parallel_process_chunks(data, func)

Process data chunks in parallel using SIMD.

```python
def parallel_process_chunks(self, data: bytes, func: Callable) -> List[Any]:
```

**Parameters:**
- `data`: Data to process in chunks
- `func`: Function to apply to each chunk

**Returns:**
- `List[Any]`: Results from processing each chunk

## SIMD Instruction Support

### x86/x64 Architecture

```python
# AVX-512 (Intel Skylake-X and later, AMD Zen 4)
if 'avx512' in accelerator.get_supported_instructions():
    # 512-bit vector operations
    result = accelerator.compress_avx512(text)

# AVX-2 (Intel Haswell and later, AMD Excavator)
if 'avx2' in accelerator.get_supported_instructions():
    # 256-bit vector operations
    result = accelerator.compress_avx2(text)

# SSE4 (Intel Penryn and later)
if 'sse4' in accelerator.get_supported_instructions():
    # 128-bit vector operations
    result = accelerator.compress_sse4(text)
```

### ARM Architecture

```python
# NEON (ARMv7 and later, all ARM64)
if 'neon' in accelerator.get_supported_instructions():
    # 128-bit vector operations on ARM
    result = accelerator.compress_neon(text)
```

## Usage Examples

### Basic SIMD Acceleration

```python
from aura_compression.simd_accelerator import SIMDAccelerator

# Initialize accelerator
accelerator = SIMDAccelerator()

# Check availability
if accelerator.is_available():
    print("SIMD acceleration available")
    print("Supported instructions:", accelerator.get_supported_instructions())

    # Compress with SIMD
    compressed, metadata = accelerator.compress_simd("Hello World")
    print(f"SIMD compression ratio: {metadata['ratio']:.2f}x")
else:
    print("SIMD acceleration not available")
```

### Feature Extraction Acceleration

```python
# Accelerate ML feature extraction
features = accelerator.accelerate_feature_extraction(text)

print("Accelerated features:")
for name, value in features.items():
    print(f"  {name}: {value:.3f}")
```

### Parallel Processing

```python
# Process large data in parallel chunks
def process_chunk(chunk):
    # Custom processing function
    return len(chunk), sum(chunk)

results = accelerator.parallel_process_chunks(data, process_chunk)

for i, (length, total) in enumerate(results):
    print(f"Chunk {i}: length={length}, sum={total}")
```

## Performance Characteristics

### Speed Improvements

| Message Size | SIMD Speedup | Use Case |
|--------------|--------------|----------|
| < 100 bytes | 1.5-2.0x | Tiny messages |
| 100-500 bytes | 2.0-3.0x | Small messages |
| 500-2000 bytes | 1.5-2.5x | Medium messages |
| > 2000 bytes | 1.1-1.5x | Large messages |

### Memory Efficiency

- **Zero-copy processing**: SIMD operations work on existing memory
- **Cache-friendly**: Optimized for CPU cache line sizes
- **Memory bandwidth**: Efficient use of memory bandwidth

### CPU Utilization

- **Parallel processing**: Utilizes multiple CPU cores
- **Vector operations**: Processes multiple data elements simultaneously
- **Branch prediction**: Optimized for common compression patterns

## Hardware Detection

### Automatic Detection

```python
# Automatic hardware detection
accelerator = SIMDAccelerator()

# Check what SIMD is available
instructions = accelerator.get_supported_instructions()

if 'avx512' in instructions:
    print("AVX-512 available - maximum performance")
elif 'avx2' in instructions:
    print("AVX-2 available - good performance")
elif 'sse4' in instructions:
    print("SSE4 available - basic SIMD")
else:
    print("No SIMD acceleration available")
```

### ARM NEON Detection

```python
# ARM-specific detection
if accelerator.is_neon_available():
    print("ARM NEON available")
    # Use NEON-optimized routines
    result = accelerator.compress_neon(text)
```

## Integration with Compression Pipeline

### Automatic SIMD Integration

```python
from aura_compression.compressor import ProductionHybridCompressor

# SIMD is automatically used when available
compressor = ProductionHybridCompressor()

# Check if SIMD was used in last compression
if compressor.last_compression_used_simd():
    speedup = compressor.get_simd_speedup()
    print(f"SIMD provided {speedup:.1f}x speedup")
```

### Manual SIMD Control

```python
# Manual SIMD control
compressor.enable_simd(True)
compressor.set_simd_chunk_size(128)

# Compress with SIMD
compressed, metadata = compressor.compress(text)
```

## Error Handling

SIMD operations provide graceful fallbacks:

```python
try:
    result = accelerator.compress_simd(text)
except SIMDNotAvailableError:
    # Fallback to scalar processing
    result = accelerator.compress_scalar(text)
except SIMDProcessingError as e:
    logger.error(f"SIMD processing failed: {e}")
    # Fallback to standard compression
    result = compressor.compress_fallback(text)
```

## Dependencies

- `cpuinfo`: CPU feature detection
- `numpy`: Array operations (optional)
- `ctypes`: Low-level CPU instruction access
- `multiprocessing`: Parallel processing
- `functools`: Function utilities

## Platform Support

### Supported Architectures

- **x86/x64**: Intel and AMD processors with SIMD support
- **ARM64**: Apple Silicon, ARM servers, mobile devices
- **ARM32**: Raspberry Pi, embedded systems (limited)

### Operating System Support

- **Linux**: Full SIMD support
- **macOS**: Full SIMD support (Intel and Apple Silicon)
- **Windows**: Full SIMD support
- **FreeBSD**: Limited support

## Troubleshooting

### Common Issues

**SIMD not detected:**
```bash
# Check CPU features
python -c "import cpuinfo; print(cpuinfo.get_cpu_info()['flags'])"
```

**Performance not improved:**
- Check if data size is appropriate for SIMD (typically 64+ bytes)
- Verify chunk size alignment (64-byte boundaries)
- Check for memory bandwidth bottlenecks

**Crashes on ARM:**
- Ensure NEON is properly detected
- Check for ARM64 vs ARM32 compatibility
- Verify compiler flags for NEON support