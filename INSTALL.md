# AURA Compression Installation Guide

This guide covers all installation methods for AURA Compression across different platforms and environments.

## Table of Contents

- [Quick Start](#quick-start)
- [Python Installation](#python-installation)
- [Node.js Installation](#nodejs-installation)
- [Docker Installation](#docker-installation)
- [Development Setup](#development-setup)
- [System Requirements](#system-requirements)
- [Troubleshooting](#troubleshooting)

## Quick Start

### One-Line Install (Python)
```bash
pip install aura-compression
```

### One-Line Install (Node.js)
```bash
npm install @aura-protocol/native
```

### Docker (All-in-One)
```bash
docker run -p 8765:8765 aura/compression:latest
```

## Python Installation

### From PyPI (Recommended)
```bash
# Install latest stable version
pip install aura-compression

# Install with development dependencies
pip install aura-compression[dev]

# Install specific version
pip install aura-compression==1.0.0
```

### From Source
```bash
# Clone repository
git clone https://github.com/hendrixx-cnc/AURA.git
cd AURA

# Install in development mode
pip install -e .

# Install with all dependencies
pip install -e .[dev,docs,test]

# Install specific components
pip install -e .[gpu]        # GPU acceleration support
pip install -e .[server]     # WebSocket server
pip install -e .[all]        # Everything
```

### Virtual Environment (Recommended)
```bash
# Create virtual environment
python -m venv aura-env
source aura-env/bin/activate  # On Windows: aura-env\Scripts\activate

# Install AURA
pip install aura-compression

# Verify installation
python -c "from aura_compression import ProductionHybridCompressor; print('AURA installed successfully!')"
```

### Conda Installation
```bash
# Create conda environment
conda create -n aura python=3.11
conda activate aura

# Install AURA
pip install aura-compression

# Or use conda-forge (when available)
conda install -c conda-forge aura-compression
```

## Node.js Installation

### From npm (Recommended)
```bash
# Install latest stable version
npm install @aura-protocol/native

# Install globally
npm install -g @aura-protocol/native

# Install as dev dependency
npm install --save-dev @aura-protocol/native

# Install specific version
npm install @aura-protocol/native@0.1.0
```

### From Source (Development)
```bash
# Clone repository
git clone https://github.com/hendrixx-cnc/AURA.git
cd AURA

# Install dependencies
npm install

# Build native bindings
npm run build

# Link for development
npm link

# Run tests
npm test
```

### Yarn Installation
```bash
# Install latest stable version
yarn add @aura-protocol/native

# Install globally
yarn global add @aura-protocol/native

# Install as dev dependency
yarn add --dev @aura-protocol/native
```

### PNPM Installation
```bash
# Install latest stable version
pnpm add @aura-protocol/native

# Install globally
pnpm add -g @aura-protocol/native
```

## Docker Installation

### Pre-built Images

#### Production Server
```bash
# Pull latest image
docker pull aura/compression:latest

# Run WebSocket server
docker run -p 8765:8765 -d \
  --name aura-server \
  -v $(pwd)/data:/data \
  -v $(pwd)/logs:/logs \
  aura/compression:latest

# Check server health
curl http://localhost:8765/health
```

#### Development Environment
```bash
# Pull development image
docker pull aura/compression:dev

# Run with development tools
docker run -it -p 8765:8765 \
  -v $(pwd):/app \
  -v $(pwd)/data:/data \
  aura/compression:dev
```

### Docker Compose (Recommended)

#### Production Setup
```bash
# Clone repository
git clone https://github.com/hendrixx-cnc/AURA.git
cd AURA

# Start production services
docker-compose -f config/docker-compose.yml up -d

# View logs
docker-compose logs -f aura-server

# Scale services
docker-compose up -d --scale aura-server=3
```

#### Development Setup
```bash
# Start development environment
docker-compose -f config/docker-compose.dev.yml up -d

# Run tests in container
docker-compose exec aura-server npm test

# Access development shell
docker-compose exec aura-server bash
```

### Custom Docker Build
```bash
# Build from source
docker build -f config/dockerfile -t aura-custom .

# Build with specific Python version
docker build --build-arg PYTHON_VERSION=3.11 -f config/dockerfile -t aura-python311 .

# Build with GPU support
docker build --build-arg ENABLE_GPU=true -f config/dockerfile -t aura-gpu .
```

### Kubernetes Deployment
```bash
# Apply Kubernetes manifests
kubectl apply -f k8s/

# Check deployment status
kubectl get pods -l app=aura-compression

# Scale deployment
kubectl scale deployment aura-compression --replicas=5

# View logs
kubectl logs -f deployment/aura-compression
```

## Development Setup

### Full Development Environment
```bash
# Clone repository
git clone https://github.com/hendrixx-cnc/AURA.git
cd AURA

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install Python dependencies
pip install -e .[dev,docs,test,gpu]

# Install Node.js dependencies
npm install

# Build all components
npm run build:all

# Run full test suite
python test_runner.py

# Start development server
python tools/scripts/production_websocket_server.py --dev
```

### IDE Setup

#### VS Code
```json
{
  "python.defaultInterpreterPath": "./.venv/bin/python",
  "python.linting.enabled": true,
  "python.formatting.provider": "black",
  "typescript.preferences.importModuleSpecifier": "relative"
}
```

#### PyCharm
- Set Python interpreter to `.venv/bin/python`
- Enable pytest as test runner
- Configure Node.js for TypeScript compilation

### GPU Acceleration Setup
```bash
# Install CUDA (if not already installed)
# Follow NVIDIA CUDA installation guide for your platform

# Install PyTorch with CUDA
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# Install AURA with GPU support
pip install aura-compression[gpu]

# Verify GPU support
python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')"
```

## System Requirements

### Minimum Requirements
- **Python**: 3.8+
- **Node.js**: 16.0+
- **Memory**: 2GB RAM
- **Disk**: 500MB free space
- **Network**: Internet connection for package downloads

### Recommended Requirements
- **Python**: 3.11+
- **Node.js**: 18.0+
- **Memory**: 8GB RAM
- **Disk**: 2GB free space
- **CPU**: Multi-core processor
- **Network**: High-speed internet

### Platform Support
- **Operating Systems**: Linux, macOS, Windows
- **Architectures**: x64, ARM64
- **Containers**: Docker, Podman, Kubernetes

### Optional Dependencies
- **CUDA**: 11.8+ (for GPU acceleration)
- **Rust**: 1.70+ (for native extensions)
- **Java**: 11+ (for some integrations)

## Troubleshooting

### Python Installation Issues

#### Import Error
```bash
# Reinstall with clean cache
pip uninstall aura-compression
pip cache purge
pip install --no-cache-dir aura-compression
```

#### Permission Error
```bash
# Install with user permissions
pip install --user aura-compression

# Or use virtual environment
python -m venv aura-env
source aura-env/bin/activate
pip install aura-compression
```

#### Build Dependencies Missing
```bash
# Install system dependencies (Ubuntu/Debian)
sudo apt-get update
sudo apt-get install python3-dev gcc g++

# Install system dependencies (macOS)
brew install python gcc

# Install system dependencies (Windows)
# Install Visual Studio Build Tools
```

### Node.js Installation Issues

#### Native Build Failures
```bash
# Clear npm cache
npm cache clean --force

# Reinstall dependencies
rm -rf node_modules package-lock.json
npm install

# Use pre-built binaries
npm install @aura-protocol/native --build-from-source=false
```

#### Python Not Found
```bash
# Ensure Python is available
python --version
pip --version

# Set Python path explicitly
npm config set python /usr/bin/python3
```

### Docker Issues

#### Port Already in Use
```bash
# Find process using port 8765
lsof -i :8765

# Kill process or use different port
docker run -p 8766:8765 aura/compression:latest
```

#### Permission Denied
```bash
# Add user to docker group (Linux)
sudo usermod -aG docker $USER

# Restart session or run:
newgrp docker
```

#### Build Failures
```bash
# Clear Docker cache
docker system prune -a

# Build with no cache
docker build --no-cache -f config/dockerfile -t aura-custom .
```

### Performance Issues

#### High Memory Usage
```bash
# Limit memory usage
export AURA_MAX_MEMORY=512MB

# Use streaming compression
from aura_compression import StreamingCompressor
```

#### Slow Compression
```bash
# Enable hardware acceleration
compressor = ProductionHybridCompressor(enable_gpu=True)

# Adjust compression level
compressor = ProductionHybridCompressor(level='fast')
```

### Network Issues

#### Connection Refused
```bash
# Check if server is running
curl http://localhost:8765/health

# Start server
docker-compose up -d aura-server
```

#### WebSocket Connection Issues
```bash
# Check firewall settings
sudo ufw allow 8765

# Use secure WebSocket (WSS)
wss://your-domain.com:8765
```

## Support

### Documentation
- [API Reference](docs/api/)
- [Technical Guide](docs/technical/)
- [Performance Benchmarks](docs/benchmarks/)

### Community
- [GitHub Issues](https://github.com/hendrixx-cnc/AURA/issues)
- [GitHub Discussions](https://github.com/hendrixx-cnc/AURA/discussions)
- [Discord Community](https://discord.gg/aura-compression)

### Professional Support
- Enterprise support: enterprise@auraprotocol.org
- Consulting services: consulting@auraprotocol.org
- Training workshops: training@auraprotocol.org

---

**AURA Compression** - Transform your data infrastructure with AI-optimized compression technology.