#!/usr/bin/env python3
"""
AURA WebSocket Client

Demonstrates:
1. Client compresses message with AURA (metadata embedded automatically)
2. Client sends ONLY compressed bytes (metadata is inside the payload)
3. Server extracts metadata server-side (client doesn't send it separately)
4. Server routes using metadata without decompressing
5. Response comes back compressed, client decompresses
"""
import asyncio
import websockets
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from aura_compression import ProductionHybridCompressor


async def send_message(uri: str, message: str):
    """Send a message through AURA WebSocket"""
    compressor = ProductionHybridCompressor(enable_aura=True)

    async with websockets.connect(uri) as websocket:
        # Step 1: Compress message (metadata embedded automatically)
        compressed, method, metadata = compressor.compress(message)

        print(f"\nSending: {message[:60]}...")
        print(f"  Original size: {len(message)} bytes")
        print(f"  Compressed size: {len(compressed)} bytes")
        print(f"  Method: {method}")
        print(f"  Metadata embedded: {metadata}")

        # Step 2: Send ONLY compressed bytes
        # (Metadata is already inside the compressed payload)
        await websocket.send(compressed)

        # Step 3: Receive compressed response
        response_compressed = await websocket.recv()

        # Step 4: Decompress response
        response_text = compressor.decompress(response_compressed)
        response = json.loads(response_text)

        print(f"  Response: {response}")
        print(f"  Fast-path used: {response.get('fast_path', False)}")


async def demo():
    """Demonstrate AURA WebSocket communication"""
    uri = "ws://localhost:8765"

    print("="*80)
    print("AURA WebSocket Client Demo")
    print("="*80)
    print("\nKey Points:")
    print("  • Metadata is EMBEDDED in compressed payload")
    print("  • Client sends ONLY compressed bytes")
    print("  • Server extracts metadata server-side")
    print("  • No separate metadata transmission")
    print("="*80)

    # Example messages
    messages = [
        "I need to reset my password. My email is user@example.com",
        "What's the status of my order #12345?",
        "I have a question about my last invoice for $99.99",
        "Can you help me understand how your product works?",
    ]

    for msg in messages:
        try:
            await send_message(uri, msg)
            await asyncio.sleep(0.1)  # Small delay between messages
        except Exception as e:
            print(f"Error: {e}")
            print("Make sure the server is running: python src/python/examples/websocket_server.py")
            break


if __name__ == "__main__":
    asyncio.run(demo())
