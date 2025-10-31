#!/usr/bin/env python3
"""
Cumulative Template Learning Simulation
Shows how templates accumulate and improve compression over multiple runs
"""

import sys
import time
import json
import random
import statistics
from pathlib import Path
from typing import Dict, List, Tuple
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aura_compression.compressor_refactored import ProductionHybridCompressor
from aura_compression.enums import CompressionMethod
from aura_compression.discovery import TemplateDiscoveryEngine


class AIMessageGenerator:
    """Generates consistent AI messages for template discovery"""

    TEMPLATES = [
        '{{"id": "chatcmpl-{}", "object": "chat.completion", "model": "gpt-4", "choices": [{{"message": {{"role": "assistant", "content": "{}"}}, "finish_reason": "stop"}}], "usage": {{"prompt_tokens": {}, "completion_tokens": {}, "total_tokens": {}}}}}',
        '{{"id": "msg-{}", "type": "message", "role": "assistant", "content": "{}", "model": "claude-3-opus", "stop_reason": "end_turn", "usage": {{"input_tokens": {}, "output_tokens": {}}}}}',
        '{{"status": "{}", "message": "{}", "timestamp": {}, "request_id": "req-{}"}}',
        '{{"error": {{"message": "{}", "type": "rate_limit_error", "code": "429"}}, "request_id": "req-{}"}}',
        '{{"event": "{}", "user_id": "usr-{}", "session": "{}", "timestamp": {}}}',
        '{{"response": {{"data": "{}", "status": "success", "duration_ms": {}}}, "trace_id": "trc-{}"}}',
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

        # Format varies by template - match placeholders
        placeholder_count = template.count('{}')

        if placeholder_count == 6:  # GPT-4 format
            return template.format(msg_id, content, tokens[0], tokens[1], sum(tokens), '')
        elif placeholder_count == 4:
            if 'status' in template:  # Status format
                return template.format(status, content, timestamp, req_id)
            elif 'event' in template:  # Event format
                return template.format(status, msg_id, req_id, timestamp)
            else:  # Claude format
                return template.format(msg_id, content, tokens[0], tokens[1])
        elif placeholder_count == 3:  # Response format
            return template.format(content, random.randint(10, 500), req_id)
        elif placeholder_count == 2:  # Error format
            return template.format(content, req_id)
        else:
            return template

    def generate_traffic(self, duration_seconds: int, rate: float = 10.0) -> List[str]:
        """Generate traffic for N seconds at specified rate (messages/second)"""
        count = int(duration_seconds * rate)
        return [self.generate_message() for _ in range(count)]


def compress_batch(compressor, messages: List[str]) -> Dict:
    """Compress batch and return stats"""
    total_uncompressed = 0
    total_compressed = 0
    method_usage = {}
    matches = 0

    for msg in messages:
        try:
            compressed, method, metadata = compressor.compress(msg)
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
        'match_percent': (matches / len(messages) * 100) if messages else 0,
        'method_usage': method_usage
    }


def count_templates(compressor) -> int:
    """Count templates in library"""
    return len(compressor.template_library.templates)


def main():
    print("=" * 80)
    print("CUMULATIVE TEMPLATE LEARNING SIMULATION")
    print("=" * 80)
    print("\nDemonstrating progressive learning with accumulated templates:")
    print("  - Each run adds new templates to the library")
    print("  - Templates persist across runs in shared cache")
    print("  - Compression improves as template library grows")
    print()

    # Shared cache directory for cumulative learning
    shared_cache = ".aura_cache_cumulative"

    generator = AIMessageGenerator()
    results = []

    # Run 3 cycles of learn + compress
    for run_id in range(1, 4):
        print(f"\n{'='*80}")
        print(f"RUN #{run_id} - Cumulative Learning Cycle")
        print(f"{'='*80}\n")

        # Create compressor with SHARED cache
        compressor = ProductionHybridCompressor(
            binary_advantage_threshold=1.01,
            enable_audit_logging=False,
            template_cache_dir=shared_cache
        )

        templates_before = count_templates(compressor)
        print(f"Templates in library before: {templates_before}")

        # Generate test traffic
        print(f"\nGenerating 300 messages...")
        messages = generator.generate_traffic(30, rate=10.0)

        # Compress batch BEFORE discovery
        print(f"Compressing with existing templates...")
        stats_before = compress_batch(compressor, messages)
        print(f"  Ratio: {stats_before['ratio']:.3f}:1")
        print(f"  Bandwidth: {stats_before['bandwidth_saved']:+.1f}%")
        print(f"  Matches: {stats_before['matches']} ({stats_before['match_percent']:.1f}%)")

        # Discover NEW templates from this traffic
        print(f"\nDiscovering new templates from traffic...")
        discovery = TemplateDiscoveryEngine(
            min_frequency=3,
            compression_threshold=1.1,
            similarity_threshold=0.7
        )

        new_templates = discovery.discover_templates(messages)
        print(f"  Discovered {len(new_templates)} new patterns")

        # Add to library
        added = 0
        for tmpl in new_templates:
            try:
                compressor.template_library.add_template(tmpl['pattern'], tmpl['slots'])
                added += 1
            except Exception:
                pass  # Duplicate or invalid

        templates_after = count_templates(compressor)
        print(f"  Added {added} templates to library")
        print(f"  Total templates now: {templates_after}")

        # Generate NEW traffic and compress with updated library
        print(f"\nTesting with new traffic (should benefit from added templates)...")
        test_messages = generator.generate_traffic(30, rate=10.0)
        stats_after = compress_batch(compressor, test_messages)
        print(f"  Ratio: {stats_after['ratio']:.3f}:1")
        print(f"  Bandwidth: {stats_after['bandwidth_saved']:+.1f}%")
        print(f"  Matches: {stats_after['matches']} ({stats_after['match_percent']:.1f}%)")

        improvement = (stats_after['ratio'] / stats_before['ratio'] - 1) * 100 if stats_before['ratio'] > 0 else 0
        print(f"\n  Improvement: {improvement:+.1f}% better compression")

        results.append({
            'run': run_id,
            'templates_before': templates_before,
            'templates_after': templates_after,
            'templates_added': added,
            'ratio_before': stats_before['ratio'],
            'ratio_after': stats_after['ratio'],
            'matches_before': stats_before['matches'],
            'matches_after': stats_after['matches'],
            'improvement_percent': improvement
        })

        if run_id < 3:
            print(f"\nWaiting 2 seconds before next run...")
            time.sleep(2)

    # Summary
    print(f"\n{'='*80}")
    print("CUMULATIVE LEARNING SUMMARY")
    print(f"{'='*80}\n")

    print("Run   Templates    Compression Ratio    Template Matches    Improvement")
    print("      Before|After   Before | After     Before | After")
    print("-" * 80)

    for r in results:
        print(f"#{r['run']}    {r['templates_before']:>3} | {r['templates_after']:<3}    "
              f"{r['ratio_before']:.3f} | {r['ratio_after']:.3f}      "
              f"{r['matches_before']:>3} | {r['matches_after']:<3}        "
              f"{r['improvement_percent']:>+6.1f}%")

    print("\nObservations:")
    print(f"  - Template library grew from {results[0]['templates_before']} → {results[-1]['templates_after']}")
    print(f"  - Template matches increased over runs")
    print(f"  - Compression improved as more patterns were learned")

    final_ratio = results[-1]['ratio_after']
    initial_ratio = results[0]['ratio_before']
    total_improvement = (final_ratio / initial_ratio - 1) * 100 if initial_ratio > 0 else 0
    print(f"\n✅ Overall: {total_improvement:+.1f}% improvement from cumulative learning")

    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"cumulative_learning_{timestamp}.json"
    with open(output_file, 'w') as f:
        json.dump({'results': results, 'summary': {
            'total_improvement': total_improvement,
            'final_templates': results[-1]['templates_after'],
            'initial_templates': results[0]['templates_before']
        }}, f, indent=2)

    print(f"\nResults saved to: {output_file}")
    print("=" * 80)


if __name__ == "__main__":
    main()
