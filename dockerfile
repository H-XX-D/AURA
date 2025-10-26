# AURA Compression - Production Docker Image
# Multi-stage build for optimized image size

# Stage 1: Python build
FROM python:3.11-slim AS python-builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    && rm -rf /var/lib/apt/lists/*

# Copy Python package files
COPY pyproject.toml setup.py MANIFEST.in README.md LICENSE ./
COPY requirements.txt ./
COPY aura_compression/ ./aura_compression/
COPY packages/ ./packages/

# Build wheel
RUN pip install --no-cache-dir build && \
    python -m build --wheel

# Stage 2: Rust build
FROM rust:1.75-slim AS rust-builder

WORKDIR /build

# Copy Rust package files
COPY Cargo.toml Cargo.lock ./
COPY src/ ./src/

# Build release binary
RUN cargo build --release --bin aura-server

# Stage 3: Node.js build
FROM node:20-slim AS node-builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    make \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy Node.js package files
COPY package.json tsconfig.json binding.gyp ./
COPY src/ ./src/
COPY native/ ./native/

# Install dependencies and build
RUN npm install && \
    npm run build

# Stage 4: Production image
FROM python:3.11-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 aura && \
    mkdir -p /app /data /logs && \
    chown -R aura:aura /app /data /logs

WORKDIR /app

# Copy Python wheel and install
COPY --from=python-builder /build/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && \
    rm /tmp/*.whl

# Copy Rust binaries
COPY --from=rust-builder /build/target/release/aura-server /usr/local/bin/
COPY --from=rust-builder /build/target/release/aura-compress /usr/local/bin/
COPY --from=rust-builder /build/target/release/aura-decompress /usr/local/bin/

# Copy Node.js build
COPY --from=node-builder /build/lib/ ./lib/
COPY --from=node-builder /build/node_modules/ ./node_modules/

# Copy production server
COPY production_websocket_server.py ./
COPY production_hybrid_compression.py ./

# Set permissions
RUN chmod +x /usr/local/bin/aura-* && \
    chown -R aura:aura /app

USER aura

# Expose WebSocket port
EXPOSE 8765

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8765/health || exit 1

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    AURA_ENABLE_AUDIT=true \
    AURA_LOG_LEVEL=info \
    AURA_TEMPLATE_STORE=/data/templates.json

# Default command
CMD ["python", "production_websocket_server.py"]
