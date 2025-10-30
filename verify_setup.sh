#!/bin/bash

# AURA CI/CD Setup Verification Script
# Run this script to verify your local development environment and CI/CD configuration

set -e

echo "🔍 AURA CI/CD Setup Verification"
echo "=================================="

# Check if we're in the right directory
if [ ! -f "package.json" ] || [ ! -f "pyproject.toml" ]; then
    echo "❌ Error: Please run this script from the AURA project root directory"
    exit 1
fi

echo "✅ Project structure verified"

# Check Node.js version
NODE_VERSION=$(node --version | sed 's/v//')
REQUIRED_NODE="16.0.0"
if [ "$(printf '%s\n' "$REQUIRED_NODE" "$NODE_VERSION" | sort -V | head -n1)" = "$REQUIRED_NODE" ]; then
    echo "✅ Node.js version: $NODE_VERSION (meets requirement >= $REQUIRED_NODE)"
else
    echo "❌ Node.js version: $NODE_VERSION (requires >= $REQUIRED_NODE)"
fi

# Check npm version
NPM_VERSION=$(npm --version)
echo "ℹ️  npm version: $NPM_VERSION"

# Check Rust version
if command -v rustc &> /dev/null; then
    RUST_VERSION=$(rustc --version | awk '{print $2}')
    echo "✅ Rust version: $RUST_VERSION"
else
    echo "❌ Rust not found. Please install Rust: https://rustup.rs/"
fi

# Check cargo
if command -v cargo &> /dev/null; then
    echo "✅ Cargo available"
else
    echo "❌ Cargo not found. Please install Rust toolchain."
fi

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
REQUIRED_PYTHON="3.8.0"
if [ "$(printf '%s\n' "$REQUIRED_PYTHON" "$PYTHON_VERSION" | sort -V | head -n1)" = "$REQUIRED_PYTHON" ]; then
    echo "✅ Python version: $PYTHON_VERSION (meets requirement >= $REQUIRED_PYTHON)"
else
    echo "❌ Python version: $PYTHON_VERSION (requires >= $REQUIRED_PYTHON)"
fi

# Check pip
if command -v pip3 &> /dev/null; then
    echo "✅ pip available"
else
    echo "❌ pip not found"
fi

# Check GitHub CLI (optional)
if command -v gh &> /dev/null; then
    GH_VERSION=$(gh --version | head -n1 | awk '{print $3}')
    echo "✅ GitHub CLI version: $GH_VERSION"
else
    echo "⚠️  GitHub CLI not found (optional for CI/CD management)"
fi

# Check if we're in a git repository
if git rev-parse --git-dir > /dev/null 2>&1; then
    echo "✅ Git repository detected"

    # Check if remote origin exists
    if git remote get-url origin &> /dev/null; then
        REMOTE_URL=$(git remote get-url origin)
        if [[ $REMOTE_URL == *"github.com"* ]]; then
            echo "✅ GitHub remote configured: $REMOTE_URL"
        else
            echo "⚠️  Remote is not GitHub: $REMOTE_URL"
        fi
    else
        echo "❌ No remote origin configured"
    fi

    # Check current branch
    CURRENT_BRANCH=$(git branch --show-current)
    echo "ℹ️  Current branch: $CURRENT_BRANCH"

else
    echo "❌ Not in a git repository"
fi

# Check package.json configuration
if [ -f "package.json" ]; then
    PACKAGE_NAME=$(node -p "require('./package.json').name" 2>/dev/null || echo "unknown")
    PACKAGE_VERSION=$(node -p "require('./package.json').version" 2>/dev/null || echo "unknown")
    echo "ℹ️  npm package: $PACKAGE_NAME@$PACKAGE_VERSION"
fi

# Check pyproject.toml configuration
if [ -f "pyproject.toml" ]; then
    # Extract version using grep/sed since toml parsing might not be available
    PY_VERSION=$(grep -E '^version\s*=' pyproject.toml | head -n1 | sed 's/.*= *"\?\([^"]*\)"\?.*/\1/' || echo "unknown")
    echo "ℹ️  Python package version: $PY_VERSION"
fi

# Check for GitHub Actions workflow
if [ -f ".github/workflows/npm-build.yml" ]; then
    echo "✅ GitHub Actions workflow found: .github/workflows/npm-build.yml"
else
    echo "❌ GitHub Actions workflow missing: .github/workflows/npm-build.yml"
fi

# Check for README documentation
if [ -f "README.md" ]; then
    if grep -q "NPM_TOKEN" README.md; then
        echo "✅ README.md contains NPM_TOKEN setup instructions"
    else
        echo "⚠️  README.md may be missing NPM_TOKEN setup instructions"
    fi
else
    echo "❌ README.md not found"
fi

# Check for CI/CD documentation
if [ -f "docs/CI_CD_SETUP.md" ]; then
    echo "✅ CI/CD setup documentation found: docs/CI_CD_SETUP.md"
else
    echo "⚠️  CI/CD setup documentation not found"
fi

echo ""
echo "🎯 Next Steps:"
echo "1. If any ❌ items above, fix them before proceeding"
echo "2. Set up NPM_TOKEN in GitHub repository secrets (see docs/CI_CD_SETUP.md)"
echo "3. Push changes to trigger CI/CD pipeline"
echo "4. Monitor GitHub Actions for build results"
echo ""
echo "📚 Documentation:"
echo "- Main README: README.md"
echo "- CI/CD Setup: docs/CI_CD_SETUP.md"
echo "- GitHub Actions: .github/workflows/npm-build.yml"