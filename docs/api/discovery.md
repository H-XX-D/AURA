# Template Discovery API Reference

## Overview

The `discovery.py` module provides automatic template discovery from production traffic, enabling the system to learn and create new compression templates from real-world message patterns.

## Classes

### TemplateDiscoveryEngine

Automatic template discovery and pattern recognition.

#### Constructor

```python
TemplateDiscoveryEngine(
    min_frequency: int = 5,
    min_confidence: float = 0.8,
    max_template_length: int = 200,
    min_message_count: int = 100
)
```

**Parameters:**
- `min_frequency`: Minimum pattern frequency to consider (default: 5)
- `min_confidence`: Minimum confidence score for templates (default: 0.8)
- `max_template_length`: Maximum template length in characters (default: 200)
- `min_message_count`: Minimum messages needed for discovery (default: 100)

## Methods

### analyze_messages(messages)

Analyze a collection of messages for template patterns.

```python
def analyze_messages(self, messages: List[str]) -> List[DiscoveredTemplate]:
```

**Parameters:**
- `messages`: List of message strings to analyze

**Returns:**
- `List[DiscoveredTemplate]`: List of discovered template candidates

### discover_templates(messages)

Main discovery method that finds and validates templates.

```python
def discover_templates(self, messages: List[str]) -> List[TemplateCandidate]:
```

**Parameters:**
- `messages`: Messages to analyze for patterns

**Returns:**
- `List[TemplateCandidate]`: Validated template candidates

### extract_patterns(messages)

Extract frequent patterns from messages.

```python
def extract_patterns(self, messages: List[str]) -> List[Pattern]:
```

**Parameters:**
- `messages`: Messages to extract patterns from

**Returns:**
- `List[Pattern]`: Extracted patterns with frequency information

### cluster_similar_messages(messages)

Cluster messages by similarity for template creation.

```python
def cluster_similar_messages(self, messages: List[str]) -> List[MessageCluster]:
```

**Parameters:**
- `messages`: Messages to cluster

**Returns:**
- `List[MessageCluster]`: Clustered message groups

### validate_template(template, messages)

Validate a template against a message set.

```python
def validate_template(self, template: str, messages: List[str]) -> TemplateValidation:
```

**Parameters:**
- `template`: Template pattern to validate
- `messages`: Messages to validate against

**Returns:**
- `TemplateValidation`: Validation results with metrics

## Discovery Algorithm

### Step 1: Pattern Extraction

```python
# Extract n-grams and frequent patterns
patterns = discovery.extract_patterns(messages)

# Find common substrings
for length in range(10, max_template_length):
    ngrams = extract_ngrams(messages, length)
    frequent_patterns = filter_by_frequency(ngrams, min_frequency)
```

### Step 2: Message Clustering

```python
# Group similar messages using edit distance
clusters = discovery.cluster_similar_messages(messages)

# Clustering criteria:
# - Edit distance < threshold
# - Common substring ratio > 0.6
# - Message length similarity > 0.8
```

### Step 3: Template Generation

```python
# Create templates from clusters
for cluster in clusters:
    if len(cluster.messages) >= min_cluster_size:
        template = generate_template_from_cluster(cluster)
        validated = discovery.validate_template(template, cluster.messages)
        if validated.confidence >= min_confidence:
            candidates.append(validated)
```

### Step 4: Template Validation

```python
# Validate compression benefit and accuracy
validation = discovery.validate_template(template, messages)

# Validation metrics:
# - Coverage: % of messages matching template
# - Compression ratio: Average bytes saved
# - Confidence: Template accuracy score
# - Specificity: Template uniqueness
```

## Usage Examples

### Basic Template Discovery

```python
from aura_compression.discovery import TemplateDiscoveryEngine

# Initialize discovery engine
discovery = TemplateDiscoveryEngine(
    min_frequency=3,
    min_confidence=0.85,
    max_template_length=150
)

# Analyze production messages
messages = [
    "Error: Connection timeout after 30 seconds",
    "Error: Connection timeout after 60 seconds",
    "Error: Connection timeout after 120 seconds",
    "User login failed: invalid password",
    "User login failed: account locked",
    # ... more messages
]

# Discover templates
templates = discovery.discover_templates(messages)

print(f"Discovered {len(templates)} templates:")
for template in templates:
    print(f"  Pattern: {template.pattern}")
    print(f"  Coverage: {template.coverage:.1%}")
    print(f"  Compression ratio: {template.compression_ratio:.2f}x")
```

### Advanced Discovery with Validation

```python
# Extract raw patterns first
patterns = discovery.extract_patterns(messages)

print("Frequent patterns:")
for pattern in patterns[:10]:  # Top 10
    print(f"  '{pattern.text}': {pattern.frequency} occurrences")

# Cluster messages
clusters = discovery.cluster_similar_messages(messages)

print(f"Found {len(clusters)} message clusters")
for i, cluster in enumerate(clusters):
    print(f"  Cluster {i}: {len(cluster.messages)} messages")
    print(f"    Sample: {cluster.sample_message[:50]}...")

# Validate specific template
template = "Error: Connection timeout after {0} seconds"
validation = discovery.validate_template(template, messages)

print(f"Template validation:")
print(f"  Coverage: {validation.coverage:.1%}")
print(f"  Average compression: {validation.avg_compression:.2f}x")
print(f"  Confidence: {validation.confidence:.3f}")
```

### Integration with Template Library

```python
from aura_compression.templates import TemplateLibrary

# Initialize template library
library = TemplateLibrary()

# Add discovered templates
for template in discovered_templates:
    if template.confidence > 0.9:  # High confidence only
        template_id = library.add_template(template.pattern)
        print(f"Added template {template_id}: {template.pattern}")
```

## Discovery Performance

### Time Complexity

| Operation | Complexity | Typical Time |
|-----------|------------|---------------|
| Pattern extraction | O(n×m) | 100ms - 2s |
| Message clustering | O(n²) | 500ms - 10s |
| Template validation | O(n×k) | 50ms - 1s |
| Full discovery | O(n²) | 1-30s |

Where:
- n = number of messages
- m = average message length
- k = number of template candidates

### Memory Usage

- **Pattern storage**: ~50MB for 10K messages
- **Cluster storage**: ~100MB for large datasets
- **Template validation**: ~10MB temporary

### Scalability Recommendations

```python
# For large datasets (>10K messages)
discovery = TemplateDiscoveryEngine(
    min_message_count=1000,  # Require more messages
    max_template_length=100,  # Shorter templates
    min_frequency=10         # Higher frequency threshold
)

# Process in batches
batch_size = 5000
for i in range(0, len(messages), batch_size):
    batch = messages[i:i+batch_size]
    batch_templates = discovery.discover_templates(batch)
    # Process batch results...
```

## Template Quality Metrics

### Coverage
```python
coverage = len(matching_messages) / len(total_messages)
# Ideal: > 5% coverage for worthwhile templates
```

### Compression Ratio
```python
avg_ratio = sum(msg.compression_ratio for msg in matching_messages) / len(matching_messages)
# Ideal: > 2.0x compression ratio improvement
```

### Confidence Score
```python
confidence = (coverage * compression_benefit) / (1 + ambiguity_penalty)
# Range: 0.0 - 1.0
# Ideal: > 0.8 for production templates
```

### Specificity
```python
specificity = 1 - (overlapping_templates / total_templates)
# Measures template uniqueness
# Ideal: > 0.7 to avoid conflicts
```

## Error Handling

Discovery provides robust error handling:

```python
try:
    templates = discovery.discover_templates(messages)
except DiscoveryError as e:
    logger.error(f"Template discovery failed: {e}")
    # Continue with existing templates
except ValidationError as e:
    logger.warning(f"Template validation failed: {e}")
    # Skip invalid templates
```

## Integration Points

### With Compression Engine

```python
# Automatic template integration
engine = CompressionEngine(template_library=library)

# Discovery runs periodically
def update_templates():
    new_messages = collect_recent_messages()
    discovered = discovery.discover_templates(new_messages)

    for template in discovered:
        if template.confidence > 0.85:
            library.add_template(template.pattern)

# Schedule periodic discovery
scheduler.add_job(update_templates, 'interval', hours=24)
```

### With Audit System

```python
# Templates discovered from audit logs
audit_messages = audit_system.get_recent_messages()

discovered = discovery.discover_templates(audit_messages)

# Log template discovery
for template in discovered:
    audit_system.log_event('template_discovered', {
        'pattern': template.pattern,
        'coverage': template.coverage,
        'confidence': template.confidence
    })
```

## Dependencies

- `collections`: Frequency counting
- `difflib`: Sequence matching for clustering
- `re`: Regular expressions for pattern extraction
- `statistics`: Statistical validation
- `typing`: Type hints

## Configuration Tuning

### For Different Use Cases

```python
# High-frequency, short templates (chat apps)
chat_discovery = TemplateDiscoveryEngine(
    min_frequency=10,
    max_template_length=100,
    min_confidence=0.75
)

# Low-frequency, long templates (logs)
log_discovery = TemplateDiscoveryEngine(
    min_frequency=3,
    max_template_length=500,
    min_confidence=0.9
)

# Real-time discovery (streaming)
streaming_discovery = TemplateDiscoveryEngine(
    min_message_count=50,  # Faster discovery
    min_frequency=5,
    max_template_length=200
)
```

## Monitoring and Metrics

### Discovery Statistics

```python
stats = discovery.get_discovery_stats()

print("Discovery statistics:")
print(f"  Messages processed: {stats['messages_processed']}")
print(f"  Patterns found: {stats['patterns_found']}")
print(f"  Templates validated: {stats['templates_validated']}")
print(f"  Templates accepted: {stats['templates_accepted']}")
print(f"  Average processing time: {stats['avg_processing_time']}ms")
```

### Performance Monitoring

```python
# Monitor discovery performance
start_time = time.time()
templates = discovery.discover_templates(messages)
duration = time.time() - start_time

if duration > 30:  # Too slow
    logger.warning(f"Discovery took {duration:.1f}s, consider optimization")
```

## Troubleshooting

### Common Issues

**No templates discovered:**
- Check message volume (need > 100 messages)
- Verify message similarity (need repeated patterns)
- Adjust frequency threshold

**Poor template quality:**
- Increase confidence threshold
- Check message preprocessing
- Validate pattern extraction

**Performance issues:**
- Reduce max_template_length
- Increase min_frequency
- Process in smaller batches

**Memory issues:**
- Reduce message batch size
- Clear intermediate results
- Use streaming processing for large datasets