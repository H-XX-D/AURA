#!/bin/bash
# AURA Compression - PyPI Publishing Script

set -e

echo "===================================="
echo "AURA Compression - PyPI Publishing"
echo "===================================="
echo ""

# Check required tools
echo "[1/6] Checking required tools..."
python3 --version || { echo "❌ Python 3 not found"; exit 1; }
python3 -m pip --version || { echo "❌ pip not found"; exit 1; }
echo "✅ Required tools available"
echo ""

# Install build tools
echo "[2/6] Installing build tools..."
python3 -m pip install --upgrade build twine || {
    echo "❌ Failed to install build tools"
    exit 1
}
echo "✅ Build tools installed"
echo ""

# Clean previous builds
echo "[3/6] Cleaning previous builds..."
rm -rf build/ dist/ *.egg-info
echo "✅ Cleaned"
echo ""

# Build package
echo "[4/6] Building package..."
python3 -m build || {
    echo "❌ Build failed"
    exit 1
}
echo "✅ Package built"
echo ""

# Check package
echo "[5/6] Checking package..."
python3 -m twine check dist/* || {
    echo "❌ Package check failed"
    exit 1
}
echo "✅ Package checks passed"
echo ""

# Confirm before upload
echo "[6/6] Ready to upload to PyPI"
echo ""
ls -lh dist/
echo ""
read -p "Upload to PyPI? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "❌ Upload cancelled"
    exit 0
fi

# Upload to PyPI
echo ""
echo "Uploading to PyPI..."
python3 -m twine upload dist/* || {
    echo "❌ Upload failed"
    echo ""
    echo "For test PyPI, use:"
    echo "  python3 -m twine upload --repository testpypi dist/*"
    exit 1
}

echo ""
echo "===================================="
echo "Published Successfully!"
echo "===================================="
echo ""
echo "Package available at:"
echo "  https://pypi.org/project/aura-compression/"
echo ""
echo "Install with:"
echo "  pip install aura-compression"
echo ""
