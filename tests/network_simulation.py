#!/usr/bin/env python3
"""
Realistic Client-Server Network Simulation

Simulates:
- Human client sending prompts to AI server
- AI server responding with larger responses
- Real-world network latency and packet delays
- 1 minute duration with varying message sizes
- Honest performance reporting

This demonstrates AURA's real use case: AI-to-AI structured responses.
"""

import sys
import time
import random
import socket
import threading
from pathlib import Path
from dataclasses import dataclass
from typing import List, Tuple
import statistics

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aura_compression.compressor_refactored import ProductionHybridCompressor


@dataclass
class NetworkMetrics:
    """Track network performance metrics"""
    direction: str  # "client->server" or "server->client"
    original_size: int
    compressed_size: int
    compression_ratio: float
    compression_time_ms: float
    decompression_time_ms: float
    network_latency_ms: float
    method: str
    partial_match: bool = False
    match_coverage: float = 0.0


class SimulatedNetwork:
    """Simulates real-world network characteristics"""

    def __init__(self, base_latency_ms: float = 50.0, jitter_ms: float = 10.0):
        self.base_latency_ms = base_latency_ms
        self.jitter_ms = jitter_ms

    def transmit(self, data: bytes) -> Tuple[bytes, float]:
        """Simulate network transmission with latency and jitter"""
        # Pre-calculate to minimize overhead
        latency_ms = self.base_latency_ms + random.uniform(-self.jitter_ms, self.jitter_ms) + (len(data) / 1024.0)

        # Sleep to simulate network delay (convert ms to seconds)
        time.sleep(latency_ms * 0.001)

        return data, latency_ms


class AIServer:
    """Simulates an AI server responding to prompts"""

    def __init__(self, compressor: ProductionHybridCompressor):
        self.compressor = compressor
        self.responses = self._load_ai_responses()

    def _load_ai_responses(self) -> List[str]:
        """Load realistic AI response templates"""
        return [
            # Short technical responses
            "The function you're looking for is `numpy.array()`. It creates an n-dimensional array from a Python list or tuple. Here's a quick example:\n\n```python\nimport numpy as np\narr = np.array([1, 2, 3, 4, 5])\nprint(arr)\n```\n\nThis creates a 1D array with the values 1 through 5.",

            # Medium explanations
            "To fix this error, you need to check your import statements. The issue is likely caused by a circular dependency between your modules. Here's what you should do:\n\n1. Review your import structure\n2. Move imports inside functions if needed\n3. Consider restructuring your code to break the circular dependency\n\nCircular imports happen when Module A imports Module B, and Module B imports Module A. Python can't resolve this cleanly. The best solution is to refactor your code so the dependency only goes one way.",

            # Long detailed responses
            "Based on the error message you're seeing, this is a classic case of a race condition in your multithreaded code. Let me explain what's happening:\n\nWhen multiple threads try to access the same shared resource (in your case, the database connection pool) without proper synchronization, you can get unpredictable behavior. The error \"connection already closed\" suggests that one thread closed the connection while another was still using it.\n\nHere's how to fix it:\n\n1. **Use a thread-safe connection pool**: Libraries like `sqlalchemy` provide built-in connection pooling that handles thread safety automatically.\n\n2. **Implement proper locking**: If you must manage connections manually, use `threading.Lock()` to ensure only one thread accesses the connection at a time.\n\n3. **Use context managers**: Always use `with` statements when working with database connections to ensure they're properly closed.\n\nHere's a corrected example:\n\n```python\nimport threading\nfrom sqlalchemy import create_engine\nfrom sqlalchemy.orm import sessionmaker\n\n# Create thread-safe engine\nengine = create_engine('postgresql://user:pass@localhost/db', pool_size=10, max_overflow=20)\nSession = sessionmaker(bind=engine)\n\ndef worker():\n    # Each thread gets its own session\n    session = Session()\n    try:\n        result = session.query(MyTable).all()\n        # Process results\n    finally:\n        session.close()\n```\n\nThis approach ensures each thread has its own database session, preventing conflicts.",

            # Code review responses
            "I've reviewed your code and found several issues:\n\n**Critical Issues:**\n- Line 45: Potential SQL injection vulnerability. Use parameterized queries instead of string concatenation.\n- Line 78: Memory leak - file handle not being closed. Use context manager (`with open()`).\n- Line 112: Race condition when accessing shared state without locking.\n\n**Performance Issues:**\n- Line 23: O(n²) algorithm could be optimized to O(n log n) using sorting.\n- Line 156: Unnecessary list copy - use generator for better memory efficiency.\n\n**Style Issues:**\n- Inconsistent naming: mix of camelCase and snake_case.\n- Missing docstrings on public functions.\n- Some functions exceed 50 lines - consider breaking them up.\n\nOverall, the logic is sound but needs security and performance improvements before production deployment.",

            # Troubleshooting responses
            "The 404 error you're getting suggests the route isn't being registered correctly. Let's debug this step by step:\n\nFirst, check that your blueprint is registered:\n```python\nfrom flask import Flask, Blueprint\n\napi = Blueprint('api', __name__, url_prefix='/api')\n\n@api.route('/users')\ndef get_users():\n    return {'users': []}\n\napp = Flask(__name__)\napp.register_blueprint(api)  # Don't forget this!\n```\n\nIf that's correct, verify the route is registered:\n```python\nprint(app.url_map)\n```\n\nThis will show all registered routes. If `/api/users` isn't listed, your blueprint registration failed.",
        ]

    def generate_response(self, prompt: str) -> str:
        """Generate AI response based on prompt length and content"""
        # Select response based on prompt characteristics
        if len(prompt) < 50:
            # Short question -> short/medium response
            response = random.choice(self.responses[:3])
        elif len(prompt) < 150:
            # Medium question -> medium/long response
            response = random.choice(self.responses[2:5])
        else:
            # Long question -> detailed response
            response = random.choice(self.responses[3:])

        # Add some variation
        if random.random() > 0.7:
            response += "\n\nLet me know if you need any clarification on this!"

        return response


class HumanClient:
    """Simulates a human client sending prompts"""

    def __init__(self):
        self.prompts = self._load_prompts()

    def _load_prompts(self) -> List[str]:
        """Load realistic human prompts of varying sizes"""
        return [
            # Short questions (20-50 chars)
            "How do I create a numpy array?",
            "What's wrong with this code?",
            "Why am I getting this error?",
            "Can you explain this function?",
            "How do I fix this bug?",

            # Medium questions (50-150 chars)
            "I'm getting an ImportError when I try to run my Python script. The error says 'cannot import name X from Y'. What does this mean and how do I fix it?",
            "My Flask app returns 404 for all routes. I've checked the code and everything looks correct. What could be causing this?",
            "I have a list of dictionaries and I want to sort by a specific key. What's the most efficient way to do this in Python?",

            # Long questions/context (150+ chars)
            "I'm working on a multithreaded application that uses a database connection pool. Sometimes I get an error saying 'connection already closed' even though I'm using a connection pool. Here's my code: [code snippet]. What am I doing wrong?",
            "Can you review this code for me? I'm concerned about performance and security. It's a REST API endpoint that processes user uploads, validates the data, and stores it in PostgreSQL. The code works but I want to make sure it's production-ready before deploying.",
        ]

    def generate_prompt(self) -> str:
        """Generate a human prompt with realistic variation"""
        prompt = random.choice(self.prompts)

        # Add some natural variation
        if random.random() > 0.8:
            prompt = "Hi! " + prompt

        if random.random() > 0.9:
            prompt += " Thanks!"

        return prompt


def run_simulation(duration_seconds: int = 60):
    """Run the client-server simulation"""

    print("=" * 80)
    print("REALISTIC CLIENT-SERVER NETWORK SIMULATION")
    print("=" * 80)
    print()
    print(f"Duration: {duration_seconds} seconds")
    print("Simulating: Human client ↔ AI server with real network conditions")
    print()

    # Initialize components
    compressor = ProductionHybridCompressor(
        binary_advantage_threshold=1.01,
        min_compression_size=10,
        enable_aura=False,
        enable_audit_logging=False,
        enable_scorer=False
    )

    network = SimulatedNetwork(base_latency_ms=50.0, jitter_ms=10.0)
    client = HumanClient()
    server = AIServer(compressor)

    # Metrics tracking
    client_to_server_metrics: List[NetworkMetrics] = []
    server_to_client_metrics: List[NetworkMetrics] = []

    start_time = time.time()
    message_count = 0

    print("Starting simulation...")
    print()

    while time.time() - start_time < duration_seconds:
        message_count += 1

        # 1. Client generates prompt
        prompt = client.generate_prompt()

        # 2. Client compresses prompt
        compress_start = time.time()
        compressed_prompt, method, metadata = compressor.compress(prompt)
        compress_time = (time.time() - compress_start) * 1000

        # 3. Client sends compressed prompt over network
        transmitted_prompt, network_latency = network.transmit(compressed_prompt)

        # 4. Server decompresses prompt
        decompress_start = time.time()
        decompressed_prompt = compressor.decompress(transmitted_prompt)
        decompress_time = (time.time() - decompress_start) * 1000

        # Track client->server metrics
        client_to_server_metrics.append(NetworkMetrics(
            direction="client->server",
            original_size=len(prompt),
            compressed_size=len(compressed_prompt),
            compression_ratio=metadata.get('ratio', 0.0),
            compression_time_ms=compress_time,
            decompression_time_ms=decompress_time,
            network_latency_ms=network_latency,
            method=method.name,
            partial_match=metadata.get('partial_match', False),
            match_coverage=metadata.get('match_coverage', 0.0)
        ))

        # 5. Server generates response (AI response - always larger)
        response = server.generate_response(decompressed_prompt)

        # 6. Server compresses response
        compress_start = time.time()
        compressed_response, response_method, response_metadata = compressor.compress(response)
        compress_time = (time.time() - compress_start) * 1000

        # 7. Server sends compressed response over network
        transmitted_response, response_latency = network.transmit(compressed_response)

        # 8. Client decompresses response
        decompress_start = time.time()
        decompressed_response = compressor.decompress(transmitted_response)
        decompress_time = (time.time() - decompress_start) * 1000

        # Track server->client metrics
        server_to_client_metrics.append(NetworkMetrics(
            direction="server->client",
            original_size=len(response),
            compressed_size=len(compressed_response),
            compression_ratio=response_metadata.get('ratio', 0.0),
            compression_time_ms=compress_time,
            decompression_time_ms=decompress_time,
            network_latency_ms=response_latency,
            method=response_method.name,
            partial_match=response_metadata.get('partial_match', False),
            match_coverage=response_metadata.get('match_coverage', 0.0)
        ))

        # Print progress every 10 messages
        if message_count % 10 == 0:
            elapsed = time.time() - start_time
            print(f"Progress: {message_count} messages, {elapsed:.1f}s elapsed")

        # Small delay between messages (realistic conversation pacing)
        time.sleep(random.uniform(0.5, 2.0))

    elapsed_time = time.time() - start_time

    # Print results
    print()
    print("=" * 80)
    print("SIMULATION RESULTS")
    print("=" * 80)
    print()
    print(f"Duration: {elapsed_time:.2f} seconds")
    print(f"Messages exchanged: {message_count} round-trips")
    print(f"Rate: {message_count / elapsed_time:.2f} messages/second")
    print()

    # Client -> Server (Human prompts)
    print("-" * 80)
    print("CLIENT → SERVER (Human Prompts)")
    print("-" * 80)

    c2s_original = sum(m.original_size for m in client_to_server_metrics)
    c2s_compressed = sum(m.compressed_size for m in client_to_server_metrics)
    c2s_ratios = [m.compression_ratio for m in client_to_server_metrics]
    c2s_latencies = [m.network_latency_ms for m in client_to_server_metrics]
    c2s_methods = {}
    for m in client_to_server_metrics:
        c2s_methods[m.method] = c2s_methods.get(m.method, 0) + 1

    print(f"Total data: {c2s_original:,} bytes → {c2s_compressed:,} bytes")
    print(f"Average compression ratio: {statistics.mean(c2s_ratios):.3f}x")
    print(f"Median compression ratio: {statistics.median(c2s_ratios):.3f}x")
    print(f"Average network latency: {statistics.mean(c2s_latencies):.2f}ms")
    print(f"Compression methods used:")
    for method, count in sorted(c2s_methods.items(), key=lambda x: x[1], reverse=True):
        pct = (count / len(client_to_server_metrics)) * 100
        print(f"  {method}: {count} ({pct:.1f}%)")

    if c2s_original < c2s_compressed:
        print(f"⚠ WARNING: Data expanded by {((c2s_compressed / c2s_original) - 1) * 100:.1f}%")
        print("  Human prompts are too small/diverse for effective compression")
    elif c2s_original > c2s_compressed:
        savings = c2s_original - c2s_compressed
        savings_pct = (savings / c2s_original) * 100
        print(f"✓ Bandwidth saved: {savings:,} bytes ({savings_pct:.1f}%)")

    print()

    # Server -> Client (AI responses)
    print("-" * 80)
    print("SERVER → CLIENT (AI Responses)")
    print("-" * 80)

    s2c_original = sum(m.original_size for m in server_to_client_metrics)
    s2c_compressed = sum(m.compressed_size for m in server_to_client_metrics)
    s2c_ratios = [m.compression_ratio for m in server_to_client_metrics]
    s2c_latencies = [m.network_latency_ms for m in server_to_client_metrics]
    s2c_methods = {}
    for m in server_to_client_metrics:
        s2c_methods[m.method] = s2c_methods.get(m.method, 0) + 1

    print(f"Total data: {s2c_original:,} bytes → {s2c_compressed:,} bytes")
    print(f"Average compression ratio: {statistics.mean(s2c_ratios):.3f}x")
    print(f"Median compression ratio: {statistics.median(s2c_ratios):.3f}x")
    print(f"Average network latency: {statistics.mean(s2c_latencies):.2f}ms")
    print(f"Compression methods used:")
    for method, count in sorted(s2c_methods.items(), key=lambda x: x[1], reverse=True):
        pct = (count / len(server_to_client_metrics)) * 100
        print(f"  {method}: {count} ({pct:.1f}%)")

    if s2c_original < s2c_compressed:
        print(f"⚠ WARNING: Data expanded by {((s2c_compressed / s2c_original) - 1) * 100:.1f}%")
    elif s2c_original > s2c_compressed:
        savings = s2c_original - s2c_compressed
        savings_pct = (savings / s2c_original) * 100
        print(f"✓ Bandwidth saved: {savings:,} bytes ({savings_pct:.1f}%)")

    print()

    # Overall statistics
    print("-" * 80)
    print("OVERALL STATISTICS")
    print("-" * 80)

    total_original = c2s_original + s2c_original
    total_compressed = c2s_compressed + s2c_compressed
    overall_ratio = total_original / total_compressed if total_compressed > 0 else 0.0

    print(f"Total data transmitted: {total_original:,} bytes → {total_compressed:,} bytes")
    print(f"Overall compression ratio: {overall_ratio:.3f}x")

    if total_original > total_compressed:
        total_savings = total_original - total_compressed
        total_savings_pct = (total_savings / total_original) * 100
        print(f"Total bandwidth saved: {total_savings:,} bytes ({total_savings_pct:.1f}%)")
    else:
        expansion = total_compressed - total_original
        expansion_pct = (expansion / total_original) * 100
        print(f"⚠ Net data expansion: {expansion:,} bytes ({expansion_pct:.1f}%)")

    print()
    print("=" * 80)
    print("HONEST ASSESSMENT")
    print("=" * 80)
    print()

    # Honest assessment based on actual results
    avg_compression = statistics.mean(c2s_ratios + s2c_ratios)

    if avg_compression > 1.5:
        print("✓ EXCELLENT: AURA is performing well for this use case")
        print(f"  Average {avg_compression:.2f}x compression is effective")
    elif avg_compression > 1.0:
        print("✓ GOOD: Compression is working (ratio > 1.0x)")
        print(f"  Average {avg_compression:.2f}x provides modest bandwidth savings")
    else:
        print("⚠ POOR: Compression is expanding data (ratio < 1.0x)")
        print(f"  Average {avg_compression:.2f}x means AURA is not effective here")
        print()
        print("Reasons:")
        print("  - Messages are too small (< 100 bytes average)")
        print("  - Content is too diverse (no repeated patterns)")
        print("  - Template library not optimized for this data type")
        print()
        print("AURA works best with:")
        print("  - AI-to-AI structured responses (JSON, API calls)")
        print("  - Larger messages (> 500 bytes)")
        print("  - Repeated patterns and templates")

    print()


if __name__ == "__main__":
    import sys

    # Allow duration to be passed as argument
    duration = 60
    if len(sys.argv) > 1:
        try:
            duration = int(sys.argv[1])
        except ValueError:
            print(f"Invalid duration: {sys.argv[1]}, using default 60 seconds")

    run_simulation(duration_seconds=duration)
