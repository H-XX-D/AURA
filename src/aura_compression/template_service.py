#!/usr/bin/env python3
"""
Template Service - Unified Template Management System
Combines template management, synchronization, and discovery
"""

import json
import logging
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from aura_compression.template_manager import TemplateManager
from aura_compression.templates import TemplateLibrary
from aura_compression.background_workers import TemplateDiscoveryWorker
from aura_compression.persistent_cache import PersistentTemplateCache


logger = logging.getLogger(__name__)


class TemplateService:
    """
    Unified template service that manages templates, synchronization, and discovery
    """

    def __init__(self,
                 enable_discovery: bool = True,
                 discovery_interval_seconds: int = 3600,
                 audit_log_directory: str = "./audit_logs",
                 cache_dir: str = ".aura_cache"):
        """
        Initialize the template service

        Args:
            enable_discovery: Whether to enable background template discovery
            discovery_interval_seconds: How often to run discovery
            audit_log_directory: Path to audit logs for discovery
        """
        self.enable_discovery = enable_discovery
        self.discovery_interval = discovery_interval_seconds
        self.audit_log_directory = audit_log_directory
        self.cache_dir = cache_dir

        # Initialize components with SQL-based persistent cache
        self.template_library = TemplateLibrary(cache_dir=cache_dir)
        self.template_manager = TemplateManager(self.template_library)
        self.persistent_cache = PersistentTemplateCache(cache_dir=cache_dir)

        # Discovery worker
        self.discovery_worker = None
        if enable_discovery:
            self._start_discovery_worker()

        # Thread safety
        self._lock = threading.RLock()

    def _start_discovery_worker(self):
        """Start the background discovery worker"""
        try:
            self.discovery_worker = TemplateDiscoveryWorker(
                audit_log_directory=self.audit_log_directory,
                discovery_interval_seconds=self.discovery_interval,
                cache_dir=self.cache_dir,
            )
            # Start the worker (it handles its own threading)
            self.discovery_worker.start()
        except Exception as e:
            # Discovery is optional, don't fail if it can't start
            logger.warning("Could not start template discovery worker: %s", e)
            self.discovery_worker = None

    def sync_template_store(self):
        """
        Synchronize template store - load latest templates from SQL cache
        This is called before compression operations to ensure fresh templates
        """
        with self._lock:
            try:
                # Reload templates from discovery worker if available
                if self.discovery_worker:
                    discovered = self.discovery_worker.get_discovered_templates()
                    if discovered:
                        # Update template library with latest templates
                        dynamic_templates = {}
                        for template_id, pattern in discovered.items():
                            if isinstance(pattern, str):
                                dynamic_templates[template_id] = pattern
                        
                        # Sync dynamic templates into the template library
                        if dynamic_templates:
                            self.template_library.sync_dynamic_templates(dynamic_templates)
            except Exception as e:
                # Sync is best-effort, don't fail operations
                logger.warning("Template sync failed: %s", e)

    def heal_template_cache(self,
                             text: Optional[str] = None,
                             template_id: Optional[int] = None,
                             force_full_reset: bool = False) -> None:
        """Self-heal template caches when stale entries are detected."""
        with self._lock:
            if force_full_reset:
                if self.template_manager:
                    self.template_manager.clear_cache()
                self.template_library.clear_match_cache()
                self.template_library.clear_persistent_cache()
            else:
                if text:
                    self.template_library.invalidate_text_cache(text)
                    if self.template_manager:
                        self.template_manager.invalidate_text(text)

            if template_id is not None:
                try:
                    self.template_library.remove(template_id)
                except Exception:
                    pass

            self.sync_template_store()

    def find_template_match(self, text: str) -> Optional[Any]:
        """
        Find the best template match for text
        """
        with self._lock:
            return self.template_manager.find_template_match(text)

    def get_template_store(self, client_version: int = 0) -> Dict[str, Any]:
        """
        Get template store for client synchronization from SQL cache
        """
        with self._lock:
            templates = {}
            metadata: Dict[str, Any] = {}
            if self.discovery_worker:
                templates = self.discovery_worker.get_discovered_templates()
                metadata = self.discovery_worker.get_store_metadata()
            
            return {
                'version': 1,
                'templates': templates,
                'last_updated': metadata.get('last_updated', datetime.now(timezone.utc).isoformat()),
                'total_templates': len(templates),
            }

    def get_template_by_id(self, template_id: int) -> Optional[Dict[str, Any]]:
        """
        Get specific template by ID from SQL cache
        """
        if self.discovery_worker:
            templates = self.discovery_worker.get_discovered_templates()
            pattern = templates.get(template_id)
            if pattern:
                return {
                    'id': template_id,
                    'pattern': pattern,
                    'version': 1,
                }
        return None

    def get_stats(self) -> Dict[str, Any]:
        """
        Get template service statistics
        """
        with self._lock:
            store_data = self.get_template_store()
            return {
                'total_templates': store_data.get('total_templates', 0),
                'store_version': store_data.get('version', 0),
                'last_updated': store_data.get('last_updated'),
                'discovery_enabled': self.discovery_worker is not None,
                'discovery_interval': self.discovery_interval,
            }

    def record_template_use(self, template_id: int):
        """
        Record that a template was used for statistics
        """
        # This could be extended to track usage statistics
        pass
