#!/usr/bin/env python3
"""
AI-to-AI Network Traffic Simulation

Simulates realistic network traffic between AI systems over 30 seconds,
testing AURA compression performance in production-like conditions.

Simulates:
- OpenAI API responses (GPT-4 style)
- Anthropic Claude responses
- Function calling / tool use
- Streaming responses
- Error messages
- Status updates

Network conditions:
- Realistic latency (10-100ms)
- Jitter (±5-20ms)
- Occasional packet loss (0.1-1%)
- Bandwidth constraints
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


@dataclass
class NetworkStats:
    """Statistics for network simulation"""
    total_messages: int
    total_bytes_uncompressed: int
    total_bytes_compressed: int
    total_bytes_transferred: int  # Including protocol overhead
    compression_ratio: float
    bandwidth_saved_percent: float
    avg_latency_ms: float
    avg_compression_time_ms: float
    avg_decompression_time_ms: float
    method_usage: Dict[str, int]
    errors: int
    duration_seconds: float


class NetworkSimulator:
    """Simulates realistic network conditions"""

    def __init__(self, base_latency_ms: float = 30.0, jitter_ms: float = 10.0,
                 packet_loss_rate: float = 0.001, bandwidth_mbps: float = 100.0):
        self.base_latency_ms = base_latency_ms
        self.jitter_ms = jitter_ms
        self.packet_loss_rate = packet_loss_rate
        self.bandwidth_mbps = bandwidth_mbps
        self.bytes_per_second = (bandwidth_mbps * 1_000_000) / 8

    def transmit(self, data: bytes) -> Tuple[bytes, float, bool]:
        """
        Simulate network transmission

        Returns:
            (data, latency_ms, success)
        """
        # Calculate transfer time based on bandwidth
        transfer_time_ms = (len(data) / self.bytes_per_second) * 1000

        # Add base latency + jitter
        latency = self.base_latency_ms + random.uniform(-self.jitter_ms, self.jitter_ms)
        total_time = latency + transfer_time_ms

        # Simulate packet loss
        if random.random() < self.packet_loss_rate:
            return b'', total_time, False

        # Simulate network delay
        time.sleep(total_time / 1000.0)

        return data, total_time, True


class AIMessageGenerator:
    """Generates realistic AI-to-AI messages"""

    # Common OpenAI/Anthropic response templates ({{ }} to escape braces)
    RESPONSE_TEMPLATES = [
        # Short responses
        '{{"id": "msg-{id}", "type": "message", "role": "assistant", "content": "{content}", "model": "claude-3-opus", "stop_reason": "end_turn", "usage": {{"input_tokens": {input}, "output_tokens": {output}}}}}',

        '{{"id": "chatcmpl-{id}", "object": "chat.completion", "model": "gpt-4", "choices": [{{"index": 0, "message": {{"role": "assistant", "content": "{content}"}}, "finish_reason": "stop"}}], "usage": {{"prompt_tokens": {input}, "completion_tokens": {output}, "total_tokens": {total}}}}}',

        # Function calling
        '{{"id": "msg-{id}", "type": "message", "role": "assistant", "content": [{{"type": "tool_use", "id": "tool-{tool_id}", "name": "{function}", "input": {params}}}], "model": "claude-3-opus", "stop_reason": "tool_use"}}',

        # Status updates
        '{{"status": "{status}", "message": "{message}", "timestamp": {timestamp}, "request_id": "req-{id}"}}',

        # Errors
        '{{"error": {{"message": "{error_msg}", "type": "{error_type}", "code": "{error_code}"}}, "request_id": "req-{id}"}}',

        # Long structured responses (code generation, analysis)
        '{{"id": "msg-{id}", "content": "{long_content}", "metadata": {{"tokens": {tokens}, "model": "gpt-4-turbo", "temperature": 0.7, "top_p": 0.9}}, "analysis": {analysis}}}',
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

    FUNCTION_NAMES = [
        "search_database", "execute_query", "analyze_code", "generate_report",
        "fetch_data", "process_batch", "validate_input", "transform_data"
    ]

    STATUS_MESSAGES = [
        ("processing", "Request is being processed"),
        ("completed", "Task completed successfully"),
        ("pending", "Task queued for processing"),
        ("failed", "Task execution failed"),
    ]

    def generate_message(self) -> str:
        """Generate a realistic AI message"""
        template = random.choice(self.RESPONSE_TEMPLATES)

        # Fill in template variables
        msg_id = ''.join(random.choices('0123456789abcdef', k=16))
        tool_id = ''.join(random.choices('0123456789', k=8))
        content = random.choice(self.CONTENT_SAMPLES)

        # Generate token counts
        input_tokens = random.randint(50, 500)
        output_tokens = random.randint(20, 300)
        total_tokens = input_tokens + output_tokens

        # Function params
        params = json.dumps({
            "query": "SELECT * FROM users WHERE active = true",
            "limit": random.randint(10, 100)
        })

        # Status
        status, message = random.choice(self.STATUS_MESSAGES)

        # Long content (for code generation)
        long_content = content * random.randint(5, 20)

        # Analysis data
        analysis = json.dumps({
            "complexity": random.choice(["low", "medium", "high"]),
            "score": round(random.uniform(0.5, 0.99), 2),
            "recommendations": ["Optimize loops", "Add error handling", "Improve naming"]
        })

        msg = template.format(
            id=msg_id,
            tool_id=tool_id,
            content=content,
            input=input_tokens,
            output=output_tokens,
            total=total_tokens,
            function=random.choice(self.FUNCTION_NAMES),
            params=params,
            status=status,
            message=message,
            timestamp=int(time.time()),
            error_msg="Rate limit exceeded",
            error_type="rate_limit_error",
            error_code="429",
            long_content=long_content,
            tokens=random.randint(500, 2000),
            analysis=analysis
        )

        return msg

    def generate_traffic_pattern(self, duration_seconds: int = 30) -> List[Tuple[float, str]]:
        """
        Generate realistic traffic pattern over time

        Returns:
            List of (timestamp_offset, message) tuples
        """
        messages = []
        current_time = 0.0

        # Simulate burst patterns (AI models generate responses in bursts)
        while current_time < duration_seconds:
            # Burst duration (AI processing time)
            burst_duration = random.uniform(0.5, 3.0)

            # Messages in this burst
            burst_size = random.randint(5, 30)

            for _ in range(burst_size):
                if current_time >= duration_seconds:
                    break

                message = self.generate_message()
                messages.append((current_time, message))

                # Inter-message delay within burst (very small)
                current_time += random.uniform(0.01, 0.1)

            # Quiet period between bursts
            current_time += random.uniform(0.2, 2.0)

        return messages


def run_simulation(simulation_id: int, duration_seconds: int = 30) -> NetworkStats:
    """
    Run a single 30-second AI-to-AI network simulation

    Args:
        simulation_id: ID for this simulation run
        duration_seconds: Duration of simulation

    Returns:
        NetworkStats with results
    """
    print(f"\n{'='*80}")
    print(f"SIMULATION #{simulation_id} - {duration_seconds}s AI-to-AI Network Traffic")
    print(f"{'='*80}\n")

    # Initialize components
    compressor = ProductionHybridCompressor(
        binary_advantage_threshold=1.01,
        min_compression_size=10,
        enable_aura=False,
        enable_audit_logging=False,
        template_cache_size=256,
        enable_scorer=False
    )

    # Add typical AI response templates
    lib = compressor._template_service.template_manager.template_library
    lib.add(1, '{"id": "{0}", "type": "message", "role": "assistant", "content": "{1}", "model": "{2}"}')
    lib.add(2, '{"id": "{0}", "object": "chat.completion", "model": "{1}", "choices": [{2}]}')
    lib.add(3, '{"status": "{0}", "message": "{1}", "timestamp": {2}}')
    lib.add(4, '{"error": {"message": "{0}", "type": "{1}"}}')

    # Network simulator (realistic internet conditions)
    network = NetworkSimulator(
        base_latency_ms=30.0,  # Average internet latency
        jitter_ms=10.0,         # Network jitter
        packet_loss_rate=0.001, # 0.1% packet loss
        bandwidth_mbps=100.0    # 100 Mbps connection
    )

    # Message generator
    generator = AIMessageGenerator()

    # Generate traffic pattern
    print("Generating traffic pattern...")
    traffic_pattern = generator.generate_traffic_pattern(duration_seconds)
    print(f"Generated {len(traffic_pattern)} messages over {duration_seconds}s")
    print(f"Average rate: {len(traffic_pattern)/duration_seconds:.1f} messages/second\n")

    # Simulation metrics
    total_bytes_uncompressed = 0
    total_bytes_compressed = 0
    total_bytes_transferred = 0
    compression_times = []
    decompression_times = []
    latencies = []
    method_usage = {}
    errors = 0

    # Run simulation
    print("Running simulation...")
    start_time = time.time()

    for i, (timestamp_offset, message) in enumerate(traffic_pattern):
        # Wait until this message should be sent
        elapsed = time.time() - start_time
        wait_time = timestamp_offset - elapsed
        if wait_time > 0:
            time.sleep(wait_time)

        # Compress message
        try:
            t0 = time.perf_counter()
            compressed, method, metadata = compressor.compress(message)
            compression_time = (time.perf_counter() - t0) * 1000  # ms

            compression_times.append(compression_time)
            method_usage[method.name] = method_usage.get(method.name, 0) + 1

            # Track sizes
            original_size = len(message.encode('utf-8'))
            compressed_size = len(compressed)

            # Add protocol overhead (TCP/IP headers ~40 bytes + TLS ~40 bytes)
            protocol_overhead = 80
            transferred_size = compressed_size + protocol_overhead

            total_bytes_uncompressed += original_size
            total_bytes_compressed += compressed_size
            total_bytes_transferred += transferred_size

            # Transmit over network
            received_data, latency, success = network.transmit(compressed)
            latencies.append(latency)

            if not success:
                errors += 1
                continue

            # Decompress
            t0 = time.perf_counter()
            decompressed, _ = compressor.decompress(received_data, return_metadata=True)
            decompression_time = (time.perf_counter() - t0) * 1000  # ms
            decompression_times.append(decompression_time)

            # Verify
            if decompressed != message:
                print(f"ERROR: Message {i} decompression mismatch!")
                errors += 1

        except Exception as e:
            print(f"ERROR processing message {i}: {e}")
            errors += 1

        # Progress indicator
        if (i + 1) % 50 == 0:
            elapsed = time.time() - start_time
            progress = (elapsed / duration_seconds) * 100
            print(f"  Progress: {i+1}/{len(traffic_pattern)} messages ({progress:.1f}%)")

    actual_duration = time.time() - start_time

    # Calculate statistics
    compression_ratio = total_bytes_uncompressed / total_bytes_compressed if total_bytes_compressed > 0 else 1.0
    bandwidth_saved = ((total_bytes_uncompressed - total_bytes_transferred) / total_bytes_uncompressed) * 100 if total_bytes_uncompressed > 0 else 0.0

    stats = NetworkStats(
        total_messages=len(traffic_pattern),
        total_bytes_uncompressed=total_bytes_uncompressed,
        total_bytes_compressed=total_bytes_compressed,
        total_bytes_transferred=total_bytes_transferred,
        compression_ratio=compression_ratio,
        bandwidth_saved_percent=bandwidth_saved,
        avg_latency_ms=statistics.mean(latencies) if latencies else 0.0,
        avg_compression_time_ms=statistics.mean(compression_times) if compression_times else 0.0,
        avg_decompression_time_ms=statistics.mean(decompression_times) if decompression_times else 0.0,
        method_usage=method_usage,
        errors=errors,
        duration_seconds=actual_duration
    )

    # Print results
    print(f"\n{'='*80}")
    print(f"SIMULATION #{simulation_id} RESULTS")
    print(f"{'='*80}\n")

    print(f"Duration: {stats.duration_seconds:.2f}s (target: {duration_seconds}s)")
    print(f"Messages: {stats.total_messages} ({stats.total_messages/stats.duration_seconds:.1f} msg/s)")
    print(f"Errors: {stats.errors}\n")

    print("Data Transfer:")
    print(f"  Uncompressed: {stats.total_bytes_uncompressed:,} bytes ({stats.total_bytes_uncompressed/1024:.1f} KB)")
    print(f"  Compressed:   {stats.total_bytes_compressed:,} bytes ({stats.total_bytes_compressed/1024:.1f} KB)")
    print(f"  Transferred:  {stats.total_bytes_transferred:,} bytes ({stats.total_bytes_transferred/1024:.1f} KB)")
    print(f"  Compression ratio: {stats.compression_ratio:.2f}:1")
    print(f"  Bandwidth saved: {stats.bandwidth_saved_percent:.1f}%\n")

    print("Performance:")
    print(f"  Avg compression time:   {stats.avg_compression_time_ms:.3f} ms")
    print(f"  Avg decompression time: {stats.avg_decompression_time_ms:.3f} ms")
    print(f"  Avg network latency:    {stats.avg_latency_ms:.2f} ms\n")

    print("Compression Methods Used:")
    for method, count in sorted(stats.method_usage.items(), key=lambda x: x[1], reverse=True):
        percentage = (count / stats.total_messages) * 100
        print(f"  {method:20s}: {count:4d} ({percentage:5.1f}%)")

    return stats


def run_multi_simulation(num_runs: int = 3, duration_seconds: int = 30):
    """Run multiple simulations and aggregate results"""
    print(f"\n{'#'*80}")
    print(f"AI-TO-AI NETWORK SIMULATION - {num_runs} RUNS x {duration_seconds}s")
    print(f"{'#'*80}")

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

    total_messages = sum(s.total_messages for s in all_stats)
    total_uncompressed = sum(s.total_bytes_uncompressed for s in all_stats)
    total_compressed = sum(s.total_bytes_compressed for s in all_stats)
    total_transferred = sum(s.total_bytes_transferred for s in all_stats)

    avg_compression_ratio = statistics.mean([s.compression_ratio for s in all_stats])
    avg_bandwidth_saved = statistics.mean([s.bandwidth_saved_percent for s in all_stats])
    avg_compression_time = statistics.mean([s.avg_compression_time_ms for s in all_stats])
    avg_decompression_time = statistics.mean([s.avg_decompression_time_ms for s in all_stats])
    avg_latency = statistics.mean([s.avg_latency_ms for s in all_stats])

    print(f"Total Messages: {total_messages:,}")
    print(f"Total Duration: {sum(s.duration_seconds for s in all_stats):.1f}s")
    print(f"Total Errors: {sum(s.errors for s in all_stats)}\n")

    print("Aggregate Data Transfer:")
    print(f"  Total Uncompressed: {total_uncompressed:,} bytes ({total_uncompressed/1024/1024:.2f} MB)")
    print(f"  Total Compressed:   {total_compressed:,} bytes ({total_compressed/1024/1024:.2f} MB)")
    print(f"  Total Transferred:  {total_transferred:,} bytes ({total_transferred/1024/1024:.2f} MB)")
    print(f"  Bandwidth Saved:    {total_uncompressed - total_transferred:,} bytes ({(total_uncompressed - total_transferred)/1024/1024:.2f} MB)\n")

    print("Average Performance Metrics:")
    print(f"  Compression Ratio:      {avg_compression_ratio:.2f}:1 (±{statistics.stdev([s.compression_ratio for s in all_stats]):.2f})")
    print(f"  Bandwidth Saved:        {avg_bandwidth_saved:.1f}% (±{statistics.stdev([s.bandwidth_saved_percent for s in all_stats]):.1f}%)")
    print(f"  Compression Time:       {avg_compression_time:.3f} ms (±{statistics.stdev([s.avg_compression_time_ms for s in all_stats]):.3f} ms)")
    print(f"  Decompression Time:     {avg_decompression_time:.3f} ms (±{statistics.stdev([s.avg_decompression_time_ms for s in all_stats]):.3f} ms)")
    print(f"  Network Latency:        {avg_latency:.2f} ms (±{statistics.stdev([s.avg_latency_ms for s in all_stats]):.2f} ms)\n")

    # Aggregate method usage
    all_methods = {}
    for stats in all_stats:
        for method, count in stats.method_usage.items():
            all_methods[method] = all_methods.get(method, 0) + count

    print("Overall Method Usage:")
    for method, count in sorted(all_methods.items(), key=lambda x: x[1], reverse=True):
        percentage = (count / total_messages) * 100
        print(f"  {method:20s}: {count:5d} ({percentage:5.1f}%)")

    # Save results to JSON
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = f"ai_network_simulation_{timestamp}.json"

    results = {
        "timestamp": timestamp,
        "num_runs": num_runs,
        "duration_seconds": duration_seconds,
        "summary": {
            "total_messages": total_messages,
            "total_uncompressed_bytes": total_uncompressed,
            "total_compressed_bytes": total_compressed,
            "total_transferred_bytes": total_transferred,
            "avg_compression_ratio": avg_compression_ratio,
            "avg_bandwidth_saved_percent": avg_bandwidth_saved,
            "avg_compression_time_ms": avg_compression_time,
            "avg_decompression_time_ms": avg_decompression_time,
            "avg_network_latency_ms": avg_latency,
            "method_usage": all_methods
        },
        "individual_runs": [asdict(s) for s in all_stats]
    }

    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to: {results_file}")
    print(f"\n{'='*80}\n")


if __name__ == "__main__":
    # Run 3 simulations of 30 seconds each
    run_multi_simulation(num_runs=3, duration_seconds=30)
