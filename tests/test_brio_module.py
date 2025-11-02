#!/usr/bin/env python3
"""Comprehensive tests for BRIO module"""

from aura_compression.brio import BrioEncoder, BrioDecoder
from aura_compression.templates import TemplateLibrary

print('='*60)
print('BRIO Module Comprehensive Tests')
print('='*60)

# Create template library
template_lib = TemplateLibrary()

# Create encoder and decoder
encoder = BrioEncoder(template_library=template_lib)
decoder = BrioDecoder(template_library=template_lib)

# Test 1: Basic compression/decompression
print('\n[Test 1] Basic compression/decompression')
test_text = 'Hello, this is a test message for BRIO compression!'
print(f'  Original: {test_text}')
print(f'  Size: {len(test_text)} bytes')

compressed = encoder.compress(test_text)
print(f'  Compressed size: {len(compressed.payload)} bytes')
print(f'  Ratio: {len(test_text) / len(compressed.payload):.2f}x')

decompressed = decoder.decompress(compressed.payload)
print(f'  Match: {decompressed.text == test_text}')
if decompressed.text == test_text:
    print('  ✅ PASSED')
else:
    print(f'  ❌ FAILED')
    print(f'  Expected: {test_text}')
    print(f'  Got: {decompressed.text}')

# Test 2: Long text with repetition
print('\n[Test 2] Long text with repetition (LZ77 test)')
test_long = 'The quick brown fox jumps over the lazy dog. ' * 20
print(f'  Original size: {len(test_long)} bytes')

compressed_long = encoder.compress(test_long)
print(f'  Compressed size: {len(compressed_long.payload)} bytes')
print(f'  Ratio: {len(test_long) / len(compressed_long.payload):.2f}x')

decompressed_long = decoder.decompress(compressed_long.payload)
if decompressed_long.text == test_long:
    print('  ✅ PASSED - Compression with repetition works')
else:
    print('  ❌ FAILED')

# Test 3: Short message
print('\n[Test 3] Short message')
short = 'Hi!'
compressed_short = encoder.compress(short)
decompressed_short = decoder.decompress(compressed_short.payload)
print(f'  Original: "{short}" ({len(short)} bytes)')
print(f'  Compressed: {len(compressed_short.payload)} bytes')
if decompressed_short.text == short:
    print('  ✅ PASSED')
else:
    print('  ❌ FAILED')

# Test 4: Empty string
print('\n[Test 4] Empty string')
try:
    empty = ''
    compressed_empty = encoder.compress(empty)
    decompressed_empty = decoder.decompress(compressed_empty.payload)
    if decompressed_empty.text == empty:
        print('  ✅ PASSED - Empty string handled')
    else:
        print('  ❌ FAILED')
except Exception as e:
    print(f'  ⚠️  Exception: {e}')

# Test 5: Unicode text
print('\n[Test 5] Unicode text')
unicode_text = 'Hello 世界 🌍 Ñoño مرحبا Привет'
try:
    compressed_unicode = encoder.compress(unicode_text)
    decompressed_unicode = decoder.decompress(compressed_unicode.payload)
    if decompressed_unicode.text == unicode_text:
        print('  ✅ PASSED - Unicode handled correctly')
    else:
        print('  ❌ FAILED')
        print(f'  Expected: {unicode_text}')
        print(f'  Got: {decompressed_unicode.text}')
except Exception as e:
    print(f'  ❌ FAILED with exception: {e}')

# Test 6: Dictionary words (common words should compress well)
print('\n[Test 6] Dictionary compression')
dict_text = 'the the the and and or but if then else when where what who why how'
compressed_dict = encoder.compress(dict_text)
decompressed_dict = decoder.decompress(compressed_dict.payload)
print(f'  Original size: {len(dict_text)} bytes')
print(f'  Compressed size: {len(compressed_dict.payload)} bytes')
print(f'  Ratio: {len(dict_text) / len(compressed_dict.payload):.2f}x')
if decompressed_dict.text == dict_text:
    print('  ✅ PASSED - Dictionary compression works')
else:
    print('  ❌ FAILED')

# Test 7: Structured log message (template test)
print('\n[Test 7] Structured log message (template potential)')
log_msg = 'API REQUEST user=1001 action=login timestamp=2024-11-01T10:30:00Z status=success'
# Add template for better compression
template_lib.add(1000, 'API REQUEST user={0} action={1} timestamp={2} status={3}')
compressed_log = encoder.compress(log_msg)
decompressed_log = decoder.decompress(compressed_log.payload)
print(f'  Original size: {len(log_msg)} bytes')
print(f'  Compressed size: {len(compressed_log.payload)} bytes')
print(f'  Ratio: {len(log_msg) / len(compressed_log.payload):.2f}x')
if decompressed_log.text == log_msg:
    print('  ✅ PASSED - Log message compression works')
else:
    print('  ❌ FAILED')

# Test 8: Special characters
print('\n[Test 8] Special characters and punctuation')
special = 'Test!@#$%^&*()_+-=[]{}|;:,.<>?/~`'
try:
    compressed_special = encoder.compress(special)
    decompressed_special = decoder.decompress(compressed_special.payload)
    if decompressed_special.text == special:
        print('  ✅ PASSED - Special characters handled')
    else:
        print('  ❌ FAILED')
except Exception as e:
    print(f'  ❌ FAILED with exception: {e}')

# Test 9: Newlines and whitespace
print('\n[Test 9] Newlines and whitespace')
whitespace = 'Line 1\nLine 2\n\tTabbed\n  Spaced'
compressed_ws = encoder.compress(whitespace)
decompressed_ws = decoder.decompress(compressed_ws.payload)
if decompressed_ws.text == whitespace:
    print('  ✅ PASSED - Whitespace preserved')
else:
    print('  ❌ FAILED')

# Test 10: Large text
print('\n[Test 10] Large text (1000 chars)')
large = 'Lorem ipsum dolor sit amet, consectetur adipiscing elit. ' * 20
compressed_large = encoder.compress(large)
decompressed_large = decoder.decompress(compressed_large.payload)
print(f'  Original size: {len(large)} bytes')
print(f'  Compressed size: {len(compressed_large.payload)} bytes')
print(f'  Ratio: {len(large) / len(compressed_large.payload):.2f}x')
if decompressed_large.text == large:
    print('  ✅ PASSED - Large text handled')
else:
    print('  ❌ FAILED')

print('\n' + '='*60)
print('BRIO Module Tests Complete')
print('='*60)

# Cleanup
template_lib.shutdown()
