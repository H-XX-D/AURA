#!/usr/bin/env python3
"""
Unit tests for GPUAcceleratorService
"""
import unittest
from unittest.mock import patch, MagicMock

from aura_compression.gpu_accelerator_service import (
    GPUAcceleratorService,
    NoOpGPUAcceleratorService,
    create_gpu_accelerator_service,
    GPU_AVAILABLE
)


class TestGPUAcceleratorService(unittest.TestCase):

    def test_gpu_service_creation_enabled(self):
        """Test GPUAcceleratorService creation when enabled"""
        with patch('aura_compression.gpu_accelerator_service.GPU_AVAILABLE', True):
            service = GPUAcceleratorService(enable_gpu=True)
            self.assertTrue(service.is_available())
            self.assertFalse(service.is_enabled())  # Not enabled until initialized

    def test_gpu_service_creation_disabled(self):
        """Test GPUAcceleratorService creation when disabled"""
        service = GPUAcceleratorService(enable_gpu=False)
        self.assertFalse(service.is_enabled())

    def test_noop_gpu_service(self):
        """Test NoOpGPUAcceleratorService"""
        service = NoOpGPUAcceleratorService()

        self.assertFalse(service.is_available())
        self.assertFalse(service.is_enabled())
        self.assertIsNone(service.match_templates_gpu("test"))
        # Should not raise exception
        service.initialize_for_templates(None)

    def test_create_gpu_service_enabled(self):
        """Test factory function creates GPUAcceleratorService when enabled and available"""
        with patch('aura_compression.gpu_accelerator_service.GPU_AVAILABLE', True):
            service = create_gpu_accelerator_service(enable_gpu=True)
            self.assertIsInstance(service, GPUAcceleratorService)

    def test_create_gpu_service_disabled(self):
        """Test factory function creates NoOpGPUAcceleratorService when disabled"""
        service = create_gpu_accelerator_service(enable_gpu=False)
        self.assertIsInstance(service, NoOpGPUAcceleratorService)

    def test_create_gpu_service_unavailable(self):
        """Test factory function creates NoOpGPUAcceleratorService when GPU unavailable"""
        with patch('aura_compression.gpu_accelerator_service.GPU_AVAILABLE', False):
            service = create_gpu_accelerator_service(enable_gpu=True)
            self.assertIsInstance(service, NoOpGPUAcceleratorService)

    @patch('aura_compression.gpu_accelerator_service.TorchGPUTemplateMatch')
    def test_initialize_for_templates_success(self, mock_gpu_class):
        """Test successful GPU initialization with templates"""
        with patch('aura_compression.gpu_accelerator_service.GPU_AVAILABLE', True):
            mock_matcher = MagicMock()
            mock_gpu_class.return_value = mock_matcher

            # Mock template library
            mock_template_lib = MagicMock()
            mock_template_lib.templates = {1: "template1", 2: "template2"}

            service = GPUAcceleratorService(enable_gpu=True)
            service.initialize_for_templates(mock_template_lib)

            # Should be enabled after initialization
            self.assertTrue(service.is_enabled())
            mock_gpu_class.assert_called_once_with(["template1", "template2"])

    @patch('aura_compression.gpu_accelerator_service.TorchGPUTemplateMatch')
    def test_initialize_for_templates_failure(self, mock_gpu_class):
        """Test GPU initialization failure fallback"""
        with patch('aura_compression.gpu_accelerator_service.GPU_AVAILABLE', True):
            mock_gpu_class.side_effect = Exception("GPU init failed")

            mock_template_lib = MagicMock()
            mock_template_lib.templates = {1: "template1"}

            service = GPUAcceleratorService(enable_gpu=True)
            service.initialize_for_templates(mock_template_lib)

            # Should fallback to disabled
            self.assertFalse(service.is_enabled())

    def test_match_templates_gpu_not_enabled(self):
        """Test GPU matching when not enabled returns None"""
        service = GPUAcceleratorService(enable_gpu=False)
        result = service.match_templates_gpu("test text")
        self.assertIsNone(result)

    @patch('aura_compression.gpu_accelerator_service.TorchGPUTemplateMatch')
    def test_match_templates_gpu_success(self, mock_gpu_class):
        """Test successful GPU template matching"""
        with patch('aura_compression.gpu_accelerator_service.GPU_AVAILABLE', True):
            mock_matcher = MagicMock()
            mock_matcher.match_batch_gpu.return_value = ([0], [0.95], {"stats": "test"})
            mock_gpu_class.return_value = mock_matcher

            mock_template_lib = MagicMock()
            mock_template_lib.templates = {5: "template5", 10: "template10"}

            service = GPUAcceleratorService(enable_gpu=True)
            service.initialize_for_templates(mock_template_lib)

            result = service.match_templates_gpu("test text")

            self.assertIsNotNone(result)
            template_id, score, stats = result
            self.assertEqual(template_id, 5)  # First template in sorted order
            self.assertEqual(score, 0.95)

    @patch('aura_compression.gpu_accelerator_service.TorchGPUTemplateMatch')
    def test_match_templates_gpu_index_out_of_range(self, mock_gpu_class):
        """Test GPU matching when index is out of range"""
        with patch('aura_compression.gpu_accelerator_service.GPU_AVAILABLE', True):
            mock_matcher = MagicMock()
            mock_matcher.match_batch_gpu.return_value = ([999], [0.95], {"stats": "test"})
            mock_gpu_class.return_value = mock_matcher

            mock_template_lib = MagicMock()
            mock_template_lib.templates = {1: "template1"}

            service = GPUAcceleratorService(enable_gpu=True)
            service.initialize_for_templates(mock_template_lib)

            result = service.match_templates_gpu("test text")
            self.assertIsNone(result)  # Should return None for out of range

    @patch('aura_compression.gpu_accelerator_service.TorchGPUTemplateMatch')
    def test_match_templates_gpu_exception(self, mock_gpu_class):
        """Test GPU matching exception handling"""
        with patch('aura_compression.gpu_accelerator_service.GPU_AVAILABLE', True):
            mock_matcher = MagicMock()
            mock_matcher.match_batch_gpu.side_effect = Exception("GPU error")
            mock_gpu_class.return_value = mock_matcher

            mock_template_lib = MagicMock()
            mock_template_lib.templates = {1: "template1"}

            service = GPUAcceleratorService(enable_gpu=True)
            service.initialize_for_templates(mock_template_lib)

            result = service.match_templates_gpu("test text")
            self.assertIsNone(result)  # Should return None on exception


if __name__ == '__main__':
    unittest.main()