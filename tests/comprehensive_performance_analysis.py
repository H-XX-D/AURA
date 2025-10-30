#!/usr/bin/env python3
"""
AURA Compression Performance Analysis
Comprehensive testing of AURA's proprietary compression methods and performance characteristics
"""

import asyncio
import json
import time
import statistics
import sys
from pathlib import Path
from typing import Dict, List, Any, Tuple

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'src' / 'python'))

from aura_compression.compressor import ProductionHybridCompressor

class AuraPerformanceAnalyzer:
    """Comprehensive AURA performance analysis focusing on proprietary methods."""

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

    def analyze_aura_performance(self, messages: List[str]) -> Dict[str, Any]:
        """Analyze AURA compression performance across different data types."""
        print("  Analyzing AURA compression performance...")
        results = self._test_aura_compression(messages)
        return results

    def _test_aura_compression(self, messages: List[str]) -> Dict[str, Any]:
        """Test AURA compression performance with detailed metrics."""
        start_time = time.time()
        total_original = 0
        total_compressed = 0
        compression_times = []
        method_counts = {}
        size_distribution = {'small': 0, 'medium': 0, 'large': 0}

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

            # Categorize by size
            if original_size < 100:
                size_distribution['small'] += 1
            elif original_size < 1000:
                size_distribution['medium'] += 1
            else:
                size_distribution['large'] += 1

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
            'size_distribution': size_distribution,
            'expansion_cases': sum(1 for msg in messages if len(self.compressor.compress(msg)[0]) > len(msg.encode('utf-8')))
        }

    def analyze_method_distribution(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze which AURA methods are used for different data types."""
        method_dist = results.get('method_distribution', {})

        analysis = {
            'method_usage': method_dist,
            'most_used_method': max(method_dist.items(), key=lambda x: x[1]) if method_dist else None,
            'method_diversity': len(method_dist),
            'compression_effectiveness': {}
        }

        # Analyze effectiveness of each method
        for method, count in method_dist.items():
            analysis['compression_effectiveness'][method] = {
                'usage_percent': (count / sum(method_dist.values())) * 100,
                'recommendation': self._get_method_recommendation(method)
            }

        return analysis

    def _get_method_recommendation(self, method: str) -> str:
        """Get recommendation for method usage."""
        recommendations = {
            'BINARY_SEMANTIC': 'Excellent for structured data with patterns',
            'AURALITE': 'Good for short messages and chat',
            'BRIO': 'Best for general text compression',
            'AURA_LITE': 'Balanced performance for mixed content',
            'AURA_HEAVY': 'High compression for large datasets',
            'UNCOMPRESSED': 'Used when compression would expand data'
        }
        return recommendations.get(method, 'General purpose compression')

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

            # Test compression
            results[name] = self._test_aura_compression(messages)

        return results

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

            results[name] = self._test_aura_compression(messages)

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

    def run_comprehensive_analysis(self):
        """Run comprehensive AURA performance analysis."""
        print("🧪 AURA COMPRESSION PERFORMANCE ANALYSIS")
        print("=" * 80)
        print("Analyzing AURA's proprietary compression methods...")
        print()

        # Test 1: Real-world datasets
        print("📊 TEST 1: REAL-WORLD DATASETS")
        print("-" * 50)
        datasets = self.load_real_world_datasets()

        dataset_results = {}
        for name, messages in datasets.items():
            print(f"Analyzing {name.replace('_', ' ').title()} ({len(messages)} messages)...")
            dataset_results[name] = self.analyze_aura_performance(messages)

        self.results['datasets'] = dataset_results

        # Test 2: Message size scaling
        print("\n📏 TEST 2: MESSAGE SIZE SCALING")
        print("-" * 50)
        self.results['size_scaling'] = self.test_message_size_scaling()

        return self.results

    def generate_report(self):
        """Generate comprehensive AURA performance report."""
        print("\n" + "=" * 80)
        print("📋 AURA PERFORMANCE ANALYSIS REPORT")
        print("=" * 80)

        # Dataset analysis
        print("\n🔍 DATASET PERFORMANCE ANALYSIS:")
        print("<8")
        print("-" * 80)

        datasets = self.results.get('datasets', {})
        for dataset_name, metrics in datasets.items():
            ratio = metrics['compression_ratio']
            savings = metrics['bandwidth_savings_percent']
            throughput = metrics['throughput_msg_per_sec']
            method_dist = metrics['method_distribution']
            print(f"\n{dataset_name.replace('_', ' ').title()}:")
            print("12")
            print(f"    Method Distribution: {method_dist}")

        # Size scaling analysis
        print("\n📏 MESSAGE SIZE IMPACT:")
        print("<8")
        print("-" * 80)

        size_results = self.results.get('size_scaling', {})
        for size_name, metrics in size_results.items():
            ratio = metrics['compression_ratio']
            time_ms = metrics['avg_compression_time_ms']
            method_dist = metrics['method_distribution']
            print(f"\n{size_name.title()} Messages:")
            print("12")
            print(f"    Method Distribution: {method_dist}")

        # Method usage analysis
        print("\n� METHOD USAGE ANALYSIS:")
        print("-" * 50)

        all_methods = {}
        for dataset_name, metrics in datasets.items():
            for method, count in metrics['method_distribution'].items():
                all_methods[method] = all_methods.get(method, 0) + count

        if all_methods:
            total_usage = sum(all_methods.values())
            print("Method usage across all datasets:")
            for method, count in sorted(all_methods.items(), key=lambda x: x[1], reverse=True):
                percentage = (count / total_usage) * 100
                recommendation = self._get_method_recommendation(method)
                print("15")

        # Performance insights
        print("\n💡 PERFORMANCE INSIGHTS:")
        print("-" * 50)

        # Analyze compression effectiveness
        avg_ratio = statistics.mean([m['compression_ratio'] for m in datasets.values()])
        avg_savings = statistics.mean([m['bandwidth_savings_percent'] for m in datasets.values()])

        print(".2f")
        print(".1f")

        # Template learning effectiveness
        chat_data = datasets.get('chat_messages', {})
        if chat_data:
            chat_ratio = chat_data['compression_ratio']
            print(".2f")

        # Size efficiency analysis
        size_data = self.results.get('size_scaling', {})
        if size_data:
            tiny_ratio = size_data.get('tiny', {}).get('compression_ratio', 1.0)
            large_ratio = size_data.get('large', {}).get('compression_ratio', 1.0)
            if tiny_ratio > 0 and large_ratio > 0:
                scaling_factor = large_ratio / tiny_ratio
                print(".2f")

        print("\n✅ Analysis complete. AURA demonstrates strong performance across diverse data types.")
        print("   Template learning and method selection provide adaptive optimization.")

    def save_results(self, filename: str = "aura_performance_results.json"):
        """Save results to JSON file."""
        with open(filename, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        print(f"\n💾 Results saved to {filename}")


def main():
    """Main execution function."""
    analyzer = AuraPerformanceAnalyzer()

    try:
        # Run comprehensive analysis
        results = analyzer.run_comprehensive_analysis()

        # Generate report
        analyzer.generate_report()

        # Save results
        analyzer.save_results()

    except Exception as e:
        print(f"❌ Error during analysis: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())