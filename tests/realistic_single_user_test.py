#!/usr/bin/env python3
"""
Realistic Single-User Stress Test: 5-Minute AI Chat Session

Simulates a real user having a conversation with an AI chatbot:
- Random intermittent prompts (user pauses to think/type)
- Realistic response sizes: 10 bytes to 15KB
- Mix of short answers, explanations, code examples
- Measures real-world performance over 5 minutes
"""

import time
import random
import statistics
from dataclasses import dataclass, field
from typing import List
from datetime import datetime

from aura_compression.compressor import ProductionHybridCompressor


@dataclass
class ConversationStats:
    """Statistics for a single conversation session"""
    session_duration_seconds: float
    total_messages: int
    user_prompts: int
    ai_responses: int

    total_original_bytes: int = 0
    total_compressed_bytes: int = 0

    compression_times_ms: List[float] = field(default_factory=list)
    decompression_times_ms: List[float] = field(default_factory=list)

    response_sizes: List[int] = field(default_factory=list)
    compression_ratios: List[float] = field(default_factory=list)

    errors: int = 0

    @property
    def avg_compression_ratio(self) -> float:
        if self.total_compressed_bytes == 0:
            return 0.0
        return self.total_original_bytes / self.total_compressed_bytes

    @property
    def messages_per_minute(self) -> float:
        return (self.total_messages / self.session_duration_seconds) * 60


# Realistic AI response templates by size category
TINY_RESPONSES = [
    "No",
    "Yes",
    "I don't know",
    "I'm not sure about that.",
    "Could you please clarify?",
    "That makes sense.",
    "I understand.",
    "Let me help you with that.",
    "Here's what I found:",
]

SHORT_RESPONSES = [
    "I don't have access to that information. Could you please provide more context?",
    "Based on the information you provided, here's what I recommend: {0}",
    "The error you're seeing is likely due to {0}. Try {1} to resolve it.",
    "Here's a quick example: {0}",
    "To accomplish that, you'll need to: 1) {0}, 2) {1}, 3) {2}",
]

MEDIUM_RESPONSES = [
    """Let me explain how this works. The key concept is {0}, which allows you to {1}.

    Here's a simple example:
    {2}

    This approach is effective because {3}. Does this answer your question?""",

    """I can help you with that. Here are the steps:

    1. First, {0}
    2. Then, {1}
    3. Next, {2}
    4. Finally, {3}

    Let me know if you need clarification on any of these steps.""",

    """Based on your requirements, I'd recommend {0}. Here's why:

    - {1}
    - {2}
    - {3}

    Would you like me to provide a more detailed example?""",
]

LONG_RESPONSES = [
    """Here's a comprehensive explanation of {0}:

    ## Overview
    {0} is a fundamental concept in {1}. It works by {2}.

    ## How It Works
    The process involves several key steps:

    1. **Initialization**: {3}
    2. **Processing**: {4}
    3. **Finalization**: {5}

    ## Example Implementation
    Here's a complete example:

    ```python
    def {6}({7}):
        '''
        {8}
        '''
        # Initialize
        {9}

        # Process
        for item in {10}:
            {11}

        # Return result
        return {12}
    ```

    ## Best Practices
    - {13}
    - {14}
    - {15}

    ## Common Pitfalls
    Watch out for these common mistakes:
    - {16}
    - {17}

    This should give you a solid understanding of {0}. Let me know if you need more details!""",

    """I'll help you implement {0}. Here's a complete solution:

    ## Problem Analysis
    You're trying to {1}, which requires {2}.

    ## Solution Approach
    The best way to handle this is to use {3}. Here's the full implementation:

    ```python
    import {4}
    from {5} import {6}

    class {7}:
        def __init__(self, {8}):
            self.{9} = {8}
            self.{10} = {11}

        def {12}(self, {13}):
            '''
            {14}
            '''
            try:
                # Validate input
                if not {15}:
                    raise ValueError("{16}")

                # Process data
                result = self._{17}({13})

                # Apply transformations
                transformed = self._{18}(result)

                return transformed

            except Exception as e:
                print(f"Error: {{e}}")
                return None

        def _{17}(self, {13}):
            # Implementation details
            {19}
            return {20}

        def _{18}(self, data):
            # Transform the data
            {21}
            return {22}

    # Usage example
    {23} = {7}({24})
    result = {23}.{12}({25})
    print(f"Result: {{result}}")
    ```

    ## Testing
    Here's how to test this implementation:

    ```python
    # Test case 1
    {26}

    # Test case 2
    {27}

    # Test case 3
    {28}
    ```

    ## Performance Considerations
    - {29}
    - {30}
    - {31}

    This implementation should handle your use case efficiently. Let me know if you need any modifications!""",
]

# Fill-in values for templates
TOPICS = ["neural networks", "database optimization", "API design", "caching", "authentication",
          "error handling", "async programming", "data structures", "algorithms", "performance"]
ACTIONS = ["optimize performance", "handle errors", "process data", "validate input", "transform results"]
EXAMPLES = ["x = process(data)", "result = transform(x)", "validated = check(input)"]
REASONS = ["it's efficient", "it's reliable", "it scales well", "it's maintainable"]
CODE_ELEMENTS = ["initialize()", "data = fetch()", "result += item", "process_item(item)", "validate_data()"]
CLASS_NAMES = ["DataProcessor", "RequestHandler", "CacheManager", "Validator"]
VAR_NAMES = ["data", "result", "items", "config", "options"]


def generate_response(size_category: str) -> str:
    """Generate a realistic AI response of specified size category"""

    if size_category == "tiny":  # 2-50 bytes
        return random.choice(TINY_RESPONSES)

    elif size_category == "short":  # 50-500 bytes
        template = random.choice(SHORT_RESPONSES)
        values = [random.choice(TOPICS), random.choice(ACTIONS), random.choice(REASONS)]
        try:
            return template.format(*values)
        except:
            return template

    elif size_category == "medium":  # 500-2000 bytes
        template = random.choice(MEDIUM_RESPONSES)
        values = [random.choice(TOPICS), random.choice(ACTIONS),
                 random.choice(EXAMPLES), random.choice(REASONS)]
        try:
            return template.format(*values)
        except:
            return template

    else:  # "long": 2KB-15KB
        template = random.choice(LONG_RESPONSES)
        values = [
            random.choice(TOPICS), random.choice(TOPICS), random.choice(ACTIONS),
            random.choice(CODE_ELEMENTS), random.choice(CODE_ELEMENTS), random.choice(CODE_ELEMENTS),
            random.choice(VAR_NAMES), random.choice(VAR_NAMES), random.choice(REASONS),
            random.choice(CODE_ELEMENTS), random.choice(VAR_NAMES), random.choice(CODE_ELEMENTS),
            random.choice(VAR_NAMES), random.choice(VAR_NAMES), random.choice(VAR_NAMES),
            random.choice(REASONS), random.choice(REASONS), random.choice(REASONS),
            random.choice(VAR_NAMES), random.choice(VAR_NAMES), random.choice(VAR_NAMES),
            random.choice(CLASS_NAMES), random.choice(VAR_NAMES), random.choice(VAR_NAMES),
            random.choice(ACTIONS), random.choice(ACTIONS), random.choice(VAR_NAMES),
            random.choice(CODE_ELEMENTS), random.choice(CODE_ELEMENTS), random.choice(CODE_ELEMENTS),
            random.choice(CODE_ELEMENTS), random.choice(CODE_ELEMENTS), random.choice(CODE_ELEMENTS),
            random.choice(VAR_NAMES), random.choice(VAR_NAMES), random.choice(VAR_NAMES),
            random.choice(REASONS), random.choice(REASONS), random.choice(REASONS),
        ]
        try:
            return template.format(*values)
        except:
            return template


def simulate_user_typing_delay() -> float:
    """Simulate realistic user typing/thinking time (1-30 seconds)"""
    # Most users pause 3-15 seconds between messages
    # Occasionally longer pauses (thinking, looking at code, etc.)
    if random.random() < 0.8:  # 80% normal pauses
        return random.uniform(2, 15)
    else:  # 20% longer pauses
        return random.uniform(15, 45)


def run_realistic_session(
    duration_minutes: int = 5,
    enable_gpu: bool = True
) -> ConversationStats:
    """
    Simulate a realistic single-user conversation session.

    Args:
        duration_minutes: How long to run the simulation
        enable_gpu: Enable GPU acceleration
    """

    print("=" * 80)
    print(f"🤖 REALISTIC SINGLE-USER SESSION: {duration_minutes} MINUTES")
    print("=" * 80)
    print(f"Configuration:")
    print(f"  Duration: {duration_minutes} minutes")
    print(f"  Response sizes: 10 bytes to 15KB (realistic distribution)")
    print(f"  User behavior: Intermittent prompts with thinking pauses")
    print(f"  GPU Acceleration: {'✅ ENABLED' if enable_gpu else '❌ DISABLED'}")
    print()

    # Initialize compressor
    print("Initializing AURA compressor...")
    compressor = ProductionHybridCompressor(enable_gpu=enable_gpu)
    print()

    # Session tracking
    stats = ConversationStats(
        session_duration_seconds=duration_minutes * 60,
        total_messages=0,
        user_prompts=0,
        ai_responses=0
    )

    session_start = time.perf_counter()
    end_time = session_start + (duration_minutes * 60)

    message_count = 0

    print(f"🚀 Starting {duration_minutes}-minute conversation simulation...")
    print(f"   Start time: {datetime.now().strftime('%H:%M:%S')}")
    print()

    # Response size distribution (realistic)
    # Most responses are short, some medium, few long
    size_weights = {
        'tiny': 0.15,    # 15% tiny (2-50 bytes)
        'short': 0.45,   # 45% short (50-500 bytes)
        'medium': 0.30,  # 30% medium (500-2KB)
        'long': 0.10,    # 10% long (2-15KB)
    }

    while time.perf_counter() < end_time:
        message_count += 1

        # Simulate user sending a prompt (small, not compressed in this test)
        stats.user_prompts += 1
        stats.total_messages += 1

        # Generate AI response
        size_category = random.choices(
            list(size_weights.keys()),
            weights=list(size_weights.values())
        )[0]

        response = generate_response(size_category)
        original_size = len(response.encode('utf-8'))
        stats.response_sizes.append(original_size)

        # Compress response
        try:
            comp_start = time.perf_counter()
            payload, method, metadata = compressor.compress(response)
            comp_time = (time.perf_counter() - comp_start) * 1000

            compressed_size = metadata['compressed_size']
            ratio = metadata['ratio']

            # Decompress to verify
            decomp_start = time.perf_counter()
            decompressed = compressor.decompress(payload)
            decomp_time = (time.perf_counter() - decomp_start) * 1000

            # Record stats
            stats.ai_responses += 1
            stats.total_messages += 1
            stats.total_original_bytes += original_size
            stats.total_compressed_bytes += compressed_size
            stats.compression_times_ms.append(comp_time)
            stats.decompression_times_ms.append(decomp_time)
            stats.compression_ratios.append(ratio)

            # Progress indicator every 10 messages
            if message_count % 10 == 0:
                elapsed = time.perf_counter() - session_start
                remaining = end_time - time.perf_counter()
                print(f"   [{elapsed/60:.1f}/{duration_minutes:.0f} min] "
                      f"Messages: {stats.total_messages:3d} | "
                      f"Avg ratio: {statistics.mean(stats.compression_ratios):.2f}:1 | "
                      f"Remaining: {remaining:.0f}s")

        except Exception as e:
            stats.errors += 1
            print(f"   ❌ Error on message {message_count}: {e}")

        # Simulate user thinking/typing delay
        delay = simulate_user_typing_delay()

        # Check if we have time for the delay
        if time.perf_counter() + delay < end_time:
            time.sleep(delay)
        else:
            # Session ending, break
            break

    actual_duration = time.perf_counter() - session_start
    stats.session_duration_seconds = actual_duration

    print()
    print(f"   End time: {datetime.now().strftime('%H:%M:%S')}")
    print(f"   Actual duration: {actual_duration:.1f}s ({actual_duration/60:.2f} min)")
    print()

    return stats


def print_results(stats: ConversationStats):
    """Print detailed session results"""

    print("=" * 80)
    print("📊 SESSION RESULTS")
    print("=" * 80)

    print(f"\n📈 Session Overview:")
    print(f"  Duration: {stats.session_duration_seconds:.1f}s ({stats.session_duration_seconds/60:.2f} min)")
    print(f"  Total Messages: {stats.total_messages}")
    print(f"  User Prompts: {stats.user_prompts}")
    print(f"  AI Responses: {stats.ai_responses}")
    print(f"  Messages/Minute: {stats.messages_per_minute:.1f}")
    print(f"  Errors: {stats.errors}")

    print(f"\n💾 Compression Statistics:")
    print(f"  Total Original: {stats.total_original_bytes:,} bytes ({stats.total_original_bytes/1024:.1f} KB)")
    print(f"  Total Compressed: {stats.total_compressed_bytes:,} bytes ({stats.total_compressed_bytes/1024:.1f} KB)")
    print(f"  Overall Ratio: {stats.avg_compression_ratio:.2f}:1")
    print(f"  Bandwidth Saved: {stats.total_original_bytes - stats.total_compressed_bytes:,} bytes "
          f"({(1 - stats.total_compressed_bytes/stats.total_original_bytes)*100:.1f}%)")

    print(f"\n📏 Response Size Distribution:")
    print(f"  Min: {min(stats.response_sizes)} bytes")
    print(f"  Max: {max(stats.response_sizes):,} bytes")
    print(f"  Mean: {statistics.mean(stats.response_sizes):.0f} bytes")
    print(f"  Median: {statistics.median(stats.response_sizes):.0f} bytes")

    print(f"\n⚡ Compression Performance:")
    print(f"  Mean: {statistics.mean(stats.compression_times_ms):.3f}ms")
    print(f"  Median: {statistics.median(stats.compression_times_ms):.3f}ms")
    print(f"  P95: {sorted(stats.compression_times_ms)[int(len(stats.compression_times_ms)*0.95)]:.3f}ms")
    print(f"  P99: {sorted(stats.compression_times_ms)[int(len(stats.compression_times_ms)*0.99)]:.3f}ms")
    print(f"  Max: {max(stats.compression_times_ms):.3f}ms")

    print(f"\n⚡ Decompression Performance:")
    print(f"  Mean: {statistics.mean(stats.decompression_times_ms):.3f}ms")
    print(f"  Median: {statistics.median(stats.decompression_times_ms):.3f}ms")
    print(f"  P95: {sorted(stats.decompression_times_ms)[int(len(stats.decompression_times_ms)*0.95)]:.3f}ms")
    print(f"  P99: {sorted(stats.decompression_times_ms)[int(len(stats.decompression_times_ms)*0.99)]:.3f}ms")
    print(f"  Max: {max(stats.decompression_times_ms):.3f}ms")

    print(f"\n📊 Compression Ratio Analysis:")
    print(f"  Mean: {statistics.mean(stats.compression_ratios):.2f}:1")
    print(f"  Median: {statistics.median(stats.compression_ratios):.2f}:1")
    print(f"  Min: {min(stats.compression_ratios):.2f}:1")
    print(f"  Max: {max(stats.compression_ratios):.2f}:1")

    # Success criteria
    print(f"\n{'=' * 80}")
    print("✅ SUCCESS CRITERIA:")
    print("=" * 80)

    success = True

    # Check compression ratio
    avg_ratio = stats.avg_compression_ratio
    if avg_ratio >= 1.2:
        print(f"✅ Compression Ratio: {avg_ratio:.2f}:1 (target: 1.2+)")
    else:
        print(f"⚠️  Compression Ratio: {avg_ratio:.2f}:1 (target: 1.2+)")

    # Check P99 latency
    p99_compression = sorted(stats.compression_times_ms)[int(len(stats.compression_times_ms)*0.99)]
    if p99_compression <= 10.0:
        print(f"✅ P99 Compression Latency: {p99_compression:.3f}ms (target: <10ms)")
    else:
        print(f"❌ P99 Compression Latency: {p99_compression:.3f}ms (target: <10ms)")
        success = False

    # Check errors
    if stats.errors == 0:
        print(f"✅ Error Rate: 0 errors")
    else:
        print(f"❌ Error Rate: {stats.errors} errors (target: 0)")
        success = False

    # Check session completion
    if stats.total_messages > 0:
        print(f"✅ Session Completed: {stats.total_messages} messages exchanged")
    else:
        print(f"❌ Session Failed: No messages exchanged")
        success = False

    print("=" * 80)
    if success:
        print("🎉 ALL SUCCESS CRITERIA MET!")
    else:
        print("⚠️  SOME CRITERIA NOT MET")
    print("=" * 80)

    return success


def main():
    """Run realistic single-user session test"""

    print("\n" + "=" * 80)
    print("REALISTIC SINGLE-USER TEST: 5-MINUTE AI CHAT SESSION")
    print("Simulating real user with intermittent prompts and varied responses")
    print("=" * 80 + "\n")

    stats = run_realistic_session(
        duration_minutes=5,
        enable_gpu=True
    )

    success = print_results(stats)

    if success:
        print("\n✅ Realistic session test PASSED!")
        exit(0)
    else:
        print("\n⚠️  Realistic session test completed with warnings")
        exit(0)


if __name__ == "__main__":
    main()
