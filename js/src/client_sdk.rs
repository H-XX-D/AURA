//! Client SDK implementation

use crate::{Compressor, DecompressionMetadata, Result};
use std::collections::HashMap;

pub struct ClientSDK {
    compressor: Compressor,
}

impl ClientSDK {
    pub fn new(
        template_store_path: Option<String>,
        extra_templates: Option<HashMap<u32, String>>,
    ) -> Self {
        let mut compressor = Compressor::new(true, template_store_path, false, None, None);

        if let Some(templates) = extra_templates {
            for (id, pattern) in templates {
                compressor.register_template(id, pattern);
            }
        }

        Self { compressor }
    }

    pub fn decode_payload(
        &self,
        payload: &[u8],
        return_metadata: bool,
    ) -> Result<(String, Option<DecompressionMetadata>)> {
        let text = self.compressor.decompress(payload)?;

        if return_metadata {
            let method = if !payload.is_empty() {
                crate::CompressionMethod::from_byte(payload[0])?.as_str().to_string()
            } else {
                "unknown".to_string()
            };

            let metadata = DecompressionMetadata {
                method,
                template_ids: vec![],
            };

            Ok((text, Some(metadata)))
        } else {
            Ok((text, None))
        }
    }

    pub fn compress(
        &self,
        text: &str,
        template_id: Option<u32>,
        slots: Option<Vec<String>>,
    ) -> Result<(Vec<u8>, crate::CompressionMethod, crate::CompressionMetadata)> {
        self.compressor.compress(text, template_id, slots)
    }

    pub fn register_template(&mut self, template_id: u32, pattern: String) {
        self.compressor.register_template(template_id, pattern);
    }

    pub fn list_templates(&self) -> HashMap<u32, String> {
        self.compressor.list_templates()
    }
}
