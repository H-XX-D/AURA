#!/usr/bin/env python3
"""
AURA Compression System - Master Test Runner
===========================================

Comprehensive test suite runner for the optimized AURA compression system.
Executes all test files and generates detailed reports.

Features:
- Parallel test execution
- Detailed console output
- JSON report generation
- Performance timing
- Success/failure tracking
- Comprehensive error reporting

Usage:
    python tests/test_runner.py [--verbose] [--json-report] [--fail-fast]
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path
from typing import Dict, List, Any, Tuple
from datetime import datetime

class TestRunner:
    """Master test runner for AURA compression system tests."""

    def __init__(self, verbose: bool = False, json_report: bool = True, fail_fast: bool = False):
        self.verbose = verbose
        self.json_report = json_report
        self.fail_fast = fail_fast
        self.test_results = {}
        self.start_time = None
        self.end_time = None

        # Test files to run
        self.test_files = [
            'test_compression_core.py',
            'test_compression_methods.py',
            'test_compression_thresholds.py',
            'test_audit_integration.py',
            # Future test files to be added:
            # 'test_performance_benchmarking.py',
            # 'test_edge_cases.py',
            # 'test_acceleration_features.py',
            # 'test_template_system.py',
            # 'test_network_aware.py',
            # 'test_integration_scenarios.py',
            # 'test_compliance_validation.py',
            # 'test_stress_testing.py',
            # 'test_data_formats.py',
            # 'test_memory_management.py',
            # 'test_concurrent_operations.py',
            # 'test_adaptive_learning.py',
            # 'test_validation_pipeline.py',
            # 'test_benchmarking_suite.py'
        ]

    def print_header(self):
        """Print the test suite header."""
        print("=" * 80)
        print("AURA COMPRESSION SYSTEM - COMPREHENSIVE TEST SUITE")
        print("=" * 80)
        print(f"Test Environment: Python {sys.version.split()[0]}")
        print(f"Working Directory: {os.getcwd()}")
        print(f"Test Files: {len(self.test_files)}")
        print(f"Verbose Mode: {'Enabled' if self.verbose else 'Disabled'}")
        print(f"JSON Report: {'Enabled' if self.json_report else 'Disabled'}")
        print(f"Fail Fast: {'Enabled' if self.fail_fast else 'Disabled'}")
        print("=" * 80)
        print()

    def run_test_file(self, test_file: str) -> Tuple[bool, float, str]:
        """
        Run a single test file and return results.

        Args:
            test_file: Name of the test file to run

        Returns:
            Tuple of (success: bool, duration: float, output: str)
        """
        test_path = Path(__file__).parent / test_file

        if not test_path.exists():
            error_msg = f"Test file not found: {test_file}"
            print(f"❌ ERROR: {error_msg}")
            return False, 0.0, error_msg

        print(f"Running {test_file}")
        print("=" * (len(test_file) + 8))

        start_time = time.time()

        try:
            # Capture output by redirecting stdout
            import subprocess
            result = subprocess.run(
                [sys.executable, str(test_path)],
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )

            duration = time.time() - start_time

            if result.returncode == 0:
                print("✅ PASS")
                if self.verbose:
                    print("Output:")
                    print(result.stdout)
                return True, duration, result.stdout
            else:
                print("❌ FAIL")
                print("Error Output:")
                print(result.stderr)
                if result.stdout and self.verbose:
                    print("Standard Output:")
                    print(result.stdout)
                return False, duration, result.stderr

        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            error_msg = f"Test timed out after 300 seconds: {test_file}"
            print(f"⏰ TIMEOUT: {error_msg}")
            return False, duration, error_msg

        except Exception as e:
            duration = time.time() - start_time
            error_msg = f"Test execution failed: {str(e)}"
            print(f"💥 ERROR: {error_msg}")
            return False, duration, error_msg

    def run_all_tests(self) -> bool:
        """Run all test files and return overall success."""
        self.start_time = time.time()
        self.print_header()

        total_tests = len(self.test_files)
        passed_tests = 0
        failed_tests = 0
        total_duration = 0.0

        print(f"Running {total_tests} test files...\n")

        for i, test_file in enumerate(self.test_files, 1):
            print(f"[{i}/{total_tests}] ", end="")

            success, duration, output = self.run_test_file(test_file)

            self.test_results[test_file] = {
                'success': success,
                'duration': duration,
                'output': output,
                'timestamp': datetime.now().isoformat()
            }

            total_duration += duration

            if success:
                passed_tests += 1
                print(f"✅ PASS {test_file} ({duration:.2f}s)")
            else:
                failed_tests += 1
                print(f"❌ FAIL {test_file} ({duration:.2f}s)")

                if self.fail_fast:
                    print("\n❌ FAIL FAST: Stopping execution due to test failure")
                    break

            print()

        self.end_time = time.time()

        # Print summary
        self.print_summary(passed_tests, failed_tests, total_tests, total_duration)

        # Generate JSON report if requested
        if self.json_report:
            self.generate_json_report()

        return failed_tests == 0

    def print_summary(self, passed: int, failed: int, total: int, duration: float):
        """Print the test execution summary."""
        print("=" * 80)
        print("TEST SUITE SUMMARY")
        print("=" * 80)

        for test_file, result in self.test_results.items():
            status = "✅ PASS" if result['success'] else "❌ FAIL"
            print(f"{status} {test_file} ({result['duration']:.2f}s)")

        print()
        print("Overall Results:")
        print(f"  Total Tests: {total}")
        print(f"  Passed: {passed}")
        print(f"  Failed: {failed}")
        print(f"  Success Rate: {(passed/total*100):.1f}%" if total > 0 else "N/A")
        print(f"  Total Time: {duration:.2f}s")
        print()

        if failed == 0:
            print("✅ Test suite PASSED - All tests successful")
        else:
            print(f"❌ Test suite FAILED - {failed} test(s) failed")

    def generate_json_report(self):
        """Generate a detailed JSON report of test results."""
        report = {
            'test_suite': 'AURA Compression System - Comprehensive Test Suite',
            'timestamp': datetime.now().isoformat(),
            'environment': {
                'python_version': sys.version,
                'working_directory': str(Path.cwd()),
                'platform': sys.platform
            },
            'configuration': {
                'verbose': self.verbose,
                'json_report': self.json_report,
                'fail_fast': self.fail_fast
            },
            'summary': {
                'total_tests': len(self.test_results),
                'passed_tests': sum(1 for r in self.test_results.values() if r['success']),
                'failed_tests': sum(1 for r in self.test_results.values() if not r['success']),
                'total_duration': sum(r['duration'] for r in self.test_results.values()),
                'success_rate': (sum(1 for r in self.test_results.values() if r['success']) / len(self.test_results) * 100) if self.test_results else 0
            },
            'test_results': self.test_results,
            'execution_time': {
                'start': datetime.fromtimestamp(self.start_time).isoformat() if self.start_time else None,
                'end': datetime.fromtimestamp(self.end_time).isoformat() if self.end_time else None,
                'duration': self.end_time - self.start_time if self.start_time and self.end_time else None
            }
        }

        report_path = Path(__file__).parent / 'test_report.json'
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        print(f"\n📄 JSON report saved to: {report_path}")


def main():
    """Main entry point for the test runner."""
    parser = argparse.ArgumentParser(
        description='AURA Compression System - Master Test Runner',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tests/test_runner.py                    # Run all tests
  python tests/test_runner.py --verbose         # Run with verbose output
  python tests/test_runner.py --fail-fast       # Stop on first failure
  python tests/test_runner.py --no-json-report  # Skip JSON report generation
        """
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output showing test details'
    )

    parser.add_argument(
        '--json-report', '-j',
        action='store_true',
        default=True,
        help='Generate JSON report (default: enabled)'
    )

    parser.add_argument(
        '--no-json-report',
        action='store_false',
        dest='json_report',
        help='Disable JSON report generation'
    )

    parser.add_argument(
        '--fail-fast', '-f',
        action='store_true',
        help='Stop execution on first test failure'
    )

    args = parser.parse_args()

    # Change to the project root directory
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)

    # Run the tests
    runner = TestRunner(
        verbose=args.verbose,
        json_report=args.json_report,
        fail_fast=args.fail_fast
    )

    success = runner.run_all_tests()

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()