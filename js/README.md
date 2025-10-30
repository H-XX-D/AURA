# AURA Compression - Node.js/TypeScript Package

This directory contains the Node.js/TypeScript components for AURA compression.

## Current Status

**Note**: The native Node.js bindings are not yet implemented. The package currently provides a JavaScript fallback implementation.

## File Structure

```
js/
├── package.json          # Package configuration
├── tsconfig.json         # TypeScript configuration
├── binding.gyp           # Native binding configuration (future)
├── src/                  # TypeScript source code
└── node_modules/         # Dependencies
```

## Development

### Prerequisites
- Node.js 18+
- npm or yarn

### Setup
```bash
cd js
npm install
```

### Build
```bash
npm run build:all  # Build all components
npm run build:docs # Build documentation
```

### Test
```bash
npm test
npm run test:integration
npm run test:performance
```

## Future Implementation

The native bindings will provide:
- High-performance C++ compression algorithms
- Direct integration with the Rust compression core
- Zero-copy operations for maximum speed
- SIMD acceleration on supported platforms

## Scripts

- `npm run build` - Build native bindings (when implemented)
- `npm run build:python` - Build Python components
- `npm run build:docs` - Generate TypeScript documentation
- `npm run dev` - Development server with hot reload
- `npm run benchmark` - Performance benchmarking
- `npm run audit` - Security audit

## Integration

This package integrates with the main AURA compression system located in the parent directory. The Python implementation in `../src/python/` provides the core compression algorithms.