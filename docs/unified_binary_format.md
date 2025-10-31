# Unified Binary Format with Metadata Header

## Motivation

**Problem:** Current format mixes different encodings:
- Binary semantic: custom binary format (11 bytes overhead)
- Auralite: base64-encoded (33% overhead)
- AI semantic: varies
- No consistent metadata for audit logging

**Solution:** Universal binary format with compact metadata header for ALL compression methods.

## Benefits

1. **Audit Compliance**: Every message has metadata (template_id, method, timestamps)
2. **Smaller Headers**: Binary encoding (6-8 bytes vs 11+ bytes)
3. **Fast Routing**: Read metadata without decompressing payload
4. **Unified Parser**: Single codepath for all methods
5. **Version Support**: Built-in format versioning

## Universal Binary Format

```
┌─────────────────────────────────────────────────────────────┐
│                    AURA Binary Message                       │
├─────────────────────────────────────────────────────────────┤
│ Header (6-12 bytes)                                          │
│  ├─ Magic + Version (1 byte)                                │
│  ├─ Flags (1 byte)                                           │
│  ├─ Compression Method (1 byte)                             │
│  ├─ Payload Length (2 bytes, optional)                      │
│  └─ Metadata (0-6 bytes, based on flags)                    │
├─────────────────────────────────────────────────────────────┤
│ Payload (variable)                                           │
│  └─ Compressed data (method-specific encoding)              │
└─────────────────────────────────────────────────────────────┘
```

## Header Design (6-byte minimum)

### Byte 0: Magic + Version
```
Bits 7-4: Magic number (0xA for AURA)
Bits 3-0: Format version (0-15)

Example: 0xA1 = AURA format version 1
```

### Byte 1: Flags
```
Bit 7: Has metadata (0=no, 1=yes)
Bit 6: Has template_id (0=no, 1=yes)
Bit 5: Has timestamp (0=no, 1=yes)
Bit 4: Payload length included (0=no, 1=yes)
Bit 3: Reserved
Bit 2-0: Whitespace variant (000=none, 001=leading space, 010=trailing space, 111=custom)
```

### Byte 2: Compression Method
```
0x00 = BINARY_SEMANTIC
0x01 = AURALITE
0x02 = BRIO
0x04 = AURA_HEAVY
0x20 = AI_SEMANTIC
0xFF = UNCOMPRESSED
```

### Bytes 3-4: Payload Length (optional, if flag bit 4 set)
```
2 bytes, big-endian
Allows up to 65KB payloads
For larger: use extended format
```

### Bytes 5+: Metadata (conditional)
```
If flag bit 6 set: Template ID (2 bytes)
If flag bit 5 set: Timestamp (4 bytes, Unix epoch seconds)
```

## Example Encodings

### Example 1: Binary Semantic, No Metadata (6 bytes header)
```
Message: "How do I create a numpy array?"
Template ID: 62
Slot: "do I create a numpy array"

Header:
  [0xA1] Magic + Version 1
  [0x40] Flags: has_template_id=1
  [0x00] Method: BINARY_SEMANTIC
  [0x00][0x1D] Payload length: 29 bytes
  [0x00][0x3E] Template ID: 62

Payload (29 bytes):
  [0x01] Slot count: 1
  [0x00][0x19] Slot 0 length: 25
  [... 25 bytes ...] "do I create a numpy array"

Total: 6 + 29 = 35 bytes (vs 36 bytes old format)
Savings: 1 byte
```

### Example 2: Auralite, No Metadata (5 bytes header)
```
Message: "What's wrong with this code?"
Compressed payload: [auralite bytes]

Header:
  [0xA1] Magic + Version 1
  [0x10] Flags: payload_length=1
  [0x01] Method: AURALITE
  [0x00][0x1F] Payload length: 31 bytes

Payload (31 bytes):
  [... auralite compressed data ...]

Total: 5 + 31 = 36 bytes
```

### Example 3: Binary Semantic with Audit Metadata (12 bytes header)
```
Message: "How do I create a numpy array?"
Template ID: 62
Timestamp: 1704067200 (2024-01-01 00:00:00)

Header:
  [0xA1] Magic + Version 1
  [0xE0] Flags: has_metadata=1, has_template_id=1, has_timestamp=1
  [0x00] Method: BINARY_SEMANTIC
  [0x00][0x1D] Payload length: 29 bytes
  [0x00][0x3E] Template ID: 62
  [0x65][0x8F][0x0A][0x00] Timestamp: 1704067200

Payload (29 bytes):
  [... same as Example 1 ...]

Total: 12 + 29 = 41 bytes
Overhead for audit: 6 bytes (timestamp + extra flags)
```

## Binary Semantic Payload Format (Optimized)

Since we moved template_id to header, payload is simpler:

```
[slot_count:1][slot_lengths:2n][whitespace_data:*][slot_data:*]
```

### Whitespace Encoding (based on header flags bits 2-0)
```
000 (0): No whitespace
001 (1): Single leading space (implicit, no data)
010 (2): Single trailing space (implicit, no data)
011 (3): Leading + trailing space (implicit, no data)
111 (7): Custom whitespace (read from payload)
```

### Custom Whitespace Format (only when flags bits 2-0 = 111)
```
[ws_flags:1][leading_len:1][trailing_len:1][leading_data:*][trailing_data:*]
```

## Overhead Comparison

| Scenario | Old Format | New Format | Savings |
|----------|------------|------------|---------|
| Binary semantic, no WS | 11 bytes | 6 bytes | 5 bytes |
| Binary semantic + audit | 11 bytes | 12 bytes | -1 byte |
| Auralite | 1 byte | 5 bytes | -4 bytes |
| With common whitespace | 11 bytes | 6 bytes | 5 bytes |
| With custom whitespace | 11+ bytes | 9+ bytes | 2+ bytes |

**Net result:**
- Binary semantic: 5 bytes saved (significant for small messages)
- Other methods: 4 bytes overhead (but gain audit compliance)
- With audit metadata: ~same overhead but gain full traceability

## Audit Compliance

With `has_timestamp` and `has_template_id` flags:
- **Every message** can be logged with metadata
- Template usage tracking for optimization
- Timestamp for performance analysis
- Method selection for strategy tuning
- Zero additional parsing cost

## Implementation Strategy

### Phase 1: Core Format (Current Sprint)
1. Implement unified header encoder/decoder
2. Migrate binary semantic to new format
3. Update compression_engine.py

### Phase 2: Method Migration
1. Wrap Auralite in unified format
2. Wrap AI semantic in unified format
3. Update all compression methods

### Phase 3: Audit Integration
1. Add timestamp generation
2. Add audit logging hooks
3. Update metadata tracking

### Phase 4: Optimization
1. Benchmark header overhead
2. Optimize common case (no metadata)
3. Add header caching for repeated templates

## Code Changes

### Files to Modify

1. **enums.py**
   - Add header constants
   - Add whitespace variant enum
   - Add flag bit masks

2. **compression_engine.py**
   - Add `_encode_unified_header()`
   - Add `_decode_unified_header()`
   - Update `compress_binary_semantic()`
   - Update `decompress_binary_semantic()`

3. **audit.py**
   - Hook into header metadata
   - Log template_id + timestamp + method

4. **metadata.py**
   - Parse unified header for routing
   - Fast-path extraction

## Backward Compatibility

**Version Detection:**
```python
def detect_format_version(data: bytes) -> int:
    if len(data) == 0:
        raise ValueError("Empty data")

    magic = (data[0] & 0xF0) >> 4
    if magic == 0xA:  # AURA magic number
        version = data[0] & 0x0F
        return version
    else:
        return 0  # Legacy format (no magic)
```

**Migration Path:**
- Writer: Always use version 1 (unified format)
- Reader: Support version 0 (legacy) and version 1 (unified)
- Gradual migration over time

## Performance Impact

### Compression
- **Faster**: Single header encoding path
- **Smaller**: 5-6 bytes saved on binary semantic
- **Consistent**: All methods use same header

### Decompression
- **Faster**: Single header parsing
- **Metadata extraction**: Zero-copy (read header bytes directly)
- **Routing**: Fast method dispatch from byte 2

### Audit Logging
- **Zero overhead** when disabled (flags bit 7 = 0)
- **6 bytes overhead** when enabled (timestamp + flags)
- **No parsing penalty**: metadata in header, not payload

## Security Considerations

### Header Validation
```python
def validate_header(data: bytes) -> bool:
    # Check magic number
    magic = (data[0] & 0xF0) >> 4
    if magic != 0xA:
        return False

    # Check version
    version = data[0] & 0x0F
    if version > 1:
        return False  # Unsupported version

    # Check method
    method = data[2]
    if method not in VALID_METHODS:
        return False

    return True
```

### Size Limits
- Max header size: 12 bytes (with all metadata)
- Max payload size: 65KB (2-byte length) or unlimited (if flag bit 4 = 0)
- Total message size: Configurable limit

## Testing Strategy

1. **Unit tests**: Header encoding/decoding
2. **Roundtrip tests**: All compression methods
3. **Audit tests**: Metadata preservation
4. **Performance tests**: Header overhead benchmarks
5. **Migration tests**: Legacy format compatibility

## Success Metrics

- [ ] All traffic uses unified format
- [ ] Header overhead ≤ 6 bytes for common case
- [ ] Audit metadata available at zero parsing cost
- [ ] Backward compatible with legacy format
- [ ] Performance: header parsing < 0.001ms
