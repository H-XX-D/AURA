# Binary Semantic Header Optimization

## Problem
Current whitespace-aware format uses 11 bytes overhead:
- 1 byte: method
- 2 bytes: template_id
- 1 byte: slot_count
- 1 byte: whitespace flags
- 4 bytes: whitespace lengths (2 bytes each for leading/trailing)
- 2 bytes: slot length (per slot)

**Total: 9 bytes + 2n bytes (where n = slot count)**

For small messages, this overhead kills compression.

## Solution: Compact Hexadecimal Header

Use a single flags byte to encode common whitespace patterns:

### Hex Flags Byte (8 bits)
```
Bit 7-6: Whitespace variant
  00 = No whitespace
  01 = Single space leading
  10 = Single space trailing
  11 = Custom (read lengths)

Bit 5-4: Reserved for future use

Bit 3-0: Slot count (0-15)
```

### New Header Format (Compact)

**Case 1: No whitespace or standard whitespace (6 bytes minimum)**
```
[method:1][template_id:2][flags:1][slot_lengths:2n][slot_data:*]
```

**Case 2: Custom whitespace (variable)**
```
[method:1][template_id:2][flags:1][ws_len:1-2][ws_data:*][slot_lengths:2n][slot_data:*]
```

### Encoding Examples

#### Example 1: No whitespace, 1 slot
```
flags = 0b00000001 = 0x01
  Bits 7-6: 00 (no whitespace)
  Bits 5-4: 00 (reserved)
  Bits 3-0: 0001 (1 slot)

Header: [0x00][template_id:2][0x01][slot_len:2]
Total: 6 bytes overhead (was 11)
Savings: 5 bytes
```

#### Example 2: Single leading space, 2 slots
```
flags = 0b01000010 = 0x42
  Bits 7-6: 01 (single leading space)
  Bits 5-4: 00 (reserved)
  Bits 3-0: 0010 (2 slots)

Header: [0x00][template_id:2][0x42][slot_lens:4]
Total: 7 bytes overhead (was 13)
Savings: 6 bytes
```

#### Example 3: Custom whitespace (multiple spaces, tabs, newlines)
```
flags = 0b11000001 = 0xC1
  Bits 7-6: 11 (custom whitespace)
  Bits 5-4: 00 (reserved)
  Bits 3-0: 0001 (1 slot)

Whitespace encoding:
  [ws_flags:1][leading_len:1][trailing_len:1][leading_data:*][trailing_data:*]

  ws_flags byte:
    Bit 0: has leading
    Bit 1: has trailing
    Bits 2-7: reserved

Header: [0x00][template_id:2][0xC1][ws_flags:1][ws_lens:2][ws_data:*][slot_len:2]
Total: 8 bytes + ws_data overhead (only when needed)
```

## Slot Count Encoding

Using 4 bits allows 0-15 slots.

**For templates with >15 slots:**
```
flags = 0b****1111 (bits 3-0 = 15)
Extended byte: [ext_slot_count:1]

This allows up to 255 slots while keeping common case (≤15 slots) compact.
```

## Implementation Impact

### Overhead Reduction
| Scenario | Old | New | Savings |
|----------|-----|-----|---------|
| No whitespace, 1 slot | 11 bytes | 6 bytes | 5 bytes |
| Single space, 1 slot | 11 bytes | 6 bytes | 5 bytes |
| Custom whitespace | 11+ bytes | 8+ bytes | 3 bytes |

### Compression Effectiveness

**Before:** Template must save >11 bytes to break even
**After:** Template must save >6 bytes to break even

For "How {0}?" template (saves ~5 bytes):
- Old: 11 - 5 = 6 bytes net overhead ❌
- New: 6 - 5 = 1 byte net overhead ✓ (marginal)

For "What's {0}?" template (saves ~7 bytes):
- Old: 11 - 7 = 4 bytes net overhead ❌
- New: 6 - 7 = -1 byte net savings ✓

## Migration Strategy

### Version Byte
Add version to method byte high bits:

```
Method byte format:
  Bits 7-5: Version (0-7)
  Bits 4-0: Method (0-31)

Version 0: Legacy format (11-byte overhead)
Version 1: Compact hex header (6-byte overhead)
```

### Backward Compatibility
- Reader checks version bits
- Version 0: Use old decompression
- Version 1: Use new decompression
- Writer always uses Version 1

## Code Impact

### Files to Modify
1. `compression_engine.py`:
   - `compress_binary_semantic()`: Use compact header
   - `decompress_binary_semantic()`: Support both versions

2. `enums.py`:
   - Add header version constants
   - Add whitespace variant enum

### Performance Impact
- Compression: Negligible (simpler encoding)
- Decompression: Negligible (single flag byte parsing)
- Space: 5-6 bytes saved per message (significant for small messages)

## Validation
- All existing tests should pass
- New tests for compact header variants
- Migration test (old format → new format)
