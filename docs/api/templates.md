# Template System

Core template library providing pattern matching, formatting, and dynamic template management for binary semantic compression.

## Overview

The template system enables ultra-compact compression by recognizing repetitive patterns in data and replacing them with compact template references. This is particularly effective for AI assistant responses, log messages, and structured data.

## Key Classes

### TemplateMatch
Represents a successful template match with extracted slot values.

```python
@dataclass
class TemplateMatch:
    template_id: int      # Template identifier
    slots: List[str]      # Extracted slot values
    start: Optional[int]  # Match start position (optional)
    end: Optional[int]    # Match end position (optional)
```

### TemplateEntry
Basic template information structure.

```python
@dataclass
class TemplateEntry:
    template_id: int      # Unique template identifier
    pattern: str          # Template pattern with {0}, {1}, etc.
    slot_count: int       # Number of slots in the pattern
```

### TemplateRecord
Complete template record with compiled regex patterns for matching.

```python
@dataclass
class TemplateRecord:
    template_id: int
    pattern: str
    regex: Pattern[str]           # Full match regex
    partial_regex: Pattern[str]   # Partial match regex
    slot_order: List[int]         # Order of slots in pattern
    literal_length: int           # Length of literal text
    anchor_literal: Optional[str] # Anchor literal for fast matching
    anchor_casefold: Optional[str] # Case-folded anchor
```

## TemplateLibrary Class

Main interface for template management and matching.

### Class Signature

```python
class TemplateLibrary:
    def __init__(self,
                 custom_templates: Optional[Dict[int, str]] = None,
                 enable_fast_matching: bool = True,
                 enable_persistent_cache: bool = True,
                 cache_dir: str = ".aura_cache")
```

### Parameters

- **`custom_templates`** *(Optional[Dict[int, str]])*: Additional templates to register
- **`enable_fast_matching`** *(bool, default=True)*: Enable fast matching optimizations
- **`enable_persistent_cache`** *(bool, default=True)*: Enable persistent cache for restarts
- **`cache_dir`** *(str, default=".aura_cache")*: Directory for persistent cache

### Template ID Ranges

```
0-127:   DEFAULT_TEMPLATES    (128 slots - built-in common patterns)
128-191: DYNAMIC_RANGE       (64 slots - discovered at runtime)
192-255: CLIENT_SYNC_RANGE   (64 slots - client-discovered templates)
```

### Default Templates

The library includes 68+ built-in templates covering common AI assistant patterns:

#### Common Responses (0-19)
```python
0: "I don't have access to {0}. {1}"
1: "No"
2: "I don't know"
3: "I'm not sure"
4: "That's correct"
# ... etc
```

#### Questions (60-69)
```python
60: "What {0}?"
61: "Why {0}?"
62: "How {0}?"
63: "When {0}?"
64: "Where {0}?"
# ... etc
```

#### Instructions (70-89)
```python
70: "To {0}, {1}."
71: "To {0}, use {1}."
72: "To {0}, use {1}: `{2}`"
# ... etc
```

## Core Methods

### Template Matching

#### `match(text: str) -> Optional[TemplateMatch]`
Find the best matching template for the given text.

**Parameters:**
- `text` *(str)*: Text to match against templates

**Returns:**
- `TemplateMatch` if a match is found, `None` otherwise

**Example:**
```python
library = TemplateLibrary()
match = library.match("I don't have access to real-time data. Some reason")

if match:
    print(f"Template {match.template_id}: {match.slots}")
    # Output: Template 0: ['real-time data', 'Some reason']
```

#### `find_best_match(text: str) -> Optional[TemplateMatch]`
Find the best matching template using advanced scoring.

**Parameters:**
- `text` *(str)*: Text to find match for

**Returns:**
- Best `TemplateMatch` or `None`

### Template Management

#### `add_template(template_id: int, pattern: str) -> bool`
Add a new template to the library.

**Parameters:**
- `template_id` *(int)*: Unique template identifier
- `pattern` *(str)*: Template pattern with {0}, {1}, etc. placeholders

**Returns:**
- `True` if added successfully, `False` if ID already exists

**Example:**
```python
success = library.add_template(300, "Error: {message} at {timestamp}")
print(f"Template added: {success}")
```

#### `get_template(template_id: int) -> Optional[str]`
Retrieve template pattern by ID.

**Parameters:**
- `template_id` *(int)*: Template identifier

**Returns:**
- Template pattern string or `None` if not found

#### `remove_template(template_id: int) -> bool`
Remove a template from the library.

**Parameters:**
- `template_id` *(int)*: Template identifier to remove

**Returns:**
- `True` if removed, `False` if not found

### Template Formatting

#### `format_template(template_id: int, slots: List[str]) -> str`
Format a template with slot values.

**Parameters:**
- `template_id` *(int)*: Template identifier
- `slots` *(List[str])*: Values for template slots

**Returns:**
- Formatted string with slots filled

**Example:**
```python
text = library.format_template(0, ["real-time data", "some reason"])
print(text)  # "I don't have access to real-time data. some reason"
```

#### `get_entry(template_id: int) -> Optional[TemplateEntry]`
Get detailed template entry information.

**Parameters:**
- `template_id` *(int)*: Template identifier

**Returns:**
- `TemplateEntry` with full template information

### Dynamic Template Management

#### `add_dynamic_template(pattern: str) -> Optional[int]`
Add a template to the dynamic range (128-191).

**Parameters:**
- `pattern` *(str)*: Template pattern

**Returns:**
- Assigned template ID or `None` if no slots available

#### `add_client_sync_template(pattern: str) -> Optional[int]`
Add a template to the client sync range (192-255).

**Parameters:**
- `pattern` *(str)*: Template pattern

**Returns:**
- Assigned template ID or `None` if no slots available

### Performance & Caching

#### `get_cache_stats() -> Dict[str, Any]`
Get cache performance statistics.

**Returns:**
- Dictionary with cache hits, misses, and efficiency metrics

**Example:**
```python
stats = library.get_cache_stats()
print(f"Cache hits: {stats['hits']}")
print(f"Cache misses: {stats['misses']}")
print(f"Hit rate: {stats['hit_rate']:.1%}")
```

#### `clear_cache()`
Clear the match cache.

#### `enable_cache(enable: bool)`
Enable or disable the match cache.

**Parameters:**
- `enable` *(bool)*: Whether to enable caching

### Bulk Operations

#### `bulk_add_templates(templates: Dict[int, str])`
Add multiple templates at once.

**Parameters:**
- `templates` *(Dict[int, str])*: Dictionary of template_id -> pattern

#### `get_all_templates() -> Dict[int, str]`
Get all templates in the library.

**Returns:**
- Dictionary of all template_id -> pattern mappings

## Advanced Features

### Fast Matching Optimization

The library uses multiple optimization techniques for fast template matching:

1. **Length Bucketing**: Templates grouped by pattern length
2. **Pattern Hashing**: Fast pre-filtering using pattern hashes
3. **Anchor Literals**: Quick rejection using unique literal strings
4. **LRU Cache**: Recently matched templates cached for performance

### Persistent Cache

Templates and match results can be persisted across restarts:

```python
# Enable persistent cache
library = TemplateLibrary(
    enable_persistent_cache=True,
    cache_dir="/var/cache/aura"
)

# Cache survives restarts
# Templates are automatically loaded on next startup
```

### Template Discovery Integration

The template library integrates with the discovery system:

```python
from aura_compression.discovery import TemplateDiscoveryEngine

# Discover new templates from traffic
discovery = TemplateDiscoveryEngine()
candidates = discovery.analyze_messages(log_messages)

# Add discovered templates
for candidate in candidates:
    if candidate.confidence > 0.8:  # High confidence only
        template_id = library.add_dynamic_template(candidate.pattern)
        print(f"Added template {template_id}: {candidate.pattern}")
```

## Usage Examples

### Basic Template Matching
```python
from aura_compression.templates import TemplateLibrary

library = TemplateLibrary()

# Match text against templates
text = "What programming language?"
match = library.match(text)

if match:
    print(f"Matched template {match.template_id}")
    print(f"Slots: {match.slots}")
else:
    print("No template match found")
```

### Custom Template Management
```python
# Add custom templates
library.add_template(1000, "User {username} logged in from {ip}")
library.add_template(1001, "Error {code}: {message}")

# Use in compression
from aura_compression import ProductionHybridCompressor

compressor = ProductionHybridCompressor()
compressed, method, metadata = compressor.compress_with_template(
    1000, ["john_doe", "192.0.2.100"]
)
```

### Performance Monitoring
```python
# Monitor cache performance
stats = library.get_cache_stats()
hit_rate = stats['hits'] / (stats['hits'] + stats['misses'])

if hit_rate < 0.5:
    print("Low cache hit rate - consider template optimization")
    # Add more specific templates or adjust cache size
```

### Bulk Template Operations
```python
# Load templates from configuration
custom_templates = {
    2000: "API call to {endpoint} failed with {status_code}",
    2001: "Database query timeout after {seconds} seconds",
    2002: "Cache miss for key {key} in region {region}"
}

library.bulk_add_templates(custom_templates)

# Export all templates
all_templates = library.get_all_templates()
with open('templates_export.json', 'w') as f:
    json.dump(all_templates, f, indent=2)
```

## Performance Characteristics

### Matching Speed
- **Cache Hit**: ~1μs (microsecond)
- **Fast Match**: ~50μs (length + hash filtering)
- **Full Regex Match**: ~200μs (worst case)

### Memory Usage
- **Default Templates**: ~50KB (68 templates)
- **Template Records**: ~100KB (compiled regex patterns)
- **Match Cache**: 1MB LRU cache (configurable)

### Cache Efficiency
- **Hit Rate**: 70-90% for repetitive traffic
- **Memory per Entry**: ~200 bytes
- **Eviction Policy**: LRU (Least Recently Used)

## Error Handling

```python
try:
    match = library.match(text)
    if match:
        formatted = library.format_template(match.template_id, match.slots)
        print(f"Matched and formatted: {formatted}")
except ValueError as e:
    print(f"Template error: {e}")
except KeyError as e:
    print(f"Template not found: {e}")
```

## Integration Points

### With Compression Engine
```python
from aura_compression.compression_engine import CompressionEngine

engine = CompressionEngine(template_library=library)
compressed, metadata = engine.compress_binary_semantic(text, template_match)
```

### With Discovery System
```python
from aura_compression.discovery import TemplateDiscoveryEngine

discovery = TemplateDiscoveryEngine(template_library=library)
# Discovery automatically registers new templates
```

### With Audit System
```python
from aura_compression.audit import AuditLogger

auditor = AuditLogger(template_library=library)
# Audit logs include template resolution for compliance
```

---

**Module**: `aura_compression.templates`  
**Version**: 2.0.0  
**Last Updated**: October 30, 2025