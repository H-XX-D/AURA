#!/usr/bin/env python3
"""
Test AI-to-AI Partial Compression

Demonstrates partial template matching with structured AI responses
(the actual use case AURA was designed for).
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aura_compression.compressor_refactored import ProductionHybridCompressor
from aura_compression.templates import TemplateLibrary


def test_ai_to_ai_compression():
    """Test partial compression with AI-structured messages"""

    print("=" * 80)
    print("AI-TO-AI PARTIAL COMPRESSION TEST")
    print("=" * 80)
    print()

    # Create compressor
    compressor = ProductionHybridCompressor(
        binary_advantage_threshold=1.01,
        min_compression_size=10,
        enable_aura=False,
        enable_audit_logging=False,
        template_cache_size=256,
        enable_scorer=False
    )

    # Add AI-to-AI templates (simulating what would be discovered)
    lib = compressor._template_service.template_manager.template_library

    # Template for OpenAI-style API responses
    lib.add(1, '{"id": "{0}", "object": "chat.completion", "model": "{1}", "choices": [{"message": {"content": "{2}"}}]}')

    # Template for status responses
    lib.add(2, '{"status": "{0}", "message": "{1}", "timestamp": {2}}')

    print("Added AI-to-AI templates:")
    print("  Template 1: OpenAI API response structure")
    print("  Template 2: Status response structure")
    print()

    # Test messages (AI responses with extra data)
    test_cases = [
        {
            'name': 'OpenAI API response with usage data',
            'message': '{"id": "chatcmpl-abc123", "object": "chat.completion", "model": "gpt-4", "choices": [{"message": {"content": "The capital of France is Paris."}}], "usage": {"prompt_tokens": 10, "completion_tokens": 8, "total_tokens": 18}}'
        },
        {
            'name': 'Status response with metadata',
            'message': '{"status": "success", "message": "Operation completed", "timestamp": 1698765432, "metadata": {"user": "alice", "duration_ms": 125}}'
        },
        {
            'name': 'Partial match - mixed content',
            'message': 'Response from AI: {"status": "success", "message": "Task done", "timestamp": 1698765432} - Process completed successfully.'
        }
    ]

    results = []
    for test in test_cases:
        message = test['message']
        name = test['name']

        print(f"Test: {name}")
        print(f"Message ({len(message)} bytes):")
        print(f"  {message[:80]}{'...' if len(message) > 80 else ''}")
        print()

        # Check template matches
        full_match = compressor._template_service.find_template_match(message)
        partial_matches = lib.find_substring_matches(message)

        print(f"  Full match: {full_match is not None}")
        print(f"  Partial matches: {len(partial_matches)}")

        if partial_matches:
            for i, match in enumerate(partial_matches):
                coverage = (match.end - match.start) / len(message) * 100
                print(f"    Match {i+1}: Template {match.template_id}, Coverage {coverage:.1f}%")

        # Compress
        try:
            compressed, method, metadata = compressor.compress(message)

            ratio = metadata.get('ratio', 0.0)
            partial = metadata.get('partial_match', False)
            coverage = metadata.get('match_coverage', 0.0)

            print(f"  Compression:")
            print(f"    Method: {method.name}")
            print(f"    Ratio: {ratio:.3f}x")
            print(f"    Original: {len(message)} bytes → Compressed: {len(compressed)} bytes")
            print(f"    Partial match: {partial}")
            if partial:
                print(f"    Template coverage: {coverage:.1%}")

            # Verify decompression
            try:
                decompressed, _ = compressor.decompress(compressed, return_metadata=True)
                matches = decompressed == message
                print(f"    Decompression: {'✓ OK' if matches else '✗ FAILED'}")
            except Exception as e:
                print(f"    Decompression: ✗ ERROR - {e}")
                matches = False

            results.append({
                'name': name,
                'ratio': ratio,
                'partial': partial,
                'coverage': coverage,
                'success': matches
            })

        except Exception as e:
            print(f"  Compression: ✗ ERROR - {e}")
            results.append({
                'name': name,
                'ratio': 0.0,
                'partial': False,
                'coverage': 0.0,
                'success': False
            })

        print()

    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print()

    successful = sum(1 for r in results if r['success'])
    partial_used = sum(1 for r in results if r['partial'])
    avg_ratio = sum(r['ratio'] for r in results) / len(results) if results else 0.0

    print(f"Tests run: {len(results)}")
    print(f"Successful: {successful}/{len(results)}")
    print(f"Partial matching used: {partial_used}/{len(results)}")
    print(f"Average compression ratio: {avg_ratio:.3f}x")
    print()

    if avg_ratio > 1.5:
        print("✓ EXCELLENT: Partial compression working well for AI-to-AI data!")
        print(f"  {avg_ratio:.3f}x is much better than the 0.965x from human messages")
    elif avg_ratio > 1.0:
        print("✓ GOOD: Compression is working (ratio > 1.0x)")
    else:
        print("⚠ WARNING: Compression ratio < 1.0x (expanding data)")

    print()
    print("Note: Partial compression is now connected to the pipeline.")
    print("For production AI-to-AI use, add more templates via discovery.")

    assert successful == len(results), f"Only {successful}/{len(results)} tests passed"


if __name__ == "__main__":
    try:
        test_ai_to_ai_compression()
        sys.exit(0)
    except AssertionError:
        sys.exit(1)
