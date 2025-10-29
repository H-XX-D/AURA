#!/usr/bin/env python3
"""
Real-Time AURA Audit Log Viewer - Human-Readable Server-Side Logs

This tool displays compression audit logs in real-time, fully human-readable.
Perfect for monitoring, debugging, and compliance verification.

Usage:
    python3 audit_log_viewer.py                    # View default audit log
    python3 audit_log_viewer.py --tail             # Real-time tail mode
    python3 audit_log_viewer.py --user demo_user   # Filter by user
    python3 audit_log_viewer.py --errors           # Show only errors
"""
import argparse
import time
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional


class AuditLogViewer:
    """Human-readable audit log viewer with real-time monitoring."""

    # ANSI color codes for beautiful terminal output
    COLORS = {
        'RESET': '\033[0m',
        'BOLD': '\033[1m',
        'RED': '\033[91m',
        'GREEN': '\033[92m',
        'YELLOW': '\033[93m',
        'BLUE': '\033[94m',
        'MAGENTA': '\033[95m',
        'CYAN': '\033[96m',
        'GRAY': '\033[90m',
    }

    # Event type colors
    EVENT_COLORS = {
        'compress_success': 'GREEN',
        'decompress_success': 'BLUE',
        'compress_failure': 'RED',
        'decompress_failure': 'RED',
        'method_selection': 'CYAN',
        'pattern_discovery': 'MAGENTA',
        'dictionary_build': 'MAGENTA',
    }

    # Level colors
    LEVEL_COLORS = {
        'INFO': 'GRAY',
        'WARNING': 'YELLOW',
        'ERROR': 'RED',
        'SECURITY': 'MAGENTA',
    }

    def __init__(self, db_path: str = "audit/demo_audit.db", use_colors: bool = True):
        """Initialize audit log viewer."""
        self.db_path = Path(db_path)
        self.use_colors = use_colors
        self.last_id = 0

    def color(self, text: str, color_name: str) -> str:
        """Apply color to text if colors are enabled."""
        if not self.use_colors:
            return text
        color = self.COLORS.get(color_name, '')
        reset = self.COLORS['RESET']
        return f"{color}{text}{reset}"

    def format_timestamp(self, iso_timestamp: str) -> str:
        """Format timestamp for display."""
        try:
            dt = datetime.fromisoformat(iso_timestamp.replace('Z', '+00:00'))
            return dt.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3] + ' UTC'
        except:
            return iso_timestamp

    def format_bytes(self, bytes_val: int) -> str:
        """Format bytes in human-readable format."""
        if bytes_val < 1024:
            return f"{bytes_val} B"
        elif bytes_val < 1024 * 1024:
            return f"{bytes_val / 1024:.2f} KB"
        else:
            return f"{bytes_val / (1024 * 1024):.2f} MB"

    def format_entry(self, entry: dict, detailed: bool = True) -> str:
        """Format a single audit entry as human-readable text."""
        lines = []

        # Event header
        event_type = entry['event_type']
        event_color = self.EVENT_COLORS.get(event_type, 'RESET')
        level_color = self.LEVEL_COLORS.get(entry['level'], 'RESET')

        header = f"[{entry['id']}] {event_type.upper()}"
        lines.append(self.color(header, event_color))

        # Timestamp and level
        timestamp = self.format_timestamp(entry['timestamp'])
        level_badge = f"[{entry['level']}]"
        lines.append(f"  {timestamp} {self.color(level_badge, level_color)}")

        # User context (compact)
        if entry['user_id'] or entry['session_id']:
            user_info = f"  👤 User: {entry['user_id'] or 'N/A'} | Session: {entry['session_id'] or 'N/A'}"
            if entry['source_ip']:
                user_info += f" | IP: {entry['source_ip']}"
            lines.append(user_info)

        # Compression metrics (compact)
        if entry['original_size'] and entry['compressed_size']:
            orig = self.format_bytes(entry['original_size'])
            comp = self.format_bytes(entry['compressed_size'])
            ratio = entry['compression_ratio'] or 1.0
            latency = entry['latency_ms'] or 0

            # Calculate savings
            if entry['original_size'] > 0:
                savings = ((entry['original_size'] - entry['compressed_size']) / entry['original_size'] * 100)
                savings_text = f"saved {savings:.1f}%" if savings > 0 else f"expanded {-savings:.1f}%"
            else:
                savings_text = "N/A"

            metrics = f"  📊 {orig} → {comp} ({ratio:.2f}:1, {savings_text})"
            if latency > 0:
                metrics += f" | ⚡ {latency:.2f} ms"

            # Color code based on performance
            if ratio >= 2.0 and latency < 5.0:
                metrics = self.color(metrics, 'GREEN')
            elif ratio < 1.0:
                metrics = self.color(metrics, 'YELLOW')

            lines.append(metrics)

        # Method
        if entry['method'] and entry['method'] != 'pending':
            lines.append(f"  🔧 Method: {entry['method']}")

        # Metadata (selective - only show important fields)
        if detailed and entry['metadata']:
            import json
            meta = json.loads(entry['metadata']) if isinstance(entry['metadata'], str) else entry['metadata']

            interesting_keys = ['template_id', 'patterns_found', 'file_type', 'compression_layer', 'error']
            for key in interesting_keys:
                if key in meta:
                    lines.append(f"     ↳ {key}: {meta[key]}")

        # Data lineage (compact hash display)
        if detailed and entry['data_hash']:
            hash_short = entry['data_hash'][:16] + '...'
            lines.append(f"  🔗 Data: {hash_short}")

        lines.append("")  # Blank line between entries
        return "\n".join(lines)

    def view(self, filters: Optional[dict] = None, limit: int = 20, detailed: bool = True):
        """View audit logs with optional filters."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Build query
        where_clauses = []
        params = []

        if filters:
            if 'user_id' in filters:
                where_clauses.append("user_id = ?")
                params.append(filters['user_id'])

            if 'session_id' in filters:
                where_clauses.append("session_id = ?")
                params.append(filters['session_id'])

            if 'level' in filters:
                where_clauses.append("level = ?")
                params.append(filters['level'])

            if 'event_type' in filters:
                where_clauses.append("event_type = ?")
                params.append(filters['event_type'])

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        query = f"""
            SELECT * FROM audit_log
            WHERE {where_sql}
            ORDER BY id DESC
            LIMIT ?
        """
        params.append(limit)

        cursor.execute(query, params)
        columns = [desc[0] for desc in cursor.description]

        # Print header
        print(self.color("=" * 100, 'BOLD'))
        print(self.color("AURA COMPRESSION - LIVE AUDIT LOG (Human-Readable)", 'BOLD'))
        print(self.color("=" * 100, 'BOLD'))
        print(f"Database: {self.db_path}")
        if filters:
            print(f"Filters: {filters}")
        print(self.color("=" * 100, 'BOLD'))
        print()

        # Print entries
        count = 0
        for row in cursor.fetchall():
            entry = dict(zip(columns, row))
            print(self.format_entry(entry, detailed=detailed))
            count += 1

        print(self.color(f"Showing {count} most recent entries", 'GRAY'))
        print()
        conn.close()

    def tail(self, interval: float = 1.0, filters: Optional[dict] = None):
        """Tail audit log in real-time (like tail -f)."""
        print(self.color("=" * 100, 'BOLD'))
        print(self.color("AURA COMPRESSION - REAL-TIME AUDIT LOG MONITOR", 'BOLD'))
        print(self.color("=" * 100, 'BOLD'))
        print(f"Database: {self.db_path}")
        print("Monitoring for new events... (Press Ctrl+C to stop)")
        print(self.color("=" * 100, 'BOLD'))
        print()

        conn = sqlite3.connect(str(self.db_path))

        # Get current max ID
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(id) FROM audit_log")
        result = cursor.fetchone()
        self.last_id = result[0] or 0

        try:
            while True:
                # Query for new entries
                where_clauses = [f"id > {self.last_id}"]
                params = []

                if filters:
                    if 'user_id' in filters:
                        where_clauses.append("user_id = ?")
                        params.append(filters['user_id'])
                    if 'level' in filters:
                        where_clauses.append("level = ?")
                        params.append(filters['level'])

                where_sql = " AND ".join(where_clauses)

                query = f"""
                    SELECT * FROM audit_log
                    WHERE {where_sql}
                    ORDER BY id ASC
                """

                cursor.execute(query, params)
                columns = [desc[0] for desc in cursor.description]

                new_entries = []
                for row in cursor.fetchall():
                    entry = dict(zip(columns, row))
                    new_entries.append(entry)
                    self.last_id = max(self.last_id, entry['id'])

                # Print new entries
                for entry in new_entries:
                    print(self.format_entry(entry, detailed=True))

                time.sleep(interval)

        except KeyboardInterrupt:
            print()
            print(self.color("Monitoring stopped.", 'YELLOW'))
            print()

        finally:
            conn.close()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='AURA Audit Log Viewer - Human-Readable Server-Side Logs',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('--db', type=str, default='audit/demo_audit.db',
                        help='Path to audit database (default: audit/demo_audit.db)')
    parser.add_argument('--tail', action='store_true',
                        help='Real-time tail mode (like tail -f)')
    parser.add_argument('--user', type=str,
                        help='Filter by user ID')
    parser.add_argument('--session', type=str,
                        help='Filter by session ID')
    parser.add_argument('--errors', action='store_true',
                        help='Show only errors and warnings')
    parser.add_argument('--limit', type=int, default=20,
                        help='Number of entries to show (default: 20)')
    parser.add_argument('--no-color', action='store_true',
                        help='Disable colored output')
    parser.add_argument('--compact', action='store_true',
                        help='Compact output (less detail)')

    args = parser.parse_args()

    # Build filters
    filters = {}
    if args.user:
        filters['user_id'] = args.user
    if args.session:
        filters['session_id'] = args.session
    if args.errors:
        filters['level'] = 'ERROR'  # This will need to be enhanced to include WARNING

    # Create viewer
    viewer = AuditLogViewer(db_path=args.db, use_colors=not args.no_color)

    # Run in appropriate mode
    if args.tail:
        viewer.tail(interval=1.0, filters=filters if filters else None)
    else:
        viewer.view(filters=filters if filters else None, limit=args.limit, detailed=not args.compact)


if __name__ == "__main__":
    main()
