#!/usr/bin/env python3
"""
60-Second AI Network Simulation with Template Discovery
Runs 3 times to show consistent progressive learning behavior
"""

import sys
import time
import json
import random
import statistics
from pathlib import Path
from typing import Dict, List, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aura_compression.compressor_refactored import ProductionHybridCompressor
from aura_compression.enums import CompressionMethod
from aura_compression.discovery import TemplateDiscoveryEngine


@dataclass
class RunStats:
    """Statistics for one simulation run"""
    run_id: int
    duration_seconds: float
    total_messages: int
    templates_discovered: int
    templates_used: int

    # Phase 1 (cold)
    phase1_messages: int
    phase1_compression_ratio: float
    phase1_bandwidth_saved: float
    phase1_matches: int

    # Phase 2 (warm)
    phase2_messages: int
    phase2_compression_ratio: float
    phase2_bandwidth_saved: float
    phase2_matches: int

    # Improvement
    improvement_ratio: float
    improvement_bandwidth: float


class AIMessageGenerator:
    """Generates consistent AI messages for template discovery"""

    TEMPLATES = [
        '{{"id": "chatcmpl-{}", "object": "chat.completion", "model": "gpt-4", "choices": [{{"message": {{"role": "assistant", "content": "{}"}}, "finish_reason": "stop"}}], "usage": {{"prompt_tokens": {}, "completion_tokens": {}, "total_tokens": {}}}}}',
        '{{"id": "msg-{}", "type": "message", "role": "assistant", "content": "{}", "model": "claude-3-opus", "stop_reason": "end_turn", "usage": {{"input_tokens": {}, "output_tokens": {}}}}}',
        '{{"status": "{}", "message": "{}", "timestamp": {}, "request_id": "req-{}"}}',
        '{{"error": {{"message": "{}", "type": "rate_limit_error", "code": "429"}}, "request_id": "req-{}"}}',
    ]

    CONTENT_SAMPLES = [
        "The implementation uses O(log n) binary search for optimal lookup time.",
        "Based on error logs, this appears to be a race condition in the thread pool.",
        "Refactored code now includes proper error handling and type safety.",
        "API request failed due to rate limiting. Retry with exponential backoff.",
        "Analysis complete. Found 3 critical vulnerabilities in the codebase.",
        "Neural network achieved 94.3% accuracy on validation set.",
        "Database query optimized. Execution time reduced from 2.3s to 0.15s.",
        "Parsing JSON response. Schema validation passed successfully.",
        "Memory usage: 2.4GB. CPU: 34%. No bottlenecks detected.",
        "Deployment successful. All health checks passing.",
    ]

    def generate_message(self) -> str:
        template = random.choice(self.TEMPLATES)
        msg_id = ''.join(random.choices('0123456789abcdef', k=12))
        content = random.choice(self.CONTENT_SAMPLES)
        tokens = [random.randint(50, 500), random.randint(20, 300)]
        status = random.choice(["processing", "completed", "pending", "failed"])
        timestamp = int(time.time())
        req_id = ''.join(random.choices('0123456789abcdef', k=8))
        error = "Rate limit exceeded"

        try:
            return template.format(msg_id, content, tokens[0], tokens[1], sum(tokens),
                                 status, error, timestamp, req_id)
        except:
            return f'{{"id": "{msg_id}", "content": "{content}"}}'

    def generate_traffic(self, duration_seconds: int, rate: float = 10.0) -> List[str]:
        """Generate traffic for N seconds at specified rate (messages/second)"""
        count = int(duration_seconds * rate)
        return [self.generate_message() for _ in range(count)]


def compress_batch(compressor, messages: List[str]) -> Tuple[Dict, List]:
    """Compress batch and return stats"""
    total_uncompressed = 0
    total_compressed = 0
    method_usage = {}
    matches = 0
    times = []

    for msg in messages:
        try:
            t0 = time.perf_counter()
            compressed, method, metadata = compressor.compress(msg)
            comp_time = (time.perf_counter() - t0) * 1000

            times.append(comp_time)
            method_usage[method.name] = method_usage.get(method.name, 0) + 1

            total_uncompressed += len(msg.encode('utf-8'))
            total_compressed += len(compressed)

            if method == CompressionMethod.BINARY_SEMANTIC:
                matches += 1

        except Exception as e:
            print(f"Error: {e}")

    ratio = total_uncompressed / total_compressed if total_compressed > 0 else 1.0
    bw_saved = ((total_uncompressed - total_compressed) / total_uncompressed) * 100 if total_uncompressed > 0 else 0.0

    return {
        'messages': len(messages),
        'ratio': ratio,
        'bandwidth_saved': bw_saved,
        'matches': matches,
        'avg_time_ms': statistics.mean(times) if times else 0.0,
        'method_usage': method_usage
    }, times


def run_60s_simulation(run_id: int) -> RunStats:
    """Run one 60-second simulation"""
    print(f"\n{'='*80}")
    print(f"RUN #{run_id} - 60 Second AI-to-AI Network Simulation")
    print(f"{'='*80}\n")

    generator = AIMessageGenerator()
    start_time = time.time()

    # Phase 1: Cold start (30 seconds)
    print("Phase 1: COLD START (30s, no templates)...")
    compressor = ProductionHybridCompressor(
        binary_advantage_threshold=1.01,
        enable_audit_logging=False,
        template_cache_dir=f".aura_cache_run{run_id}"
    )

    phase1_messages = generator.generate_traffic(30, rate=10.0)
    print(f"  Generated {len(phase1_messages)} messages")

    phase1_stats, _ = compress_batch(compressor, phase1_messages)
    print(f"  Compression: {phase1_stats['ratio']:.3f}:1")
    print(f"  Matches: {phase1_stats['matches']}")

    # Discovery phase
    print("\nDiscovery: Learning templates...")
    discovery = TemplateDiscoveryEngine(
        min_frequency=3,
        compression_threshold=1.1,
        similarity_threshold=0.7
    )

    templates = discovery.discover_templates(phase1_messages)
    print(f"  Discovered {len(templates)} templates")

    # Add templates
    lib = compressor._template_service.template_manager.template_library
    for tid, t in enumerate(templates, start=1):
        lib.add(tid, t.pattern)

    compressor._template_service.sync_template_store()
    print(f"  Added {len(templates)} templates to library")

    # Phase 2: Warm start (30 seconds)
    print("\nPhase 2: WARM START (30s, with templates)...")
    phase2_messages = generator.generate_traffic(30, rate=10.0)
    print(f"  Generated {len(phase2_messages)} messages")

    phase2_stats, _ = compress_batch(compressor, phase2_messages)
    print(f"  Compression: {phase2_stats['ratio']:.3f}:1")
    print(f"  Matches: {phase2_stats['matches']}")

    duration = time.time() - start_time

    # Calculate improvement
    improvement_ratio = phase2_stats['ratio'] / phase1_stats['ratio'] if phase1_stats['ratio'] > 0 else 1.0
    improvement_bw = phase2_stats['bandwidth_saved'] - phase1_stats['bandwidth_saved']

    stats = RunStats(
        run_id=run_id,
        duration_seconds=duration,
        total_messages=len(phase1_messages) + len(phase2_messages),
        templates_discovered=len(templates),
        templates_used=phase2_stats['matches'],

        phase1_messages=phase1_stats['messages'],
        phase1_compression_ratio=phase1_stats['ratio'],
        phase1_bandwidth_saved=phase1_stats['bandwidth_saved'],
        phase1_matches=phase1_stats['matches'],

        phase2_messages=phase2_stats['messages'],
        phase2_compression_ratio=phase2_stats['ratio'],
        phase2_bandwidth_saved=phase2_stats['bandwidth_saved'],
        phase2_matches=phase2_stats['matches'],

        improvement_ratio=improvement_ratio,
        improvement_bandwidth=improvement_bw
    )

    print(f"\nRun #{run_id} Complete:")
    print(f"  Duration: {duration:.1f}s")
    print(f"  Improvement: {improvement_ratio:.2f}x compression ratio")
    print(f"  Bandwidth: {improvement_bw:+.1f}% improvement")

    return stats


def run_multi_simulation():
    """Run 3 × 60-second simulations"""
    print(f"\n{'#'*80}")
    print(f"60-SECOND AI NETWORK SIMULATION - 3 RUNS")
    print(f"{'#'*80}")
    print("\nDemonstrating progressive template learning:")
    print("  - Phase 1: Cold start (30s) - no templates")
    print("  - Discovery: Learn patterns from traffic")
    print("  - Phase 2: Warm start (30s) - use templates")
    print("  - Measure improvement\n")

    all_stats = []

    for run in range(1, 4):
        stats = run_60s_simulation(run)
        all_stats.append(stats)

        if run < 3:
            print("\nWaiting 2 seconds before next run...\n")
            time.sleep(2)

    # Aggregate results
    print(f"\n{'='*80}")
    print(f"AGGREGATE RESULTS - 3 RUNS × 60 SECONDS")
    print(f"{'='*80}\n")

    total_messages = sum(s.total_messages for s in all_stats)
    avg_templates = statistics.mean([s.templates_discovered for s in all_stats])
    avg_improvement_ratio = statistics.mean([s.improvement_ratio for s in all_stats])
    avg_improvement_bw = statistics.mean([s.improvement_bandwidth for s in all_stats])

    # Phase 1 averages
    avg_phase1_ratio = statistics.mean([s.phase1_compression_ratio for s in all_stats])
    avg_phase1_bw = statistics.mean([s.phase1_bandwidth_saved for s in all_stats])
    avg_phase1_matches = statistics.mean([s.phase1_matches for s in all_stats])

    # Phase 2 averages
    avg_phase2_ratio = statistics.mean([s.phase2_compression_ratio for s in all_stats])
    avg_phase2_bw = statistics.mean([s.phase2_bandwidth_saved for s in all_stats])
    avg_phase2_matches = statistics.mean([s.phase2_matches for s in all_stats])

    print(f"Total Messages: {total_messages:,}")
    print(f"Average Templates Discovered: {avg_templates:.1f}")
    print(f"Average Template Usage: {avg_phase2_matches:.1f} matches ({avg_phase2_matches/300*100:.1f}%)\n")

    print("Phase 1 (Cold Start) Averages:")
    print(f"  Compression Ratio: {avg_phase1_ratio:.3f}:1")
    print(f"  Bandwidth Saved: {avg_phase1_bw:.1f}%")
    print(f"  Template Matches: {avg_phase1_matches:.0f}\n")

    print("Phase 2 (Warm Start) Averages:")
    print(f"  Compression Ratio: {avg_phase2_ratio:.3f}:1")
    print(f"  Bandwidth Saved: {avg_phase2_bw:.1f}%")
    print(f"  Template Matches: {avg_phase2_matches:.0f}\n")

    print("Average Improvement:")
    print(f"  Compression Ratio: {avg_improvement_ratio:.2f}x better")
    print(f"  Bandwidth Saved: {avg_improvement_bw:+.1f}%")
    print(f"  Match Rate: {avg_phase2_matches:.0f} → {(avg_phase2_matches/300)*100:.1f}% usage\n")

    # Individual run breakdown
    print("Individual Run Results:")
    print(f"{'Run':<6} {'Phase1':<12} {'Phase2':<12} {'Improvement':<15} {'Templates':<10}")
    print("-" * 65)
    for s in all_stats:
        print(f"#{s.run_id:<5} {s.phase1_compression_ratio:>6.3f}:1     {s.phase2_compression_ratio:>6.3f}:1     {s.improvement_ratio:>7.2f}x        {s.templates_discovered:>3} patterns")

    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = f"simulation_60s_{timestamp}.json"

    results = {
        "timestamp": timestamp,
        "duration_per_run": "60 seconds (30s cold + 30s warm)",
        "num_runs": 3,
        "summary": {
            "total_messages": total_messages,
            "avg_templates_discovered": avg_templates,
            "avg_phase1_ratio": avg_phase1_ratio,
            "avg_phase2_ratio": avg_phase2_ratio,
            "avg_improvement_ratio": avg_improvement_ratio,
            "avg_improvement_bandwidth": avg_improvement_bw,
            "avg_template_usage_percent": (avg_phase2_matches/300)*100
        },
        "runs": [asdict(s) for s in all_stats]
    }

    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to: {results_file}")

    # Final assessment
    if avg_improvement_ratio >= 1.05:
        print("\n✅ SUCCESS: Template discovery showed measurable improvement!")
    elif avg_improvement_ratio >= 1.02:
        print("\n✅ GOOD: Template discovery showed modest improvement")
    else:
        print("\n⚠️  PARTIAL: Improvement is marginal")

    print(f"{'='*80}\n")

    return results


if __name__ == "__main__":
    run_multi_simulation()
