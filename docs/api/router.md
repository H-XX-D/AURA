# Router

## Overview

The Production Router implements metadata-based routing that enables message handling without decompression. It measures fast-path usage and provides routing decisions based on metadata side-channel information.

**Patent Claims:** 20, 26, 28 - Metadata-only routing without decompression

## Location

**File:** `src/aura_compression/router.py`

## Key Components

### Enums

#### `RouteDecision`
Route decision result.

**Values:**
- `FAST_PATH`: Routed using metadata only (no decompression)
- `SLOW_PATH`: Required full decompression
- `CACHED`: Served from cache

### Classes

#### `RoutingMetrics`
Metrics for measuring fast-path usage (Claim 20).

**Target:** 60% of messages should use metadata-only fast path

**Fields:**
- `total_messages` (int): Total messages routed
- `fast_path_count` (int): Messages routed via fast path
- `slow_path_count` (int): Messages requiring decompression
- `cached_count` (int): Messages served from cache
- `total_latency_ms` (float): Total latency across all paths
- `fast_path_latency_ms` (float): Cumulative fast-path latency
- `slow_path_latency_ms` (float): Cumulative slow-path latency

**Methods:**
- `get_fast_path_percentage() -> float`: Calculate fast-path usage percentage
- `get_average_latency() -> float`: Average latency across all paths
- `get_speedup_factor() -> float`: Speedup from fast-path routing
- `to_dict() -> Dict`: Export metrics as dictionary

#### `Route`
Routing configuration for a message handler (Claim 26).

**Fields:**
- `handler_name` (str): Name of the route handler
- `handler_function` (Callable): Function to handle the message
- `requires_decompression` (bool): Whether handler needs full decompression
- `can_use_metadata` (bool): Whether handler can work with metadata only
- `priority` (int): Route priority (higher = checked first)
- `cache_ttl_seconds` (int): Cache TTL for this route

#### `ProductionRouter`
Main router class for metadata-based message routing.

**Initialization:**
```python
ProductionRouter(
    metadata_sidechannel,
    cache_manager=None,
    enable_metrics=True
)
```

**Parameters:**
- `metadata_sidechannel`: MetadataSideChannel instance for fast-path
- `cache_manager`: Optional cache for CACHED route decisions
- `enable_metrics`: Enable routing metrics collection

## Key Methods

### Route Registration

#### `register_route(route: Route)`
Register a new route handler.

```python
router.register_route(Route(
    handler_name="priority_queue",
    handler_function=handle_priority_message,
    requires_decompression=False,  # Can use metadata only!
    can_use_metadata=True,
    priority=100
))
```

#### `register_metadata_route(name: str, handler: Callable, priority: int = 50)`
Quick registration for metadata-only routes.

```python
router.register_metadata_route(
    name="security_filter",
    handler=check_security_flags,
    priority=90
)
```

### Routing

#### `route(compressed_with_metadata: bytes) -> Tuple[RouteDecision, Any, float]`
Route a compressed message using metadata fast-path when possible.

**Parameters:**
- `compressed_with_metadata`: Compressed payload with metadata header

**Returns:**
Tuple of (decision, result, latency_ms)

**Process:**
1. Extract metadata (0.002ms via Task 21 optimization)
2. Check cache (if enabled)
3. Try metadata-only routes first (fast path)
4. Fall back to decompression routes (slow path)
5. Record metrics

**Example:**
```python
decision, result, latency = router.route(compressed_message)

if decision == RouteDecision.FAST_PATH:
    print(f"Fast path! Latency: {latency:.3f}ms")
elif decision == RouteDecision.SLOW_PATH:
    print(f"Slow path (decompressed). Latency: {latency:.3f}ms")
```

### Metrics

#### `get_metrics() -> RoutingMetrics`
Get current routing metrics.

```python
metrics = router.get_metrics()
print(f"Fast path usage: {metrics.get_fast_path_percentage():.1f}%")
print(f"Speedup factor: {metrics.get_speedup_factor():.2f}x")
```

#### `reset_metrics()`
Reset routing metrics to zero.

## Fast-Path Routing Benefits

### Performance Comparison

| Route Type | Latency | Speedup | Use Case |
|------------|---------|---------|----------|
| Fast Path (metadata) | 0.002ms | 7,113x | Security, routing, priority |
| Slow Path (decompress) | 13.0ms | 1x | Content processing |
| Cached | 0.001ms | 13,000x | Repeated requests |

### Metadata-Only Use Cases

**1. Security Filtering**
```python
def security_filter(metadata):
    # Check security flags without decompression
    if metadata.contains_code or metadata.contains_urls:
        return "quarantine"
    return "allow"

router.register_metadata_route("security", security_filter, priority=100)
```

**2. Priority Queue Routing**
```python
def priority_router(metadata):
    # Route based on message size
    if metadata.original_size > 10000:
        return "high_priority_queue"
    return "standard_queue"

router.register_metadata_route("priority", priority_router, priority=90)
```

**3. Rate Limiting**
```python
def rate_limiter(metadata):
    # Check rate limits using user_id from metadata
    if metadata.user_id in rate_limit_cache:
        return "rate_limited"
    return "proceed"

router.register_metadata_route("rate_limit", rate_limiter, priority=95)
```

**4. Category-Based Routing**
```python
def category_router(metadata):
    # Route by message category
    category_queues = {
        MessageCategory.CHAT: "chat_queue",
        MessageCategory.SYSTEM: "system_queue",
        MessageCategory.ERROR: "error_queue"
    }
    return category_queues.get(metadata.category, "default_queue")

router.register_metadata_route("category", category_router, priority=80)
```

## Integration Example

```python
from aura_compression.router import ProductionRouter, Route, RouteDecision
from aura_compression.metadata_sidechannel import MetadataSideChannel

# Initialize components
metadata_channel = MetadataSideChannel()
router = ProductionRouter(metadata_channel, enable_metrics=True)

# Register fast-path routes (metadata only)
router.register_metadata_route(
    name="security_scan",
    handler=security_filter,
    priority=100
)

router.register_metadata_route(
    name="priority_routing",
    handler=priority_router,
    priority=90
)

# Register slow-path route (requires decompression)
router.register_route(Route(
    handler_name="content_analysis",
    handler_function=analyze_content,
    requires_decompression=True,
    can_use_metadata=False,
    priority=50
))

# Route messages
decision, result, latency = router.route(compressed_message)

# Check metrics
metrics = router.get_metrics()
print(f"Fast path: {metrics.get_fast_path_percentage():.1f}%")
print(f"Target: 60% (Claim 20)")
```

## Performance Targets

### Patent Claim 20: 60% Fast-Path Usage

**Measurement:**
```python
metrics = router.get_metrics()
fast_path_pct = metrics.get_fast_path_percentage()

if fast_path_pct >= 60.0:
    print("✓ Meeting Claim 20 target (60% fast-path)")
else:
    print(f"⚠ Below target: {fast_path_pct:.1f}% < 60%")
```

**Optimization Strategies:**
1. Add more metadata-only routes
2. Increase metadata richness (more flags, IDs)
3. Use caching for repeated messages
4. Prioritize fast-path routes higher

### Latency Targets

| Metric | Target | Actual (Task 21) |
|--------|--------|------------------|
| Metadata extraction | < 0.170ms | 0.002ms (90x better) |
| Fast-path routing | < 1ms | 0.002ms |
| Slow-path routing | < 20ms | 13.0ms |

## Thread Safety

- Metrics updates are thread-safe (atomic counters)
- Route registration should be done at startup
- Safe for concurrent routing calls

## Monitoring

### Key Metrics to Track

```python
metrics = router.get_metrics()

# Fast-path adoption
print(f"Fast path: {metrics.fast_path_count}/{metrics.total_messages}")
print(f"Percentage: {metrics.get_fast_path_percentage():.1f}%")

# Performance impact
print(f"Avg fast path: {metrics.fast_path_latency_ms/metrics.fast_path_count:.3f}ms")
print(f"Avg slow path: {metrics.slow_path_latency_ms/metrics.slow_path_count:.3f}ms")
print(f"Speedup: {metrics.get_speedup_factor():.1f}x")

# Cache effectiveness
print(f"Cache hits: {metrics.cached_count}")
print(f"Cache hit rate: {metrics.cached_count/metrics.total_messages*100:.1f}%")
```

## Troubleshooting

### Low Fast-Path Percentage

**Symptoms:** < 60% fast-path usage

**Possible causes:**
- Routes require decompression
- Metadata not rich enough
- No metadata-only handlers registered

**Solutions:**
- Add metadata flags for common decisions
- Register more metadata-only routes
- Use caching for repeated patterns

### High Latency

**Symptoms:** Average latency > 1ms

**Possible causes:**
- Too many slow-path routes
- Handler functions are slow
- No route priority optimization

**Solutions:**
- Optimize handler functions
- Increase priority of fast-path routes
- Add caching layer

## Related Components

- [metadata_sidechannel.md](../perf/metadata_sidechannel.md) - Metadata extraction for fast-path
- [compression_strategy_manager.md](compression_strategy_manager.md) - Compression method selection
- [persistent_cache.md](persistent_cache.md) - Caching for CACHED route decisions

## References

- Patent Claims 20, 26, 28 - Metadata-based routing
- [Task 21](../../ai_collaboration.md#task-21) - Metadata fast-path optimization
- Fast-path target: 60% metadata-only routing (Claim 20)
