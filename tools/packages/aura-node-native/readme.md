# @aura-protocol/native

**High-Performance Native Node.js Bindings for AURA Protocol**

Native Rust implementation with N-API bindings providing **2-10x faster** compression/decompression compared to pure JavaScript.

## Features

- **Blazing Fast**: Native Rust implementation via N-API
- **Cross-Platform**: Supports macOS (x64/ARM64), Linux (x64/ARM64), Windows (x64/ARM64)
- **Zero-Copy**: Efficient memory usage with minimal allocations
- **Drop-In Replacement**: Same API as `@aura-protocol/compression`
- **Pre-Built Binaries**: No compilation required for major platforms

## Installation

```bash
npm install @aura-protocol/native
```

## Quick Start

```javascript
const { AuraCompressor } = require('@aura-protocol/native');

const compressor = new AuraCompressor();

// Compress
const result = compressor.compress("Hello, world!");
console.log(`Compressed: ${result.originalSize} → ${result.compressedSize} bytes`);
console.log(`Ratio: ${result.ratio.toFixed(2)}:1`);

// Decompress
const decompressed = compressor.decompress(result.data);
console.log(decompressed.plaintext); // "Hello, world!"
```

## Performance Comparison

| Operation | Pure JS | Native Rust | Speedup |
|-----------|---------|-------------|---------|
| Compress (small) | 0.15ms | 0.03ms | **5x faster** |
| Compress (large) | 2.5ms | 0.25ms | **10x faster** |
| Decompress | 0.08ms | 0.02ms | **4x faster** |
| Template encode | 0.05ms | 0.01ms | **5x faster** |

*Benchmarked on M1 MacBook Pro*

## API Reference

### Class: `AuraCompressor`

#### `new AuraCompressor()`

Create a new compressor with default templates.

```javascript
const compressor = new AuraCompressor();
```

#### `AuraCompressor.withConfig(binaryThreshold, minSize)`

Create compressor with custom configuration.

**Parameters:**
- `binaryThreshold` (number): Ratio threshold for binary semantic compression (default: 1.1)
- `minSize` (number): Minimum message size to compress in bytes (default: 50)

```javascript
const compressor = AuraCompressor.withConfig(1.2, 100);
```

#### `compressor.compress(text)`

Compress text using the best available method.

**Parameters:**
- `text` (string): Text to compress

**Returns:** `CompressionResult`
```typescript
{
  data: Buffer,
  method: CompressionMethod,
  originalSize: number,
  compressedSize: number,
  ratio: number,
  templateId?: number
}
```

```javascript
const result = compressor.compress("Your message here");
```

#### `compressor.compressWithTemplate(templateId, slots)`

Compress using a specific template.

**Parameters:**
- `templateId` (number): Template ID (0-255)
- `slots` (string[]): Slot values to fill

**Returns:** `CompressionResult`

```javascript
const result = compressor.compressWithTemplate(0, [
  "real-time weather data",
  "Please check a weather website"
]);
```

#### `compressor.decompress(data)`

Decompress data.

**Parameters:**
- `data` (Buffer): Compressed data

**Returns:** `DecompressionResult`
```typescript
{
  plaintext: string,
  method: CompressionMethod,
  originalSize: number,
  compressedSize: number,
  ratio: number,
  templateId?: number
}
```

```javascript
const result = compressor.decompress(compressedData);
console.log(result.plaintext);
```

#### `compressor.addTemplate(template)`

Add a custom template.

**Parameters:**
- `template` (Template):
  ```typescript
  {
    id: number,        // Template ID (0-255)
    pattern: string,   // Template pattern with {0}, {1}, etc.
    description: string,
    slots: number      // Number of slots
  }
  ```

```javascript
compressor.addTemplate({
  id: 200,
  pattern: "Order #{0} has been {1}",
  description: "Order status",
  slots: 2
});
```

#### `compressor.getTemplate(id)`

Get template by ID.

**Parameters:**
- `id` (number): Template ID

**Returns:** `Template | null`

```javascript
const template = compressor.getTemplate(0);
```

## Compression Methods

```typescript
enum CompressionMethod {
  BinarySemantic = 1,   // Template-based compression (6-8:1 ratio)
  Brotli = 2,           // Brotli compression (1.2-1.5:1 ratio)
  Uncompressed = 255    // No compression (for tiny messages)
}
```

## Default Templates

The compressor includes 8 default templates for common AI responses:

| ID | Pattern | Use Case |
|----|---------|----------|
| 0 | `I don't have access to {0}. {1}` | No real-time data responses |
| 1 | `I can help you with {0}. {1}` | Offer help |
| 2 | `To {0}, you need to {1}.` | Instructions |
| 10 | `Yes, I can help with that. {0}` | Help confirmation |
| 20 | `{0} is {1} {2} {3}.` | Definitions |
| 40 | `To {0}, use {1}: \`{2}\`` | Tool instructions |
| 90 | `To {0}, I recommend: {1}` | Recommendations |
| 100 | `Yes, I can help with that. What specific {0} would you like to know more about?` | Clarification |

## Platform Support

### Pre-Built Binaries

- macOS x64 (Intel)
- macOS ARM64 (Apple Silicon)
- Linux x64 (glibc)
- Linux x64 (musl)
- Linux ARM64 (glibc)
- Linux ARM64 (musl)
- Windows x64
- Windows ARM64

### Building from Source

If pre-built binaries aren't available for your platform:

```bash
npm install --build-from-source
```

**Requirements:**
- Rust 1.70+ (`curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh`)
- Node.js 16+

## Why Native?

AURA's compression algorithms are CPU-intensive. The native Rust implementation provides:

1. **Speed**: 2-10x faster than JavaScript
2. **Memory Efficiency**: Zero-copy design, minimal allocations
3. **Reliability**: Rust's safety guarantees prevent memory errors
4. **Scalability**: Better performance under high load

## When to Use

**Use Native (`@aura-protocol/native`) when:**
- You need maximum performance
- Processing high message volumes (>1000/sec)
- Running on servers with high load
- Every millisecond counts

**Use Pure JS (`@aura-protocol/compression`) when:**
- Prototyping or testing
- Building from source isn't possible
- Bundle size is critical (browser)
- Platform compatibility is uncertain

## Examples

### Express.js Middleware

```javascript
const { AuraCompressor } = require('@aura-protocol/native');
const express = require('express');

const compressor = new AuraCompressor();
const app = express();

app.use(express.json());

app.post('/api/chat', (req, res) => {
  const response = "Your AI response here";

  // Compress response
  const result = compressor.compress(response);

  res.set('Content-Encoding', 'aura');
  res.send(result.data);
});
```

### WebSocket Server

```javascript
const { AuraCompressor } = require('@aura-protocol/native');
const WebSocket = require('ws');

const compressor = new AuraCompressor();
const wss = new WebSocket.Server({ port: 8080 });

wss.on('connection', (ws) => {
  ws.on('message', (data) => {
    // Decompress incoming
    const decoded = compressor.decompress(data);
    console.log('Received:', decoded.plaintext);

    // Compress outgoing
    const response = "AI response here";
    const result = compressor.compress(response);
    ws.send(result.data);
  });
});
```

## Benchmarks

Run benchmarks:

```bash
cd packages/aura-node-native
cargo bench
```

## License

See LICENSE file. Patent pending.

## Support

- **Documentation**: [https://auraprotocol.org/docs](https://auraprotocol.org/docs)
- **Issues**: [https://github.com/yourusername/aura-compression/issues](https://github.com/yourusername/aura-compression/issues)
- **Email**: support@auraprotocol.org

---

**AURA Protocol** | Native Performance | Patent Pending
