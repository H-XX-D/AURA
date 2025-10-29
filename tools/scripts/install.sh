#!/bin/bash
# AURA Compression - Installation Script

set -e  # Exit on error

echo "===================================="
echo "AURA Compression - Installation"
echo "===================================="
echo ""

# Check Python version
echo "[1/5] Checking Python version..."
python3 --version || {
    echo "❌ Python 3.8+ is required but not found"
    exit 1
}

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
REQUIRED_VERSION="3.8"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo "❌ Python $REQUIRED_VERSION or higher is required (found $PYTHON_VERSION)"
    exit 1
fi

echo "✅ Python $PYTHON_VERSION detected"
echo ""

# Check pip
echo "[2/5] Checking pip..."
python3 -m pip --version || {
    echo "❌ pip is not installed"
    exit 1
}
echo "✅ pip is available"
echo ""

# Install dependencies
echo "[3/5] Installing dependencies..."
python3 -m pip install -r requirements.txt || {
    echo "❌ Failed to install dependencies"
    exit 1
}
echo "✅ Dependencies installed"
echo ""

# Install AURA package
echo "[4/5] Installing AURA Compression..."
python3 -m pip install -e . || {
    echo "❌ Failed to install AURA package"
    exit 1
}
echo "✅ AURA Compression installed"
echo ""

# Verify installation
echo "[5/5] Verifying installation..."
python3 -c "from aura_compression import AuraCompressor; print('AURA version:', AuraCompressor.__module__)" || {
    echo "❌ Installation verification failed"
    exit 1
}
echo "✅ Installation verified"
echo ""

echo "===================================="
echo "Installation Complete!"
echo "===================================="
echo ""
echo "Try it out:"
echo "  python3 production_websocket_server.py"
echo ""
echo "Or use in your code:"
echo "  from aura_compression import AuraCompressor"
echo "  compressor = AuraCompressor()"
echo ""
