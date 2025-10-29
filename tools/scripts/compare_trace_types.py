#!/usr/bin/env python3
"""
Compare Algorithmic vs Network-Aware Traces

Shows the dramatic difference between measuring just compression algorithm
performance vs. realistic end-to-end network performance.
"""

import json
import statistics
from pathlib import Path
from typing import Dict, List, Any


def load_trace_sample(trace_file: str, max_entries: int = 5) -> List[Dict[str, Any]]:
    """Load a sample of trace entries."""
    entries = []
    try:
        with open(trace_file, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                if i >= max_entries:
                    break
                entries.append(json.loads(line.strip()))
    except Exception as e:
        print(f"Error loading {trace_file}: {e}")
    return entries


def analyze_algorithmic_traces() -> Dict[str, Any]:
    """Analyze the original algorithmic-only traces."""
    trace_file = "expanded_test_traces/user_1_traces.jsonl"
    entries = load_trace_sample(trace_file, 20)

    if not entries:
        return {"error": "No algorithmic traces found"}

    latencies = [entry.get("latency_ms", 0) for entry in entries]

    return {
        "type": "algorithmic_only",
        "description": "Original traces - compression algorithm only",
        "sample_size": len(entries),
        "avg_latency_ms": statistics.mean(latencies) if latencies else 0,
        "min_latency_ms": min(latencies) if latencies else 0,
        "max_latency_ms": max(latencies) if latencies else 0,
        "latency_range": f"{min(latencies):.3f} - {max(latencies):.3f}ms" if latencies else "N/A",
        "includes_network": False,
        "includes_connection_setup": False,
        "includes_protocol_overhead": False,
        "realistic_network_conditions": False
    }


def analyze_network_traces() -> List[Dict[str, Any]]:
    """Analyze network-aware traces across different network types."""
    network_types = ["wifi_fast", "lte_4g", "satellite", "fiber"]
    results = []

    for network_type in network_types:
        summary_file = f"network_simulation_traces/{network_type}/network_summary.json"

        try:
            with open(summary_file, 'r', encoding='utf-8') as f:
                summary = json.load(f)

            # Load a sample trace to show detailed timing
            trace_file = f"network_simulation_traces/{network_type}/user_1_traces.jsonl"
            sample_entries = load_trace_sample(trace_file, 3)

            result = {
                "type": "network_aware",
                "network_type": network_type,
                "description": f"Network-aware traces - {summary.get('network_profile', {}).get('bandwidth_mbps', 0)} Mbps, {summary.get('network_profile', {}).get('base_latency_ms', 0)}ms base latency",
                "sample_size": summary.get("total_entries", 0),
                "avg_compression_latency_ms": summary.get("avg_compression_latency_ms", 0),
                "avg_network_latency_ms": summary.get("avg_network_latency_ms", 0),
                "avg_end_to_end_latency_ms": summary.get("avg_end_to_end_latency_ms", 0),
                "min_end_to_end_latency_ms": summary.get("min_end_to_end_latency_ms", 0),
                "max_end_to_end_latency_ms": summary.get("max_end_to_end_latency_ms", 0),
                "end_to_end_range": f"{summary.get('min_end_to_end_latency_ms', 0):.1f} - {summary.get('max_end_to_end_latency_ms', 0):.1f}ms",
                "includes_network": True,
                "includes_connection_setup": True,
                "includes_protocol_overhead": True,
                "realistic_network_conditions": True,
                "bandwidth_mbps": summary.get("network_profile", {}).get("bandwidth_mbps", 0),
                "base_latency_ms": summary.get("network_profile", {}).get("base_latency_ms", 0),
                "packet_loss_rate": summary.get("network_profile", {}).get("packet_loss_rate", 0),
                "sample_detailed_timing": sample_entries[0] if sample_entries else None
            }

            results.append(result)

        except Exception as e:
            print(f"Error analyzing {network_type}: {e}")

    return results


def print_comparison():
    """Print a comprehensive comparison between trace types."""

    print("=" * 100)
    print("ALGORITHMIC vs NETWORK-AWARE TRACE COMPARISON")
    print("=" * 100)
    print()

    # Analyze algorithmic traces
    algo_results = analyze_algorithmic_traces()

    # Analyze network traces
    network_results = analyze_network_traces()

    print("📊 ALGORITHMIC-ONLY TRACES (Original)")
    print("-" * 50)
    print(f"Description: {algo_results.get('description', 'N/A')}")
    print(f"Sample Size: {algo_results.get('sample_size', 0)} entries")
    print(f"Average Latency: {algo_results.get('avg_latency_ms', 0):.3f}ms")
    print(f"Latency Range: {algo_results.get('latency_range', 'N/A')}")
    print(f"Includes Network Conditions: {algo_results.get('realistic_network_conditions', False)}")
    print(f"Includes Connection Setup: {algo_results.get('includes_connection_setup', False)}")
    print(f"Includes Protocol Overhead: {algo_results.get('includes_protocol_overhead', False)}")
    print()

    print("🌐 NETWORK-AWARE TRACES (New)")
    print("-" * 50)

    for result in network_results:
        print(f"\nNetwork: {result['network_type'].upper()}")
        print(f"  Description: {result['description']}")
        print(f"  Sample Size: {result['sample_size']} entries")
        print(f"  Compression Latency: {result['avg_compression_latency_ms']:.3f}ms")
        print(f"  Network Latency: {result['avg_network_latency_ms']:.1f}ms")
        print(f"  End-to-End Latency: {result['avg_end_to_end_latency_ms']:.1f}ms")
        print(f"  End-to-End Range: {result['end_to_end_range']}")
        print(f"  Bandwidth: {result['bandwidth_mbps']} Mbps")
        print(f"  Base Latency: {result['base_latency_ms']}ms")
        print(f"  Packet Loss Rate: {result['packet_loss_rate']:.1%}")

        # Show detailed timing breakdown for first network type
        if result['network_type'] == 'wifi_fast' and result.get('sample_detailed_timing'):
            timing = result['sample_detailed_timing']
            print("  Sample Timing Breakdown:")
            network_timing = timing.get('network_timing', {})
            print(f"    • Connection Setup: {network_timing.get('connection_setup_ms', 0):.1f}ms")
            print(f"    • SSL Handshake: {network_timing.get('ssl_handshake_ms', 0):.1f}ms")
            print(f"    • DNS Resolution: {network_timing.get('dns_resolution_ms', 0):.1f}ms")
            print(f"    • TCP Handshake: {network_timing.get('tcp_handshake_ms', 0):.1f}ms")
            print(f"    • Data Transmission: {network_timing.get('transmission_ms', 0):.3f}ms")
            print(f"    • Protocol Overhead: {network_timing.get('protocol_overhead_ms', 0):.1f}ms")
            print(f"    • Total Network: {timing.get('total_network_latency_ms', 0):.1f}ms")
            print(f"    • End-to-End: {timing.get('total_end_to_end_latency_ms', 0):.1f}ms")

    print()
    print("🎯 KEY INSIGHTS")
    print("-" * 50)

    if network_results:
        fastest_network = min(network_results, key=lambda x: x['avg_end_to_end_latency_ms'])
        slowest_network = max(network_results, key=lambda x: x['avg_end_to_end_latency_ms'])

        algo_latency = algo_results.get('avg_latency_ms', 0)
        network_latency = fastest_network['avg_end_to_end_latency_ms']

        print(f"• Algorithm-only traces show: {algo_latency:.3f}ms average latency")
        print(f"• Fastest network (Fiber): {fastest_network['avg_end_to_end_latency_ms']:.1f}ms end-to-end")
        print(f"• Slowest network (Satellite): {slowest_network['avg_end_to_end_latency_ms']:.1f}ms end-to-end")
        print(f"• Network dominates latency: {network_latency/algo_latency:.0f}x more than algorithm alone")
        print("• Real applications need network-aware performance testing")
    print()
    print("💡 RECOMMENDATIONS")
    print("-" * 50)
    print("• Use algorithmic traces for compression algorithm optimization")
    print("• Use network-aware traces for real-world performance testing")
    print("• Test across multiple network types for comprehensive coverage")
    print("• Consider network conditions in performance requirements")
    print("• Monitor both compression efficiency AND network transmission time")


if __name__ == "__main__":
    print_comparison()