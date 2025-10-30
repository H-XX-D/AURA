#!/usr/bin/env python3
"""
Memory Profiler for AURA Template Libraries
Provides detailed heap analysis and memory leak detection for large template libraries.
"""

import gc
import sys
import tracemalloc
import psutil
import threading
import time
from typing import Dict, List, Any, Optional, Tuple, Set
from collections import defaultdict, Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
import weakref
import inspect
import os
from pathlib import Path


@dataclass
class MemorySnapshot:
    """Snapshot of memory usage at a point in time."""
    timestamp: datetime
    total_memory_mb: float
    template_memory_mb: float
    cache_memory_mb: float
    heap_size_mb: float
    gc_objects: int
    tracemalloc_stats: List[Tuple[str, int]]
    top_allocators: List[Tuple[str, int]]


@dataclass
class MemoryLeak:
    """Detected memory leak information."""
    object_type: str
    count: int
    total_size_bytes: int
    growth_rate: float  # bytes per minute
    first_seen: datetime
    last_seen: datetime
    stack_traces: List[str]


@dataclass
class TemplateMemoryProfile:
    """Memory profile for template library."""
    total_templates: int
    average_template_size_bytes: int
    largest_template_bytes: int
    memory_efficiency: float  # templates per MB
    cache_hit_rate: float
    memory_fragmentation: float
    recommended_cache_size: int


class TemplateMemoryProfiler:
    """
    Advanced memory profiler for AURA template libraries.

    Features:
    - Real-time heap analysis
    - Memory leak detection
    - Template library profiling
    - Cache efficiency analysis
    - Memory fragmentation detection
    - Automated recommendations
    """

    def __init__(self,
                 enable_tracemalloc: bool = True,
                 snapshot_interval_seconds: int = 60,
                 leak_detection_threshold_mb: int = 50,
                 max_snapshots: int = 100):
        """
        Initialize template memory profiler.

        Args:
            enable_tracemalloc: Enable detailed memory tracing
            snapshot_interval_seconds: Seconds between memory snapshots
            leak_detection_threshold_mb: Memory growth threshold for leak detection
            max_snapshots: Maximum number of snapshots to keep
        """
        self.enable_tracemalloc = enable_tracemalloc
        self.snapshot_interval = snapshot_interval_seconds
        self.leak_threshold_bytes = leak_detection_threshold_mb * 1024 * 1024
        self.max_snapshots = max_snapshots

        # Memory tracking
        self.snapshots: List[MemorySnapshot] = []
        self.memory_leaks: List[MemoryLeak] = []
        self.object_refs: Dict[str, Set[int]] = defaultdict(set)  # type -> object ids

        # Template-specific tracking
        self.template_objects: Set[int] = set()
        self.cache_objects: Set[int] = set()

        # Performance monitoring
        self.monitoring_active = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.lock = threading.RLock()

        # Initialize tracing if enabled
        if self.enable_tracemalloc:
            tracemalloc.start()
            tracemalloc.clear_traces()

        # Start monitoring
        self.start_monitoring()

    def start_monitoring(self) -> None:
        """Start background memory monitoring."""
        if self.monitoring_active:
            return

        self.monitoring_active = True

        def monitor_worker():
            while self.monitoring_active:
                try:
                    self._take_memory_snapshot()
                    self._detect_memory_leaks()
                    time.sleep(self.snapshot_interval)
                except Exception as e:
                    print(f"Memory monitoring error: {e}")
                    time.sleep(5)

        self.monitor_thread = threading.Thread(
            target=monitor_worker,
            daemon=True,
            name="template_memory_profiler"
        )
        self.monitor_thread.start()

    def stop_monitoring(self) -> None:
        """Stop memory monitoring."""
        self.monitoring_active = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)

    def register_template_library(self, template_library: Any) -> None:
        """
        Register a template library for specialized tracking.

        Args:
            template_library: Template library object to monitor
        """
        try:
            # Get object ID for tracking
            lib_id = id(template_library)
            self.template_objects.add(lib_id)

            # Try to register internal objects
            if hasattr(template_library, '_cache'):
                cache_id = id(template_library._cache)
                self.cache_objects.add(cache_id)

            if hasattr(template_library, '_templates'):
                templates_id = id(template_library._templates)
                self.template_objects.add(templates_id)

        except Exception as e:
            print(f"Warning: Failed to register template library: {e}")

    def _take_memory_snapshot(self) -> None:
        """Take a comprehensive memory snapshot."""
        timestamp = datetime.now()

        # Get process memory
        process = psutil.Process()
        memory_info = process.memory_info()
        total_memory_mb = memory_info.rss / (1024 * 1024)

        # Get heap information
        heap_size_mb = 0
        gc_objects = 0

        if self.enable_tracemalloc:
            current, peak = tracemalloc.get_traced_memory()
            heap_size_mb = current / (1024 * 1024)

            # Get tracemalloc statistics
            tracemalloc_stats = tracemalloc.take_snapshot().statistics('lineno')
            top_allocators = [(str(stat), stat.size) for stat in tracemalloc_stats[:10]]
        else:
            # Fallback without tracemalloc
            tracemalloc_stats = []
            top_allocators = []

        # Count GC objects
        gc_objects = len(gc.get_objects())

        # Estimate template and cache memory
        template_memory_mb = self._estimate_template_memory()
        cache_memory_mb = self._estimate_cache_memory()

        # Create snapshot
        snapshot = MemorySnapshot(
            timestamp=timestamp,
            total_memory_mb=total_memory_mb,
            template_memory_mb=template_memory_mb,
            cache_memory_mb=cache_memory_mb,
            heap_size_mb=heap_size_mb,
            gc_objects=gc_objects,
            tracemalloc_stats=tracemalloc_stats,
            top_allocators=top_allocators
        )

        with self.lock:
            self.snapshots.append(snapshot)

            # Maintain snapshot limit
            if len(self.snapshots) > self.max_snapshots:
                self.snapshots.pop(0)

    def _estimate_template_memory(self) -> float:
        """Estimate memory used by template objects."""
        if not self.enable_tracemalloc:
            return 0.0

        try:
            snapshot = tracemalloc.take_snapshot()
            total_template_memory = 0

            for stat in snapshot.statistics('traceback'):
                # Check if this allocation is related to templates
                for frame in stat.traceback:
                    if 'template' in frame.filename.lower() or 'template' in str(frame):
                        total_template_memory += stat.size
                        break

            return total_template_memory / (1024 * 1024)

        except Exception:
            return 0.0

    def _estimate_cache_memory(self) -> float:
        """Estimate memory used by cache objects."""
        if not self.enable_tracemalloc:
            return 0.0

        try:
            snapshot = tracemalloc.take_snapshot()
            total_cache_memory = 0

            for stat in snapshot.statistics('traceback'):
                # Check if this allocation is related to cache
                for frame in stat.traceback:
                    if 'cache' in frame.filename.lower() or 'cache' in str(frame):
                        total_cache_memory += stat.size
                        break

            return total_cache_memory / (1024 * 1024)

        except Exception:
            return 0.0

    def _detect_memory_leaks(self) -> None:
        """Detect potential memory leaks by analyzing memory growth patterns."""
        if len(self.snapshots) < 3:
            return

        # Analyze recent snapshots for growth patterns
        recent_snapshots = self.snapshots[-10:]  # Last 10 snapshots

        # Check for continuous memory growth
        memory_values = [s.total_memory_mb for s in recent_snapshots]
        time_values = [(s.timestamp - recent_snapshots[0].timestamp).total_seconds() / 60 for s in recent_snapshots]  # minutes

        if len(memory_values) >= 3:
            # Calculate growth rate (linear regression slope)
            growth_rate = self._calculate_growth_rate(time_values, memory_values)

            # Convert to bytes per minute
            growth_rate_bytes_per_min = growth_rate * 1024 * 1024

            # Check if growth exceeds threshold
            if growth_rate_bytes_per_min > (self.leak_threshold_bytes / 60):  # threshold per minute
                self._analyze_leak_details(recent_snapshots, growth_rate_bytes_per_min)

    def _calculate_growth_rate(self, x_values: List[float], y_values: List[float]) -> float:
        """Calculate linear growth rate using simple linear regression."""
        if len(x_values) != len(y_values) or len(x_values) < 2:
            return 0.0

        n = len(x_values)
        sum_x = sum(x_values)
        sum_y = sum(y_values)
        sum_xy = sum(x * y for x, y in zip(x_values, y_values))
        sum_x2 = sum(x * x for x in x_values)

        denominator = n * sum_x2 - sum_x * sum_x
        if denominator == 0:
            return 0.0

        slope = (n * sum_xy - sum_x * sum_y) / denominator
        return slope

    def _analyze_leak_details(self, snapshots: List[MemorySnapshot], growth_rate: float) -> None:
        """Analyze details of detected memory leak."""
        if not self.enable_tracemalloc or not snapshots:
            return

        # Get memory statistics from most recent snapshot
        recent_snapshot = snapshots[-1]
        previous_snapshot = snapshots[-2] if len(snapshots) > 1 else None

        # Find objects that have grown significantly
        if previous_snapshot:
            # Compare top allocators
            current_allocators = dict(recent_snapshot.top_allocators)
            previous_allocators = dict(previous_snapshot.top_allocators) if previous_snapshot.top_allocators else {}

            for allocator, current_size in current_allocators.items():
                previous_size = previous_allocators.get(allocator, 0)
                growth = current_size - previous_size

                if growth > self.leak_threshold_bytes * 0.1:  # 10% of leak threshold
                    leak = MemoryLeak(
                        object_type=allocator,
                        count=1,  # We don't have exact count
                        total_size_bytes=current_size,
                        growth_rate=growth_rate,
                        first_seen=snapshots[0].timestamp,
                        last_seen=recent_snapshot.timestamp,
                        stack_traces=[allocator]  # Simplified
                    )

                    # Check if we already have this leak
                    existing_leak = None
                    for existing in self.memory_leaks:
                        if existing.object_type == leak.object_type:
                            existing_leak = existing
                            break

                    if existing_leak:
                        existing_leak.last_seen = leak.last_seen
                        existing_leak.total_size_bytes = max(existing_leak.total_size_bytes, leak.total_size_bytes)
                        existing_leak.growth_rate = (existing_leak.growth_rate + leak.growth_rate) / 2
                    else:
                        self.memory_leaks.append(leak)

    def profile_template_library(self, template_library: Any) -> TemplateMemoryProfile:
        """
        Create a detailed memory profile of a template library.

        Args:
            template_library: Template library to profile

        Returns:
            Detailed memory profile
        """
        try:
            # Get basic statistics
            total_templates = len(template_library._templates) if hasattr(template_library, '_templates') else 0

            # Estimate sizes
            template_sizes = []
            if hasattr(template_library, '_templates'):
                for template in template_library._templates.values():
                    if isinstance(template, dict):
                        template_sizes.append(len(str(template)))
                    else:
                        template_sizes.append(sys.getsizeof(template))

            average_size = sum(template_sizes) / max(1, len(template_sizes))
            largest_size = max(template_sizes) if template_sizes else 0

            # Calculate memory efficiency
            total_memory_bytes = sum(template_sizes)
            memory_efficiency = len(template_sizes) / max(1, total_memory_bytes / (1024 * 1024))

            # Get cache statistics
            cache_hit_rate = 0.0
            if hasattr(template_library, 'get_stats'):
                stats = template_library.get_stats()
                cache_hit_rate = stats.get('hit_rate', 0.0)

            # Estimate fragmentation (simplified)
            fragmentation = self._estimate_fragmentation()

            # Recommend cache size based on working set
            recommended_size = self._recommend_cache_size(template_library)

            return TemplateMemoryProfile(
                total_templates=total_templates,
                average_template_size_bytes=int(average_size),
                largest_template_bytes=largest_size,
                memory_efficiency=memory_efficiency,
                cache_hit_rate=cache_hit_rate,
                memory_fragmentation=fragmentation,
                recommended_cache_size=recommended_size
            )

        except Exception as e:
            print(f"Warning: Failed to profile template library: {e}")
            return TemplateMemoryProfile(
                total_templates=0,
                average_template_size_bytes=0,
                largest_template_bytes=0,
                memory_efficiency=0.0,
                cache_hit_rate=0.0,
                memory_fragmentation=0.0,
                recommended_cache_size=10000
            )

    def _estimate_fragmentation(self) -> float:
        """Estimate memory fragmentation (0-1 scale, higher = more fragmented)."""
        if not self.enable_tracemalloc or not self.snapshots:
            return 0.0

        try:
            # Simple fragmentation estimate based on allocation patterns
            recent_snapshot = self.snapshots[-1]

            # Calculate variance in allocation sizes
            sizes = [size for _, size in recent_snapshot.top_allocators]
            if len(sizes) < 2:
                return 0.0

            mean_size = sum(sizes) / len(sizes)
            variance = sum((size - mean_size) ** 2 for size in sizes) / len(sizes)
            std_dev = variance ** 0.5

            # Fragmentation score (coefficient of variation)
            fragmentation = std_dev / max(1, mean_size)

            # Normalize to 0-1 scale
            return min(1.0, fragmentation / 2.0)

        except Exception:
            return 0.0

    def _recommend_cache_size(self, template_library: Any) -> int:
        """Recommend optimal cache size based on usage patterns."""
        try:
            # Base recommendation on available memory and usage patterns
            available_memory_mb = psutil.virtual_memory().available / (1024 * 1024)

            # Use 10% of available memory for cache, but cap at reasonable limits
            memory_based_size = int((available_memory_mb * 0.1) / 0.001)  # ~1KB per entry

            # Adjust based on template library size
            template_count = len(template_library._templates) if hasattr(template_library, '_templates') else 10000

            # Take minimum of memory-based and template-count based recommendations
            recommended = min(memory_based_size, template_count * 2)

            # Ensure reasonable bounds
            return max(1000, min(100000, recommended))

        except Exception:
            return 10000  # Safe default

    def get_memory_report(self) -> Dict[str, Any]:
        """Generate comprehensive memory report."""
        with self.lock:
            if not self.snapshots:
                return {"error": "No memory snapshots available"}

            latest_snapshot = self.snapshots[-1]

            # Calculate memory trends
            memory_trend = "stable"
            if len(self.snapshots) >= 2:
                recent_memory = [s.total_memory_mb for s in self.snapshots[-5:]]
                if recent_memory[-1] > recent_memory[0] * 1.1:  # 10% growth
                    memory_trend = "increasing"
                elif recent_memory[-1] < recent_memory[0] * 0.9:  # 10% decrease
                    memory_trend = "decreasing"

            # Analyze leaks
            active_leaks = [leak for leak in self.memory_leaks
                          if (datetime.now() - leak.last_seen).total_seconds() < 3600]  # Active in last hour

            report = {
                'current_memory': {
                    'total_mb': latest_snapshot.total_memory_mb,
                    'template_mb': latest_snapshot.template_memory_mb,
                    'cache_mb': latest_snapshot.cache_memory_mb,
                    'heap_mb': latest_snapshot.heap_size_mb,
                    'gc_objects': latest_snapshot.gc_objects,
                },
                'memory_trends': {
                    'trend': memory_trend,
                    'peak_memory_mb': max(s.total_memory_mb for s in self.snapshots),
                    'average_memory_mb': sum(s.total_memory_mb for s in self.snapshots) / len(self.snapshots),
                },
                'memory_leaks': {
                    'active_leaks': len(active_leaks),
                    'total_detected_leaks': len(self.memory_leaks),
                    'leak_details': [
                        {
                            'type': leak.object_type,
                            'size_mb': leak.total_size_bytes / (1024 * 1024),
                            'growth_rate_mb_per_min': leak.growth_rate / (1024 * 1024),
                            'first_seen': leak.first_seen.isoformat(),
                            'last_seen': leak.last_seen.isoformat(),
                        }
                        for leak in active_leaks[:5]  # Top 5 leaks
                    ],
                },
                'performance': {
                    'snapshots_taken': len(self.snapshots),
                    'monitoring_active': self.monitoring_active,
                    'tracemalloc_enabled': self.enable_tracemalloc,
                    'snapshot_interval_seconds': self.snapshot_interval,
                },
                'recommendations': self._generate_recommendations(),
            }

            return report

    def _generate_recommendations(self) -> List[str]:
        """Generate memory optimization recommendations."""
        recommendations = []

        if not self.snapshots:
            return recommendations

        latest = self.snapshots[-1]

        # Memory usage recommendations
        if latest.total_memory_mb > 1000:  # Over 1GB
            recommendations.append("High memory usage detected. Consider reducing cache size or template library size.")

        # Leak recommendations
        active_leaks = [l for l in self.memory_leaks
                       if (datetime.now() - l.last_seen).total_seconds() < 3600]
        if active_leaks:
            recommendations.append(f"Memory leaks detected in {len(active_leaks)} object types. Check for circular references.")

        # Fragmentation recommendations
        fragmentation = self._estimate_fragmentation()
        if fragmentation > 0.7:
            recommendations.append("High memory fragmentation detected. Consider memory compaction or cache reorganization.")

        # Cache recommendations
        if latest.cache_memory_mb > latest.template_memory_mb * 2:
            recommendations.append("Cache memory exceeds template memory significantly. Consider cache size optimization.")

        return recommendations

    def force_garbage_collection(self) -> Dict[str, Any]:
        """Force garbage collection and return statistics."""
        initial_objects = len(gc.get_objects())
        initial_uncollectable = gc.collect()

        final_objects = len(gc.get_objects())

        return {
            'objects_before': initial_objects,
            'objects_after': final_objects,
            'objects_collected': initial_objects - final_objects,
            'uncollectable_objects': initial_uncollectable,
            'collection_cycles': gc.get_stats(),
        }

    def __del__(self):
        """Cleanup on destruction."""
        self.stop_monitoring()
        if self.enable_tracemalloc:
            tracemalloc.stop()


def create_template_memory_profiler(enable_tracemalloc: bool = True) -> TemplateMemoryProfiler:
    """
    Factory function to create a template memory profiler.

    Args:
        enable_tracemalloc: Enable detailed memory tracing

    Returns:
        Configured TemplateMemoryProfiler instance
    """
    return TemplateMemoryProfiler(enable_tracemalloc=enable_tracemalloc)