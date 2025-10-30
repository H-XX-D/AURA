#!/usr/bin/env python3
"""
AURA Compression Test Runner
============================

Comprehensive test runner that executes all test suites with benchmarking.
"""

import sys
import os
import time
import json
import argparse
import unittest
from pathlib import Path
from typing import Dict, List, Any

# Add source path
project_root = Path(__file__).parent
src_path = project_root / 'src' / 'python'
sys.path.insert(0, str(src_path))
sys.path.insert(0, str(project_root))  # Add tests directory to path

from test_framework import BenchmarkRunner
from test_data_generator import TestDataGenerator, PerformanceBaseline


class ComprehensiveTestRunner:
    """Comprehensive test runner for all AURA components."""

    def __init__(self):
        self.benchmark_runner = BenchmarkRunner()
        self.performance_baseline = PerformanceBaseline()
        self.test_data_generator = TestDataGenerator()
        self.results = {
            "unit_tests": {},
            "integration_tests": {},
            "benchmarks": {},
            "performance_checks": {},
            "summary": {}
        }

    def run_unit_tests(self) -> bool:
        """Run all unit tests."""
        print("🧪 Running Unit Tests")
        print("=" * 50)

        success = True
        unit_test_files = [
            'tests/unit/test_compressor.py',
            'tests/test_template_service.py',
            'tests/test_core_functionality.py',
        ]

        for test_file in unit_test_files:
            if os.path.exists(test_file):
                print(f"Running {test_file}...")
                try:
                    # Load and run the test module
                    module_name = test_file.replace('/', '.').replace('.py', '')
                    module = __import__(module_name, fromlist=[''])

                    # Create test suite
                    loader = unittest.TestLoader()
                    suite = loader.loadTestsFromModule(module)
                    runner = unittest.TextTestRunner(verbosity=1, stream=sys.stdout)
                    result = runner.run(suite)

                    self.results["unit_tests"][test_file] = {
                        "tests_run": result.testsRun,
                        "failures": len(result.failures),
                        "errors": len(result.errors),
                        "success": result.wasSuccessful()
                    }

                    if not result.wasSuccessful():
                        success = False
                        print(f"  ❌ {test_file} failed")
                    else:
                        print(f"  ✅ {test_file} passed")

                except Exception as e:
                    print(f"  ❌ {test_file} error: {e}")
                    success = False
                    self.results["unit_tests"][test_file] = {"error": str(e)}
            else:
                print(f"  ⚠️  {test_file} not found")

        return success

    def run_integration_tests(self) -> bool:
        """Run integration tests."""
        print("\n🔗 Running Integration Tests")
        print("=" * 50)

        success = True
        integration_test_files = [
            'tests/integration/test_end_to_end.py',
        ]

        for test_file in integration_test_files:
            if os.path.exists(test_file):
                print(f"Running {test_file}...")
                try:
                    module_name = test_file.replace('/', '.').replace('.py', '')
                    module = __import__(module_name, fromlist=[''])

                    loader = unittest.TestLoader()
                    suite = loader.loadTestsFromModule(module)
                    runner = unittest.TextTestRunner(verbosity=1, stream=sys.stdout)
                    result = runner.run(suite)

                    self.results["integration_tests"][test_file] = {
                        "tests_run": result.testsRun,
                        "failures": len(result.failures),
                        "errors": len(result.errors),
                        "success": result.wasSuccessful()
                    }

                    if not result.wasSuccessful():
                        success = False
                        print(f"  ❌ {test_file} failed")
                    else:
                        print(f"  ✅ {test_file} passed")

                except Exception as e:
                    print(f"  ❌ {test_file} error: {e}")
                    success = False
                    self.results["integration_tests"][test_file] = {"error": str(e)}
            else:
                print(f"  ⚠️  {test_file} not found")

        return success

    def run_benchmarks(self, iterations: int = 10) -> bool:
        """Run benchmark tests."""
        print(f"\n📊 Running Benchmarks ({iterations} iterations)")
        print("=" * 50)

        try:
            results = self.benchmark_runner.run_benchmarks(iterations)
            self.results["benchmarks"] = {
                "metrics_collected": len(results),
                "iterations": iterations,
                "timestamp": time.time()
            }

            print(f"  ✅ Benchmarks completed: {len(results)} metrics collected")

            # Check for performance regressions
            results_dict = [result.to_dict() for result in results]
            self._check_performance_regressions(results_dict)

            return True

        except Exception as e:
            print(f"  ❌ Benchmarks failed: {e}")
            self.results["benchmarks"] = {"error": str(e)}
            return False

    def _check_performance_regressions(self, benchmark_results: List[Dict[str, Any]]):
        """Check benchmark results for performance regressions."""
        print("  🔍 Checking for performance regressions...")

        regressions = []
        improvements = []

        for result in benchmark_results:
            test_name = result["test_name"]
            metric_name = result["metric_name"]
            value = result["value"]

            check = self.performance_baseline.check_regression(test_name, metric_name, value)

            if check["status"] == "regression":
                regressions.append({
                    "test": test_name,
                    "metric": metric_name,
                    "message": check["message"],
                    "baseline": check["baseline"],
                    "current": check["current"]
                })
            elif check["status"] == "improvement":
                improvements.append({
                    "test": test_name,
                    "metric": metric_name,
                    "message": check["message"]
                })

            # Update baseline with current value
            self.performance_baseline.update_baseline(test_name, metric_name, value)

        self.results["performance_checks"] = {
            "regressions": regressions,
            "improvements": improvements,
            "total_checks": len(benchmark_results)
        }

        if regressions:
            print(f"  ⚠️  Found {len(regressions)} performance regressions")
            for reg in regressions[:3]:  # Show first 3
                print(f"    - {reg['test']}: {reg['message']}")
        else:
            print("  ✅ No performance regressions detected")

        if improvements:
            print(f"  🎉 Found {len(improvements)} performance improvements")

    def run_comprehensive_data_tests(self) -> bool:
        """Run tests with comprehensive data sets."""
        print("\n📋 Running Comprehensive Data Tests")
        print("=" * 50)

        try:
            from aura_compression import ProductionHybridCompressor

            compressor = ProductionHybridCompressor(enable_aura=True)
            test_suite = TestDataGenerator.generate_compression_test_suite()

            # Initialize results structure
            self.results["comprehensive_data_tests"] = {}

            total_tests = 0
            total_passed = 0

            for data_type, messages in test_suite.items():
                print(f"Testing {data_type} ({len(messages)} messages)...")

                passed = 0
                for i, message in enumerate(messages):
                    try:
                        compressed, method, metadata = compressor.compress(message)
                        decompressed = compressor.decompress(compressed)

                        if decompressed == message:
                            passed += 1
                        else:
                            print(f"    ❌ Message {i} round-trip failed")

                    except Exception as e:
                        print(f"    ❌ Message {i} error: {e}")

                success_rate = passed / len(messages)
                print(".1%")

                total_tests += len(messages)
                total_passed += passed

                self.results["comprehensive_data_tests"][data_type] = {
                    "total": len(messages),
                    "passed": passed,
                    "success_rate": success_rate
                }

            overall_success_rate = total_passed / total_tests if total_tests > 0 else 0
            print(".1%")

            self.results["comprehensive_data_tests"]["overall"] = {
                "total_tests": total_tests,
                "total_passed": total_passed,
                "success_rate": overall_success_rate
            }

            return overall_success_rate > 0.99  # 99% success threshold

        except Exception as e:
            print(f"  ❌ Comprehensive data tests failed: {e}")
            self.results["comprehensive_data_tests"] = {"error": str(e)}
            return False

    def generate_summary_report(self) -> str:
        """Generate a comprehensive summary report."""
        report = []
        report.append("# AURA Compression Test Suite Report")
        report.append(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")

        # Overall status
        unit_success = all(r.get("success", False) for r in self.results["unit_tests"].values() if isinstance(r, dict))
        integration_success = all(r.get("success", False) for r in self.results["integration_tests"].values() if isinstance(r, dict))
        benchmark_success = "error" not in self.results["benchmarks"]

        report.append("## Overall Status")
        report.append(f"- Unit Tests: {'✅ PASS' if unit_success else '❌ FAIL'}")
        report.append(f"- Integration Tests: {'✅ PASS' if integration_success else '❌ FAIL'}")
        report.append(f"- Benchmarks: {'✅ PASS' if benchmark_success else '❌ FAIL'}")
        report.append("")

        # Detailed results
        for test_type, results in self.results.items():
            if test_type == "summary":
                continue

            report.append(f"## {test_type.replace('_', ' ').title()}")

            if isinstance(results, dict):
                for key, value in results.items():
                    if isinstance(value, dict):
                        if "success" in value:
                            status = "✅" if value["success"] else "❌"
                            report.append(f"- {key}: {status} ({value.get('tests_run', 0)} tests)")
                        elif "error" in value:
                            report.append(f"- {key}: ❌ Error - {value['error']}")
                        else:
                            report.append(f"- {key}: {value}")
                    else:
                        report.append(f"- {key}: {value}")
            else:
                report.append(f"Results: {results}")

            report.append("")

        return "\n".join(report)

    def save_results(self, filename: str = "test_results.json"):
        """Save complete test results."""
        with open(filename, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)

        print(f"📄 Detailed results saved to {filename}")

    def run_all_tests(self, iterations: int = 10) -> bool:
        """Run the complete test suite."""
        print("🚀 AURA Compression - Complete Test Suite")
        print("=" * 60)

        start_time = time.time()

        # Initialize results structure
        self.results = {
            "unit_tests": {},
            "integration_tests": {},
            "benchmarks": {},
            "performance_checks": {},
            "comprehensive_data_tests": {},
            "summary": {}
        }

        # Run all test suites
        unit_success = self.run_unit_tests()
        integration_success = self.run_integration_tests()
        benchmark_success = self.run_benchmarks(iterations)
        data_test_success = self.run_comprehensive_data_tests()

        # Calculate summary
        total_time = time.time() - start_time
        overall_success = unit_success and integration_success and benchmark_success and data_test_success

        self.results["summary"] = {
            "overall_success": overall_success,
            "total_time_seconds": total_time,
            "unit_tests_passed": unit_success,
            "integration_tests_passed": integration_success,
            "benchmarks_passed": benchmark_success,
            "data_tests_passed": data_test_success,
            "timestamp": time.time()
        }

        # Generate and display report
        report = self.generate_summary_report()
        print("\n" + "="*80)
        print(report)
        print("="*80)

        # Save results
        self.save_results()

        if overall_success:
            print("\n🎉 All tests passed successfully!")
        else:
            print("\n⚠️  Some tests failed - check the detailed results above")

        return overall_success


def main():
    parser = argparse.ArgumentParser(description="AURA Compression Comprehensive Test Runner")
    parser.add_argument('--unit', action='store_true', help='Run unit tests only')
    parser.add_argument('--integration', action='store_true', help='Run integration tests only')
    parser.add_argument('--benchmark', action='store_true', help='Run benchmarks only')
    parser.add_argument('--data', action='store_true', help='Run comprehensive data tests only')
    parser.add_argument('--all', action='store_true', help='Run complete test suite')
    parser.add_argument('--iterations', type=int, default=10, help='Number of benchmark iterations')
    parser.add_argument('--output', type=str, default='test_results.json', help='Output file for results')

    args = parser.parse_args()

    # Default to running all tests
    if not any([args.unit, args.integration, args.benchmark, args.data, args.all]):
        args.all = True

    runner = ComprehensiveTestRunner()

    try:
        success = True

        if args.unit or args.all:
            success &= runner.run_unit_tests()

        if args.integration or args.all:
            success &= runner.run_integration_tests()

        if args.benchmark or args.all:
            success &= runner.run_benchmarks(args.iterations)

        if args.data or args.all:
            success &= runner.run_comprehensive_data_tests()

        if args.all:
            # Generate final summary for complete run
            report = runner.generate_summary_report()
            print("\n" + "="*80)
            print("FINAL TEST SUITE SUMMARY")
            print("="*80)
            print(report)

        runner.save_results(args.output)

        if success:
            print("\n✅ Test suite completed successfully!")
            sys.exit(0)
        else:
            print("\n❌ Some tests failed!")
            sys.exit(1)

    except Exception as e:
        print(f"\n💥 Test runner failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()