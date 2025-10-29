#!/usr/bin/env python3
"""
AURA Trace Analysis Script

Analyzes and compares different trace datasets for performance insights.
"""

import json
import statistics
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Any


def analyze_trace_directory(trace_dir: str) -> Dict[str, Any]:
    """Analyze a directory of trace files."""

    trace_path = Path(trace_dir)
    if not trace_path.exists():
        return {"error": f"Directory {trace_dir} not found"}

    stats = {
        "directory": trace_dir,
        "total_entries": 0,
        "total_users": 0,
        "compression_methods": defaultdict(int),
        "compression_ratios": [],
        "latencies": [],
        "message_lengths": [],
        "success_rate": 0.0,
        "avg_compression_ratio": 0.0,
        "avg_latency_ms": 0.0,
        "avg_message_length": 0.0,
        "compression_ratio_std": 0.0,
        "latency_std": 0.0
    }

    successful_entries = 0

    # Find all trace files
    trace_files = list(trace_path.glob("user_*_traces.jsonl"))
    stats["total_users"] = len(trace_files)

    for trace_file in trace_files:
        try:
            with open(trace_file, 'r', encoding='utf-8') as f:
                for line in f:
                    entry = json.loads(line.strip())
                    stats["total_entries"] += 1

                    # Collect statistics
                    if entry.get("success", True):
                        successful_entries += 1
                        stats["compression_ratios"].append(entry.get("compression_ratio", 1.0))
                        stats["latencies"].append(entry.get("latency_ms", 0.0))
                        stats["message_lengths"].append(entry.get("message_length", 0))

                    # Count compression methods
                    method = entry.get("method", "UNKNOWN")
                    stats["compression_methods"][method] += 1

        except Exception as e:
            print(f"Error reading {trace_file}: {e}")
            continue

    # Calculate averages and statistics
    if successful_entries > 0:
        stats["success_rate"] = successful_entries / stats["total_entries"]
        stats["avg_compression_ratio"] = statistics.mean(stats["compression_ratios"])
        stats["avg_latency_ms"] = statistics.mean(stats["latencies"])
        stats["avg_message_length"] = statistics.mean(stats["message_lengths"])

        if len(stats["compression_ratios"]) > 1:
            stats["compression_ratio_std"] = statistics.stdev(stats["compression_ratios"])
        if len(stats["latencies"]) > 1:
            stats["latency_std"] = statistics.stdev(stats["latencies"])

    return stats


def print_comparison(original_stats: Dict, expanded_stats: Dict):
    """Print a comparison between original and expanded traces."""

    print("\n" + "="*80)
    print("TRACE DATASET COMPARISON")
    print("="*80)

    print(f"\n{'Metric':<25} {'Original':<15} {'Expanded':<15} {'Improvement':<15}")
    print("-" * 70)

    metrics = [
        ("Total Users", "total_users", "total_users"),
        ("Total Entries", "total_entries", "total_entries"),
        ("Avg Compression Ratio", "avg_compression_ratio", "avg_compression_ratio"),
        ("Avg Latency (ms)", "avg_latency_ms", "avg_latency_ms"),
        ("Avg Message Length", "avg_message_length", "avg_message_length"),
        ("Success Rate", "success_rate", "success_rate"),
    ]

    for label, orig_key, exp_key in metrics:
        orig_val = original_stats.get(orig_key, 0)
        exp_val = expanded_stats.get(exp_key, 0)

        if "ratio" in orig_key.lower():
            orig_str = f"{orig_val:.3f}"
            exp_str = f"{exp_val:.3f}"
            if orig_val == 0:
                improvement = "N/A" if exp_val == 0 else "∞"
            elif exp_val > orig_val:
                improvement = f"+{(exp_val/orig_val - 1)*100:.1f}%"
            else:
                improvement = f"{(exp_val/orig_val - 1)*100:.1f}%"
        elif "rate" in orig_key.lower():
            orig_str = f"{orig_val:.1%}"
            exp_str = f"{exp_val:.1%}"
            improvement = f"{(exp_val - orig_val)*100:.1f}pp"
        elif "latency" in orig_key.lower():
            orig_str = f"{orig_val:.3f}"
            exp_str = f"{exp_val:.3f}"
            if orig_val == 0:
                improvement = "N/A" if exp_val == 0 else "∞"
            elif exp_val < orig_val:
                improvement = f"{(1 - exp_val/orig_val)*100:.1f}%"
            else:
                improvement = f"+{(exp_val/orig_val - 1)*100:.1f}%"
        else:
            orig_str = f"{orig_val:,}"
            exp_str = f"{exp_val:,}"
            if orig_val == 0:
                improvement = "N/A" if exp_val == 0 else "∞"
            else:
                improvement = f"{(exp_val/orig_val - 1)*100:.1f}x"

        print(f"{label:<25} {orig_str:<15} {exp_str:<15} {improvement:<15}")

    print(f"\nCompression Methods (Original):")
    for method, count in original_stats.get("compression_methods", {}).items():
        pct = count / original_stats["total_entries"] * 100
        print(f"  {method}: {count:,} ({pct:.1f}%)")

    print(f"\nCompression Methods (Expanded):")
    for method, count in expanded_stats.get("compression_methods", {}).items():
        pct = count / expanded_stats["total_entries"] * 100
        print(f"  {method}: {count:,} ({pct:.1f}%)")


def main():
    """Main analysis function."""

    print("Analyzing AURA test trace datasets...")

    # Analyze all trace directories
    directories = [
        "data/traces/test_traces", 
        "data/traces/improved_test_traces", 
        "data/traces/expanded_test_traces"
    ]

    results = {}
    for directory in directories:
        print(f"\nAnalyzing {directory}...")
        results[directory] = analyze_trace_directory(directory)

        if "error" not in results[directory]:
            stats = results[directory]
            print(f"  Users: {stats['total_users']}")
            print(f"  Entries: {stats['total_entries']:,}")
            print(f"  Avg compression ratio: {stats['avg_compression_ratio']:.3f}")
            print(f"  Avg latency: {stats['avg_latency_ms']:.3f}ms")
            print(f"  Success rate: {stats['success_rate']:.1%}")

    # Compare original vs expanded
    if "data/traces/test_traces" in results and "data/traces/expanded_test_traces" in results:
        print_comparison(results["data/traces/test_traces"], results["data/traces/expanded_test_traces"])

    # Save detailed results
    with open("trace_analysis_results.json", 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print("\nDetailed results saved to trace_analysis_results.json")


if __name__ == "__main__":
    main()