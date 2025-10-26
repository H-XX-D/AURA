#!/usr/bin/env python3
"""
Display human-readable audit logs from AURA compression system.

This demonstrates that ALL audit logs are human-readable server-side,
not just machine-readable database entries.
"""
from aura_compression.audit_layer import CompressionAuditor
import json
from datetime import datetime

def format_timestamp(iso_timestamp):
    """Convert ISO timestamp to human-readable format."""
    try:
        dt = datetime.fromisoformat(iso_timestamp.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M:%S UTC')
    except:
        return iso_timestamp

def format_bytes(bytes_val):
    """Format bytes in human-readable format."""
    if bytes_val < 1024:
        return f"{bytes_val} B"
    elif bytes_val < 1024 * 1024:
        return f"{bytes_val / 1024:.2f} KB"
    else:
        return f"{bytes_val / (1024 * 1024):.2f} MB"

def print_audit_log(db_path='audit/demo_audit.db', limit=10):
    """Print human-readable audit log."""

    # Open the audit database
    auditor = CompressionAuditor(db_path=db_path)

    # Query recent events
    recent = auditor.db.query({}, limit=limit)

    print()
    print("=" * 100)
    print("AURA COMPRESSION - HUMAN-READABLE SERVER-SIDE AUDIT LOG")
    print("=" * 100)
    print(f"Database: {db_path}")
    print(f"Total Events: {len(recent)}")
    print("=" * 100)
    print()

    for i, entry in enumerate(recent, 1):
        # Header
        print(f"[{i}] EVENT: {entry['event_type'].upper()}")
        print("-" * 100)

        # Time and identification
        print(f"  Time:      {format_timestamp(entry['timestamp'])}")
        print(f"  Event ID:  {entry['event_id']}")
        print(f"  Level:     {entry['level']}")

        # User context
        print(f"  User:      {entry['user_id'] or 'N/A'}")
        print(f"  Session:   {entry['session_id'] or 'N/A'}")
        print(f"  Source IP: {entry['source_ip'] or 'N/A'}")

        # Compression details
        print(f"  Method:    {entry['method'] or 'N/A'}")
        print(f"  Original:  {format_bytes(entry['original_size'] or 0)}")
        print(f"  Compressed: {format_bytes(entry['compressed_size'] or 0)}")

        if entry['compression_ratio']:
            ratio = entry['compression_ratio']
            savings = ((entry['original_size'] - entry['compressed_size']) / entry['original_size'] * 100) if entry['original_size'] else 0
            print(f"  Ratio:     {ratio:.2f}:1 (saved {savings:.1f}%)")

        if entry['latency_ms']:
            print(f"  Latency:   {entry['latency_ms']:.2f} ms")

        # Metadata (human-readable)
        if entry['metadata']:
            meta = entry['metadata']
            print(f"  Metadata:")
            for key, value in meta.items():
                if key != 'compression_ratio':  # Already shown above
                    print(f"    - {key}: {value}")

        # Data lineage
        if entry['data_hash']:
            print(f"  Data Hash: {entry['data_hash'][:32]}... (SHA256)")

        # Audit chain integrity
        if entry['previous_hash']:
            print(f"  Chain Link: {entry['previous_hash'][:32]}... → {entry['entry_hash'][:32]}...")
        else:
            print(f"  Chain Link: [FIRST ENTRY] → {entry['entry_hash'][:32] if entry['entry_hash'] else 'N/A'}...")

        print()

    print("=" * 100)
    print("END OF AUDIT LOG")
    print("=" * 100)
    print()

    # Show statistics
    print("SUMMARY STATISTICS:")
    print("-" * 100)
    stats = auditor.get_stats(hours=24)
    print(f"Time Range: {stats['time_range']}")
    print(f"Start: {stats['start_time']}")
    print(f"End: {stats['end_time']}")
    print()
    print("Metrics by Method:")
    for method, metrics in stats['metrics_by_method'].items():
        print(f"  {method}:")
        print(f"    Operations:     {metrics['operations']}")
        print(f"    Total In:       {format_bytes(metrics['total_bytes_in'])}")
        print(f"    Total Out:      {format_bytes(metrics['total_bytes_out'])}")
        print(f"    Avg Ratio:      {metrics['avg_ratio']:.2f}:1")
        print(f"    Avg Latency:    {metrics['avg_latency_ms']:.2f} ms")
        print(f"    Latency Range:  {metrics['min_latency_ms']:.2f} - {metrics['max_latency_ms']:.2f} ms")

    print()
    print("=" * 100)

    # Verify audit chain
    print("\nAUDIT CHAIN VERIFICATION:")
    print("-" * 100)
    is_valid, errors = auditor.verify_chain(1, len(recent))
    if is_valid:
        print("✓ AUDIT CHAIN INTEGRITY: VERIFIED")
        print("  All cryptographic hashes match. No tampering detected.")
    else:
        print("✗ AUDIT CHAIN INTEGRITY: FAILED")
        for error in errors:
            print(f"  ERROR: {error}")

    print()

if __name__ == "__main__":
    import sys

    db_path = sys.argv[1] if len(sys.argv) > 1 else 'audit/demo_audit.db'
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10

    print_audit_log(db_path, limit)
