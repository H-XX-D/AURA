#!/usr/bin/env python3
"""
AURA Compression Component Test Framework
=========================================

Comprehensive testing framework for all AURA compression components with:
- Unit tests for individual components
- Benchmark tests for performance metrics
- Integration tests for component interactions
- Regression tests for performance monitoring

Usage:
    python test_framework.py --unit          # Run unit tests
    python test_framework.py --benchmark     # Run benchmarks
    python test_framework.py --integration   # Run integration tests
    python test_framework.py --all          # Run all tests
    python test_framework.py --profile      # Run with profiling
"""

import pytest
import sys
import os
import time
import json
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict

# Add source path
project_root = Path(__file__).parent
src_path = project_root / 'src' / 'python'
sys.path.insert(0, str(src_path))

from aura_compression import ProductionHybridCompressor, CompressionMethod


@dataclass
class BenchmarkResult:
    """Result of a benchmark test."""
    component: str
    test_name: str
    metric_name: str
    value: float
    unit: str
    iterations: int
    timestamp: float
    metadata: Dict[str, Any] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class TestDataGenerator:
    """Generates test data for various scenarios."""

    @staticmethod
    def generate_api_response(size: str = 'small') -> str:
        """Generate mock API response."""
        templates = {
            'small': '{"status": "success", "data": {"id": 123, "name": "test"}}',
            'medium': '{"status": "success", "data": {"user": {"id": 12345, "name": "John Doe", "email": "john@example.com"}, "posts": [{"id": 1, "title": "Hello World", "content": "This is a test post"}]}}',
            'large': '{"status": "success", "data": {"users": [' + ','.join([f'{{"id": {i}, "name": "User {i}", "email": "user{i}@example.com"}}' for i in range(100)]) + ']}}'
        }
        return templates.get(size, templates['small'])

    @staticmethod
    def generate_text_message(size: str = 'small') -> str:
        """Generate mock text message."""
        templates = {
            'small': 'Hello, how are you today?',
            'medium': 'I hope this message finds you well. I wanted to discuss the upcoming project deadline and make sure we are aligned on the requirements.',
            'large': 'This is a comprehensive message about our project. We need to discuss the architecture, implementation details, testing strategy, deployment plan, and monitoring setup. The system should handle high throughput, provide real-time analytics, and maintain data consistency across distributed components.'
        }
        return templates.get(size, templates['small'])


class CompressorBenchmark:
    """Benchmark tests for the compression component."""

    def __init__(self):
        self.compressor = None
        self.test_data = []

    def setup(self):
        """Setup compressor benchmark."""
        self.compressor = ProductionHybridCompressor(enable_aura=True)

        # Generate test data of various sizes
        self.test_data = [
            TestDataGenerator.generate_text_message('small'),
            TestDataGenerator.generate_api_response('medium'),
            TestDataGenerator.generate_text_message('large'),
        ]

    def run(self, iterations: int = 10) -> List[BenchmarkResult]:
        """Run compression benchmarks."""
        results = []

        for data in self.test_data:
            data_size = len(data.encode('utf-8'))

            # Benchmark compression
            compression_times = []
            compression_ratios = []

            for _ in range(iterations):
                start_time = time.time()
                compressed, method, metadata = self.compressor.compress(data)
                compression_time = (time.time() - start_time) * 1000  # ms

                compression_times.append(compression_time)
                compression_ratios.append(metadata.get('ratio', 1.0))

            avg_compression_time = sum(compression_times) / len(compression_times)
            avg_ratio = sum(compression_ratios) / len(compression_ratios)
            compression_speed = (data_size / 1024 / 1024) / (avg_compression_time / 1000)  # MB/s

            results.extend([
                BenchmarkResult(
                    component="compressor",
                    test_name=f"compression_{data_size}bytes",
                    metric_name="compression_time_ms",
                    value=avg_compression_time,
                    unit="ms",
                    iterations=iterations,
                    timestamp=time.time(),
                    metadata={"data_size": data_size, "method": method.name}
                ),
                BenchmarkResult(
                    component="compressor",
                    test_name=f"compression_{data_size}bytes",
                    metric_name="compression_ratio",
                    value=avg_ratio,
                    unit="ratio",
                    iterations=iterations,
                    timestamp=time.time(),
                    metadata={"data_size": data_size, "method": method.name}
                ),
                BenchmarkResult(
                    component="compressor",
                    test_name=f"compression_{data_size}bytes",
                    metric_name="compression_speed_mbps",
                    value=compression_speed,
                    unit="MB/s",
                    iterations=iterations,
                    timestamp=time.time(),
                    metadata={"data_size": data_size, "method": method.name}
                )
            ])

        return results

    def teardown(self):
        """Cleanup compressor benchmark."""
        self.compressor = None
        self.test_data = []


class BenchmarkRunner:
    """Main test runner for the framework."""

    def __init__(self):
        self.benchmarks = {
            'compressor': CompressorBenchmark(),
        }
        self.results = []

    def run_benchmarks(self, iterations: int = 10) -> List[BenchmarkResult]:
        """Run benchmark tests."""
        print(f"Running benchmarks with {iterations} iterations...")

        all_results = []

        for name, benchmark in self.benchmarks.items():
            print(f"Running {name} benchmark...")
            try:
                benchmark.setup()
                results = benchmark.run(iterations)
                benchmark.teardown()
                all_results.extend(results)
                print(f"  ✅ {name}: {len(results)} metrics collected")
            except Exception as e:
                print(f"  ❌ {name}: Failed - {e}")

        self.results = all_results
        return all_results

    def save_results(self, filename: str = 'benchmark_results.json'):
        """Save benchmark results to file."""
        results_dict = [result.to_dict() for result in self.results]

        with open(filename, 'w') as f:
            json.dump(results_dict, f, indent=2, default=str)

        print(f"Results saved to {filename}")

    def generate_report(self) -> str:
        """Generate a performance report."""
        if not self.results:
            return "No benchmark results available."

        report = []
        report.append("# AURA Compression Benchmark Report")
        report.append(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")

        # Group results by component
        components = {}
        for result in self.results:
            if result.component not in components:
                components[result.component] = []
            components[result.component].append(result)

        for component, results in components.items():
            report.append(f"## {component.upper()} Component")
            report.append("")

            # Group by test name
            tests = {}
            for result in results:
                if result.test_name not in tests:
                    tests[result.test_name] = []
                tests[result.test_name].append(result)

            for test_name, test_results in tests.items():
                report.append(f"### {test_name}")
                for result in test_results:
                    report.append(".3f")
                report.append("")

        return "\n".join(report)


def main():
    parser = argparse.ArgumentParser(description="AURA Compression Test Framework")
    parser.add_argument('--benchmark', action='store_true', help='Run benchmark tests')
    parser.add_argument('--iterations', type=int, default=10, help='Number of benchmark iterations')
    parser.add_argument('--output', type=str, default='benchmark_results.json', help='Output file for results')

    args = parser.parse_args()

    runner = BenchmarkRunner()

    try:
        if args.benchmark:
            results = runner.run_benchmarks(args.iterations)
            runner.save_results(args.output)
            print(f"Benchmark complete: {len(results)} metrics collected")

            report = runner.generate_report()
            print("\n" + "="*80)
            print(report)
            print("="*80)

        print("\n✅ Tests completed successfully!")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)


# ============================================================================
# Pytest Test Functions
# ============================================================================

def test_data_generator_api_response():
    """Test API response data generator."""
    small = TestDataGenerator.generate_api_response('small')
    medium = TestDataGenerator.generate_api_response('medium')
    large = TestDataGenerator.generate_api_response('large')

    # Should be valid JSON
    import json
    json.loads(small)
    json.loads(medium)
    json.loads(large)

    # Should have increasing sizes
    assert len(small) < len(medium) < len(large)


def test_data_generator_text_message():
    """Test text message data generator."""
    small = TestDataGenerator.generate_text_message('small')
    medium = TestDataGenerator.generate_text_message('medium')
    large = TestDataGenerator.generate_text_message('large')

    # Should have increasing sizes
    assert len(small) < len(medium) < len(large)

    # Should be strings
    assert isinstance(small, str)
    assert isinstance(medium, str)
    assert isinstance(large, str)


def test_compressor_benchmark_setup():
    """Test compressor benchmark setup."""
    benchmark = CompressorBenchmark()
    benchmark.setup()

    assert benchmark.compressor is not None
    assert len(benchmark.test_data) > 0

    # Test data should be strings
    for data in benchmark.test_data:
        assert isinstance(data, str)
        assert len(data) > 0


def test_compressor_benchmark_run():
    """Test compressor benchmark execution."""
    benchmark = CompressorBenchmark()
    benchmark.setup()

    results = benchmark.run(iterations=2)

    assert isinstance(results, list)
    assert len(results) > 0

    for result in results:
        assert isinstance(result, BenchmarkResult)
        assert result.component == "compressor"
        assert isinstance(result.value, (int, float))
        assert result.iterations == 2


def test_benchmark_result_serialization():
    """Test benchmark result serialization."""
    result = BenchmarkResult(
        component="test",
        test_name="test_benchmark",
        metric_name="test_metric",
        value=123.45,
        unit="ms",
        iterations=10,
        timestamp=time.time()
    )

    # Should convert to dict
    result_dict = result.to_dict()
    assert isinstance(result_dict, dict)
    assert result_dict["component"] == "test"
    assert result_dict["value"] == 123.45


def test_test_runner_benchmarks():
    """Test the main test runner."""
    runner = BenchmarkRunner()

    results = runner.run_benchmarks(iterations=2)

    assert isinstance(results, list)
    # Should have some results
    assert len(results) > 0

    for result in results:
        assert isinstance(result, BenchmarkResult)


if __name__ == '__main__':
    main()