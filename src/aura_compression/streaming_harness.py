#!/usr/bin/env python3
"""
Streaming Test Harness - Patent Claim 20
Demonstrates metadata-only fast paths achieve 60% usage in multi-agent scenarios
"""
import time
import threading
from dataclasses import dataclass
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

from aura_compression.compressor import ProductionHybridCompressor
from aura_compression.metadata import MetadataExtractor
from aura_compression.router import ProductionRouter, RoutingMetrics


@dataclass
class ConversationMessage:
    """Single message in a conversation"""
    session_id: str
    message_id: int
    text: str
    is_ai_to_ai: bool = False  # AI-to-AI messages compress better


class StreamingHarness:
    """
    Streaming test harness for measuring fast-path performance (Claim 20)

    Simulates concurrent human-AI and AI-to-AI conversations
    Measures latency improvements when metadata-only fast paths are used
    Target: >= 60% of messages in multi-agent scenarios use fast path
    """

    def __init__(
        self,
        concurrent_sessions: int = 10,
        messages_per_session: int = 50,
    ):
        """
        Args:
            concurrent_sessions: Number of simultaneous conversations
            messages_per_session: Messages per conversation
        """
        self.concurrent_sessions = concurrent_sessions
        self.messages_per_session = messages_per_session

        self.compressor = ProductionHybridCompressor(enable_aura=True)
        self.extractor = MetadataExtractor()
        self.router = ProductionRouter()

        # Register handlers
        self._setup_routes()

        # Metrics
        self.total_latency_ms = 0.0
        self.message_count = 0

    def _setup_routes(self):
        """Setup routes for different message types"""
        # Fast-path handler for template-based messages
        def fast_path_handler(metadata: Dict[str, Any]) -> str:
            """Handler that works with metadata only"""
            return f"Fast path: template {metadata.get('template_ids', [])}"

        # Slow-path handler for unstructured messages
        def slow_path_handler(plaintext: str, metadata: Dict[str, Any]) -> str:
            """Handler that needs full decompression"""
            return f"Slow path: {len(plaintext)} bytes"

        # Register routes
        self.router.register_route(
            handler_name="template_handler",
            handler_function=fast_path_handler,
            template_ids=[0, 1, 2, 10, 11, 12, 20, 30, 40],  # Common templates
            requires_decompression=False,  # Fast path
        )

        self.router.set_default_handler(slow_path_handler)

    def generate_conversation_messages(self, session_id: str) -> List[ConversationMessage]:
        """
        Generate realistic conversation messages (Claim 20)

        Mix of:
        - Human-to-AI: Questions, requests
        - AI-to-Human: Template-based responses (fast-path candidates)
        - AI-to-AI: Function calls, status updates (high fast-path usage)
        """
        messages = []

        # Human-to-AI messages (varied, less compressible)
        human_messages = [
            "What's the weather like today?",
            "Can you help me with this problem?",
            "How do I install the software?",
            "What are the system requirements?",
            "Tell me about the features.",
        ]

        # AI-to-Human responses (template-based, fast-path candidates)
        ai_responses = [
            "I don't have access to real-time weather data. Please check a weather service.",
            "I don't have access to your specific problem details. Could you provide more information?",
            "To install the software, use pip: `pip install package-name`",
            "The main requirements are: Python 3.8+, 4GB RAM, and 1GB disk space.",
            "Common features include: compression, encryption, and audit logging.",
        ]

        # AI-to-AI messages (structured, high fast-path usage)
        ai_to_ai_messages = [
            '{"function": "execute_task", "args": {"task_id": "abc123"}}',
            '{"function": "query_database", "args": {"query": "SELECT * FROM users"}}',
            '{"function": "call_api", "args": {"endpoint": "/api/v1/data"}}',
            '{"function": "get_status", "args": {"service": "database"}}',
        ]

        for i in range(self.messages_per_session):
            # Alternate between human, AI, and AI-to-AI messages
            if i % 4 == 0:
                # Human question
                text = human_messages[i % len(human_messages)]
                is_ai_to_ai = False
            elif i % 4 == 1:
                # AI response (template-based)
                text = ai_responses[i % len(ai_responses)]
                is_ai_to_ai = False
            else:
                # AI-to-AI (structured, fast-path)
                text = ai_to_ai_messages[i % len(ai_to_ai_messages)]
                is_ai_to_ai = True

            messages.append(ConversationMessage(
                session_id=session_id,
                message_id=i,
                text=text,
                is_ai_to_ai=is_ai_to_ai,
            ))

        return messages

    def process_message(self, message: ConversationMessage) -> Dict[str, Any]:
        """
        Process single message through compression -> metadata extraction -> routing (Claim 20)

        Returns:
            Dictionary with timing and routing information
        """
        start_time = time.time()

        # Compress message
        compressed, method, metadata = self.compressor.compress(message.text)
        compress_time = (time.time() - start_time) * 1000

        # Extract metadata (fast)
        extract_start = time.time()
        extracted = self.extractor.extract(compressed)
        metadata_dict = extracted.to_dict()
        extract_time = (time.time() - extract_start) * 1000

        # Route message (may use fast path)
        route_start = time.time()
        result = self.router.route(
            metadata=metadata_dict,
            compressed_data=compressed,
            decompressor=lambda data: self.compressor.decompress(data),
        )
        route_time = (time.time() - route_start) * 1000

        total_time = (time.time() - start_time) * 1000

        return {
            'session_id': message.session_id,
            'message_id': message.message_id,
            'is_ai_to_ai': message.is_ai_to_ai,
            'compress_time_ms': compress_time,
            'extract_time_ms': extract_time,
            'route_time_ms': route_time,
            'total_time_ms': total_time,
            'used_fast_path': extracted.fast_path_candidate,
        }

    def run_session(self, session_id: str) -> List[Dict[str, Any]]:
        """Run single conversation session"""
        messages = self.generate_conversation_messages(session_id)
        results = []

        for message in messages:
            result = self.process_message(message)
            results.append(result)

        return results

    def run(self) -> Dict[str, Any]:
        """
        Run full streaming harness (Claim 20)

        Simulates multiple concurrent conversations
        Measures fast-path usage percentage
        Target: >= 60% for multi-agent scenarios

        Returns:
            Comprehensive metrics dictionary
        """
        print(f"\n{'='*80}")
        print(f"STREAMING HARNESS - Patent Claim 20")
        print(f"{'='*80}")
        print(f"Concurrent sessions: {self.concurrent_sessions}")
        print(f"Messages per session: {self.messages_per_session}")
        print(f"Total messages: {self.concurrent_sessions * self.messages_per_session}")
        print(f"{'='*80}\n")

        start_time = time.time()

        # Run sessions concurrently
        all_results = []
        with ThreadPoolExecutor(max_workers=self.concurrent_sessions) as executor:
            futures = []
            for i in range(self.concurrent_sessions):
                session_id = f"session_{i:03d}"
                future = executor.submit(self.run_session, session_id)
                futures.append(future)

            for future in as_completed(futures):
                results = future.result()
                all_results.extend(results)

        total_time = time.time() - start_time

        # Analyze results
        fast_path_count = sum(1 for r in all_results if r['used_fast_path'])
        slow_path_count = len(all_results) - fast_path_count
        fast_path_percentage = (fast_path_count / len(all_results)) * 100

        ai_to_ai_messages = [r for r in all_results if r['is_ai_to_ai']]
        ai_to_ai_fast_path = sum(1 for r in ai_to_ai_messages if r['used_fast_path'])
        ai_to_ai_percentage = (ai_to_ai_fast_path / len(ai_to_ai_messages)) * 100 if ai_to_ai_messages else 0

        avg_total_latency = sum(r['total_time_ms'] for r in all_results) / len(all_results)
        avg_fast_path_latency = sum(r['total_time_ms'] for r in all_results if r['used_fast_path']) / fast_path_count if fast_path_count > 0 else 0
        avg_slow_path_latency = sum(r['total_time_ms'] for r in all_results if not r['used_fast_path']) / slow_path_count if slow_path_count > 0 else 0

        speedup = avg_slow_path_latency / avg_fast_path_latency if avg_fast_path_latency > 0 else 1.0

        # Get router metrics
        router_metrics = self.router.get_metrics()

        metrics = {
            'total_messages': len(all_results),
            'fast_path_count': fast_path_count,
            'slow_path_count': slow_path_count,
            'fast_path_percentage': fast_path_percentage,
            'target_percentage': 60.0,
            'meets_target': fast_path_percentage >= 60.0,

            'ai_to_ai_messages': len(ai_to_ai_messages),
            'ai_to_ai_fast_path_percentage': ai_to_ai_percentage,

            'average_total_latency_ms': avg_total_latency,
            'average_fast_path_latency_ms': avg_fast_path_latency,
            'average_slow_path_latency_ms': avg_slow_path_latency,
            'speedup_factor': speedup,

            'total_execution_time_seconds': total_time,
            'messages_per_second': len(all_results) / total_time,

            'router_metrics': router_metrics,
        }

        # Print results
        self._print_results(metrics)

        return metrics

    def _print_results(self, metrics: Dict[str, Any]):
        """Print streaming harness results"""
        print(f"\n{'='*80}")
        print(f"STREAMING HARNESS RESULTS")
        print(f"{'='*80}")
        print(f"Total messages:           {metrics['total_messages']}")
        print(f"Fast-path messages:       {metrics['fast_path_count']}")
        print(f"Slow-path messages:       {metrics['slow_path_count']}")
        print(f"Fast-path percentage:     {metrics['fast_path_percentage']:.1f}%")
        print(f"Target (Claim 20):        {metrics['target_percentage']:.1f}%")
        print(f"Meets target:             {'✅ YES' if metrics['meets_target'] else '❌ NO'}")
        print()
        print(f"AI-to-AI messages:        {metrics['ai_to_ai_messages']}")
        print(f"AI-to-AI fast-path:       {metrics['ai_to_ai_fast_path_percentage']:.1f}%")
        print()
        print(f"Average total latency:    {metrics['average_total_latency_ms']:.3f}ms")
        print(f"Fast-path latency:        {metrics['average_fast_path_latency_ms']:.3f}ms")
        print(f"Slow-path latency:        {metrics['average_slow_path_latency_ms']:.3f}ms")
        print(f"Speedup factor:           {metrics['speedup_factor']:.1f}x")
        print()
        print(f"Execution time:           {metrics['total_execution_time_seconds']:.2f}s")
        print(f"Messages per second:      {metrics['messages_per_second']:.1f}")
        print(f"{'='*80}\n")


def run_streaming_harness_demo():
    """Run streaming harness demonstration"""
    harness = StreamingHarness(
        concurrent_sessions=10,
        messages_per_session=50,
    )

    metrics = harness.run()

    return metrics


if __name__ == "__main__":
    run_streaming_harness_demo()
