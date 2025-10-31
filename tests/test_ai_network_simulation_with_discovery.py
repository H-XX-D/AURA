#!/usr/bin/env python3
"""
AI-to-AI Network Traffic Simulation WITH Template Discovery

This version demonstrates the INTENDED behavior:
1. First pass: Discover templates from initial traffic
2. Add templates to library and persist to SQLite
3. Second pass: Use discovered templates with partial matching
4. Show bandwidth savings improve as templates are learned

This is how AURA is SUPPOSED to work in production.
"""

import sys
import time
import json
import random
import statistics
from pathlib import Path
from typing import Dict, List, Tuple, Any
from dataclasses import dataclass, asdict
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aura_compression.compressor_refactored import ProductionHybridCompressor
from aura_compression.enums import CompressionMethod
from aura_compression.discovery import TemplateDiscoveryEngine


@dataclass
class SimulationPhaseStats:
    """Statistics for one phase of simulation"""
    phase_name: str
    total_messages: int
    total_bytes_uncompressed: int
    total_bytes_compressed: int
    compression_ratio: float
    bandwidth_saved_percent: float
    avg_compression_time_ms: float
    method_usage: Dict[str, int]
    templates_in_library: int
    partial_match_count: int
    full_match_count: int


class AIMessageGenerator:
    """Generates realistic but CONSISTENT AI messages for template discovery"""

    # Simplified templates that will be discoverable
    TEMPLATES = [
        # OpenAI style
        '{{"id": "chatcmpl-{}", "object": "chat.completion", "model": "gpt-4", "choices": [{{"message": {{"role": "assistant", "content": "{}"}}, "finish_reason": "stop"}}], "usage": {{"prompt_tokens": {}, "completion_tokens": {}, "total_tokens": {}}}}}',

        # Claude style
        '{{"id": "msg-{}", "type": "message", "role": "assistant", "content": "{}", "model": "claude-3-opus", "stop_reason": "end_turn", "usage": {{"input_tokens": {}, "output_tokens": {}}}}}',

        # Status update
        '{{"status": "{}", "message": "{}", "timestamp": {}, "request_id": "req-{}"}}',

        # Error response
        '{{"error": {{"message": "{}", "type": "rate_limit_error", "code": "429"}}, "request_id": "req-{}"}}',

        # Function calling
        '{{"id": "msg-{}", "type": "message", "role": "assistant", "content": [{{"type": "tool_use", "id": "tool-{}", "name": "{}", "input": {{"query": "{}", "limit": {}}}}}], "model": "claude-3-opus"}}',
    ]

    CONTENT_SAMPLES = [
        "The implementation should use a binary search tree for O(log n) lookup time.",
        "Based on the error logs, the issue appears to be a race condition in the thread pool executor.",
        "Here's the refactored code with improved error handling and type safety.",
        "The API request failed due to rate limiting. Retry with exponential backoff.",
        "Analysis complete. Found 3 critical vulnerabilities and 12 warnings in the codebase.",
        "The neural network achieved 94.3% accuracy on the validation set after 50 epochs.",
        "Database query optimized. Execution time reduced from 2.3s to 0.15s.",
        "Parsing JSON response from external API. Schema validation passed.",
        "Memory usage: 2.4GB. CPU utilization: 34%. No bottlenecks detected.",
        "Deployment successful to production environment. Health checks passing.",
    ]

    FUNCTION_NAMES = ["search_database", "execute_query", "analyze_code", "generate_report"]
    STATUS_VALUES = ["processing", "completed", "pending", "failed"]

    def generate_message(self) -> str:
        """Generate a message from one of the templates"""
        template = random.choice(self.TEMPLATES)

        msg_id = ''.join(random.choices('0123456789abcdef', k=12))
        content = random.choice(self.CONTENT_SAMPLES)
        prompt_tokens = random.randint(50, 500)
        completion_tokens = random.randint(20, 300)
        total_tokens = prompt_tokens + completion_tokens
        status = random.choice(self.STATUS_VALUES)
        error_msg = "Rate limit exceeded - please retry after 60 seconds"
        tool_id = str(random.randint(1000, 9999))
        function_name = random.choice(self.FUNCTION_NAMES)
        query = "SELECT * FROM users WHERE active = true"
        limit = random.randint(10, 100)
        timestamp = int(time.time())
        req_id = ''.join(random.choices('0123456789abcdef', k=8))

        try:
            msg = template.format(
                msg_id, content, prompt_tokens, completion_tokens, total_tokens,
                msg_id, status, error_msg, timestamp, req_id,
                tool_id, function_name, query, limit
            )
            return msg
        except (IndexError, KeyError):
            # Simplified version if format fails
            return f'{{"id": "{msg_id}", "content": "{content}"}}'

    def generate_batch(self, count: int) -> List[str]:
        """Generate a batch of messages"""
        return [self.generate_message() for _ in range(count)]


def run_simulation_with_learning(num_messages_per_phase: int = 300):
    """
    Run simulation in 3 phases to show progressive learning:

    Phase 1: COLD START - No templates, poor compression
    Phase 2: DISCOVER - Learn templates from Phase 1 messages
    Phase 3: WARM - Use discovered templates, better compression
    """
    print(f"\n{'#'*80}")
    print(f"AI-TO-AI SIMULATION WITH TEMPLATE DISCOVERY")
    print(f"{'#'*80}\n")

    print("This simulation demonstrates AURA's intended behavior:")
    print("  Phase 1: Cold start (no templates)")
    print("  Phase 2: Discover templates from traffic")
    print("  Phase 3: Use discovered templates (partial matching)\n")

    generator = AIMessageGenerator()
    results = []

    # ========================================================================
    # PHASE 1: COLD START
    # ========================================================================
    print(f"{'='*80}")
    print(f"PHASE 1: COLD START (No Templates)")
    print(f"{'='*80}\n")

    compressor = ProductionHybridCompressor(
        binary_advantage_threshold=1.01,
        min_compression_size=10,
        enable_aura=False,
        enable_audit_logging=False,
        template_cache_size=256,
        enable_scorer=False,
        template_cache_dir=".aura_cache_simulation"
    )

    print(f"Generating {num_messages_per_phase} messages...")
    phase1_messages = generator.generate_batch(num_messages_per_phase)

    print(f"Compressing with NO templates...")
    phase1_stats = compress_batch(compressor, phase1_messages, "Phase 1")
    results.append(phase1_stats)

    print(f"\nPhase 1 Results:")
    print(f"  Compression ratio: {phase1_stats.compression_ratio:.3f}:1")
    print(f"  Bandwidth saved: {phase1_stats.bandwidth_saved_percent:.1f}%")
    print(f"  Primary method: {max(phase1_stats.method_usage, key=phase1_stats.method_usage.get)}")
    print(f"  Templates in library: {phase1_stats.templates_in_library}")
    print(f"  Full matches: {phase1_stats.full_match_count}")
    print(f"  Partial matches: {phase1_stats.partial_match_count}")

    # ========================================================================
    # PHASE 2: TEMPLATE DISCOVERY
    # ========================================================================
    print(f"\n{'='*80}")
    print(f"PHASE 2: TEMPLATE DISCOVERY")
    print(f"{'='*80}\n")

    print(f"Discovering templates from {len(phase1_messages)} messages...")

    # Use template discovery engine
    discovery_engine = TemplateDiscoveryEngine(
        min_frequency=3,  # Need at least 3 occurrences
        compression_threshold=1.1,  # Must save at least 10%
        similarity_threshold=0.7,  # Clustering threshold
        starting_template_id=200,
        max_template_id=255
    )

    discovered_templates = discovery_engine.discover_templates(phase1_messages)

    print(f"Discovered {len(discovered_templates)} templates\n")

    if discovered_templates:
        print("Top 5 discovered templates:")
        for i, template in enumerate(discovered_templates[:5], 1):
            print(f"  {i}. Pattern: {template.pattern[:80]}...")
            print(f"     Frequency: {template.frequency}, Savings: {template.compression_ratio:.2f}x")

    # Add discovered templates to compressor
    lib = compressor._template_service.template_manager.template_library
    template_id = 1
    for template in discovered_templates:
        lib.add(template_id, template.pattern)
        template_id += 1

    # Sync to SQLite
    print(f"\nSyncing {len(discovered_templates)} templates to SQLite...")
    compressor._template_service.sync_template_store()

    print(f"Templates persisted to: {compressor._template_service.template_store_path}")

    # ========================================================================
    # PHASE 3: WARM START (WITH TEMPLATES)
    # ========================================================================
    print(f"\n{'='*80}")
    print(f"PHASE 3: WARM START (With Discovered Templates)")
    print(f"{'='*80}\n")

    # Generate NEW messages (same patterns, different data)
    print(f"Generating {num_messages_per_phase} NEW messages...")
    phase3_messages = generator.generate_batch(num_messages_per_phase)

    print(f"Compressing with {len(discovered_templates)} templates...")
    phase3_stats = compress_batch(compressor, phase3_messages, "Phase 3")
    results.append(phase3_stats)

    print(f"\nPhase 3 Results:")
    print(f"  Compression ratio: {phase3_stats.compression_ratio:.3f}:1")
    print(f"  Bandwidth saved: {phase3_stats.bandwidth_saved_percent:.1f}%")
    print(f"  Primary method: {max(phase3_stats.method_usage, key=phase3_stats.method_usage.get) if phase3_stats.method_usage else 'None'}")
    print(f"  Templates in library: {phase3_stats.templates_in_library}")
    print(f"  Full matches: {phase3_stats.full_match_count}")
    print(f"  Partial matches: {phase3_stats.partial_match_count}")

    # ========================================================================
    # COMPARISON
    # ========================================================================
    print(f"\n{'='*80}")
    print(f"COMPARISON: COLD START vs WARM START")
    print(f"{'='*80}\n")

    improvement_ratio = phase3_stats.compression_ratio / phase1_stats.compression_ratio
    bandwidth_improvement = phase3_stats.bandwidth_saved_percent - phase1_stats.bandwidth_saved_percent

    print(f"Compression Ratio:")
    print(f"  Phase 1 (cold): {phase1_stats.compression_ratio:.3f}:1")
    print(f"  Phase 3 (warm): {phase3_stats.compression_ratio:.3f}:1")
    print(f"  Improvement: {improvement_ratio:.2f}x better\n")

    print(f"Bandwidth Saved:")
    print(f"  Phase 1 (cold): {phase1_stats.bandwidth_saved_percent:.1f}%")
    print(f"  Phase 3 (warm): {phase3_stats.bandwidth_saved_percent:.1f}%")
    print(f"  Improvement: {bandwidth_improvement:+.1f}%\n")

    print(f"Template Matching:")
    print(f"  Phase 1: {phase1_stats.full_match_count} full + {phase1_stats.partial_match_count} partial")
    print(f"  Phase 3: {phase3_stats.full_match_count} full + {phase3_stats.partial_match_count} partial")
    print(f"  Improvement: {phase3_stats.full_match_count + phase3_stats.partial_match_count - phase1_stats.full_match_count - phase1_stats.partial_match_count} more matches\n")

    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = f"ai_simulation_with_discovery_{timestamp}.json"

    results_data = {
        "timestamp": timestamp,
        "num_messages_per_phase": num_messages_per_phase,
        "phases": {
            "phase1_cold": asdict(phase1_stats),
            "phase3_warm": asdict(phase3_stats),
        },
        "improvement": {
            "compression_ratio_multiplier": improvement_ratio,
            "bandwidth_saved_improvement_percent": bandwidth_improvement,
        },
        "templates_discovered": len(discovered_templates),
    }

    with open(results_file, 'w') as f:
        json.dump(results_data, f, indent=2)

    print(f"Results saved to: {results_file}\n")

    if improvement_ratio > 1.5:
        print("✅ EXCELLENT: Template discovery improved compression by >50%!")
    elif improvement_ratio > 1.2:
        print("✅ GOOD: Template discovery improved compression by >20%")
    elif improvement_ratio > 1.0:
        print("⚠️  MODEST: Template discovery showed some improvement")
    else:
        print("❌ PROBLEM: Template discovery did not improve compression")

    return results_data


def compress_batch(compressor, messages: List[str], phase_name: str) -> SimulationPhaseStats:
    """Compress a batch of messages and collect statistics"""
    total_uncompressed = 0
    total_compressed = 0
    compression_times = []
    method_usage = {}
    full_matches = 0
    partial_matches = 0

    for i, message in enumerate(messages):
        try:
            t0 = time.perf_counter()
            compressed, method, metadata = compressor.compress(message)
            compression_time = (time.perf_counter() - t0) * 1000

            compression_times.append(compression_time)
            method_usage[method.name] = method_usage.get(method.name, 0) + 1

            original_size = len(message.encode('utf-8'))
            compressed_size = len(compressed)

            total_uncompressed += original_size
            total_compressed += compressed_size

            # Track template matches
            if metadata.get('partial_match'):
                partial_matches += 1
            elif method == CompressionMethod.BINARY_SEMANTIC:
                full_matches += 1

        except Exception as e:
            print(f"Error compressing message {i}: {e}")

    # Get template library size
    template_lib = compressor._template_service.template_manager.template_library
    templates_count = len(template_lib.templates)

    ratio = total_uncompressed / total_compressed if total_compressed > 0 else 1.0
    bandwidth_saved = ((total_uncompressed - total_compressed) / total_uncompressed) * 100 if total_uncompressed > 0 else 0.0

    return SimulationPhaseStats(
        phase_name=phase_name,
        total_messages=len(messages),
        total_bytes_uncompressed=total_uncompressed,
        total_bytes_compressed=total_compressed,
        compression_ratio=ratio,
        bandwidth_saved_percent=bandwidth_saved,
        avg_compression_time_ms=statistics.mean(compression_times) if compression_times else 0.0,
        method_usage=method_usage,
        templates_in_library=templates_count,
        partial_match_count=partial_matches,
        full_match_count=full_matches,
    )


if __name__ == "__main__":
    run_simulation_with_learning(num_messages_per_phase=300)
