"""Persistent template cache for surviving application restarts.

The implementation now stores cache entries in a lightweight SQLite database
so the cache survives process restarts while remaining resilient to partial
writes or concurrent updates."""

import json
import hashlib
import logging
import sqlite3
import threading
import time
from pathlib import Path
from typing import Dict, Optional, Any, List
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

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
        self.cache_file = self.cache_dir / "template_cache.db"
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

        # Database connection and schema setup
        self._conn = sqlite3.connect(self.cache_file, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._initialize_database()

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

    def _initialize_database(self) -> None:
        """Ensure the SQLite backing store is ready for use."""
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS template_cache (
                    cache_key TEXT PRIMARY KEY,
                    payload   TEXT NOT NULL,
                    last_access REAL NOT NULL
                )
                """
            )

    def _load_cache(self) -> None:
        """Load cache from disk."""
        if not self.cache_file.exists():
            return

        loaded_count = 0
        try:
            cursor = self._conn.execute(
                "SELECT cache_key, payload FROM template_cache ORDER BY last_access"
            )
            for cache_key, payload in cursor:
                if len(self._cache) >= self.max_size:
                    break
                try:
                    value = json.loads(payload)
                except (TypeError, json.JSONDecodeError):
                    continue
                self._cache[cache_key] = value
                self._access_order.append(cache_key)
                loaded_count += 1

            if loaded_count:
                logger.info(f"Loaded {loaded_count} cached template matches from {self.cache_file}")

        except sqlite3.Error as exc:
            logger.info(f"Warning: Failed to load template cache: {exc}")
            with self._conn:
                self._conn.execute("DELETE FROM template_cache")

    def _save_cache_sync(self) -> None:
        """Synchronously save cache to disk."""
        try:
            with self._lock:
                with self._conn:
                    self._conn.execute("DELETE FROM template_cache")
                    rows = [
                        (
                            cache_key,
                            json.dumps(self._cache[cache_key]),
                            idx,
                        )
                        for idx, cache_key in enumerate(self._access_order)
                    ]
                    if rows:
                        self._conn.executemany(
                            "INSERT INTO template_cache (cache_key, payload, last_access) VALUES (?, ?, ?)",
                            rows,
                        )

        except sqlite3.Error as exc:
            logger.info(f"Warning: Failed to save template cache: {exc}")

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
