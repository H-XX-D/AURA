#!/usr/bin/env python3
"""
Real-World Internet Compression Simulation
Simulates AURA compression system performance over internet-like conditions
"""

import asyncio
import websockets
import json
import time
import random
import statistics
import threading
from typing import Dict, List, Any, Tuple
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'src' / 'python'))

from aura_compression.compressor import ProductionHybridCompressor

class NetworkSimulator:
    """Simulates internet network conditions."""

    def __init__(self, latency_ms: float = 50.0, bandwidth_mbps: float = 10.0,
                 packet_loss: float = 0.01, jitter_ms: float = 10.0):
        self.latency_ms = latency_ms
        self.bandwidth_mbps = bandwidth_mbps
        self.packet_loss = packet_loss
        self.jitter_ms = jitter_ms

    async def simulate_network_delay(self, data_size_bytes: int) -> float:
        """Simulate network transmission time based on data size and bandwidth."""
        # Base latency
        delay = self.latency_ms / 1000.0

        # Bandwidth delay (data_size in bits / bandwidth in bits per second)
        bandwidth_delay = (data_size_bytes * 8) / (self.bandwidth_mbps * 1000000)

        # Add jitter
        jitter = random.uniform(-self.jitter_ms, self.jitter_ms) / 1000.0

        # Packet loss simulation (occasional extra delay)
        if random.random() < self.packet_loss:
            delay += random.uniform(0.1, 0.5)  # Retransmission delay

        total_delay = delay + bandwidth_delay + jitter
        await asyncio.sleep(max(0.001, total_delay))  # Minimum 1ms delay
        return total_delay

class MessageGenerator:
    """Generates realistic internet traffic messages."""

    def __init__(self):
        # Chat messages
        self.chat_templates = [
            "Hello everyone!",
            "How is everyone doing today?",
            "Thanks for the help!",
            "I need assistance with this issue",
            "Can someone explain this to me?",
            "Great work on the latest update!",
            "I'm having trouble with the login",
            "The performance has improved significantly",
            "Can we schedule a meeting to discuss this?",
            "I appreciate all the hard work",
            "This feature is exactly what I needed",
            "The user interface is very intuitive"
        ]

        # API responses
        self.api_responses = [
            {"status": "success", "data": {"user_id": 123, "action": "login"}},
            {"status": "error", "message": "Invalid credentials", "code": 401},
            {"status": "success", "data": {"posts": [{"id": 1, "title": "Hello World"}]}},
            {"status": "success", "data": {"stats": {"users": 1000, "posts": 5000}}},
        ]

        # Log entries
        self.log_levels = ['INFO', 'WARN', 'ERROR', 'DEBUG']
        self.log_components = ['auth', 'api', 'db', 'cache', 'worker']
        self.log_messages = [
            'User login successful',
            'Database query executed',
            'Cache miss for key',
            'API request processed',
            'Worker task completed',
            'Connection established',
            'File uploaded successfully',
            'Validation failed',
            'Rate limit exceeded',
            'Service unavailable'
        ]

        # Email/SMTP style messages
        self.email_subjects = [
            "Welcome to our platform",
            "Password reset request",
            "Your order has been shipped",
            "Important security update",
            "Weekly newsletter",
            "Account verification required"
        ]

    def generate_message(self, message_type: str = None) -> Tuple[str, str]:
        """Generate a random message of specified or random type."""
        if message_type is None:
            message_type = random.choice(['chat', 'api', 'log', 'email'])

        if message_type == 'chat':
            user = f"User_{random.randint(1, 1000)}"
            message = random.choice(self.chat_templates)
            # Add some variation
            if random.random() < 0.3:
                message += " " + "".join(random.choices("abcdefghijklmnopqrstuvwxyz", k=random.randint(5, 20)))
            content = json.dumps({
                "type": "chat",
                "timestamp": time.time(),
                "user": user,
                "message": message,
                "message_id": f"msg_{random.randint(1000, 9999)}"
            })
            return content, 'chat'

        elif message_type == 'api':
            response = random.choice(self.api_responses).copy()
            response["timestamp"] = time.time()
            response["request_id"] = f"req_{random.randint(1000, 9999)}"
            content = json.dumps(response)
            return content, 'api'

        elif message_type == 'log':
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
            level = random.choice(self.log_levels)
            component = random.choice(self.log_components)
            message = random.choice(self.log_messages)

            if 'User' in message:
                message += f": user_id={random.randint(1000, 9999)}"
            elif 'Database' in message:
                message += f": table=users, duration={random.randint(1, 100)}ms"
            elif 'Cache' in message:
                message += f": key=user:{random.randint(1000, 9999)}"

            content = f"{timestamp} {level} [{component}] {message}"
            return content, 'log'

        elif message_type == 'email':
            subject = random.choice(self.email_subjects)
            body = f"This is the body of the email with subject: {subject}. " * random.randint(1, 3)
            content = f"Subject: {subject}\n\n{body.strip()}"
            return content, 'email'

        else:
            # Default to chat
            return self.generate_message('chat')

class CompressionServer:
    """WebSocket server that handles compressed message traffic."""

    def __init__(self, network_simulator: NetworkSimulator):
        self.compressor = ProductionHybridCompressor(enable_aura=True, min_compression_size=10)
        self.network_sim = network_simulator
        self.stats = {
            'messages_processed': 0,
            'total_original_bytes': 0,
            'total_compressed_bytes': 0,
            'compression_ratios': [],
            'method_usage': {},
            'processing_times': [],
            'network_delays': [],
            'message_types': {},
            'start_time': time.time()
        }
        self.lock = threading.Lock()

    async def handle_client(self, websocket):
        """Handle individual client connections."""
        client_id = f"client_{random.randint(1000, 9999)}"
        print(f"🌐 New client connected: {client_id}")

        try:
            async for message in websocket:
                # Simulate network receive delay
                data_size = len(message)
                network_delay = await self.network_sim.simulate_network_delay(data_size)

                # Process the message
                start_time = time.time()
                try:
                    # Try to decompress if it's compressed, otherwise treat as plain text
                    if isinstance(message, bytes) and len(message) > 0:
                        method_byte = message[0]
                        if 0x00 <= method_byte <= 0xFF:  # Valid compression method
                            decompressed = self.compressor.decompress(message)
                            original_size = len(decompressed.encode('utf-8'))
                            compressed_size = len(message)
                        else:
                            # Plain text message
                            decompressed = message.decode('utf-8')
                            original_size = len(message)
                            compressed_size = len(message)
                    else:
                        decompressed = message.decode('utf-8') if isinstance(message, bytes) else str(message)
                        original_size = len(decompressed.encode('utf-8'))
                        compressed_size = len(message) if isinstance(message, bytes) else len(message.encode('utf-8'))

                    processing_time = time.time() - start_time

                    # Compress response
                    response_text = f"Echo: {decompressed}"
                    compressed_response, method, metadata = self.compressor.compress(response_text)
                    response_size = len(compressed_response)

                    # Simulate network send delay
                    send_delay = await self.network_sim.simulate_network_delay(response_size)

                    # Send response
                    await websocket.send(compressed_response)

                    # Update statistics
                    with self.lock:
                        self.stats['messages_processed'] += 1
                        self.stats['total_original_bytes'] += original_size
                        self.stats['total_compressed_bytes'] += compressed_size

                        if original_size > 0:
                            ratio = original_size / compressed_size
                            self.stats['compression_ratios'].append(ratio)

                        method_name = method.name if hasattr(method, 'name') else str(method)
                        self.stats['method_usage'][method_name] = self.stats['method_usage'].get(method_name, 0) + 1

                        self.stats['processing_times'].append(processing_time)
                        self.stats['network_delays'].append(network_delay + send_delay)

                        # Try to detect message type
                        try:
                            msg_data = json.loads(decompressed)
                            msg_type = msg_data.get('type', 'unknown')
                        except:
                            if 'Subject:' in decompressed:
                                msg_type = 'email'
                            elif any(level in decompressed for level in ['INFO', 'WARN', 'ERROR', 'DEBUG']):
                                msg_type = 'log'
                            else:
                                msg_type = 'text'

                        self.stats['message_types'][msg_type] = self.stats['message_types'].get(msg_type, 0) + 1

                except Exception as e:
                    print(f"❌ Error processing message from {client_id}: {e}")
                    # Send error response
                    error_msg = "Error processing message"
                    await websocket.send(error_msg.encode())

        except websockets.exceptions.ConnectionClosed:
            print(f"📴 Client disconnected: {client_id}")
        except Exception as e:
            print(f"❌ Unexpected error with {client_id}: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get current performance statistics."""
        with self.lock:
            runtime = time.time() - self.stats['start_time']

            stats_copy = self.stats.copy()
            stats_copy.update({
                'runtime_seconds': runtime,
                'messages_per_second': self.stats['messages_processed'] / max(1, runtime),
                'average_compression_ratio': statistics.mean(self.stats['compression_ratios']) if self.stats['compression_ratios'] else 1.0,
                'average_processing_time_ms': statistics.mean(self.stats['processing_times']) * 1000 if self.stats['processing_times'] else 0,
                'average_network_delay_ms': statistics.mean(self.stats['network_delays']) * 1000 if self.stats['network_delays'] else 0,
                'bandwidth_savings_percent': ((sum(self.stats['compression_ratios']) / max(1, len(self.stats['compression_ratios']))) - 1) * 100 if self.stats['compression_ratios'] else 0,
            })

            return stats_copy

class CompressionClient:
    """Client that sends messages to the compression server."""

    def __init__(self, client_id: int, network_simulator: NetworkSimulator, message_generator: MessageGenerator):
        self.client_id = client_id
        self.network_sim = network_simulator
        self.message_gen = message_generator
        self.compressor = ProductionHybridCompressor(enable_aura=True, min_compression_size=10)
        self.stats = {
            'messages_sent': 0,
            'bytes_sent': 0,
            'bytes_received': 0,
            'compression_ratios': [],
            'response_times': [],
        }

    async def run(self, duration_seconds: int = 60):
        """Run client for specified duration."""
        uri = "ws://localhost:8765"
        end_time = time.time() + duration_seconds

        try:
            async with websockets.connect(uri) as websocket:
                print(f"🚀 Client {self.client_id} connected to server")

                while time.time() < end_time:
                    # Generate and compress message
                    message, msg_type = self.message_gen.generate_message()
                    compressed, method, metadata = self.compressor.compress(message)

                    # Send message
                    send_start = time.time()
                    await websocket.send(compressed)

                    # Receive response
                    response = await websocket.recv()
                    response_time = time.time() - send_start

                    # Decompress response
                    try:
                        decompressed_response = self.compressor.decompress(response)
                    except:
                        decompressed_response = response.decode('utf-8') if isinstance(response, bytes) else str(response)

                    # Update stats
                    original_size = len(message.encode('utf-8'))
                    compressed_size = len(compressed)
                    response_size = len(response) if isinstance(response, bytes) else len(str(response).encode('utf-8'))

                    self.stats['messages_sent'] += 1
                    self.stats['bytes_sent'] += compressed_size
                    self.stats['bytes_received'] += response_size
                    self.stats['response_times'].append(response_time)

                    if original_size > 0:
                        ratio = original_size / compressed_size
                        self.stats['compression_ratios'].append(ratio)

                    # Small delay between messages
                    await asyncio.sleep(random.uniform(0.1, 0.5))

        except Exception as e:
            print(f"❌ Client {self.client_id} error: {e}")

        print(f"✅ Client {self.client_id} finished: {self.stats['messages_sent']} messages sent")

async def run_simulation(num_clients: int = 5, duration_seconds: int = 30):
    """Run the complete internet compression simulation."""
    print("🌐 AURA INTERNET COMPRESSION SIMULATION")
    print("=" * 80)
    print(f"Clients: {num_clients} | Duration: {duration_seconds}s")
    print("=" * 80)

    # Initialize components
    network_sim = NetworkSimulator(
        latency_ms=50.0,      # Typical internet latency
        bandwidth_mbps=10.0,  # 10 Mbps connection
        packet_loss=0.01,     # 1% packet loss
        jitter_ms=15.0        # Network jitter
    )

    message_gen = MessageGenerator()
    server = CompressionServer(network_sim)

    # Start WebSocket server
    server_task = await websockets.serve(server.handle_client, "localhost", 8765)
    print("🚀 Compression server started on ws://localhost:8765")

    # Start clients
    clients = []
    client_tasks = []

    for i in range(num_clients):
        client = CompressionClient(i + 1, network_sim, message_gen)
        clients.append(client)
        client_tasks.append(asyncio.create_task(client.run(duration_seconds)))

    # Wait for simulation to complete
    print(f"⏳ Running simulation for {duration_seconds} seconds...")
    await asyncio.sleep(duration_seconds + 2)  # Extra time for cleanup

    # Cancel client tasks
    for task in client_tasks:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    # Stop server
    server_task.close()
    await server_task.wait_closed()

    # Collect and display results
    print("\n" + "=" * 80)
    print("📊 SIMULATION RESULTS")
    print("=" * 80)

    # Server statistics
    server_stats = server.get_stats()
    print("\n🔧 SERVER STATISTICS:")
    print(f"  Messages Processed: {server_stats['messages_processed']}")
    print(f"  Runtime: {server_stats['runtime_seconds']:.1f}s")
    print(f"  Throughput: {server_stats['messages_per_second']:.1f} msg/s")
    print(f"  Average Compression Ratio: {server_stats['average_compression_ratio']:.2f}x")
    print(f"  Bandwidth Savings: {server_stats['bandwidth_savings_percent']:+.1f}%")
    print(f"  Average Processing Time: {server_stats['average_processing_time_ms']:.2f}ms")
    print(f"  Average Network Delay: {server_stats['average_network_delay_ms']:.2f}ms")

    print(f"\n  Method Usage: {server_stats['method_usage']}")
    print(f"  Message Types: {server_stats['message_types']}")

    # Client statistics
    total_client_messages = sum(client.stats['messages_sent'] for client in clients)
    total_client_bytes_sent = sum(client.stats['bytes_sent'] for client in clients)
    total_client_bytes_received = sum(client.stats['bytes_received'] for client in clients)
    all_client_ratios = []
    all_client_response_times = []

    for client in clients:
        all_client_ratios.extend(client.stats['compression_ratios'])
        all_client_response_times.extend(client.stats['response_times'])

    if all_client_ratios:
        avg_client_ratio = statistics.mean(all_client_ratios)
        print("\n👥 CLIENT STATISTICS:")
        print(f"  Total Messages Sent: {total_client_messages}")
        print(f"  Average Compression Ratio: {avg_client_ratio:.2f}x")
        print(f"  Total Data Sent: {total_client_bytes_sent} bytes")
        print(f"  Total Data Received: {total_client_bytes_received} bytes")
        print(f"  Average Response Time: {statistics.mean(all_client_response_times)*1000:.2f}ms")

    # Performance analysis
    print("\n🎯 PERFORMANCE ANALYSIS:")
    if server_stats['average_compression_ratio'] > 1.2:
        print("  ✅ Excellent compression performance (>20% bandwidth savings)")
    elif server_stats['average_compression_ratio'] > 1.1:
        print("  ✅ Good compression performance (>10% bandwidth savings)")
    elif server_stats['average_compression_ratio'] > 1.0:
        print("  ⚠️ Moderate compression performance (<10% bandwidth savings)")
    else:
        print("  ❌ Poor compression performance (expansion)")

    if server_stats['average_processing_time_ms'] < 10:
        print("  ✅ Fast processing (<10ms per message)")
    elif server_stats['average_processing_time_ms'] < 50:
        print("  ⚠️ Moderate processing (10-50ms per message)")
    else:
        print("  ❌ Slow processing (>50ms per message)")

    if server_stats['messages_per_second'] > 100:
        print("  ✅ High throughput (>100 msg/s)")
    elif server_stats['messages_per_second'] > 50:
        print("  ⚠️ Moderate throughput (50-100 msg/s)")
    else:
        print("  ❌ Low throughput (<50 msg/s)")

    print("\n🏆 SIMULATION COMPLETE")
    print("=" * 80)

def main():
    """Main simulation function."""
    import argparse

    parser = argparse.ArgumentParser(description="AURA Internet Compression Simulation")
    parser.add_argument('--clients', type=int, default=3, help='Number of concurrent clients')
    parser.add_argument('--duration', type=int, default=20, help='Simulation duration in seconds')
    parser.add_argument('--latency', type=float, default=50.0, help='Network latency in ms')
    parser.add_argument('--bandwidth', type=float, default=10.0, help='Network bandwidth in Mbps')

    args = parser.parse_args()

    # Update network conditions
    network_sim = NetworkSimulator(
        latency_ms=args.latency,
        bandwidth_mbps=args.bandwidth
    )

    # Run simulation with custom network conditions
    asyncio.run(run_simulation_with_custom_network(args.clients, args.duration, network_sim))

async def run_simulation_with_custom_network(num_clients: int, duration_seconds: int, network_sim: NetworkSimulator):
    """Run simulation with custom network conditions."""
    print("🌐 AURA INTERNET COMPRESSION SIMULATION")
    print("=" * 80)
    print(f"Clients: {num_clients} | Duration: {duration_seconds}s")
    print(f"Network: {network_sim.latency_ms}ms latency, {network_sim.bandwidth_mbps}Mbps bandwidth")
    print("=" * 80)

    message_gen = MessageGenerator()
    server = CompressionServer(network_sim)

    # Start WebSocket server
    server_task = await websockets.serve(server.handle_client, "localhost", 8765)
    print("🚀 Compression server started on ws://localhost:8765")

    # Start clients
    clients = []
    client_tasks = []

    for i in range(num_clients):
        client = CompressionClient(i + 1, network_sim, message_gen)
        clients.append(client)
        client_tasks.append(asyncio.create_task(client.run(duration_seconds)))

    # Wait for simulation
    print(f"⏳ Running simulation for {duration_seconds} seconds...")
    await asyncio.sleep(duration_seconds + 2)

    # Cleanup
    for task in client_tasks:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    server_task.close()
    await server_task.wait_closed()

    # Results
    server_stats = server.get_stats()
    print("\n📊 RESULTS:")
    print(f"  Messages: {server_stats['messages_processed']}")
    print(f"  Compression Ratio: {server_stats['average_compression_ratio']:.2f}x")
    print(f"  Bandwidth Savings: {server_stats['bandwidth_savings_percent']:+.1f}%")
    print(f"  Throughput: {server_stats['messages_per_second']:.1f} msg/s")
    print(f"  Processing Time: {server_stats['average_processing_time_ms']:.2f}ms")
    print(f"  Network Delay: {server_stats['average_network_delay_ms']:.2f}ms")

if __name__ == "__main__":
    # Run with default settings
    asyncio.run(run_simulation(num_clients=3, duration_seconds=20))