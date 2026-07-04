# AURA Compression System Architecture

## Overview

AURA is a modular hybrid compression framework designed for AI-to-AI communication and structured data. The system uses a layered architecture with pluggable compression methods, template discovery, and intelligent routing.

**Current Status**: Alpha (v2.0.1)
**Python Version**: 3.8+
**External Dependencies**: None (runtime)

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     User Application Layer                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              ProductionHybridCompressor (Main API)               │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  • compress(data) → (compressed, method, metadata)        │  │
│  │  • decompress(compressed) → original                      │  │
│  │  • discover_templates(data) → templates                   │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
            ┌─────────────────┼─────────────────┐
            ▼                 ▼                 ▼
    ┌───────────────┐ ┌───────────────┐ ┌───────────────┐
    │   Template    │ │  Compression  │ │   Metadata    │
    │   Service     │ │   Strategy    │ │  Sidechannel  │
    │               │ │   Manager     │ │               │
    └───────────────┘ └───────────────┘ └───────────────┘
            │                 │                 │
            ▼                 ▼                 ▼
    ┌───────────────┐ ┌───────────────┐ ┌───────────────┐
    │   Template    │ │  Compression  │ │    Router     │
    │   Discovery   │ │    Engine     │ │               │
    └───────────────┘ └───────────────┘ └───────────────┘
            │                 │                 │
            ▼                 ▼                 ▼
    ┌───────────────┐ ┌───────────────┐ ┌───────────────┐
    │  Persistent   │ │  ML Algorithm │ │  Background   │
    │    Cache      │ │   Selector    │ │   Workers     │
    │   (SQLite)    │ │   (Future)    │ │               │
    └───────────────┘ └───────────────┘ └───────────────┘
                              │
            ┌─────────────────┼─────────────────────────┐
            ▼                 ▼                         ▼
    ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐
    │Binary        │  │  AuraLite    │  │  Pattern Semantic    │
    │Semantic      │  │  (LZ77+Huff) │  │  (Large Files)       │
    └──────────────┘  └──────────────┘  └──────────────────────┘
            ▼                 ▼                         ▼
    ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐
    │  BRIO        │  │ AURA_HEAVY   │  │   Uncompressed       │
    │(Dict+LZ+rANS)│  │ (Hybrid)     │  │                      │
    └──────────────┘  └──────────────┘  └──────────────────────┘
```

---

## Core Components

### 1. ProductionHybridCompressor
**File**: [`src/aura_compression/compressor_refactored.py`](../src/aura_compression/compressor_refactored.py)

The main entry point and orchestrator for all compression operations.

**Responsibilities**:
- API facade for compression/decompression
- Component initialization and lifecycle management
- Method selection coordination
- Fast-path optimization for hot paths

**Key Methods**:
```python
compress(data: bytes | str) → (bytes, CompressionMethod, dict)
decompress(data: bytes) → bytes
discover_templates(data: str) → List[Template]
```

**Configuration Options**:
- `binary_advantage_threshold`: Minimum compression ratio to use binary semantic (default: 1.01)
- `enable_aura`: Enable experimental AURA_HEAVY method
- `enable_ml_selection`: Use ML-based method selection (requires training)
- `enable_audit_logging`: Enable compliance audit trail
- `template_cache_size`: LRU cache size for templates (default: 128)

---

### 2. Compression Strategy Manager
**File**: [`src/aura_compression/compression_strategy_manager.py`](../src/aura_compression/compression_strategy_manager.py)
**Size**: 1,032 lines (⚠️ needs refactoring)

Intelligent routing system that selects the optimal compression method for each message.

**Responsibilities**:
- Analyze data characteristics (entropy, patterns, size)
- Score available compression methods
- Select optimal method based on heuristics
- Cache scoring decisions for performance

**Selection Heuristics**:
1. **Size-based routing**:
   - `< 100 bytes`: Prefer uncompressed or AuraLite
   - `100-1000 bytes`: Consider Binary Semantic if templates match
   - `> 1MB`: Route to Pattern Semantic for large files

2. **Content analysis**:
   - High entropy (>7.0): Prefer BRIO or uncompressed
   - Repetitive patterns: Binary Semantic
   - Structured data (JSON/XML): Template-based methods

3. **Template availability**:
   - Template match >80%: Binary Semantic
   - Partial match 30-80%: Partial compression
   - No match: Fall back to traditional methods

**Performance**:
- Metric caching with 256-entry LRU
- Fast path for repeated similar messages
- Lazy evaluation of expensive metrics

---

### 3. Template Service
**File**: [`src/aura_compression/template_service.py`](../src/aura_compression/template_service.py)

Manages template discovery, storage, and matching.

**Responsibilities**:
- Template storage and retrieval
- Full and partial template matching
- Template synchronization with persistent cache
- Fuzzy matching for similar templates

**Components**:
- **TemplateManager**: In-memory template operations
- **TemplateLibrary**: Core template storage and matching
- **TemplateDiscovery**: Automatic template extraction from data streams
- **PersistentCache**: SQLite-backed template persistence

**Template Matching**:
- Full match: Entire message matches a template
- Partial match: Substring matches with leftover handling
- Fuzzy match: Similar templates with edit distance

---

### 4. Compression Engine
**File**: [`src/aura_compression/compression_engine.py`](../src/aura_compression/compression_engine.py)

Low-level compression/decompression implementation for all methods.

**Responsibilities**:
- Execute compression with selected method
- Execute decompression with method auto-detection
- Handle format versioning and compatibility
- Provide method-specific optimizations

**Supported Methods**:
1. **BINARY_SEMANTIC (0x00)**: Template-based semantic compression
2. **AURALITE (0x01)**: LZ77 + Huffman coding
3. **BRIO (0x02)**: Dictionary + LZ77 + rANS entropy coding
4. **AURA_HEAVY (0x04)**: Hybrid semantic + traditional (experimental)
5. **PATTERN_SEMANTIC (0x20)**: Pattern-based compression for large files
6. **UNCOMPRESSED (0xFF)**: Pass-through for incompressible data

**Format**:
```
[1 byte: method] [4 bytes: original_size] [N bytes: compressed_data]
```

---

### 5. Metadata Sidechannel
**File**: [`src/aura_compression/metadata_sidechannel.py`](../src/aura_compression/metadata_sidechannel.py)

Enables processing compressed data without full decompression.

**Responsibilities**:
- Extract metadata from compressed messages
- Classify message urgency (CRITICAL, HIGH, NORMAL, LOW)
- Security screening (SAFE, REVIEW, BLOCKED)
- Route messages based on metadata

**Use Cases**:
- Message routing without decompression overhead
- Priority queue management
- Security filtering at compression boundary
- Logging and monitoring

**Metadata Extraction**:
- Message category and priority
- Template ID (if template-based)
- Compression method and ratio
- Security classification
- Timestamp and sequence info

---

### 6. Pattern Semantic Compressor
**File**: [`src/aura_compression/pattern_semantic_large_file.py`](../src/aura_compression/pattern_semantic_large_file.py)

Specialized compressor for large files (>1MB) with repeating patterns.

**Responsibilities**:
- Semantic chunking of large files
- Regex-based pattern recognition
- Dictionary-based compression
- Context-aware encoding

**Approach**:
1. Split file into semantic chunks (functions, JSON objects, etc.)
2. Extract common patterns using regex
3. Build frequency-based dictionary
4. Encode with pattern references + zlib

**Best For**:
- Source code files
- Log files with repeating patterns
- Large JSON/XML documents
- Configuration files

**Performance**:
- Typical ratio: 5:1 to 50:1+ (highly data-dependent)
- Memory usage: ~2-3x file size during compression
- Not suitable for streaming (loads entire file)

---

### 7. ML Algorithm Selector
**File**: [`src/aura_compression/ml_algorithm_selector.py`](../src/aura_compression/ml_algorithm_selector.py)
**Size**: 1,023 lines (⚠️ needs refactoring)
**Status**: ⚠️ Future feature - requires training data

Machine learning system for compression method selection.

**Responsibilities**:
- Feature extraction from messages
- ML-based method prediction
- Performance tracking and retraining
- A/B testing of selection strategies

**Current Status**:
- Framework implemented but not trained
- Feature extraction works
- Prediction defaults to heuristic fallback
- Requires real-world training data to be effective

**Features Extracted**:
- Message size distribution
- Entropy and compression characteristics
- Structural patterns (JSON, XML, etc.)
- Historical compression performance
- Template match likelihood

---

### 8. Router
**File**: [`src/aura_compression/router.py`](../src/aura_compression/router.py)

Network-aware compression routing based on transport characteristics.

**Responsibilities**:
- Select compression based on network conditions
- Optimize for latency vs throughput tradeoffs
- TCP vs UDP-aware routing
- Adaptive compression for varying bandwidth

**Routing Rules**:
- **Low latency networks**: Prefer faster methods (AuraLite)
- **High bandwidth**: Use maximum compression (BRIO, AURA_HEAVY)
- **Lossy networks**: Include redundancy/checksums
- **TCP**: More aggressive compression (BRIO threshold: 1000 bytes)
- **UDP**: Smaller chunks, faster methods

---

### 9. Background Workers
**File**: [`src/aura_compression/background_workers.py`](../src/aura_compression/background_workers.py)

Asynchronous task processing for non-blocking operations.

**Responsibilities**:
- Template discovery in background
- Persistent cache synchronization
- Performance metric collection
- Audit log writing

**Workers**:
1. **TemplateDiscoveryWorker**: Continuous template mining
2. **CacheSyncWorker**: Periodic SQLite synchronization
3. **AuditLogWorker**: Async audit trail writing
4. **MetricCollectionWorker**: Performance telemetry

**Status**: ⚠️ Framework exists but workers not actively used in current implementation

---

### 10. Persistent Cache
**File**: [`src/aura_compression/persistent_cache.py`](../src/aura_compression/persistent_cache.py)

SQLite-backed storage for templates and compression state.

**Responsibilities**:
- Template persistence across restarts
- Template metadata storage
- Usage statistics tracking
- Legacy JSON cache migration

**Schema**:
```sql
CREATE TABLE templates (
    template_id INTEGER PRIMARY KEY,
    pattern TEXT NOT NULL,
    usage_count INTEGER DEFAULT 0,
    created_at TIMESTAMP,
    last_used TIMESTAMP
)
```

**Features**:
- WAL mode for concurrent access
- Automatic schema migration
- Corruption recovery
- Export/import for sharing

---

## Compression Methods

### Binary Semantic (0x00)
Template-based compression using learned patterns.

**Algorithm**:
1. Match message against template library
2. Extract variable slots
3. Encode: `[template_id][slot_count][slot1_len][slot1_data]...`
4. Add metadata header

**Best For**: Structured messages with high repetition
**Typical Ratio**: 10:1 to 100:1 for templated data
**Speed**: Very fast (template lookup + slot encoding)

### AuraLite (0x01)
LZ77 sliding window + Huffman coding.

**Algorithm**:
1. LZ77 for back-references (32KB window)
2. Huffman coding for literals and lengths
3. Compact encoding of distances

**Best For**: Small to medium messages with local repetition
**Typical Ratio**: 2:1 to 5:1
**Speed**: Fast (optimized for <10KB messages)

### BRIO (0x02)
Dictionary + LZ77 + rANS entropy coding.

**Algorithm**:
1. Dictionary encoding for common words/tokens
2. LZ77 for sequence repetition
3. rANS for final entropy coding
4. Multi-pass optimization

**Best For**: Medium to large messages with mixed patterns
**Typical Ratio**: 3:1 to 15:1
**Speed**: Moderate (more thorough than AuraLite)

### AURA_HEAVY (0x04)
Experimental hybrid semantic + traditional compression.

**Algorithm**:
1. Semantic analysis and chunking
2. Template extraction per chunk
3. Dictionary building across chunks
4. Multi-method compression per chunk
5. Optimal method selection

**Best For**: Maximum compression regardless of speed
**Typical Ratio**: 5:1 to 20:1
**Speed**: Slow (experimental, heavy analysis)
**Status**: ⚠️ Experimental - disabled by default

### Pattern Semantic (0x20)
Pattern-based compression for large files.

**Algorithm**:
1. Semantic chunking (preserve structure)
2. Regex pattern extraction
3. Frequency-based dictionary
4. Pattern reference encoding
5. zlib compression of residuals

**Best For**: Large files (>1MB) with patterns
**Typical Ratio**: 5:1 to 50:1+ (highly variable)
**Speed**: Slow (full file processing)

---

## Data Flow

### Compression Path

```
1. Input Data (bytes/str)
        ↓
2. Metadata Extraction (optional)
   - Extract priority, category, security
        ↓
3. Fast Path Check
   - Check cache for known patterns
   - Return cached result if hit
        ↓
4. Strategy Selection
   - Analyze data characteristics
   - Score available methods
   - Select optimal method
        ↓
5. Template Matching (if applicable)
   - Check template library
   - Full match → Binary Semantic
   - Partial match → Partial compression
   - No match → Traditional methods
        ↓
6. Compression Engine
   - Execute selected method
   - Add format header
   - Validate output
        ↓
7. Metadata Enrichment
   - Add compression ratio
   - Add method info
   - Add template ID (if used)
        ↓
8. Output (compressed_bytes, method, metadata)
```

### Decompression Path

```
1. Input (compressed_bytes)
        ↓
2. Header Parsing
   - Extract method byte
   - Extract original size
   - Validate format
        ↓
3. Method Routing
   - Route to appropriate decoder
        ↓
4. Decompression Engine
   - Execute method-specific decompression
   - Template substitution (if Binary Semantic)
   - LZ77 expansion (if AuraLite/BRIO)
   - Pattern expansion (if Pattern Semantic)
        ↓
5. Validation
   - Check size matches header
   - Verify data integrity
        ↓
6. Output (original_bytes)
```

---

## Performance Characteristics

### Compression Speed
- **Binary Semantic**: ~50-100 MB/s (template lookup)
- **AuraLite**: ~20-40 MB/s (LZ77 + Huffman)
- **BRIO**: ~10-20 MB/s (dictionary + LZ77 + rANS)
- **AURA_HEAVY**: ~1-5 MB/s (heavy analysis)
- **Pattern Semantic**: ~5-15 MB/s (large files)

### Decompression Speed
- **All methods**: 2-5x faster than compression
- **Binary Semantic**: ~100-200 MB/s (template expansion)
- **No method overhead** > 1ms for messages < 10KB

### Memory Usage
- **Base**: ~5-10 MB (template cache + buffers)
- **Per message**: ~2-4x message size during compression
- **Template cache**: Configurable (default: 128 templates)
- **Pattern Semantic**: ~2-3x file size for large files

### Latency Targets
- **Fast path**: < 0.1 ms (cached patterns)
- **Binary Semantic**: < 0.5 ms (small messages)
- **AuraLite/BRIO**: < 2 ms (< 10KB messages)
- **Pattern Semantic**: No real-time guarantee (large files)

---

## Extension Points

### Adding a New Compression Method

1. **Define enum** in [`enums.py`](../src/aura_compression/enums.py):
```python
class CompressionMethod(Enum):
    MY_METHOD = 0x30
```

2. **Implement in CompressionEngine** ([`compression_engine.py`](../src/aura_compression/compression_engine.py)):
```python
def _compress_my_method(self, data: bytes) -> bytes:
    # Your compression logic
    return compressed_data

def _decompress_my_method(self, data: bytes) -> bytes:
    # Your decompression logic
    return original_data
```

3. **Add to strategy manager** ([`compression_strategy_manager.py`](../src/aura_compression/compression_strategy_manager.py)):
```python
def _score_my_method(self, data: bytes, metrics: dict) -> float:
    # Return score 0.0-1.0
    return score
```

4. **Add tests** in `tests/test_my_method.py`

### Adding a New Template Matcher

Extend [`templates.py`](../src/aura_compression/templates.py):
```python
class MyTemplateMatcher:
    def match(self, data: str) -> Optional[TemplateMatch]:
        # Your matching logic
        return match
```

---

## Configuration

### Environment Variables
- `AURA_ENABLE_EXPERIMENTAL`: Enable AURA_HEAVY (default: false)
- `AURA_TEMPLATE_CACHE_DIR`: Template cache location (default: .aura_cache)
- `AURA_LOG_LEVEL`: Logging level (default: INFO)

### Runtime Configuration
Pass to `ProductionHybridCompressor.__init__()`:
- `binary_advantage_threshold`: Compression ratio threshold
- `enable_ml_selection`: Use ML selector (requires training)
- `enable_audit_logging`: Enable audit trail
- `template_cache_size`: LRU cache size

---

## Known Limitations

1. **Large file memory usage**: Pattern Semantic loads entire file (not streaming)
2. **ML selector needs training**: Framework exists but requires real-world data
3. **God classes**: 2 files >1000 lines need refactoring
4. **No formal benchmarks**: Performance claims based on internal testing
5. **No multi-language support**: Python only (C/Rust extensions planned)
6. **Small message overhead**: Messages <100 bytes may expand

---

## Future Roadmap

### Short-term (v2.1)
- [ ] Refactor god classes (compression_strategy_manager, ml_algorithm_selector)
- [ ] Add test coverage metrics
- [ ] Streaming API for large files
- [ ] Formal benchmark suite

### Medium-term (v2.5)
- [ ] Train ML algorithm selector
- [ ] Add Rust extensions for hot paths
- [ ] Multi-language bindings (C API)
- [ ] Production deployment guide

### Long-term (v3.0)
- [ ] Distributed template synchronization
- [ ] Hardware acceleration (SIMD, GPU)
- [ ] Pre-trained models for common data types
- [ ] Real-time adaptive compression

---

## References

- **Repository**: https://github.com/H-XX-D/AURA
- **License**: Apache 2.0 (see [LICENSE](../LICENSE))
- **Python Version**: 3.8+
- **Status**: Alpha (not production-ready)

**Last Updated**: 2025-10-31
**Version**: 2.0.1
