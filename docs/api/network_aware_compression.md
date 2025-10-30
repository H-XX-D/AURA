# Network Aware Compression API Reference

## Overview

The `network_aware_compression.py` module provides adaptive compression that optimizes for network conditions, automatically adjusting compression strategies based on latency, bandwidth, and packet loss.

## Classes

### NetworkAwareCompressor

Adaptive compression based on network conditions.

#### Constructor

```python
NetworkAwareCompressor(
    enable_adaptation: bool = True,
    network_monitor_interval: float = 1.0,
    adaptation_threshold: float = 0.1
)
```

**Parameters:**
- `enable_adaptation`: Enable automatic network adaptation (default: True)
- `network_monitor_interval`: Network monitoring interval in seconds (default: 1.0)
- `adaptation_threshold`: Threshold for triggering adaptation (default: 0.1)

## Methods

### compress_adaptive(text, network_conditions=None)

Compress with network-aware adaptation.

```python
def compress_adaptive(self, text: str, network_conditions: Optional[Dict[str, Any]] = None) -> Tuple[bytes, dict]:
```

**Parameters:**
- `text`: Input text to compress
- `network_conditions`: Optional network metrics (auto-detected if None)

**Returns:**
- `Tuple[bytes, dict]`: (compressed_data, metadata)

### get_network_conditions()

Get current network condition assessment.

```python
def get_network_conditions(self) -> Dict[str, Any]:
```

**Returns:**
- `Dict[str, Any]`: Network condition metrics

### adapt_strategy(network_quality)

Adapt compression strategy for network quality.

```python
def adapt_strategy(self, network_quality: str) -> Dict[str, Any]:
```

**Parameters:**
- `network_quality`: Network quality level ('excellent', 'good', 'moderate', 'poor', 'very_poor')

**Returns:**
- `Dict[str, Any]`: Adapted compression parameters

### monitor_network()

Monitor network conditions in background.

```python
def monitor_network(self) -> None:
```

Starts background network monitoring thread.

## Network Condition Assessment

### Quality Levels

```python
network_quality = compressor.get_network_conditions()

# Returns assessment like:
{
    'quality': 'excellent',     # excellent, good, moderate, poor, very_poor
    'latency_ms': 15,           # Round-trip time
    'bandwidth_mbps': 500,      # Download bandwidth
    'packet_loss': 0.001,       # Packet loss ratio (0.0-1.0)
    'jitter_ms': 2,             # Latency variation
    'connection_type': 'fiber'  # wifi, ethernet, cellular, satellite
}
```

### Automatic Adaptation Logic

```python
# Network-aware strategy selection
if network_quality == 'excellent':
    strategy = 'maximum_compression'  # BRIO full, slow but best ratio
elif network_quality == 'good':
    strategy = 'balanced'            # AURA-Lite, good balance
elif network_quality == 'moderate':
    strategy = 'balanced'            # AURA-Lite, adaptive
elif network_quality == 'poor':
    strategy = 'fast_compression'    # Binary semantic or uncompressed
else:  # very_poor
    strategy = 'minimal_compression' # Uncompressed for speed
```

## Usage Examples

### Basic Network-Aware Compression

```python
from aura_compression.network_aware_compression import NetworkAwareCompressor

# Initialize with network monitoring
compressor = NetworkAwareCompressor(enable_adaptation=True)

# Start network monitoring
compressor.monitor_network()

# Compress with automatic adaptation
compressed, metadata = compressor.compress_adaptive(text)

print(f"Network quality: {metadata['network_quality']}")
print(f"Selected strategy: {metadata['strategy']}")
print(f"Compression ratio: {metadata['ratio']:.2f}x")
```

### Manual Network Specification

```python
# Specify network conditions manually
network_conditions = {
    'latency_ms': 100,
    'bandwidth_mbps': 10,
    'packet_loss': 0.05,
    'connection_type': 'satellite'
}

compressed, metadata = compressor.compress_adaptive(text, network_conditions)
```

### Network Quality Monitoring

```python
# Get current network assessment
conditions = compressor.get_network_conditions()

print("Current network conditions:")
for key, value in conditions.items():
    print(f"  {key}: {value}")

# Get adaptation recommendations
adaptation = compressor.adapt_strategy(conditions['quality'])
print(f"Recommended strategy: {adaptation['strategy']}")
print(f"Chunk size: {adaptation['chunk_size']}")
print(f"Priority: {adaptation['priority']}")  # speed, ratio, balanced
```

## Network Quality Metrics

### Latency Thresholds

| Quality Level | Latency (ms) | Bandwidth (Mbps) | Packet Loss |
|---------------|--------------|------------------|-------------|
| Excellent | < 10 | > 100 | < 0.001 |
| Good | < 50 | > 10 | < 0.01 |
| Moderate | < 200 | > 1 | < 0.05 |
| Poor | < 1000 | > 0.1 | < 0.1 |
| Very Poor | > 1000 | < 0.1 | > 0.1 |

### Connection Type Detection

```python
# Automatic connection type detection
connection_types = {
    'wifi': {'typical_latency': 20, 'typical_bandwidth': 100},
    'ethernet': {'typical_latency': 5, 'typical_bandwidth': 1000},
    'cellular': {'typical_latency': 50, 'typical_bandwidth': 50},
    'satellite': {'typical_latency': 600, 'typical_bandwidth': 20},
    'dialup': {'typical_latency': 150, 'typical_bandwidth': 0.056}
}
```

## Adaptive Strategies

### Strategy Selection Matrix

| Network Quality | Primary Strategy | Fallback | Chunk Size | Priority |
|-----------------|------------------|----------|------------|----------|
| Excellent | BRIO Full | AURA Heavy | Large (4KB) | Ratio |
| Good | AURA-Lite | BRIO TCP | Medium (2KB) | Balanced |
| Moderate | AURA-Lite | Binary Semantic | Small (1KB) | Balanced |
| Poor | Binary Semantic | Uncompressed | Tiny (512B) | Speed |
| Very Poor | Uncompressed | Uncompressed | Stream | Speed |

### Dynamic Adaptation

```python
# Real-time adaptation based on performance feedback
def adapt_to_performance(self, compression_time, network_rtt):
    efficiency = compression_time / network_rtt

    if efficiency > 2.0:  # Compression slower than network
        self.increase_speed_priority()
    elif efficiency < 0.5:  # Network much slower
        self.increase_ratio_priority()
    else:
        self.maintain_balance()
```

## Performance Characteristics

### Network-Aware Performance

| Network Quality | Compression Ratio | Processing Time | Bandwidth Savings |
|-----------------|-------------------|-----------------|-------------------|
| Excellent | 4.5:1 | 2.0ms | 78% |
| Good | 3.2:1 | 1.2ms | 69% |
| Moderate | 2.1:1 | 0.8ms | 52% |
| Poor | 1.8:1 | 0.4ms | 44% |
| Very Poor | 1.0:1 | 0.1ms | 0% |

### Adaptation Speed

- **Network detection**: ~10ms initial, ~1ms ongoing
- **Strategy switching**: ~0.1ms (pre-computed)
- **Quality reassessment**: Every 1 second (configurable)

## Integration with Main Compressor

### Automatic Network Awareness

```python
from aura_compression.compressor import ProductionHybridCompressor

# Network awareness is built-in
compressor = ProductionHybridCompressor(enable_network_adaptation=True)

# Compressor automatically adapts to network
compressed, metadata = compressor.compress(text)

# Check network adaptation
if metadata.get('network_adapted', False):
    print(f"Network quality: {metadata['network_quality']}")
    print(f"Adaptation applied: {metadata['adaptation']}")
```

### Manual Network Control

```python
# Manual network specification
compressor.set_network_conditions({
    'latency_ms': 50,
    'bandwidth_mbps': 25,
    'packet_loss': 0.02
})

# Force specific adaptation
compressor.set_network_adaptation('aggressive')  # conservative, balanced, aggressive
```

## Background Monitoring

### Continuous Network Monitoring

```python
# Start background monitoring
compressor.monitor_network()

# Monitoring runs in separate thread
# Automatically updates compression strategies
# Adapts to changing network conditions

# Stop monitoring when done
compressor.stop_network_monitoring()
```

### Monitoring Statistics

```python
# Get monitoring statistics
stats = compressor.get_network_stats()

print("Network monitoring stats:")
print(f"  Samples collected: {stats['samples']}")
print(f"  Average latency: {stats['avg_latency_ms']}ms")
print(f"  Quality changes: {stats['quality_changes']}")
print(f"  Adaptation triggers: {stats['adaptations']}")
```

## Error Handling

Network-aware compression provides robust error handling:

```python
try:
    compressed, metadata = compressor.compress_adaptive(text)
except NetworkDetectionError:
    # Fallback to default compression
    compressed, metadata = compressor.compress_default(text)
except NetworkTimeoutError:
    # Use fastest compression
    compressed, metadata = compressor.compress_fastest(text)
```

## Dependencies

- `psutil`: Network interface monitoring
- `speedtest-cli`: Bandwidth testing (optional)
- `ping3`: Latency measurement
- `threading`: Background monitoring
- `time`: Timing measurements

## Platform Support

### Supported Platforms

- **macOS**: Full network monitoring
- **Linux**: Full network monitoring
- **Windows**: Limited network monitoring
- **Containers**: Network detection may be limited

### Network Interface Detection

```python
# Automatic interface detection
interfaces = compressor.detect_network_interfaces()

for interface in interfaces:
    print(f"Interface: {interface['name']}")
    print(f"  Type: {interface['type']}")  # wifi, ethernet, cellular
    print(f"  Speed: {interface['speed_mbps']} Mbps")
    print(f"  Active: {interface['active']}")
```

## Troubleshooting

### Common Issues

**Network not detected:**
```bash
# Check network interfaces
python -c "import psutil; print(psutil.net_if_stats())"

# Test connectivity
ping -c 3 8.8.8.8
```

**Poor adaptation:**
- Check monitoring interval (default 1.0s)
- Verify network permissions
- Test with manual network conditions

**Performance overhead:**
- Disable monitoring for static networks
- Increase monitoring interval
- Use manual network specification

**Container environments:**
- Network detection may be limited
- Use manual network condition specification
- Disable automatic adaptation if needed