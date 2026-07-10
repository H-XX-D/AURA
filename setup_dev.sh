#!/bin/bash
# AURA Compression Development Setup Script

set -euo pipefail

echo "🚀 Setting up AURA Compression development environment..."

# Check Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "📋 Python version: $python_version"

python3 - <<'PY'
import sys

if not ((3, 10) <= sys.version_info[:2] <= (3, 13)):
    raise SystemExit(
        "AURA development requires Python 3.10 through 3.13; "
        f"found {sys.version_info.major}.{sys.version_info.minor}."
    )
PY

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Install the package in development mode
echo "📦 Installing AURA Compression in development mode..."
pip install -e ".[dev]"

# Run basic tests to verify installation
echo "🧪 Running basic tests..."
make PYTHON=python test-aiwire

echo "✅ Development environment setup complete!"
echo ""
echo "To activate the virtual environment in future sessions:"
echo "  source venv/bin/activate"
echo ""
echo "Available commands:"
echo "  make help          - Show available make commands"
echo "  make test          - Run the complete test suite"
echo "  make test-aiwire   - Run the fast AIWire gate"
echo "  make check         - Run blocking format, lint, and test checks"
echo "  make type-check    - Report the current typing debt"
echo "  make format        - Format code and sort imports"
echo "  make coverage      - Run tests with coverage"
