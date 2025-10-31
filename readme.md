# AURA Compression System

[![Python Tests](https://github.com/hendrixx-cnc/AURA/workflows/Python%20Tests/badge.svg)](https://github.com/hendrixx-cnc/AURA/actions)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Tests: 168 passing](https://img.shields.io/badge/tests-168%20passing-brightgreen.svg)](tests/)

**AI-Optimized Hybrid Compression Framework**

AURA is an experimental compression framework designed for AI-to-AI communication and structured data. It combines template-based compression, dictionary encoding, and entropy coding to achieve high compression ratios on repetitive data patterns.

## Project Status: Alpha

This is an **alpha-stage** research project. While the core functionality works and tests pass, it's not yet recommended for production use without thorough testing in your specific environment.

**What Works:**
- ✅ Core compression/decompression with 5 methods
- ✅ Template discovery and pattern matching
- ✅ Metadata sidechannel for fast-path processing
- ✅ Pattern-based semantic compression for large files (>1MB)
- ✅ 168 passing tests with good coverage
- ✅ Zero external dependencies

**Known Limitations:**
- ⚠️ Performance varies significantly by data type
- ⚠️ Small messages (<100 bytes) may expand rather than compress
- ⚠️ ML algorithm selector exists but needs training data to be effective
- ⚠️ No formal benchmarks against industry-standard compressors
- ⚠️ Limited documentation on optimal configuration
- ⚠️ No production deployments yet

## Installation

### Requirements
- Python 3.8 or higher
- No external dependencies (100% pure Python)

### Basic Installation
```bash
git clone https://github.com/hendrixx-cnc/AURA.git
cd AURA
pip install -e .
```

### Development Installation
```bash
pip install -e .[dev]
```

## Quick Start

### Basic Usage
```python
from aura_compression import ProductionHybridCompressor

# Initialize compressor
compressor = ProductionHybridCompressor()

# Compress data
message = "Your data here"
compressed, method, metadata = compressor.compress(message)

# Decompress
decompressed = compressor.decompress(compressed)

print(f"Original: {len(message)} bytes")
print(f"Compressed: {len(compressed)} bytes")
print(f"Method: {method.name}")
print(f"Ratio: {metadata['ratio']:.2f}:1")
```

### CLI Utilities

For large payloads, the repository ships with a streaming CLI that keeps
template discovery and binary semantics enabled while processing fixed-size
chunks.

#### Compress a large file

```bash
python tools/compress_large_file.py compress \
  --input /path/to/enwik8 \
  --output /path/to/enwik8.aura \
  --chunk-size 64K \
  --progress percent \
  --stats-format table
```

Key options:
- `--chunk-size` accepts raw bytes or suffixed values like `128K`, `4M`, `1G`.
- `--progress` controls the visual feedback (`auto`, `bar`, `percent`, `none`).
- `--stats-format` chooses between table or JSON output; combine with
  `--stats-file` to persist the results.

#### Decompress

```bash
python tools/compress_large_file.py decompress \
  --input /path/to/enwik8.aura \
  --output /path/to/enwik8.restored \
  --progress bar
```

#### Inspect a container without decompressing

```bash
python tools/compress_large_file.py info \
  --input /path/to/enwik8.aura \
  --max-chunks 3 \
  --stats-format json
```

The `info` command prints header metadata, per-method counts, template usage,
and a handful of representative chunks.

#### Verify integrity

```bash
python tools/compress_large_file.py verify \
  --input /path/to/enwik8.aura \
  --progress none
```

`verify` decompresses the archive in-memory to confirm integrity without
writing an output file. All commands support the optional `--stats-file` flag
to save summaries for CI pipelines or audits.

### Configuration Options
```python
compressor = ProductionHybridCompressor(
    # Compression settings
    binary_advantage_threshold=1.01,  # Minimum ratio to use binary compression
    min_compression_size=10,          # Minimum bytes to attempt compression

    # Feature flags
    enable_aura=False,                # Use only AURA methods (no zstd fallback)
    enable_ml_selection=True,         # Use ML for method selection (needs training)
    enable_fast_path=True,            # Enable SIMD optimizations
    enable_audit_logging=False,       # Log compression operations
    enable_scorer=True,               # Score compression quality
)
```

## Core Features

### Compression Methods

1. **BINARY_SEMANTIC** - Template-based compression for highly repetitive data
   - Best for: Structured responses with known patterns
   - Typical ratio: 10:1 to 50:1 (on suitable data)

2. **AURALITE** - Lightweight template + dictionary compression
   - Best for: General-purpose compression of small to medium messages
   - Typical ratio: 2:1 to 8:1

3. **BRIO** - Dictionary + LZ77 + rANS entropy coding
   - Best for: Medium to large messages with mixed patterns
   - Typical ratio: 3:1 to 15:1

4. **AURA_HEAVY** - Hybrid semantic + traditional compression
   - Best for: Maximum compression regardless of speed
   - Typical ratio: 5:1 to 20:1

5. **PATTERN_SEMANTIC** - Pattern-based semantic compression for large files (>1MB)
   - Best for: Large files with patterns (code, logs, JSON, XML)
   - Typical ratio: 5:1 to 50:1+ (highly data-dependent)
   - Uses semantic chunking, regex patterns, dictionary compression, and context-aware encoding

### Advanced Features

**Template Discovery** - Automatically learns patterns from data
```python
from aura_compression import TemplateDiscoveryEngine

engine = TemplateDiscoveryEngine()
engine.add_message(message)  # Feed production data
candidates = engine.discover_templates()
```

**Metadata Sidechannel** - Process compressed data without decompression
```python
from aura_compression import MetadataSideChannel

sidechannel = MetadataSideChannel()
metadata = sidechannel.extract_metadata(compressed_data)
# Route, classify, or filter without decompressing
```

**ML Algorithm Selection** - Intelligent method selection (experimental, needs training)
```python
from aura_compression import MLAlgorithmSelector

# Works but improves with training data from your production usage
selector = MLAlgorithmSelector(enable_learning=True)
best_method = selector.select_method(data_characteristics)

# Selector learns from performance over time
selector.record_performance(result)
```

**Built-in Compliance & Audit Layer** - Production-ready from day one
```python
from aura_compression import ProductionHybridCompressor

# Enable compliance logging (GDPR, HIPAA, SOC2 compatible)
compressor = ProductionHybridCompressor(
    enable_audit_logging=True,
    audit_log_directory="./audit_logs",
    session_id="session_123",
    user_id="user_456"
)

# All operations automatically logged with:
# - Cryptographic integrity (SHA-256 chain)
# - Immutable append-only logs
# - GDPR Article 15 compliance (right to access)
# - HIPAA 45 CFR 164.312(b) audit trails
# - SOC2 CC6.1 control compliance
# - Separate logs for: client-delivered, AI-generated, metadata, safety alerts
```

The audit system was architected with compliance requirements from the beginning, not bolted on later. Every compression operation can be traced, verified, and exported for regulatory compliance.

## Performance Characteristics

### Compression Speed
- Typical: 0.05ms - 0.50ms per message (small messages <1KB)
- Large files: 10-100ms (depending on method and size)
- SIMD optimizations provide 2-5x speedup on compatible hardware

### Compression Ratios
**Highly data-dependent.** Representative examples:

| Data Type | Typical Ratio | Best Case | Worst Case |
|-----------|---------------|-----------|------------|
| Structured JSON (repetitive) | 8:1 | 50:1 | 1:1 |
| AI responses (varied) | 3:1 | 15:1 | 0.8:1 ¹ |
| Random data | 1:1 | 1.2:1 | 0.95:1 ¹ |
| Small messages (<100 bytes) | 0.9:1 ¹ | 2:1 | 0.7:1 ¹ |

¹ Ratios < 1.0 indicate expansion (compressed is larger than original)

**Important:** Always measure with YOUR data. Compression effectiveness varies dramatically based on:
- Data structure and patterns
- Message size distribution
- Repetition and redundancy
- Template library optimization for your use case

## When to Use AURA

### Good Use Cases ✅
- AI-to-AI communication with structured responses
- API responses with repeated patterns
- Large messages (>500 bytes) with redundancy
- Scenarios where you can train templates on production data
- Applications where you control both compression and decompression

### Poor Use Cases ❌
- Small, diverse messages (<100 bytes)
- Highly random or encrypted data
- One-way compression (sender ≠ receiver)
- When compatibility with standard formats (gzip, zstd) is required
- Production systems requiring proven reliability

## Testing

Run the full test suite:
```bash
pytest tests/
```

Run with coverage:
```bash
pytest --cov=aura_compression --cov-report=html
```

Current test status: **168 tests passing** ✅

## Documentation

- [API Reference](docs/api/) - Detailed module documentation
- [Performance Guide](docs/performance.md) - Optimization tips and benchmarks
- [Architecture Overview](docs/architecture.md) - System design and internals

## Project Structure

```
AURA/
├── src/aura_compression/          # Core library
│   ├── compressor_refactored.py   # Main compression engine
│   ├── compression_strategy_manager.py
│   ├── templates.py               # Template library
│   ├── ml_algorithm_selector.py   # ML-based method selection
│   └── metadata_sidechannel.py    # Fast-path processing
├── tests/                         # 168 tests
└── docs/                          # Documentation
```

## Roadmap

**Current Focus (Q4 2025):**
- [ ] Train ML algorithm selector with diverse data sets
- [ ] Comprehensive benchmarks vs zstd/brotli/gzip
- [ ] Performance optimization (target <0.01ms for small messages)
- [ ] Production deployment guide
- [ ] Better documentation with more examples

**Future (2026):**
- [ ] Pre-trained ML models for common use cases
- [ ] Multi-language support (Go, Rust, JavaScript)
- [ ] Streaming compression API
- [ ] Cloud-based template sync service
- [ ] GPU acceleration for large files

## Contributing

Contributions welcome! This is an early-stage project, so there's plenty to improve.

**Areas needing help:**
- Training ML selector with diverse real-world data
- Benchmarking against established compressors
- Performance profiling and optimization
- Documentation and examples
- Testing on diverse data types
- Code review and quality improvements

**To contribute:**
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Make your changes with tests
4. Run the test suite (`pytest`)
5. Submit a pull request

### Development Setup
```bash
# Install dev dependencies
pip install -e .[dev]

# Run tests
pytest

# Run linting (optional - not currently enforced)
flake8 src/
black src/
mypy src/
```

## Known Issues

1. **Print statements in production code** - Should use logging module instead
2. **Some files >1000 lines** - Need refactoring for maintainability
3. **Magic numbers** - Many thresholds are hardcoded, need configuration
4. **No CI/CD** - Tests not automated in GitHub Actions
5. **Version inconsistencies** - Multiple version strings across files

See [Issues](https://github.com/hendrixx-cnc/AURA/issues) for full list.

## License

Licensed under Apache License 2.0 with a dual-license model for commercial use.

**Open Source (Free):**
- Individual developers
- Non-profit organizations
- Educational institutions
- Companies with annual revenue ≤ $5M
- Internal testing and evaluation (any company size)

**Commercial License (Required):**
- Public/production deployments by companies with revenue > $5M

See [LICENSE](LICENSE) for full details.

**Patent Notice:** This software implements patent-pending technology. Open source users receive a royalty-free patent license. See LICENSE for details.

## Contact

- **Author:** Todd Hendricks
- **Email:** todd@auraprotocol.org
- **Issues:** [GitHub Issues](https://github.com/hendrixx-cnc/AURA/issues)

## Acknowledgments

Built as a research project exploring specialized compression for AI communication. Inspired by the need for efficient AI-to-AI data exchange.

---

**Bottom Line:** AURA is an interesting experiment in specialized compression. It works well for specific use cases (structured, repetitive data), but it's not a drop-in replacement for general-purpose compressors. Evaluate it thoroughly with your own data before considering production use.
