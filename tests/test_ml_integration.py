#!/usr/bin/env python3
"""
Integration test demonstrating ML algorithm selection in action.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from aura_compression.ml_algorithm_selector import MLAlgorithmSelector, CompressionMethod, CompressionResult


def test_ml_integration():
    """Test ML algorithm selector integration."""
    print("🧠 Testing ML Algorithm Selector Integration")
    print("=" * 50)

    # Create ML selector
    selector = MLAlgorithmSelector(enable_learning=True)
    print("✓ ML Algorithm Selector initialized")

    # Test different message types
    test_messages = [
        "Hello world",  # Simple text
        "User authentication failed: invalid credentials",  # Structured message
        "Error 404: Page not found at /api/users/123",  # Error message with numbers
        "The quick brown fox jumps over the lazy dog. " * 5,  # Repetitive text (good for BRIO)
        '{"user_id": 123, "action": "login", "timestamp": 1234567890}',  # JSON data
    ]

    available_methods = [
        CompressionMethod.BRIO,
        CompressionMethod.AURALITE,
        CompressionMethod.UNCOMPRESSED
    ]

    print(f"\n📊 Testing algorithm selection for {len(test_messages)} message types:")
    print("-" * 50)

    for i, message in enumerate(test_messages, 1):
        print(f"\nMessage {i}: {message[:50]}{'...' if len(message) > 50 else ''}")

        # Get ML prediction
        prediction = selector.predict_routing_decision(message, available_methods)

        print(f"  📈 Selected: {prediction.method}")
        print(".2f")
        print(f"  🎯 Expected ratio: {prediction.expected_ratio:.2f}")
        print(f"  💭 Reasoning: {prediction.reasoning}")

        # Simulate compression performance recording
        # (In real usage, this would come from actual compression)
        mock_result = CompressionResult(
            method=prediction.method,
            original_size=len(message),
            compressed_size=int(len(message) * (1.0 / prediction.expected_ratio)),
            compression_time=0.01,
            ratio=prediction.expected_ratio
        )

        selector.record_performance(message, prediction.method, mock_result)
        print("  ✅ Performance recorded for learning")

    print(f"\n📈 ML Model Statistics:")
    stats = selector.get_method_stats()
    print(f"  • Training samples: {stats['total_samples']}")
    print(f"  • Methods tracked: {len(stats['methods'])}")
    print(f"  • Learning enabled: {stats['learning_enabled']}")

    print(f"\n🎉 ML Algorithm Selector integration test completed successfully!")
    return True


if __name__ == "__main__":
    test_ml_integration()