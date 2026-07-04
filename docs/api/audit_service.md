# Audit Service API Reference

## Overview

The `audit_service.py` module provides a distributed audit service for AURA compression systems, enabling centralized audit logging, real-time monitoring, and compliance reporting across multiple nodes.

## Classes

### AuditService

Main audit service class for distributed logging.

#### Constructor

```python
AuditService(
    service_url: str = "http://localhost:8080",
    api_key: str = None,
    enable_buffering: bool = True,
    buffer_size: int = 1000,
    flush_interval: int = 30
)
```

**Parameters:**
- `service_url`: Audit service endpoint URL
- `api_key`: Service authentication key
- `enable_buffering`: Enable event buffering (default: True)
- `buffer_size`: Maximum buffer size (default: 1000)
- `flush_interval`: Buffer flush interval in seconds (default: 30)

## Methods

### log_event(event_type, data, metadata)

Log an audit event to the service.

```python
def log_event(
    self,
    event_type: str,
    data: Dict[str, Any],
    metadata: Dict[str, Any] = None
) -> bool:
```

**Parameters:**
- `event_type`: Type of audit event
- `data`: Event data payload
- `metadata`: Additional metadata

**Returns:**
- `bool`: True if logged successfully

### log_compression(operation, original_size, compressed_size, method)

Log compression operation.

```python
def log_compression(
    self,
    operation: str,
    original_size: int,
    compressed_size: int,
    method: str
) -> None:
```

**Parameters:**
- `operation`: Compression operation type
- `original_size`: Original data size
- `compressed_size`: Compressed data size
- `method`: Compression method used

### log_performance(operation, duration, throughput, metadata)

Log performance metrics.

```python
def log_performance(
    self,
    operation: str,
    duration: float,
    throughput: float,
    metadata: Dict[str, Any] = None
) -> None:
```

**Parameters:**
- `operation`: Operation name
- `duration`: Operation duration in seconds
- `throughput`: Operations per second
- `metadata`: Additional performance data

### log_error(error_type, error_message, context)

Log error events.

```python
def log_error(
    self,
    error_type: str,
    error_message: str,
    context: Dict[str, Any] = None
) -> None:
```

**Parameters:**
- `error_type`: Type of error
- `error_message`: Error description
- `context`: Error context information

### query_events(start_date, end_date, filters)

Query audit events.

```python
def query_events(
    self,
    start_date: datetime,
    end_date: datetime,
    filters: Dict[str, Any] = None
) -> List[AuditEvent]:
```

**Parameters:**
- `start_date`: Query start date
- `end_date`: Query end date
- `filters`: Query filters

**Returns:**
- `List[AuditEvent]`: Matching audit events

### get_metrics(time_range)

Get audit service metrics.

```python
def get_metrics(self, time_range: str = "1h") -> ServiceMetrics:
```

**Parameters:**
- `time_range`: Time range for metrics ("1h", "24h", "7d")

**Returns:**
- `ServiceMetrics`: Service performance metrics

### flush_buffer()

Force flush buffered events.

```python
def flush_buffer(self) -> int:
```

**Returns:**
- `int`: Number of events flushed

## AuditEvent Class

```python
@dataclass
class AuditEvent:
    event_id: str
    timestamp: datetime
    event_type: str
    node_id: str
    user_id: Optional[str]
    session_id: Optional[str]
    data: Dict[str, Any]
    metadata: Dict[str, Any]
    compliance_flags: List[str]
```

## ServiceMetrics Class

```python
@dataclass
class ServiceMetrics:
    total_events: int
    events_per_second: float
    storage_used_gb: float
    query_latency_ms: float
    error_rate: float
    compliance_score: float
```

## Usage Examples

### Basic Service Logging

```python
from aura_compression.audit_service import AuditService

# Initialize audit service
audit = AuditService(
    service_url="https://audit.aura.company.com",
    api_key="your-api-key"
)

# Log compression event
audit.log_compression(
    operation="message_compress",
    original_size=1024,
    compressed_size=256,
    method="hybrid_brc"
)

# Log custom event
audit.log_event(
    event_type="template_discovery",
    data={
        "pattern": "User {name} logged in",
        "confidence": 0.95,
        "coverage": 0.15
    },
    metadata={
        "node_id": "node-01",
        "version": "2.0.0"
    }
)
```

### Performance Monitoring

```python
import time

start_time = time.time()
results = compressor.batch_compress(messages)
duration = time.time() - start_time

audit.log_performance(
    operation="batch_compression",
    duration=duration,
    throughput=len(messages) / duration,
    metadata={
        "message_count": len(messages),
        "average_size": sum(len(m) for m in messages) / len(messages),
        "compression_method": "adaptive"
    }
)
```

### Error Tracking

```python
try:
    result = compressor.compress_large_file(file_path)
except CompressionError as e:
    audit.log_error(
        error_type="compression_failure",
        error_message=str(e),
        context={
            "file_path": file_path,
            "file_size": os.path.getsize(file_path),
            "error_code": e.code,
            "compression_level": "maximum"
        }
    )
```

### Event Querying

```python
from datetime import datetime, timedelta

# Query last 24 hours
end_date = datetime.now()
start_date = end_date - timedelta(days=1)

# Find compression errors
errors = audit.query_events(
    start_date=start_date,
    end_date=end_date,
    filters={
        "event_type": "error",
        "data.error_type": "compression_failure"
    }
)

print(f"Found {len(errors)} compression errors")
for error in errors:
    print(f"  {error.timestamp}: {error.data['error_message']}")
```

### Real-time Monitoring

```python
# Get current metrics
metrics = audit.get_metrics(time_range="1h")

print("Audit Service Metrics (1h):")
print(f"  Total events: {metrics.total_events}")
print(f"  Events/sec: {metrics.events_per_second:.2f}")
print(f"  Storage used: {metrics.storage_used_gb:.2f} GB")
print(f"  Query latency: {metrics.query_latency_ms:.1f} ms")
print(f"  Error rate: {metrics.error_rate:.2%}")
print(f"  Compliance score: {metrics.compliance_score:.1%}")
```

## Distributed Architecture

### Service Nodes

```python
# Multiple audit nodes for redundancy
audit_nodes = [
    AuditService("https://audit1.aura.com", api_key=key1),
    AuditService("https://audit2.aura.com", api_key=key2),
    AuditService("https://audit3.aura.com", api_key=key3)
]

# Log to all nodes
for node in audit_nodes:
    node.log_event(event_type, data, metadata)
```

### Load Balancing

```python
class LoadBalancedAuditService:
    def __init__(self, services: List[AuditService]):
        self.services = services
        self.current = 0

    def log_event(self, event_type, data, metadata=None):
        # Round-robin load balancing
        service = self.services[self.current]
        self.current = (self.current + 1) % len(self.services)

        return service.log_event(event_type, data, metadata)
```

### Failover Handling

```python
class FailoverAuditService:
    def __init__(self, primary: AuditService, secondary: AuditService):
        self.primary = primary
        self.secondary = secondary

    def log_event(self, event_type, data, metadata=None):
        try:
            return self.primary.log_event(event_type, data, metadata)
        except ServiceUnavailableError:
            logger.warning("Primary audit service unavailable, using secondary")
            return self.secondary.log_event(event_type, data, metadata)
```

## Buffering and Reliability

### Event Buffering

```python
# Configure buffering for reliability
audit = AuditService(
    enable_buffering=True,
    buffer_size=5000,  # Buffer up to 5000 events
    flush_interval=60   # Flush every 60 seconds
)

# Events are buffered locally if service is unavailable
# Automatic retry with exponential backoff
```

### Reliability Features

```python
# Automatic retry configuration
audit.configure_retry(
    max_retries=3,
    initial_delay=1.0,
    max_delay=60.0,
    backoff_factor=2.0
)

# Circuit breaker pattern
audit.enable_circuit_breaker(
    failure_threshold=5,    # Open after 5 failures
    recovery_timeout=300    # Try to recover after 5 minutes
)

# Data integrity verification
audit.enable_integrity_check(
    algorithm="SHA-256",
    include_metadata=True
)
```

## Security and Compliance

### Authentication

```python
# API key authentication
audit = AuditService(
    service_url="https://audit.aura.com",
    api_key=os.getenv("AUDIT_API_KEY")
)

# OAuth2 authentication
audit.configure_oauth2(
    client_id="aura-client",
    client_secret=os.getenv("AURA_OAUTH_CLIENT_SECRET"),
    token_url="https://auth.aura.com/oauth2/token"
)

# Mutual TLS
audit.configure_mtls(
    cert_file="/path/to/client.crt",
    key_file="/path/to/client.key",
    ca_file="/path/to/ca.crt"
)
```

### Data Encryption

```python
# Enable end-to-end encryption
audit.enable_encryption(
    key_provider="aws-kms",
    key_id="alias/aura-audit-key",
    algorithm="AES-256-GCM"
)

# Field-level encryption for sensitive data
audit.configure_field_encryption({
    "user_id": "encrypt",
    "ip_address": "encrypt",
    "personal_data": "encrypt"
})
```

### Compliance Integration

```python
# GDPR compliance
audit.configure_compliance(
    standard="gdpr",
    data_retention_days=2555,  # 7 years
    anonymize_pii=True,
    consent_required=True
)

# HIPAA compliance
audit.configure_compliance(
    standard="hipaa",
    data_retention_days=2555,
    phi_encryption=True,
    audit_trail_required=True
)

# SOC2 compliance
audit.configure_compliance(
    standard="soc2",
    data_retention_days=1825,  # 5 years
    access_logging=True,
    integrity_checks=True
)
```

## Performance Optimization

### Batch Operations

```python
# Batch log multiple events
events = []

for i in range(1000):
    events.append({
        "event_type": "compression",
        "data": {
            "operation": f"compress_{i}",
            "original_size": 1024,
            "compressed_size": 256,
            "method": "brc"
        }
    })

# Single batch request
audit.log_batch(events)
```

### Asynchronous Logging

```python
import asyncio

async def log_async(audit: AuditService, events):
    tasks = []
    for event in events:
        task = asyncio.create_task(
            audit.log_event_async(**event)
        )
        tasks.append(task)

    await asyncio.gather(*tasks)

# Non-blocking logging
asyncio.run(log_async(audit, events))
```

### Connection Pooling

```python
# Configure HTTP connection pooling
audit.configure_http_client(
    max_connections=20,
    max_keepalive_connections=10,
    keepalive_expiry=30.0
)

# DNS caching and connection reuse
audit.enable_connection_reuse(
    dns_cache_ttl=300,  # 5 minutes
    connection_pool_size=50
)
```

## Monitoring and Alerting

### Health Checks

```python
# Service health check
health = audit.health_check()

print("Audit Service Health:")
print(f"  Status: {health['status']}")
print(f"  Response time: {health['response_time_ms']} ms")
print(f"  Queue size: {health['queue_size']}")
print(f"  Error count: {health['error_count']}")

if health['status'] != 'healthy':
    alert_system.send_alert("Audit service unhealthy", health)
```

### Metrics Collection

```python
# Prometheus metrics export
from prometheus_client import Gauge, Counter, Histogram

audit_events_total = Counter('audit_events_total', 'Total audit events')
audit_request_duration = Histogram('audit_request_duration_seconds', 'Request duration')

def record_metrics():
    metrics = audit.get_metrics()

    audit_events_total.inc(metrics.total_events)
    # Record latency percentiles
    audit_request_duration.observe(metrics.query_latency_ms / 1000)
```

### Alert Conditions

```python
# Define alert thresholds
alerts = {
    "high_error_rate": {
        "threshold": 0.05,  # 5% error rate
        "condition": lambda m: m.error_rate > 0.05
    },
    "high_latency": {
        "threshold": 5000,  # 5 seconds
        "condition": lambda m: m.query_latency_ms > 5000
    },
    "storage_full": {
        "threshold": 0.9,  # 90% full
        "condition": lambda m: m.storage_used_gb / m.storage_total_gb > 0.9
    }
}

# Check and alert
metrics = audit.get_metrics()
for alert_name, config in alerts.items():
    if config["condition"](metrics):
        alert_system.send_alert(
            f"Audit service {alert_name}",
            f"Threshold exceeded: {config['threshold']}"
        )
```

## Integration Patterns

### With Compression Engine

```python
from aura_compression.compression_engine import CompressionEngine

class AuditedCompressionEngine(CompressionEngine):
    def __init__(self, audit_service: AuditService):
        super().__init__()
        self.audit = audit_service

    def compress(self, data: bytes) -> bytes:
        start_time = time.time()
        try:
            result = super().compress(data)
            duration = time.time() - start_time

            # Log successful compression
            self.audit.log_compression(
                operation="compress",
                original_size=len(data),
                compressed_size=len(result),
                method=self.get_method_name()
            )

            self.audit.log_performance(
                operation="compression",
                duration=duration,
                throughput=len(data) / duration
            )

            return result

        except Exception as e:
            # Log compression failure
            self.audit.log_error(
                error_type="compression_error",
                error_message=str(e),
                context={"data_size": len(data)}
            )
            raise
```

### With Web Frameworks

```python
# FastAPI middleware
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

class AuditMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, audit_service: AuditService):
        super().__init__(app)
        self.audit = audit_service

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        # Extract request info
        user_id = request.headers.get("X-User-ID")
        session_id = request.headers.get("X-Session-ID")

        response = await call_next(request)
        duration = time.time() - start_time

        # Log API request
        await self.audit.log_event_async(
            event_type="api_request",
            data={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration": duration,
                "response_size": len(response.body) if hasattr(response, 'body') else 0
            },
            metadata={
                "user_id": user_id,
                "session_id": session_id,
                "user_agent": request.headers.get("User-Agent"),
                "ip_address": request.client.host
            }
        )

        return response
```

### With Message Queues

```python
# Kafka integration
from kafka import KafkaConsumer, KafkaProducer

class KafkaAuditBridge:
    def __init__(self, audit_service: AuditService, kafka_config):
        self.audit = audit_service
        self.producer = KafkaProducer(**kafka_config)
        self.consumer = KafkaConsumer('audit-events', **kafka_config)

    def forward_to_audit(self, kafka_message):
        """Forward Kafka messages to audit service"""
        event = json.loads(kafka_message.value)

        self.audit.log_event(
            event_type=event['type'],
            data=event['data'],
            metadata=event.get('metadata', {})
        )

    def forward_to_kafka(self, audit_event):
        """Forward audit events to Kafka"""
        kafka_message = {
            'event_id': audit_event.event_id,
            'timestamp': audit_event.timestamp.isoformat(),
            'type': audit_event.event_type,
            'data': audit_event.data,
            'metadata': audit_event.metadata
        }

        self.producer.send('audit-events', json.dumps(kafka_message))
```

## Configuration Management

### Environment Configuration

```bash
export AUDIT_SERVICE_URL="https://audit.aura.company.com"
export AUDIT_API_KEY="your-secure-api-key"
export AUDIT_BUFFER_SIZE="2000"
export AUDIT_FLUSH_INTERVAL="45"
export AUDIT_ENABLE_ENCRYPTION="true"
```

### Programmatic Configuration

```python
from aura_compression.audit_service import AuditServiceConfig

config = AuditServiceConfig(
    service_url="https://audit.aura.com",
    authentication=APIKeyAuth(api_key="key"),
    buffering=BufferConfig(
        enabled=True,
        size=1000,
        flush_interval=30
    ),
    security=SecurityConfig(
        encryption=EncryptionConfig(
            enabled=True,
            algorithm="AES-256-GCM"
        ),
        compliance=ComplianceConfig(
            standard="gdpr",
            retention_days=2555
        )
    ),
    performance=PerformanceConfig(
        max_connections=20,
        timeout_seconds=30,
        retry_attempts=3
    )
)

audit = AuditService(config)
```

## Troubleshooting

### Common Issues

**Connection failures:**
- Check service URL and network connectivity
- Verify API key authentication
- Check firewall and proxy settings

**High latency:**
- Enable buffering and batch operations
- Check network latency to service
- Monitor service performance metrics

**Data loss:**
- Ensure buffering is enabled
- Check buffer flush intervals
- Verify service availability

**Authentication errors:**
- Validate API key format and permissions
- Check token expiration
- Verify OAuth2 configuration

### Debug and Diagnostics

```python
# Enable debug logging
import logging
logging.getLogger('aura_compression.audit_service').setLevel(logging.DEBUG)

# Test service connectivity
test_result = audit.test_connection()
print(f"Service reachable: {test_result['reachable']}")
print(f"Response time: {test_result['response_time_ms']} ms")

# Check buffer status
buffer_status = audit.get_buffer_status()
print(f"Buffer size: {buffer_status['current_size']}")
print(f"Flush pending: {buffer_status['pending_flush']}")

# Validate configuration
validation = audit.validate_configuration()
if not validation['valid']:
    print("Configuration errors:")
    for error in validation['errors']:
        print(f"  - {error}")
```

## Dependencies

- `requests`: HTTP client for service communication
- `aiohttp`: Asynchronous HTTP client
- `cryptography`: Data encryption and integrity
- `pydantic`: Configuration validation
- `structlog`: Structured logging
- `backoff`: Retry logic with exponential backoff
- `prometheus_client`: Metrics collection
- `kafka-python`: Message queue integration

## Best Practices

### Reliability

1. **Always enable buffering** for production deployments
2. **Configure multiple service endpoints** for redundancy
3. **Implement circuit breaker patterns** for fault tolerance
4. **Use exponential backoff** for retry logic

### Security

1. **Use HTTPS** for all service communications
2. **Enable end-to-end encryption** for sensitive data
3. **Implement proper authentication** and authorization
4. **Regularly rotate API keys** and certificates

### Performance

1. **Batch events** when possible to reduce network overhead
2. **Use asynchronous logging** to avoid blocking operations
3. **Configure appropriate timeouts** and connection limits
4. **Monitor and optimize** query patterns

### Compliance

1. **Configure appropriate retention** periods per regulation
2. **Enable data anonymization** for PII
3. **Implement audit trails** for all data access
4. **Regular compliance audits** and reporting
