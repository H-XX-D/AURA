//! # AURA Compression
//!
//! AI-Optimized Hybrid Compression Protocol for Real-Time Communication
//!
//! Copyright (c) 2025 Todd James Hendricks
//! Licensed under Apache License 2.0
//! Patent Pending - Application No. 19/366,538
//!
//! ## Features
//!
//! - **Binary Semantic Compression**: Template-based compression with 95%+ compression ratio
//! - **AuraLite Fallback**: Proprietary fallback compression (replaces Brotli)
//! - **BRIO Multi-Template**: Advanced multi-template compression with LZ77/rANS
//! - **AURA-Lite**: Template + dictionary + literals compression
//! - **Metadata Side-Channel**: Fast-path processing without decompression (371× speedup)
//! - **Separated Audit Architecture**: GDPR/HIPAA/SOC2 compliant logging
//!
//! ## Example
//!
//! ```rust
//! use aura_compression::{Compressor, CompressionMethod};
//!
//! let compressor = Compressor::new(true, None, false, None, None);
//!
//! // Compress message
//! let text = "I cannot browse the internet.";
//! let (payload, method, metadata) = compressor.compress(text, None, None)?;
//!
//! println!("Compressed: {} bytes → {} bytes", metadata.original_size, payload.len());
//! println!("Method: {:?}", method);
//! println!("Ratio: {:.2}:1", metadata.ratio);
//!
//! // Decompress
//! let decompressed = compressor.decompress(&payload)?;
//! assert_eq!(text, decompressed);
//! # Ok::<(), Box<dyn std::error::Error>>(())
//! ```

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use thiserror::Error;

pub mod binary_semantic;
pub mod auralite;
pub mod brio;
pub mod metadata;
pub mod template_library;
pub mod compressor;
pub mod client_sdk;
pub mod server_sdk;

pub use compressor::Compressor;
pub use client_sdk::ClientSDK;
pub use server_sdk::ServerSDK;
pub use template_library::TemplateLibrary;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[repr(u8)]
pub enum CompressionMethod {
    BinarySemantic = 0x00,
    AuraLite = 0x01,
    Brio = 0x02,
    AuraLiteV2 = 0x03,
    Uncompressed = 0xFF,
}

impl CompressionMethod {
    pub fn from_byte(byte: u8) -> Result<Self, AuraError> {
        match byte {
            0x00 => Ok(Self::BinarySemantic),
            0x01 => Ok(Self::AuraLite),
            0x02 => Ok(Self::Brio),
            0x03 => Ok(Self::AuraLiteV2),
            0xFF => Ok(Self::Uncompressed),
            _ => Err(AuraError::UnknownMethod(byte)),
        }
    }

    pub fn as_str(&self) -> &'static str {
        match self {
            Self::BinarySemantic => "binary_semantic",
            Self::AuraLite => "auralite",
            Self::Brio => "brio",
            Self::AuraLiteV2 => "aura_lite",
            Self::Uncompressed => "uncompressed",
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CompressionMetadata {
    pub original_size: usize,
    pub compressed_size: usize,
    pub ratio: f64,
    pub method: String,
    pub template_ids: Vec<u32>,
    pub timestamp: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DecompressionMetadata {
    pub method: String,
    pub template_ids: Vec<u32>,
}

#[derive(Debug, Error)]
pub enum AuraError {
    #[error("Unknown compression method: 0x{0:02x}")]
    UnknownMethod(u8),

    #[error("Compression failed: {0}")]
    CompressionFailed(String),

    #[error("Decompression failed: {0}")]
    DecompressionFailed(String),

    #[error("Template not found: {0}")]
    TemplateNotFound(u32),

    #[error("Invalid payload: {0}")]
    InvalidPayload(String),

    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),

    #[error("JSON error: {0}")]
    Json(#[from] serde_json::Error),
}

pub type Result<T> = std::result::Result<T, AuraError>;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_compression_method_from_byte() {
        assert_eq!(
            CompressionMethod::from_byte(0x00).unwrap(),
            CompressionMethod::BinarySemantic
        );
        assert_eq!(
            CompressionMethod::from_byte(0x01).unwrap(),
            CompressionMethod::AuraLite
        );
        assert_eq!(
            CompressionMethod::from_byte(0x02).unwrap(),
            CompressionMethod::Brio
        );
        assert!(CompressionMethod::from_byte(0x99).is_err());
    }

    #[test]
    fn test_compression_method_as_str() {
        assert_eq!(CompressionMethod::BinarySemantic.as_str(), "binary_semantic");
        assert_eq!(CompressionMethod::AuraLite.as_str(), "auralite");
        assert_eq!(CompressionMethod::Brio.as_str(), "brio");
    }
}
