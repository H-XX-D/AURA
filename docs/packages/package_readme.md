# AURA Compression - Multi-Language Package Guide

**Copyright (c) 2025 Todd James Hendricks**
**Licensed under Apache License 2.0**
**Patent Pending - Application No. 19/366,538**

AI-Optimized Hybrid Compression Protocol for Real-Time Communication

## Available Packages

AURA Compression is available in multiple languages and deployment formats:

1. **Python** - PyPI package
2. **Node.js** - npm package with native bindings
3. **Rust** - Cargo crate
4. **Docker** - Production-ready containers

---

## Python Package

### Installation

```bash
# Install from PyPI
pip install aura-compression

# Install with WebSocket support
pip install aura-compression[websocket]

# Install with development tools
pip install aura-compression[dev]
```

### Quick Start

```python
from aura_compression import ProductionHybridCompressor

# Initialize compressor
compressor = ProductionHybridCompressor(
    enable_aura=True,
    enable_audit_logging=True,
    session_id="session_123"
)

# Compress message
text = "I cannot browse the internet."
compressed, method, metadata = compressor.compress(text)

print(f"Compressed: {len(text)}B → {len(compressed)}B")
print(f"Method: {method.name}")
print(f"Ratio: {metadata['ratio']:.2f}:1")

# Decompress
decompressed = compressor.decompress(compressed)
assert decompressed == text
```

### Client/Server SDKs

```python
# Client SDK
from packages.client_sdk import ClientSDK

client = ClientSDK(template_store_path="templates.json")
payload = b'\x00...'  # Compressed payload from server
text = client.decode_payload(payload)

# Server SDK
from packages.server_sdk import ServerSDK

server = ServerSDK(
    enable_aura=True,
    enable_audit_logging=True,
    session_id="session_123"
)
compressed, method, metadata = server.compress("Hello, world!")
```

### Building from Source

```bash
# Clone repository
git clone https://github.com/yourusername/aura-compression.git
cd aura-compression

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest tests/

# Build wheel
python -m build
```

---

## Node.js Package

### Installation

```bash
# Install from npm
npm install @aura-protocol/native

# Or with yarn
yarn add @aura-protocol/native
```

### Quick Start

```typescript
import { Compressor, CompressionMethod } from '@aura-protocol/native';

// Initialize compressor
const compressor = new Compressor({
  enableAura: true,
  enableAuditLogging: true,
  sessionId: 'session_123'
});

// Compress message
const text = "I cannot browse the internet.";
const result = compressor.compress(text);

console.log(`Compressed: ${result.metadata.originalSize}B → ${result.payload.length}B`);
console.log(`Method: ${result.metadata.method}`);
console.log(`Ratio: ${result.metadata.ratio.toFixed(2)}:1`);

// Decompress
const decompressed = compressor.decompress(result.payload);
console.assert(decompressed === text);
```

### Client/Server SDKs

```typescript
import { ClientSDK, ServerSDK } from '@aura-protocol/native';

// Client SDK
const client = new ClientSDK({
  templateStorePath: 'templates.json'
});

const payload = Buffer.from([0x00, ...]); // From server
const text = client.decodePayload(payload);

// Server SDK
const server = new ServerSDK({
  enableAura: true,
  enableAuditLogging: true,
  sessionId: 'session_123'
});

const result = server.compress("Hello, world!");
```

### Building from Source

```bash
# Clone repository
git clone https://github.com/yourusername/aura-compression.git
cd aura-compression

# Install dependencies
npm install

# Build TypeScript and native bindings
npm run build

# Run tests
npm test
```

---

## Rust Package

### Installation

Add to your `Cargo.toml`:

```toml
[dependencies]
aura-compression = "1.0.0"

# With WebSocket support
aura-compression = { version = "1.0.0", features = ["websocket"] }

# With CLI tools
aura-compression = { version = "1.0.0", features = ["cli"] }
```

### Quick Start

```rust
use aura_compression::{Compressor, CompressionMethod};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Initialize compressor
    let compressor = Compressor::new(
        true,
        None,
        true,
        Some("session_123".to_string()),
        None,
    );

    // Compress message
    let text = "I cannot browse the internet.";
    let (payload, method, metadata) = compressor.compress(text, None, None)?;

    println!("Compressed: {}B → {}B", metadata.original_size, payload.len());
    println!("Method: {:?}", method);
    println!("Ratio: {:.2}:1", metadata.ratio);

    // Decompress
    let decompressed = compressor.decompress(&payload)?;
    assert_eq!(text, decompressed);

    Ok(())
}
```

### Client/Server SDKs

```rust
use aura_compression::{ClientSDK, ServerSDK};

// Client SDK
let client = ClientSDK::new(
    Some("templates.json".to_string()),
    None,
);

let payload = vec![0x00, ...]; // From server
let (text, _) = client.decode_payload(&payload, false)?;

// Server SDK
let server = ServerSDK::new(
    true,
    None,
    true,
    Some("session_123".to_string()),
    None,
);

let (payload, method, metadata) = server.compress("Hello, world!", None, None)?;
```

### Building from Source

```bash
# Clone repository
git clone https://github.com/yourusername/aura-compression.git
cd aura-compression

# Build release
cargo build --release

# Run tests
cargo test

# Build documentation
cargo doc --open

# Install CLI tools
cargo install --path .
```

### CLI Tools

```bash
# Compress file
aura-compress input.txt -o compressed.aura

# Decompress file
aura-decompress compressed.aura -o output.txt

# Start WebSocket server
aura-server --port 8765 --enable-audit
```

---

## Docker Package

### Quick Start

```bash
# Pull image (when available on Docker Hub)
docker pull aura/compression:latest

# Or build locally
docker build -t aura/compression:latest .

# Run server
docker run -d \
  --name aura-server \
  -p 8765:8765 \
  -v $(pwd)/data:/data \
  -v $(pwd)/logs:/logs \
  -e AURA_ENABLE_AUDIT=true \
  aura/compression:latest
```

### Docker Compose

```bash
# Start production server
docker-compose up -d

# Start with Redis cache
docker-compose --profile cache up -d

# Start with monitoring (Prometheus + Grafana)
docker-compose --profile monitoring up -d

# Development mode with hot reload
docker-compose -f docker-compose.dev.yml up

# Run tests
docker-compose -f docker-compose.dev.yml run --rm aura-test
```

### Environment Variables

```bash
AURA_ENABLE_AUDIT=true          # Enable audit logging
AURA_LOG_LEVEL=info             # Log level (debug, info, warning, error)
AURA_TEMPLATE_STORE=/data/templates.json  # Template store path
AURA_SESSION_ID=default         # Session ID for audit logs
AURA_USER_ID=default            # User ID for audit logs
```

### Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: aura-compression
spec:
  replicas: 3
  selector:
    matchLabels:
      app: aura-compression
  template:
    metadata:
      labels:
        app: aura-compression
    spec:
      containers:
      - name: aura-server
        image: aura/compression:latest
        ports:
        - containerPort: 8765
        env:
        - name: AURA_ENABLE_AUDIT
          value: "true"
        - name: AURA_LOG_LEVEL
          value: "info"
        volumeMounts:
        - name: data
          mountPath: /data
        - name: logs
          mountPath: /logs
      volumes:
      - name: data
        persistentVolumeClaim:
          claimName: aura-data
      - name: logs
        persistentVolumeClaim:
          claimName: aura-logs
```

---

## Performance Benchmarks

### Compression Ratios

| Method | Ratio | Latency | Use Case |
|--------|-------|---------|----------|
| Binary Semantic | 95:1 | <0.1ms | Template matches |
| BRIO | 12:1 | 0.5ms | Multi-template |
| AURA-Lite | 8:1 | 1.2ms | Mixed content |
| AuraLite | 5:1 | 0.8ms | Fallback |

### Throughput

| Language | Compression | Decompression |
|----------|-------------|---------------|
| Rust | 450 MB/s | 620 MB/s |
| Node.js (native) | 380 MB/s | 510 MB/s |
| Python | 180 MB/s | 240 MB/s |

### Memory Usage

| Language | Baseline | Peak |
|----------|----------|------|
| Rust | 2 MB | 8 MB |
| Node.js | 15 MB | 35 MB |
| Python | 25 MB | 55 MB |

---

## Features

### Core Compression

- Binary Semantic Compression (95:1 ratio)
- AuraLite Fallback (5:1 ratio, proprietary)
- BRIO Multi-Template (12:1 ratio)
- AURA-Lite Template+Dictionary (8:1 ratio)
- 607-template library (120 core + 487 discovered)
- 87.1% coverage on AI conversations

### Advanced Features

- Metadata Side-Channel (371× speedup for fast-path)
- Separated Audit Architecture (GDPR/HIPAA/SOC2)
- Template Discovery (Claims 15-18)
- Conversation Accelerator (Claim 31)
- 6-Byte Metadata Entry (Claim 22)
- Client/Server SDKs
- WebSocket server support

### Compliance

- GDPR-compliant separated logs
- HIPAA-compliant audit trails
- SOC2-compliant access logging
- Forensic-grade immutable logs

---

## License

Apache License 2.0

Copyright (c) 2025 Todd James Hendricks

Patent Pending - Application No. 19/366,538

---

## Documentation

- [Python API Documentation](docs/python-api.md)
- [Node.js API Documentation](docs/nodejs-api.md)
- [Rust API Documentation](https://docs.rs/aura-compression)
- [Docker Guide](docs/docker-guide.md)
- [Developer Guide](docs/technical/DEVELOPER_GUIDE.md)
- [Patent Application](docs/business/PROVISIONAL_PATENT_APPLICATION_COMPLETE.md)

---

## Support

- GitHub Issues: https://github.com/yourusername/aura-compression/issues
- Documentation: https://github.com/yourusername/aura-compression/docs
- Email: todd@auraprotocol.org
