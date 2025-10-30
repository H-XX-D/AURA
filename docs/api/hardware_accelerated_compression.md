# Hardware Accelerated Compression API Reference

## Overview

The `hardware_accelerated_compression.py` module provides architecture-specific optimizations for different hardware platforms, including ARM NEON, x86 SIMD, and specialized hardware acceleration.

## Classes

### HardwareAcceleratedCompressor

Hardware-specific compression optimizations.

#### Constructor

```python
HardwareAcceleratedCompressor(
    architecture: Optional[str] = None,
    enable_neon: bool = True,
    enable_simd: bool = True,
    enable_gpu: bool = False
)
```

**Parameters:**
- `architecture`: Target architecture ('arm64', 'x86_64', 'auto') (default: auto-detect)
- `enable_neon`: Enable ARM NEON acceleration (default: True)
- `enable_simd`: Enable x86 SIMD acceleration (default: True)
- `enable_gpu`: Enable GPU acceleration (default: False)

## Methods

### detect_architecture()

Auto-detect the current hardware architecture.

```python
def detect_architecture(self) -> str:
```

**Returns:**
- `str`: Architecture name ('arm64', 'x86_64', 'unknown')

### get_hardware_features()

Get available hardware acceleration features.

```python
def get_hardware_features(self) -> Dict[str, bool]:
```

**Returns:**
- `Dict[str, bool]`: Hardware feature availability

### compress_hardware(text)

Compress using hardware-specific optimizations.

```python
def compress_hardware(self, text: str) -> Tuple[bytes, dict]:
```

**Parameters:**
- `text`: Input text to compress

**Returns:**
- `Tuple[bytes, dict]`: (compressed_data, metadata)

### optimize_for_architecture(text)

Apply architecture-specific optimizations.

```python
def optimize_for_architecture(self, text: str) -> Dict[str, Any]:
```

**Parameters:**
- `text`: Text to optimize for

**Returns:**
- `Dict[str, Any]`: Architecture-specific optimizations

## Architecture-Specific Optimizations

### ARM64 (Apple Silicon, ARM Servers)

```python
# NEON-optimized compression
if architecture == 'arm64':
    # 128-bit vector operations
    result = compressor.compress_neon(text)

    # Memory prefetch optimization
    compressor.prefetch_arm64(data)

    # Branch prediction hints
    compressor.optimize_branches_arm(text)
```

**ARM64 Features:**
- NEON SIMD instructions (128-bit vectors)
- Memory prefetch instructions
- Branch prediction hints
- Cache line optimization (64-byte alignment)

### x86_64 (Intel/AMD)

```python
# AVX-512 optimized compression
if 'avx512' in features:
    result = compressor.compress_avx512(text)

# BMI2 instruction optimization
elif 'bmi2' in features:
    result = compressor.compress_bmi2(text)
```

**x86_64 Features:**
- AVX-512 (512-bit vectors on modern Intel/AMD)
- AVX-2 (256-bit vectors)
- BMI2 (bit manipulation instructions)
- SHA-NI (cryptographic acceleration)

### Performance Characteristics

| Architecture | Typical Speedup | Memory Efficiency | Power Efficiency |
|---------------|-----------------|-------------------|------------------|
| ARM64 NEON | 2.0-3.0x | High | Excellent |
| x86 AVX-512 | 3.0-5.0x | High | Good |
| x86 AVX-2 | 2.0-3.5x | Medium | Good |
| x86 SSE4 | 1.5-2.0x | Low | Fair |

## Usage Examples

### Automatic Hardware Detection

```python
from aura_compression.hardware_accelerated_compression import HardwareAcceleratedCompressor

# Auto-detect and initialize
compressor = HardwareAcceleratedCompressor()

# Check detected architecture
arch = compressor.detect_architecture()
print(f"Detected architecture: {arch}")

# Get available features
features = compressor.get_hardware_features()
print("Available features:")
for feature, available in features.items():
    print(f"  {feature}: {available}")
```

### Architecture-Specific Compression

```python
# Compress with hardware acceleration
compressed, metadata = compressor.compress_hardware(text)

print(f"Hardware-accelerated compression:")
print(f"  Ratio: {metadata['ratio']:.2f}x")
print(f"  Time: {metadata['time_ms']:.2f}ms")
print(f"  Hardware used: {metadata['hardware']}")
```

### Manual Architecture Selection

```python
# Force specific architecture
compressor_arm = HardwareAcceleratedCompressor(architecture='arm64')
compressor_x86 = HardwareAcceleratedCompressor(architecture='x86_64')

# Compare performance
result_arm = compressor_arm.compress_hardware(text)
result_x86 = compressor_x86.compress_hardware(text)
```

## Hardware Feature Detection

### ARM64 Feature Detection

```python
# Check for ARM64-specific features
features = compressor.get_hardware_features()

if features.get('neon', False):
    print("NEON SIMD available")
if features.get('fp16', False):
    print("Half-precision floating point available")
if features.get('dotprod', False):
    print("Dot product instructions available")
```

### x86 Feature Detection

```python
# Check for x86-specific features
if features.get('avx512', False):
    print("AVX-512 available - maximum vector performance")
elif features.get('avx2', False):
    print("AVX-2 available - good vector performance")
elif features.get('sse4_1', False):
    print("SSE4.1 available - basic SIMD")

# Advanced features
if features.get('bmi2', False):
    print("BMI2 available - optimized bit operations")
if features.get('sha_ni', False):
    print("SHA-NI available - cryptographic acceleration")
```

## Memory Optimization

### Cache-Aware Processing

```python
# Optimize for CPU cache
optimized = compressor.optimize_for_cache(text, cache_line_size=64)

# Process in cache-friendly chunks
for chunk in optimized['chunks']:
    result = compressor.compress_chunk_hardware(chunk)
```

### Memory Prefetch

```python
# Prefetch data into cache
compressor.prefetch_data(data, prefetch_distance=256)

# Compress with prefetch optimization
result = compressor.compress_with_prefetch(text)
```

## Power Efficiency

### ARM64 Power Optimization

```python
# Use efficient NEON instructions
compressor.enable_power_efficient_mode()

# Balance performance and power
compressor.set_power_profile('balanced')  # performance, balanced, efficiency
```

### Dynamic Frequency Scaling

```python
# Adapt to thermal constraints
compressor.enable_thermal_throttling()

# Monitor and adapt
while compressing:
    temp = compressor.get_cpu_temperature()
    if temp > 80:
        compressor.reduce_frequency()
```

## Integration with Main Compressor

### Automatic Hardware Integration

```python
from aura_compression.compressor import ProductionHybridCompressor

# Hardware acceleration is automatically used
compressor = ProductionHybridCompressor(enable_hardware_acceleration=True)

# Check hardware usage
metadata = compressor.compress(text)[1]
if metadata.get('hardware_accelerated', False):
    print(f"Hardware used: {metadata['hardware_type']}")
    print(f"Speedup: {metadata['hardware_speedup']:.1f}x")
```

### Manual Hardware Control

```python
# Manual hardware selection
compressor.enable_hardware_acceleration(True)
compressor.set_preferred_hardware('arm64')  # arm64, x86_64, auto

# Hardware-specific settings
compressor.set_hardware_chunk_size(128)
compressor.enable_hardware_prefetch(True)
```

## Error Handling

Hardware acceleration provides graceful fallbacks:

```python
try:
    result = compressor.compress_hardware(text)
except HardwareNotAvailableError:
    # Fallback to software compression
    result = compressor.compress_software(text)
except HardwareError as e:
    logger.error(f"Hardware acceleration failed: {e}")
    # Fallback to basic compression
    result = compressor.compress_basic(text)
```

## Benchmarking

### Hardware Performance Testing

```python
# Run hardware benchmarks
benchmarks = compressor.run_hardware_benchmarks()

print("Hardware benchmarks:")
for test_name, results in benchmarks.items():
    print(f"  {test_name}: {results['throughput']} MB/s, {results['efficiency']}%")
```

### Comparative Analysis

```python
# Compare hardware vs software
software_result = compressor.compress_software(text)
hardware_result = compressor.compress_hardware(text)

speedup = software_result[1]['time_ms'] / hardware_result[1]['time_ms']
ratio_improvement = hardware_result[1]['ratio'] / software_result[1]['ratio']

print(f"Hardware speedup: {speedup:.1f}x")
print(f"Ratio improvement: {ratio_improvement:.2f}x")
```

## Dependencies

- `platform`: System information
- `cpuinfo`: CPU feature detection
- `psutil`: System monitoring
- `ctypes`: Hardware instruction access
- `subprocess`: System command execution

## Platform Support

### Supported Platforms

- **macOS ARM64**: Apple Silicon (M1, M2, M3)
- **macOS Intel**: x86_64 with SIMD
- **Linux ARM64**: ARM servers, Raspberry Pi 4+
- **Linux x86_64**: Intel and AMD servers
- **Windows x86_64**: Intel and AMD systems

### Hardware Requirements

- **ARM64**: NEON support (all modern ARM64)
- **x86_64**: SSE4.1 minimum, AVX-2 recommended, AVX-512 optimal
- **Memory**: 128MB minimum for acceleration structures
- **CPU**: Multi-core recommended for parallel processing

## Troubleshooting

### Common Issues

**Hardware not detected:**
```bash
# Check system information
python -c "import platform; print(platform.machine(), platform.system())"

# Check CPU features
python -c "import cpuinfo; print(cpuinfo.get_cpu_info()['flags'][:10])"
```

**Performance not improved:**
- Verify data size (> 1KB typically needed)
- Check memory alignment (64-byte boundaries)
- Monitor CPU temperature and frequency

**Crashes on ARM:**
- Ensure 64-bit ARM (ARM64, not ARM32)
- Check for NEON instruction set
- Verify compiler flags

**Permission errors:**
- May need root access for some hardware features
- Check if virtualization interferes with hardware access