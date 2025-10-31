# Background Workers

## Overview

Background Workers provide automatic template discovery and maintenance functionality. The system continuously mines audit logs to discover new compression templates, test their effectiveness, and promote them to production use without manual intervention.

**Patent Claims:** 3, 16, 17 - Continuous template mining and automatic promotion

## Location

**File:** `src/aura_compression/background_workers.py`

## Key Components

### `TemplateDiscoveryWorker`

Background worker that runs on a schedule to discover, test, and promote new compression templates from audit logs.

#### Initialization

```python
TemplateDiscoveryWorker(
    audit_log_directory="./audit_logs",
    template_store_path="./template_store.json",
    discovery_interval_seconds=3600,  # Run every hour
    min_messages_for_discovery=100,
    min_frequency=5,
    compression_threshold=1.1,
    user_id=None,
    discovery_mode="platform"
)
```

**Parameters:**
- `audit_log_directory`: Path to audit logs containing message history
- `template_store_path`: Path to persistent template store JSON file
- `discovery_interval_seconds`: How often to run discovery (default: 1 hour)
- `min_messages_for_discovery`: Minimum messages needed before running discovery
- `min_frequency`: Minimum pattern occurrences for template promotion (Claim 16)
- `compression_threshold`: Minimum compression ratio advantage (e.g., 1.1 = 10% better)
- `user_id`: Optional user ID for user-specific template discovery
- `discovery_mode`: "platform" (shared templates) or "user" (per-user templates)

### Template ID Allocation (V3)

The system uses a hierarchical template ID allocation scheme:

| ID Range | Count | Purpose | Mode |
|----------|-------|---------|------|
| 0-49 | 50 | AI → AI communication | Universal |
| 50-108 | 59 | Human → AI messages | Universal |
| 109-148 | 40 | ML/AI model templates | Universal |
| **149-1000** | **852** | **Platform rolling discovery** | **Shared** |
| 1001-1015 | 15 | Reserved routing templates | System |
| 1016-1047 | 32 | User-specific templates | Per-user |

**Platform Mode** (`discovery_mode="platform"`):
- Uses ID range 149-1000 (852 slots)
- Templates shared across all users
- Suitable for common message patterns

**User Mode** (`discovery_mode="user"`):
- Uses ID range 1016-1047 (32 slots per user)
- Templates isolated to specific user
- Requires `user_id` parameter

## Key Methods

### `start()`
Start the background worker thread.

```python
worker.start()
```

Starts a daemon thread that:
1. Runs every `discovery_interval_seconds`
2. Checks if enough new messages exist
3. Triggers template discovery
4. Promotes discovered templates

### `stop()`
Stop the background worker thread gracefully.

```python
worker.stop()
```

Sets running flag to False and waits for thread to complete.

### `run_discovery(force: bool = False) -> Dict[str, Any]`
Run a single discovery cycle manually.

**Parameters:**
- `force`: Skip message count check and run immediately

**Returns:**
Dictionary with discovery results:
```python
{
    'templates_discovered': 5,
    'templates_promoted': 3,
    'messages_analyzed': 1250,
    'discovery_time_seconds': 12.5,
    'timestamp': '2025-10-30T21:35:06'
}
```

**Process:**
1. Load unanalyzed messages from audit logs
2. Extract message patterns
3. Calculate frequency and compression effectiveness
4. Promote templates meeting thresholds
5. Save to template store
6. Mark messages as processed

### Discovery Pipeline

```
Audit Logs → Pattern Extraction → Frequency Analysis →
Compression Testing → Threshold Filtering → Template Promotion →
Template Store → Production Use
```

## Template Discovery Process

### 1. Message Collection
- Reads audit logs from `audit_log_directory`
- Filters for unprocessed messages
- Tracks processed message IDs to avoid re-analysis

### 2. Pattern Extraction
- Identifies variable slots in messages
- Extracts template structure
- Groups similar messages

### 3. Frequency Analysis
- Counts pattern occurrences
- Filters patterns with `frequency >= min_frequency`
- Prioritizes high-frequency patterns

### 4. Compression Testing
- Compares template compression vs baseline
- Calculates compression ratio improvement
- Filters by `compression_threshold` (e.g., 1.1 = 10% better)

### 5. Template Promotion
- Assigns template IDs from allocated range
- Saves to `template_store.json`
- Makes available for production compression

### 6. Persistence
- Saves discovered templates
- Tracks processed message IDs
- Updates worker statistics

## Integration Example

```python
from aura_compression.background_workers import TemplateDiscoveryWorker

# Create worker for platform-wide discovery
worker = TemplateDiscoveryWorker(
    audit_log_directory="./audit_logs",
    template_store_path="./template_store.json",
    discovery_interval_seconds=3600,  # Every hour
    min_messages_for_discovery=100,
    min_frequency=5,
    compression_threshold=1.1,
    discovery_mode="platform"
)

# Start background thread
worker.start()

# ... application runs ...

# Manual discovery (optional)
results = worker.run_discovery(force=True)
print(f"Discovered {results['templates_discovered']} new templates")

# Stop worker on shutdown
worker.stop()
```

## User-Specific Discovery

For per-user template isolation:

```python
# Create worker for specific user
user_worker = TemplateDiscoveryWorker(
    audit_log_directory=f"./audit_logs/user_{user_id}",
    template_store_path=f"./templates/user_{user_id}.json",
    discovery_interval_seconds=7200,  # Every 2 hours
    user_id=user_id,
    discovery_mode="user",
    min_frequency=3,  # Lower threshold for user templates
    compression_threshold=1.05  # 5% improvement sufficient
)

user_worker.start()
```

## Performance Characteristics

### Discovery Cycle Performance
- **Message analysis**: ~0.5ms per message
- **Pattern extraction**: ~1ms per unique pattern
- **Compression testing**: ~5ms per candidate template
- **Total cycle time**: 10-30 seconds for 1,000 messages

### Resource Usage
- **CPU**: Bursty during discovery cycles, idle between
- **Memory**: ~10MB base + ~1KB per analyzed message
- **Disk I/O**: Reads audit logs, writes template store

### Scheduling
- **Default interval**: 3600 seconds (1 hour)
- **Minimum messages**: 100 new messages required
- **Thread model**: Single daemon thread per worker

## Configuration Guidelines

### High-Traffic Applications
```python
discovery_interval_seconds=1800  # Every 30 minutes
min_messages_for_discovery=500   # Need more data
min_frequency=10                 # Higher quality threshold
compression_threshold=1.2        # 20% improvement required
```

### Low-Traffic Applications
```python
discovery_interval_seconds=7200  # Every 2 hours
min_messages_for_discovery=50    # Lower threshold
min_frequency=3                  # Accept rarer patterns
compression_threshold=1.05       # 5% improvement sufficient
```

### Development/Testing
```python
discovery_interval_seconds=300   # Every 5 minutes
min_messages_for_discovery=10    # Quick discovery
min_frequency=2                  # Very low threshold
compression_threshold=1.01       # Any improvement
```

## Monitoring

### Worker Statistics

```python
# Check worker status
print(f"Running: {worker.running}")
print(f"Last run: {worker.last_discovery_run}")
print(f"Total discovered: {worker.total_templates_discovered}")
print(f"Processed messages: {len(worker.processed_message_ids)}")
```

### Discovery Results

Each `run_discovery()` returns metrics:
- `templates_discovered`: New templates found
- `templates_promoted`: Templates added to production
- `messages_analyzed`: Messages processed this cycle
- `discovery_time_seconds`: Cycle duration

## Thread Safety

- Worker runs in separate daemon thread
- Template store writes are atomic (file replacement)
- Processed message tracking is thread-safe
- Safe to run multiple workers with different stores

## Limitations

1. **Single-threaded**: One discovery cycle at a time
2. **Memory-bound**: All messages loaded into memory
3. **No distributed coordination**: Each worker operates independently
4. **Template limit**: 852 platform templates, 32 user templates

## Troubleshooting

### No Templates Discovered

**Possible causes:**
- Not enough messages (`min_messages_for_discovery`)
- Patterns too rare (`min_frequency`)
- Compression threshold too high (`compression_threshold`)
- Template ID range exhausted

**Solutions:**
- Lower `min_frequency` threshold
- Reduce `compression_threshold`
- Check template store for ID usage
- Increase discovery interval for more data

### High CPU Usage

**Possible causes:**
- Discovery interval too short
- Too many messages per cycle
- Complex pattern extraction

**Solutions:**
- Increase `discovery_interval_seconds`
- Raise `min_messages_for_discovery`
- Archive old audit logs

### Template Store Corruption

**Recovery:**
- Worker creates backup before writes
- Restore from `template_store.json.backup`
- Re-run discovery to regenerate

## Related Components

- [discovery.md](discovery.md) - Template discovery engine
- [audit.md](audit.md) - Audit logging system
- [templates.md](templates.md) - Template storage and matching
- [template_service.md](template_service.md) - Template service layer

## References

- Patent Claims 3, 16, 17 - Automatic template discovery and promotion
- Template ID allocation scheme (V3)
- [Task 19](../../ai_collaboration.md#task-19) - Template cache self-healing
