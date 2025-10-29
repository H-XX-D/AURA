# AURA Compression Test Framework

A comprehensive testing framework for the AURA compression system with unit tests, benchmarks, integration tests, and performance monitoring.

## Overview

This test framework provides:

- **Unit Tests**: Individual component testing
- **Integration Tests**: End-to-end workflow testing
- **Benchmarks**: Performance measurements and regression detection
- **Data Generators**: Realistic test data for various scenarios
- **Test Runner**: Unified execution of all test suites

## Directory Structure

```
tests/
├── unit/                          # Unit tests for individual components
│   └── test_compressor.py        # Core compressor tests
├── integration/                   # Integration and end-to-end tests
│   └── test_end_to_end.py        # Full workflow tests
├── performance/                   # Performance test results (auto-generated)
├── test_data_generator.py         # Test data generators
├── test_framework.py             # Benchmark framework
├── test_runner.py                # Main test runner
└── test_*.py                     # Legacy test files
```

## Quick Start

### Run All Tests
```bash
# Activate virtual environment (if using one)
source venv/bin/activate

# Run complete test suite
python test_runner.py --all

# Run with custom benchmark iterations
python test_runner.py --all --iterations 50
```

### Run Specific Test Types
```bash
# Unit tests only
python test_runner.py --unit

# Benchmarks only
python test_runner.py --benchmark --iterations 20

# Integration tests only
python test_runner.py --integration

# Comprehensive data tests
python test_runner.py --data
```

### Run Benchmarks Separately
```bash
# Run benchmark framework directly
python test_framework.py --benchmark --iterations 10
```

## Test Components

### Unit Tests (`tests/unit/`)

Test individual components in isolation:

- **Compressor Tests**: Core compression/decompression functionality
- **Data Integrity**: Round-trip verification
- **Error Handling**: Invalid input handling
- **Unicode Support**: International character handling

### Integration Tests (`tests/integration/`)

Test component interactions and workflows:

- **End-to-End Compression**: Complete compression pipelines
- **API Workflows**: Realistic API response compression
- **WebSocket Messages**: Real-time message compression
- **Batch Processing**: Multiple message handling

### Benchmarks (`test_framework.py`)

Performance measurements:

- **Compression Speed**: MB/s throughput
- **Compression Ratio**: Size reduction percentage
- **Memory Usage**: Peak memory consumption
- **Latency**: Response time percentiles

### Data Generators (`test_data_generator.py`)

Generate realistic test data:

- **API Responses**: JSON API data
- **Log Entries**: Server log messages
- **Chat Messages**: Real-time chat data
- **Structured Data**: Database records
- **Random Text**: Variable-length text

## Performance Monitoring

The framework includes automatic performance regression detection:

- **Baseline Tracking**: Stores performance baselines in `performance_baseline.json`
- **Regression Alerts**: Detects significant performance changes
- **Improvement Tracking**: Identifies performance improvements
- **Historical Comparison**: Compares against previous runs

## Configuration

### Benchmark Configuration

```python
# In test_framework.py
class CompressorBenchmark:
    def __init__(self):
        self.test_data = [
            # Customize test data
            TestDataGenerator.generate_api_response('small'),
            TestDataGenerator.generate_log_entry('large'),
            # Add custom test cases
        ]
```

### Performance Thresholds

```python
# In test_data_generator.py
baseline.update_baseline("compression", "speed_mbps", value, threshold=0.1)  # 10% threshold
```

## Output Files

- `benchmark_results.json`: Detailed benchmark metrics
- `test_results.json`: Complete test suite results
- `performance_baseline.json`: Performance baselines for regression detection

## Example Output

```
🚀 AURA Compression - Complete Test Suite
============================================================

🧪 Running Unit Tests
==================================================
Running tests/unit/test_compressor.py...
  ✅ tests/unit/test_compressor.py passed

🔗 Running Integration Tests
==================================================
Running tests/integration/test_end_to_end.py...
  ✅ tests/integration/test_end_to_end.py passed

📊 Running Benchmarks (10 iterations)
==================================================
Running compressor benchmark...
  ✅ compressor: 9 metrics collected
  🔍 Checking for performance regressions...
  ✅ No performance regressions detected

📋 Running Comprehensive Data Tests
==================================================
Testing api_responses (50 messages)...
  Success rate: 100.0%
...
  Overall success rate: 100.0%

================================================================================
# AURA Compression Test Suite Report
Generated: 2025-10-27 22:45:03

## Overall Status
- Unit Tests: ✅ PASS
- Integration Tests: ✅ PASS
- Benchmarks: ✅ PASS
- Data Tests: ✅ PASS
================================================================================

🎉 All tests passed successfully!
```

## Benchmark Metrics

The framework measures:

| Metric | Description | Unit |
|--------|-------------|------|
| `compression_time_ms` | Time to compress data | milliseconds |
| `compression_ratio` | Compressed/original size | ratio (e.g., 0.8 = 80%) |
| `compression_speed_mbps` | Compression throughput | MB/s |
| `decompression_speed_mbps` | Decompression throughput | MB/s |
| `memory_usage_mb` | Peak memory usage | MB |
| `latency_ms` | End-to-end latency | milliseconds |

## Extending the Framework

### Adding New Unit Tests

1. Create `tests/unit/test_your_component.py`
2. Inherit from `unittest.TestCase`
3. Add test methods following the pattern `test_*`

### Adding New Benchmarks

1. Create a new benchmark class inheriting from `BenchmarkTest`
2. Implement `setup()`, `run()`, and `teardown()` methods
3. Add to `TestRunner.benchmarks` dictionary

### Adding New Test Data

1. Extend `TestDataGenerator` with new static methods
2. Add to `generate_compression_test_suite()` for automatic inclusion

## CI/CD Integration

Add to your CI pipeline:

```yaml
# GitHub Actions example
- name: Run AURA Tests
  run: |
    source venv/bin/activate
    python test_runner.py --all --iterations 20

- name: Check Performance Regression
  run: |
    # Check if performance_checks show regressions
    python -c "
    import json
    with open('test_results.json') as f:
        results = json.load(f)
    regressions = results['performance_checks']['regressions']
    if regressions:
        print(f'🚨 Performance regressions detected: {len(regressions)}')
        for reg in regressions:
            print(f'  - {reg[\"test\"]}: {reg[\"message\"]}')
        exit(1)
    else:
        print('✅ No performance regressions')
    "
```

## Troubleshooting

### Import Errors
Ensure the virtual environment is activated and PYTHONPATH is set:
```bash
source venv/bin/activate
PYTHONPATH=/path/to/aura/src/python python test_runner.py
```

### Performance Baselines
Delete `performance_baseline.json` to reset baselines:
```bash
rm performance_baseline.json
```

### Test Failures
Check detailed results in `test_results.json` for specific error messages.

## Contributing

When adding new tests:

1. Follow existing naming conventions
2. Add comprehensive docstrings
3. Include edge cases and error conditions
4. Update this README if adding new functionality
5. Ensure tests pass in CI/CD pipeline
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
python tools/scripts/generate_test_data.py --count 1000
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
