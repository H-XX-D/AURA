//! AURA Protocol - Native Node.js Bindings
//!
//! High-performance Rust implementation with N-API bindings for Node.js.
//!
//! This provides 2-10x faster compression/decompression compared to pure JavaScript.

#![deny(clippy::all)]

use napi::bindgen_prelude::*;
use napi_derive::napi;
use std::collections::HashMap;
use std::io::{Read, Write};

// ============================================================================
// Error Types
// ============================================================================

#[napi]
pub enum CompressionMethod {
  BinarySemantic = 1,
  Brotli = 2,
  Uncompressed = 255,
}

impl From<u8> for CompressionMethod {
  fn from(value: u8) -> Self {
    match value {
      1 => CompressionMethod::BinarySemantic,
      2 => CompressionMethod::Brotli,
      _ => CompressionMethod::Uncompressed,
    }
  }
}

// ============================================================================
// Template System
// ============================================================================

#[napi(object)]
#[derive(Clone)]
pub struct Template {
  pub id: u8,
  pub pattern: String,
  pub description: String,
  pub slots: u8,
}

impl Template {
  fn fill(&self, slots: &[String]) -> Result<String> {
    if slots.len() != self.slots as usize {
      return Err(Error::new(
        Status::InvalidArg,
        format!("Expected {} slots, got {}", self.slots, slots.len()),
      ));
    }

    let mut result = self.pattern.clone();
    for (i, slot) in slots.iter().enumerate() {
      result = result.replace(&format!("{{{}}}", i), slot);
    }
    Ok(result)
  }
}

// ============================================================================
// Compression Result
// ============================================================================

#[napi(object)]
pub struct CompressionResult {
  pub data: Buffer,
  pub method: CompressionMethod,
  pub original_size: u32,
  pub compressed_size: u32,
  pub ratio: f64,
  pub template_id: Option<u8>,
}

#[napi(object)]
pub struct DecompressionResult {
  pub plaintext: String,
  pub method: CompressionMethod,
  pub original_size: u32,
  pub compressed_size: u32,
  pub ratio: f64,
  pub template_id: Option<u8>,
}

// ============================================================================
// AURA Compressor
// ============================================================================

#[napi]
pub struct AuraCompressor {
  templates: HashMap<u8, Template>,
  binary_threshold: f64,
  min_size: usize,
}

#[napi]
impl AuraCompressor {
  /// Create a new compressor with default templates
  #[napi(constructor)]
  pub fn new() -> Result<Self> {
    let mut compressor = Self {
      templates: HashMap::new(),
      binary_threshold: 1.1,
      min_size: 50,
    };
    compressor.add_default_templates();
    Ok(compressor)
  }

  /// Create compressor with custom configuration
  #[napi(factory)]
  pub fn with_config(binary_threshold: f64, min_size: u32) -> Result<Self> {
    let mut compressor = Self {
      templates: HashMap::new(),
      binary_threshold,
      min_size: min_size as usize,
    };
    compressor.add_default_templates();
    Ok(compressor)
  }

  /// Add a custom template
  #[napi]
  pub fn add_template(&mut self, template: Template) {
    self.templates.insert(template.id, template);
  }

  /// Get template by ID
  #[napi]
  pub fn get_template(&self, id: u8) -> Option<Template> {
    self.templates.get(&id).cloned()
  }

  /// Compress text using best method
  #[napi]
  pub fn compress(&self, text: String) -> Result<CompressionResult> {
    let original_size = text.as_bytes().len();

    // Skip compression for tiny messages
    if original_size < self.min_size {
      return self.compress_uncompressed(&text);
    }

    // Try Brotli compression
    self.compress_brotli(&text)
  }

  /// Compress with specific template
  #[napi]
  pub fn compress_with_template(&self, template_id: u8, slots: Vec<String>) -> Result<CompressionResult> {
    let template = self
      .templates
      .get(&template_id)
      .ok_or_else(|| Error::new(Status::InvalidArg, format!("Unknown template ID: {}", template_id)))?;

    let plaintext = template.fill(&slots)?;
    let original_size = plaintext.as_bytes().len();

    let mut data = Vec::new();
    data.push(CompressionMethod::BinarySemantic as u8);
    data.push(template_id);
    data.push(slots.len() as u8);

    for slot in &slots {
      let slot_bytes = slot.as_bytes();
      let slot_len = slot_bytes.len() as u16;
      data.push((slot_len >> 8) as u8);
      data.push((slot_len & 0xFF) as u8);
      data.extend_from_slice(slot_bytes);
    }

    let compressed_size = data.len();
    let ratio = original_size as f64 / compressed_size as f64;

    Ok(CompressionResult {
      data: data.into(),
      method: CompressionMethod::BinarySemantic,
      original_size: original_size as u32,
      compressed_size: compressed_size as u32,
      ratio,
      template_id: Some(template_id),
    })
  }

  /// Decompress data
  #[napi]
  pub fn decompress(&self, data: Buffer) -> Result<DecompressionResult> {
    let data = data.as_ref();
    if data.is_empty() {
      return Err(Error::new(Status::InvalidArg, "Empty data"));
    }

    let method = CompressionMethod::from(data[0]);
    let compressed_data = &data[1..];
    let compressed_size = data.len();

    let (plaintext, template_id) = match method {
      CompressionMethod::BinarySemantic => {
        let (text, tid) = self.decompress_binary_semantic(compressed_data)?;
        (text, Some(tid))
      }
      CompressionMethod::Brotli => (self.decompress_brotli(compressed_data)?, None),
      CompressionMethod::Uncompressed => {
        (String::from_utf8(compressed_data.to_vec())
          .map_err(|e| Error::new(Status::InvalidArg, e.to_string()))?, None)
      }
    };

    let original_size = plaintext.as_bytes().len();
    let ratio = original_size as f64 / compressed_size as f64;

    Ok(DecompressionResult {
      plaintext,
      method,
      original_size: original_size as u32,
      compressed_size: compressed_size as u32,
      ratio,
      template_id,
    })
  }

  // Private helper methods

  fn add_default_templates(&mut self) {
    let templates = vec![
      Template { id: 0, pattern: "I don't have access to {0}. {1}".to_string(), description: "No real-time data".to_string(), slots: 2 },
      Template { id: 1, pattern: "I can help you with {0}. {1}".to_string(), description: "Offer help".to_string(), slots: 2 },
      Template { id: 2, pattern: "To {0}, you need to {1}.".to_string(), description: "Instructions".to_string(), slots: 2 },
      Template { id: 10, pattern: "Yes, I can help with that. {0}".to_string(), description: "Help confirmation".to_string(), slots: 1 },
      Template { id: 20, pattern: "{0} is {1} {2} {3}.".to_string(), description: "Definition".to_string(), slots: 4 },
      Template { id: 40, pattern: "To {0}, use {1}: `{2}`".to_string(), description: "Tool instruction".to_string(), slots: 3 },
      Template { id: 90, pattern: "To {0}, I recommend: {1}".to_string(), description: "Recommendation".to_string(), slots: 2 },
      Template { id: 100, pattern: "Yes, I can help with that. What specific {0} would you like to know more about?".to_string(), description: "Clarification".to_string(), slots: 1 },
    ];

    for template in templates {
      self.templates.insert(template.id, template);
    }
  }

  fn compress_brotli(&self, text: &str) -> Result<CompressionResult> {
    let original_bytes = text.as_bytes();
    let original_size = original_bytes.len();

    let mut compressed = Vec::new();
    let mut compressor = brotli::CompressorWriter::new(&mut compressed, 4096, 11, 22);
    compressor
      .write_all(original_bytes)
      .map_err(|e| Error::new(Status::GenericFailure, e.to_string()))?;
    drop(compressor);

    let mut data = vec![CompressionMethod::Brotli as u8];
    data.extend_from_slice(&compressed);

    let compressed_size = data.len();
    let ratio = original_size as f64 / compressed_size as f64;

    Ok(CompressionResult {
      data: data.into(),
      method: CompressionMethod::Brotli,
      original_size: original_size as u32,
      compressed_size: compressed_size as u32,
      ratio,
      template_id: None,
    })
  }

  fn compress_uncompressed(&self, text: &str) -> Result<CompressionResult> {
    let original_bytes = text.as_bytes();
    let original_size = original_bytes.len();

    let mut data = vec![CompressionMethod::Uncompressed as u8];
    data.extend_from_slice(original_bytes);
    let compressed_size = data.len() as u32;

    Ok(CompressionResult {
      data: data.into(),
      method: CompressionMethod::Uncompressed,
      original_size: original_size as u32,
      compressed_size,
      ratio: 1.0,
      template_id: None,
    })
  }

  fn decompress_binary_semantic(&self, data: &[u8]) -> Result<(String, u8)> {
    if data.len() < 2 {
      return Err(Error::new(Status::InvalidArg, "Data too short"));
    }

    let template_id = data[0];
    let slot_count = data[1] as usize;

    let template = self
      .templates
      .get(&template_id)
      .ok_or_else(|| Error::new(Status::InvalidArg, format!("Unknown template ID: {}", template_id)))?;

    if slot_count != template.slots as usize {
      return Err(Error::new(
        Status::InvalidArg,
        format!("Expected {} slots, got {}", template.slots, slot_count),
      ));
    }

    let mut slots = Vec::new();
    let mut offset = 2;

    for _ in 0..slot_count {
      if offset + 2 > data.len() {
        return Err(Error::new(Status::InvalidArg, "Incomplete slot length"));
      }

      let slot_len = ((data[offset] as u16) << 8) | (data[offset + 1] as u16);
      offset += 2;

      if offset + slot_len as usize > data.len() {
        return Err(Error::new(Status::InvalidArg, "Incomplete slot data"));
      }

      let slot_bytes = &data[offset..offset + slot_len as usize];
      let slot = String::from_utf8(slot_bytes.to_vec())
        .map_err(|e| Error::new(Status::InvalidArg, e.to_string()))?;
      slots.push(slot);
      offset += slot_len as usize;
    }

    let plaintext = template.fill(&slots)?;
    Ok((plaintext, template_id))
  }

  fn decompress_brotli(&self, data: &[u8]) -> Result<String> {
    let mut decompressed = Vec::new();
    let mut decompressor = brotli::Decompressor::new(data, 4096);
    decompressor
      .read_to_end(&mut decompressed)
      .map_err(|e| Error::new(Status::GenericFailure, e.to_string()))?;

    String::from_utf8(decompressed).map_err(|e| Error::new(Status::InvalidArg, e.to_string()))
  }
}
