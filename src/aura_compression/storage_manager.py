#!/usr/bin/env python3
"""
Storage Manager - Handles sidechain storage and data persistence
Extracted from the monolithic ProductionHybridCompressor
"""
import os
import re
import struct
from pathlib import Path
import json
import hashlib
from typing import Dict, List, Tuple, Optional, Any
from enum import Enum
from datetime import datetime
from collections import Counter

from aura_compression.enums import (
    CompressionMethod,
    TEMPLATE_METADATA_KIND,
    _SEMANTIC_PREVIEW_LIMIT,
    _SEMANTIC_TOKEN_LIMIT,
    _SEMANTIC_TOKEN_PATTERN,
)


class StorageManager:
    """
    Manages sidechain storage and data persistence operations
    """

    def __init__(self,
                 storage_path: Optional[str] = None,
                 enable_sidechain: bool = True,
                 max_storage_size: int = 100 * 1024 * 1024):  # 100MB default
        """
        Initialize storage manager
        """
        self.enable_sidechain = enable_sidechain
        self.max_storage_size = max_storage_size

        if storage_path:
            self.storage_path = Path(storage_path)
        else:
            # Default to ./sidechain relative to current directory
            self.storage_path = Path("./sidechain")

        self._cold_storage_path = self.storage_path / "cold"
        self._setup_storage_directories()

        # Storage stats
        self._storage_stats = {
            'total_size': 0,
            'file_count': 0,
            'compression_ratio_sum': 0.0,
            'access_count': 0,
        }

    def _setup_storage_directories(self):
        """
        Set up storage directories
        """
        try:
            self.storage_path.mkdir(parents=True, exist_ok=True)
            self._cold_storage_path.mkdir(parents=True, exist_ok=True)
        except Exception:
            # Disable sidechain if we can't create directories
            self.enable_sidechain = False

    def store_compressed_data(self,
                             key: str,
                             compressed_data: bytes,
                             metadata: dict,
                             ttl_seconds: Optional[int] = None) -> bool:
        """
        Store compressed data in sidechain storage
        """
        if not self.enable_sidechain:
            return False

        try:
            # Create storage key
            storage_key = self._get_storage_key(key)

            # Prepare storage data
            storage_data = {
                'compressed_data': compressed_data.hex(),
                'metadata': metadata,
                'stored_at': datetime.now().isoformat(),
                'ttl_seconds': ttl_seconds,
            }

            # Check storage size limits
            if not self._check_storage_limits(len(compressed_data)):
                return False

            # Store in hot storage first
            file_path = self.storage_path / f"{storage_key}.json"
            with open(file_path, 'w') as f:
                json.dump(storage_data, f)

            # Update stats
            self._update_storage_stats(compressed_data, metadata)

            return True

        except Exception:
            return False

    def retrieve_compressed_data(self, key: str) -> Optional[Tuple[bytes, dict]]:
        """
        Retrieve compressed data from sidechain storage
        """
        if not self.enable_sidechain:
            return None

        try:
            storage_key = self._get_storage_key(key)

            # Try hot storage first
            file_path = self.storage_path / f"{storage_key}.json"
            if file_path.exists():
                return self._load_from_file(file_path)

            # Try cold storage
            cold_file_path = self._cold_storage_path / f"{storage_key}.json"
            if cold_file_path.exists():
                return self._load_from_file(cold_file_path)

            return None

        except Exception:
            return None

    def _load_from_file(self, file_path: Path) -> Optional[Tuple[bytes, dict]]:
        """
        Load compressed data from a storage file
        """
        try:
            with open(file_path, 'r') as f:
                storage_data = json.load(f)

            # Check TTL
            if storage_data.get('ttl_seconds'):
                stored_at = datetime.fromisoformat(storage_data['stored_at'])
                ttl_seconds = storage_data['ttl_seconds']
                if (datetime.now() - stored_at).total_seconds() > ttl_seconds:
                    # Expired, remove file
                    file_path.unlink()
                    return None

            compressed_data = bytes.fromhex(storage_data['compressed_data'])
            metadata = storage_data['metadata']

            # Update access stats
            self._storage_stats['access_count'] += 1

            return compressed_data, metadata

        except Exception:
            return None

    def _get_storage_key(self, key: str) -> str:
        """
        Generate a storage key from the input key
        """
        # Use SHA256 hash to create a filesystem-safe key
        return hashlib.sha256(key.encode('utf-8')).hexdigest()

    def _check_storage_limits(self, data_size: int) -> bool:
        """
        Check if storing data would exceed storage limits
        """
        current_size = self._get_current_storage_size()
        return (current_size + data_size) <= self.max_storage_size

    def _get_current_storage_size(self) -> int:
        """
        Get current total size of stored data
        """
        try:
            total_size = 0
            for file_path in self.storage_path.rglob("*.json"):
                total_size += file_path.stat().st_size
            for file_path in self._cold_storage_path.rglob("*.json"):
                total_size += file_path.stat().st_size
            return total_size
        except Exception:
            return 0

    def _update_storage_stats(self, compressed_data: bytes, metadata: dict):
        """
        Update storage statistics
        """
        self._storage_stats['total_size'] += len(compressed_data)
        self._storage_stats['file_count'] += 1

        if 'ratio' in metadata:
            self._storage_stats['compression_ratio_sum'] += metadata['ratio']

    def move_to_cold_storage(self, key: str) -> bool:
        """
        Move data from hot to cold storage
        """
        if not self.enable_sidechain:
            return False

        try:
            storage_key = self._get_storage_key(key)
            hot_path = self.storage_path / f"{storage_key}.json"
            cold_path = self._cold_storage_path / f"{storage_key}.json"

            if hot_path.exists():
                hot_path.rename(cold_path)
                return True

            return False

        except Exception:
            return False

    def cleanup_expired_data(self) -> int:
        """
        Clean up expired data from storage
        """
        if not self.enable_sidechain:
            return 0

        cleaned_count = 0

        try:
            # Clean hot storage
            for file_path in self.storage_path.glob("*.json"):
                try:
                    with open(file_path, 'r') as f:
                        storage_data = json.load(f)

                    if storage_data.get('ttl_seconds'):
                        stored_at = datetime.fromisoformat(storage_data['stored_at'])
                        ttl_seconds = storage_data['ttl_seconds']
                        if (datetime.now() - stored_at).total_seconds() > ttl_seconds:
                            file_path.unlink()
                            cleaned_count += 1
                except Exception:
                    # Remove corrupted files
                    file_path.unlink()
                    cleaned_count += 1

            # Clean cold storage
            for file_path in self._cold_storage_path.glob("*.json"):
                try:
                    with open(file_path, 'r') as f:
                        storage_data = json.load(f)

                    if storage_data.get('ttl_seconds'):
                        stored_at = datetime.fromisoformat(storage_data['stored_at'])
                        ttl_seconds = storage_data['ttl_seconds']
                        if (datetime.now() - stored_at).total_seconds() > ttl_seconds:
                            file_path.unlink()
                            cleaned_count += 1
                except Exception:
                    # Remove corrupted files
                    file_path.unlink()
                    cleaned_count += 1

        except Exception:
            pass

        return cleaned_count

    def get_storage_stats(self) -> dict:
        """
        Get storage statistics
        """
        stats = self._storage_stats.copy()

        if stats['file_count'] > 0:
            stats['average_compression_ratio'] = stats['compression_ratio_sum'] / stats['file_count']
        else:
            stats['average_compression_ratio'] = 0.0

        stats['current_size'] = self._get_current_storage_size()
        stats['size_limit'] = self.max_storage_size
        stats['usage_percentage'] = (stats['current_size'] / self.max_storage_size) * 100 if self.max_storage_size > 0 else 0

        return stats

    def clear_storage(self) -> bool:
        """
        Clear all stored data
        """
        if not self.enable_sidechain:
            return False

        try:
            # Remove all files
            for file_path in self.storage_path.glob("*.json"):
                file_path.unlink()
            for file_path in self._cold_storage_path.glob("*.json"):
                file_path.unlink()

            # Reset stats
            self._storage_stats = {
                'total_size': 0,
                'file_count': 0,
                'compression_ratio_sum': 0.0,
                'access_count': 0,
            }

            return True

        except Exception:
            return False