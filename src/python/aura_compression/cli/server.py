#!/usr/bin/env python3
"""
AURA Compression CLI - Server Command

Usage:
    aura-server [options]

Options:
    -h, --host HOST      Host to bind server (default: 0.0.0.0)
    -p, --port PORT      Port to bind server (default: 8765)
    --demo               Run demo instead of server
    --help               Show this help message
"""

import argparse
import asyncio
import sys
import os
from http import HTTPStatus
from typing import List, Optional

# Add the parent directory to the path so we can import aura_compression
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from aura_compression import ProductionHybridCompressor


class SimpleWebSocketServer:
    """Simple WebSocket server for AURA compression demonstration."""

    def __init__(self):
        self.compressor = ProductionHybridCompressor(enable_aura=True)

    def generate_response(self, user_message: str) -> str:
        """Generate a simple AI-like response."""
        user_lower = user_message.lower()

        if "hello" in user_lower or "hi" in user_lower:
            return "Hello! How can I help you today?"
        elif "weather" in user_lower:
            return "I don't have access to real-time weather information. Please check a weather service."
        elif "help" in user_lower:
            return "I can help with various topics. What would you like to know about?"
        elif "python" in user_lower:
            return "Python is a great programming language! It's known for its simplicity and readability."
        else:
            return f"That's an interesting question about '{user_message[:50]}'. I'd be happy to help!"

    async def handle_connection(self, websocket, path):
        """Handle a WebSocket connection."""
        client = websocket.remote_address
        print(f"🔌 Client connected: {client}")

        try:
            async for message in websocket:
                if isinstance(message, str):
                    # Expect binary compressed data
                    error_msg = "Error: Expected binary compressed data"
                    compressed_error, _, _ = self.compressor.compress(error_msg)
                    await websocket.send(compressed_error)
                    continue

                try:
                    # Decompress the message
                    decompressed = self.compressor.decompress(message)
                    print(f"📥 Received: {decompressed}")

                    # Generate response
                    response = self.generate_response(decompressed)
                    print(f"📤 Sending: {response}")

                    # Compress and send response
                    compressed_response, method, metadata = self.compressor.compress(response)
                    print(f"   Compressed {len(response)} -> {len(compressed_response)} bytes (method: {method})")

                    await websocket.send(compressed_response)

                except Exception as e:
                    error_msg = f"Error processing message: {e}"
                    print(f"❌ {error_msg}")
                    compressed_error, _, _ = self.compressor.compress(error_msg)
                    await websocket.send(compressed_error)

        except Exception as e:
            print(f"❌ Connection error for {client}: {e}")

    async def process_request(self, path, request_headers):
        """Handle HTTP health check requests."""
        if path == "/health":
            return HTTPStatus.OK, [("Content-Type", "text/plain")], b"ok\n"
        return None

    async def serve(self, host: str = "0.0.0.0", port: int = 8765):
        """Run the WebSocket server."""
        try:
            import websockets
        except ImportError:
            print("❌ Error: websockets package not installed. Install with: pip install websockets")
            sys.exit(1)

        print("=" * 80)
        print("AURA WEBSOCKET SERVER")
        print("AI-Optimized Hybrid Compression")
        print("=" * 80)
        print(f"Listening on ws://{host}:{port}")
        print(f"Health check: http://{host}:{port}/health")
        print("Press Ctrl+C to stop")
        print()

        try:
            async with websockets.serve(
                self.handle_connection,
                host,
                port,
                process_request=self.process_request,
                max_size=None,
            ):
                await asyncio.Future()  # Run forever
        except KeyboardInterrupt:
            print("\n🛑 Shutting down AURA WebSocket server")


def run_demo():
    """Run a simple demonstration of the compression."""
    print("=" * 80)
    print("AURA COMPRESSION DEMO")
    print("=" * 80)
    print()

    compressor = ProductionHybridCompressor(enable_aura=True)

    test_messages = [
        "Hello, how are you today?",
        "Can you help me with Python programming?",
        "What's the weather like today?",
        "I need help with data compression algorithms.",
        "This is a longer message to test compression efficiency with more content and repeated patterns that should compress well with the AURA algorithm.",
    ]

    total_original = 0
    total_compressed = 0

    for i, message in enumerate(test_messages, 1):
        compressed, method, metadata = compressor.compress(message)
        decompressed = compressor.decompress(compressed)

        original_size = len(message.encode('utf-8'))
        compressed_size = len(compressed)
        ratio = original_size / compressed_size if compressed_size > 0 else 1.0

        total_original += original_size
        total_compressed += compressed_size

        print(f"Message {i}:")
        print(f"  Original: {original_size} bytes")
        print(f"  Compressed: {compressed_size} bytes")
        print(f"  Ratio: {ratio:.2f}:1")
        print(f"  Method: {method}")
        print(f"  Success: {decompressed == message}")
        print()

    overall_ratio = total_original / total_compressed if total_compressed > 0 else 1.0
    savings = total_original - total_compressed
    savings_pct = (savings / total_original) * 100 if total_original > 0 else 0

    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total Original: {total_original} bytes")
    print(f"Total Compressed: {total_compressed} bytes")
    print(f"Overall Ratio: {overall_ratio:.2f}:1")
    print(f"Space Saved: {savings} bytes ({savings_pct:.1f}%)")
    print()


def main():
    """Main entry point for aura-server CLI."""
    parser = argparse.ArgumentParser(
        description="Run AURA WebSocket compression server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        '-H', '--host',
        default='0.0.0.0',
        help='Host to bind server (default: 0.0.0.0)'
    )

    parser.add_argument(
        '-p', '--port',
        type=int,
        default=8765,
        help='Port to bind server (default: 8765)'
    )

    parser.add_argument(
        '--demo',
        action='store_true',
        help='Run compression demo instead of server'
    )

    args = parser.parse_args()

    if args.demo:
        run_demo()
    else:
        server = SimpleWebSocketServer()
        try:
            asyncio.run(server.serve(host=args.host, port=args.port))
        except KeyboardInterrupt:
            print("\nShutting down AURA server")


if __name__ == '__main__':
    main()