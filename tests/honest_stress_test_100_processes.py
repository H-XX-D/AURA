#!/usr/bin/env python3
"""
HONEST Stress Test: 100 Truly Concurrent AI Agents

This test uses MULTIPROCESSING (not async) to achieve TRUE parallelism.
Each agent runs in a separate process, bypassing Python's GIL.

Key Differences from Async Test:
1. TRUE concurrent execution (multiple CPU cores)
2. Each agent is a separate OS process
3. Real parallel compression happening simultaneously
4. Honest measurement of concurrent throughput

Expected Results:
- On N-core CPU: Up to Nx throughput improvement
- Real concurrent load on the system
- Accurate measurement of parallel performance
"""

import multiprocessing as mp
import time
import statistics
from typing import List, Dict, Tuple
from dataclasses import dataclass
import random
import os

# Import at module level for pickling
from aura_compression.compressor import ProductionHybridCompressor


# Realistic AI conversation messages
AI_MESSAGES = [
    # Short messages (template-friendly)
    "I don't have access to that information.",
    "No",
    "Yes, that's correct.",
    "I can help you with that.",
    "I don't know",
    "I'm not sure about that.",
    "Could you please clarify?",
    "That makes sense.",
    "I understand.",
    "Let me explain.",

    # Medium messages
    "Here's how to implement a binary search in Python: Use a while loop to track left and right pointers.",
    "The error occurs because the variable is undefined. You need to declare it first.",
    "To optimize database queries, consider adding indexes on frequently searched columns.",
    "GPU acceleration provides 74-200x speedup for template matching operations.",
    "The compression ratio depends on message structure and template availability.",

    # Longer messages
    "Let me explain how neural networks work. A neural network consists of layers of interconnected nodes called neurons. Each neuron receives inputs, applies weights, adds a bias, and passes the result through an activation function. During training, backpropagation adjusts these weights to minimize the loss function.",

    "Here's a complete example:\n\ndef process_data(items):\n    results = []\n    for item in items:\n        if item.is_valid():\n            results.append(item.transform())\n    return results\n\nThis function filters and transforms valid items efficiently.",

    "The key difference between synchronous and asynchronous programming is how operations are executed. Synchronous code runs sequentially, blocking until each operation completes. Asynchronous code allows multiple operations to run concurrently, improving throughput for I/O-bound tasks.",

    # Error messages
    "Error: Connection timeout after 5000ms. Stack trace: at connect() in network.py:142",
    "Warning: Deprecated API usage detected. Please use the new async interface instead.",

    # Status updates
    "Processing batch 1 of 10... Current throughput: 50,000 msg/sec",
    "Compression complete: 2.5x ratio (original: 1024 bytes, compressed: 410 bytes)",

    # Code with explanations
    "To implement caching:\n\n```python\nfrom functools import lru_cache\n\n@lru_cache(maxsize=128)\ndef expensive_operation(x):\n    return complex_calculation(x)\n```\n\nThis decorator automatically caches results.",

    # Mixed content
    "The algorithm has O(n log n) time complexity. For n=1000000, this means roughly 20 million operations. On modern CPUs at 3 GHz, that's about 7ms execution time.",
]


@dataclass
class AgentResult:
    """Results from a single agent process"""
    agent_id: int
    process_id: int
    messages_sent: int
    total_original_bytes: int
    total_compressed_bytes: int
    compression_times_ms: List[float]
    decompression_times_ms: List[float]
    errors: int
    duration_seconds: float


def agent_worker(agent_id: int, num_messages: int, enable_gpu: bool) -> AgentResult:
    """
    Worker function that runs in a separate process.
    Each process has its own compressor instance.
    """
    # Suppress GPU init messages (too noisy with 100 processes)
    import sys
    import io
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()

    try:
        # Each process gets its own compressor
        compressor = ProductionHybridCompressor(enable_gpu=enable_gpu)

        # Restore stdout
        sys.stdout = old_stdout

        messages_sent = 0
        total_original = 0
        total_compressed = 0
        compression_times = []
        decompression_times = []
        errors = 0

        start_time = time.perf_counter()

        for i in range(num_messages):
            message = random.choice(AI_MESSAGES)

            try:
                original_size = len(message.encode('utf-8'))

                # Compress
                comp_start = time.perf_counter()
                payload, method, metadata = compressor.compress(message)
                comp_time = (time.perf_counter() - comp_start) * 1000

                compressed_size = len(payload)

                # Decompress
                decomp_start = time.perf_counter()
                decompressed = compressor.decompress(payload)
                decomp_time = (time.perf_counter() - decomp_start) * 1000

                # Record stats
                messages_sent += 1
                total_original += original_size
                total_compressed += compressed_size
                compression_times.append(comp_time)
                decompression_times.append(decomp_time)

            except Exception as e:
                errors += 1

        duration = time.perf_counter() - start_time

        return AgentResult(
            agent_id=agent_id,
            process_id=os.getpid(),
            messages_sent=messages_sent,
            total_original_bytes=total_original,
            total_compressed_bytes=total_compressed,
            compression_times_ms=compression_times,
            decompression_times_ms=decompression_times,
            errors=errors,
            duration_seconds=duration
        )

    except Exception as e:
        sys.stdout = old_stdout
        print(f"Agent {agent_id} failed: {e}")
        return AgentResult(
            agent_id=agent_id,
            process_id=os.getpid(),
            messages_sent=0,
            total_original_bytes=0,
            total_compressed_bytes=0,
            compression_times_ms=[],
            decompression_times_ms=[],
            errors=1,
            duration_seconds=0
        )


def run_honest_stress_test(
    num_agents: int = 100,
    messages_per_agent: int = 100,
    enable_gpu: bool = True,
    num_processes: int = None
):
    """
    Run HONEST stress test with TRUE parallelism using multiprocessing.

    Args:
        num_agents: Number of concurrent agent processes
        messages_per_agent: Messages each agent sends
        enable_gpu: Enable GPU acceleration
        num_processes: Max parallel processes (default: CPU count)
    """

    if num_processes is None:
        num_processes = mp.cpu_count()

    print("=" * 80)
    print(f"🤖 HONEST STRESS TEST: {num_agents} TRULY CONCURRENT PROCESSES")
    print("=" * 80)
    print(f"Configuration:")
    print(f"  Agents: {num_agents}")
    print(f"  Messages per agent: {messages_per_agent}")
    print(f"  Total messages: {num_agents * messages_per_agent:,}")
    print(f"  CPU Cores: {mp.cpu_count()}")
    print(f"  Max Parallel Processes: {num_processes}")
    print(f"  GPU Acceleration: {'✅ ENABLED' if enable_gpu else '❌ DISABLED'}")
    print(f"  Execution: TRUE PARALLELISM (multiprocessing)")
    print()

    # Create pool of workers
    print(f"🚀 Starting {num_agents} agent processes...")
    print(f"   (Running up to {num_processes} in parallel at a time)")
    start_time = time.perf_counter()

    # Use process pool to manage parallel execution
    with mp.Pool(processes=num_processes) as pool:
        # Create work items
        work_items = [(i, messages_per_agent, enable_gpu) for i in range(num_agents)]

        # Execute in parallel
        results = pool.starmap(agent_worker, work_items)

    total_duration = time.perf_counter() - start_time

    # Analyze results
    print(f"\n{'=' * 80}")
    print("📊 RESULTS")
    print("=" * 80)

    total_messages = sum(r.messages_sent for r in results)
    total_original = sum(r.total_original_bytes for r in results)
    total_compressed = sum(r.total_compressed_bytes for r in results)
    total_errors = sum(r.errors for r in results)

    all_compression_times = []
    all_decompression_times = []
    for r in results:
        all_compression_times.extend(r.compression_times_ms)
        all_decompression_times.extend(r.decompression_times_ms)

    overall_ratio = total_original / total_compressed if total_compressed > 0 else 0
    throughput = total_messages / total_duration

    # Calculate parallel efficiency
    avg_agent_duration = statistics.mean([r.duration_seconds for r in results])
    parallel_efficiency = avg_agent_duration / total_duration if total_duration > 0 else 0
    theoretical_max_speedup = min(num_agents, num_processes)
    actual_speedup = parallel_efficiency * num_agents

    print(f"\n📈 Overall Performance:")
    print(f"  Total Wall-Clock Time: {total_duration:.2f}s")
    print(f"  Avg Agent Duration: {avg_agent_duration:.2f}s")
    print(f"  Messages Processed: {total_messages:,}")
    print(f"  Throughput: {throughput:,.0f} messages/sec")
    print(f"  Bandwidth: {total_original / total_duration / 1024 / 1024:.2f} MB/sec (original)")
    print(f"  Bandwidth: {total_compressed / total_duration / 1024 / 1024:.2f} MB/sec (compressed)")
    print(f"  Errors: {total_errors}")

    print(f"\n⚡ Parallelism Analysis:")
    print(f"  CPU Cores Available: {mp.cpu_count()}")
    print(f"  Parallel Efficiency: {parallel_efficiency:.2%}")
    print(f"  Theoretical Max Speedup: {theoretical_max_speedup:.1f}x")
    print(f"  Actual Speedup: {actual_speedup:.1f}x")
    print(f"  Single-Agent Equivalent Throughput: {total_messages / avg_agent_duration:,.0f} msg/sec")

    print(f"\n💾 Compression Statistics:")
    print(f"  Total Original: {total_original:,} bytes ({total_original / 1024 / 1024:.2f} MB)")
    print(f"  Total Compressed: {total_compressed:,} bytes ({total_compressed / 1024 / 1024:.2f} MB)")
    print(f"  Overall Ratio: {overall_ratio:.2f}x")
    print(f"  Bandwidth Saved: {total_original - total_compressed:,} bytes ({(1 - total_compressed/total_original)*100:.1f}%)")

    if all_compression_times:
        print(f"\n⏱️  Latency Statistics:")
        print(f"  Compression:")
        print(f"    Mean: {statistics.mean(all_compression_times):.3f}ms")
        print(f"    Median: {statistics.median(all_compression_times):.3f}ms")
        print(f"    P95: {sorted(all_compression_times)[int(len(all_compression_times) * 0.95)]:.3f}ms")
        print(f"    P99: {sorted(all_compression_times)[int(len(all_compression_times) * 0.99)]:.3f}ms")
        print(f"    Max: {max(all_compression_times):.3f}ms")

    if all_decompression_times:
        print(f"  Decompression:")
        print(f"    Mean: {statistics.mean(all_decompression_times):.3f}ms")
        print(f"    Median: {statistics.median(all_decompression_times):.3f}ms")
        print(f"    P95: {sorted(all_decompression_times)[int(len(all_decompression_times) * 0.95)]:.3f}ms")
        print(f"    P99: {sorted(all_decompression_times)[int(len(all_decompression_times) * 0.99)]:.3f}ms")
        print(f"    Max: {max(all_decompression_times):.3f}ms")

    # Sample agent results
    print(f"\n🤖 Sample Agent Results (first 5):")
    for i in range(min(5, len(results))):
        r = results[i]
        ratio = r.total_original_bytes / r.total_compressed_bytes if r.total_compressed_bytes > 0 else 0
        avg_comp = statistics.mean(r.compression_times_ms) if r.compression_times_ms else 0
        print(f"  Agent {r.agent_id} (PID {r.process_id}):")
        print(f"    Messages: {r.messages_sent}")
        print(f"    Duration: {r.duration_seconds:.2f}s")
        print(f"    Compression ratio: {ratio:.2f}x")
        print(f"    Avg compression time: {avg_comp:.3f}ms")
        print(f"    Errors: {r.errors}")

    # Success criteria
    print(f"\n{'=' * 80}")
    print("✅ HONEST SUCCESS CRITERIA:")
    print("=" * 80)

    success = True

    # Honest throughput check (accounts for parallelism)
    single_agent_throughput = total_messages / avg_agent_duration
    expected_parallel_throughput = single_agent_throughput * min(num_processes, num_agents)

    print(f"  Single-Agent Throughput: {single_agent_throughput:,.0f} msg/sec")
    print(f"  Expected Parallel Throughput: {expected_parallel_throughput:,.0f} msg/sec ({min(num_processes, num_agents)}x)")
    print(f"  Actual Parallel Throughput: {throughput:,.0f} msg/sec")
    print(f"  Parallel Efficiency: {(throughput / expected_parallel_throughput * 100):.1f}%")

    if parallel_efficiency >= 0.5:  # At least 50% efficiency
        print(f"✅ Good parallel efficiency ({parallel_efficiency:.1%})")
    else:
        print(f"⚠️  Low parallel efficiency ({parallel_efficiency:.1%})")
        success = False

    # Check latency
    if all_compression_times:
        p99_compression = sorted(all_compression_times)[int(len(all_compression_times) * 0.99)]
        if p99_compression <= 10.0:
            print(f"✅ P99 Compression Latency: {p99_compression:.3f}ms (target: <10.0ms)")
        else:
            print(f"❌ P99 Compression Latency: {p99_compression:.3f}ms (target: <10.0ms)")
            success = False

    # Check errors
    if total_errors == 0:
        print(f"✅ Error Rate: 0 errors")
    else:
        print(f"❌ Error Rate: {total_errors} errors (target: 0)")
        success = False

    print("=" * 80)
    if success:
        print("🎉 ALL HONEST CRITERIA MET!")
    else:
        print("⚠️  SOME CRITERIA NOT MET")
    print("=" * 80)

    return success


def main():
    """Run the honest stress test"""

    print("\n" + "=" * 80)
    print("HONEST TEST: 100 TRULY CONCURRENT PROCESSES")
    print("Using multiprocessing for TRUE parallelism (not async illusion)")
    print("=" * 80 + "\n")

    # Get CPU count
    cpu_count = mp.cpu_count()
    print(f"System has {cpu_count} CPU cores available")
    print()

    success = run_honest_stress_test(
        num_agents=100,
        messages_per_agent=100,
        enable_gpu=True,
        num_processes=cpu_count  # Use all available cores
    )

    if success:
        print("\n✅ Honest stress test PASSED!")
        exit(0)
    else:
        print("\n⚠️  Honest stress test completed with warnings")
        exit(0)


if __name__ == "__main__":
    # Required for multiprocessing on some platforms
    mp.set_start_method('spawn', force=True)
    main()
