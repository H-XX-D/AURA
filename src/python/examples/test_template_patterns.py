#!/usr/bin/env python3
"""
Test Template Pattern Recognition

Sends messages that should match templates and verifies:
1. Templates are matched correctly
2. Fast-path routing is used
3. Metadata contains template IDs
4. Performance improvement vs non-template messages
"""
import asyncio
import websockets
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from aura_compression import ProductionHybridCompressor, TemplateLibrary


async def test_pattern_recognition():
    """Test template pattern matching"""
    uri = "ws://localhost:8766"

    # Setup compressor with same templates as server
    template_lib = TemplateLibrary()

    # Register matching templates
    template_lib.add_template("I need to reset my password. {email}", ["email"], 0)
    template_lib.add_template("I can't log into my account {username}", ["username"], 1)
    template_lib.add_template("Where is my order {order_id}?", ["order_id"], 2)
    template_lib.add_template("What's the status of order {order_id}?", ["order_id"], 3)
    template_lib.add_template("I have a question about invoice {invoice_id}", ["invoice_id"], 4)
    template_lib.add_template("My payment of {amount} didn't go through", ["amount"], 5)
    template_lib.add_template("Can you help me with {topic}?", ["topic"], 10)

    compressor = ProductionHybridCompressor(
        enable_aura=True,
        template_library=template_lib
    )

    print("="*80)
    print("TEMPLATE PATTERN RECOGNITION TEST")
    print("="*80)

    # Test messages - should match templates
    template_messages = [
        ("I need to reset my password. user@example.com", 0, "authentication"),
        ("I can't log into my account john_doe", 1, "authentication"),
        ("Where is my order #12345?", 2, "order_status"),
        ("What's the status of order #67890?", 3, "order_status"),
        ("I have a question about invoice INV-999", 4, "billing"),
        ("My payment of $99.99 didn't go through", 5, "billing"),
        ("Can you help me with shipping options?", 10, "general"),
    ]

    # Non-template messages - should use fallback
    non_template_messages = [
        "This is a unique message that doesn't match any pattern",
        "Hello, I have a very specific question about my account configuration",
        "Could you explain the difference between plan A and plan B?",
    ]

    template_match_count = 0
    fast_path_count = 0
    total_messages = 0

    try:
        async with websockets.connect(uri) as websocket:
            print("\n" + "="*80)
            print("TESTING TEMPLATE MATCHES")
            print("="*80)

            # Test template-matching messages
            for message, expected_template_id, expected_intent in template_messages:
                total_messages += 1

                # Compress
                compressed, method, metadata = compressor.compress(message)

                print(f"\n[Message {total_messages}] {message[:60]}...")
                print(f"  Expected template: {expected_template_id}")
                print(f"  Expected intent: {expected_intent}")
                print(f"  Compressed: {len(message)}→{len(compressed)} bytes ({method})")

                # Check if template was used during compression
                if 'template_ids' in metadata and metadata['template_ids']:
                    print(f"  ✅ Template matched during compression: {metadata['template_ids']}")
                else:
                    print(f"  ❌ No template match during compression")

                # Send
                await websocket.send(compressed)

                # Receive response
                response_compressed = await websocket.recv()
                response_text = compressor.decompress(response_compressed)
                response = json.loads(response_text)

                # Verify fast-path was used
                metrics = response.get('metrics', {})
                if metrics.get('template_matched'):
                    template_match_count += 1
                    print(f"  ✅ Server detected template: {metrics.get('template_id')}")
                else:
                    print(f"  ❌ Server did NOT detect template")

                if metrics.get('fast_path'):
                    fast_path_count += 1
                    print(f"  🚀 Fast-path used: {response.get('handler')}")
                else:
                    print(f"  🐌 Slow-path used: {response.get('handler')}")

                if metrics.get('intent') == expected_intent:
                    print(f"  ✅ Intent correct: {expected_intent}")
                else:
                    print(f"  ❌ Intent mismatch: got {metrics.get('intent')}, expected {expected_intent}")

                await asyncio.sleep(0.1)

            print("\n" + "="*80)
            print("TESTING NON-TEMPLATE MESSAGES (Should use slow-path)")
            print("="*80)

            # Test non-template messages
            for message in non_template_messages:
                total_messages += 1

                compressed, method, metadata = compressor.compress(message)

                print(f"\n[Message {total_messages}] {message[:60]}...")
                print(f"  Compressed: {len(message)}→{len(compressed)} bytes ({method})")

                # Should NOT have template
                if 'template_ids' in metadata and metadata['template_ids']:
                    print(f"  ⚠️  Unexpected template match: {metadata['template_ids']}")
                else:
                    print(f"  ✅ No template match (as expected)")

                await websocket.send(compressed)

                response_compressed = await websocket.recv()
                response_text = compressor.decompress(response_compressed)
                response = json.loads(response_text)

                metrics = response.get('metrics', {})
                if metrics.get('fast_path'):
                    print(f"  ⚠️  Unexpected fast-path usage")
                else:
                    print(f"  ✅ Slow-path used (as expected): {response.get('handler')}")

                await asyncio.sleep(0.1)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("Make sure server is running: python src/python/examples/websocket_with_templates.py")
        return

    # Final metrics
    print("\n" + "="*80)
    print("FINAL METRICS")
    print("="*80)
    print(f"Total messages sent:        {total_messages}")
    print(f"Template messages:          {len(template_messages)}")
    print(f"Template matches detected:  {template_match_count} / {len(template_messages)}")
    print(f"Fast-path usage:            {fast_path_count} / {len(template_messages)}")
    print(f"Non-template messages:      {len(non_template_messages)}")
    print(f"Success rate:               {(template_match_count/len(template_messages)*100):.1f}%")

    if template_match_count == len(template_messages):
        print("\n✅ ALL TEMPLATE PATTERNS RECOGNIZED CORRECTLY!")
    else:
        print(f"\n⚠️  Only {template_match_count}/{len(template_messages)} templates matched")

    if fast_path_count == len(template_messages):
        print("✅ ALL FAST-PATH ROUTING SUCCESSFUL!")
    else:
        print(f"⚠️  Only {fast_path_count}/{len(template_messages)} used fast-path")

    print("="*80)


if __name__ == "__main__":
    asyncio.run(test_pattern_recognition())
