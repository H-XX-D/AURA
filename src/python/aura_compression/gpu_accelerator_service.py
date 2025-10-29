#!/usr/bin/env python3
"""
GPU Accelerator Service - Extracted GPU acceleration functionality from ProductionHybridCompressor
Handles GPU-accelerated template matching with graceful CPU fallback
"""
from typing import Optional, List, Tuple, Dict, Any, Protocol

# GPU imports with graceful fallback
try:
    from .gpu_torch_accelerated import TorchGPUTemplateMatch
    GPU_AVAILABLE = True
    # Type alias for cleaner annotations
    GPUTemplateMatcher = TorchGPUTemplateMatch
except ImportError:
    TorchGPUTemplateMatch = None
    GPU_AVAILABLE = False
    # Fallback type
    GPUTemplateMatcher = Any


class GPUAcceleratorServiceInterface(Protocol):
    """Protocol for GPU accelerator service implementations"""

    def is_available(self) -> bool:
        """Check if GPU acceleration is available"""
        ...

    def is_enabled(self) -> bool:
        """Check if GPU acceleration is enabled"""
        ...

    def match_templates_gpu(self, text: str) -> Optional[Tuple[int, float, Dict[str, Any]]]:
        """
        Perform GPU-accelerated template matching

        Returns:
            Tuple of (template_id, score, stats) or None if no match/fallback to CPU
        """
        ...

    def initialize_for_templates(self, template_library: Any) -> None:
        """Initialize GPU matcher with templates from library"""
        ...


class GPUAcceleratorService(GPUAcceleratorServiceInterface):
    """
    Service for GPU-accelerated template matching with CPU fallback
    """

    def __init__(self, enable_gpu: bool = True):
        """
        Initialize GPU accelerator service

        Args:
            enable_gpu: Whether to enable GPU acceleration if available
        """
        self.enable_gpu = enable_gpu and GPU_AVAILABLE
        self._gpu_matcher: Optional[Any] = None
        self._template_id_map: List[int] = []  # Maps GPU index to template ID

        if self.enable_gpu:
            print("✅ GPU Acceleration service initialized")
        else:
            print("ℹ️  GPU Acceleration service disabled (not available or disabled)")

    def is_available(self) -> bool:
        """Check if GPU acceleration is available on this system"""
        return GPU_AVAILABLE

    def is_enabled(self) -> bool:
        """Check if GPU acceleration is enabled"""
        return self.enable_gpu and self._gpu_matcher is not None

    def initialize_for_templates(self, template_library: Any) -> None:
        """
        Initialize GPU matcher with templates from library

        Args:
            template_library: Template library instance with templates dict
        """
        if not self.enable_gpu or TorchGPUTemplateMatch is None:
            return

        try:
            # Get all templates as strings for GPU matcher
            # templates is a dict {template_id: template_string}
            self._template_id_map = sorted(template_library.templates.keys())
            template_strings = [template_library.templates[tid] for tid in self._template_id_map]

            self._gpu_matcher = TorchGPUTemplateMatch(template_strings)
            print(f"✅ GPU Acceleration enabled for template matching (74-200x speedup)")
        except Exception as e:
            print(f"⚠️  GPU initialization failed, falling back to CPU: {e}")
            self.enable_gpu = False
            self._gpu_matcher = None

    def match_templates_gpu(self, text: str) -> Optional[Tuple[int, float, Dict[str, Any]]]:
        """
        Perform GPU-accelerated template matching

        Args:
            text: Text to match against templates

        Returns:
            Tuple of (template_id, score, stats) or None if no match or fallback needed
        """
        if not self.is_enabled() or self._gpu_matcher is None:
            return None

        try:
            # Use GPU for parallel template matching
            template_indices, scores, stats = self._gpu_matcher.match_batch_gpu([text])
            gpu_index = int(template_indices[0])

            # Map GPU index back to actual template ID
            if gpu_index < len(self._template_id_map):
                best_template_id = self._template_id_map[gpu_index]
                best_score = float(scores[0])
                return (best_template_id, best_score, stats)
            else:
                # Index out of range - fallback to CPU
                return None

        except Exception as e:
            # GPU failed - fallback to CPU
            print(f"⚠️  GPU matching failed, falling back to CPU: {e}")
            return None

    def get_gpu_matcher(self) -> Optional[Any]:
        """Get the underlying GPU matcher (for advanced operations)"""
        return self._gpu_matcher

    def get_template_id_map(self) -> List[int]:
        """Get the template ID mapping"""
        return self._template_id_map.copy()


class NoOpGPUAcceleratorService(GPUAcceleratorServiceInterface):
    """
    No-operation GPU accelerator service for when GPU is disabled
    """

    def is_available(self) -> bool:
        """GPU not available"""
        return False

    def is_enabled(self) -> bool:
        """GPU not enabled"""
        return False

    def match_templates_gpu(self, text: str) -> Optional[Tuple[int, float, Dict[str, Any]]]:
        """No-op implementation - always fallback to CPU"""
        return None

    def initialize_for_templates(self, template_library: Any) -> None:
        """No-op implementation"""
        pass


def create_gpu_accelerator_service(enable_gpu: bool = True) -> GPUAcceleratorServiceInterface:
    """
    Factory function to create appropriate GPU accelerator service

    Args:
        enable_gpu: Whether to enable GPU acceleration if available

    Returns:
        GPUAcceleratorServiceInterface implementation
    """
    if enable_gpu and GPU_AVAILABLE:
        return GPUAcceleratorService(enable_gpu=enable_gpu)
    else:
        return NoOpGPUAcceleratorService()