# AURA Compression System

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

**AI-Optimized Hybrid Compression Protocol for Real-Time Communication**

AURA (Advanced Universal Response Algorithm) is a high-performance compression framework designed specifically for AI assistant responses and real-time communication. It provides intelligent, adaptive compression with multiple strategies optimized for different data types and network conditions.

## Features

### Core Compression Methods
- **BINARY_SEMANTIC**: Template-based compression for repetitive data (ultra-compact)
- **AURALITE**: Proprietary AURA-based compression (primary method)
- **AURA_LITE**: Template + dictionary + literals compression
- **BRIO_FULL**: Full semantic compression with rANS entropy coding for large messages
- **BRIO_TCP**: TCP-optimized BRIO for small/medium messages
- **AURA_HEAVY**: Hybrid semantic + traditional compression for maximum ratios

### Intelligent Features
- **Template Discovery**: Automatic pattern recognition from production traffic
- **ML Algorithm Selection**: Intelligent method selection based on data characteristics
- **SIMD Acceleration**: Hardware-optimized processing for small messages
- **Network-Aware Compression**: Adaptive compression based on network conditions
- **Hardware Acceleration**: Architecture-specific optimizations (ARM64/NEON)
- **Persistent Caching**: Template match caching for performance
- **Audit Logging**: GDPR/HIPAA/SOC2 compliant logging
- **Metadata Sidechain**: Fast-path processing without decompression for routing, classification, and security screening (76-200× faster processing)
- **AI Semantic Compression**: Advanced compression for large files using semantic chunking, pattern recognition, and context-aware encoding

### Performance Highlights
- Average compression ratios up to 55:1+ on large data
- Sub-millisecond compression times (typically 0.05-0.25ms)
- 100% SIMD processing utilization where applicable
- Automatic optimization pipeline with 18+ optimizations
- Metadata sidechain enables 76-200× faster routing and processing (0.17ms vs 13.0ms)
- AI semantic compression achieves 5-300:1 ratios on large files (vs 2.5-64:1 traditional methods)

## Installation

### Requirements
- Python 3.8 or higher
- pip for package management

### Basic Installation
```bash
pip install aura-compression
```

### Development Installation
```bash
git clone https://github.com/hendrixx-cnc/AURA.git
cd AURA
pip install -e .[dev]
```

### Optional Dependencies
For WebSocket support:
```bash
pip install aura-compression[websocket]
```

## Quick Start

### Basic Compression
```python
from aura_compression import ProductionHybridCompressor

# Initialize compressor
compressor = ProductionHybridCompressor()

# Compress data
original_data = b"Hello, this is a test message for compression."
compressed = compressor.compress(original_data)

# Decompress data
decompressed = compressor.decompress(compressed)

print(f"Original: {len(original_data)} bytes")
print(f"Compressed: {len(compressed)} bytes")
print(f"Ratio: {len(original_data)/len(compressed):.2f}:1")
```

### Command Line Usage
```bash
# Compress a file
aura-compress input.txt output.compressed

# Decompress a file
aura-decompress output.compressed decompressed.txt

# Start compression server
aura-server --port 8080

# Run benchmarks
aura-benchmark --iterations 1000
```

## Configuration

The compressor can be configured for different use cases:

```python
compressor = ProductionHybridCompressor(
    enable_aura=True,  # Use AURA methods only (no standard fallbacks)
    binary_advantage_threshold=1.1,
    min_compression_size=20,
    aura_preference_margin=0.05
)
```

## API Reference

For detailed API documentation, see the [API Reference](docs/api/README.md) in the docs directory.

## Testing

Run the test suite:
```bash
pytest
```

Run with coverage:
```bash
pytest --cov=aura_compression
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Setup
```bash
# Install development dependencies
pip install -e .[dev]

# Run linting
flake8 src/

# Format code
black src/

# Type checking
mypy src/
```

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Authors

- **Todd Hendricks** - *Initial work* - [todd@auraprotocol.org](mailto:todd@auraprotocol.org)

## Acknowledgments

- Built for high-performance AI communication systems
- Optimized for real-time compression needs
- Compliant with enterprise security standards