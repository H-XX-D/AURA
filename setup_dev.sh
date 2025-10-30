#!/bin/bash
# AURA Compression Development Setup Script

set -e

echo "🚀 Setting up AURA Compression development environment..."

# Check Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "📋 Python version: $python_version"

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
python tests/test_metadata_sidechain_routing.py

echo "✅ Development environment setup complete!"
echo ""
echo "To activate the virtual environment in future sessions:"
echo "  source venv/bin/activate"
echo ""
echo "Available commands:"
echo "  make help          - Show available make commands"
echo "  make test          - Run basic tests"
echo "  make test-all      - Run all tests with pytest"
echo "  make lint          - Run linting"
echo "  make format        - Format code"
echo "  make coverage      - Run tests with coverage"