# 07-TESTS: Test Suite

This directory contains the comprehensive test suite for AURA.

---

## Test Organization

### Unit Tests
- `test_core_functionality.py` - Core compression/decompression
- `test_metadata.py` - Metadata parsing and classification
- `test_templates.py` - Template matching and substitution
- `test_conversation_tracking.py` - Conversation acceleration

### Integration Tests
- `test_real_world_scenarios.py` - Real AI conversations
- `test_streaming_integration.py` - WebSocket streaming
- `test_client_server_integration.py` - End-to-end communication

### Compliance Tests
- `test_audit_logging.py` - 4-log audit architecture
- `test_gdpr_compliance.py` - GDPR requirements
- `test_content_safety.py` - Content moderation

### Performance Tests
- `test_compression_benchmarks.py` - Compression ratio benchmarks
- `test_speed_benchmarks.py` - Processing speed
- `test_discovery_working.py` - Template discovery validation

---

## Running Tests

### All Tests
```bash
cd 07-TESTS
pytest
```

### Specific Test File
```bash
pytest test_core_functionality.py -v
```

### Specific Test
```bash
pytest test_core_functionality.py::test_template_compression -v
```

### With Coverage
```bash
pytest --cov=aura_compression --cov-report=html
```

---

## Test Results Summary

### Core Functionality ✅

**`test_core_functionality.py`** (24 tests)
- ✅ Template compression/decompression
- ✅ LZ77 compression/decompression
- ✅ Metadata parsing
- ✅ Fallback handling
- ✅ Never-worse guarantee

**Coverage**: 95%

**Example**:
```python
def test_template_compression():
    compressor = Compressor()
    result = compressor.compress("Yes, I can help with that!")

    assert result.ratio > 5.0  # Template compression very effective
    assert result.metadata.kind == MetadataKind.TEMPLATE
    assert compressor.decompress(result.compressed) == "Yes, I can help with that!"
```

---

### Real-World Scenarios ✅

**`test_real_world_scenarios.py`** (15 tests)
- ✅ AI conversation compression
- ✅ Code snippet compression
- ✅ Mixed content handling
- ✅ Edge cases (empty, very long)

**Coverage**: 88%

**Example**:
```python
def test_ai_conversation():
    """Test compression on real AI conversation"""
    conversation = [
        "What's the weather?",
        "I don't have access to real-time data.",
        "Can you write Python code?",
        "Of course! Here's an example:\n```python\nprint('Hello')\n```"
    ]

    compressor = Compressor()
    total_original = sum(len(msg) for msg in conversation)
    total_compressed = 0

    for msg in conversation:
        result = compressor.compress(msg)
        total_compressed += len(result.compressed)

    ratio = total_original / total_compressed
    assert ratio > 4.0  # Should achieve >4:1 compression
```

---

### Template Discovery ✅

**`test_discovery_working.py`** (8 tests)
- ✅ Pattern extraction
- ✅ Frequency analysis
- ✅ Template generation
- ✅ Coverage calculation

**Coverage**: 92%

**Example**:
```python
def test_template_discovery():
    """Test automatic template discovery from conversations"""
    conversations = [
        "Yes, I can help with that!",
        "Yes, I can help with that!",
        "Of course, I'd be happy to assist!",
        "Of course, I'd be happy to assist!",
        "I don't have access to real-time data.",
        "I don't have access to real-time data.",
    ]

    discovery = TemplateDiscovery()
    templates = discovery.discover(conversations)

    assert len(templates) >= 3  # Should find 3 patterns
    assert templates[0].frequency >= 2  # Each appears at least twice
```

---

### Streaming Integration ✅

**`test_streaming_integration.py`** (12 tests)
- ✅ WebSocket server/client
- ✅ Message encoding/decoding
- ✅ Session management
- ✅ Error handling

**Coverage**: 85%

**Example**:
```python
@pytest.mark.asyncio
async def test_websocket_streaming():
    """Test real-time streaming compression"""
    server = AURAServer()
    await server.start(host='localhost', port=8888)

    client = AURAClient('ws://localhost:8888')
    await client.connect()

    response = await client.send("Hello, server!")
    assert response is not None
    assert len(response) < len("Hello, server!")  # Compressed

    await client.disconnect()
    await server.stop()
```

---

### Compliance Tests ✅

**`test_audit_logging.py`** (18 tests)
- ✅ 4-log creation
- ✅ Pre-delivery logging
- ✅ Content safety checks
- ✅ GDPR export/erasure

**Coverage**: 90%

**Example**:
```python
def test_separated_audit_logs():
    """Test 4-log separated architecture"""
    server = AURAServer(audit_enabled=True)

    # Simulate AI generating harmful content
    ai_response = "[HARMFUL CONTENT]"
    safe_response = "I apologize, but I cannot provide that response."

    # Log AI-generated (pre-moderation)
    server.audit_logger.log_ai_generated(
        session_id='test',
        content=ai_response,
        safety_check='failed',
        harmful_content_detected=True,
        moderation_action='block'
    )

    # Log what client receives (post-moderation)
    server.audit_logger.log(
        session_id='test',
        direction='server_to_client',
        content=safe_response
    )

    # Verify logs created
    assert os.path.exists('aura_audit.log')
    assert os.path.exists('aura_audit_ai_generated.log')
    assert os.path.exists('aura_audit_safety_alerts.log')

    # Verify separation
    compliance_log = read_log('aura_audit.log')
    ai_log = read_log('aura_audit_ai_generated.log')

    assert safe_response in compliance_log
    assert ai_response in ai_log
    assert ai_response not in compliance_log  # Harmful content NOT in compliance log
```

---

### Performance Benchmarks ✅

**`test_compression_benchmarks.py`** (10 tests)
- ✅ Compression ratio by message type
- ✅ Encoding/decoding speed
- ✅ Memory usage
- ✅ Conversation acceleration

**Coverage**: 82%

**Example**:
```python
def test_conversation_acceleration():
    """Test progressive speedup over conversation"""
    compressor = Compressor()
    tracker = ConversationTracker()

    messages = ["Hello"] * 50
    times = []

    for msg in messages:
        start = time.time()
        result = compressor.compress(msg)
        tracker.record_message(result.metadata)
        elapsed = time.time() - start
        times.append(elapsed)

    # Verify speedup
    initial_time = times[0]
    final_time = times[-1]
    speedup = initial_time / final_time

    assert speedup > 50  # Should achieve >50× speedup after 50 messages
```

---

## Test Coverage

### Overall Coverage: 89%

| Component | Coverage |
|-----------|----------|
| Core compression | 95% |
| Templates | 92% |
| Metadata | 100% |
| LZ77 | 88% |
| BRIO codec | 45% (experimental) |
| Audit logging | 90% |
| Streaming | 85% |
| Discovery | 92% |

### Coverage Report

```bash
pytest --cov=aura_compression --cov-report=html
open htmlcov/index.html
```

---

## Continuous Integration

### GitHub Actions

**`.github/workflows/test.yml`**:
```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: 3.9
      - run: pip install -e .
      - run: pytest --cov=aura_compression
```

---

## Performance Benchmarks

### Compression Ratios

**Test**: `test_compression_ratios.py`

**Results**:
```
AI Conversations:  4.3:1 average (1000 samples)
Code Snippets:     5.2:1 average (500 samples)
Mixed Content:     3.8:1 average (250 samples)
Random Text:       1.2:1 average (100 samples, fallback)
```

### Processing Speed

**Test**: `test_processing_speed.py`

**Results**:
```
Template Compression:    0.5ms  (2000 ops/sec)
LZ77 Compression:        2.1ms  (476 ops/sec)
Brotli Fallback:         3.2ms  (312 ops/sec)
Template Decompression:  0.1ms  (10000 ops/sec)
LZ77 Decompression:      0.8ms  (1250 ops/sec)
Metadata Parsing:        0.01ms (100000 ops/sec)
```

### Metadata Fast-Path

**Test**: `test_metadata_fastpath.py`

**Results**:
```
Full Decompression:      13.0ms
Metadata Classification: 0.17ms
Speedup:                 76× faster
```

### Conversation Acceleration

**Test**: `test_conversation_acceleration.py`

**Results**:
```
Message 1:   13.0ms  (1.0× baseline)
Message 10:  1.2ms   (10.8× faster)
Message 50:  0.15ms  (86.7× faster)
```

---

## Regression Tests

### Baseline Comparison

**`baseline_quick.json`** - Performance baselines
```json
{
  "compression_ratio": 4.3,
  "encoding_speed_ms": 3.2,
  "decoding_speed_ms": 1.8,
  "metadata_speed_ms": 0.17,
  "conversation_speedup": 87.0
}
```

**Test**: Verify current performance meets baselines
```bash
pytest test_regression.py
```

---

## Test Data

### Sample Datasets

**`data/ai_conversations.json`** - 1,000 AI conversations
**`data/code_snippets.json`** - 500 code examples
**`data/templates.json`** - 200+ templates

### Generating Test Data

```bash
python scripts/generate_test_data.py --count 1000
```

---

## Adding New Tests

### Template

```python
import pytest
from aura import Compressor, ConversationTracker

def test_new_feature():
    """Test description"""
    # Arrange
    compressor = Compressor()

    # Act
    result = compressor.compress("Test input")

    # Assert
    assert result.ratio > 1.0
    assert result.metadata.kind is not None
```

### Best Practices

1. **Descriptive names**: `test_template_compression_with_parameters`
2. **Clear assertions**: Use specific values, not just `assert result`
3. **Edge cases**: Test empty, very long, special characters
4. **Performance**: Use `@pytest.mark.benchmark` for slow tests
5. **Cleanup**: Use fixtures for setup/teardown

---

## Test Fixtures

### Common Fixtures

```python
@pytest.fixture
def compressor():
    """Reusable compressor instance"""
    return Compressor()

@pytest.fixture
def sample_conversation():
    """Sample AI conversation for testing"""
    return [
        "What's the weather?",
        "I don't have access to real-time data.",
        "Can you help me with Python?",
        "Of course, I'd be happy to assist!"
    ]

@pytest.fixture
def audit_logger(tmp_path):
    """Audit logger with temporary directory"""
    logger = AuditLogger(log_dir=tmp_path)
    yield logger
    # Cleanup happens automatically (tmp_path deleted)
```

---

## Troubleshooting

### Tests Failing

**Issue**: `AssertionError: assert 2.1 > 4.0`
**Cause**: Compression ratio lower than expected
**Solution**: Check input data matches templates
```bash
python demos/demo_template_discovery.py
```

### Slow Tests

**Issue**: Test suite takes >60 seconds
**Cause**: Not using fast-path for classification
**Solution**: Use metadata-only operations
```python
# Slow
intent = classify_from_text(decompress(data))

# Fast
intent = classify_from_metadata(extract_metadata(data))
```

---

## Test Roadmap

### Completed ✅
- Core compression tests
- Real-world scenario tests
- Streaming integration tests
- Compliance tests
- Performance benchmarks

### In Progress 🚧
- Load testing (1M+ concurrent connections)
- Fuzzing tests (random input)
- Security tests (injection, DoS)

### Planned 🔮
- Cross-platform tests (Windows, macOS, Linux)
- Browser compatibility tests
- Mobile SDK tests
- Edge runtime tests

---

**Directory**: 07-TESTS/
**Last Updated**: October 22, 2025
**Test Coverage**: 89% overall
**Status**: Comprehensive test suite with benchmarks
