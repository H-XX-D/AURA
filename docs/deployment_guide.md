# AURA Compression - Deployment Guide

**Patent Application:** 19/366,538
**Version:** 1.0
**Last Updated:** October 23, 2025

## Table of Contents

1. [Pre-Deployment Checklist](#pre-deployment-checklist)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Deployment Strategies](#deployment-strategies)
5. [Monitoring & Observability](#monitoring--observability)
6. [Troubleshooting](#troubleshooting)
7. [Security Considerations](#security-considerations)
8. [Performance Tuning](#performance-tuning)

---

## Pre-Deployment Checklist

### System Requirements

**Minimum:**
- Python 3.8+
- 2 CPU cores
- 4 GB RAM
- 10 GB disk space (for audit logs)

**Recommended (Production):**
- Python 3.11+
- 8 CPU cores
- 16 GB RAM
- 100 GB SSD storage
- Load balancer (nginx/HAProxy)

### Dependencies

```bash
# Core dependencies
pip install brotli>=1.0.9

# Optional: for experimental BRIO
# (no additional dependencies - uses standard library)

# Development/Testing
pip install pytest pytest-cov
```

### Pre-Flight Validation

```bash
# Run all tests
python -m pytest tests/ -v

# Verify all 31 tests pass
# Expected: 31 passed in ~0.1s

# Check code coverage
python -m pytest tests/ --cov=aura_compression --cov-report=term

# Expected: 61% coverage (production modules)
```

---

## Installation

### Method 1: Package Installation (Recommended)

```bash
# Clone repository
git clone https://github.com/your-org/aura-compression.git
cd aura-compression

# Install in development mode
pip install -e .

# Verify installation
python -c "from aura_compression import ProductionHybridCompressor; print('OK')"
```

### Method 2: Direct Integration

```python
# Add to your project
import sys
sys.path.append('/path/to/aura-compression')

from aura_compression import ProductionHybridCompressor

compressor = ProductionHybridCompressor()
```

### Method 3: Docker Deployment

**Dockerfile:**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy AURA compression
COPY aura_compression/ ./aura_compression/
COPY setup.py .
RUN pip install -e .

# Create directories
RUN mkdir -p /var/log/aura /var/lib/aura

# Copy application
COPY . .

# Run
CMD ["python", "your_app.py"]
```

**docker-compose.yml:**

```yaml
version: '3.8'

services:
  aura-app:
    build: .
    environment:
      - AURA_ENABLE_EXPERIMENTAL=true
      - AURA_TEMPLATE_STORE=/var/lib/aura/templates.json
      - AURA_AUDIT_LOG_DIR=/var/log/aura
    volumes:
      - aura-templates:/var/lib/aura
      - aura-logs:/var/log/aura
    ports:
      - "8000:8000"

volumes:
  aura-templates:
  aura-logs:
```

---

## Configuration

### Basic Configuration

```python
# config/aura_config.py

from aura_compression import ProductionHybridCompressor

def create_compressor(env='production'):
    """Create configured compressor instance"""

    if env == 'production':
        return ProductionHybridCompressor(
            enable_aura=True,                    # Enable BRIO
            min_compression_size=10,             # Compress small messages
            template_store_path='/var/lib/aura/templates.json',
            enable_audit_logging=True,
            audit_log_directory='/var/log/aura',
            aura_preference_margin=0.10          # 10% BRIO preference
        )

    elif env == 'development':
        return ProductionHybridCompressor(
            enable_aura=False,                   # Disable BRIO in dev
            min_compression_size=50,
            template_store_path='./dev_templates.json',
            enable_audit_logging=False
        )

    elif env == 'staging':
        return ProductionHybridCompressor(
            enable_aura=True,
            min_compression_size=20,
            template_store_path='/tmp/staging_templates.json',
            enable_audit_logging=True,
            audit_log_directory='/tmp/staging_audit'
        )
```

### Template Discovery Configuration

```python
# config/discovery_config.py

from aura_compression import TemplateDiscoveryWorker

def start_discovery_worker(compressor):
    """Start background template discovery"""

    worker = TemplateDiscoveryWorker(
        compressor=compressor,
        discovery_interval=3600,      # Every hour
        min_message_count=100,        # Minimum messages before discovery
        template_store_path='/var/lib/aura/templates.json',
        discovery_mode='platform'     # 'platform' or 'user'
    )

    # Start worker thread
    worker.start()

    return worker
```

### Router Configuration

```python
# config/router_config.py

from aura_compression import ProductionRouter

def configure_router():
    """Configure production router"""

    router = ProductionRouter()

    # Register fast-path routes

    # Template-based routes
    router.register_route(
        template_ids=[1, 2, 5],           # "I cannot...", "I'm unable...", etc.
        handler=lambda msg: handle_error_response(msg),
        cache_ttl=300
    )

    router.register_route(
        template_ids=[55, 56, 57, 58],    # Order status queries
        handler=lambda msg: handle_order_status(msg),
        cache_ttl=60
    )

    # Function-based routes
    router.register_route(
        function_ids=['execute_task', 'query_database'],
        handler=lambda msg: handle_ai_function(msg),
        cache_ttl=0  # No caching for functions
    )

    return router
```

---

## Deployment Strategies

### Strategy 1: Incremental Rollout (Recommended)

**Phase 1: ML/AI Outputs (Week 1)**
- Deploy for ML model outputs only
- Expected: 100% template hit rate, 4-6x compression
- Monitor for 1 week

```python
def should_use_aura(message_type):
    if message_type == 'ml_output':
        return True  # Enable AURA
    else:
        return False  # Use existing compression
```

**Phase 2: API Responses (Week 2-3)**
- Add structured API responses
- Expected: 80-100% hit rate, 3-5x compression
- Monitor fast-path percentage (target: 60%+)

**Phase 3: User Requests (Week 4-5)**
- Add form-based user inputs
- Expected: 50-90% hit rate, 2-4x compression
- Monitor compression ratios by template

**Phase 4: Full Rollout (Week 6+)**
- Enable for all message types
- Let fallback handle edge cases
- Continuous monitoring

### Strategy 2: A/B Testing

```python
import random

def get_compressor(user_id):
    """A/B test AURA vs baseline"""

    # Hash user ID to group (consistent assignment)
    user_hash = hash(user_id)
    group = 'aura' if user_hash % 2 == 0 else 'baseline'

    if group == 'aura':
        return ProductionHybridCompressor(enable_aura=True)
    else:
        return ProductionHybridCompressor(enable_aura=False)

# Track metrics per group
metrics = {
    'aura': {'bandwidth': 0, 'latency': [], 'errors': 0},
    'baseline': {'bandwidth': 0, 'latency': [], 'errors': 0}
}
```

### Strategy 3: Canary Deployment

```python
# Deploy to 5% of traffic first
CANARY_PERCENTAGE = 5

def route_to_canary():
    return random.random() < (CANARY_PERCENTAGE / 100)

def handle_message(message):
    if route_to_canary():
        # Use AURA compression
        compressor = ProductionHybridCompressor(enable_aura=True)
    else:
        # Use baseline
        compressor = ProductionHybridCompressor(enable_aura=False)

    return compressor.compress(message)
```

---

## Monitoring & Observability

### Key Metrics to Track

**Compression Metrics:**
```python
from dataclasses import dataclass
from typing import Dict

@dataclass
class CompressionMetrics:
    total_messages: int
    compression_ratios: Dict[str, float]  # by method
    template_hit_rate: float
    bandwidth_saved_bytes: int
    avg_encode_latency_ms: float
    avg_decode_latency_ms: float

    def to_dict(self):
        return {
            'total_messages': self.total_messages,
            'compression_ratios': self.compression_ratios,
            'template_hit_rate': self.template_hit_rate,
            'bandwidth_saved_mb': self.bandwidth_saved_bytes / (1024 * 1024),
            'avg_encode_latency_ms': self.avg_encode_latency_ms,
            'avg_decode_latency_ms': self.avg_decode_latency_ms
        }
```

**Prometheus Exporter:**

```python
from prometheus_client import Counter, Histogram, Gauge

# Counters
messages_compressed = Counter(
    'aura_messages_compressed_total',
    'Total messages compressed',
    ['method']
)

bytes_saved = Counter(
    'aura_bytes_saved_total',
    'Total bytes saved'
)

# Histograms
encode_latency = Histogram(
    'aura_encode_latency_seconds',
    'Compression latency',
    buckets=[0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05, 0.1]
)

compression_ratio = Histogram(
    'aura_compression_ratio',
    'Compression ratio',
    buckets=[0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0, 6.0]
)

# Gauges
template_hit_rate = Gauge(
    'aura_template_hit_rate',
    'Template hit rate percentage'
)

def track_compression(method, original_size, compressed_size, latency):
    messages_compressed.labels(method=method).inc()
    bytes_saved.inc(original_size - compressed_size)
    encode_latency.observe(latency)
    ratio = original_size / compressed_size if compressed_size > 0 else 0
    compression_ratio.observe(ratio)
```

**Grafana Dashboard:**

```json
{
  "dashboard": {
    "title": "AURA Compression Metrics",
    "panels": [
      {
        "title": "Compression Ratio by Method",
        "targets": [
          {
            "expr": "rate(aura_messages_compressed_total[5m])"
          }
        ]
      },
      {
        "title": "Bandwidth Saved",
        "targets": [
          {
            "expr": "rate(aura_bytes_saved_total[5m]) / 1024 / 1024"
          }
        ]
      },
      {
        "title": "Encode Latency (p95)",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, aura_encode_latency_seconds)"
          }
        ]
      },
      {
        "title": "Template Hit Rate",
        "targets": [
          {
            "expr": "aura_template_hit_rate"
          }
        ]
      }
    ]
  }
}
```

### Logging

```python
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/aura/compression.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('aura.compression')

# Log compression events
def compress_with_logging(compressor, text):
    try:
        start = time.time()
        payload, method, metadata = compressor.compress(text)
        latency = (time.time() - start) * 1000

        logger.info(
            f"Compressed message: "
            f"method={metadata['method']}, "
            f"ratio={metadata['ratio']:.2f}x, "
            f"latency={latency:.2f}ms, "
            f"template_id={metadata.get('template_id', 'N/A')}"
        )

        return payload, method, metadata

    except Exception as e:
        logger.error(f"Compression failed: {e}", exc_info=True)
        raise
```

### Health Checks

```python
from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/health')
def health_check():
    """Basic health check"""
    return jsonify({'status': 'healthy'}), 200

@app.route('/health/detailed')
def detailed_health():
    """Detailed health with metrics"""

    try:
        # Test compression
        compressor = ProductionHybridCompressor()
        test_payload, _, _ = compressor.compress("test")
        test_text = compressor.decompress(test_payload)

        # Get metrics
        metrics = get_compression_metrics()

        return jsonify({
            'status': 'healthy',
            'compression_working': test_text == "test",
            'total_messages': metrics.total_messages,
            'template_hit_rate': metrics.template_hit_rate,
            'avg_latency_ms': metrics.avg_encode_latency_ms
        }), 200

    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500
```

---

## Troubleshooting

### Common Issues

#### 1. Low Template Hit Rate (<10%)

**Symptoms:**
- Most messages using brotli fallback
- Low compression ratios
- `metadata['method']` rarely shows `'binary_semantic'` or `'aura'`

**Diagnosis:**
```python
# Check template matching
from aura_compression import TemplateLibrary

lib = TemplateLibrary()
test_messages = [...]  # Your messages

for msg in test_messages:
    match = lib.match(msg)
    if match:
        print(f"Matched template {match.template_id}")
    else:
        print(f"No match: {msg[:60]}")
```

**Solutions:**
1. Add custom templates for your domain
2. Run template discovery on audit logs
3. Check message format matches template patterns
4. Use fuzzy matching (future enhancement)

#### 2. High Encode Latency (>5ms)

**Symptoms:**
- `avg_encode_latency_ms > 5.0`
- Slow response times
- CPU spikes

**Diagnosis:**
```python
import cProfile

# Profile compression
profiler = cProfile.Profile()
profiler.enable()

for msg in messages:
    compressor.compress(msg)

profiler.disable()
profiler.print_stats(sort='cumulative')
```

**Solutions:**
1. Increase `min_compression_size` threshold
2. Disable BRIO for small messages
3. Use faster compression method:
   ```python
   compressor = ProductionHybridCompressor(
       enable_aura=False,  # Disable BRIO
       min_compression_size=100  # Higher threshold
   )
   ```
4. Check for disk I/O bottlenecks (audit logging)
5. Scale horizontally (add more cores)

#### 3. Template Store Corruption

**Symptoms:**
- `FileNotFoundError` or `JSONDecodeError`
- Templates not loading
- Discovery worker crashes

**Diagnosis:**
```bash
# Check template store
cat /var/lib/aura/templates.json | jq .

# Validate JSON
python -c "import json; json.load(open('/var/lib/aura/templates.json'))"
```

**Solutions:**
1. Restore from backup:
   ```bash
   cp /var/lib/aura/templates.json.backup /var/lib/aura/templates.json
   ```

2. Rebuild from audit logs:
   ```python
   from aura_compression import TemplateDiscoveryEngine

   engine = TemplateDiscoveryEngine()
   messages = load_messages_from_audit_logs()
   candidates = engine.discover_templates(messages)

   for candidate in candidates:
       engine.promote_template(candidate)

   store = engine.get_template_store()
   save_template_store(store)
   ```

3. Reset to defaults:
   ```python
   import json

   default_store = {
       "version": "1.0",
       "platform_templates": {},
       "user_templates": {}
   }

   with open('/var/lib/aura/templates.json', 'w') as f:
       json.dump(default_store, f, indent=2)
   ```

#### 4. Audit Log Disk Usage

**Symptoms:**
- Disk space running out
- `/var/log/aura` growing rapidly
- Slow writes

**Diagnosis:**
```bash
# Check audit log size
du -sh /var/log/aura/*

# Check disk space
df -h /var/log
```

**Solutions:**
1. Rotate logs daily:
   ```bash
   # /etc/logrotate.d/aura
   /var/log/aura/*/*.jsonl {
       daily
       rotate 30
       compress
       delaycompress
       notifempty
       create 0644 app app
   }
   ```

2. Archive old logs:
   ```bash
   # Archive logs older than 30 days
   find /var/log/aura -name "*.jsonl" -mtime +30 -exec gzip {} \;
   find /var/log/aura -name "*.gz" -mtime +90 -delete
   ```

3. Use log streaming:
   ```python
   # Stream to external service (e.g., S3, CloudWatch)
   import boto3

   def archive_audit_logs(log_dir):
       s3 = boto3.client('s3')
       for log_file in Path(log_dir).glob('**/*.jsonl'):
           s3.upload_file(
               str(log_file),
               'my-audit-bucket',
               f'audit-logs/{log_file.name}'
           )
           log_file.unlink()  # Delete local copy
   ```

---

## Security Considerations

### 1. Audit Log Protection

**File Permissions:**
```bash
# Restrict audit log access
chmod 700 /var/log/aura
chown app:app /var/log/aura

# Audit logs should be append-only
chattr +a /var/log/aura/*/*.jsonl
```

**Encryption at Rest:**
```bash
# Encrypt audit log partition
cryptsetup luksFormat /dev/sdb1
cryptsetup luksOpen /dev/sdb1 aura-audit
mkfs.ext4 /dev/mapper/aura-audit
mount /dev/mapper/aura-audit /var/log/aura
```

### 2. Template Store Security

**Prevent Template Injection:**
```python
def validate_template(pattern: str) -> bool:
    """Validate template is safe"""

    # Check for code injection
    dangerous_patterns = ['__', 'eval', 'exec', 'import', '__builtins__']
    if any(p in pattern.lower() for p in dangerous_patterns):
        return False

    # Check slot count
    slot_count = pattern.count('{')
    if slot_count > 10:  # Max 10 slots
        return False

    # Check pattern length
    if len(pattern) > 1000:
        return False

    return True

# Use in discovery
if validate_template(candidate.pattern):
    engine.promote_template(candidate)
```

### 3. Rate Limiting

```python
from functools import wraps
import time

def rate_limit(max_calls=100, period=60):
    """Rate limit decorator"""
    calls = []

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            now = time.time()
            calls[:] = [c for c in calls if c > now - period]

            if len(calls) >= max_calls:
                raise Exception("Rate limit exceeded")

            calls.append(now)
            return func(*args, **kwargs)

        return wrapper
    return decorator

@rate_limit(max_calls=1000, period=60)
def compress_message(text):
    return compressor.compress(text)
```

### 4. Input Validation

```python
def validate_message(text: str) -> bool:
    """Validate message before compression"""

    # Check size
    if len(text) > 1_000_000:  # 1 MB max
        raise ValueError("Message too large")

    # Check encoding
    try:
        text.encode('utf-8')
    except UnicodeEncodeError:
        raise ValueError("Invalid UTF-8 encoding")

    # Check for null bytes
    if '\x00' in text:
        raise ValueError("Null bytes not allowed")

    return True
```

---

## Performance Tuning

### 1. Optimize for Your Workload

**For API responses (structured data):**
```python
compressor = ProductionHybridCompressor(
    enable_aura=True,              # Enable BRIO
    min_compression_size=10,       # Compress small messages
    aura_preference_margin=0.15    # Prefer BRIO (15% margin)
)
```

**For chat/conversational:**
```python
compressor = ProductionHybridCompressor(
    enable_aura=False,             # Disable BRIO (brotli is better)
    min_compression_size=50,       # Higher threshold
)
```

**For ML outputs:**
```python
compressor = ProductionHybridCompressor(
    enable_aura=True,
    min_compression_size=5,        # Compress everything
    aura_preference_margin=0.05    # Strongly prefer BRIO
)
```

### 2. Template Discovery Tuning

```python
# Aggressive discovery (learns quickly, may have noise)
worker = TemplateDiscoveryWorker(
    discovery_interval=1800,       # Every 30 minutes
    min_message_count=50,          # Low threshold
    min_frequency=5                # Low frequency requirement
)

# Conservative discovery (slow to learn, high quality)
worker = TemplateDiscoveryWorker(
    discovery_interval=7200,       # Every 2 hours
    min_message_count=500,         # High threshold
    min_frequency=20               # High frequency requirement
)
```

### 3. Memory Optimization

```python
# Limit template cache size
lib = TemplateLibrary()
# Default: loads all templates into memory

# For memory-constrained environments, lazy-load templates
compressor = ProductionHybridCompressor(
    template_store_path='/var/lib/aura/templates.json'
)
# Templates loaded on-demand via _ensure_template_loaded()
```

### 4. CPU Optimization

```python
# Multi-process compression (for high throughput)
from multiprocessing import Pool

def compress_batch(messages):
    compressor = ProductionHybridCompressor()
    return [compressor.compress(msg) for msg in messages]

with Pool(processes=8) as pool:
    results = pool.map(compress_batch, message_batches)
```

---

## Deployment Checklist

- [ ] All tests passing (31/31)
- [ ] Environment variables configured
- [ ] Template store initialized
- [ ] Audit log directory created with proper permissions
- [ ] Log rotation configured
- [ ] Monitoring/alerting set up
- [ ] Health checks implemented
- [ ] Backup strategy defined
- [ ] Rollback plan documented
- [ ] Security review completed
- [ ] Performance benchmarks run
- [ ] Documentation updated
- [ ] Team trained on troubleshooting

---

**Document Version:** 1.0
**Patent Application:** 19/366,538
**Last Updated:** October 23, 2025
