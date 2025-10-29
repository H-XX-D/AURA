# Package Publishing Guide

This guide covers the complete process for building and publishing AURA Compression packages to PyPI and npm.

## Prerequisites

### For Both Platforms
- Git repository with clean working directory
- All tests passing
- Valid API tokens/accounts

### For PyPI Publishing
- PyPI account: https://pypi.org/account/register/
- API token from: https://pypi.org/manage/account/token/
- `twine` and `build` packages installed

### For npm Publishing
- npm account: https://www.npmjs.com/signup
- API token from: `npm login` or https://www.npmjs.com/settings/tokens
- Node.js and npm installed

## Python Package Publishing (PyPI)

### Automated Publishing Script

The repository includes a comprehensive publishing script:

```bash
# Make script executable (first time only)
chmod +x tools/scripts/publish_pypi.sh

# Run the publishing script
./tools/scripts/publish_pypi.sh
```

### Manual Publishing Steps

If you prefer manual control:

```bash
# 1. Install build tools
pip install --upgrade build twine

# 2. Clean previous builds
rm -rf build/ dist/ *.egg-info

# 3. Build the package
python -m build

# 4. Check the package
python -m twine check dist/*

# 5. Upload to PyPI
python -m twine upload dist/*
```

### Test PyPI (Recommended First)

For testing before production release:

```bash
# Upload to Test PyPI
python -m twine upload --repository testpypi dist/*

# Install from Test PyPI
pip install --index-url https://test.pypi.org/simple/ aura-compression
```

### Environment Setup

Create `~/.pypirc` for authentication:

```ini
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
username = __token__
password = pypi-AgEIcHlwaS5vcmc...

[testpypi]
username = __token__
password = pypi-AgEIcHlwaS5vcmc...
```

## Node.js Package Publishing (npm)

### Publishing the Native Bindings Package

The Node.js package is located in `tools/packages/aura-node-native/`:

```bash
# 1. Navigate to the package directory
cd tools/packages/aura-node-native

# 2. Install dependencies
npm install

# 3. Build the native bindings
npm run build

# 4. Run tests
npm test

# 5. Login to npm (if not already logged in)
npm login

# 6. Dry run (optional)
npm publish --dry-run

# 7. Publish to npm
npm publish
```

### Cross-Platform Builds

For publishing binaries for multiple platforms:

```bash
# Build for all supported platforms
npm run universal

# Or build artifacts for specific platforms
npm run artifacts

# Then publish
npm publish
```

### Version Management

Update version before publishing:

```bash
# Update version (patch)
npm version patch

# Update version (minor)
npm version minor

# Update version (major)
npm version major

# Or set specific version
npm version 1.2.3
```

### Publishing to npm Registry

The package is configured for public publishing:

```json
{
  "name": "@aura-protocol/native",
  "publishConfig": {
    "registry": "https://registry.npmjs.org/",
    "access": "public"
  }
}
```

## Pre-Publishing Checklist

### For Both Packages
- [ ] All tests pass: `npm test` / `python -m pytest`
- [ ] Code is linted and formatted
- [ ] Documentation is up to date
- [ ] Version numbers are correct
- [ ] Changelog is updated
- [ ] License information is accurate

### For Python Package
- [ ] `setup.py` metadata is correct
- [ ] Dependencies are properly specified
- [ ] Python versions supported (3.8+)
- [ ] Package builds successfully: `python -m build`

### For Node.js Package
- [ ] Native bindings build successfully
- [ ] Package includes all necessary files
- [ ] Binary compatibility across platforms
- [ ] TypeScript definitions are included

## Post-Publishing Verification

### Verify PyPI Package
```bash
# Check package page
open https://pypi.org/project/aura-compression/

# Install and test
pip install aura-compression
python -c "from aura_compression import ProductionHybridCompressor; print('✅ Import successful')"
```

### Verify npm Package
```bash
# Check package page
open https://www.npmjs.com/package/@aura-protocol/native

# Install and test
npm install @aura-protocol/native
node -e "const { ProductionHybridCompressor } = require('@aura-protocol/native'); console.log('✅ Import successful')"
```

## Troubleshooting

### PyPI Issues
```bash
# If upload fails due to existing version
# Bump version in setup.py and pyproject.toml
# Then rebuild and re-upload

# If authentication fails
# Check ~/.pypirc file
# Or use: twine upload -u __token__ -p pypi-... dist/*
```

### npm Issues
```bash
# If publish fails due to permissions
npm login
npm whoami

# If version already exists
npm version patch  # or minor/major
npm publish

# If native build fails
npm run build:debug  # for debugging
# Check Rust/Cargo installation
# Verify Node.js version compatibility
```

### Common Issues
- **Version conflicts**: Ensure version is unique and follows semver
- **File permissions**: Check executable permissions on scripts
- **Network issues**: Retry with `--timeout` flags if needed
- **Platform compatibility**: Test on multiple platforms before publishing

## CI/CD Integration

For automated publishing, consider GitHub Actions:

### PyPI Workflow (`.github/workflows/publish-pypi.yml`)
```yaml
name: Publish to PyPI
on:
  release:
    types: [published]
jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install build twine
      - name: Build package
        run: python -m build
      - name: Publish
        run: python -m twine upload dist/*
        env:
          TWINE_USERNAME: __token__
          TWINE_PASSWORD: ${{ secrets.PYPI_API_TOKEN }}
```

### npm Workflow (`.github/workflows/publish-npm.yml`)
```yaml
name: Publish to npm
on:
  release:
    types: [published]
jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'
      - name: Install dependencies
        run: cd tools/packages/aura-node-native && npm ci
      - name: Build
        run: cd tools/packages/aura-node-native && npm run build
      - name: Publish
        run: cd tools/packages/aura-node-native && npm publish
        env:
          NODE_AUTH_TOKEN: ${{ secrets.NPM_TOKEN }}
```</content>
<parameter name="filePath">/Users/hendrixx./AURA/PACKAGE_PUBLISHING_GUIDE.md