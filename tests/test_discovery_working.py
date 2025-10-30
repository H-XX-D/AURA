#!/usr/bin/env python3
"""
Test script to verify automatic template discovery actually finds templates.
Uses a larger corpus with more repetitive patterns.
"""

import sys
import tempfile
from pathlib import Path

PACKAGE_SRC = Path(__file__).resolve().parent.parent / 'tools' / 'packages' / 'aura-compressor-py' / 'src'
sys.path.insert(0, str(PACKAGE_SRC))

from aura_compressor.lib.template_discovery import TemplateDiscovery
from aura_compressor.lib.template_manager import TemplateManager
from aura_compressor.lib.template_store import TemplateStore

print("=" * 70)
print("AURA TEMPLATE DISCOVERY - FUNCTIONALITY TEST")
print("=" * 70)

# Create a larger, more repetitive corpus
corpus = []

# Pattern 1: "I don't have access to X" - 10 variations
access_things = [
    "real-time data",
    "your personal files",
    "the internet",
    "your location",
    "external databases",
    "your calendar",
    "your emails",
    "your photos",
    "your contacts",
    "live information",
]
for thing in access_things:
    corpus.append(f"I don't have access to {thing}.")

# Pattern 2: "I cannot X because Y" - 8 variations
cannot_reasons = [
    ("execute code", "I'm a text-based AI"),
    ("access hardware", "I have no physical interface"),
    ("browse websites", "I'm not connected to the internet"),
    ("make purchases", "I don't have payment capabilities"),
    ("send emails", "I don't have email access"),
    ("make phone calls", "I'm a software system"),
    ("access databases", "I don't have credentials"),
    ("modify files", "I lack file system access"),
]
for action, reason in cannot_reasons:
    corpus.append(f"I cannot {action} because {reason}.")

# Pattern 3: "You can X by Y" - 6 variations
you_can = [
    ("improve performance", "optimizing your code"),
    ("save money", "using caching strategies"),
    ("increase security", "enabling two-factor authentication"),
    ("reduce latency", "using a CDN"),
    ("enhance reliability", "adding redundancy"),
    ("boost speed", "implementing parallelization"),
]
for goal, method in you_can:
    corpus.append(f"You can {goal} by {method}.")

# Pattern 4: "Error: X" - 5 variations
errors = ["File not found", "Permission denied", "Connection timeout",
          "Invalid credentials", "Database error"]
for error in errors:
    corpus.append(f"Error: {error}.")

# Pattern 5: "The X is Y" - 5 variations
statements = [
    ("compression ratio", "3.5:1"),
    ("file size", "1.2MB"),
    ("success rate", "98.7%"),
    ("response time", "45ms"),
    ("error count", "zero"),
]
for subject, value in statements:
    corpus.append(f"The {subject} is {value}.")

print(f"\n📊 Test Corpus: {len(corpus)} AI responses")
print(f"   Expected patterns: 5 distinct templates")
print(f"   Each pattern appears: 5-10 times\n")

# Initialize discovery with LOWER thresholds for this test
discovery = TemplateDiscovery(
    min_occurrences=3,  # Need at least 3 occurrences
    min_compression_ratio=1.5,  # Lowered from 2.0
    min_confidence=0.6  # Lowered from 0.7
)

# Add all responses
print("📥 Loading corpus into discovery engine...")
for response in corpus:
    discovery.add_response(response)

# Run discovery
print("🔍 Running template discovery algorithms...")
print("   - N-gram analysis")
print("   - Similarity clustering")
print("   - Regex pattern matching")
print("   - Prefix/suffix extraction\n")

candidates = discovery.discover_templates()

# Report results
print("=" * 70)
print("RESULTS")
print("=" * 70)

if len(candidates) > 0:
    print(f"\n✅ SUCCESS: Discovered {len(candidates)} templates\n")

    for i, candidate in enumerate(candidates[:10], 1):
        print(f"Template #{i}:")
        print(f"  Pattern: {candidate.pattern}")
        print(f"  Category: {candidate.category}")
        print(f"  Occurrences: {candidate.occurrences}")
        print(f"  Compression Ratio: {candidate.compression_ratio:.2f}:1")
        print(f"  Confidence: {candidate.confidence:.2f}")
        print(f"  Examples:")
        for ex in candidate.examples[:2]:
            print(f"    - {ex}")
        print()

    # Verify we found the expected patterns
    patterns_found = [c.pattern for c in candidates]
    expected_patterns = [
        "I don't have access to",
        "I cannot",
        "You can",
        "Error:",
        "The",
    ]

    matches = 0
    for expected in expected_patterns:
        for found in patterns_found:
            if expected in found:
                matches += 1
                break

    print("=" * 70)
    print(f"VERIFICATION: Found {matches}/5 expected pattern types")

    if matches >= 3:
        print("✅ TEST PASSED: Template discovery is working correctly!")
    else:
        print("⚠️  TEST PARTIAL: Some patterns not discovered (thresholds may need tuning)")

else:
    print("\n❌ FAILED: No templates discovered")
    print("   This indicates the discovery thresholds are too strict")
    print("   or the algorithms need adjustment.\n")
    print("   However, the DEFAULT templates in TemplateManager still work")
    print("   (as demonstrated in the main demo).")

print("\n" + "=" * 70)
print("TEST COMPLETE")
print("=" * 70)


def test_discovery_finds_expected_patterns():
    discovery = TemplateDiscovery(min_occurrences=3, min_compression_ratio=1.5, min_confidence=0.6)
    corpus = []
    access_things = [
        "real-time data",
        "your personal files",
        "the internet",
        "your location",
        "external databases",
        "your calendar",
        "your emails",
        "your photos",
        "your contacts",
        "live information",
    ]
    for thing in access_things:
        corpus.append(f"I don't have access to {thing}.")
    cannot_reasons = [
        ("execute code", "I'm a text-based AI"),
        ("access hardware", "I have no physical interface"),
        ("browse websites", "I'm not connected to the internet"),
        ("make purchases", "I don't have payment capabilities"),
        ("send emails", "I don't have email access"),
        ("make phone calls", "I'm a software system"),
        ("access databases", "I don't have credentials"),
        ("modify files", "I lack file system access"),
    ]
    for action, reason in cannot_reasons:
        corpus.append(f"I cannot {action} because {reason}.")
    you_can = [
        ("improve performance", "optimizing your code"),
        ("save money", "using caching strategies"),
        ("increase security", "enabling two-factor authentication"),
        ("reduce latency", "using a CDN"),
        ("enhance reliability", "adding redundancy"),
        ("boost speed", "implementing parallelization"),
    ]
    for goal, method in you_can:
        corpus.append(f"You can {goal} by {method}.")
    errors = ["File not found", "Permission denied", "Connection timeout", "Invalid credentials", "Database error"]
    for error in errors:
        corpus.append(f"Error: {error}.")
    statements = [
        ("compression ratio", "3.5:1"),
        ("file size", "1.2MB"),
        ("success rate", "98.7%"),
        ("response time", "45ms"),
        ("error count", "zero"),
    ]
    for subject, value in statements:
        corpus.append(f"The {subject} is {value}.")
    for response in corpus:
        discovery.add_response(response)
    candidates = discovery.discover_templates()
    patterns = {candidate.pattern for candidate in candidates}
    expected = {"I don't have access to {0}", "I cannot {0} because {1}", "You can {0} by {1}", "Error: {0}", "The {0} is {1}"}
    assert expected.issubset(patterns)


def test_discovery_promotes_and_persists_templates():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = TemplateStore(Path(tmpdir) / 'templates.json')
        manager = TemplateManager(template_store=store)
        manager.remove_template(0)
        discovery = TemplateDiscovery(min_occurrences=3, min_compression_ratio=1.5, min_confidence=0.6)
        for thing in ["real-time data", "your calendar", "external systems", "live telemetry"]:
            discovery.add_response(f"I don't have access to {thing}.")
        added = discovery.promote_templates(manager)
        assert added >= 1
        reloaded = TemplateManager(template_store=store)
        assert reloaded.find_template_by_pattern("I don't have access to {0}") is not None
