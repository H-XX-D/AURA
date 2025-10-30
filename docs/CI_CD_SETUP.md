# AURA CI/CD Setup Guide

This guide covers the setup and configuration of AURA's CI/CD pipeline for automated multi-platform builds and publishing.

## Overview

AURA uses GitHub Actions for continuous integration and deployment, providing automated builds for multiple platforms and automated publishing to npm.

## Supported Platforms

The CI/CD pipeline builds native binaries for:

- **macOS x64** - Intel-based Macs
- **macOS ARM64** - Apple Silicon (M1/M2/M3)
- **Linux x64** - Most Linux distributions
- **Linux ARM64** - ARM-based Linux systems
- **Windows x64** - Windows 10/11 (MSVC)

## GitHub Actions Workflow

The main workflow file is located at `.github/workflows/npm-build.yml` and includes:

- **Matrix builds** for all supported platforms
- **Native binary compilation** using Rust/NAPI
- **Automated testing** before publishing
- **Artifact uploads** for each platform
- **Automated npm publishing** on successful builds

## Setting up NPM_TOKEN

### Step 1: Generate npm Automation Token

1. Visit [npmjs.com](https://www.npmjs.com) and log in
2. Click your profile picture → **Access Tokens**
3. Click **Generate New Token**
4. Select **Automation** as the token type
5. Add a descriptive name (e.g., "AURA CI/CD")
6. Copy the generated token immediately (it won't be shown again)

### Step 2: Add Token to GitHub Secrets

1. Go to your GitHub repository: `https://github.com/hendrixx-cnc/AURA`
2. Click the **Settings** tab
3. In the left sidebar, click **Secrets and variables** → **Actions**
4. Click **New repository secret**
5. Configure the secret:
   - **Name**: `NPM_TOKEN`
   - **Secret**: Paste the npm token you generated
6. Click **Add secret**

### Step 3: Verify Configuration

1. Push a commit to the `main` branch or create a pull request
2. Go to the **Actions** tab in your repository
3. You should see the "npm-build" workflow running
4. Check that all platform builds complete successfully
5. Verify that the npm package is published (check npmjs.com)

## Workflow Triggers

The CI/CD pipeline runs automatically on:

- **Push to main branch**: Full build and publish cycle
- **Pull requests**: Build verification without publishing
- **Manual trigger**: Via GitHub Actions interface

## Publishing Behavior

### Automatic Publishing
- Only occurs on pushes to the `main` branch
- Requires all tests to pass
- Requires all platform builds to succeed
- Uses the version specified in `package.json`

### Version Management
- Update the version in `package.json` before pushing to `main`
- Use semantic versioning (e.g., 1.2.3)
- The CI/CD will publish the exact version specified

## Troubleshooting

### Build Failures

**Check the Actions logs**:
1. Go to the **Actions** tab
2. Click on the failed workflow run
3. Review the logs for each platform build
4. Common issues:
   - Missing dependencies
   - Rust toolchain issues
   - Node.js version compatibility

### Publishing Failures

**Verify NPM_TOKEN**:
1. Ensure the token is correctly set in repository secrets
2. Check that the token hasn't expired
3. Verify the token has automation permissions

**Check Package Configuration**:
1. Ensure `package.json` has correct name and version
2. Verify all required fields are present
3. Check that the package name is available on npm

### Permission Issues

**Repository Access**:
- Ensure the repository owner has npm publishing permissions
- Check that the NPM_TOKEN belongs to the correct npm account

**GitHub Permissions**:
- The workflow requires write permissions to the repository
- Ensure secrets are accessible to the workflow

## Manual Publishing

If you need to publish manually (not recommended for regular use):

```bash
# Install dependencies
npm install

# Build for all platforms
npm run build

# Publish to npm
npm publish
```

## Security Considerations

- **Token Security**: Never commit npm tokens to the repository
- **Token Rotation**: Regularly rotate automation tokens
- **Minimal Permissions**: Use automation tokens with minimal required permissions
- **Repository Access**: Limit who can modify CI/CD workflows and secrets

## Monitoring

### Build Status
- Check the **Actions** tab for build status
- Set up notifications for failed builds
- Review build times and resource usage

### Publishing Status
- Monitor npmjs.com for package updates
- Check download statistics
- Review any publishing errors

## Advanced Configuration

### Custom Build Matrix
Edit `.github/workflows/npm-build.yml` to modify the build matrix:

```yaml
strategy:
  matrix:
    include:
      - target: x86_64-apple-darwin
        os: macos-latest
      - target: aarch64-apple-darwin
        os: macos-latest
      # Add or remove platforms as needed
```

### Additional Testing
Add custom test steps to the workflow:

```yaml
- name: Run Integration Tests
  run: npm run test:integration
```

### Custom Publishing Logic
Modify the publishing step for custom requirements:

```yaml
- name: Publish to npm
  run: npm publish --tag latest
  env:
    NODE_AUTH_TOKEN: ${{ secrets.NPM_TOKEN }}
```

## Support

For CI/CD issues:
1. Check GitHub Actions documentation
2. Review npm publishing guidelines
3. Contact the development team

## Related Documentation

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [npm Publishing Guide](https://docs.npmjs.com/packages-and-modules/contributing-packages-to-the-registry)
- [Rust/NAPI Documentation](https://napi.rs/)