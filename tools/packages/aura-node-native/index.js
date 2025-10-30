const { platform, arch } = process

let nativeBinding = null
let loadError = null

// Simple platform-specific binary loading without fallbacks
switch (platform) {
  case 'darwin':
    if (arch === 'x64') {
      try {
        nativeBinding = require('./aura-native.darwin-x64.node')
      } catch (e) {
        loadError = e
      }
    } else if (arch === 'arm64') {
      try {
        nativeBinding = require('./aura-native.darwin-arm64.node')
      } catch (e) {
        loadError = e
      }
    } else {
      throw new Error(`Unsupported macOS architecture: ${arch}`)
    }
    break
  case 'linux':
    if (arch === 'x64') {
      try {
        nativeBinding = require('./aura-native.linux-x64-gnu.node')
      } catch (e) {
        loadError = e
      }
    } else if (arch === 'arm64') {
      try {
        nativeBinding = require('./aura-native.linux-arm64-gnu.node')
      } catch (e) {
        loadError = e
      }
    } else {
      throw new Error(`Unsupported Linux architecture: ${arch}`)
    }
    break
  case 'win32':
    if (arch === 'x64') {
      try {
        nativeBinding = require('./aura-native.win32-x64-msvc.node')
      } catch (e) {
        loadError = e
      }
    } else {
      throw new Error(`Unsupported Windows architecture: ${arch}`)
    }
    break
  default:
    throw new Error(`Unsupported platform: ${platform}`)
}

if (!nativeBinding) {
  if (loadError) {
    throw loadError
  }
  throw new Error(`Failed to load native binding for ${platform}-${arch}`)
}

const { CompressionMethod, AuraCompressor } = nativeBinding

module.exports.CompressionMethod = CompressionMethod
module.exports.AuraCompressor = AuraCompressor
