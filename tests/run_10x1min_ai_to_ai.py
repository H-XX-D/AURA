#!/usr/bin/env python3
"""
Run ai_to_ai_network_simulation.py 10 times for 1 minute each
Aggregates results and provides comprehensive analysis
"""

import subprocess
import json
import re
import statistics
import time
from datetime import datetime
from pathlib import Path


def parse_simulation_output(output: str) -> dict:
    """Parse key metrics from simulation output"""
    metrics = {}

    # Extract overall ratio
    ratio_match = re.search(r'Overall ratio: ([\d.]+)x', output)
    if ratio_match:
        metrics['overall_ratio'] = float(ratio_match.group(1))

    # Extract total bytes
    total_match = re.search(r'Total bytes: ([\d,]+) → ([\d,]+)', output)
    if total_match:
        metrics['total_original'] = int(total_match.group(1).replace(',', ''))
        metrics['total_compressed'] = int(total_match.group(2).replace(',', ''))

    # Extract average sizes
    req_size_match = re.search(r'Average request size: ([\d.]+) bytes', output)
    if req_size_match:
        metrics['avg_request_size'] = float(req_size_match.group(1))

    res_size_match = re.search(r'Average response size: ([\d.]+) bytes', output)
    if res_size_match:
        metrics['avg_response_size'] = float(res_size_match.group(1))

    # Extract orchestrator metrics
    orch_match = re.search(r'ORCHESTRATOR → WORKER.*?Original: ([\d,]+) bytes.*?Compressed: ([\d,]+) bytes.*?Ratio: ([\d.]+)x', output, re.DOTALL)
    if orch_match:
        metrics['orchestrator_original'] = int(orch_match.group(1).replace(',', ''))
        metrics['orchestrator_compressed'] = int(orch_match.group(2).replace(',', ''))
        metrics['orchestrator_ratio'] = float(orch_match.group(3))

    # Extract worker metrics
    worker_match = re.search(r'WORKER → ORCHESTRATOR.*?Original: ([\d,]+) bytes.*?Compressed: ([\d,]+) bytes.*?Ratio: ([\d.]+)x', output, re.DOTALL)
    if worker_match:
        metrics['worker_original'] = int(worker_match.group(1).replace(',', ''))
        metrics['worker_compressed'] = int(worker_match.group(2).replace(',', ''))
        metrics['worker_ratio'] = float(worker_match.group(3))

    # Extract counts
    count_match = re.search(r'(\d+) exchanges', output)
    if count_match:
        metrics['exchanges'] = int(count_match.group(1))

    # Extract assessment
    if '✓ OUTSTANDING' in output:
        metrics['assessment'] = 'OUTSTANDING'
    elif '✓ STRONG' in output:
        metrics['assessment'] = 'STRONG'
    elif '✓ MODEST' in output:
        metrics['assessment'] = 'MODEST'
    elif '⚠ LIMITED' in output:
        metrics['assessment'] = 'LIMITED'
    else:
        metrics['assessment'] = 'UNKNOWN'

    return metrics


def run_simulation(run_number: int, duration_seconds: int = 60) -> dict:
    """Run a single simulation"""
    print(f"\n{'='*80}")
    print(f"SIMULATION #{run_number} - {duration_seconds}s AI-to-AI Structured Traffic")
    print(f"{'='*80}\n")

    start_time = time.time()

    # Run the simulation
    result = subprocess.run(
        ['python3', 'tests/ai_to_ai_network_simulation.py', str(duration_seconds)],
        capture_output=True,
        text=True,
        cwd=Path.cwd()
    )

    duration = time.time() - start_time

    # Print output
    print(result.stdout)

    if result.stderr:
        print("STDERR:", result.stderr)

    # Parse metrics
    metrics = parse_simulation_output(result.stdout)
    metrics['run_number'] = run_number
    metrics['duration'] = duration
    metrics['return_code'] = result.returncode
    metrics['raw_output'] = result.stdout

    return metrics


def run_multi_simulation(num_runs: int = 10, duration_seconds: int = 60):
    """Run multiple simulations and aggregate results"""
    print("#" * 80)
    print(f"10x1-MINUTE AI-TO-AI STRUCTURED TRAFFIC SIMULATION")
    print("#" * 80)
    print(f"\nRunning {num_runs} simulations × {duration_seconds}s each")
    print(f"Expected total time: ~{num_runs * duration_seconds / 60:.1f} minutes\n")

    all_metrics = []

    for run in range(1, num_runs + 1):
        metrics = run_simulation(run, duration_seconds)
        all_metrics.append(metrics)

        if run < num_runs:
            print(f"\nWaiting 2 seconds before next run...\n")
            time.sleep(2)

    # Aggregate results
    print(f"\n{'='*80}")
    print(f"AGGREGATED RESULTS - {num_runs} SIMULATIONS")
    print(f"{'='*80}\n")

    # Calculate totals
    total_original = sum(m.get('total_original', 0) for m in all_metrics)
    total_compressed = sum(m.get('total_compressed', 0) for m in all_metrics)
    total_exchanges = sum(m.get('exchanges', 0) for m in all_metrics)
    successful_runs = sum(1 for m in all_metrics if m.get('return_code') == 0)

    print(f"Successful Runs: {successful_runs}/{num_runs}")
    print(f"Total Exchanges: {total_exchanges:,}")
    print(f"Total Duration: {sum(m.get('duration', 0) for m in all_metrics):.1f}s\n")

    print("Aggregate Data Transfer:")
    print(f"  Total Original:    {total_original:,} bytes ({total_original/1024/1024:.2f} MB)")
    print(f"  Total Compressed:  {total_compressed:,} bytes ({total_compressed/1024/1024:.2f} MB)")

    if total_compressed > 0:
        overall_ratio = total_original / total_compressed
        bandwidth_saved = total_original - total_compressed
        print(f"  Overall Ratio:     {overall_ratio:.3f}x")
        print(f"  Bandwidth Saved:   {bandwidth_saved:,} bytes ({bandwidth_saved/1024/1024:.2f} MB)")
        print(f"  Savings Percent:   {(bandwidth_saved/total_original)*100:.1f}%\n")

    # Calculate statistics
    valid_metrics = [m for m in all_metrics if 'overall_ratio' in m]

    if valid_metrics:
        ratios = [m['overall_ratio'] for m in valid_metrics]
        orch_ratios = [m.get('orchestrator_ratio', 0) for m in valid_metrics if 'orchestrator_ratio' in m]
        worker_ratios = [m.get('worker_ratio', 0) for m in valid_metrics if 'worker_ratio' in m]

        print("Compression Ratio Statistics:")
        print(f"  Overall Mean:      {statistics.mean(ratios):.3f}x (±{statistics.stdev(ratios):.3f})")
        print(f"  Overall Range:     {min(ratios):.3f}x - {max(ratios):.3f}x")

        if orch_ratios:
            print(f"  Orchestrator Mean: {statistics.mean(orch_ratios):.3f}x (±{statistics.stdev(orch_ratios):.3f})")
        if worker_ratios:
            print(f"  Worker Mean:       {statistics.mean(worker_ratios):.3f}x (±{statistics.stdev(worker_ratios):.3f})")
        print()

    # Assessment distribution
    assessments = [m.get('assessment', 'UNKNOWN') for m in all_metrics]
    print("Assessment Distribution:")
    for assessment in ['OUTSTANDING', 'STRONG', 'MODEST', 'LIMITED', 'UNKNOWN']:
        count = assessments.count(assessment)
        if count > 0:
            print(f"  {assessment:12s}: {count:2d} runs ({100*count/num_runs:.0f}%)")
    print()

    # Per-run summary table
    print("Per-Run Summary:")
    print(f"{'Run':>4} {'Exchanges':>10} {'Original':>12} {'Compressed':>12} {'Ratio':>8} {'Assessment':>12}")
    print("-" * 80)
    for m in all_metrics:
        run = m.get('run_number', 0)
        exchanges = m.get('exchanges', 0)
        original = m.get('total_original', 0)
        compressed = m.get('total_compressed', 0)
        ratio = m.get('overall_ratio', 0)
        assessment = m.get('assessment', 'UNKNOWN')
        print(f"{run:4d} {exchanges:10d} {original:12,d} {compressed:12,d} {ratio:8.3f}x {assessment:>12s}")

    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"ai_to_ai_10x1min_{timestamp}.json"

    output_data = {
        'simulation_type': 'ai_to_ai_structured_10x1min',
        'num_runs': num_runs,
        'duration_per_run': duration_seconds,
        'timestamp': timestamp,
        'successful_runs': successful_runs,
        'individual_runs': all_metrics,
        'aggregates': {
            'total_original': total_original,
            'total_compressed': total_compressed,
            'total_exchanges': total_exchanges,
            'overall_ratio': total_original / total_compressed if total_compressed > 0 else 0,
            'bandwidth_saved': total_original - total_compressed,
            'savings_percent': ((total_original - total_compressed) / total_original * 100) if total_original > 0 else 0,
        }
    }

    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2, default=str)

    print(f"\nResults saved to: {output_file}")
    print("=" * 80)


if __name__ == "__main__":
    run_multi_simulation(num_runs=10, duration_seconds=60)
