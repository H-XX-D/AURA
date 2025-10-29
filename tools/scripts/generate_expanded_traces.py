#!/usr/bin/env python3
"""
AURA Test Trace Generator

Generates comprehensive performance traces for testing and benchmarking.
Creates realistic conversational data with various message patterns.
"""

import json
import time
import random
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime, timedelta

# Add project root to path
ROOT = Path(__file__).resolve().parent
import sys
sys.path.insert(0, str(ROOT))

from aura_compression import ProductionHybridCompressor


class TraceGenerator:
    """Generates comprehensive test traces for AURA compression benchmarking."""

    def __init__(self):
        self.compressor = ProductionHybridCompressor(enable_gpu=True)
        self.base_timestamp = datetime(2025, 10, 27, 9, 0, 0)  # Start at 9 AM

    def get_realistic_messages(self) -> List[str]:
        """Generate realistic conversational messages covering various patterns."""

        # Template-based responses (should compress well)
        template_messages = [
            "I don't have access to that information.",
            "I cannot browse the internet or access external websites.",
            "I don't have real-time data access.",
            "I recommend checking the official documentation.",
            "That appears to be a technical issue.",
            "I suggest updating to the latest version.",
            "Please try restarting the application.",
            "The error indicates a configuration problem.",
            "I need more context to help you properly.",
            "This is outside my current capabilities.",
            "Let me help you with that step by step.",
            "The solution depends on your specific setup.",
            "I recommend consulting the documentation first.",
            "This requires administrative privileges.",
            "The process should complete automatically.",
            "Please check your system requirements.",
            "I can provide general guidance on this topic.",
            "The issue might be related to permissions.",
            "Try clearing your cache and cookies.",
            "This is a common configuration issue.",
        ]

        # Technical messages (mixed compression)
        technical_messages = [
            "To install the package, run: pip install numpy scipy matplotlib",
            "The API endpoint is: https://api.example.com/v2/users/123",
            "Error 404: Resource not found at /api/v1/data",
            "Connection timeout after 5000ms at database.example.com:5432",
            "Build completed successfully in 45.2 seconds",
            "Memory usage: 2.1 GB / 8.0 GB (26.3%)",
            "CPU utilization: 78% across 4 cores",
            "Database query executed in 123ms, returned 1,247 rows",
            "SSL certificate expires in 30 days",
            "Backup completed: 2.5 GB transferred in 180 seconds",
            "Deployment v1.2.3 started at 2025-10-27T14:30:00Z",
            "Health check passed: all systems operational",
            "Rate limit exceeded: 95/100 requests per minute",
            "Cache hit ratio: 87.3% (1,234 hits / 1,412 requests)",
            "Session expired - please authenticate again",
            "File upload failed: size exceeds 10MB limit",
            "API version 2.1.0 is now available",
            "Scheduled maintenance: 2 hours on 2025-10-28T03:00:00Z",
            "Security alert: unusual login attempt detected",
            "Performance degradation detected in service layer",
        ]

        # Conversational messages (variable compression)
        conversational_messages = [
            "Hello! How can I assist you today?",
            "That's an interesting question. Let me think about it.",
            "I understand your concern, and I'm here to help.",
            "Could you provide more details about the issue?",
            "Thank you for bringing this to my attention.",
            "I'm glad I could help resolve your problem.",
            "That makes perfect sense in this context.",
            "Would you like me to explain this further?",
            "I appreciate your patience while I look into this.",
            "This is a complex topic that deserves careful consideration.",
            "Let me break this down into simpler terms for you.",
            "Your feedback is valuable and helps improve the system.",
            "I can see why this would be confusing at first glance.",
            "This is actually a very common question among users.",
            "The key insight here is understanding the underlying mechanism.",
            "I recommend starting with the basics before diving deeper.",
            "This approach has proven effective in similar situations.",
            "The solution involves balancing multiple competing priorities.",
            "Experience shows that this method yields the best results.",
            "The most important factor is choosing the right tool for the job.",
        ]

        # Error messages and edge cases
        error_messages = [
            "Exception: ValueError: invalid literal for int() with base 10: 'abc'",
            "Traceback (most recent call last): File \"script.py\", line 42, in process_data",
            "ConnectionError: [Errno 110] Connection timed out",
            "KeyError: 'user_id' not found in session data",
            "TypeError: unsupported operand type(s) for +: 'int' and 'str'",
            "ImportError: No module named 'nonexistent_package'",
            "PermissionError: [Errno 13] Permission denied: '/etc/config.json'",
            "MemoryError: Unable to allocate 1.2 GB for array",
            "RecursionError: maximum recursion depth exceeded",
            "UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff in position 0",
            "AssertionError: Expected value 42, got 24",
            "IndexError: list index out of range (expected 0-9, got 15)",
            "AttributeError: 'NoneType' object has no attribute 'method'",
            "OSError: [Errno 28] No space left on device",
            "TimeoutError: Operation timed out after 30 seconds",
        ]

        # Long messages (test large data handling)
        long_messages = [
            "When developing machine learning models, it's crucial to consider multiple factors including data quality, model architecture selection, hyperparameter tuning, cross-validation strategies, and performance metrics. Each of these components plays a critical role in determining the success of your ML project. Data quality affects everything from training stability to final model accuracy. Model architecture must be chosen based on the specific problem type, data characteristics, and computational constraints. Hyperparameter tuning can significantly impact model performance but requires careful validation to avoid overfitting. Cross-validation helps ensure your model generalizes well to unseen data. Finally, selecting appropriate performance metrics ensures you're measuring what actually matters for your use case.",
            "System administration involves managing complex infrastructure components including servers, networks, databases, security policies, monitoring systems, backup strategies, and disaster recovery plans. Each component requires specialized knowledge and careful coordination. Server management includes hardware maintenance, OS updates, and resource optimization. Network configuration involves routing, firewalls, load balancers, and security groups. Database administration covers schema design, query optimization, backup procedures, and performance tuning. Security policies must balance accessibility with protection against threats. Monitoring systems track system health, performance metrics, and alert conditions. Backup strategies ensure data durability and quick recovery. Disaster recovery plans provide business continuity during major incidents.",
            "Software development methodologies have evolved significantly over the past few decades, from waterfall to agile to DevOps practices. Each approach has its strengths and weaknesses depending on project size, team structure, and organizational culture. Waterfall provides clear structure and documentation but lacks flexibility. Agile methodologies emphasize iterative development, customer collaboration, and responding to change. DevOps extends agile by integrating development and operations teams, automating deployment pipelines, and implementing continuous integration and delivery. Modern practices also include infrastructure as code, microservices architecture, containerization, and cloud-native development. The key is selecting the right methodology for your specific context and being willing to adapt as circumstances change.",
        ]

        # Combine all message types
        all_messages = (template_messages * 3 +  # Repeat templates for better compression stats
                       technical_messages * 2 +
                       conversational_messages * 2 +
                       error_messages +
                       long_messages)

        # Shuffle for realistic conversation flow
        random.shuffle(all_messages)
        return all_messages

    def generate_user_trace(self, user_id: int, num_messages: int = 50) -> List[Dict[str, Any]]:
        """Generate a complete trace for a single user."""

        messages = self.get_realistic_messages()
        trace_data = []

        current_timestamp = self.base_timestamp + timedelta(hours=user_id)  # Stagger users

        for turn in range(min(num_messages, len(messages))):
            message = messages[turn]

            # Add some realistic timing variation
            time_offset = timedelta(
                minutes=random.randint(1, 30),
                seconds=random.randint(0, 59)
            )
            current_timestamp += time_offset

            # Compress the message and measure performance
            start_time = time.time()
            try:
                compressed, method, metadata = self.compressor.compress(message)
                latency_ms = (time.time() - start_time) * 1000

                # Calculate compression ratio
                original_size = len(message.encode('utf-8'))
                compressed_size = len(compressed)
                compression_ratio = original_size / compressed_size if compressed_size > 0 else 1.0

                trace_entry = {
                    "user_id": user_id,
                    "turn": turn,
                    "timestamp": current_timestamp.isoformat(),
                    "message": message,
                    "message_length": len(message),
                    "method": method.name if hasattr(method, 'name') else str(method),
                    "compression_ratio": compression_ratio,
                    "latency_ms": latency_ms,
                    "original_size": original_size,
                    "compressed_size": compressed_size,
                    "success": True
                }

            except Exception as e:
                # Handle compression failures
                trace_entry = {
                    "user_id": user_id,
                    "turn": turn,
                    "timestamp": current_timestamp.isoformat(),
                    "message": message,
                    "message_length": len(message),
                    "method": "ERROR",
                    "compression_ratio": 1.0,
                    "latency_ms": (time.time() - start_time) * 1000,
                    "original_size": len(message.encode('utf-8')),
                    "compressed_size": len(message.encode('utf-8')),
                    "success": False,
                    "error": str(e)
                }

            trace_data.append(trace_entry)

        return trace_data

    def save_trace(self, user_id: int, trace_data: List[Dict[str, Any]], output_dir: str = "expanded_test_traces"):
        """Save trace data to JSONL file."""

        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)

        filename = f"user_{user_id}_traces.jsonl"
        filepath = output_path / filename

        with open(filepath, 'w', encoding='utf-8') as f:
            for entry in trace_data:
                json.dump(entry, f, ensure_ascii=False)
                f.write('\n')

        print(f"Generated {len(trace_data)} trace entries for user {user_id}")

    def generate_all_traces(self, num_users: int = 20, messages_per_user: int = 100):
        """Generate traces for multiple users."""

        print(f"Generating expanded test traces for {num_users} users...")
        print(f"Target: {messages_per_user} messages per user")

        total_entries = 0

        for user_id in range(1, num_users + 1):
            trace_data = self.generate_user_trace(user_id, messages_per_user)
            self.save_trace(user_id, trace_data)
            total_entries += len(trace_data)

        print(f"\nCompleted! Generated {total_entries} total trace entries")
        print(f"Average {total_entries/num_users:.1f} entries per user")

        # Generate summary statistics
        self.generate_summary_stats(num_users)

    def generate_summary_stats(self, num_users: int):
        """Generate summary statistics across all traces."""

        stats = {
            "total_users": num_users,
            "total_entries": 0,
            "compression_methods": {},
            "avg_compression_ratio": 0.0,
            "avg_latency_ms": 0.0,
            "success_rate": 0.0,
            "generated_at": datetime.now().isoformat()
        }

        total_ratio = 0.0
        total_latency = 0.0
        successful_entries = 0

        for user_id in range(1, num_users + 1):
            filepath = Path("expanded_test_traces") / f"user_{user_id}_traces.jsonl"

            if filepath.exists():
                with open(filepath, 'r', encoding='utf-8') as f:
                    for line in f:
                        entry = json.loads(line.strip())
                        stats["total_entries"] += 1

                        # Count compression methods
                        method = entry.get("method", "UNKNOWN")
                        stats["compression_methods"][method] = stats["compression_methods"].get(method, 0) + 1

                        # Accumulate statistics
                        if entry.get("success", True):
                            successful_entries += 1
                            total_ratio += entry.get("compression_ratio", 1.0)
                            total_latency += entry.get("latency_ms", 0.0)

        # Calculate averages
        if successful_entries > 0:
            stats["avg_compression_ratio"] = total_ratio / successful_entries
            stats["avg_latency_ms"] = total_latency / successful_entries
            stats["success_rate"] = successful_entries / stats["total_entries"]

        # Save summary
        with open("expanded_test_traces/trace_summary.json", 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)

        print("\nSummary statistics saved to expanded_test_traces/trace_summary.json")
        print(f"Total entries: {stats['total_entries']}")
        print(f"Average compression ratio: {stats['avg_compression_ratio']:.2f}")
        print(f"Average latency: {stats['avg_latency_ms']:.2f}ms")
        print(f"Success rate: {stats['success_rate']:.1%}")


def main():
    """Main entry point."""

    import argparse

    parser = argparse.ArgumentParser(description="Generate expanded AURA test traces")
    parser.add_argument("--users", type=int, default=20, help="Number of users to generate traces for")
    parser.add_argument("--messages", type=int, default=100, help="Number of messages per user")
    parser.add_argument("--output", type=str, default="expanded_test_traces", help="Output directory")

    args = parser.parse_args()

    generator = TraceGenerator()
    generator.generate_all_traces(args.users, args.messages)


if __name__ == "__main__":
    main()