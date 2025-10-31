"""Persistent template cache for surviving application restarts."""

import json
import hashlib
import os
from pathlib import Path
from typing import Dict, Optional, Any, List, Tuple
import threading
import time
from concurrent.futures import ThreadPoolExecutor

# TemplateMatch data structure (to avoid circular imports)
# We'll work with dictionaries and convert in TemplateLibrary


class PersistentTemplateCache:
    """Persistent cache for template matches that survives application restarts.

    Features:
    - Disk-based storage with efficient serialization
    - LRU eviction with configurable size limits
    - Thread-safe operations
    - Automatic background saving
    - Cache warming on startup
    """

    def __init__(self, cache_dir: str = ".aura_cache", max_size: int = 10000,
                 save_interval: float = 30.0, compression_enabled: bool = True):
        """Initialize persistent cache.

        Args:
            cache_dir: Directory to store cache files
            max_size: Maximum number of cache entries
            save_interval: Seconds between automatic saves
            compression_enabled: Whether to compress cache data
        """
        self.cache_dir = Path(cache_dir)
        self.cache_file = self.cache_dir / "template_cache.json"
        self.max_size = max_size
        self.save_interval = save_interval
        self.compression_enabled = compression_enabled

        # In-memory cache with access tracking for LRU
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._access_order: List[str] = []
        self._lock = threading.RLock()

        # Statistics
        self.hits = 0
        self.misses = 0
        self.evictions = 0

        # Background saving
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="cache_saver")
        self._last_save = time.time()
        self._shutdown = False

        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Load existing cache
        self._load_cache()

        # Start background save thread
        self._start_background_saver()

    def get(self, text: str) -> Optional[Dict[str, Any]]:
        """Get cached template match data for text."""
        cache_key = self._make_key(text)

        with self._lock:
            if cache_key in self._cache:
                # Update access order for LRU
                self._access_order.remove(cache_key)
                self._access_order.append(cache_key)

                self.hits += 1
                return self._cache[cache_key].copy()  # Return copy to avoid modification
            else:
                self.misses += 1
                return None

    def put(self, text: str, match_data: Dict[str, Any]) -> None:
        """Store template match data in cache."""
        cache_key = self._make_key(text)

        with self._lock:
            # Check if we need to evict
            if cache_key not in self._cache and len(self._cache) >= self.max_size:
                self._evict_lru()

            # Store the match data
            self._cache[cache_key] = match_data.copy()
            self._access_order.append(cache_key)

        # Save immediately for testing/debugging
        self._save_cache_sync()

    def clear(self) -> None:
        """Clear all cached entries."""
        with self._lock:
            self._cache.clear()
            self._access_order.clear()
            self.hits = 0
            self.misses = 0
            self.evictions = 0
        self._save_cache_async()

    def clear_and_persist(self) -> None:
        """Clear cache and immediately persist the empty state."""
        with self._lock:
            self._cache.clear()
            self._access_order.clear()
            self.hits = 0
            self.misses = 0
            self.evictions = 0
        self._save_cache_sync()

    def invalidate_text(self, text: str) -> None:
        """Remove cached entry for specific text."""
        cache_key = self._make_key(text)
        with self._lock:
            if cache_key in self._cache:
                self._cache.pop(cache_key, None)
                try:
                    self._access_order.remove(cache_key)
                except ValueError:
                    pass
        self._save_cache_async()

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total_requests = self.hits + self.misses
            hit_rate = self.hits / total_requests if total_requests > 0 else 0.0

            return {
                'size': len(self._cache),
                'max_size': self.max_size,
                'hits': self.hits,
                'misses': self.misses,
                'hit_rate': hit_rate,
                'evictions': self.evictions,
                'cache_file_size': self.cache_file.stat().st_size if self.cache_file.exists() else 0
            }

    def shutdown(self) -> None:
        """Shutdown the cache and save final state."""
        self._shutdown = True
        self._executor.shutdown(wait=True)
        self._save_cache_sync()

    def _make_key(self, text: str) -> str:
        """Create cache key from text using SHA-256 hash."""
        return hashlib.sha256(text.encode('utf-8')).hexdigest()

    def _evict_lru(self) -> None:
        """Evict least recently used entry."""
        if self._access_order:
            lru_key = self._access_order.pop(0)
            del self._cache[lru_key]
            self.evictions += 1

    def _load_cache(self) -> None:
        """Load cache from disk."""
        if not self.cache_file.exists():
            return

        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Validate and load entries
            loaded_count = 0
            for key, value in data.items():
                if isinstance(value, dict) and len(self._cache) < self.max_size:
                    self._cache[key] = value
                    self._access_order.append(key)
                    loaded_count += 1

            print(f"Loaded {loaded_count} cached template matches from {self.cache_file}")

        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Failed to load template cache: {e}")
            # Remove corrupted cache file
            try:
                self.cache_file.unlink()
            except OSError:
                pass

    def _save_cache_sync(self) -> None:
        """Synchronously save cache to disk."""
        try:
            # Ensure cache directory exists
            self.cache_dir.mkdir(parents=True, exist_ok=True)

            # Use a more unique temp file name to avoid conflicts
            import uuid
            temp_file = self.cache_file.parent / f"template_cache_{uuid.uuid4().hex[:8]}.tmp"

            # Write to temp file
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(self._cache, f, indent=None, separators=(',', ':'))

            # Atomic move
            temp_file.replace(self.cache_file)

        except IOError as e:
            print(f"Warning: Failed to save template cache: {e}")
            # Try to clean up temp file if it exists
            try:
                if 'temp_file' in locals():
                    temp_file.unlink(missing_ok=True)
            except:
                pass

    def _save_cache_async(self) -> None:
        """Asynchronously save cache to disk."""
        if not self._shutdown:
            self._executor.submit(self._save_cache_sync)

    def _start_background_saver(self) -> None:
        """Start background thread for periodic cache saving."""
        def saver_thread():
            while not self._shutdown:
                time.sleep(self.save_interval)
                if time.time() - self._last_save >= self.save_interval:
                    self._save_cache_async()
                    self._last_save = time.time()

        thread = threading.Thread(target=saver_thread, daemon=True, name="cache_background_saver")
        thread.start()

    def __del__(self):
        """Ensure cache is saved on destruction."""
        if hasattr(self, '_shutdown') and not self._shutdown:
            self.shutdown()
