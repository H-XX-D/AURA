//! Core compression implementation

use crate::{AuraError, CompressionMetadata, CompressionMethod, Result};
use crate::template_library::TemplateLibrary;
use std::time::{SystemTime, UNIX_EPOCH};

pub struct Compressor {
    enable_aura: bool,
    template_library: TemplateLibrary,
    enable_audit_logging: bool,
    session_id: Option<String>,
    user_id: Option<String>,
    aura_preference_margin: f64,
}

impl Compressor {
    pub fn new(
        enable_aura: bool,
        template_store_path: Option<String>,
        enable_audit_logging: bool,
        session_id: Option<String>,
        user_id: Option<String>,
    ) -> Self {
        let mut template_library = TemplateLibrary::new();

        if let Some(path) = template_store_path {
            if let Err(e) = template_library.load_from_file(&path) {
                log::warn!("Failed to load template store: {}", e);
            }
        }

        Self {
            enable_aura,
            template_library,
            enable_audit_logging,
            session_id,
            user_id,
            aura_preference_margin: 0.1,
        }
    }

    pub fn compress(
        &self,
        text: &str,
        template_id: Option<u32>,
        slots: Option<Vec<String>>,
    ) -> Result<(Vec<u8>, CompressionMethod, CompressionMetadata)> {
        let original_size = text.len();
        let timestamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_secs();

        // Try binary semantic first
        if let Some(tid) = template_id {
            if let Some(slot_list) = slots {
                let payload = self.compress_binary_semantic(tid, &slot_list)?;
                let compressed_size = payload.len();
                let ratio = original_size as f64 / compressed_size as f64;

                return Ok((
                    payload,
                    CompressionMethod::BinarySemantic,
                    CompressionMetadata {
                        original_size,
                        compressed_size,
                        ratio,
                        method: "binary_semantic".to_string(),
                        template_ids: vec![tid],
                        timestamp,
                    },
                ));
            }
        }

        // Try template matching
        if let Some((tid, slots)) = self.template_library.match_template(text) {
            let payload = self.compress_binary_semantic(tid, &slots)?;
            let compressed_size = payload.len();
            let ratio = original_size as f64 / compressed_size as f64;

            return Ok((
                payload,
                CompressionMethod::BinarySemantic,
                CompressionMetadata {
                    original_size,
                    compressed_size,
                    ratio,
                    method: "binary_semantic".to_string(),
                    template_ids: vec![tid],
                    timestamp,
                },
            ));
        }

        // Fallback to AuraLite
        let payload = self.compress_auralite(text)?;
        let compressed_size = payload.len();
        let ratio = original_size as f64 / compressed_size as f64;

        Ok((
            payload,
            CompressionMethod::AuraLite,
            CompressionMetadata {
                original_size,
                compressed_size,
                ratio,
                method: "auralite".to_string(),
                template_ids: vec![],
                timestamp,
            },
        ))
    }

    fn compress_binary_semantic(&self, template_id: u32, slots: &[String]) -> Result<Vec<u8>> {
        let mut payload = vec![0x00]; // Binary semantic method
        payload.push(template_id as u8);
        payload.push(slots.len() as u8);

        for slot in slots {
            let slot_bytes = slot.as_bytes();
            payload.extend_from_slice(&(slot_bytes.len() as u16).to_be_bytes());
            payload.extend_from_slice(slot_bytes);
        }

        Ok(payload)
    }

    fn compress_auralite(&self, text: &str) -> Result<Vec<u8>> {
        // Simple AuraLite implementation
        let mut payload = vec![0x01]; // AuraLite method
        let text_bytes = text.as_bytes();
        payload.extend_from_slice(&(text_bytes.len() as u32).to_be_bytes());
        payload.extend_from_slice(text_bytes);
        Ok(payload)
    }

    pub fn decompress(&self, payload: &[u8]) -> Result<String> {
        if payload.is_empty() {
            return Err(AuraError::InvalidPayload("Empty payload".to_string()));
        }

        let method = CompressionMethod::from_byte(payload[0])?;

        match method {
            CompressionMethod::BinarySemantic => self.decompress_binary_semantic(&payload[1..]),
            CompressionMethod::AuraLite | CompressionMethod::AuraLiteV2 => {
                self.decompress_auralite(&payload[1..])
            }
            CompressionMethod::Uncompressed => {
                String::from_utf8(payload[1..].to_vec())
                    .map_err(|e| AuraError::DecompressionFailed(e.to_string()))
            }
            _ => Err(AuraError::UnknownMethod(payload[0])),
        }
    }

    fn decompress_binary_semantic(&self, data: &[u8]) -> Result<String> {
        if data.len() < 2 {
            return Err(AuraError::InvalidPayload("Malformed binary payload".to_string()));
        }

        let template_id = data[0] as u32;
        let slot_count = data[1] as usize;
        let mut offset = 2;
        let mut slots = Vec::new();

        for _ in 0..slot_count {
            if offset + 2 > data.len() {
                return Err(AuraError::InvalidPayload("Malformed binary payload".to_string()));
            }

            let slot_len = u16::from_be_bytes([data[offset], data[offset + 1]]) as usize;
            offset += 2;

            if offset + slot_len > data.len() {
                return Err(AuraError::InvalidPayload("Malformed binary payload".to_string()));
            }

            let slot = String::from_utf8(data[offset..offset + slot_len].to_vec())
                .map_err(|e| AuraError::DecompressionFailed(e.to_string()))?;
            slots.push(slot);
            offset += slot_len;
        }

        self.template_library.format_template(template_id, &slots)
    }

    fn decompress_auralite(&self, data: &[u8]) -> Result<String> {
        if data.len() < 4 {
            return Err(AuraError::InvalidPayload("Malformed AuraLite payload".to_string()));
        }

        let text_len = u32::from_be_bytes([data[0], data[1], data[2], data[3]]) as usize;

        if data.len() < 4 + text_len {
            return Err(AuraError::InvalidPayload("Malformed AuraLite payload".to_string()));
        }

        String::from_utf8(data[4..4 + text_len].to_vec())
            .map_err(|e| AuraError::DecompressionFailed(e.to_string()))
    }

    pub fn register_template(&mut self, template_id: u32, pattern: String) {
        self.template_library.register(template_id, pattern);
    }

    pub fn list_templates(&self) -> HashMap<u32, String> {
        self.template_library.list()
    }
}
