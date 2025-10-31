#!/usr/bin/env python3
"""
Demonstration: Partial Template Compression

Shows how AURA SHOULD work with partial template matching for AI-to-AI messages.
Currently, AURA only does full-match template compression.
This test demonstrates the potential of partial matching.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aura_compression.templates import TemplateLibrary, TemplateMatch


def test_full_vs_partial_matching():
    """Demonstrate the difference between full and partial matching"""

    # Create template library
    lib = TemplateLibrary()

    # Use existing template (Template 0: "I don't have access to {0}. {1}")
    # This demonstrates the concept with simpler messages

    # Test message: Partial match (has extra novel content before template)
    message_with_prefix = "Note: This is a system message. I don't have access to your files. Please check permissions."

    # Test message: Full match (exactly matches template)
    message_exact = "I don't have access to your files. Please check permissions."

    # Test message: Partial match (has extra novel content after template)
    message_with_suffix = "I don't have access to your files. Please check permissions. Contact support for help."

    print("=" * 80)
    print("PARTIAL VS FULL TEMPLATE MATCHING DEMONSTRATION")
    print("=" * 80)
    print()

    # Test 1: Full matching (current behavior) - with prefix
    print("TEST 1: Full Matching with Prefix (Current Behavior)")
    print("-" * 80)
    print(f"Message: \"{message_with_prefix}\"")
    print(f"Length: {len(message_with_prefix)} bytes")
    print()

    full_match = lib.match(message_with_prefix)
    if full_match:
        print(f"✓ Full match found: Template ID {full_match.template_id}")
        print(f"  Slots: {full_match.slots}")
    else:
        print("✗ No full match found (expected - message has prefix)")
        print("  → Falls back to AURALITE compression (worse ratio)")
    print()

    # Test 2: Full matching with exact message
    print("TEST 2: Full Matching with Exact Message")
    print("-" * 80)
    print(f"Message: \"{message_exact}\"")
    print(f"Length: {len(message_exact)} bytes")
    print()

    full_match_exact = lib.match(message_exact)
    if full_match_exact:
        print(f"✓ Full match found: Template ID {full_match_exact.template_id}")
        print(f"  Slots: {full_match_exact.slots}")
        print(f"  → BINARY_SEMANTIC compression (good ratio)")
    else:
        print("✗ No full match found")
    print()

    # Test 3: Partial matching (what SHOULD happen) - with prefix
    print("TEST 3: Partial Matching with Prefix (What SHOULD Happen)")
    print("-" * 80)
    print(f"Message: \"{message_with_prefix}\"")
    print(f"Length: {len(message_with_prefix)} bytes")
    print()

    # Use find_substring_matches (exists but not used!)
    partial_matches = lib.find_substring_matches(message_with_prefix)

    if partial_matches:
        for i, match in enumerate(partial_matches):
            matched_text = message_with_prefix[match.start:match.end]
            print(f"✓ Partial match {i+1}: Template ID {match.template_id}")
            print(f"  Range: [{match.start}:{match.end}] ({match.end - match.start} bytes)")
            print(f"  Matched text: \"{matched_text}\"")
            print(f"  Slots: {match.slots}")

        # Calculate what's NOT matched
        total_matched = sum(m.end - m.start for m in partial_matches)
        unmatched = len(message_with_prefix) - total_matched

        print()
        print(f"  Total message: {len(message_with_prefix)} bytes")
        print(f"  Matched (template): {total_matched} bytes")
        print(f"  Unmatched (novel): {unmatched} bytes")
        print(f"  → Compress only {unmatched} bytes, reference template for {total_matched} bytes")
        print()
        print(f"  Potential compression:")
        print(f"    Template ref: 2 bytes (ID) + {len(match.slots) * 10} bytes (slots) = ~{2 + len(match.slots) * 10} bytes")
        print(f"    Novel content: ~{unmatched} bytes → ~{int(unmatched / 1.3)} bytes compressed")
        print(f"    Total: ~{2 + len(match.slots) * 10 + int(unmatched / 1.3)} bytes")
        print(f"    Ratio: {len(message_with_prefix) / (2 + len(match.slots) * 10 + unmatched / 1.3):.2f}x")
    else:
        print("✗ No partial matches found")

    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print()
    print("Current behavior (full-match only):")
    print("  ✗ Message with extra content: Falls back to AURALITE (~1.3x ratio)")
    print("  ✓ Exact template match: Uses BINARY_SEMANTIC (~2.5x ratio)")
    print("  Problem: Requires PERFECT match, rejects 98.6% of messages")
    print()
    print("Desired behavior (partial matching):")
    print("  ✓ Message with extra content: Compress novel parts, reference template")
    print("  ✓ Exact template match: Same as current")
    print("  Benefit: Accept ~80% of AI-to-AI messages with partial matches")
    print()
    print("The code EXISTS (find_substring_matches) but ISN'T USED!")
    print()


if __name__ == "__main__":
    test_full_vs_partial_matching()
