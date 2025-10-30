//! Template library management

use crate::{AuraError, Result};
use std::collections::HashMap;
use std::fs;

pub struct TemplateLibrary {
    templates: HashMap<u32, String>,
}

impl TemplateLibrary {
    pub fn new() -> Self {
        let mut library = Self {
            templates: HashMap::new(),
        };

        // Load core templates
        library.load_core_templates();

        library
    }

    fn load_core_templates(&mut self) {
        // Core limitation templates (0-9)
        self.templates.insert(0, "I don't have access to {0}. {1}".to_string());
        self.templates.insert(1, "I cannot {0}.".to_string());
        self.templates.insert(2, "I'm unable to {0} because {1}.".to_string());
        self.templates.insert(3, "I don't have the ability to {0}.".to_string());
        self.templates.insert(4, "I'm not able to {0}.".to_string());
        self.templates.insert(5, "I cannot {0} as I {1}.".to_string());
        self.templates.insert(6, "I'm sorry, but I cannot {0}.".to_string());
        self.templates.insert(7, "I don't have {0}.".to_string());
        self.templates.insert(8, "Unfortunately, I cannot {0}.".to_string());
        self.templates.insert(9, "I'm unable to {0}.".to_string());

        // Core facts templates (10-19)
        self.templates.insert(10, "The {0} of {1} is {2}.".to_string());
        self.templates.insert(11, "{0} is {1}.".to_string());
        self.templates.insert(12, "The capital of {0} is {1}.".to_string());
        self.templates.insert(13, "{0} was born in {1}.".to_string());
        self.templates.insert(14, "The population of {0} is approximately {1}.".to_string());
        self.templates.insert(15, "{0} is located in {1}.".to_string());
        self.templates.insert(16, "The year {0} was {1}.".to_string());
        self.templates.insert(17, "{0} occurred in {1}.".to_string());
        self.templates.insert(18, "The distance from {0} to {1} is {2}.".to_string());
        self.templates.insert(19, "{0} is known for {1}.".to_string());
    }

    pub fn register(&mut self, template_id: u32, pattern: String) {
        self.templates.insert(template_id, pattern);
    }

    pub fn format_template(&self, template_id: u32, slots: &[String]) -> Result<String> {
        let pattern = self.templates
            .get(&template_id)
            .ok_or(AuraError::TemplateNotFound(template_id))?;

        let mut result = pattern.clone();
        for (i, slot) in slots.iter().enumerate() {
            let placeholder = format!("{{{}}}", i);
            result = result.replace(&placeholder, slot);
        }

        Ok(result)
    }

    pub fn match_template(&self, text: &str) -> Option<(u32, Vec<String>)> {
        // Simple template matching - try exact matches first
        for (&id, pattern) in &self.templates {
            if let Some(slots) = self.extract_slots(text, pattern) {
                return Some((id, slots));
            }
        }
        None
    }

    fn extract_slots(&self, text: &str, pattern: &str) -> Option<Vec<String>> {
        // Simple slot extraction - split pattern by placeholders
        let parts: Vec<&str> = pattern.split(|c| c == '{' || c == '}').collect();
        let mut slots = Vec::new();
        let mut text_pos = 0;

        for (i, part) in parts.iter().enumerate() {
            if part.is_empty() {
                continue;
            }

            // Check if this is a placeholder index (odd positions)
            if i % 2 == 1 {
                continue; // Skip placeholder indices
            }

            // Find the literal part in text
            if let Some(pos) = text[text_pos..].find(part) {
                // Extract slot value before this literal
                if i > 0 && text_pos < pos + text_pos {
                    slots.push(text[text_pos..pos + text_pos].to_string());
                }
                text_pos = pos + text_pos + part.len();
            } else {
                return None; // Pattern doesn't match
            }
        }

        Some(slots)
    }

    pub fn load_from_file(&mut self, path: &str) -> Result<()> {
        let content = fs::read_to_string(path)?;
        let data: serde_json::Value = serde_json::from_str(&content)?;

        if let Some(templates) = data.get("templates").and_then(|v| v.as_object()) {
            for (key, value) in templates {
                if let (Ok(id), Some(pattern)) = (key.parse::<u32>(), value.get("pattern").and_then(|v| v.as_str())) {
                    self.templates.insert(id, pattern.to_string());
                }
            }
        }

        Ok(())
    }

    pub fn list(&self) -> HashMap<u32, String> {
        self.templates.clone()
    }
}
