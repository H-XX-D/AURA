#!/usr/bin/env python3
"""
Background Workers - Automatic Template Discovery and Maintenance
Implements Claims 3, 17: Continuous template mining from audit logs
"""

import json
import logging
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from aura_compression.audit import AuditLogger, AuditLogType
from aura_compression.discovery import TemplateCandidate, TemplateDiscoveryEngine

logger = logging.getLogger(__name__)


class TemplateDiscoveryWorker:
    """
    Background worker that continuously mines audit logs for new templates (Claims 3, 17)
    Runs on a schedule to discover, test, and promote new compression templates
    """

    def __init__(
        self,
        audit_log_directory: str = "./audit_logs",
        discovery_interval_seconds: int = 3600,  # Run every hour
        min_messages_for_discovery: int = 100,
        min_frequency: int = 2,  # Reduced from 5 to 2 for faster discovery
        compression_threshold: float = 1.05,  # Reduced from 1.1 to 1.05 (5% compression advantage)
        user_id: Optional[str] = None,  # For user-specific discovery (204-255)
        discovery_mode: str = "platform",  # "platform" or "user"
        cache_dir: str = ".aura_cache",  # SQL cache directory
    ):
        """
        Args:
            audit_log_directory: Path to audit logs
            discovery_interval_seconds: How often to run discovery (default 1 hour)
            min_messages_for_discovery: Minimum messages needed to run discovery
            min_frequency: Minimum pattern occurrences for promotion (default: 2, Claim 16)
            compression_threshold: Minimum compression advantage (default: 1.05 = 5% better, Claim 16)
            user_id: User ID for user-specific templates (mode="user", IDs 204-255)
            discovery_mode: "platform" (129-188, shared) or "user" (204-255, per-user)
            cache_dir: Directory for SQL-based persistent cache
        """
        self.audit_log_directory = audit_log_directory
        self.cache_dir = cache_dir
        self.discovery_interval = discovery_interval_seconds
        self.min_messages_for_discovery = min_messages_for_discovery
        self.user_id = user_id
        self.discovery_mode = discovery_mode

        # V3 Allocation (with ML IDs):
        # AI → AI: 0-49 (50 slots, universal)
        # Human → AI: 50-108 (59 slots, universal) [REDUCED by 20]
        # ML/AI Models: 109-148 (40 slots, universal) [NEW]
        # Platform rolling: 149-1000 (852 slots, shared) [INCREASED from 60 to 852]
        # Reserved routing: 1001-1015 (15 slots, system) [SHIFTED]
        # User-specific: 1016-1047 (32 slots per user, isolated) [SHIFTED]

        if discovery_mode == "user":
            if not user_id:
                raise ValueError("user_id required for user-specific discovery")
            starting_id = 1016  # Shifted from 224
            max_id = 1047  # 32 slots per user
        else:  # platform mode
            starting_id = 149  # Changed from 129
            max_id = 1000  # Increased from 208 to 1000 for larger template storage

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

        # In-memory template store for quick access (points to SQL cache)
        self.discovered_templates: Dict[int, str] = {}
        self._scope = f"user:{self.user_id}" if self.discovery_mode == "user" else "platform"
        self._db_conn: Optional[sqlite3.Connection] = None
        self._db_lock = threading.RLock()
        self._init_database()

        # Track processed messages to avoid re-analysis
        self.processed_message_ids: set = set()
        self._load_processed_message_ids()

        # Load existing template store
        self._load_template_store()

    def _init_database(self) -> None:
        """Initialize SQLite backing store for discovered templates."""
        Path(self.cache_dir).mkdir(parents=True, exist_ok=True)
        db_path = Path(self.cache_dir) / "template_store.db"
        self._db_conn = sqlite3.connect(db_path, check_same_thread=False)
        self._db_conn.execute("PRAGMA journal_mode=WAL")
        self._db_conn.execute("PRAGMA synchronous=NORMAL")
        with self._db_lock, self._db_conn:
            self._db_conn.execute("""
                CREATE TABLE IF NOT EXISTS template_store (
                    template_id INTEGER NOT NULL,
                    scope TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    user_id TEXT,
                    data_json TEXT NOT NULL,
                    discovered_by TEXT,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (template_id, scope)
                )
                """)
            self._db_conn.execute("""
                CREATE TABLE IF NOT EXISTS cold_storage_templates (
                    template_id INTEGER NOT NULL,
                    scope TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    user_id TEXT,
                    data_json TEXT NOT NULL,
                    retired_at TEXT NOT NULL,
                    PRIMARY KEY (template_id, scope)
                )
                """)
            self._db_conn.execute("""
                CREATE TABLE IF NOT EXISTS template_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """)

    def _close_database(self) -> None:
        """Close SQLite connection."""
        if self._db_conn is not None:
            try:
                self._db_conn.close()
            except sqlite3.Error:
                pass
            self._db_conn = None

    def _candidate_from_payload(self, payload: Dict[str, Any]) -> Optional[TemplateCandidate]:
        """Rehydrate TemplateCandidate from stored JSON payload."""
        pattern = payload.get("pattern")
        if not pattern:
            return None

        candidate = TemplateCandidate(
            pattern=pattern,
            frequency=payload.get("frequency", 0),
            compression_ratio=payload.get("compression_ratio", 1.0),
            slot_count=payload.get("slot_count") or pattern.count("{"),
            examples=payload.get("examples", []),
            safety_approved=payload.get("safety_approved", True),
            version=payload.get("version", 1),
            discovered_at=payload.get("discovered_at"),
        )
        candidate.usage_count = payload.get("usage_count", 0)
        candidate.last_used = payload.get("last_used")
        candidate.days_since_used = payload.get("days_since_used", 0)
        return candidate

    def _migrate_legacy_template_store(self) -> None:
        """Migrate legacy JSON template store into SQLite backend."""
        legacy_file = Path(self.cache_dir) / "discovered_templates.json"
        if not legacy_file.exists():
            return

        try:
            data = json.loads(legacy_file.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning(f"Failed to read legacy template store: {exc}")
            legacy_file.rename(legacy_file.with_suffix(".corrupt"))
            return

        scope_templates: Dict[int, Dict[str, Any]]
        if self.discovery_mode == "user":
            scope_templates = data.get("user_templates", {}).get(self.user_id, {}) or {}
        else:
            scope_templates = data.get("platform_templates", {}) or {}

        cold_templates = data.get("cold_storage_templates", {})
        namespace = f"user:{self.user_id}" if self.discovery_mode == "user" else "platform"
        now = datetime.now(timezone.utc).isoformat()

        with self._db_lock, self._db_conn:
            for tid_str, template_data in scope_templates.items():
                try:
                    template_id = int(tid_str)
                except ValueError:
                    continue
                payload = json.dumps(template_data)
                discovered_by = template_data.get("discovered_by")
                self._db_conn.execute(
                    """
                    INSERT OR REPLACE INTO template_store
                    (template_id, scope, mode, user_id, data_json, discovered_by, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        template_id,
                        namespace,
                        self.discovery_mode,
                        self.user_id,
                        payload,
                        discovered_by,
                        now,
                    ),
                )

            for tid_str, template_data in cold_templates.items():
                try:
                    template_id = int(tid_str)
                except ValueError:
                    continue
                payload = json.dumps(template_data)
                self._db_conn.execute(
                    """
                    INSERT OR REPLACE INTO cold_storage_templates
                    (template_id, scope, mode, user_id, data_json, retired_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        template_id,
                        namespace,
                        self.discovery_mode,
                        self.user_id,
                        payload,
                        now,
                    ),
                )

            self._db_conn.execute(
                """
                INSERT INTO template_metadata(key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
                """,
                (f"last_updated::{namespace}", now),
            )

        backup_path = legacy_file.with_suffix(".json.backup")
        try:
            legacy_file.rename(backup_path)
            logger.info(f"Migrated legacy template store to SQLite (backup: {backup_path.name})")
        except OSError:
            logger.info(
                "Migrated legacy template store to SQLite; original file kept for reference"
            )

    def _load_templates_from_db(self) -> None:
        """Populate in-memory structures from SQLite backend."""
        if self._db_conn is None:
            return

        self.discovered_templates.clear()
        self.discovery_engine.promoted_templates.clear()
        self.discovery_engine.cold_storage.clear()

        max_template_id = self.discovery_engine.starting_template_id - 1

        with self._db_lock:
            cursor = self._db_conn.cursor()
            cursor.execute(
                """
                SELECT template_id, data_json
                FROM template_store
                WHERE scope=?
                ORDER BY template_id
                """,
                (self._scope,),
            )
            for template_id, payload_json in cursor.fetchall():
                try:
                    payload = json.loads(payload_json)
                except json.JSONDecodeError:
                    continue

                candidate = self._candidate_from_payload(payload)
                if candidate is None:
                    continue

                self.discovery_engine.promoted_templates[template_id] = candidate
                self.discovered_templates[template_id] = candidate.pattern
                max_template_id = max(max_template_id, template_id)

            cursor.execute(
                """
                SELECT template_id, data_json
                FROM cold_storage_templates
                WHERE scope=?
                """,
                (self._scope,),
            )
            for template_id, payload_json in cursor.fetchall():
                try:
                    payload = json.loads(payload_json)
                except json.JSONDecodeError:
                    continue

                candidate = self._candidate_from_payload(payload)
                if candidate is None:
                    continue
                self.discovery_engine.cold_storage[template_id] = candidate

        if max_template_id >= self.discovery_engine.starting_template_id:
            self.discovery_engine.next_template_id = max_template_id + 1

        self.total_templates_discovered = len(self.discovery_engine.promoted_templates)

        if self.discovery_mode == "user":
            logger.info(
                f"Loaded {self.total_templates_discovered} user-specific templates for {self.user_id}"
            )
        else:
            logger.info(f"Loaded {self.total_templates_discovered} platform-wide templates")

    def _load_processed_message_ids(self):
        """Load set of already processed message IDs from cache directory"""
        processed_file = Path(self.cache_dir) / "processed_messages.json"
        if processed_file.exists():
            try:
                with open(processed_file, "r") as f:
                    data = json.load(f)
                    self.processed_message_ids = set(data.get("processed_ids", []))
                    logger.info(f"Loaded {len(self.processed_message_ids)} processed message IDs")
            except Exception as e:
                logger.info(f"Failed to load processed message IDs: {e}")
                self.processed_message_ids = set()

    def _save_processed_message_ids(self):
        """Save set of processed message IDs to cache directory"""
        processed_file = Path(self.cache_dir) / "processed_messages.json"
        try:
            # Ensure cache directory exists
            Path(self.cache_dir).mkdir(parents=True, exist_ok=True)
            data = {
                "processed_ids": list(self.processed_message_ids),
                "last_updated": datetime.now().isoformat(),
            }
            with open(processed_file, "w") as f:
                json.dump(data, f)
        except Exception as e:
            logger.warning(f"Failed to save processed message IDs: {e}")

    def _load_template_store(self):
        """Load existing templates from SQLite cache, migrating legacy JSON if needed."""
        try:
            self._migrate_legacy_template_store()
            self._load_templates_from_db()
        except Exception as e:
            logger.warning(f"Failed to load template store: {e}")

    def _save_template_store(self):
        """Persist templates to SQLite cache."""
        if self._db_conn is None:
            return

        now = datetime.now(timezone.utc).isoformat()
        active_count = len(self.discovery_engine.promoted_templates)
        cold_count = len(self.discovery_engine.cold_storage)

        try:
            with self._db_lock:
                cursor = self._db_conn.cursor()
                cursor.execute("BEGIN IMMEDIATE")
                cursor.execute("DELETE FROM template_store WHERE scope=?", (self._scope,))
                cursor.execute("DELETE FROM cold_storage_templates WHERE scope=?", (self._scope,))

                self.discovered_templates.clear()

                for template_id, candidate in self.discovery_engine.promoted_templates.items():
                    payload = candidate.to_dict()
                    if self.discovery_mode == "user":
                        payload["user_id"] = self.user_id
                    elif self.user_id:
                        payload["discovered_by"] = self.user_id

                    cursor.execute(
                        """
                        INSERT INTO template_store
                        (template_id, scope, mode, user_id, data_json, discovered_by, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            template_id,
                            self._scope,
                            self.discovery_mode,
                            self.user_id,
                            json.dumps(payload),
                            payload.get("discovered_by"),
                            now,
                        ),
                    )
                    self.discovered_templates[template_id] = candidate.pattern

                for template_id, candidate in self.discovery_engine.cold_storage.items():
                    payload = candidate.to_dict()
                    payload["retired_at"] = now
                    cursor.execute(
                        """
                        INSERT INTO cold_storage_templates
                        (template_id, scope, mode, user_id, data_json, retired_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            template_id,
                            self._scope,
                            self.discovery_mode,
                            self.user_id,
                            json.dumps(payload),
                            now,
                        ),
                    )

                cursor.execute(
                    """
                    INSERT INTO template_metadata(key, value)
                    VALUES (?, ?)
                    ON CONFLICT(key) DO UPDATE SET value=excluded.value
                    """,
                    (f"last_updated::{self._scope}", now),
                )
                cursor.execute(
                    """
                    INSERT INTO template_metadata(key, value)
                    VALUES (?, ?)
                    ON CONFLICT(key) DO UPDATE SET value=excluded.value
                    """,
                    (
                        f"audit_log::{self._scope}",
                        json.dumps(self.discovery_engine.export_audit_log()),
                    ),
                )

                self._db_conn.commit()

            if self.discovery_mode == "user":
                logger.info(f"Saved {active_count} user-specific templates for {self.user_id}")
            else:
                logger.info(f"Saved {active_count} platform-wide templates")
                logger.info(f"Saved {cold_count} cold storage templates")
        except Exception as e:
            if self._db_conn:
                self._db_conn.rollback()
            logger.error(f"Failed to save template store: {e}")

    def get_store_metadata(self) -> Dict[str, Any]:
        """Return metadata about the template store (timestamps, audit log)."""
        if self._db_conn is None:
            return {}

        metadata: Dict[str, Any] = {}
        with self._db_lock:
            cursor = self._db_conn.cursor()
            cursor.execute(
                "SELECT value FROM template_metadata WHERE key=?",
                (f"last_updated::{self._scope}",),
            )
            row = cursor.fetchone()
            if row and row[0]:
                metadata["last_updated"] = row[0]

            cursor.execute(
                "SELECT value FROM template_metadata WHERE key=?",
                (f"audit_log::{self._scope}",),
            )
            row = cursor.fetchone()
            if row and row[0]:
                try:
                    metadata["audit_log"] = json.loads(row[0])
                except json.JSONDecodeError:
                    metadata["audit_log"] = row[0]

        return metadata

    def _get_recent_messages(self, hours: int = 24) -> List[str]:
        """Get recent messages from audit logs that haven't been processed yet"""
        messages = []

        # Read from client_delivered log
        entries = self.audit_logger.get_entries(
            AuditLogType.CLIENT_DELIVERED,
            limit=10000,  # Last 10k messages
        )

        # Filter to recent messages and exclude already processed ones
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        for entry in entries:
            try:
                entry_time = datetime.fromisoformat(entry.timestamp.replace("Z", "+00:00"))
                if (
                    entry_time >= cutoff
                    and entry.plaintext
                    and entry.entry_id not in self.processed_message_ids
                ):
                    messages.append(entry.plaintext)
                    # Mark as processed immediately
                    self.processed_message_ids.add(entry.entry_id)
            except Exception:
                continue

        # Save updated processed message IDs
        if messages:  # Only save if we found new messages
            self._save_processed_message_ids()

        return messages

    def run_discovery(self) -> int:
        """
        Run template discovery on recent audit logs (Claim 3)

        Returns:
            Number of new templates discovered and promoted
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"TEMPLATE DISCOVERY RUN - {datetime.now().isoformat()}")
        logger.info(f"{'='*80}")

        # Get recent messages
        logger.info("Fetching recent messages from audit logs...")
        messages = self._get_recent_messages(hours=24)

        if len(messages) < self.min_messages_for_discovery:
            logger.info(
                f"Not enough messages for discovery: {len(messages)} < {self.min_messages_for_discovery}"
            )
            return 0

        logger.info(f"Analyzing {len(messages)} messages...")

        # Run discovery pipeline (Claims 3, 15, 16)
        candidates = self.discovery_engine.discover_templates(messages)

        # Promote qualified candidates (Claim 17)
        new_templates = 0
        for candidate in candidates:
            if (
                candidate.safety_approved
                and candidate.compression_ratio >= self.discovery_engine.compression_threshold
            ):
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
                        logger.info(f"Skipping promotion: {exc}")
                        continue
                    new_templates += 1

        # Save updated template store (Claim 17)
        if new_templates > 0:
            self._save_template_store()
            self.total_templates_discovered += new_templates

        self.last_discovery_run = datetime.now()

        logger.info(f"\n{'='*80}")
        logger.info(f"DISCOVERY COMPLETE: {new_templates} new templates promoted")
        logger.info(f"Total templates in store: {self.total_templates_discovered}")
        logger.info(f"{'='*80}\n")

        return new_templates

    def _worker_loop(self):
        """Background worker loop"""
        logger.info(f"Template discovery worker started (interval: {self.discovery_interval}s)")

        while self.running:
            try:
                self.run_discovery()
            except Exception as e:
                logger.info(f"Error in discovery worker: {e}")

            # Sleep until next run
            time.sleep(self.discovery_interval)

    def start(self):
        """Start background worker (Claim 3)"""
        if self.running:
            logger.info("Worker already running")
            return

        if self._db_conn is None:
            self._init_database()
            self._load_template_store()

        self.running = True
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
        logger.info("Template discovery worker started")

    def stop(self):
        """Stop background worker"""
        was_running = self.running
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5)
            self.worker_thread = None
        self._close_database()
        if was_running:
            logger.info("Template discovery worker stopped")

    def get_discovered_templates(self) -> Dict[int, str]:
        """Get all discovered templates (template_id -> pattern mapping) from SQL cache"""
        return self.discovered_templates.copy()

    def get_status(self) -> Dict[str, Any]:
        """Get worker status for monitoring"""
        return {
            "running": self.running,
            "last_discovery_run": (
                self.last_discovery_run.isoformat() if self.last_discovery_run else None
            ),
            "total_templates_discovered": self.total_templates_discovered,
            "discovery_interval_seconds": self.discovery_interval,
            "cache_dir": self.cache_dir,
        }


# Global worker instance
_discovery_worker: Optional[TemplateDiscoveryWorker] = None


def start_discovery_worker(
    audit_log_directory: str = "./audit_logs",
    cache_dir: str = ".aura_cache",
    discovery_interval_seconds: int = 3600,
) -> TemplateDiscoveryWorker:
    """
    Start global template discovery worker (Claim 3)

    Args:
        audit_log_directory: Path to audit logs
        cache_dir: Directory for SQL-based persistent cache
        discovery_interval_seconds: Discovery interval (default 1 hour)

    Returns:
        TemplateDiscoveryWorker instance
    """
    global _discovery_worker

    if _discovery_worker is None:
        _discovery_worker = TemplateDiscoveryWorker(
            audit_log_directory=audit_log_directory,
            cache_dir=cache_dir,
            discovery_interval_seconds=discovery_interval_seconds,
        )

    _discovery_worker.start()
    return _discovery_worker


def stop_discovery_worker():
    """Stop global template discovery worker"""
    global _discovery_worker
    if _discovery_worker:
        _discovery_worker.stop()
        _discovery_worker = None


def get_discovery_worker() -> Optional[TemplateDiscoveryWorker]:
    """Get global discovery worker instance"""
    return _discovery_worker
