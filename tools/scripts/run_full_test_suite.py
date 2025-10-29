#!/usr/bin/env python3
"""
AURA Full System Test Suite
Runs all tests and generates comprehensive report
"""
import subprocess
import sys
import time
import os
from pathlib import Path


class TestSuiteRunner:
    """Orchestrates running all AURA tests."""

    def __init__(self):
        self.results = {}
        self.start_time = None
        self.total_tests = 0
        self.total_passed = 0
        self.total_failed = 0

    def print_header(self, title):
        """Print formatted section header."""
        print("\n" + "=" * 80)
        print(f"  {title}")
        print("=" * 80 + "\n")

    def run_test_file(self, test_file, description):
        """Run a single test file and capture results."""
        print(f"▶ Running: {description}")
        print(f"  File: {test_file}")
        print("-" * 80)

        start = time.time()
        try:
            result = subprocess.run(
                [sys.executable, test_file],
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            elapsed = time.time() - start

            self.results[test_file] = {
                'description': description,
                'returncode': result.returncode,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'elapsed': elapsed,
                'passed': result.returncode == 0
            }

            if result.returncode == 0:
                print(f"✅ PASSED ({elapsed:.2f}s)")
                self.total_passed += 1
            else:
                print(f"❌ FAILED ({elapsed:.2f}s)")
                self.total_failed += 1
                if result.stderr:
                    print(f"\nError output:\n{result.stderr[:500]}")

            print()
            return result.returncode == 0

        except subprocess.TimeoutExpired:
            elapsed = time.time() - start
            print(f"⏱️  TIMEOUT ({elapsed:.2f}s)")
            self.results[test_file] = {
                'description': description,
                'returncode': -1,
                'stdout': '',
                'stderr': 'Test timed out after 5 minutes',
                'elapsed': elapsed,
                'passed': False
            }
            self.total_failed += 1
            return False

        except Exception as e:
            elapsed = time.time() - start
            print(f"💥 ERROR: {str(e)}")
            self.results[test_file] = {
                'description': description,
                'returncode': -1,
                'stdout': '',
                'stderr': str(e),
                'elapsed': elapsed,
                'passed': False
            }
            self.total_failed += 1
            return False

    def run_all_tests(self):
        """Run all AURA tests in sequence."""
        self.start_time = time.time()

        self.print_header("🚀 AURA FULL SYSTEM TEST SUITE")
        print(f"Start time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Python version: {sys.version}")
        print()

        # Define all test suites
        test_suites = [
            # Core functionality
            ("tests/test_core_functionality.py", "Core Functionality Tests"),

            # AuraHeavy tests
            ("tests/test_aura_heavy.py", "AuraHeavy Compression Layer Tests"),

            # AURA Lite codec
            ("tests/test_aura_lite_codec.py", "AURA Lite Codec Tests"),

            # Template system
            ("tests/test_template_anchor_sync.py", "Template Anchor Synchronization Tests"),

            # Discovery and routing
            ("tests/test_discovery_working.py", "Discovery System Tests"),

            # Patent claims verification
            ("tests/test_patent_claims.py", "Patent Claims Verification Tests"),

            # Real-world scenarios
            ("tests/test_real_world_scenario.py", "Real-World Scenario Tests"),

            # Client-server integration
            ("tests/test_client_server_integration.py", "Client-Server Integration Tests"),

            # Streaming integration
            ("tests/test_streaming_integration.py", "Streaming Integration Tests"),
        ]

        # Run each test suite
        self.print_header("📋 RUNNING TEST SUITES")

        for test_file, description in test_suites:
            if not Path(test_file).exists():
                print(f"⚠️  SKIPPED: {description} (file not found)")
                print(f"   File: {test_file}\n")
                continue

            self.total_tests += 1
            self.run_test_file(test_file, description)

        # Performance/stress tests (optional - longer running)
        self.print_header("⚡ PERFORMANCE & STRESS TESTS (OPTIONAL)")

        stress_tests = [
            ("tests/stress_test_10_users.py", "Stress Test: 10 Concurrent Users"),
            # Skip 50 user test by default (takes too long)
            # ("tests/stress_test_50_users.py", "Stress Test: 50 Concurrent Users"),
        ]

        print("Note: Running basic stress tests only. For full stress tests, run manually.")
        print()

        for test_file, description in stress_tests:
            if Path(test_file).exists():
                self.total_tests += 1
                self.run_test_file(test_file, description)

        # Generate final report
        self.generate_report()

    def generate_report(self):
        """Generate comprehensive test report."""
        total_time = time.time() - self.start_time

        self.print_header("📊 FINAL TEST REPORT")

        # Summary statistics
        print("SUMMARY STATISTICS:")
        print(f"  Total test suites run: {self.total_tests}")
        print(f"  Passed: {self.total_passed} ({self.total_passed/self.total_tests*100:.1f}%)")
        print(f"  Failed: {self.total_failed} ({self.total_failed/self.total_tests*100:.1f}%)")
        print(f"  Total execution time: {total_time:.2f}s ({total_time/60:.1f} minutes)")
        print()

        # Detailed results
        print("DETAILED RESULTS:")
        print("-" * 80)

        for test_file, result in self.results.items():
            status = "✅ PASS" if result['passed'] else "❌ FAIL"
            print(f"{status} | {result['description']}")
            print(f"       Time: {result['elapsed']:.2f}s | File: {test_file}")

            if not result['passed'] and result['stderr']:
                # Show first few lines of error
                error_preview = result['stderr'][:200].replace('\n', ' ')
                print(f"       Error: {error_preview}...")
            print()

        # Final verdict
        print("=" * 80)
        if self.total_failed == 0:
            print("🎉 ALL TESTS PASSED! AURA is ready for production.")
            verdict = True
        else:
            print(f"⚠️  {self.total_failed} TEST SUITE(S) FAILED. Review errors above.")
            verdict = False
        print("=" * 80)

        # Save report to file
        self.save_report_to_file()

        return verdict

    def save_report_to_file(self):
        """Save detailed report to file."""
        report_file = "test_results/latest_test_report.txt"
        os.makedirs("test_results", exist_ok=True)

        with open(report_file, 'w') as f:
            f.write("AURA FULL SYSTEM TEST SUITE REPORT\n")
            f.write(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 80 + "\n\n")

            f.write(f"Total test suites: {self.total_tests}\n")
            f.write(f"Passed: {self.total_passed}\n")
            f.write(f"Failed: {self.total_failed}\n")
            f.write(f"Success rate: {self.total_passed/self.total_tests*100:.1f}%\n\n")

            for test_file, result in self.results.items():
                f.write(f"\n{'='*80}\n")
                f.write(f"Test: {result['description']}\n")
                f.write(f"File: {test_file}\n")
                f.write(f"Status: {'PASSED' if result['passed'] else 'FAILED'}\n")
                f.write(f"Time: {result['elapsed']:.2f}s\n")

                if result['stdout']:
                    f.write(f"\nOutput:\n{result['stdout']}\n")

                if result['stderr']:
                    f.write(f"\nErrors:\n{result['stderr']}\n")

        print(f"\n📝 Detailed report saved to: {report_file}")


def main():
    """Main entry point."""
    runner = TestSuiteRunner()

    try:
        runner.run_all_tests()

        # Exit with appropriate code
        sys.exit(0 if runner.total_failed == 0 else 1)

    except KeyboardInterrupt:
        print("\n\n⚠️  Test suite interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n💥 Fatal error running test suite: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
