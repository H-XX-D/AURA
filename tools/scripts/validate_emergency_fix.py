#!/usr/bin/env python3
"""
Validate Emergency Configuration Fix

Compares current configuration against emergency configuration to verify:
1. No negative compression ratios
2. All messages compress (not expand)
3. Bandwidth savings are positive
4. Template hit rates are acceptable
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from aura_compression import ProductionHybridCompressor
from config.emergency_config import EMERGENCY_COMPRESSION_CONFIG, CONSERVATIVE_BRIO_CONFIG

# Update configs to use expanded template store
EMERGENCY_WITH_TEMPLATES = EMERGENCY_COMPRESSION_CONFIG.copy()
EMERGENCY_WITH_TEMPLATES['template_store_path'] = 'template_store_expanded.json'

CONSERVATIVE_WITH_TEMPLATES = CONSERVATIVE_BRIO_CONFIG.copy()
CONSERVATIVE_WITH_TEMPLATES['template_store_path'] = 'template_store_expanded.json'


# Test messages from the problematic websocket summary
TEST_MESSAGES = [
    "I don't have access to real-time weather data. Please check weather.com",
    "The capital of France is Paris.",
    "To install packages, use pip: `pip install numpy`",
    "Yes, I can help with that. What specific aspect would you like to know more about?",
    "The time complexity of binary search is O(log n) because it divides the search space in half.",
    "Common HTTP status codes include: 200, 404, 500.",
    "To debug this issue, I recommend: check console, verify endpoint, test authentication",
    "Neural networks work by adjusting weights through backpropagation.",
    "I understand your concern.",
    "Error 404: Resource not found",
    "Processing request...",
    "Authentication successful",
    "Database connection established",
    "Request completed in 45ms",
    "Cache hit for key: user_profile_123",
    "API rate limit: 95/100 requests",
    "Service status: operational",
    "Deployment started at 2025-10-23T10:30:00Z",
    "Health check passed: all systems nominal",
    "Retry 2/3 failed: connection timeout",
    "Task completed successfully",
    "Invalid input: missing required field",
    "Session expired - please log in again",
    "Data synchronized with remote server",
    "Backup completed: 1.2GB transferred",
]


def run_benchmark(config_name: str, config: dict):
    """Run benchmark with given configuration"""
    print(f"\n{'=' * 80}")
    print(f"Testing: {config_name}")
    print(f"{'=' * 80}\n")

    compressor = ProductionHybridCompressor(**config)

    total_original = 0
    total_compressed = 0
    expansion_count = 0
    template_hits = 0
    method_counts = {}

    results = []

    for message in TEST_MESSAGES:
        original_size = len(message.encode('utf-8'))
        compressed, method, metadata = compressor.compress(message)

        total_original += original_size
        total_compressed += metadata['compressed_size']

        # Check for expansion
        if metadata['compressed_size'] > original_size:
            expansion_count += 1

        # Track template hits
        if metadata.get('template_id') is not None:
            template_hits += 1

        # Track method distribution
        method_name = metadata['method']
        method_counts[method_name] = method_counts.get(method_name, 0) + 1

        results.append({
            'message': message[:50],
            'original': original_size,
            'compressed': metadata['compressed_size'],
            'ratio': metadata['ratio'],
            'method': method_name,
            'template_id': metadata.get('template_id'),
        })

    # Calculate metrics
    compression_ratio = total_original / total_compressed if total_compressed > 0 else 0
    bandwidth_savings = ((total_original - total_compressed) / total_original) * 100 if total_original > 0 else 0
    template_hit_rate = (template_hits / len(TEST_MESSAGES)) * 100
    expansion_percentage = (expansion_count / len(TEST_MESSAGES)) * 100

    # Print summary
    print(f"Total messages: {len(TEST_MESSAGES)}")
    print(f"Total original bytes: {total_original:,}")
    print(f"Total compressed bytes: {total_compressed:,}")
    print(f"Compression ratio: {compression_ratio:.2f}x")
    print(f"Bandwidth savings: {bandwidth_savings:.1f}%")
    print(f"Template hit rate: {template_hit_rate:.1f}%")
    print(f"Expansion count: {expansion_count} ({expansion_percentage:.1f}%)")
    print()

    # Method distribution
    print("Method distribution:")
    for method, count in sorted(method_counts.items()):
        percentage = (count / len(TEST_MESSAGES)) * 100
        print(f"  {method}: {count} ({percentage:.1f}%)")
    print()

    # Health check
    print("Health Check:")
    issues = []

    if compression_ratio < 1.0:
        issues.append(f"  CRITICAL: Compression ratio {compression_ratio:.2f}x < 1.0x (expanding data)")
    elif compression_ratio < 1.5:
        issues.append(f"  WARNING: Compression ratio {compression_ratio:.2f}x < 1.5x (suboptimal)")
    else:
        print(f"  OK: Compression ratio {compression_ratio:.2f}x >= 1.5x")

    if bandwidth_savings < 0:
        issues.append(f"  CRITICAL: Bandwidth savings {bandwidth_savings:.1f}% < 0% (using more bandwidth)")
    elif bandwidth_savings < 33:
        issues.append(f"  WARNING: Bandwidth savings {bandwidth_savings:.1f}% < 33% (suboptimal)")
    else:
        print(f"  OK: Bandwidth savings {bandwidth_savings:.1f}% >= 33%")

    if expansion_percentage > 10:
        issues.append(f"  CRITICAL: {expansion_percentage:.1f}% of messages expanding (target: <10%)")
    elif expansion_percentage > 5:
        issues.append(f"  WARNING: {expansion_percentage:.1f}% of messages expanding (target: <5%)")
    else:
        print(f"  OK: {expansion_percentage:.1f}% expansion rate <= 5%")

    if template_hit_rate < 40:
        issues.append(f"  WARNING: Template hit rate {template_hit_rate:.1f}% < 40% (suboptimal)")
    else:
        print(f"  OK: Template hit rate {template_hit_rate:.1f}% >= 40%")

    if issues:
        print()
        for issue in issues:
            print(issue)

    print()

    # Show worst cases
    print("Worst 5 compression ratios:")
    worst = sorted(results, key=lambda r: r['ratio'])[:5]
    for i, result in enumerate(worst, 1):
        expanding = " (EXPANDING!)" if result['compressed'] > result['original'] else ""
        print(f"  {i}. {result['message'][:40]}...")
        print(f"     {result['original']} -> {result['compressed']} bytes ({result['ratio']:.2f}x) [{result['method']}]{expanding}")
    print()

    return {
        'compression_ratio': compression_ratio,
        'bandwidth_savings': bandwidth_savings,
        'template_hit_rate': template_hit_rate,
        'expansion_percentage': expansion_percentage,
        'method_counts': method_counts,
    }


def main():
    print("\n" + "=" * 80)
    print("EMERGENCY CONFIGURATION VALIDATION")
    print("=" * 80)

    # Test current problematic configuration
    print("\nCURRENT CONFIGURATION (Baseline):")
    print("  enable_aura: True")
    print("  min_compression_size: 50")
    print("  aura_preference_margin: 0.05")

    current_results = run_benchmark(
        "Current Configuration (PROBLEMATIC)",
        {
            'enable_aura': True,
            'min_compression_size': 50,
            'aura_preference_margin': 0.05,
        }
    )

    # Test emergency configuration
    print("\n" + "=" * 80)
    emergency_results = run_benchmark(
        "Emergency Configuration (RECOMMENDED)",
        EMERGENCY_WITH_TEMPLATES
    )

    # Test conservative BRIO configuration
    print("\n" + "=" * 80)
    conservative_results = run_benchmark(
        "Conservative BRIO Configuration (ALTERNATIVE)",
        CONSERVATIVE_WITH_TEMPLATES
    )

    # Comparison
    print("\n" + "=" * 80)
    print("CONFIGURATION COMPARISON")
    print("=" * 80)
    print()

    configs = [
        ("Current (Problematic)", current_results),
        ("Emergency (Recommended)", emergency_results),
        ("Conservative BRIO", conservative_results),
    ]

    print(f"{'Configuration':<30} {'Ratio':>8} {'Bandwidth':>10} {'Templates':>10} {'Expansion':>10}")
    print("-" * 80)

    for name, results in configs:
        print(f"{name:<30} "
              f"{results['compression_ratio']:>7.2f}x "
              f"{results['bandwidth_savings']:>9.1f}% "
              f"{results['template_hit_rate']:>9.1f}% "
              f"{results['expansion_percentage']:>9.1f}%")

    print()
    print("Recommendation:")
    print()

    # Determine best configuration
    best_config = max(configs[1:], key=lambda c: c[1]['compression_ratio'])  # Exclude current

    if best_config[1]['compression_ratio'] > 1.5 and best_config[1]['expansion_percentage'] < 5:
        print(f"  Deploy: {best_config[0]}")
        print(f"  Expected compression: {best_config[1]['compression_ratio']:.2f}x")
        print(f"  Expected bandwidth savings: {best_config[1]['bandwidth_savings']:.1f}%")
        print(f"  Expected expansion rate: {best_config[1]['expansion_percentage']:.1f}%")
    else:
        print("  WARNING: Neither emergency configuration meets all targets")
        print("  Recommend further investigation and template library expansion")

    print()
    print("=" * 80)
    print("Next Steps:")
    print("=" * 80)
    print()
    print("1. Deploy emergency configuration immediately:")
    print("   from config.emergency_config import get_compressor")
    print("   compressor = get_compressor()")
    print()
    print("2. Monitor metrics for 48 hours:")
    print("   - Compression ratio should be > 1.0x")
    print("   - Bandwidth savings should be > 0%")
    print("   - Expansion rate should be < 5%")
    print()
    print("3. Proceed to Week 2: Template Library Expansion")
    print("   - Run template discovery on audit logs")
    print("   - Add 50+ domain-specific templates")
    print("   - Target 60-80% template hit rate")
    print()


if __name__ == "__main__":
    main()
