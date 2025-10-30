# AURA Compression - Project Structure

This document outlines the organized project structure for the AURA compression system.

## Directory Structure

```
AURA/
├── js/                          # Node.js/TypeScript components
│   ├── package.json            # Node.js package configuration
│   ├── package-lock.json       # Node.js lockfile
│   ├── node_modules/           # Node.js dependencies
│   ├── tsconfig.json           # TypeScript configuration
│   ├── binding.gyp             # Native module bindings
│   └── src/                    # JavaScript/TypeScript source
├── rust/                        # Rust components
│   └── cargo.toml              # Rust package configuration
├── src/                         # Source code
│   └── python/                 # Python source code
├── tests/                       # Test suite
│   ├── test_runner.py          # Master test runner
│   ├── test_compression_core.py
│   ├── test_compression_methods.py
│   ├── test_compression_thresholds.py
│   ├── test_audit_integration.py
│   └── README.md               # Test documentation
├── config/                      # Configuration files
│   ├── docker/                 # Docker configurations
│   ├── deployment/             # Deployment configs
│   ├── development/            # Development configs
│   ├── docker-compose.yml      # Docker compose
│   ├── docker-compose.dev.yml  # Development compose
│   ├── dockerfile              # Main dockerfile
│   ├── dockerfile.dev          # Development dockerfile
│   ├── dockerfile_dev          # Alternative dev dockerfile
│   └── manifest.in             # Python manifest
├── docs/                        # Documentation
│   ├── api/                    # API documentation
│   ├── audit/                  # Audit documentation
│   ├── business/               # Business documentation
│   ├── guides/                 # User guides
│   ├── packages/               # Package documentation
│   ├── technical/              # Technical documentation
│   ├── CI_CD_SETUP.md          # CI/CD setup
│   └── INSTALL.md              # Installation guide
├── tools/                       # Development tools
├── benchmarks/                  # Benchmark scripts and data
├── data/                        # Data files
├── audit_logs/                  # Audit log storage (runtime)
├── logs/                        # Application logs (runtime)
├── results/                     # Result files (runtime)
├── pyproject.toml               # Python project configuration
├── setup.py                     # Python setup script
├── requirements.txt             # Python dependencies
├── readme.md                    # Main project README
├── LICENSE                      # License file
├── .gitignore                   # Git ignore patterns
├── .dockerignore                # Docker ignore patterns
└── verify_setup.sh              # Setup verification script
```

## Language-Specific Organization

### Python Components
- **Source**: `src/python/`
- **Config**: `pyproject.toml`, `setup.py`, `requirements.txt`
- **Tests**: `tests/`
- **Entry Points**: CLI scripts defined in `pyproject.toml`

### Node.js/TypeScript Components
- **Source**: `js/src/`
- **Config**: `js/package.json`, `js/tsconfig.json`
- **Build**: `js/binding.gyp` for native modules
- **Dependencies**: `js/node_modules/`

### Rust Components
- **Config**: `rust/cargo.toml`
- **Source**: Referenced from cargo.toml

## Configuration Files

All configuration files are centralized in the `config/` directory:
- Docker configurations in `config/docker/`
- Deployment configs in `config/deployment/`
- Development configs in `config/development/`

## Runtime Data

Directories for runtime-generated data:
- `audit_logs/`: Audit logs (ignored by git)
- `logs/`: Application logs (ignored by git)
- `results/`: Result files (ignored by git)

## Development Workflow

### Python Development
```bash
# Install Python dependencies
pip install -r requirements.txt

# Run tests
python tests/test_runner.py

# Install in development mode
pip install -e .
```

### Node.js Development
```bash
# Change to js directory
cd js

# Install dependencies
npm install

# Run tests
npm test

# Build
npm run build
```

### Docker Development
```bash
# Build container
docker build -f config/dockerfile -t aura .

# Run container
docker run -p 8765:8765 aura
```

## File Organization Principles

1. **Language Separation**: Each language has its own directory
2. **Configuration Centralization**: All config files in `config/`
3. **Runtime Data Isolation**: Generated files in separate directories
4. **Clear Documentation**: Comprehensive docs in `docs/`
5. **Test Organization**: All tests in `tests/` with master runner