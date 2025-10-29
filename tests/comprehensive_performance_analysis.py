#!/usr/bin/env python3
"""
Comprehensive AURA Compression Performance Analysis
Honest testing with real-world data for actionable insights
"""

import asyncio
import json
import time
import statistics
import sys
import gzip
import bz2
import lzma
from pathlib import Path
from typing import Dict, List, Any, Tuple

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'src' / 'python'))

from aura_compression.compressor import ProductionHybridCompressor

class ComprehensivePerformanceTester:
    """Comprehensive testing with real-world data and honest metrics."""

    def __init__(self):
        self.compressor = ProductionHybridCompressor(enable_aura=True, min_compression_size=1)
        self.results = {}

    def load_real_world_datasets(self) -> Dict[str, List[str]]:
        """Load realistic message datasets from various internet applications."""
        datasets = {}

        # Chat messages (WhatsApp, Slack, Discord style)
        datasets['chat_messages'] = [
            "Hey, how are you doing today?",
            "Thanks for the quick response!",
            "Can you help me with this issue?",
            "That sounds like a great idea!",
            "I'll get back to you soon",
            "Sorry for the delay",
            "Let me check that for you",
            "Perfect, that works for me",
            "Thanks for your help!",
            "Have a great day!",
            "I'll look into this",
            "That's very helpful",
            "I appreciate your assistance",
            "Let me know if you need anything else",
            "Thanks for reaching out",
            "I'm happy to help",
            "That makes sense",
            "I'll take care of it",
            "No problem at all",
            "You're welcome"
        ]

        # API responses (REST API style)
        datasets['api_responses'] = [
            '{"status": "success", "data": {"user_id": 12345, "name": "John Doe", "email": "john@example.com"}}',
            '{"status": "error", "message": "Invalid authentication token", "code": 401}',
            '{"status": "success", "data": {"posts": [{"id": 1, "title": "Hello World", "content": "This is a test post"}]}}',
            '{"status": "success", "data": {"stats": {"users": 1250, "posts": 5432, "comments": 8765}}}',
            '{"status": "success", "data": {"products": [{"id": 1, "name": "Widget", "price": 29.99}]}}',
            '{"status": "error", "message": "Resource not found", "code": 404}',
            '{"status": "success", "data": {"orders": [{"id": 1001, "total": 149.99, "status": "pending"}]}}'
        ]

        # Log entries (server logs)
        datasets['log_entries'] = [
            f"2024-01-15 10:{i:02d}:30 INFO [web-server] Request processed successfully - GET /api/users - 200 OK - 45ms"
            for i in range(10, 20)
        ] + [
            f"2024-01-15 10:{i:02d}:45 ERROR [database] Connection timeout - retrying in 5 seconds"
            for i in range(20, 25)
        ] + [
            f"2024-01-15 10:{i:02d}:12 WARN [cache] Cache miss for key user:12345"
            for i in range(25, 30)
        ]

        # Email subjects and bodies
        datasets['emails'] = [
            "Subject: Welcome to our platform\n\nDear user,\n\nWelcome to our amazing platform! We're excited to have you on board.\n\nBest regards,\nThe Team",
            "Subject: Password reset request\n\nHi there,\n\nWe received a request to reset your password. Click the link below to proceed.\n\nReset Link: https://example.com/reset/abc123\n\nIf you didn't request this, please ignore this email.\n\nBest,\nSecurity Team",
            "Subject: Your order has been shipped\n\nHello,\n\nYour order #12345 has been shipped and is on its way to you.\n\nTracking number: 1Z999AA1234567890\n\nYou can track your package here: https://tracking.example.com\n\nThank you for shopping with us!\n\nBest regards,\nShipping Team"
        ]

        # IoT sensor data (JSON format)
        datasets['iot_data'] = [
            '{"sensor_id": "temp_001", "timestamp": 1640995200, "temperature": 23.5, "humidity": 65.2, "location": "room_1"}',
            '{"sensor_id": "motion_002", "timestamp": 1640995260, "motion_detected": true, "confidence": 0.95, "location": "hallway"}',
            '{"sensor_id": "light_003", "timestamp": 1640995320, "lux": 450, "color_temp": 2700, "location": "living_room"}',
            '{"sensor_id": "power_004", "timestamp": 1640995380, "watts": 125.7, "voltage": 120.5, "location": "kitchen"}'
        ]

        # Repetitive content (common in data streams)
        datasets['repetitive'] = [
            "OK" * 50,  # Status responses
            "1" * 100,  # Binary data simulation
            "Hello World " * 30,  # Repeated phrases
            "ERROR: Connection failed\n" * 20,  # Error logs
            "data: {\"type\": \"heartbeat\"}\n\n" * 15  # Server-sent events
        ]

        return datasets

    def benchmark_compression_algorithms(self, messages: List[str]) -> Dict[str, Any]:
        """Benchmark AURA against standard compression algorithms."""
        algorithms = {
            'aura': self._test_aura_compression,
            'gzip': self._test_gzip_compression,
            'bz2': self._test_bz2_compression,
            'lzma': self._test_lzma_compression,
        }

        results = {}

        for name, func in algorithms.items():
            print(f"  Testing {name.upper()}...")
            results[name] = func(messages)

        return results

    def _test_aura_compression(self, messages: List[str]) -> Dict[str, Any]:
        """Test AURA compression performance."""
        start_time = time.time()
        total_original = 0
        total_compressed = 0
        compression_times = []
        method_counts = {}

        for msg in messages:
            msg_start = time.time()
            compressed, method, metadata = self.compressor.compress(msg)
            compression_times.append(time.time() - msg_start)

            original_size = len(msg.encode('utf-8'))
            compressed_size = len(compressed)

            total_original += original_size
            total_compressed += compressed_size

            method_name = method.name
            method_counts[method_name] = method_counts.get(method_name, 0) + 1

        total_time = time.time() - start_time

        return {
            'total_original_bytes': total_original,
            'total_compressed_bytes': total_compressed,
            'compression_ratio': total_original / total_compressed if total_compressed > 0 else 1.0,
            'bandwidth_savings_percent': ((total_original / total_compressed) - 1) * 100 if total_compressed > 0 else 0,
            'total_time_seconds': total_time,
            'avg_compression_time_ms': statistics.mean(compression_times) * 1000,
            'throughput_msg_per_sec': len(messages) / total_time,
            'throughput_mbps': (total_original * 8 / 1000000) / total_time,  # Mbps
            'method_distribution': method_counts,
            'expansion_cases': sum(1 for msg in messages if len(self.compressor.compress(msg)[0]) > len(msg.encode('utf-8')))
        }

    def _test_gzip_compression(self, messages: List[str]) -> Dict[str, Any]:
        """Test gzip compression performance."""
        start_time = time.time()
        total_original = 0
        total_compressed = 0
        compression_times = []

        for msg in messages:
            msg_start = time.time()
            compressed = gzip.compress(msg.encode('utf-8'))
            compression_times.append(time.time() - msg_start)

            original_size = len(msg.encode('utf-8'))
            compressed_size = len(compressed)

            total_original += original_size
            total_compressed += compressed_size

        total_time = time.time() - start_time

        return {
            'total_original_bytes': total_original,
            'total_compressed_bytes': total_compressed,
            'compression_ratio': total_original / total_compressed if total_compressed > 0 else 1.0,
            'bandwidth_savings_percent': ((total_original / total_compressed) - 1) * 100 if total_compressed > 0 else 0,
            'total_time_seconds': total_time,
            'avg_compression_time_ms': statistics.mean(compression_times) * 1000,
            'throughput_msg_per_sec': len(messages) / total_time,
            'throughput_mbps': (total_original * 8 / 1000000) / total_time,
            'expansion_cases': sum(1 for msg in messages if len(gzip.compress(msg.encode('utf-8'))) > len(msg.encode('utf-8')))
        }

    def _test_bz2_compression(self, messages: List[str]) -> Dict[str, Any]:
        """Test bz2 compression performance."""
        start_time = time.time()
        total_original = 0
        total_compressed = 0
        compression_times = []

        for msg in messages:
            msg_start = time.time()
            compressed = bz2.compress(msg.encode('utf-8'))
            compression_times.append(time.time() - msg_start)

            original_size = len(msg.encode('utf-8'))
            compressed_size = len(compressed)

            total_original += original_size
            total_compressed += compressed_size

        total_time = time.time() - start_time

        return {
            'total_original_bytes': total_original,
            'total_compressed_bytes': total_compressed,
            'compression_ratio': total_original / total_compressed if total_compressed > 0 else 1.0,
            'bandwidth_savings_percent': ((total_original / total_compressed) - 1) * 100 if total_compressed > 0 else 0,
            'total_time_seconds': total_time,
            'avg_compression_time_ms': statistics.mean(compression_times) * 1000,
            'throughput_msg_per_sec': len(messages) / total_time,
            'throughput_mbps': (total_original * 8 / 1000000) / total_time,
            'expansion_cases': sum(1 for msg in messages if len(bz2.compress(msg.encode('utf-8'))) > len(msg.encode('utf-8')))
        }

    def _test_lzma_compression(self, messages: List[str]) -> Dict[str, Any]:
        """Test LZMA compression performance."""
        start_time = time.time()
        total_original = 0
        total_compressed = 0
        compression_times = []

        for msg in messages:
            msg_start = time.time()
            compressed = lzma.compress(msg.encode('utf-8'))
            compression_times.append(time.time() - msg_start)

            original_size = len(msg.encode('utf-8'))
            compressed_size = len(compressed)

            total_original += original_size
            total_compressed += compressed_size

        total_time = time.time() - start_time

        return {
            'total_original_bytes': total_original,
            'total_compressed_bytes': total_compressed,
            'compression_ratio': total_original / total_compressed if total_compressed > 0 else 1.0,
            'bandwidth_savings_percent': ((total_original / total_compressed) - 1) * 100 if total_compressed > 0 else 0,
            'total_time_seconds': total_time,
            'avg_compression_time_ms': statistics.mean(compression_times) * 1000,
            'throughput_msg_per_sec': len(messages) / total_time,
            'throughput_mbps': (total_original * 8 / 1000000) / total_time,
            'expansion_cases': sum(1 for msg in messages if len(lzma.compress(msg.encode('utf-8'))) > len(msg.encode('utf-8')))
        }

    def test_message_size_scaling(self) -> Dict[str, Any]:
        """Test how compression performs with different message sizes."""
        size_tests = [
            ("tiny", 10, 50),      # 10-50 bytes
            ("small", 100, 500),   # 100-500 bytes
            ("medium", 1000, 5000), # 1KB-5KB
            ("large", 10000, 50000) # 10KB-50KB
        ]

        results = {}

        for name, min_size, max_size in size_tests:
            print(f"  Testing {name} messages ({min_size}-{max_size} bytes)...")

            # Generate messages of specific sizes
            messages = []
            for i in range(20):  # 20 messages per size category
                if name == "tiny":
                    msg = f"Message {i} with some text"
                elif name == "small":
                    msg = f"Message {i} with " + "some additional text " * 5
                elif name == "medium":
                    msg = f"Message {i} with " + "some additional text " * 50
                else:  # large
                    msg = f"Message {i} with " + "some additional text " * 500

                # Trim to approximate size range
                while len(msg.encode('utf-8')) > max_size:
                    msg = msg[:-10]
                while len(msg.encode('utf-8')) < min_size:
                    msg += " padding"

                messages.append(msg)

            results[name] = self.benchmark_compression_algorithms(messages)

        return results

    def test_network_conditions(self) -> Dict[str, Any]:
        """Test performance under different network conditions."""
        network_conditions = [
            ("dialup", 56, 200, 0.05),      # 56Kbps, 200ms latency, 5% loss
            ("dsl", 1000, 50, 0.01),        # 1Mbps, 50ms latency, 1% loss
            ("cable", 25000, 20, 0.005),    # 25Mbps, 20ms latency, 0.5% loss
            ("fiber", 100000, 5, 0.001),    # 100Mbps, 5ms latency, 0.1% loss
        ]

        # Use a standard message set
        messages = self.load_real_world_datasets()['chat_messages'] * 10  # 200 messages

        results = {}

        for name, bandwidth_kbps, latency_ms, loss_rate in network_conditions:
            print(f"  Testing {name} conditions ({bandwidth_kbps}Kbps, {latency_ms}ms latency)...")

            # Simulate network transmission time
            aura_results = self._test_aura_compression(messages)

            # Calculate network transmission times
            original_transmission_time = (aura_results['total_original_bytes'] * 8 / 1000) / bandwidth_kbps
            compressed_transmission_time = (aura_results['total_compressed_bytes'] * 8 / 1000) / bandwidth_kbps

            # Add latency and loss effects
            total_latency = latency_ms / 1000 * len(messages)  # Round trip for each message
            retransmission_time = original_transmission_time * loss_rate * 2  # Retransmission overhead

            results[name] = {
                'compression_results': aura_results,
                'original_transmission_seconds': original_transmission_time,
                'compressed_transmission_seconds': compressed_transmission_time,
                'latency_overhead_seconds': total_latency,
                'retransmission_overhead_seconds': retransmission_time,
                'total_original_time_seconds': original_transmission_time + total_latency + retransmission_time,
                'total_compressed_time_seconds': compressed_transmission_time + total_latency + retransmission_time,
                'time_savings_percent': ((original_transmission_time - compressed_transmission_time) / original_transmission_time) * 100 if original_transmission_time > 0 else 0
            }

        return results

    def run_comprehensive_tests(self):
        """Run all comprehensive tests."""
        print("🧪 COMPREHENSIVE AURA COMPRESSION PERFORMANCE ANALYSIS")
        print("=" * 80)
        print("Running honest tests with real-world data for actionable insights...")
        print()

        # Test 1: Real-world datasets
        print("📊 TEST 1: REAL-WORLD DATASETS")
        print("-" * 50)
        datasets = self.load_real_world_datasets()

        dataset_results = {}
        for name, messages in datasets.items():
            print(f"Testing {name.replace('_', ' ').title()} ({len(messages)} messages)...")
            dataset_results[name] = self.benchmark_compression_algorithms(messages)

        self.results['datasets'] = dataset_results

        # Test 2: Message size scaling
        print("\n📏 TEST 2: MESSAGE SIZE SCALING")
        print("-" * 50)
        self.results['size_scaling'] = self.test_message_size_scaling()

        # Test 3: Network conditions
        print("\n🌐 TEST 3: NETWORK CONDITIONS IMPACT")
        print("-" * 50)
        self.results['network_conditions'] = self.test_network_conditions()

        return self.results

    def generate_report(self):
        """Generate comprehensive performance report."""
        print("\n" + "=" * 80)
        print("📋 COMPREHENSIVE PERFORMANCE REPORT")
        print("=" * 80)

        # Dataset comparison
        print("\n🔍 DATASET PERFORMANCE COMPARISON:")
        print("<8")
        print("-" * 80)

        datasets = self.results.get('datasets', {})
        for dataset_name, algorithms in datasets.items():
            print(f"\n{dataset_name.replace('_', ' ').title()}:")
            for algo_name, metrics in algorithms.items():
                ratio = metrics['compression_ratio']
                savings = metrics['bandwidth_savings_percent']
                throughput = metrics['throughput_msg_per_sec']
                print("12")

        # Size scaling analysis
        print("\n📏 MESSAGE SIZE IMPACT:")
        print("<8")
        print("-" * 80)

        datasets = self.results.get('datasets', {})

        size_results = self.results.get('size_scaling', {})
        for size_name, algorithms in size_results.items():
            print(f"\n{size_name.title()} Messages:")
            for algo_name, metrics in algorithms.items():
                ratio = metrics['compression_ratio']
                time_ms = metrics['avg_compression_time_ms']
                print("12")

        # Network conditions analysis
        print("\n🌐 NETWORK CONDITIONS IMPACT:")
        print("<12")
        print("-" * 80)

        network_results = self.results.get('network_conditions', {})
        for condition_name, data in network_results.items():
            comp_results = data['compression_results']
            time_savings = data['time_savings_percent']
            print(f"\n{condition_name.title()}:")
            print(".2f")
            print(".1f")
            print(".1f")

        # Honest recommendations
        print("\n💡 HONEST RECOMMENDATIONS:")
        print("-" * 50)

        # Analyze AURA's strengths and weaknesses
        aura_datasets = {}
        gzip_datasets = {}

        for dataset_name, algorithms in datasets.items():
            if 'aura' in algorithms:
                aura_datasets[dataset_name] = algorithms['aura']['compression_ratio']
            if 'gzip' in algorithms:
                gzip_datasets[dataset_name] = algorithms['gzip']['compression_ratio']

        aura_avg_ratio = statistics.mean(aura_datasets.values()) if aura_datasets else 1.0
        gzip_avg_ratio = statistics.mean(gzip_datasets.values()) if gzip_datasets else 1.0

        print(f"  AURA average compression ratio: {aura_avg_ratio:.2f}x")
        print(f"  Gzip average compression ratio: {gzip_avg_ratio:.2f}x")
        if aura_avg_ratio > gzip_avg_ratio:
            print("  ✅ AURA outperforms gzip on average")
        else:
            print("  ⚠️ AURA underperforms compared to gzip")

        # Performance analysis
        chat_performance = datasets.get('chat_messages', {}).get('aura', {})
        if chat_performance:
            chat_ratio = chat_performance['compression_ratio']
            if chat_ratio > 2.0:
                print("  ✅ Excellent for chat applications")
            elif chat_ratio > 1.5:
                print("  ⚠️ Good for chat applications")
            else:
                print("  ❌ Poor for chat applications")

        # Network impact
        dialup_results = network_results.get('dialup', {})
        if dialup_results:
            time_savings = dialup_results['time_savings_percent']
            if time_savings > 20:
                print("  ✅ Significant benefits on slow networks")
            elif time_savings > 10:
                print("  ⚠️ Moderate benefits on slow networks")
            else:
                print("  ❌ Minimal benefits on slow networks")

        print("\n🏆 BOTTOM LINE:")
        print("-" * 50)
        print("AURA provides specialized compression for predictable message patterns.")
        print("Best suited for chatbots, APIs, and structured data with known templates.")
        print("Consider traditional compression (gzip) for arbitrary internet traffic.")
        print("=" * 80)

def main():
    """Run comprehensive performance analysis."""
    tester = ComprehensivePerformanceTester()
    results = tester.run_comprehensive_tests()
    tester.generate_report()

    # Save results for further analysis
    with open('/Users/hendrixx./AURA/comprehensive_performance_results.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)

    print("\n💾 Results saved to: comprehensive_performance_results.json")

if __name__ == "__main__":
    main()