#!/usr/bin/env python3
"""Debug binary semantic format"""

import sys
import struct
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aura_compression.compressor_refactored import ProductionHybridCompressor


compressor = ProductionHybridCompressor(
    enable_aura=False,
    enable_audit_logging=False,
    enable_scorer=False
)

message = "How do I create a numpy array?"

print(f"Original message: \"{message}\"")
print(f"Length: {len(message)} bytes")
print()

# Compress
compressed, method, metadata = compressor.compress(message)

print(f"Compression method: {method.name}")
print(f"Compressed size: {len(compressed)} bytes")
print(f"Metadata: {metadata}")
print()

# Analyze compressed data
print("Compressed data breakdown:")
print(f"  Total bytes: {len(compressed)}")
print(f"  Hex: {compressed.hex()}")
print()

# Parse it manually
view = memoryview(compressed)
offset = 0

method_byte = view[offset]
print(f"  Byte {offset}: Method = {method_byte}")
offset += 1

template_id = struct.unpack(">H", view[offset:offset+2].tobytes())[0]
print(f"  Bytes {offset}-{offset+1}: Template ID = {template_id}")
offset += 2

slot_count = view[offset]
print(f"  Byte {offset}: Slot count = {slot_count}")
offset += 1

ws_flags = view[offset]
print(f"  Byte {offset}: Whitespace flags = {ws_flags:#04x}")
offset += 1

leading_ws_len, trailing_ws_len = struct.unpack(">HH", view[offset:offset+4].tobytes())
print(f"  Bytes {offset}-{offset+3}: WS lengths = leading:{leading_ws_len}, trailing:{trailing_ws_len}")
offset += 4

if leading_ws_len > 0:
    leading_ws = view[offset:offset+leading_ws_len].tobytes().decode('utf-8')
    print(f"  Bytes {offset}-{offset+leading_ws_len-1}: Leading WS = {repr(leading_ws)}")
    offset += leading_ws_len

if trailing_ws_len > 0:
    trailing_ws = view[offset:offset+trailing_ws_len].tobytes().decode('utf-8')
    print(f"  Bytes {offset}-{offset+trailing_ws_len-1}: Trailing WS = {repr(trailing_ws)}")
    offset += trailing_ws_len

print(f"  Bytes remaining for slots: {len(view) - offset}")
print(f"  Expected slot length bytes: {slot_count * 2}")

if len(view) - offset < slot_count * 2:
    print(f"  ✗ ERROR: Not enough bytes for slot lengths!")
    print(f"    Need {slot_count * 2}, have {len(view) - offset}")
