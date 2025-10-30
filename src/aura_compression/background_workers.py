#!/usr/bin/env python3
"""
Background Workers - Automatic Template Discovery and Maintenance
Implements Claims 3, 17: Continuous template mining from audit logs
"""
import json
import threading
import time
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, timezone

from aura_compression.audit import AuditLogger, AuditLogType
from aura_compression.discovery import TemplateDiscoveryEngine, TemplateCandidate


class TemplateDiscoveryWorker:
    """
    Background worker that continuously mines audit logs for new templates (Claims 3, 17)
    Runs on a schedule to discover, test, and promote new compression templates
    """

    def __init__(
        self,
        audit_log_directory: str = "./audit_logs",
        template_store_path: str = "./template_store.json",
        discovery_interval_seconds: int = 3600,  # Run every hour
        min_messages_for_discovery: int = 100,
        min_frequency: int = 5,
        compression_threshold: float = 1.1,
        user_id: Optional[str] = None,  # For user-specific discovery (204-255)
        discovery_mode: str = "platform",  # "platform" or "user"
    ):
        """
        Args:
            audit_log_directory: Path to audit logs
            template_store_path: Path to template store JSON file
            discovery_interval_seconds: How often to run discovery (default 1 hour)
            min_messages_for_discovery: Minimum messages needed to run discovery
            min_frequency: Minimum pattern occurrences for promotion (Claim 16)
            compression_threshold: Minimum compression advantage (1.1 = 10% better, Claim 16)
            user_id: User ID for user-specific templates (mode="user", IDs 204-255)
            discovery_mode: "platform" (129-188, shared) or "user" (204-255, per-user)
        """
        self.audit_log_directory = audit_log_directory
        self.template_store_path = template_store_path
        self.discovery_interval = discovery_interval_seconds
        self.min_messages_for_discovery = min_messages_for_discovery
        self.user_id = user_id
        self.discovery_mode = discovery_mode

        # V3 Allocation (with ML IDs):
        # AI → AI: 0-49 (50 slots, universal)
        # Human → AI: 50-108 (59 slots, universal) [REDUCED by 20]
        # ML/AI Models: 109-148 (40 slots, universal) [NEW]
        # Platform rolling: 149-208 (60 slots, shared) [SHIFTED]
        # Reserved routing: 209-223 (15 slots, system) [SHIFTED]
        # User-specific: 224-255 (32 slots per user, isolated) [REDUCED by 20]

        if discovery_mode == "user":
            if not user_id:
                raise ValueError("user_id required for user-specific discovery")
            starting_id = 224  # Changed from 204
            max_id = 255       # 32 slots per user
        else:  # platform mode
            starting_id = 149  # Changed from 129
            max_id = 208       # Changed from 188

        self.discovery_engine = TemplateDiscoveryEngine(
            min_frequency=min_frequency,
            compression_threshold=compression_threshold,
            starting_template_id=starting_id,
            max_template_id=max_id,
        )

        self.audit_logger = AuditLogger(audit_log_directory)

        # Worker state
        self.running = False
        self.worker_thread: Optional[threading.Thread] = None
        self.last_discovery_run: Optional[datetime] = None
        self.total_templates_discovered = 0

        # Load existing template store
        self._load_template_store()

    def _load_template_store(self):
        """Load existing templates from disk (Claim 17)"""
        store_path = Path(self.template_store_path)
        if not store_path.exists():
            return

        with open(store_path, 'r') as f:
            data = json.load(f)

        # Load templates based on discovery mode
        if self.discovery_mode == "user":
            # Load user-specific templates (204-255)
            templates_dict = data.get('user_templates', {}).get(self.user_id, {})
        else:
            # Load platform-wide templates (129-188)
            # Backwards compatibility: check both 'platform_templates' and old 'templates' key
            templates_dict = data.get('platform_templates', data.get('templates', {}))

        # Restore promoted templates
        for tid, template_data in templates_dict.items():
            try:
                template_id = int(tid)
            except ValueError:
                print(f"Skipping template with non-integer id: {tid}")
                continue

            if template_id < self.discovery_engine.starting_template_id or template_id > self.discovery_engine.max_template_id:
                continue

            candidate = TemplateCandidate(
                pattern=template_data['pattern'],
                frequency=template_data['frequency'],
                compression_ratio=template_data['compression_ratio'],
                slot_count=template_data['slot_count'],
                safety_approved=template_data['safety_approved'],
                version=template_data['version'],
                discovered_at=template_data['discovered_at'],
            )
            self.discovery_engine.promoted_templates[template_id] = candidate
            next_id = max(
                self.discovery_engine.next_template_id,
                template_id + 1
            )
            self.discovery_engine.next_template_id = min(
                next_id,
                self.discovery_engine.max_template_id + 1,
            )

        self.total_templates_discovered = len(self.discovery_engine.promoted_templates)

        if self.discovery_mode == "user":
            print(f"Loaded {self.total_templates_discovered} user-specific templates for {self.user_id}")
        else:
            print(f"Loaded {self.total_templates_discovered} platform-wide templates")

    def _save_template_store(self):
        """Save templates to disk for client synchronization (Claim 17)"""
        store_path = Path(self.template_store_path)

        # Load existing data
        if store_path.exists():
            with open(store_path, 'r') as f:
                data = json.load(f)
        else:
            data = {
                'version': 1,
                'platform_templates': {},  # Shared 129-188
                'user_templates': {},      # Per-user 204-255
            }

        data['last_updated'] = datetime.now().isoformat()

        if self.discovery_mode == "user":
            # User-specific templates (204-255)
            if 'user_templates' not in data:
                data['user_templates'] = {}
            if self.user_id not in data['user_templates']:
                data['user_templates'][self.user_id] = {}

            for template_id, candidate in self.discovery_engine.promoted_templates.items():
                template_dict = candidate.to_dict()
                template_dict['user_id'] = self.user_id
                data['user_templates'][self.user_id][str(template_id)] = template_dict

            print(f"Saved {len(self.discovery_engine.promoted_templates)} user-specific templates for {self.user_id}")

        else:  # platform mode
            # Platform-wide templates (129-188)
            if 'platform_templates' not in data:
                data['platform_templates'] = {}

            for template_id, candidate in self.discovery_engine.promoted_templates.items():
                template_dict = candidate.to_dict()
                # Track who discovered it for analytics
                if self.user_id:
                    template_dict['discovered_by'] = self.user_id
                data['platform_templates'][str(template_id)] = template_dict

            print(f"Saved {len(self.discovery_engine.promoted_templates)} platform-wide templates")

        # Keep audit log
        data['audit_log'] = self.discovery_engine.export_audit_log()

        # Atomic write
        temp_path = store_path.with_suffix('.tmp')
        with open(temp_path, 'w') as f:
            json.dump(data, f, indent=2)

        temp_path.replace(store_path)

    def _get_recent_messages(self, hours: int = 24) -> List[str]:
        """Get recent messages from audit logs for discovery"""
        messages = []

        # Read from client_delivered log
        entries = self.audit_logger.get_entries(
            AuditLogType.CLIENT_DELIVERED,
            limit=10000,  # Last 10k messages
        )

        # Filter to recent messages (with timezone-aware comparison)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        for entry in entries:
            try:
                entry_time = datetime.fromisoformat(entry.timestamp.replace('Z', '+00:00'))
                if entry_time >= cutoff and entry.plaintext:
                    messages.append(entry.plaintext)
            except Exception:
                continue

        return messages

    def run_discovery(self) -> int:
        """
        Run template discovery on recent audit logs (Claim 3)

        Returns:
            Number of new templates discovered and promoted
        """
        print(f"\n{'='*80}")
        print(f"TEMPLATE DISCOVERY RUN - {datetime.now().isoformat()}")
        print(f"{'='*80}")

        # Get recent messages
        print("Fetching recent messages from audit logs...")
        messages = self._get_recent_messages(hours=24)

        if len(messages) < self.min_messages_for_discovery:
            print(f"Not enough messages for discovery: {len(messages)} < {self.min_messages_for_discovery}")
            return 0

        print(f"Analyzing {len(messages)} messages...")

        # Run discovery pipeline (Claims 3, 15, 16)
        candidates = self.discovery_engine.discover_templates(messages)

        # Promote qualified candidates (Claim 17)
        new_templates = 0
        for candidate in candidates:
            if candidate.safety_approved and candidate.compression_ratio >= self.discovery_engine.compression_threshold:
                # Check if similar template already exists
                is_duplicate = False
                for existing in self.discovery_engine.promoted_templates.values():
                    if existing.pattern == candidate.pattern:
                        is_duplicate = True
                        break

                if not is_duplicate:
                    try:
                        template_id = self.discovery_engine.promote_template(candidate)
                    except RuntimeError as exc:
                        print(f"Skipping promotion: {exc}")
                        continue
                    new_templates += 1

        # Save updated template store (Claim 17)
        if new_templates > 0:
            self._save_template_store()
            self.total_templates_discovered += new_templates

        self.last_discovery_run = datetime.now()

        print(f"\n{'='*80}")
        print(f"DISCOVERY COMPLETE: {new_templates} new templates promoted")
        print(f"Total templates in store: {self.total_templates_discovered}")
        print(f"{'='*80}\n")

        return new_templates

    def _worker_loop(self):
        """Background worker loop"""
        print(f"Template discovery worker started (interval: {self.discovery_interval}s)")

        while self.running:
            try:
                self.run_discovery()
            except Exception as e:
                print(f"Error in discovery worker: {e}")

            # Sleep until next run
            time.sleep(self.discovery_interval)

    def start(self):
        """Start background worker (Claim 3)"""
        if self.running:
            print("Worker already running")
            return

        self.running = True
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
        print("Template discovery worker started")

    def stop(self):
        """Stop background worker"""
        if not self.running:
            return

        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5)
        print("Template discovery worker stopped")

    def get_status(self) -> Dict[str, Any]:
        """Get worker status for monitoring"""
        return {
            'running': self.running,
            'last_discovery_run': self.last_discovery_run.isoformat() if self.last_discovery_run else None,
            'total_templates_discovered': self.total_templates_discovered,
            'discovery_interval_seconds': self.discovery_interval,
            'template_store_path': self.template_store_path,
        }


class TemplateSyncService:
    """
    Template synchronization service for clients (Claim 17)
    Provides API for clients to fetch latest templates
    """

    def __init__(self, template_store_path: str = "./template_store.json"):
        self.template_store_path = template_store_path

    def get_template_store(self, client_version: int = 0) -> Dict[str, Any]:
        """
        Get template store for client synchronization (Claim 17)

        Args:
            client_version: Client's current template version (0 = get all)

        Returns:
            Dictionary with templates and metadata
        """
        store_path = Path(self.template_store_path)

        if not store_path.exists():
            return {
                'version': 0,
                'templates': {},
                'last_updated': None,
            }

        with open(store_path, 'r') as f:
            data = json.load(f)

        # Filter to only new templates if client has a version
        if client_version > 0:
            filtered_templates = {}
            for tid, template_data in data['templates'].items():
                if template_data.get('version', 1) > client_version:
                    filtered_templates[tid] = template_data
            data['templates'] = filtered_templates

        return {
            'version': data.get('version', 1),
            'templates': data['templates'],
            'last_updated': data.get('last_updated'),
            'total_templates': len(data['templates']),
        }

    def get_template_by_id(self, template_id: int) -> Optional[Dict[str, Any]]:
        """Get specific template by ID"""
        store = self.get_template_store()
        return store['templates'].get(str(template_id))


# Global worker instance
_discovery_worker: Optional[TemplateDiscoveryWorker] = None


def start_discovery_worker(
    audit_log_directory: str = "./audit_logs",
    template_store_path: str = "./template_store.json",
    discovery_interval_seconds: int = 3600,
) -> TemplateDiscoveryWorker:
    """
    Start global template discovery worker (Claim 3)

    Args:
        audit_log_directory: Path to audit logs
        template_store_path: Path to template store
        discovery_interval_seconds: Discovery interval (default 1 hour)

    Returns:
        TemplateDiscoveryWorker instance
    """
    global _discovery_worker

    if _discovery_worker is None:
        _discovery_worker = TemplateDiscoveryWorker(
            audit_log_directory=audit_log_directory,
            template_store_path=template_store_path,
            discovery_interval_seconds=discovery_interval_seconds,
        )

    _discovery_worker.start()
    return _discovery_worker


def stop_discovery_worker():
    """Stop global template discovery worker"""
    global _discovery_worker
    if _discovery_worker:
        _discovery_worker.stop()


def get_discovery_worker() -> Optional[TemplateDiscoveryWorker]:
    """Get global discovery worker instance"""
    return _discovery_worker
