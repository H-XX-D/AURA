# Audit System API Reference

## Overview

The `audit.py` module provides comprehensive audit logging and compliance tracking for AURA compression operations, ensuring GDPR, HIPAA, and SOC2 compliance with detailed operational tracking.

## Classes

### AuditLogger

Main audit logging class.

#### Constructor

```python
AuditLogger(
    log_path: str = "./audit_logs",
    enable_compression: bool = True,
    retention_days: int = 90,
    compliance_level: str = "gdpr"
)
```

**Parameters:**
- `log_path`: Directory for audit logs (default: "./audit_logs")
- `enable_compression`: Compress audit logs (default: True)
- `retention_days`: Log retention period (default: 90)
- `compliance_level`: Compliance standard ("gdpr", "hipaa", "soc2")

## Methods

### log_compression_event(message, compressed_size, original_size, method)

Log a compression operation.

```python
def log_compression_event(
    self,
    message: str,
    compressed_size: int,
    original_size: int,
    method: str
) -> None:
```

**Parameters:**
- `message`: Original message content
- `compressed_size`: Size after compression
- `original_size`: Original message size
- `method`: Compression method used

### log_decompression_event(compressed_data, decompressed_size, method)

Log a decompression operation.

```python
def log_decompression_event(
    self,
    compressed_data: bytes,
    decompressed_size: int,
    method: str
) -> None:
```

**Parameters:**
- `compressed_data`: Compressed data
- `decompressed_size`: Size after decompression
- `method`: Decompression method used

### log_template_discovery(pattern, confidence, coverage)

Log template discovery events.

```python
def log_template_discovery(
    self,
    pattern: str,
    confidence: float,
    coverage: float
) -> None:
```

**Parameters:**
- `pattern`: Discovered template pattern
- `confidence`: Template confidence score
- `coverage`: Template coverage percentage

### log_performance_metrics(operation, duration, throughput)

Log performance metrics.

```python
def log_performance_metrics(
    self,
    operation: str,
    duration: float,
    throughput: float
) -> None:
```

**Parameters:**
- `operation`: Operation name
- `duration`: Operation duration in seconds
- `throughput`: Operations per second

### log_error(error_type, error_message, context)

Log error events.

```python
def log_error(
    self,
    error_type: str,
    error_message: str,
    context: Dict[str, Any]
) -> None:
```

**Parameters:**
- `error_type`: Type of error
- `error_message`: Error description
- `context`: Additional error context

### query_logs(start_date, end_date, filters)

Query audit logs with filters.

```python
def query_logs(
    self,
    start_date: datetime,
    end_date: datetime,
    filters: Dict[str, Any] = None
) -> List[AuditEntry]:
```

**Parameters:**
- `start_date`: Query start date
- `end_date`: Query end date
- `filters`: Additional query filters

**Returns:**
- `List[AuditEntry]`: Matching audit entries

### get_compliance_report(period_days)

Generate compliance report.

```python
def get_compliance_report(self, period_days: int = 30) -> ComplianceReport:
```

**Parameters:**
- `period_days`: Report period in days

**Returns:**
- `ComplianceReport`: Compliance status report

### rotate_logs()

Rotate audit logs based on retention policy.

```python
def rotate_logs(self) -> None:
```

## AuditEntry Class

```python
@dataclass
class AuditEntry:
    timestamp: datetime
    event_type: str
    user_id: Optional[str]
    session_id: Optional[str]
    operation: str
    data_size: int
    compression_ratio: float
    method: str
    ip_address: Optional[str]
    user_agent: Optional[str]
    metadata: Dict[str, Any]
```

## ComplianceReport Class

```python
@dataclass
class ComplianceReport:
    period_start: datetime
    period_end: datetime
    total_events: int
    compliance_violations: int
    data_processed_gb: float
    average_compression_ratio: float
    audit_coverage: float
    recommendations: List[str]
```

## Usage Examples

### Basic Audit Logging

```python
from aura_compression.audit import AuditLogger

# Initialize audit logger
auditor = AuditLogger(
    log_path="/var/log/aura",
    compliance_level="gdpr",
    retention_days=2555  # 7 years for GDPR
)

# Log compression operations
original_size = len(message)
compressed, method, metadata = compressor.compress(message)
compressed_size = len(compressed)

auditor.log_compression_event(
    message=message,
    compressed_size=compressed_size,
    original_size=original_size,
    method=method
)
```

### Performance Monitoring

```python
import time

start_time = time.time()
result = compressor.compress_large_dataset(dataset)
duration = time.time() - start_time

throughput = len(dataset) / duration  # bytes per second

auditor.log_performance_metrics(
    operation="bulk_compression",
    duration=duration,
    throughput=throughput
)
```

### Error Tracking

```python
try:
    result = compressor.compress(message)
except CompressionError as e:
    auditor.log_error(
        error_type="compression_failure",
        error_message=str(e),
        context={
            "message_length": len(message),
            "compression_method": "hybrid",
            "error_code": e.code
        }
    )
```

### Template Discovery Auditing

```python
from aura_compression.discovery import TemplateDiscoveryEngine

discovery = TemplateDiscoveryEngine()
templates = discovery.discover_templates(messages)

for template in templates:
    auditor.log_template_discovery(
        pattern=template.pattern,
        confidence=template.confidence,
        coverage=template.coverage
    )
```

### Compliance Reporting

```python
# Generate monthly compliance report
report = auditor.get_compliance_report(period_days=30)

print(f"Audit Period: {report.period_start} to {report.period_end}")
print(f"Total Events: {report.total_events}")
print(f"Compliance Violations: {report.compliance_violations}")
print(f"Data Processed: {report.data_processed_gb:.2f} GB")
print(f"Audit Coverage: {report.audit_coverage:.1%}")

if report.recommendations:
    print("Recommendations:")
    for rec in report.recommendations:
        print(f"  - {rec}")
```

### Log Querying

```python
from datetime import datetime, timedelta

# Query last 24 hours
end_date = datetime.now()
start_date = end_date - timedelta(days=1)

# Find compression failures
failures = auditor.query_logs(
    start_date=start_date,
    end_date=end_date,
    filters={
        "event_type": "error",
        "operation": "compression"
    }
)

print(f"Found {len(failures)} compression failures")
for failure in failures:
    print(f"  {failure.timestamp}: {failure.metadata.get('error_message')}")
```

## Compliance Standards

### GDPR Compliance

```python
# GDPR-compliant configuration
auditor = AuditLogger(
    compliance_level="gdpr",
    retention_days=2555,  # 7 years
    enable_compression=False,  # No compression for audit integrity
    log_path="/secure/audit/gdpr"
)

# Required GDPR audit fields
audit_entry = {
    "data_subject_id": user_id,
    "processing_purpose": "data_compression",
    "legal_basis": "contract_performance",
    "data_retention": "7_years",
    "international_transfer": False
}
```

### HIPAA Compliance

```python
# HIPAA-compliant configuration
auditor = AuditLogger(
    compliance_level="hipaa",
    retention_days=2555,  # 7 years minimum
    enable_compression=True,  # Encrypted compression allowed
    log_path="/secure/audit/hipaa"
)

# HIPAA audit requirements
hipaa_audit = {
    "patient_id": patient_id,
    "provider_id": provider_id,
    "access_type": "compression_operation",
    "phi_accessed": True,
    "emergency_access": False
}
```

### SOC2 Compliance

```python
# SOC2-compliant configuration
auditor = AuditLogger(
    compliance_level="soc2",
    retention_days=1825,  # 5 years
    enable_compression=True,
    log_path="/secure/audit/soc2"
)

# SOC2 control objectives
soc2_audit = {
    "control_objective": "data_integrity",
    "trust_service_category": "security",
    "evidence_type": "audit_log",
    "monitoring_frequency": "continuous"
}
```

## Audit Log Format

### JSON Log Entry

```json
{
  "timestamp": "2024-01-15T10:30:45.123Z",
  "event_type": "compression",
  "user_id": "user_12345",
  "session_id": "sess_abc123",
  "operation": "compress_message",
  "data_size": 1024,
  "compression_ratio": 2.5,
  "method": "hybrid_brc",
  "ip_address": "192.0.2.100",
  "user_agent": "AURA-Client/2.0",
  "metadata": {
    "template_used": true,
    "template_id": 42,
    "processing_time_ms": 15
  }
}
```

### Compressed Log Storage

```python
# Enable compressed audit logs
auditor = AuditLogger(
    enable_compression=True,
    compression_method="lz4"  # Fast compression for logs
)

# Logs are automatically compressed and stored
# Decompression happens automatically during queries
```

## Performance Considerations

### Log Rotation Strategy

```python
# Automatic log rotation
auditor.rotate_logs()

# Rotation triggers:
# - Daily rotation at midnight
# - Size-based rotation (> 100MB)
# - Retention-based cleanup (> 90 days)
```

### Indexing for Fast Queries

```python
# Audit logs are indexed by:
# - timestamp (range queries)
# - event_type (exact match)
# - user_id (exact match)
# - operation (exact match)
# - ip_address (CIDR matching)
```

### Batch Logging

```python
# Batch log multiple events
audit_entries = []

for message in messages:
    entry = AuditEntry(
        timestamp=datetime.now(),
        event_type="compression",
        operation="bulk_compress",
        data_size=len(message),
        compression_ratio=2.1,
        method="brc",
        metadata={"batch_id": batch_id}
    )
    audit_entries.append(entry)

auditor.log_batch(audit_entries)
```

## Security Features

### Data Sanitization

```python
# Automatically sanitize sensitive data
auditor.log_compression_event(
    message=message,  # Automatically sanitized
    compressed_size=compressed_size,
    original_size=original_size,
    method=method
)

# Sanitization rules:
# - Remove PII from log messages
# - Hash sensitive identifiers
# - Mask credit card numbers
# - Redact passwords
```

### Integrity Verification

```python
# Verify log integrity
is_valid = auditor.verify_log_integrity(log_file)

if not is_valid:
    auditor.log_error(
        error_type="integrity_violation",
        error_message="Audit log integrity check failed",
        context={"log_file": log_file}
    )
```

### Access Control

```python
# Role-based access to audit logs
auditor.set_access_policy({
    "admin": ["read", "write", "delete"],
    "auditor": ["read"],
    "user": ["read_own"]
})

# Check permissions
if auditor.can_access(user, "read", resource):
    logs = auditor.query_logs(start_date, end_date)
```

## Integration Examples

### With Compression Engine

```python
from aura_compression.compression_engine import CompressionEngine

class AuditedCompressionEngine(CompressionEngine):
    def __init__(self, auditor: AuditLogger):
        super().__init__()
        self.auditor = auditor

    def compress(self, data: bytes) -> bytes:
        start_time = time.time()
        result = super().compress(data)
        duration = time.time() - start_time

        self.auditor.log_compression_event(
            message="",  # Don't log actual data
            compressed_size=len(result),
            original_size=len(data),
            method=self.get_method_name()
        )

        self.auditor.log_performance_metrics(
            operation="compression",
            duration=duration,
            throughput=len(data) / duration
        )

        return result
```

### With Web Framework

```python
# Flask middleware for audit logging
@app.before_request
def audit_request():
    g.request_start = time.time()
    g.user_id = get_current_user_id()
    g.session_id = session.get('session_id')

@app.after_request
def audit_response(response):
    duration = time.time() - g.request_start

    auditor.log_event(
        event_type="api_request",
        user_id=g.user_id,
        session_id=g.session_id,
        operation=request.endpoint,
        data_size=len(response.get_data()),
        metadata={
            "method": request.method,
            "path": request.path,
            "status_code": response.status_code,
            "duration": duration
        }
    )

    return response
```

### With Monitoring Systems

```python
# Export metrics to Prometheus
from prometheus_client import Gauge, Counter

compression_events = Counter('aura_compression_events_total', 'Total compression events')
compression_ratio = Gauge('aura_compression_ratio', 'Average compression ratio')

def export_metrics():
    report = auditor.get_compliance_report(period_days=1)
    compression_events.inc(report.total_events)
    compression_ratio.set(report.average_compression_ratio)
```

## Troubleshooting

### Common Issues

**High log volume:**
- Enable compression: `enable_compression=True`
- Increase retention: `retention_days=30`
- Use sampling for high-frequency events

**Slow queries:**
- Add more specific filters
- Use date ranges effectively
- Consider archiving old logs

**Storage issues:**
- Monitor disk usage
- Configure log rotation
- Use compressed storage

**Compliance violations:**
- Review compliance configuration
- Check data sanitization rules
- Verify retention policies

### Debug Logging

```python
import logging

# Enable audit debug logging
logging.getLogger('aura_compression.audit').setLevel(logging.DEBUG)

# Log all audit operations
auditor.enable_debug_logging()

# Check audit health
health = auditor.get_health_status()
print(f"Audit system healthy: {health['healthy']}")
print(f"Log files: {health['log_files_count']}")
print(f"Total size: {health['total_size_mb']} MB")
```

## Dependencies

- `json`: Log serialization
- `datetime`: Timestamp handling
- `pathlib`: File system operations
- `lz4`: Log compression (optional)
- `cryptography`: Log integrity verification
- `ipaddress`: IP address handling
- `dataclasses`: Data structures

## Configuration

### Environment Variables

```bash
export AURA_AUDIT_LOG_PATH="/var/log/aura"
export AURA_AUDIT_RETENTION_DAYS="90"
export AURA_AUDIT_COMPRESSION="true"
export AURA_AUDIT_COMPLIANCE_LEVEL="gdpr"
```

### Configuration File

```yaml
audit:
  log_path: "/var/log/aura"
  retention_days: 90
  enable_compression: true
  compliance_level: "gdpr"
  security:
    enable_integrity_check: true
    sanitize_sensitive_data: true
  performance:
    max_log_queue_size: 1000
    batch_write_interval: 5
```

## Monitoring and Alerts

### Key Metrics

```python
metrics = auditor.get_metrics()

print("Audit Metrics:")
print(f"  Events per second: {metrics['events_per_second']}")
print(f"  Storage used: {metrics['storage_mb']} MB")
print(f"  Oldest log: {metrics['oldest_log_days']} days")
print(f"  Compliance score: {metrics['compliance_score']:.1%}")
```

### Alert Conditions

```python
# Alert on compliance violations
if report.compliance_violations > 0:
    alert_system.send_alert(
        "Compliance violation detected",
        f"{report.compliance_violations} violations in last 30 days"
    )

# Alert on storage issues
if health['total_size_mb'] > 1000:  # 1GB
    alert_system.send_alert(
        "Audit log storage high",
        f"Total size: {health['total_size_mb']} MB"
    )
```

## Best Practices

### Log Management

1. **Regular Rotation**: Rotate logs daily or when they exceed size limits
2. **Compression**: Enable compression for storage efficiency
3. **Retention**: Configure appropriate retention based on compliance requirements
4. **Backup**: Regularly backup audit logs to secure storage

### Security

1. **Access Control**: Implement role-based access to audit logs
2. **Integrity**: Enable integrity checking for critical logs
3. **Encryption**: Encrypt audit logs at rest and in transit
4. **Monitoring**: Monitor access to audit logs

### Performance

1. **Batch Logging**: Use batch operations for high-frequency events
2. **Async Writing**: Write logs asynchronously to avoid blocking
3. **Indexing**: Ensure proper indexing for query performance
4. **Archiving**: Archive old logs to separate storage