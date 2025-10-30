#!/usr/bin/env python3
"""
AURA Compression Training Data Generator
Generates sample datasets and configuration files to help users bootstrap compression.

This script creates realistic training data across multiple domains to help users
achieve the claimed 1.45:1 compression ratios and understand when they are realistic.
"""

import json
import random
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any
import os
import re
import argparse


class TrainingDataGenerator:
    """Generates training data for AURA compression bootstrap."""

    def __init__(self, seed: int = 42, template_store_path: str = './data/templates/template_store_expanded.json'):
        random.seed(seed)
        self.template_store_path = template_store_path
        self.templates = self._load_existing_templates()

    def _generate_log_templates(self) -> List[str]:
        """Generate realistic log message templates."""
        return [
            "User {username} logged in from {ip_address} at {timestamp}",
            "Failed login attempt for user {username} from {ip_address}",
            "Database query executed in {duration}ms: {query_type} on {table_name}",
            "API request {method} {endpoint} completed with status {status_code} in {duration}ms",
            "File {filename} uploaded successfully ({size} bytes) by user {username}",
            "System alert: {component} {severity} - {message}",
            "Cache miss for key {cache_key} in region {region}",
            "Payment processed: ${amount} for order {order_id}",
            "Email sent to {recipient} with subject '{subject}'",
            "Background job {job_id} completed in {duration}ms with status {status}",
            "Security event: {event_type} detected from {source_ip}",
            "Performance metric: {metric_name} = {value} for service {service_name}",
            "Error in {component}: {error_message} (code: {error_code})",
            "Configuration updated: {config_key} = {config_value} by {user}",
            "Network connection established to {destination} on port {port}",
            "Disk usage warning: {mount_point} at {usage_percent}% capacity",
            "Memory usage alert: {process_name} using {memory_mb}MB",
            "SSL certificate for {domain} expires in {days_remaining} days",
            "Backup completed: {backup_name} ({size_gb}GB) in {duration} minutes",
            "Load balancer health check failed for instance {instance_id}",
        ]

    def _generate_api_templates(self) -> List[str]:
        """Generate API response templates."""
        return [
            '{"status": "success", "data": {data}, "timestamp": "{timestamp}"}',
            '{"error": "{error_message}", "code": {error_code}, "timestamp": "{timestamp}"}',
            '{"user_id": "{user_id}", "action": "{action}", "resource": "{resource}", "timestamp": "{timestamp}"}',
            '{"order_id": "{order_id}", "status": "{status}", "total": {total}, "items": {item_count}}',
            '{"metric": "{metric_name}", "value": {value}, "tags": {tags}, "timestamp": "{timestamp}"}',
            '{"notification": "{message}", "type": "{notification_type}", "user_id": "{user_id}"}',
            '{"session_id": "{session_id}", "user_agent": "{user_agent}", "ip": "{ip_address}"}',
            '{"product_id": "{product_id}", "name": "{product_name}", "price": {price}, "category": "{category}"}',
            '{"transaction_id": "{transaction_id}", "amount": {amount}, "currency": "{currency}", "status": "{status}"}',
            '{"log_id": "{log_id}", "level": "{level}", "message": "{message}", "component": "{component}"}',
        ]

    def _generate_metrics_templates(self) -> List[str]:
        """Generate metrics and monitoring templates."""
        return [
            "cpu_usage_percent{service=\"{service}\",host=\"{host}\"} {value} {timestamp}",
            "memory_bytes{service=\"{service}\",host=\"{host}\"} {value} {timestamp}",
            "request_duration_seconds{method=\"{method}\",endpoint=\"{endpoint}\"} {value} {timestamp}",
            "error_rate{service=\"{service}\",error_type=\"{error_type}\"} {value} {timestamp}",
            "queue_length{service=\"{service}\",queue_name=\"{queue}\"} {value} {timestamp}",
            "disk_usage_bytes{mount=\"{mount}\",host=\"{host}\"} {value} {timestamp}",
            "network_bytes_total{interface=\"{interface}\",direction=\"{direction}\"} {value} {timestamp}",
            "active_connections{service=\"{service}\",port=\"{port}\"} {value} {timestamp}",
            "response_size_bytes{method=\"{method}\",endpoint=\"{endpoint}\"} {value} {timestamp}",
            "cache_hit_ratio{service=\"{service}\",cache_type=\"{cache}\"} {value} {timestamp}",
        ]

    def _generate_event_templates(self) -> List[str]:
        """Generate event-driven message templates."""
        return [
            "Event: {event_type} triggered by {actor} at {timestamp}",
            "Webhook received from {source} with payload size {size} bytes",
            "Message queued in {queue_name} with priority {priority}",
            "Alert: {alert_name} fired with severity {severity}",
            "Task {task_id} scheduled for execution at {scheduled_time}",
            "Callback completed for request {request_id} with result {result}",
            "Subscription {subscription_id} renewed for user {user_id}",
            "Notification sent via {channel} to {recipient_count} recipients",
            "Workflow {workflow_id} transitioned to state {new_state}",
            "Integration sync completed: {records_processed} records in {duration}ms",
        ]

    def _generate_message_templates(self) -> List[str]:
        """Generate general message templates."""
        return [
            "Hello {name}, welcome to {service}!",
            "Your order #{order_id} has been {status}",
            "Password reset requested for account {email}",
            "Verification code: {code} (expires in {minutes} minutes)",
            "Thank you for your payment of ${amount}",
            "Your account balance is now ${balance}",
            "New message from {sender}: {preview}",
            "File {filename} is ready for download",
            "Your appointment is confirmed for {date} at {time}",
            "Security alert: unusual activity detected on {device}",
        ]

    def _load_existing_templates(self) -> Dict[str, List[str]]:
        """Load templates from the expanded template store."""
        try:
            with open(self.template_store_path, 'r') as f:
                data = json.load(f)

            templates_by_category = {}
            for template_id, template_data in data.get('templates', {}).items():
                category = template_data.get('category', 'general')
                pattern = template_data.get('pattern', '')

                if category not in templates_by_category:
                    templates_by_category[category] = []

                templates_by_category[category].append(pattern)

            # Group categories for generation
            grouped_templates = {
                'logs': [],
                'api': [],
                'metrics': [],
                'events': [],
                'messages': []
            }

            for category, patterns in templates_by_category.items():
                cat_lower = category.lower()
                if 'log' in cat_lower or 'error' in cat_lower or 'status' in cat_lower:
                    grouped_templates['logs'].extend(patterns)
                elif 'api' in cat_lower or 'response' in cat_lower or 'auth' in cat_lower:
                    grouped_templates['api'].extend(patterns)
                elif 'metric' in cat_lower or 'analytics' in cat_lower or 'monitoring' in cat_lower:
                    grouped_templates['metrics'].extend(patterns)
                elif 'event' in cat_lower or 'network' in cat_lower or 'communication' in cat_lower:
                    grouped_templates['events'].extend(patterns)
                else:
                    grouped_templates['messages'].extend(patterns)

            # Ensure each category has some templates
            for category in grouped_templates:
                if not grouped_templates[category]:
                    grouped_templates[category] = getattr(self, f'_generate_{category}_templates')()

            return grouped_templates

        except Exception as e:
            print(f"Failed to load templates from {self.template_store_path}: {e}")
            # Fallback to generated templates
            return {
                'logs': self._generate_log_templates(),
                'api': self._generate_api_templates(),
                'metrics': self._generate_metrics_templates(),
                'events': self._generate_event_templates(),
                'messages': self._generate_message_templates(),
            }

    def _generate_random_value_for_slot(self, category: str, slot_index: int) -> str:
        """Generate appropriate random values for template slots based on category."""
        generators = {
            'logs': [
                lambda: random.choice(['john.doe', 'jane.smith', 'admin', 'user123', 'alice']),
                lambda: str(random.randint(10, 5000)),  # duration
                lambda: random.choice(['192.168.1.100', '10.0.0.1', '172.16.0.1']),
                lambda: random.choice(['GET', 'POST', 'PUT', 'DELETE']),
                lambda: random.choice(['/api/users', '/api/orders', '/health']),
                lambda: str(random.choice([200, 201, 400, 404, 500])),
            ],
            'api': [
                lambda: random.choice(['john.doe', 'jane.smith', 'admin']),
                lambda: str(random.randint(50, 2000)),  # duration
                lambda: str(random.randint(1, 1000)),  # count
                lambda: f"key_{random.randint(1,1000)}",
                lambda: str(random.randint(10, 100)),  # limit
                lambda: str(random.randint(100, 1000)),  # per hour
            ],
            'metrics': [
                lambda: random.choice(['web', 'api', 'db', 'cache']),
                lambda: random.choice(['us-east-1', 'us-west-2']),
                lambda: f"{random.uniform(0, 100):.2f}",
                lambda: str(random.randint(1000000000, 2000000000)),  # timestamp
            ],
            'events': [
                lambda: random.choice(['login', 'logout', 'purchase', 'signup']),
                lambda: random.choice(['john.doe', 'jane.smith']),
                lambda: random.choice(['success', 'failed', 'pending']),
            ],
            'messages': [
                lambda: random.choice(['john.doe', 'jane.smith', 'alice']),
                lambda: random.choice(['Welcome', 'Order confirmed', 'Password reset']),
                lambda: f"msg_{random.randint(1,1000)}",
            ]
        }

        category_generators = generators.get(category, generators['messages'])
        generator_index = slot_index % len(category_generators)
        return category_generators[generator_index]()

    def _replace_special_placeholders(self, message: str) -> str:
        """Replace special placeholders like __TIMESTAMP_0__, __UUID_0__, __TIME_0_MS__."""
        replacements = {
            '__TIMESTAMP_0__': lambda: datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            '__UUID_0__': lambda: str(uuid.uuid4())[:8],
            '__TIME_0_MS__': lambda: str(random.randint(10, 5000)),
            '__TIME_1_MS__': lambda: str(random.randint(10, 5000)),
        }

        for placeholder, generator in replacements.items():
            if placeholder in message:
                message = message.replace(placeholder, generator())

        return message

    def generate_sample_messages(self, category: str, count: int = 100) -> List[str]:
        """Generate sample messages for a specific category using actual templates."""
        if category not in self.templates:
            raise ValueError(f"Unknown category: {category}")

        messages = []
        templates = self.templates[category]

        if not templates:
            # Fallback if no templates for category
            return [f"Sample {category} message {i}" for i in range(count)]

        for _ in range(count):
            template = random.choice(templates)

            # Replace placeholders like {0}, {1}, etc. with random values
            message = template

            # Handle different placeholder formats
            if '{0}' in message or '{1}' in message:
                # Standard {0}, {1}, etc. format
                slot_count = max([int(match.group(1)) for match in re.finditer(r'\{(\d+)\}', message)] + [0]) + 1
                for i in range(slot_count):
                    placeholder = f"{{{i}}}"
                    if placeholder in message:
                        value = self._generate_random_value_for_slot(category, i)
                        message = message.replace(placeholder, str(value))
            elif '__' in message:
                # Handle __PLACEHOLDER__ format
                message = self._replace_special_placeholders(message)
            # If no placeholders, use template as-is

            messages.append(message)

        return messages

    def generate_training_dataset(self, categories: List[str] = None, messages_per_category: int = 500) -> Dict[str, Any]:
        """Generate a complete training dataset."""
        if categories is None:
            categories = list(self.templates.keys())

        dataset = {
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'generator_version': '1.0',
                'categories': categories,
                'messages_per_category': messages_per_category,
                'total_messages': len(categories) * messages_per_category,
                'description': 'Training dataset for AURA compression system bootstrap'
            },
            'categories': {}
        }

        for category in categories:
            messages = self.generate_sample_messages(category, messages_per_category)
            dataset['categories'][category] = {
                'message_count': len(messages),
                'sample_messages': messages[:10],  # Include first 10 as samples
                'all_messages': messages
            }

        return dataset

    def save_training_data(self, dataset: Dict[str, Any], output_dir: str = './training_data'):
        """Save training dataset to files."""
        os.makedirs(output_dir, exist_ok=True)

        # Save metadata
        with open(f"{output_dir}/metadata.json", 'w') as f:
            json.dump(dataset['metadata'], f, indent=2)

        # Save each category as separate file
        for category, data in dataset['categories'].items():
            category_data = {
                'category': category,
                'message_count': data['message_count'],
                'messages': data['all_messages']
            }
            with open(f"{output_dir}/{category}_training.json", 'w') as f:
                json.dump(category_data, f, indent=2)

        # Save combined dataset
        with open(f"{output_dir}/combined_training.json", 'w') as f:
            json.dump(dataset, f, indent=2)

        print(f"Training data saved to {output_dir}")
        print(f"Total messages: {dataset['metadata']['total_messages']}")
        print(f"Categories: {', '.join(dataset['metadata']['categories'])}")


def create_bootstrap_config(training_data_dir: str = './training_data') -> Dict[str, Any]:
    """Create a bootstrap configuration for AURA compression."""
    config = {
        'aura_compression': {
            'version': '2.0',
            'bootstrap_mode': True,
            'training_data_path': training_data_dir,
            'aggressive_mode': {
                'large_file_threshold': 512,  # More aggressive
                'very_large_threshold': 50000,  # More aggressive
                'binary_advantage_threshold': 1.05,  # 5% better is enough
                'tcp_brio_threshold': 1000,  # More messages use TCP-optimized BRIO
                'min_compression_size': 20,
            },
            'fuzzy_matching': {
                'enabled': True,
                'min_similarity': 0.85,
                'max_distance': 30,
            },
            'template_discovery': {
                'enabled': True,
                'min_frequency': 3,
                'max_templates': 1000,
            },
            'hardware_acceleration': {
                'enable_simd': True,
                'enable_gpu': True,
                'enable_hardware_optimized': True,
            },
        },
        'expected_performance': {
            'compression_ratios': {
                'logs': '1.8:1 to 3.2:1',
                'api_responses': '2.1:1 to 4.5:1',
                'metrics': '3.5:1 to 8.2:1',
                'events': '1.6:1 to 2.8:1',
                'messages': '1.4:1 to 2.5:1',
                'mixed_workload': '1.45:1 to 3.8:1',
            },
            'when_145_ratios_achievable': [
                'High template similarity (>80% of messages match known patterns)',
                'Structured data (JSON, logs, metrics)',
                'Repetitive content with minor variations',
                'Large message volumes for template learning',
                'Proper template library coverage',
            ],
            'factors_affecting_ratios': [
                'Template library size and coverage',
                'Message structure and predictability',
                'Data entropy and randomness',
                'Template matching accuracy',
                'Fuzzy matching effectiveness',
                'Hardware acceleration utilization',
            ],
        },
        'usage_examples': {
            'high_compression_scenario': {
                'description': 'System logs with structured format',
                'sample_message': 'User john.doe logged in from 192.168.1.100 at 2023-10-29T14:30:25Z',
                'expected_ratio': '3.2:1',
                'reason': 'High template similarity, structured timestamps and IPs',
            },
            'moderate_compression_scenario': {
                'description': 'API responses with variable data',
                'sample_message': '{"status": "success", "data": {"user_id": "12345", "balance": 99.50}, "timestamp": "2023-10-29T14:30:25Z"}',
                'expected_ratio': '2.1:1',
                'reason': 'Structured JSON with variable numeric/string content',
            },
            'low_compression_scenario': {
                'description': 'Random or highly entropic data',
                'sample_message': 'Random text with no patterns: abcdefghijklmnopqrstuvwxyz0123456789',
                'expected_ratio': '1.05:1',
                'reason': 'High entropy, no template matches, minimal compression possible',
            },
        },
    }

    return config


def main():
    """Main function to generate training data and bootstrap config."""
    parser = argparse.ArgumentParser(description='Generate AURA compression training data')
    parser.add_argument('--output-dir', default='./training_data', help='Output directory for training data')
    parser.add_argument('--messages-per-category', type=int, default=500, help='Number of messages per category')
    parser.add_argument('--categories', nargs='+', help='Categories to generate (default: all)')
    parser.add_argument('--seed', type=int, default=42, help='Random seed for reproducibility')

    args = parser.parse_args()

    # Generate training data
    generator = TrainingDataGenerator(seed=args.seed)
    dataset = generator.generate_training_dataset(
        categories=args.categories,
        messages_per_category=args.messages_per_category
    )

    # Save training data
    generator.save_training_data(dataset, args.output_dir)

    # Create and save bootstrap config
    config = create_bootstrap_config(args.output_dir)
    config_path = f"{args.output_dir}/bootstrap_config.json"
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)

    print(f"Bootstrap configuration saved to {config_path}")
    print("\nTo use this training data with AURA compression:")
    print("1. Load the bootstrap_config.json")
    print("2. Use the training data to populate your template library")
    print("3. Enable aggressive compression settings")
    print("4. Monitor compression ratios and adjust thresholds as needed")


if __name__ == "__main__":
    main()