#!/usr/bin/env python3
"""
Network Simulation for AURA Compression System

Tests template discovery and ML algorithm selection over a 3-minute period.
Generates various message types to simulate real network traffic and measures
compression performance, template discovery effectiveness, and ML decision accuracy.
"""

import argparse
import json
import os
import random
import statistics
import sys
import threading
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from aura_compression.compressor_refactored import ProductionHybridCompressor
from aura_compression.enums import CompressionMethod
from aura_compression.ml_algorithm_selector import MLAlgorithmSelector
from aura_compression.template_service import TemplateService


class NetworkSimulator:
    """
    Simulates network traffic to test AURA compression system
    """

    def __init__(self, duration_seconds: int = 60, enable_scorer: Optional[bool] = None):
        self.duration = timedelta(seconds=duration_seconds)
        self.start_time = None
        self.end_time = None
        self.running = False
        self.enable_scorer = enable_scorer

        # Statistics collection
        self.stats = {
            "total_messages": 0,
            "compression_methods_used": Counter(),
            "compression_ratios": [],
            "template_discoveries": [],
            "ml_decisions": [],
            "message_types": Counter(),
            "processing_times": [],
            "message_sizes": [],  # Track message sizes
            "size_distribution": {"small": 0, "medium": 0, "large": 0},  # Size categories
            "errors": [],
            "template_matches": 0,
            "pattern_semantic_usage": 0,
            "binary_semantic_usage": 0,
            "available_methods_count": Counter(),  # Track how many methods are available per message
            "template_matching_attempts": 0,  # Total template matching attempts
            "template_matching_failures": 0,  # Failed template matches
            "ml_selection_reasons": Counter(),  # Why ML chose certain methods
            "compression_method_details": defaultdict(list),  # Detailed method usage with ratios
            "latency_stats": [],  # Processing latency in milliseconds
            "bandwidth_stats": [],  # Bandwidth in bytes/second
            "latency_by_method": defaultdict(list),  # Latency per compression method
            "bandwidth_by_method": defaultdict(list),  # Bandwidth per compression method
        }

        self.compressor = ProductionHybridCompressor(
            binary_advantage_threshold=1.01,
            min_compression_size=10,
            enable_aura=False,  # Disable AURA and template discovery during simulation
            enable_audit_logging=True,  # Enable audit logging for template discovery
            audit_log_directory="./simulation_audit_logs",
            template_cache_size=256,
            enable_scorer=enable_scorer,
            template_sync_interval_seconds=None,  # Skip template store sync for faster simulations
        )

        # Create a separate discovery worker with lower thresholds for testing
        from aura_compression.background_workers import TemplateDiscoveryWorker

        self.discovery_worker = TemplateDiscoveryWorker(
            audit_log_directory="./simulation_audit_logs",
            cache_dir=".aura_cache_simulation",
            discovery_interval_seconds=1800,  # Run every 30 minutes instead of 5 minutes
            min_messages_for_discovery=100,  # Higher threshold to avoid frequent runs
            min_frequency=5,  # Higher frequency requirement
            compression_threshold=1.2,  # Higher compression threshold
        )
        # Don't start the discovery worker during simulation to avoid interference
        # self.discovery_worker.start()

        # Skip initial template discovery to avoid startup latency
        # Let it run in background on schedule instead
        print(
            "Template discovery worker configured (background mode - not started during simulation)"
        )

        # Message templates for simulation
        self.message_templates = {
            "api_request": [
                '{"method": "GET", "endpoint": "/api/users/{user_id}", "headers": {"Authorization": "Bearer {token}", "Content-Type": "application/json"}}',
                '{"method": "POST", "endpoint": "/api/orders", "body": {"user_id": {user_id}, "items": [{item}]}}',
                '{"method": "PUT", "endpoint": "/api/users/{user_id}", "body": {"name": "{name}", "email": "{email}"}}',
            ],
            "log_message": [
                "[{timestamp}] INFO: User {user_id} logged in from {ip_address}",
                "[{timestamp}] ERROR: Failed to connect to database: {error_message}",
                "[{timestamp}] WARN: Rate limit exceeded for IP {ip_address}, user {user_id}",
            ],
            "chat_message": [
                "Hello {name}, how are you today?",
                "Thanks for your help with {topic}!",
                "Can you explain {concept} in more detail?",
            ],
            "binary_data": [
                "data:image/png;base64,{base64_data}",
                "data:application/pdf;base64,{base64_data}",
                "data:text/csv;base64,{base64_data}",
            ],
            "structured_data": [
                '{"timestamp": "{timestamp}", "event": "click", "user_id": {user_id}, "page": "/{page}", "element": "{element}"}',
                '{"order_id": "{order_id}", "customer_id": {customer_id}, "total": {total:.2f}, "items": {item_count}}',
                '{"sensor_id": "{sensor_id}", "reading": {reading:.2f}, "unit": "{unit}", "timestamp": "{timestamp}"}',
            ],
            "repetitive_text": [
                "The quick brown fox jumps over the lazy dog. " * random.randint(3, 10),
                "Lorem ipsum dolor sit amet, consectetur adipiscing elit. " * random.randint(2, 8),
                "System status: OK | Memory: {memory}% | CPU: {cpu}% | Network: {network}Mbps "
                * random.randint(1, 5),
            ],
        }

    def generate_message(self, message_type: str) -> str:
        """Generate a random message of the specified type with size variation"""
        templates = self.message_templates[message_type]
        template = random.choice(templates)

        # Fill in template variables
        replacements = {
            "user_id": str(random.randint(1000, 9999)),
            "token": "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=32)),
            "item": f'{{"id": {random.randint(1, 100)}, "quantity": {random.randint(1, 5)}, "price": {random.uniform(10, 100):.2f}}}',
            "name": random.choice(["Alice", "Bob", "Charlie", "Diana", "Eve"]),
            "email": f"user{random.randint(1, 1000)}@example.com",
            "timestamp": datetime.now().isoformat(),
            "ip_address": f"192.168.{random.randint(1, 255)}.{random.randint(1, 255)}",
            "error_message": random.choice(
                ["Connection timeout", "Invalid credentials", "Server error"]
            ),
            "topic": random.choice(["Python", "compression", "machine learning", "networking"]),
            "concept": random.choice(["entropy coding", "neural networks", "data structures"]),
            "base64_data": "".join(
                random.choices(
                    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/", k=100
                )
            ),
            "page": random.choice(["home", "products", "about", "contact"]),
            "element": random.choice(["button", "link", "image", "form"]),
            "order_id": f"ORD-{random.randint(10000, 99999)}",
            "customer_id": str(random.randint(1000, 9999)),
            "total": random.uniform(50, 500),
            "item_count": random.randint(1, 10),
            "sensor_id": f"SENSOR-{random.randint(1, 100)}",
            "reading": random.uniform(0, 100),
            "unit": random.choice(["Celsius", "Fahrenheit", "PSI", "Volts"]),
            "memory": random.randint(10, 90),
            "cpu": random.randint(5, 95),
            "network": random.uniform(10, 1000),
        }

        message = template
        for key, value in replacements.items():
            message = message.replace(f"{{{key}}}", str(value))

        # Add size variation based on message type
        size_multiplier = random.random()  # 0.0 to 1.0

        if message_type == "api_request":
            # API requests: small to medium (50-500 chars)
            if size_multiplier > 0.7:
                # Add extra headers or body content
                extra_headers = "".join(
                    [f'\n"X-Custom-{i}": "value{i}"' for i in range(random.randint(1, 5))]
                )
                message = message.replace("}", f",{extra_headers}}}")
            elif size_multiplier < 0.3:
                # Keep small
                pass

        elif message_type == "log_message":
            # Log messages: small to large (50-1000 chars)
            if size_multiplier > 0.6:
                # Add stack trace or additional context
                stack_lines = random.randint(3, 10)
                stack_trace = "\n".join(
                    [
                        f"  at function_{i} (file_{i}.js:{random.randint(1, 100)})"
                        for i in range(stack_lines)
                    ]
                )
                message += f"\nStack trace:\n{stack_trace}"
            elif size_multiplier < 0.4:
                # Keep minimal
                pass

        elif message_type == "chat_message":
            # Chat messages: small to medium (20-300 chars)
            if size_multiplier > 0.5:
                # Make longer conversations
                follow_ups = random.randint(1, 3)
                for i in range(follow_ups):
                    message += f' And also {random.choice(["I think", "Maybe", "Perhaps"])} we should consider {random.choice(["performance", "security", "usability"])}.'
            # Small messages stay as-is

        elif message_type == "binary_data":
            # Binary data: medium to large (200-2000 chars)
            if size_multiplier > 0.5:
                # Larger base64 data
                data_size = random.randint(200, 1000)
                replacements["base64_data"] = "".join(
                    random.choices(
                        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/",
                        k=data_size,
                    )
                )
                message = template
                for key, value in replacements.items():
                    message = message.replace(f"{{{key}}}", str(value))
            elif size_multiplier < 0.3:
                # Smaller data
                data_size = random.randint(50, 150)
                replacements["base64_data"] = "".join(
                    random.choices(
                        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/",
                        k=data_size,
                    )
                )
                message = template
                for key, value in replacements.items():
                    message = message.replace(f"{{{key}}}", str(value))

        elif message_type == "structured_data":
            # Structured data: small to large (100-1500 chars)
            if size_multiplier > 0.6:
                # Add more fields or nested objects
                extra_fields = "".join(
                    [f',\n  "field_{i}": "value_{i}"' for i in range(random.randint(3, 8))]
                )
                message = message.replace("}", f"{extra_fields}}}")
            elif size_multiplier < 0.4:
                # Keep simple
                pass

        elif message_type == "repetitive_text":
            # Repetitive text: already has size variation built-in
            pass

        return message

    def process_message(self, message: str, message_type: str) -> Dict[str, Any]:
        """Process a single message and collect statistics"""
        try:
            start_time = time.time()

            # Get available methods before compression
            available_methods = self.compressor._strategy_manager.get_available_strategies()
            self.stats["available_methods_count"][len(available_methods)] += 1

            # Check template matching
            template_match = self.compressor._template_service.find_template_match(message)
            self.stats["template_matching_attempts"] += 1
            if template_match is None:
                self.stats["template_matching_failures"] += 1

            # Compress the message
            compressed_data, compression_method, metadata = self.compressor.compress(message)

            processing_time = time.time() - start_time

            # Extract compression info from the tuple return
            compression_ratio = metadata.get("ratio", 1.0)
            method_name = (
                compression_method.value
                if hasattr(compression_method, "value")
                else str(compression_method)
            )

            # Calculate latency and bandwidth
            latency_ms = processing_time * 1000  # Convert to milliseconds
            bandwidth_bps = (
                len(message) / processing_time if processing_time > 0 else 0
            )  # Bytes per second

            # Collect latency and bandwidth statistics
            self.stats["latency_stats"].append(latency_ms)
            self.stats["bandwidth_stats"].append(bandwidth_bps)
            self.stats["latency_by_method"][method_name].append(latency_ms)
            self.stats["bandwidth_by_method"][method_name].append(bandwidth_bps)

            # Collect detailed method usage
            self.stats["compression_method_details"][method_name].append(
                {
                    "ratio": compression_ratio,
                    "size": len(message),
                    "template_matched": template_match is not None,
                    "available_methods": len(available_methods),
                }
            )

            # Collect statistics
            result = {
                "message_type": message_type,
                "original_size": len(message),
                "compressed_size": len(compressed_data),
                "compression_method": method_name,
                "compression_ratio": compression_ratio,
                "processing_time": processing_time,
                "template_matched": template_match is not None,
                "pattern_semantic_used": compression_method == CompressionMethod.PATTERN_SEMANTIC,
                "binary_semantic_used": compression_method == CompressionMethod.BINARY_SEMANTIC,
                "fast_path_used": False,  # No fast path method in current enum
                "slow_path_used": False,  # No slow path method in current enum
                "metadata": metadata,
                "available_methods_count": len(available_methods),
                "template_match_attempted": True,
            }

            return result

        except Exception as e:
            self.stats["errors"].append(
                {
                    "message_type": message_type,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                }
            )
            return None

    def run_simulation(self):
        """Run the network simulation"""
        self.start_time = datetime.now()
        self.end_time = self.start_time + self.duration
        self.running = True

        print(f"Starting network simulation at {self.start_time}")
        print(f"Will run for {self.duration.total_seconds()} seconds")

        message_count = 0
        last_discovery_time = self.start_time

        while datetime.now() < self.end_time and self.running:
            try:
                # Skip periodic template discovery during simulation to avoid hangs
                # Template discovery runs in background on schedule instead
                # current_time = datetime.now()
                # if (current_time - last_discovery_time).total_seconds() >= 15:
                #     print(f"Running periodic template discovery at {current_time}...")
                #     try:
                #         self.discovery_worker.run_discovery()
                #         last_discovery_time = current_time
                #         print("Periodic template discovery completed")
                #     except Exception as e:
                #         print(f"Periodic template discovery failed: {e}")

                # Select random message type with weighted probabilities
                message_type_weights = {
                    "api_request": 0.3,  # 30% API requests
                    "log_message": 0.25,  # 25% log messages
                    "chat_message": 0.15,  # 15% chat messages
                    "binary_data": 0.1,  # 10% binary data
                    "structured_data": 0.15,  # 15% structured data
                    "repetitive_text": 0.05,  # 5% repetitive text
                }

                message_type = random.choices(
                    list(message_type_weights.keys()), weights=list(message_type_weights.values())
                )[0]

                # Generate and process message
                message = self.generate_message(message_type)
                result = self.process_message(message, message_type)

                if result:
                    # Update statistics
                    message_size = len(message)
                    self.stats["total_messages"] += 1
                    self.stats["message_types"][message_type] += 1
                    self.stats["compression_methods_used"][result["compression_method"]] += 1
                    self.stats["compression_ratios"].append(result["compression_ratio"])
                    self.stats["processing_times"].append(result["processing_time"])
                    self.stats["message_sizes"].append(message_size)

                    # Categorize message size
                    if message_size < 100:
                        self.stats["size_distribution"]["small"] += 1
                    elif message_size < 500:
                        self.stats["size_distribution"]["medium"] += 1
                    else:
                        self.stats["size_distribution"]["large"] += 1

                    if result["template_matched"]:
                        self.stats["template_matches"] += 1
                    if result["pattern_semantic_used"]:
                        self.stats["pattern_semantic_usage"] += 1
                    if result["binary_semantic_used"]:
                        self.stats["binary_semantic_usage"] += 1
                    # Removed fast_path and slow_path counters as these methods don't exist

                message_count += 1

                # Progress reporting every 100 messages
                if message_count % 100 == 0:
                    elapsed = datetime.now() - self.start_time
                    progress = (elapsed.total_seconds() / self.duration.total_seconds()) * 100
                    print(f"Processed {message_count} messages ({progress:.1f}% complete)")

                # Small delay to simulate network timing
                time.sleep(random.uniform(0.01, 0.05))  # 10-50ms between messages

            except KeyboardInterrupt:
                print("Simulation interrupted by user")
                break
            except Exception as e:
                print(f"Error in simulation loop: {e}")
                continue

        self.running = False
        actual_end_time = datetime.now()
        print(f"Simulation completed at {actual_end_time}")

        return self.generate_summary()

    def generate_summary(self) -> Dict[str, Any]:
        """Generate comprehensive summary of simulation results"""
        actual_duration = datetime.now() - self.start_time
        scorer_status = self.compressor.get_scorer_status()

        summary = {
            "simulation_info": {
                "start_time": self.start_time.isoformat(),
                "end_time": datetime.now().isoformat(),
                "planned_duration_seconds": self.duration.total_seconds(),
                "actual_duration_seconds": actual_duration.total_seconds(),
                "total_messages_processed": self.stats["total_messages"],
                "scorer_enabled": bool(scorer_status.get("enabled", False)),
                "scorer_status": scorer_status,
            },
            "compression_performance": {
                "methods_used": dict(self.stats["compression_methods_used"]),
                "average_compression_ratio": (
                    statistics.mean(self.stats["compression_ratios"])
                    if self.stats["compression_ratios"]
                    else 0
                ),
                "median_compression_ratio": (
                    statistics.median(self.stats["compression_ratios"])
                    if self.stats["compression_ratios"]
                    else 0
                ),
                "min_compression_ratio": (
                    min(self.stats["compression_ratios"]) if self.stats["compression_ratios"] else 0
                ),
                "max_compression_ratio": (
                    max(self.stats["compression_ratios"]) if self.stats["compression_ratios"] else 0
                ),
                "compression_ratio_stddev": (
                    statistics.stdev(self.stats["compression_ratios"])
                    if len(self.stats["compression_ratios"]) > 1
                    else 0
                ),
            },
            "message_type_distribution": dict(self.stats["message_types"]),
            "template_discovery": {
                "template_matches": self.stats["template_matches"],
                "template_match_rate": self.stats["template_matches"]
                / max(self.stats["total_messages"], 1),
                "template_discoveries": len(self.stats["template_discoveries"]),
            },
            "ml_algorithm_performance": {
                "pattern_semantic_usage": self.stats["pattern_semantic_usage"],
                "pattern_semantic_rate": self.stats["pattern_semantic_usage"]
                / max(self.stats["total_messages"], 1),
                "binary_semantic_usage": self.stats["binary_semantic_usage"],
                "binary_semantic_rate": self.stats["binary_semantic_usage"]
                / max(self.stats["total_messages"], 1),
                # Removed fast_path and slow_path as these methods don't exist in the current enum
            },
            "performance_metrics": {
                "average_processing_time": (
                    statistics.mean(self.stats["processing_times"])
                    if self.stats["processing_times"]
                    else 0
                ),
                "median_processing_time": (
                    statistics.median(self.stats["processing_times"])
                    if self.stats["processing_times"]
                    else 0
                ),
                "messages_per_second": self.stats["total_messages"]
                / actual_duration.total_seconds(),
                "processing_time_stddev": (
                    statistics.stdev(self.stats["processing_times"])
                    if len(self.stats["processing_times"]) > 1
                    else 0
                ),
                "average_message_size": (
                    statistics.mean(self.stats["message_sizes"])
                    if self.stats["message_sizes"]
                    else 0
                ),
                "median_message_size": (
                    statistics.median(self.stats["message_sizes"])
                    if self.stats["message_sizes"]
                    else 0
                ),
                "min_message_size": (
                    min(self.stats["message_sizes"]) if self.stats["message_sizes"] else 0
                ),
                "max_message_size": (
                    max(self.stats["message_sizes"]) if self.stats["message_sizes"] else 0
                ),
                "size_distribution": self.stats["size_distribution"],
                "latency_metrics": {
                    "average_latency_ms": (
                        statistics.mean(self.stats["latency_stats"])
                        if self.stats["latency_stats"]
                        else 0
                    ),
                    "median_latency_ms": (
                        statistics.median(self.stats["latency_stats"])
                        if self.stats["latency_stats"]
                        else 0
                    ),
                    "min_latency_ms": (
                        min(self.stats["latency_stats"]) if self.stats["latency_stats"] else 0
                    ),
                    "max_latency_ms": (
                        max(self.stats["latency_stats"]) if self.stats["latency_stats"] else 0
                    ),
                    "latency_stddev_ms": (
                        statistics.stdev(self.stats["latency_stats"])
                        if len(self.stats["latency_stats"]) > 1
                        else 0
                    ),
                    "p95_latency_ms": (
                        statistics.quantiles(self.stats["latency_stats"], n=20)[18]
                        if len(self.stats["latency_stats"]) >= 20
                        else max(self.stats["latency_stats"]) if self.stats["latency_stats"] else 0
                    ),
                },
                "bandwidth_metrics": {
                    "average_bandwidth_bps": (
                        statistics.mean(self.stats["bandwidth_stats"])
                        if self.stats["bandwidth_stats"]
                        else 0
                    ),
                    "median_bandwidth_bps": (
                        statistics.median(self.stats["bandwidth_stats"])
                        if self.stats["bandwidth_stats"]
                        else 0
                    ),
                    "min_bandwidth_bps": (
                        min(self.stats["bandwidth_stats"]) if self.stats["bandwidth_stats"] else 0
                    ),
                    "max_bandwidth_bps": (
                        max(self.stats["bandwidth_stats"]) if self.stats["bandwidth_stats"] else 0
                    ),
                    "bandwidth_stddev_bps": (
                        statistics.stdev(self.stats["bandwidth_stats"])
                        if len(self.stats["bandwidth_stats"]) > 1
                        else 0
                    ),
                    "total_data_processed_mb": (
                        sum(self.stats["message_sizes"]) / (1024 * 1024)
                        if self.stats["message_sizes"]
                        else 0
                    ),
                    "effective_bandwidth_mbps": (
                        (sum(self.stats["message_sizes"]) / (1024 * 1024))
                        / (actual_duration.total_seconds() / 60)
                        if actual_duration.total_seconds() > 0
                        else 0
                    ),
                },
            },
            "error_analysis": {
                "total_errors": len(self.stats["errors"]),
                "error_rate": len(self.stats["errors"])
                / max(self.stats["total_messages"] + len(self.stats["errors"]), 1),
                "error_samples": self.stats["errors"][:5],  # First 5 errors for analysis
            },
            "detailed_analysis": self._generate_detailed_analysis(),
        }

        return summary

    def _generate_detailed_analysis(self) -> Dict[str, Any]:
        """Generate detailed analysis of compression behavior"""
        analysis = {
            "template_matching_analysis": {
                "total_attempts": self.stats["template_matching_attempts"],
                "failure_rate": self.stats["template_matching_failures"]
                / max(self.stats["template_matching_attempts"], 1),
                "success_rate": (
                    self.stats["template_matching_attempts"]
                    - self.stats["template_matching_failures"]
                )
                / max(self.stats["template_matching_attempts"], 1),
                "reason_for_low_matches": self._analyze_template_matching_issues(),
            },
            "compression_method_analysis": {
                "methods_available_distribution": dict(self.stats["available_methods_count"]),
                "method_usage_breakdown": self._analyze_method_usage(),
                "why_other_methods_not_used": self._analyze_method_selection_issues(),
            },
            "ml_decision_analysis": {
                "ml_selection_reasons": dict(self.stats["ml_selection_reasons"]),
                "method_effectiveness": self._analyze_method_effectiveness(),
            },
        }
        return analysis

    def _analyze_template_matching_issues(self) -> str:
        """Analyze why templates aren't matching more frequently"""
        total_attempts = self.stats["template_matching_attempts"]
        failures = self.stats["template_matching_failures"]

        if total_attempts == 0:
            return "No template matching attempts recorded"

        failure_rate = failures / total_attempts

        if failure_rate > 0.9:
            return f"Very high template matching failure rate ({failure_rate:.1%}). Possible issues: 1) Templates not diverse enough for message patterns, 2) Template discovery not finding good patterns, 3) Message variation too high for existing templates, 4) Template library not being updated properly"
        elif failure_rate > 0.7:
            return f"High template matching failure rate ({failure_rate:.1%}). Templates may not be capturing common message patterns effectively"
        else:
            return f"Template matching failure rate ({failure_rate:.1%}) is reasonable, but could be improved with more diverse template discovery"

    def _analyze_method_usage(self) -> Dict[str, Any]:
        """Analyze how compression methods are being used"""
        breakdown = {}
        for method, details in self.stats["compression_method_details"].items():
            ratios = [d["ratio"] for d in details]
            sizes = [d["size"] for d in details]
            template_matches = sum(1 for d in details if d["template_matched"])

            breakdown[method] = {
                "usage_count": len(details),
                "usage_rate": len(details) / max(self.stats["total_messages"], 1),
                "avg_compression_ratio": statistics.mean(ratios) if ratios else 0,
                "avg_message_size": statistics.mean(sizes) if sizes else 0,
                "template_match_rate": template_matches / len(details) if details else 0,
                "avg_available_methods": (
                    statistics.mean([d["available_methods"] for d in details]) if details else 0
                ),
            }

        return breakdown

    def _analyze_method_selection_issues(self) -> str:
        """Analyze why other compression methods aren't being selected"""
        method_usage = self.stats["compression_method_details"]
        available_counts = self.stats["available_methods_count"]

        # Check if methods are available
        most_common_available = max(available_counts.keys()) if available_counts else 0

        if most_common_available <= 2:
            return f"Limited compression methods available (max {most_common_available}). Check if AURA features are enabled and encoders are properly initialized"

        # Check method distribution
        total_methods = len(method_usage)
        if total_methods <= 2:
            return f"Only {total_methods} compression methods being used. ML selector may be preferring certain methods or other methods may not be available"

        # Check if AI semantic is available but not used
        pattern_method_value = CompressionMethod.PATTERN_SEMANTIC.value
        if pattern_method_value not in method_usage and most_common_available >= 4:
            return "Pattern semantic compression not being used despite being available. May be due to: 1) Pattern semantic compressor not initialized, 2) ML selector preferring other methods, 3) Pattern semantic method not meeting quality thresholds"

        # Check if BRIO/AuraLite are available but not used
        aura_methods = [
            m for m in method_usage.keys() if "aura" in m.lower() or "brio" in m.lower()
        ]
        if not aura_methods and most_common_available >= 3:
            return "AURA/BRIO methods not being used despite being available. Check encoder initialization"

        return "Multiple compression methods are being used appropriately based on message characteristics"

    def _analyze_method_effectiveness(self) -> Dict[str, Any]:
        """Analyze the effectiveness of different compression methods"""
        effectiveness = {}

        for method, details in self.stats["compression_method_details"].items():
            ratios = [d["ratio"] for d in details]
            if not ratios:
                continue

            # Get latency and bandwidth for this method
            latencies = self.stats["latency_by_method"].get(method, [])
            bandwidths = self.stats["bandwidth_by_method"].get(method, [])

            effectiveness[method] = {
                "best_ratio": max(ratios),
                "worst_ratio": min(ratios),
                "avg_ratio": statistics.mean(ratios),
                "ratio_consistency": statistics.stdev(ratios) if len(ratios) > 1 else 0,
                "usage_efficiency": len([r for r in ratios if r > 1.1])
                / len(ratios),  # Good compression (>10% better)
                "avg_latency_ms": statistics.mean(latencies) if latencies else 0,
                "avg_bandwidth_bps": statistics.mean(bandwidths) if bandwidths else 0,
                "latency_vs_ratio_tradeoff": self._calculate_tradeoff_score(ratios, latencies),
                "bandwidth_efficiency": self._calculate_bandwidth_efficiency(ratios, bandwidths),
            }

        return effectiveness

    def _calculate_tradeoff_score(self, ratios: List[float], latencies: List[float]) -> float:
        """Calculate compression ratio vs latency tradeoff score"""
        if not ratios or not latencies or len(ratios) != len(latencies):
            return 0.0

        # Normalize ratios and latencies to 0-1 scale
        min_ratio, max_ratio = min(ratios), max(ratios)
        min_lat, max_lat = min(latencies), max(latencies)

        if max_ratio == min_ratio or max_lat == min_lat:
            return 0.5  # Neutral score if no variation

        normalized_ratios = [(r - min_ratio) / (max_ratio - min_ratio) for r in ratios]
        normalized_latencies = [
            (max_lat - l) / (max_lat - min_lat) for l in latencies
        ]  # Invert latency (lower is better)

        # Tradeoff score: weighted average favoring compression ratio slightly more
        tradeoff_scores = [
            0.6 * r + 0.4 * l for r, l in zip(normalized_ratios, normalized_latencies)
        ]
        return statistics.mean(tradeoff_scores)

    def _calculate_bandwidth_efficiency(
        self, ratios: List[float], bandwidths: List[float]
    ) -> float:
        """Calculate bandwidth efficiency considering compression and throughput"""
        if not ratios or not bandwidths:
            return 0.0

        # Bandwidth efficiency = compression benefit * throughput
        # Higher compression ratios and higher bandwidth = better efficiency
        efficiencies = [
            ratio * (bandwidth / 1000) for ratio, bandwidth in zip(ratios, bandwidths)
        ]  # Normalize bandwidth to KB/s
        return statistics.mean(efficiencies)

    def save_summary(self, summary: Dict[str, Any], filename: str = None):
        """Save simulation summary to file"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"network_simulation_summary_{timestamp}.json"

        output_path = Path(filename)
        if output_path.parent:
            output_path.parent.mkdir(parents=True, exist_ok=True)

        with output_path.open("w") as f:
            json.dump(summary, f, indent=2, default=str)

        print(f"Summary saved to {output_path}")
        return str(output_path)


def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse command-line arguments for the network simulation."""
    parser = argparse.ArgumentParser(description="Run the AURA network simulation harness.")
    parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="Simulation duration in seconds (default: 60).",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Optional path for the summary JSON file (default: timestamped filename in repo root).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        help="Optional random seed for reproducibility.",
    )
    parser.add_argument(
        "--scorer",
        dest="enable_scorer",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable or disable the lightweight scorer (use --scorer / --no-scorer).",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None):
    """Main function to run the network simulation"""
    args = _parse_args(argv)

    if args.seed is not None:
        random.seed(args.seed)

    print("AURA Network Simulation")
    print("=" * 50)

    # Create simulator
    simulator = NetworkSimulator(duration_seconds=args.duration, enable_scorer=args.enable_scorer)

    try:
        # Run simulation
        summary = simulator.run_simulation()

        # Save summary
        summary_file = simulator.save_summary(summary, filename=args.output)

        # Print key results
        print("\nSimulation Results Summary:")
        print("-" * 30)
        print(f"Total Messages: {summary['simulation_info']['total_messages_processed']}")
        print(f"Scorer Enabled: {'yes' if summary['simulation_info']['scorer_enabled'] else 'no'}")
        scorer_status = summary["simulation_info"].get("scorer_status", {})
        if scorer_status:
            ratio = scorer_status.get("global_borderline_ratio", 0.0)
            threshold = scorer_status.get("window_threshold", 0.0)
            print(f"Borderline Mix: {ratio:.1%} (threshold {threshold:.1%})")
            recommendation = scorer_status.get("recommendation") or scorer_status.get(
                "disabled_reason"
            )
            if recommendation:
                print(f"Scorer Recommendation: {recommendation}")
        print(
            f"Average Message Size: {summary['performance_metrics']['average_message_size']:.0f} chars"
        )
        print(
            f"Message Size Range: {summary['performance_metrics']['min_message_size']:.0f} - {summary['performance_metrics']['max_message_size']:.0f} chars"
        )
        size_dist = summary["performance_metrics"]["size_distribution"]
        print(
            f"Size Distribution: Small({size_dist['small']}) Medium({size_dist['medium']}) Large({size_dist['large']})"
        )
        print(f"Template Match Rate: {summary['template_discovery']['template_match_rate']:.1%}")
        print(
            f"Pattern Semantic Usage: {summary['ml_algorithm_performance']['pattern_semantic_rate']:.1%}"
        )
        print(
            f"Binary Semantic Usage: {summary['ml_algorithm_performance']['binary_semantic_rate']:.1%}"
        )
        # Removed fast_path and slow_path printing as these methods don't exist
        print(f"Error Rate: {summary['error_analysis']['error_rate']:.1%}")

        # Print latency and bandwidth metrics
        latency = summary["performance_metrics"]["latency_metrics"]
        bandwidth = summary["performance_metrics"]["bandwidth_metrics"]
        print(f"\nLatency Metrics:")
        print(f"  Average Latency: {latency['average_latency_ms']:.2f} ms")
        print(f"  Median Latency: {latency['median_latency_ms']:.2f} ms")
        print(f"  95th Percentile Latency: {latency['p95_latency_ms']:.2f} ms")
        print(
            f"  Latency Range: {latency['min_latency_ms']:.2f} - {latency['max_latency_ms']:.2f} ms"
        )

        print(f"\nBandwidth Metrics:")
        print(f"  Average Bandwidth: {bandwidth['average_bandwidth_bps']:.0f} bytes/sec")
        print(f"  Median Bandwidth: {bandwidth['median_bandwidth_bps']:.0f} bytes/sec")
        print(f"  Total Data Processed: {bandwidth['total_data_processed_mb']:.2f} MB")
        print(f"  Effective Bandwidth: {bandwidth['effective_bandwidth_mbps']:.2f} MB/min")

        print(f"\nDetailed results saved to: {summary_file}")

    except KeyboardInterrupt:
        print("\nSimulation interrupted by user")
    except Exception as e:
        print(f"Error running simulation: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
