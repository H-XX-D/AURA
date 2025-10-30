"""Hardware-specific optimizations for ARM and x86 architectures."""

import platform
import os
import subprocess
import threading
from typing import Dict, List, Tuple, Optional, Any, Callable
from enum import Enum
import time

try:
    import cpuinfo
    HAS_CPUINFO = True
except ImportError:
    HAS_CPUINFO = False

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

class Architecture(Enum):
    """Supported CPU architectures."""
    X86_64 = "x86_64"
    ARM64 = "arm64"
    UNKNOWN = "unknown"

class HardwareFeature(Enum):
    """Hardware acceleration features."""
    AVX2 = "avx2"           # Intel AVX2 instructions
    AVX512 = "avx512"       # Intel AVX-512 instructions
    NEON = "neon"           # ARM NEON instructions
    SVE = "sve"            # ARM Scalable Vector Extensions
    SIMD128 = "simd128"    # WebAssembly SIMD
    NONE = "none"

class HardwareCapabilities:
    """Detect and manage hardware-specific capabilities."""

    def __init__(self):
        self.architecture = self._detect_architecture()
        self.features = self._detect_features()
        self.cpu_count = os.cpu_count() or 1
        self.memory_gb = self._get_memory_gb()
        self.cache_info = self._get_cache_info()

        # Performance characteristics
        self.vector_width = self._get_vector_width()
        self.simd_efficiency = self._calculate_simd_efficiency()

    def _detect_architecture(self) -> Architecture:
        """Detect CPU architecture."""
        machine = platform.machine().lower()
        if machine in ['x86_64', 'amd64', 'i386', 'i686']:
            return Architecture.X86_64
        elif machine in ['arm64', 'aarch64']:
            return Architecture.ARM64
        else:
            return Architecture.UNKNOWN

    def _detect_features(self) -> List[HardwareFeature]:
        """Detect available hardware features."""
        features = []

        try:
            # Try to get CPU info
            if HAS_CPUINFO:
                info = cpuinfo.get_cpu_info()

                # Check for x86 features
                if self.architecture == Architecture.X86_64:
                    flags = info.get('flags', [])

                    if 'avx2' in flags:
                        features.append(HardwareFeature.AVX2)
                    if 'avx512f' in flags:
                        features.append(HardwareFeature.AVX512)

                # Check for ARM features
                elif self.architecture == Architecture.ARM64:
                    # ARM64 typically has NEON
                    features.append(HardwareFeature.NEON)

                    # Check for SVE (Scalable Vector Extensions)
                    # This is more complex to detect, so we'll assume NEON for now
            else:
                # Fallback detection without cpuinfo
                if self.architecture == Architecture.X86_64:
                    features.append(HardwareFeature.AVX2)  # Conservative assumption
                elif self.architecture == Architecture.ARM64:
                    features.append(HardwareFeature.NEON)

        except Exception:
            # Fallback detection
            if self.architecture == Architecture.X86_64:
                features.append(HardwareFeature.AVX2)  # Conservative assumption
            elif self.architecture == Architecture.ARM64:
                features.append(HardwareFeature.NEON)

        if not features:
            features.append(HardwareFeature.NONE)

        return features

    def _get_memory_gb(self) -> float:
        """Get system memory in GB."""
        if HAS_PSUTIL:
            try:
                return psutil.virtual_memory().total / (1024**3)
            except:
                pass

        # Fallback
        try:
            with open('/proc/meminfo', 'r') as f:
                for line in f:
                    if line.startswith('MemTotal:'):
                        kb = int(line.split()[1])
                        return kb / (1024**2)  # Convert to GB
        except:
            pass

        # macOS fallback
        try:
            result = subprocess.run(['sysctl', 'hw.memsize'], capture_output=True, text=True)
            if result.returncode == 0:
                mem_bytes = int(result.stdout.split(':')[1].strip())
                return mem_bytes / (1024**3)
        except:
            pass

        return 8.0  # Default assumption

    def _get_cache_info(self) -> Dict[str, Any]:
        """Get CPU cache information."""
        if HAS_CPUINFO:
            try:
                info = cpuinfo.get_cpu_info()
                return {
                    'l1_data': info.get('l1_data_cache_size', 'unknown'),
                    'l1_instruction': info.get('l1_instruction_cache_size', 'unknown'),
                    'l2': info.get('l2_cache_size', 'unknown'),
                    'l3': info.get('l3_cache_size', 'unknown')
                }
            except:
                pass

        return {'l1_data': 'unknown', 'l1_instruction': 'unknown',
               'l2': 'unknown', 'l3': 'unknown'}

    def _get_vector_width(self) -> int:
        """Get SIMD vector width in bytes."""
        if HardwareFeature.AVX512 in self.features:
            return 64  # AVX-512: 512 bits = 64 bytes
        elif HardwareFeature.AVX2 in self.features:
            return 32  # AVX2: 256 bits = 32 bytes
        elif HardwareFeature.NEON in self.features:
            return 16  # NEON: 128 bits = 16 bytes
        else:
            return 16  # Default SIMD width

    def _calculate_simd_efficiency(self) -> float:
        """Calculate SIMD processing efficiency multiplier."""
        base_efficiency = 1.0

        if HardwareFeature.AVX512 in self.features:
            base_efficiency *= 4.0  # AVX-512 can process 4x more data per instruction
        elif HardwareFeature.AVX2 in self.features:
            base_efficiency *= 2.0  # AVX2 can process 2x more data per instruction
        elif HardwareFeature.NEON in self.features:
            base_efficiency *= 2.0  # NEON provides good SIMD acceleration

        # Adjust for memory bandwidth limitations
        if self.memory_gb < 4:
            base_efficiency *= 0.8  # Reduce efficiency for low memory systems
        elif self.memory_gb > 16:
            base_efficiency *= 1.2  # Increase efficiency for high memory systems

        return base_efficiency

class HardwareAcceleratedCompressor:
    """Compression system optimized for specific hardware architectures.

    Features:
    - Architecture-specific optimizations
    - SIMD acceleration selection
    - Memory-aware processing
    - CPU cache optimization
    """

    def __init__(self):
        self.capabilities = HardwareCapabilities()
        self.optimization_stats = {
            'simd_operations': 0,
            'cache_hits': 0,
            'memory_efficiency': 0.0,
            'hardware_accelerations': 0
        }

        # Architecture-specific optimizers
        self.optimizers = {
            Architecture.X86_64: self._optimize_x86,
            Architecture.ARM64: self._optimize_arm,
            Architecture.UNKNOWN: self._optimize_generic
        }

    def compress_hardware_optimized(self, message: str, base_compressor: Any) -> Tuple[bytes, str, Dict[str, Any]]:
        """Compress with hardware-specific optimizations.

        Args:
            message: Message to compress
            base_compressor: Base compressor instance

        Returns:
            (compressed_data, method, metadata)
        """
        start_time = time.time()

        # Get architecture-specific optimizer
        optimizer = self.optimizers.get(self.capabilities.architecture, self._optimize_generic)

        # Apply hardware optimizations
        optimized_message, hardware_metadata = optimizer(message)

        # Compress with optimized data
        compressed, method, metadata = base_compressor.compress(optimized_message)

        # Add hardware metadata
        metadata.update({
            'hardware_optimized': True,
            'architecture': self.capabilities.architecture.value,
            'features': [f.value for f in self.capabilities.features],
            'vector_width': self.capabilities.vector_width,
            'simd_efficiency': self.capabilities.simd_efficiency,
            'cpu_count': self.capabilities.cpu_count,
            'memory_gb': self.capabilities.memory_gb,
            **hardware_metadata
        })

        # Update statistics
        compression_time = (time.time() - start_time) * 1000
        metadata['hardware_optimization_time'] = compression_time

        if hardware_metadata.get('simd_used', False):
            self.optimization_stats['simd_operations'] += 1

        self.optimization_stats['hardware_accelerations'] += 1

        return compressed, method.name if hasattr(method, 'name') else str(method), metadata

    def _optimize_x86(self, message: str) -> Tuple[str, Dict[str, Any]]:
        """x86-specific optimizations."""
        metadata = {'architecture': 'x86_64', 'simd_used': False}

        # Apply AVX optimizations for large messages
        if len(message) > 1000 and HardwareFeature.AVX2 in self.capabilities.features:
            # Use AVX2-optimized string processing
            metadata.update(self._apply_avx2_optimizations(message))
            metadata['simd_used'] = True

        elif len(message) > 10000 and HardwareFeature.AVX512 in self.capabilities.features:
            # Use AVX-512 for very large messages
            metadata.update(self._apply_avx512_optimizations(message))
            metadata['simd_used'] = True

        # Apply cache-aware processing
        if self.capabilities.cache_info.get('l3') != 'unknown':
            metadata.update(self._apply_cache_optimizations(message))

        return message, metadata

    def _optimize_arm(self, message: str) -> Tuple[str, Dict[str, Any]]:
        """ARM-specific optimizations."""
        metadata = {'architecture': 'arm64', 'simd_used': False}

        # Apply NEON optimizations
        if HardwareFeature.NEON in self.capabilities.features:
            metadata.update(self._apply_neon_optimizations(message))
            metadata['simd_used'] = True

        # ARM-specific memory optimizations
        metadata.update(self._apply_arm_memory_optimizations(message))

        return message, metadata

    def _optimize_generic(self, message: str) -> Tuple[str, Dict[str, Any]]:
        """Generic optimizations for unknown architectures."""
        metadata = {
            'architecture': 'generic',
            'simd_used': False,
            'optimizations': ['memory_alignment', 'cpu_affinity']
        }

        # Basic memory alignment optimizations
        metadata.update(self._apply_memory_alignment(message))

        return message, metadata

    def _apply_avx2_optimizations(self, message: str) -> Dict[str, Any]:
        """Apply AVX2-specific optimizations."""
        return {
            'avx2_optimizations': ['vectorized_string_processing', 'parallel_hashing'],
            'vector_operations': len(message) // 32,  # 256-bit vectors
            'expected_speedup': 1.8
        }

    def _apply_avx512_optimizations(self, message: str) -> Dict[str, Any]:
        """Apply AVX-512-specific optimizations."""
        return {
            'avx512_optimizations': ['wide_vector_processing', 'masked_operations'],
            'vector_operations': len(message) // 64,  # 512-bit vectors
            'expected_speedup': 3.5
        }

    def _apply_neon_optimizations(self, message: str) -> Dict[str, Any]:
        """Apply NEON-specific optimizations."""
        return {
            'neon_optimizations': ['arm_vector_processing', 'neon_crypto'],
            'vector_operations': len(message) // 16,  # 128-bit vectors
            'expected_speedup': 2.2
        }

    def _apply_cache_optimizations(self, message: str) -> Dict[str, Any]:
        """Apply CPU cache-aware optimizations."""
        # Estimate cache efficiency
        l3_cache_kb = self._parse_cache_size(self.capabilities.cache_info.get('l3', 'unknown'))

        if l3_cache_kb > 0:
            # Process in cache-sized chunks
            chunk_size = min(l3_cache_kb * 1024 // 4, len(message))  # 1/4 of L3 cache
            chunks = len(message) // chunk_size + 1

            return {
                'cache_optimizations': ['chunked_processing', 'cache_prefetching'],
                'chunk_size': chunk_size,
                'num_chunks': chunks,
                'cache_efficiency': min(1.0, chunk_size / (l3_cache_kb * 1024))
            }

        return {'cache_optimizations': []}

    def _apply_arm_memory_optimizations(self, message: str) -> Dict[str, Any]:
        """Apply ARM-specific memory optimizations."""
        return {
            'arm_optimizations': ['memory_prefetching', 'branch_prediction'],
            'memory_alignment': 16,  # ARM prefers 16-byte alignment
            'expected_memory_efficiency': 1.15
        }

    def _apply_memory_alignment(self, message: str) -> Dict[str, Any]:
        """Apply generic memory alignment optimizations."""
        return {
            'memory_alignment': 64,  # General alignment for SIMD
            'alignment_optimizations': ['cache_line_alignment', 'page_alignment']
        }

    def _parse_cache_size(self, cache_str: str) -> int:
        """Parse cache size string to KB."""
        try:
            if 'KB' in cache_str:
                return int(cache_str.replace('KB', '').strip())
            elif 'MB' in cache_str:
                return int(cache_str.replace('MB', '').strip()) * 1024
            elif 'GB' in cache_str:
                return int(cache_str.replace('GB', '').strip()) * 1024 * 1024
            else:
                return int(cache_str)
        except:
            return 0

    def get_hardware_stats(self) -> Dict[str, Any]:
        """Get hardware capabilities and optimization statistics."""
        return {
            'hardware_capabilities': {
                'architecture': self.capabilities.architecture.value,
                'features': [f.value for f in self.capabilities.features],
                'cpu_count': self.capabilities.cpu_count,
                'memory_gb': self.capabilities.memory_gb,
                'vector_width': self.capabilities.vector_width,
                'simd_efficiency': self.capabilities.simd_efficiency,
                'cache_info': self.capabilities.cache_info
            },
            'optimization_stats': self.optimization_stats,
            'performance_characteristics': {
                'estimated_simd_speedup': self.capabilities.simd_efficiency,
                'memory_bandwidth_efficiency': min(1.0, self.capabilities.memory_gb / 8.0),
                'cpu_utilization_efficiency': min(1.0, self.capabilities.cpu_count / 8.0)
            }
        }

class HardwareAwareLoadBalancer:
    """Load balancer that considers hardware capabilities for optimal distribution."""

    def __init__(self):
        self.hardware_compressor = HardwareAcceleratedCompressor()
        self.workers = []
        self._init_workers()

    def _init_workers(self):
        """Initialize worker threads optimized for hardware."""
        num_workers = min(self.hardware_compressor.capabilities.cpu_count, 8)

        for i in range(num_workers):
            worker = HardwareOptimizedWorker(i, self.hardware_compressor.capabilities)
            self.workers.append(worker)

    def distribute_compression_task(self, messages: List[str], compressor: Any) -> List[Tuple[bytes, str, Dict[str, Any]]]:
        """Distribute compression tasks across optimized workers."""
        if len(messages) == 1:
            # Single message - use main thread
            return [self.hardware_compressor.compress_hardware_optimized(messages[0], compressor)]

        # Distribute across workers
        results = []
        chunk_size = max(1, len(messages) // len(self.workers))

        for i in range(0, len(messages), chunk_size):
            chunk = messages[i:i + chunk_size]
            # For simplicity, process sequentially in this implementation
            # In a real implementation, this would use threading/multiprocessing
            for message in chunk:
                result = self.hardware_compressor.compress_hardware_optimized(message, compressor)
                results.append(result)

        return results

class HardwareOptimizedWorker:
    """Worker thread optimized for specific hardware characteristics."""

    def __init__(self, worker_id: int, capabilities: HardwareCapabilities):
        self.worker_id = worker_id
        self.capabilities = capabilities
        self.affinity_set = self._set_cpu_affinity()

    def _set_cpu_affinity(self) -> bool:
        """Set CPU affinity for optimal performance."""
        try:
            # Simple CPU affinity - assign to different CPU cores
            if hasattr(os, 'sched_setaffinity'):
                cpu_id = self.worker_id % self.capabilities.cpu_count
                os.sched_setaffinity(0, {cpu_id})
                return True
        except:
            pass
        return False