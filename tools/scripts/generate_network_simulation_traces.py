#!/usr/bin/env python3
"""
AURA Network Simulation Framework

Simulates realistic network conditions for compression performance testing.
Includes latency, bandwidth, packet loss, and protocol overhead.
"""

import time
import random
import json
import asyncio
import threading
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import statistics
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent
import sys
sys.path.insert(0, str(ROOT))

from aura_compression import ProductionHybridCompressor


class NetworkType(Enum):
    """Different network types with realistic characteristics."""
    WIFI_FAST = "wifi_fast"        # 100 Mbps, 10ms latency
    WIFI_SLOW = "wifi_slow"        # 25 Mbps, 25ms latency
    ETHERNET = "ethernet"          # 1 Gbps, 1ms latency
    LTE_4G = "lte_4g"             # 50 Mbps, 45ms latency
    LTE_3G = "lte_3g"             # 2 Mbps, 150ms latency
    EDGE_2G = "edge_2g"           # 0.2 Mbps, 500ms latency
    SATELLITE = "satellite"       # 10 Mbps, 600ms latency
    FIBER = "fiber"               # 10 Gbps, 0.5ms latency


class ProtocolType(Enum):
    """Network protocols with different overhead characteristics."""
    WEBSOCKET = "websocket"       # WebSocket with framing
    HTTP2 = "http2"              # HTTP/2 with multiplexing
    HTTP1 = "http1"              # HTTP/1.1 with headers
    TCP_RAW = "tcp_raw"          # Raw TCP (minimal overhead)


@dataclass
class NetworkProfile:
    """Network condition profile."""
    name: str
    bandwidth_mbps: float          # Megabits per second
    base_latency_ms: float         # Base round-trip latency
    jitter_ms: float              # Random latency variation
    packet_loss_rate: float       # Packet loss probability (0-1)
    mtu_bytes: int                # Maximum transmission unit


@dataclass
class ProtocolOverhead:
    """Protocol-specific overhead."""
    name: str
    header_bytes_per_message: int  # Fixed header overhead
    framing_efficiency: float      # Framing efficiency (0-1)
    connection_setup_ms: float     # Connection establishment time
    ssl_handshake_ms: float       # SSL/TLS handshake time


class NetworkSimulator:
    """Simulates realistic network conditions."""

    def __init__(self):
        self.profiles = self._create_network_profiles()
        self.protocols = self._create_protocol_overheads()
        self.compressor = ProductionHybridCompressor(enable_gpu=True)

    def _create_network_profiles(self) -> Dict[str, NetworkProfile]:
        """Create realistic network profiles based on real-world measurements."""
        return {
            NetworkType.WIFI_FAST.value: NetworkProfile(
                "WiFi Fast", 100.0, 10.0, 5.0, 0.001, 1500
            ),
            NetworkType.WIFI_SLOW.value: NetworkProfile(
                "WiFi Slow", 25.0, 25.0, 10.0, 0.005, 1500
            ),
            NetworkType.ETHERNET.value: NetworkProfile(
                "Ethernet", 1000.0, 1.0, 0.5, 0.0001, 1500
            ),
            NetworkType.LTE_4G.value: NetworkProfile(
                "LTE 4G", 50.0, 45.0, 15.0, 0.01, 1420
            ),
            NetworkType.LTE_3G.value: NetworkProfile(
                "LTE 3G", 2.0, 150.0, 50.0, 0.05, 1420
            ),
            NetworkType.EDGE_2G.value: NetworkProfile(
                "EDGE 2G", 0.2, 500.0, 200.0, 0.1, 1420
            ),
            NetworkType.SATELLITE.value: NetworkProfile(
                "Satellite", 10.0, 600.0, 100.0, 0.02, 1420
            ),
            NetworkType.FIBER.value: NetworkProfile(
                "Fiber", 10000.0, 0.5, 0.1, 0.00001, 9000
            ),
        }

    def _create_protocol_overheads(self) -> Dict[str, ProtocolOverhead]:
        """Create protocol overhead profiles."""
        return {
            ProtocolType.WEBSOCKET.value: ProtocolOverhead(
                "WebSocket", 8, 0.95, 150.0, 100.0  # Connection + SSL
            ),
            ProtocolType.HTTP2.value: ProtocolOverhead(
                "HTTP/2", 20, 0.92, 120.0, 80.0
            ),
            ProtocolType.HTTP1.value: ProtocolOverhead(
                "HTTP/1.1", 800, 0.85, 100.0, 60.0  # Large headers
            ),
            ProtocolType.TCP_RAW.value: ProtocolOverhead(
                "Raw TCP", 40, 0.98, 50.0, 0.0  # TCP + IP headers only
            ),
        }

    def simulate_packet_loss(self, loss_rate: float) -> bool:
        """Simulate packet loss."""
        return random.random() < loss_rate

    def simulate_latency(self, base_latency: float, jitter: float) -> float:
        """Simulate network latency with jitter."""
        return base_latency + random.uniform(-jitter, jitter)

    def calculate_transmission_time(self, data_size_bytes: int, bandwidth_mbps: float) -> float:
        """Calculate transmission time for data over network."""
        # Convert to bits and divide by bandwidth
        data_bits = data_size_bytes * 8
        bandwidth_bps = bandwidth_mbps * 1_000_000
        return (data_bits / bandwidth_bps) * 1000  # Convert to milliseconds

    def simulate_protocol_overhead(self, message_size: int, protocol: ProtocolOverhead) -> Tuple[int, float]:
        """Calculate protocol overhead and processing time."""
        # Add protocol headers
        total_size = message_size + protocol.header_bytes_per_message

        # Account for framing efficiency
        effective_size = total_size / protocol.framing_efficiency

        # Protocol processing time (simplified)
        processing_time = protocol.connection_setup_ms * 0.1  # Per-message overhead

        return int(effective_size), processing_time

    def simulate_network_transmission(self,
                                    data_size: int,
                                    network: NetworkProfile,
                                    protocol: ProtocolOverhead,
                                    is_first_message: bool = False) -> Dict[str, Any]:
        """
        Simulate full network transmission with all realistic conditions.

        Returns detailed timing breakdown.
        """
        timing = {
            'connection_setup_ms': 0.0,
            'ssl_handshake_ms': 0.0,
            'dns_resolution_ms': 0.0,
            'tcp_handshake_ms': 0.0,
            'transmission_ms': 0.0,
            'protocol_overhead_ms': 0.0,
            'total_network_latency_ms': 0.0,
            'packet_loss_events': 0,
            'retransmissions': 0,
            'effective_data_size': data_size
        }

        # Connection establishment (only for first message)
        if is_first_message:
            # DNS resolution
            timing['dns_resolution_ms'] = random.uniform(10, 50)

            # TCP handshake (3-way)
            timing['tcp_handshake_ms'] = network.base_latency_ms * 1.5

            # SSL/TLS handshake
            timing['ssl_handshake_ms'] = protocol.ssl_handshake_ms + random.uniform(-10, 10)

            # Protocol connection setup
            timing['connection_setup_ms'] = protocol.connection_setup_ms

        # Protocol overhead
        effective_size, protocol_time = self.simulate_protocol_overhead(data_size, protocol)
        timing['protocol_overhead_ms'] = protocol_time
        timing['effective_data_size'] = effective_size

        # Network latency (RTT)
        network_latency = self.simulate_latency(network.base_latency_ms, network.jitter_ms)

        # Transmission time
        transmission_time = self.calculate_transmission_time(effective_size, network.bandwidth_mbps)
        timing['transmission_ms'] = transmission_time

        # Packet loss simulation
        packets_needed = max(1, effective_size // network.mtu_bytes)
        for _ in range(packets_needed):
            if self.simulate_packet_loss(network.packet_loss_rate):
                timing['packet_loss_events'] += 1
                timing['retransmissions'] += 1
                # Retransmission adds extra latency
                network_latency += network.base_latency_ms * 2

        # Total network time
        timing['total_network_latency_ms'] = (
            network_latency +
            transmission_time +
            timing['protocol_overhead_ms'] +
            timing['connection_setup_ms'] +
            timing['ssl_handshake_ms'] +
            timing['tcp_handshake_ms'] +
            timing['dns_resolution_ms']
        )

        return timing


class NetworkAwareTraceGenerator:
    """Generates traces that include realistic network conditions."""

    def __init__(self):
        self.simulator = NetworkSimulator()
        self.base_timestamp = datetime(2025, 10, 27, 9, 0, 0)

    def get_realistic_messages(self) -> List[str]:
        """Get diverse message types for network simulation."""
        # Generate diverse messages similar to the original trace generator
        return [
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

    def generate_network_trace(self,
                             user_id: int,
                             num_messages: int = 50,
                             network_type: str = "wifi_fast",
                             protocol_type: str = "websocket") -> List[Dict[str, Any]]:
        """
        Generate traces with realistic network conditions.
        """

        messages = self.get_realistic_messages()
        trace_data = []

        network_profile = self.simulator.profiles[network_type]
        protocol_profile = self.simulator.protocols[protocol_type]

        current_timestamp = self.base_timestamp + timedelta(hours=user_id)
        is_first_message = True

        for turn in range(min(num_messages, len(messages))):
            message = messages[turn]

            # Add realistic timing between messages
            time_offset = timedelta(
                minutes=random.randint(1, 30),
                seconds=random.randint(0, 59)
            )
            current_timestamp += time_offset

            # Step 1: Local compression (algorithm performance)
            start_compress = time.time()
            compressed, method, metadata = self.simulator.compressor.compress(message)
            compression_latency_ms = (time.time() - start_compress) * 1000

            original_size = len(message.encode('utf-8'))
            compressed_size = len(compressed)
            compression_ratio = original_size / compressed_size if compressed_size > 0 else 1.0

            # Step 2: Network transmission simulation
            network_timing = self.simulator.simulate_network_transmission(
                compressed_size,
                network_profile,
                protocol_profile,
                is_first_message
            )

            # Total end-to-end latency
            total_latency_ms = compression_latency_ms + network_timing['total_network_latency_ms']

            # Create comprehensive trace entry
            trace_entry = {
                "user_id": user_id,
                "turn": turn,
                "timestamp": current_timestamp.isoformat(),
                "message": message,
                "message_length": len(message),

                # Compression metrics
                "compression_method": method.name if hasattr(method, 'name') else str(method),
                "compression_ratio": compression_ratio,
                "compression_latency_ms": compression_latency_ms,
                "original_size": original_size,
                "compressed_size": compressed_size,

                # Network conditions
                "network_type": network_type,
                "protocol_type": protocol_type,
                "network_profile": {
                    "bandwidth_mbps": network_profile.bandwidth_mbps,
                    "base_latency_ms": network_profile.base_latency_ms,
                    "jitter_ms": network_profile.jitter_ms,
                    "packet_loss_rate": network_profile.packet_loss_rate
                },

                # Network timing breakdown
                "network_timing": network_timing,
                "total_network_latency_ms": network_timing['total_network_latency_ms'],
                "total_end_to_end_latency_ms": total_latency_ms,

                # Success and metadata
                "success": True,
                "is_first_message": is_first_message
            }

            trace_data.append(trace_entry)
            is_first_message = False  # Subsequent messages reuse connection

        return trace_data

    def generate_multi_network_traces(self,
                                    num_users: int = 5,
                                    messages_per_user: int = 25) -> Dict[str, List[Dict[str, Any]]]:
        """
        Generate traces across multiple network types for comparison.
        """

        network_types = list(self.simulator.profiles.keys())
        protocol_type = "websocket"  # Most realistic for chat applications

        all_traces = {}

        for network_type in network_types:
            print(f"Generating traces for {network_type}...")
            network_traces = []

            for user_id in range(1, num_users + 1):
                user_traces = self.generate_network_trace(
                    user_id, messages_per_user, network_type, protocol_type
                )
                network_traces.extend(user_traces)

            all_traces[network_type] = network_traces

        return all_traces

    def save_network_traces(self, traces: Dict[str, List[Dict[str, Any]]], output_dir: str = "network_simulation_traces"):
        """Save network-aware traces organized by network type."""

        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)

        for network_type, trace_data in traces.items():
            network_dir = output_path / network_type
            network_dir.mkdir(exist_ok=True)

            # Save individual user files
            users = {}
            for entry in trace_data:
                user_id = entry['user_id']
                if user_id not in users:
                    users[user_id] = []
                users[user_id].append(entry)

            for user_id, user_entries in users.items():
                filename = f"user_{user_id}_traces.jsonl"
                filepath = network_dir / filename

                with open(filepath, 'w', encoding='utf-8') as f:
                    for entry in user_entries:
                        json.dump(entry, f, ensure_ascii=False)
                        f.write('\n')

            # Save network summary
            self._save_network_summary(network_dir, trace_data, network_type)

        # Save overall comparison
        self._save_overall_comparison(output_path, traces)

    def _save_network_summary(self, network_dir: Path, trace_data: List[Dict[str, Any]], network_type: str):
        """Save summary statistics for a network type."""

        if not trace_data:
            return

        stats = {
            "network_type": network_type,
            "total_entries": len(trace_data),
            "total_users": len(set(entry['user_id'] for entry in trace_data)),
            "compression_methods": {},
            "avg_compression_ratio": statistics.mean(entry['compression_ratio'] for entry in trace_data),
            "avg_compression_latency_ms": statistics.mean(entry['compression_latency_ms'] for entry in trace_data),
            "avg_network_latency_ms": statistics.mean(entry['total_network_latency_ms'] for entry in trace_data),
            "avg_end_to_end_latency_ms": statistics.mean(entry['total_end_to_end_latency_ms'] for entry in trace_data),
            "min_end_to_end_latency_ms": min(entry['total_end_to_end_latency_ms'] for entry in trace_data),
            "max_end_to_end_latency_ms": max(entry['total_end_to_end_latency_ms'] for entry in trace_data),
            "network_profile": trace_data[0]['network_profile'],
            "protocol_type": trace_data[0]['protocol_type']
        }

        # Count compression methods
        for entry in trace_data:
            method = entry['compression_method']
            stats["compression_methods"][method] = stats["compression_methods"].get(method, 0) + 1

        with open(network_dir / "network_summary.json", 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)

    def _save_overall_comparison(self, output_path: Path, traces: Dict[str, List[Dict[str, Any]]]):
        """Save comparison across all network types."""

        comparison = {}

        for network_type, trace_data in traces.items():
            if not trace_data:
                continue

            comparison[network_type] = {
                "total_entries": len(trace_data),
                "avg_compression_ratio": statistics.mean(entry['compression_ratio'] for entry in trace_data),
                "avg_compression_latency_ms": statistics.mean(entry['compression_latency_ms'] for entry in trace_data),
                "avg_network_latency_ms": statistics.mean(entry['total_network_latency_ms'] for entry in trace_data),
                "avg_end_to_end_latency_ms": statistics.mean(entry['total_end_to_end_latency_ms'] for entry in trace_data),
                "bandwidth_mbps": trace_data[0]['network_profile']['bandwidth_mbps'],
                "base_latency_ms": trace_data[0]['network_profile']['base_latency_ms']
            }

        with open(output_path / "network_comparison.json", 'w', encoding='utf-8') as f:
            json.dump(comparison, f, indent=2, ensure_ascii=False)


def main():
    """Main entry point for network simulation."""

    import argparse

    parser = argparse.ArgumentParser(description="Generate network-aware AURA traces")
    parser.add_argument("--users", type=int, default=5, help="Number of users per network type")
    parser.add_argument("--messages", type=int, default=25, help="Number of messages per user")
    parser.add_argument("--output", type=str, default="network_simulation_traces", help="Output directory")

    args = parser.parse_args()

    print("Generating network-aware AURA traces...")
    print(f"Users per network: {args.users}")
    print(f"Messages per user: {args.messages}")

    generator = NetworkAwareTraceGenerator()
    traces = generator.generate_multi_network_traces(args.users, args.messages)
    generator.save_network_traces(traces, args.output)

    print(f"\nNetwork simulation traces saved to {args.output}/")
    print("Includes realistic network conditions for all major network types!")


if __name__ == "__main__":
    main()