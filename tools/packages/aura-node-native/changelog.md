# Changelog

All notable changes to the AURA Native Node.js bindings will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- ARM32 Linux support
- Android bindings
- iOS bindings (via React Native)
- WASM bindings for browser use
- Async compression API for large messages
- Streaming compression support

## [0.1.0] - 2025-10-22

### Added
- Initial release of AURA Native Node.js bindings
- Native Rust implementation via N-API
- `AuraCompressor` class matching JavaScript SDK API
- Binary semantic compression with template system
- Brotli fallback compression
- Cross-platform pre-built binaries for:
  - macOS x64 (Intel)
  - macOS ARM64 (Apple Silicon)
  - Linux x64 (glibc)
  - Linux x64 (musl)
  - Linux ARM64 (glibc)
  - Linux ARM64 (musl)
  - Windows x64
  - Windows ARM64

### Performance
- **2-10x faster** than pure JavaScript implementation
- Zero-copy design for minimal memory allocations
- Optimized Brotli compression (quality 11, window 22)
- Sub-millisecond compression for typical messages

### Features
- Drop-in replacement for `@aura-protocol/compression`
- Same API surface as JavaScript SDK
- 8 default templates for common AI responses
- Custom template support
- Automatic compression method selection
- Thread-safe implementation

### Technical Details
- Built with NAPI-RS 2.13
- Rust 2021 edition
- Brotli 3.4
- Release optimizations: LTO + codegen-units=1
- Node.js 16+ required

### Documentation
- Complete API documentation
- TypeScript definitions
- Performance benchmarks
- Usage examples (Express, WebSocket)
- Migration guide from pure JavaScript

### License
- Apache 2.0 for qualified users (see LICENSE)
- Patent pending (US Provisional Application)
- Commercial license required for companies >$5M revenue

### Known Limitations
- No async API yet (synchronous only)
- No streaming support yet
- Template matching is manual (no ML-based auto-detection)
- Pre-built binaries only for listed platforms

---

## Version History

- **0.1.0** (2025-10-22): Initial release - Native Rust implementation with N-API bindings
- **Future**: Async API, streaming support, additional platforms

## Upgrade Guide

### From Nothing to 0.1.0

This is the initial release. To get started:

```bash
npm install @aura-protocol/native
```

```javascript
const { AuraCompressor } = require('@aura-protocol/native');

const compressor = new AuraCompressor();
const result = compressor.compress("Your message here");
console.log(`Compressed: ${result.originalSize} → ${result.compressedSize} bytes`);
```

### Migrating from @aura-protocol/compression

The native bindings are a drop-in replacement:

```javascript
// Before (pure JavaScript)
const { AuraCompressor } = require('@aura-protocol/compression');

// After (native Rust)
const { AuraCompressor } = require('@aura-protocol/native');

// API is identical - no code changes needed!
```

**Performance improvement**: 2-10x faster automatically.

## Support

- Documentation: README.md
- Issues: https://github.com/yourusername/aura-compression/issues
- Email: support@auraprotocol.org

---

**AURA Protocol** | Native Performance | Version 0.1.0
