#!/usr/bin/env python3
"""
10x1-minute AI-to-AI Network Simulation
Tests template discovery and compression with new domain templates and looser thresholds
"""

import sys
import json
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aura_compression.compressor_refactored import ProductionHybridCompressor
from aura_compression.enums import CompressionMethod


class MessageGenerator:
    """Generate realistic AI-to-AI messages"""

    def __init__(self):
        self.msg_counter = 0

        # Realistic AI message templates (will be discovered)
        self.templates = [
            # Common API responses
            "Processing request... Status: {status}",
            "Query completed successfully in {time}ms",
            "Error: {error} - Please try again",
            "Data retrieved: {count} records found",
            "Model inference complete: confidence {conf}%",
            "Cache hit for key {key}",
            "Cache miss - fetching from database",
            "Authentication successful for user {user}",
            "Rate limit: {remaining} requests remaining",
            "Token usage: {input} input, {output} output tokens",

            # LLM-specific patterns
            "Generated response with {tokens} tokens",
            "Prompt processed in {time} seconds",
            "Model: {model} | Temperature: {temp}",
            "Finish reason: {reason}",
            "Completion ID: {id}",

            # System messages
            "Health check: All systems operational",
            "Service {service} is responding normally",
            "Latency p95: {latency}ms",
            "Queue depth: {depth} messages",
            "Worker {worker} processing batch {batch}",
        ]

        # Variable values
        self.statuses = ["success", "pending", "processing", "failed", "completed"]
        self.errors = ["timeout", "invalid_input", "rate_limited", "auth_failed", "not_found"]
        self.models = ["gpt-4", "gpt-3.5-turbo", "claude-3-opus", "claude-3-sonnet", "claude-3-haiku"]
        self.services = ["auth", "database", "cache", "queue", "inference"]
        self.finish_reasons = ["stop", "length", "content_filter", "function_call"]

    def generate_message(self) -> str:
        """Generate a single message"""
        import random

        self.msg_counter += 1
        template = random.choice(self.templates)

        # Fill in variables
        msg = template.format(
            status=random.choice(self.statuses),
            time=random.randint(10, 500),
            error=random.choice(self.errors),
            count=random.randint(0, 1000),
            conf=random.randint(75, 99),
            key=f"key_{random.randint(1000, 9999)}",
            user=f"user_{random.randint(100, 999)}",
            remaining=random.randint(0, 100),
            input=random.randint(50, 500),
            output=random.randint(100, 1000),
            tokens=random.randint(100, 1000),
            temp=round(random.uniform(0.1, 1.0), 1),
            model=random.choice(self.models),
            reason=random.choice(self.finish_reasons),
            id=f"msg_{self.msg_counter}_{random.randint(1000, 9999)}",
            service=random.choice(self.services),
            latency=random.randint(10, 200),
            depth=random.randint(0, 50),
            worker=f"worker_{random.randint(1, 10)}",
            batch=random.randint(1, 100),
        )

        return msg

    def generate_traffic_pattern(self, duration_seconds: int) -> List[tuple]:
        """Generate realistic traffic pattern with timing"""
        messages = []
        current_time = 0.0

        # Target ~5 messages per second
        target_rate = 5.0

        while current_time < duration_seconds:
            # Exponential distribution for inter-arrival times
            import random
            interval = random.expovariate(target_rate)
            current_time += interval

            if current_time < duration_seconds:
                messages.append((current_time, self.generate_message()))

        return messages


class NetworkSimulator:
    """Simulate network compression/decompression"""

    def __init__(self):
        self.compressor = ProductionHybridCompressor()
        self.stats = {
            'messages': 0,
            'errors': 0,
            'uncompressed_bytes': 0,
            'compressed_bytes': 0,
            'transferred_bytes': 0,
            'compression_times': [],
            'decompression_times': [],
            'methods_used': {},
        }

    def send_message(self, message: str) -> Dict[str, Any]:
        """Compress and transmit message"""
        self.stats['messages'] += 1

        # Measure compression
        start = time.perf_counter()
        compressed_data, method, extra_metadata = self.compressor.compress(message)
        comp_time = (time.perf_counter() - start) * 1000  # ms

        self.stats['compression_times'].append(comp_time)
        self.stats['uncompressed_bytes'] += len(message.encode('utf-8'))
        self.stats['compressed_bytes'] += len(compressed_data)

        # For transferred bytes, approximate metadata overhead (typically small)
        metadata_overhead = 32  # Approximate metadata size in bytes
        self.stats['transferred_bytes'] += len(compressed_data) + metadata_overhead

        # Track method usage
        method_name = method.name if method else "UNKNOWN"
        self.stats['methods_used'][method_name] = self.stats['methods_used'].get(method_name, 0) + 1

        return {
            'compressed_data': compressed_data,
            'method': method,
            'extra_metadata': extra_metadata,
            'compression_time': comp_time,
        }

    def receive_message(self, compressed_data: bytes) -> str:
        """Decompress received message"""
        start = time.perf_counter()
        try:
            decompressed = self.compressor.decompress(compressed_data)
            decomp_time = (time.perf_counter() - start) * 1000  # ms
            self.stats['decompression_times'].append(decomp_time)
            return decompressed
        except Exception as e:
            self.stats['errors'] += 1
            raise

    def get_stats(self) -> Dict[str, Any]:
        """Get simulation statistics"""
        stats = dict(self.stats)

        if self.stats['compression_times']:
            stats['avg_compression_time'] = sum(self.stats['compression_times']) / len(self.stats['compression_times'])
        else:
            stats['avg_compression_time'] = 0

        if self.stats['decompression_times']:
            stats['avg_decompression_time'] = sum(self.stats['decompression_times']) / len(self.stats['decompression_times'])
        else:
            stats['avg_decompression_time'] = 0

        if self.stats['uncompressed_bytes'] > 0:
            stats['compression_ratio'] = self.stats['compressed_bytes'] / self.stats['uncompressed_bytes']
            stats['bandwidth_saved_pct'] = (1 - stats['compression_ratio']) * 100
        else:
            stats['compression_ratio'] = 1.0
            stats['bandwidth_saved_pct'] = 0.0

        return stats


def run_simulation(run_number: int, duration_seconds: int) -> Dict[str, Any]:
    """Run a single simulation"""
    print(f"\n{'='*80}")
    print(f"SIMULATION #{run_number} - {duration_seconds}s AI-to-AI Traffic")
    print(f"{'='*80}\n")

    # Generate traffic
    print("Generating traffic pattern...")
    generator = MessageGenerator()
    traffic = generator.generate_traffic_pattern(duration_seconds)
    print(f"Generated {len(traffic)} messages over {duration_seconds}s")
    print(f"Average rate: {len(traffic)/duration_seconds:.1f} messages/second\n")

    # Run simulation
    print("Running simulation...")
    simulator = NetworkSimulator()
    start_time = time.perf_counter()

    for idx, (timestamp, message) in enumerate(traffic):
        if (idx + 1) % 50 == 0:
            print(f"  Progress: {idx+1}/{len(traffic)} messages ({100*(idx+1)/len(traffic):.1f}%)")

        # Send (compress)
        result = simulator.send_message(message)

        # Receive (decompress)
        decompressed = simulator.receive_message(result['compressed_data'])

        # Verify
        if decompressed != message:
            print(f"  ERROR: Message {idx+1} failed verification!")
            simulator.stats['errors'] += 1

    duration = time.perf_counter() - start_time

    # Get stats
    stats = simulator.get_stats()
    stats['duration'] = duration
    stats['run_number'] = run_number
    stats['target_duration'] = duration_seconds

    # Print results
    print(f"\n{'='*80}")
    print(f"SIMULATION #{run_number} RESULTS")
    print(f"{'='*80}\n")

    print(f"Duration: {duration:.2f}s (target: {duration_seconds}s)")
    print(f"Messages: {stats['messages']} ({stats['messages']/duration:.1f} msg/s)")
    print(f"Errors: {stats['errors']}\n")

    print("Data Transfer:")
    print(f"  Uncompressed: {stats['uncompressed_bytes']:,} bytes ({stats['uncompressed_bytes']/1024:.1f} KB)")
    print(f"  Compressed:   {stats['compressed_bytes']:,} bytes ({stats['compressed_bytes']/1024:.1f} KB)")
    print(f"  Transferred:  {stats['transferred_bytes']:,} bytes ({stats['transferred_bytes']/1024:.1f} KB)")
    print(f"  Compression ratio: {stats['compression_ratio']:.2f}:1")
    print(f"  Bandwidth saved: {stats['bandwidth_saved_pct']:+.1f}%\n")

    print("Performance:")
    print(f"  Avg compression time:   {stats['avg_compression_time']:.3f} ms")
    print(f"  Avg decompression time: {stats['avg_decompression_time']:.3f} ms\n")

    print("Compression Methods Used:")
    for method, count in sorted(stats['methods_used'].items()):
        pct = 100 * count / stats['messages']
        print(f"  {method:20s}: {count:4d} ({pct:.1f}%)")

    return stats


def run_multi_simulation(num_runs: int = 10, duration_seconds: int = 60):
    """Run multiple simulations and aggregate results"""
    print("#" * 80)
    print(f"10x1-MINUTE AI-TO-AI NETWORK SIMULATION")
    print("#" * 80)

    all_stats = []

    for run in range(1, num_runs + 1):
        stats = run_simulation(run, duration_seconds)
        all_stats.append(stats)

        if run < num_runs:
            print(f"\nWaiting 2 seconds before next run...\n")
            time.sleep(2)

    # Aggregate results
    print(f"\n{'='*80}")
    print(f"AGGREGATED RESULTS - {num_runs} SIMULATIONS")
    print(f"{'='*80}\n")

    total_messages = sum(s['messages'] for s in all_stats)
    total_duration = sum(s['duration'] for s in all_stats)
    total_errors = sum(s['errors'] for s in all_stats)
    total_uncompressed = sum(s['uncompressed_bytes'] for s in all_stats)
    total_compressed = sum(s['compressed_bytes'] for s in all_stats)
    total_transferred = sum(s['transferred_bytes'] for s in all_stats)

    print(f"Total Messages: {total_messages:,}")
    print(f"Total Duration: {total_duration:.1f}s")
    print(f"Total Errors: {total_errors}\n")

    print("Aggregate Data Transfer:")
    print(f"  Total Uncompressed: {total_uncompressed:,} bytes ({total_uncompressed/1024/1024:.2f} MB)")
    print(f"  Total Compressed:   {total_compressed:,} bytes ({total_compressed/1024/1024:.2f} MB)")
    print(f"  Total Transferred:  {total_transferred:,} bytes ({total_transferred/1024/1024:.2f} MB)")
    print(f"  Bandwidth Saved:    {total_uncompressed-total_transferred:+,} bytes ({(total_uncompressed-total_transferred)/1024/1024:+.2f} MB)\n")

    # Calculate averages and std dev
    import statistics

    ratios = [s['compression_ratio'] for s in all_stats]
    bandwidth_saved = [s['bandwidth_saved_pct'] for s in all_stats]
    comp_times = [s['avg_compression_time'] for s in all_stats]
    decomp_times = [s['avg_decompression_time'] for s in all_stats]

    print("Average Performance Metrics:")
    print(f"  Compression Ratio:      {statistics.mean(ratios):.2f}:1 (±{statistics.stdev(ratios):.2f})")
    print(f"  Bandwidth Saved:        {statistics.mean(bandwidth_saved):+.1f}% (±{statistics.stdev(bandwidth_saved):.1f}%)")
    print(f"  Compression Time:       {statistics.mean(comp_times):.3f} ms (±{statistics.stdev(comp_times):.3f} ms)")
    print(f"  Decompression Time:     {statistics.mean(decomp_times):.3f} ms (±{statistics.stdev(decomp_times):.3f} ms)\n")

    # Aggregate method usage
    all_methods = {}
    for stats in all_stats:
        for method, count in stats['methods_used'].items():
            all_methods[method] = all_methods.get(method, 0) + count

    print("Overall Method Usage:")
    for method, count in sorted(all_methods.items()):
        pct = 100 * count / total_messages
        print(f"  {method:20s}: {count:5d} ({pct:.1f}%)")

    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"simulation_10x1min_{timestamp}.json"

    output_data = {
        'simulation_type': '10x1min_ai_to_ai',
        'num_runs': num_runs,
        'duration_per_run': duration_seconds,
        'timestamp': timestamp,
        'individual_runs': all_stats,
        'aggregates': {
            'total_messages': total_messages,
            'total_duration': total_duration,
            'total_errors': total_errors,
            'total_uncompressed': total_uncompressed,
            'total_compressed': total_compressed,
            'total_transferred': total_transferred,
            'avg_compression_ratio': statistics.mean(ratios),
            'avg_bandwidth_saved_pct': statistics.mean(bandwidth_saved),
            'avg_compression_time_ms': statistics.mean(comp_times),
            'avg_decompression_time_ms': statistics.mean(decomp_times),
            'method_usage': all_methods,
        }
    }

    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2, default=str)

    print(f"\nResults saved to: {output_file}")
    print("=" * 80)


if __name__ == "__main__":
    run_multi_simulation(num_runs=10, duration_seconds=60)
