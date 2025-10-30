"""Adaptive Template Cache with Working Set Analysis and Memory Tuning."""

import json
import hashlib
import os
import psutil
import threading
import time
from pathlib import Path
from typing import Dict, Optional, Any, List, Tuple, Set
from collections import defaultdict, Counter, deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import gc
import sys
from datetime import datetime, timedelta


@dataclass
class CacheEntry:
    """Enhanced cache entry with metadata."""
    data: Dict[str, Any]
    access_count: int = 0
    last_access: float = 0.0
    first_access: float = 0.0
    size_bytes: int = 0
    hit_rate: float = 0.0


@dataclass
class WorkingSetAnalysis:
    """Analysis of cache working set patterns."""
    hot_entries: Set[str]  # Frequently accessed entries
    cold_entries: Set[str]  # Rarely accessed entries
    working_set_size: int  # Estimated working set size
    access_pattern: str  # 'temporal', 'spatial', 'mixed'
    temporal_locality: float  # Measure of temporal locality (0-1)
    spatial_locality: float  # Measure of spatial locality (0-1)
    churn_rate: float  # Rate of cache turnover


class AdaptiveTemplateCache:
    """
    Adaptive template cache with working set analysis and memory tuning.

    Features:
    - Working set analysis and pattern recognition
    - Adaptive cache sizing based on memory usage
    - Memory profiling and leak detection
    - Intelligent eviction policies
    - Performance monitoring and optimization
    """

    def __init__(self,
                 cache_dir: str = ".aura_cache",
                 initial_max_size: int = 10000,
                 memory_limit_mb: int = 512,
                 analysis_window_hours: int = 24,
                 adaptation_interval_minutes: int = 30,
                 enable_memory_profiling: bool = True):
        """
        Initialize adaptive template cache.

        Args:
            cache_dir: Directory to store cache files
            initial_max_size: Initial maximum number of cache entries
            memory_limit_mb: Memory limit for cache in MB
            analysis_window_hours: Hours of history to analyze for working sets
            adaptation_interval_minutes: Minutes between cache size adaptations
            enable_memory_profiling: Enable detailed memory profiling
        """
        self.cache_dir = Path(cache_dir)
        self.memory_limit_bytes = memory_limit_mb * 1024 * 1024
        self.analysis_window_seconds = analysis_window_hours * 3600
        self.adaptation_interval_seconds = adaptation_interval_minutes * 60

        # Cache storage
        self._cache: Dict[str, CacheEntry] = {}
        self._access_history: deque = deque(maxlen=100000)  # Recent access history
        self._lock = threading.RLock()

        # Working set analysis
        self._working_set_analysis: Optional[WorkingSetAnalysis] = None
        self._last_analysis = 0.0

        # Adaptive sizing
        self.current_max_size = initial_max_size
        self.min_cache_size = 1000
        self.max_cache_size = 50000
        self._last_adaptation = 0.0

        # Memory profiling
        self.enable_memory_profiling = enable_memory_profiling
        self.memory_stats = {
            'peak_usage_bytes': 0,
            'current_usage_bytes': 0,
            'allocation_rate': 0.0,
            'deallocation_rate': 0.0,
            'memory_pressure': 0.0,
            'gc_collections': 0,
            'memory_leaks_detected': 0
        }

        # Performance tracking
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self.adaptations = 0

        # Background tasks
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="adaptive_cache")
        self._shutdown = False

        # Cache files
        self.cache_file = self.cache_dir / "adaptive_template_cache.json"
        self.stats_file = self.cache_dir / "cache_stats.json"

        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Load existing cache
        self._load_cache()

        # Start background tasks
        self._start_background_tasks()

    def _make_key(self, text: str) -> str:
        """Create a cache key from text using SHA256 hash."""
        return hashlib.sha256(text.encode('utf-8')).hexdigest()

    def get(self, text: str) -> Optional[Dict[str, Any]]:
        """Get cached template match data for text with enhanced tracking."""
        cache_key = self._make_key(text)
        current_time = time.time()

        with self._lock:
            if cache_key in self._cache:
                entry = self._cache[cache_key]

                # Update access statistics
                entry.access_count += 1
                entry.last_access = current_time
                entry.hit_rate = entry.access_count / max(1, (current_time - entry.first_access) / 3600)  # hits per hour

                # Record access in history
                self._access_history.append((cache_key, current_time))

                self.hits += 1
                return entry.data.copy()
            else:
                self.misses += 1
                # Record miss in history
                self._access_history.append((cache_key, current_time))
                return None

    def put(self, text: str, match_data: Dict[str, Any]) -> None:
        """Store template match data with size tracking."""
        cache_key = self._make_key(text)
        current_time = time.time()

        # Estimate entry size
        entry_size = self._estimate_entry_size(match_data)

        with self._lock:
            # Check memory limits
            if self._check_memory_pressure():
                self._adaptive_resize()

            # Evict if necessary
            while len(self._cache) >= self.current_max_size:
                self._intelligent_evict()

            # Create new entry
            entry = CacheEntry(
                data=match_data.copy(),
                access_count=1,
                last_access=current_time,
                first_access=current_time,
                size_bytes=entry_size
            )

            self._cache[cache_key] = entry
            self._access_history.append((cache_key, current_time))

        # Update memory stats
        self._update_memory_stats()

    def _estimate_entry_size(self, data: Dict[str, Any]) -> int:
        """Estimate memory usage of cache entry."""
        # Rough estimation: JSON size + Python object overhead
        json_size = len(json.dumps(data, default=str))
        return json_size + 256  # Add overhead for Python objects

    def _check_memory_pressure(self) -> bool:
        """Check if we're under memory pressure."""
        if not self.enable_memory_profiling:
            return False

        try:
            process = psutil.Process()
            memory_info = process.memory_info()
            current_usage = memory_info.rss

            # Update memory stats
            self.memory_stats['current_usage_bytes'] = current_usage
            self.memory_stats['peak_usage_bytes'] = max(
                self.memory_stats['peak_usage_bytes'],
                current_usage
            )

            # Calculate memory pressure (0-1 scale)
            pressure = min(1.0, current_usage / self.memory_limit_bytes)
            self.memory_stats['memory_pressure'] = pressure

            return pressure > 0.8  # 80% threshold

        except Exception:
            return False

    def _adaptive_resize(self) -> None:
        """Adaptively resize cache based on memory pressure and working set analysis."""
        current_time = time.time()

        # Don't adapt too frequently
        if current_time - self._last_adaptation < self.adaptation_interval_seconds:
            return

        # Analyze working set
        working_set = self._analyze_working_set()

        # Calculate optimal size based on working set and memory pressure
        memory_pressure = self.memory_stats['memory_pressure']

        if memory_pressure > 0.9:
            # High memory pressure: reduce cache size
            new_size = max(self.min_cache_size, int(self.current_max_size * 0.7))
        elif memory_pressure < 0.5:
            # Low memory pressure: can increase cache size
            new_size = min(self.max_cache_size, int(self.current_max_size * 1.2))
        else:
            # Moderate pressure: optimize for working set
            new_size = max(self.min_cache_size,
                          min(self.max_cache_size,
                              working_set.working_set_size * 2))

        if new_size != self.current_max_size:
            old_size = self.current_max_size
            self.current_max_size = new_size
            self.adaptations += 1
            self._last_adaptation = current_time

            print(f"Cache resized: {old_size} -> {new_size} entries "
                  f"(memory pressure: {memory_pressure:.2f})")

            # Evict excess entries if we shrunk
            if new_size < old_size:
                self._evict_to_size(new_size)

    def _analyze_working_set(self) -> WorkingSetAnalysis:
        """Analyze cache working set patterns."""
        current_time = time.time()

        # Don't re-analyze too frequently
        if current_time - self._last_analysis < 3600:  # Once per hour
            if self._working_set_analysis:
                return self._working_set_analysis

        # Get recent access history
        cutoff_time = current_time - self.analysis_window_seconds
        recent_accesses = [(k, t) for k, t in self._access_history if t >= cutoff_time]

        if not recent_accesses:
            # Default analysis if no recent data
            return WorkingSetAnalysis(
                hot_entries=set(),
                cold_entries=set(self._cache.keys()),
                working_set_size=len(self._cache) // 4,
                access_pattern='unknown',
                temporal_locality=0.0,
                spatial_locality=0.0,
                churn_rate=0.0
            )

        # Count accesses per key
        access_counts = Counter(k for k, t in recent_accesses)
        access_times = {}
        for k, t in recent_accesses:
            if k not in access_times:
                access_times[k] = []
            access_times[k].append(t)

        # Identify hot and cold entries
        sorted_by_access = sorted(access_counts.items(), key=lambda x: x[1], reverse=True)
        total_accesses = sum(access_counts.values())

        # Top 20% are hot, bottom 50% are cold
        hot_threshold = max(1, int(len(sorted_by_access) * 0.2))
        cold_threshold = int(len(sorted_by_access) * 0.5)

        hot_entries = set(k for k, c in sorted_by_access[:hot_threshold])
        cold_entries = set(k for k, c in sorted_by_access[cold_threshold:])

        # Estimate working set size (entries that make up 80% of accesses)
        cumulative_accesses = 0
        working_set_size = 0
        for k, count in sorted_by_access:
            cumulative_accesses += count
            working_set_size += 1
            if cumulative_accesses >= total_accesses * 0.8:
                break

        # Analyze access patterns
        temporal_locality = self._calculate_temporal_locality(access_times)
        spatial_locality = self._calculate_spatial_locality(recent_accesses)

        if temporal_locality > 0.7:
            access_pattern = 'temporal'
        elif spatial_locality > 0.7:
            access_pattern = 'spatial'
        else:
            access_pattern = 'mixed'

        # Calculate churn rate (new entries vs total)
        recent_keys = set(k for k, t in recent_accesses)
        total_keys = set(self._cache.keys())
        new_keys = recent_keys - (total_keys - recent_keys)
        churn_rate = len(new_keys) / max(1, len(recent_keys))

        analysis = WorkingSetAnalysis(
            hot_entries=hot_entries,
            cold_entries=cold_entries,
            working_set_size=max(1000, working_set_size),
            access_pattern=access_pattern,
            temporal_locality=temporal_locality,
            spatial_locality=spatial_locality,
            churn_rate=churn_rate
        )

        self._working_set_analysis = analysis
        self._last_analysis = current_time

        return analysis

    def _calculate_temporal_locality(self, access_times: Dict[str, List[float]]) -> float:
        """Calculate temporal locality metric."""
        if not access_times:
            return 0.0

        # Measure how clustered accesses are in time
        all_times = []
        for times in access_times.values():
            all_times.extend(times)

        if len(all_times) < 2:
            return 0.0

        all_times.sort()
        intervals = [all_times[i+1] - all_times[i] for i in range(len(all_times)-1)]

        if not intervals:
            return 0.0

        # Coefficient of variation of intervals (lower = more clustered = higher locality)
        mean_interval = sum(intervals) / len(intervals)
        if mean_interval == 0:
            return 1.0

        variance = sum((i - mean_interval) ** 2 for i in intervals) / len(intervals)
        cv = (variance ** 0.5) / mean_interval

        # Convert to locality score (0-1, higher is better locality)
        return max(0.0, 1.0 - min(1.0, cv / 2.0))

    def _calculate_spatial_locality(self, accesses: List[Tuple[str, float]]) -> float:
        """Calculate spatial locality metric."""
        if len(accesses) < 2:
            return 0.0

        # Count consecutive accesses to same key
        consecutive_same = 0
        total_transitions = 0

        prev_key = None
        for key, _ in accesses:
            if prev_key is not None:
                total_transitions += 1
                if key == prev_key:
                    consecutive_same += 1
            prev_key = key

        return consecutive_same / max(1, total_transitions)

    def _intelligent_evict(self) -> None:
        """Evict entries using intelligent policy based on working set analysis."""
        if not self._cache:
            return

        working_set = self._analyze_working_set()

        # Never evict hot entries
        evictable_entries = [
            (key, entry) for key, entry in self._cache.items()
            if key not in working_set.hot_entries
        ]

        if not evictable_entries:
            # Fallback to LRU if all entries are hot
            evictable_entries = list(self._cache.items())

        # Sort by eviction priority (lower score = evict first)
        # Priority based on: recency, frequency, size, working set membership
        current_time = time.time()

        def eviction_priority(item):
            key, entry = item
            in_working_set = key in working_set.hot_entries

            # Calculate priority score (lower = more likely to evict)
            recency_score = (current_time - entry.last_access) / 3600  # Hours since last access
            frequency_score = 1.0 / max(1, entry.hit_rate)  # Lower hit rate = higher priority
            size_penalty = entry.size_bytes / 1000  # Larger entries slightly preferred for eviction
            working_set_bonus = 0 if in_working_set else 1  # Don't evict working set

            return recency_score + frequency_score + size_penalty + working_set_bonus

        evictable_entries.sort(key=eviction_priority, reverse=True)  # Sort descending (highest priority first)

        # Evict the worst candidate
        if evictable_entries:
            evict_key, _ = evictable_entries[0]
            del self._cache[evict_key]
            self.evictions += 1

    def _evict_to_size(self, target_size: int) -> None:
        """Evict entries until cache reaches target size."""
        while len(self._cache) > target_size:
            self._intelligent_evict()

    def _update_memory_stats(self) -> None:
        """Update detailed memory statistics."""
        if not self.enable_memory_profiling:
            return

        try:
            # Force garbage collection and count collections
            initial_collections = gc.get_stats()[2]['collections'] if hasattr(gc, 'get_stats') else 0
            gc.collect()
            final_collections = gc.get_stats()[2]['collections'] if hasattr(gc, 'get_stats') else 0
            self.memory_stats['gc_collections'] += final_collections - initial_collections

            # Get memory usage
            process = psutil.Process()
            memory_info = process.memory_info()

            # Estimate cache memory usage
            cache_memory = sum(entry.size_bytes for entry in self._cache.values())

            self.memory_stats.update({
                'cache_memory_bytes': cache_memory,
                'process_memory_bytes': memory_info.rss,
                'memory_efficiency': len(self._cache) / max(1, cache_memory / 1024),  # entries per KB
            })

        except Exception as e:
            print(f"Warning: Memory profiling error: {e}")

    def get_detailed_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics and analysis."""
        with self._lock:
            total_requests = self.hits + self.misses
            hit_rate = self.hits / total_requests if total_requests > 0 else 0.0

            working_set = self._analyze_working_set()

            stats = {
                'cache_performance': {
                    'size': len(self._cache),
                    'max_size': self.current_max_size,
                    'min_size': self.min_cache_size,
                    'max_allowed_size': self.max_cache_size,
                    'hits': self.hits,
                    'misses': self.misses,
                    'hit_rate': hit_rate,
                    'evictions': self.evictions,
                    'adaptations': self.adaptations,
                },
                'working_set_analysis': {
                    'working_set_size': working_set.working_set_size,
                    'hot_entries_count': len(working_set.hot_entries),
                    'cold_entries_count': len(working_set.cold_entries),
                    'access_pattern': working_set.access_pattern,
                    'temporal_locality': working_set.temporal_locality,
                    'spatial_locality': working_set.spatial_locality,
                    'churn_rate': working_set.churn_rate,
                },
                'memory_stats': self.memory_stats.copy(),
                'cache_efficiency': {
                    'entries_per_mb': len(self._cache) / max(1, self.memory_stats.get('cache_memory_bytes', 1) / (1024*1024)),
                    'hit_rate_per_mb': hit_rate / max(1, self.memory_stats.get('cache_memory_bytes', 1) / (1024*1024)),
                    'memory_utilization': self.memory_stats.get('cache_memory_bytes', 0) / max(1, self.memory_limit_bytes),
                },
                'access_history_size': len(self._access_history),
                'last_analysis': self._last_analysis,
                'last_adaptation': self._last_adaptation,
            }

            return stats

    def optimize_cache_settings(self) -> Dict[str, Any]:
        """Analyze cache performance and suggest optimizations."""
        stats = self.get_detailed_stats()

        recommendations = {
            'cache_size': 'increase' if stats['cache_performance']['hit_rate'] < 0.7 else 'maintain',
            'memory_limit': 'increase' if stats['memory_stats']['memory_pressure'] > 0.8 else 'maintain',
            'eviction_policy': 'working_set_aware' if stats['working_set_analysis']['temporal_locality'] > 0.5 else 'lru',
            'analysis_frequency': 'increase' if stats['working_set_analysis']['churn_rate'] > 0.3 else 'maintain',
        }

        # Calculate optimal cache size
        working_set_size = stats['working_set_analysis']['working_set_size']
        memory_pressure = stats['memory_stats']['memory_pressure']

        if memory_pressure < 0.6:
            optimal_size = min(self.max_cache_size, working_set_size * 3)
        elif memory_pressure > 0.8:
            optimal_size = max(self.min_cache_size, working_set_size)
        else:
            optimal_size = working_set_size * 2

        recommendations['optimal_cache_size'] = optimal_size
        recommendations['current_efficiency'] = stats['cache_efficiency']['hit_rate_per_mb']

        return recommendations

    def _load_cache(self) -> None:
        """Load cache from disk with enhanced error handling."""
        if not self.cache_file.exists():
            return

        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            loaded_count = 0
            current_time = time.time()

            for key, entry_data in data.items():
                if isinstance(entry_data, dict) and len(self._cache) < self.current_max_size:
                    # Reconstruct CacheEntry
                    entry = CacheEntry(
                        data=entry_data.get('data', {}),
                        access_count=entry_data.get('access_count', 1),
                        last_access=entry_data.get('last_access', current_time),
                        first_access=entry_data.get('first_access', current_time),
                        size_bytes=entry_data.get('size_bytes', 1024),
                        hit_rate=entry_data.get('hit_rate', 0.0)
                    )
                    self._cache[key] = entry
                    loaded_count += 1

            print(f"Loaded {loaded_count} adaptive cache entries from {self.cache_file}")

        except (json.JSONDecodeError, IOError, KeyError) as e:
            print(f"Warning: Failed to load adaptive cache: {e}")
            # Backup corrupted file
            try:
                backup_file = self.cache_file.with_suffix('.backup')
                self.cache_file.rename(backup_file)
                print(f"Corrupted cache backed up to {backup_file}")
            except OSError:
                pass

    def _save_cache_sync(self) -> None:
        """Synchronously save enhanced cache to disk."""
        try:
            # Prepare serializable data
            cache_data = {}
            for key, entry in self._cache.items():
                cache_data[key] = {
                    'data': entry.data,
                    'access_count': entry.access_count,
                    'last_access': entry.last_access,
                    'first_access': entry.first_access,
                    'size_bytes': entry.size_bytes,
                    'hit_rate': entry.hit_rate,
                }

            # Save cache
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=None, separators=(',', ':'))

            # Save stats
            with open(self.stats_file, 'w', encoding='utf-8') as f:
                json.dump(self.get_detailed_stats(), f, indent=2)

        except IOError as e:
            print(f"Warning: Failed to save adaptive cache: {e}")

    def _start_background_tasks(self) -> None:
        """Start background tasks for analysis and adaptation."""
        def background_worker():
            while not self._shutdown:
                try:
                    # Periodic analysis and adaptation
                    time.sleep(self.adaptation_interval_seconds)

                    if not self._shutdown:
                        self._adaptive_resize()
                        self._update_memory_stats()

                        # Save stats periodically
                        if time.time() - self._last_analysis > 3600:  # Every hour
                            self._executor.submit(self._save_cache_sync)

                except Exception as e:
                    print(f"Background cache task error: {e}")
                    time.sleep(60)  # Wait before retrying

        thread = threading.Thread(target=background_worker, daemon=True, name="adaptive_cache_worker")
        thread.start()

    def shutdown(self) -> None:
        """Shutdown the adaptive cache."""
        self._shutdown = True
        self._executor.shutdown(wait=True)
        self._save_cache_sync()

    def __del__(self):
        """Ensure cache is saved on destruction."""
        if hasattr(self, '_shutdown') and not self._shutdown:
            self.shutdown()


def create_adaptive_template_cache(cache_dir: str = ".aura_cache",
                                  memory_limit_mb: int = 512) -> AdaptiveTemplateCache:
    """
    Factory function to create an adaptive template cache.

    Args:
        cache_dir: Directory for cache storage
        memory_limit_mb: Memory limit in MB

    Returns:
        Configured AdaptiveTemplateCache instance
    """
    return AdaptiveTemplateCache(
        cache_dir=cache_dir,
        memory_limit_mb=memory_limit_mb,
        enable_memory_profiling=True
    )