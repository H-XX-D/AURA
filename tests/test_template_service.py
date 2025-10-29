#!/usr/bin/env python3
"""
Unit tests for TemplateService
"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from aura_compression.template_service import TemplateService, NoOpTemplateService, create_template_service


class TestTemplateService(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def test_template_service_creation(self):
        """Test TemplateService creation with default parameters"""
        service = TemplateService()

        self.assertIsNotNone(service.template_library)
        self.assertTrue(service.enable_normalization)
        self.assertIsNotNone(service.get_normalizer())

    def test_template_service_with_custom_params(self):
        """Test TemplateService with custom parameters"""
        service = TemplateService(
            template_store_path="/tmp/test.json",
            template_cache_size=50,
            enable_normalization=False
        )

        self.assertFalse(service.enable_normalization)
        self.assertIsNone(service.get_normalizer())
        self.assertEqual(service.template_cache_size, 50)

    def test_compress_with_template_zero_slots(self):
        """Test template compression with zero slots"""
        service = TemplateService()

        # This will fail if template 0 doesn't exist, but tests the method
        with self.assertRaises(ValueError):
            service.compress_with_template(0, [])

    def test_normalize_text_enabled(self):
        """Test text normalization when enabled"""
        service = TemplateService(enable_normalization=True)

        text = "Event at 2023-10-27T10:30:00Z completed"
        normalized, metadata = service.normalize_text(text)

        # Should contain normalization metadata
        self.assertIn('normalization_count', metadata)
        self.assertIn('replacements', metadata)

    def test_normalize_text_disabled(self):
        """Test text normalization when disabled"""
        service = TemplateService(enable_normalization=False)

        text = "Event at 2023-10-27T10:30:00Z completed"
        normalized, metadata = service.normalize_text(text)

        # Should return original text with empty metadata
        self.assertEqual(normalized, text)
        self.assertEqual(metadata, {})

    def test_record_template_use(self):
        """Test template usage recording"""
        service = TemplateService()

        # Should not raise exception
        service.record_template_use(1)
        service.record_template_use(255)

    def test_find_template_match(self):
        """Test template matching (placeholder implementation)"""
        service = TemplateService()

        # Currently returns None (placeholder)
        result = service.find_template_match("test text")
        self.assertIsNone(result)

    def test_sync_template_store_no_path(self):
        """Test template store sync when no path is set"""
        service = TemplateService(template_store_path=None)

        # Should not raise exception
        service.sync_template_store()

    def test_ensure_template_loaded(self):
        """Test ensuring template is loaded"""
        service = TemplateService()

        # Should not raise exception even for non-existent template
        service.ensure_template_loaded(999)

    def test_noop_template_service(self):
        """Test NoOpTemplateService"""
        service = NoOpTemplateService()

        # Test all methods don't raise exceptions
        with self.assertRaises(NotImplementedError):
            service.compress_with_template(0, [])

        self.assertIsNone(service.find_template_match("test"))
        service.record_template_use(1)

        normalized, metadata = service.normalize_text("test")
        self.assertEqual(normalized, "test")
        self.assertEqual(metadata, {})

        service.sync_template_store()
        service.ensure_template_loaded(1)

    def test_create_template_service(self):
        """Test factory function"""
        service = create_template_service(
            template_store_path="/tmp/test.json",
            template_cache_size=100,
            enable_normalization=True
        )

        self.assertIsInstance(service, TemplateService)
        self.assertTrue(service.enable_normalization)

    @patch('aura_compression.template_service.get_standard_normalizer')
    def test_normalizer_initialization(self, mock_get_normalizer):
        """Test normalizer initialization"""
        mock_normalizer = MagicMock()
        mock_get_normalizer.return_value = mock_normalizer

        service = TemplateService(enable_normalization=True)

        mock_get_normalizer.assert_called_once()
        self.assertEqual(service.get_normalizer(), mock_normalizer)


if __name__ == '__main__':
    unittest.main()