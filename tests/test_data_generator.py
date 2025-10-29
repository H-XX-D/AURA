#!/usr/bin/env python3
"""
Test Data Generators for AURA Compression Testing
================================================

Generators for various types of test data to ensure comprehensive testing.
"""

import random
import json
import string
import os
from typing import List, Dict, Any
from datetime import datetime, timedelta


class TestDataGenerator:
    """Comprehensive test data generator for AURA compression testing."""

    @staticmethod
    def generate_api_responses(count: int = 100) -> List[str]:
        """Generate realistic API response data."""
        responses = []

        for i in range(count):
            response = {
                "status": "success",
                "timestamp": datetime.now().isoformat(),
                "request_id": f"req_{i:06d}",
                "data": {
                    "user": {
                        "id": i,
                        "name": f"User_{i}",
                        "email": f"user{i}@example.com",
                        "created_at": (datetime.now() - timedelta(days=random.randint(1, 365))).isoformat()
                    },
                    "posts": [
                        {
                            "id": j,
                            "title": f"Post {j} by User {i}",
                            "content": f"This is the content of post {j}. " * random.randint(1, 5),
                            "likes": random.randint(0, 1000),
                            "created_at": (datetime.now() - timedelta(hours=random.randint(1, 24))).isoformat()
                        } for j in range(random.randint(1, 10))
                    ]
                }
            }
            responses.append(json.dumps(response))

        return responses

    @staticmethod
    def generate_log_entries(count: int = 100) -> List[str]:
        """Generate realistic log entries."""
        log_levels = ['DEBUG', 'INFO', 'WARN', 'ERROR']
        components = ['auth', 'api', 'db', 'cache', 'worker']
        messages = [
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

        logs = []
        base_time = datetime.now()

        for i in range(count):
            timestamp = base_time - timedelta(seconds=i*10)
            level = random.choice(log_levels)
            component = random.choice(components)
            message = random.choice(messages)

            if 'User' in message:
                message += f": user_id={random.randint(1000, 9999)}"
            elif 'Database' in message:
                message += f": table=users, duration={random.randint(1, 100)}ms"
            elif 'Cache' in message:
                message += f": key=user:{random.randint(1000, 9999)}"
            elif 'API' in message:
                message += f": method={random.choice(['GET', 'POST', 'PUT', 'DELETE'])}, status={random.choice([200, 201, 400, 404, 500])}"

            log_entry = f"{timestamp.strftime('%Y-%m-%d %H:%M:%S')} {level} [{component}] {message}"
            logs.append(log_entry)

        return logs

    @staticmethod
    def generate_chat_messages(count: int = 100) -> List[str]:
        """Generate realistic chat messages."""
        users = [f"User_{i}" for i in range(20)]
        message_templates = [
            "Hello everyone!",
            "How is everyone doing today?",
            "Thanks for the help!",
            "I need assistance with this issue",
            "The documentation is very helpful",
            "When will the new feature be released?",
            "I found a bug in the system",
            "Can someone explain this to me?",
            "Great work on the latest update!",
            "I'm having trouble with the login",
            "The performance has improved significantly",
            "Can we schedule a meeting to discuss this?",
            "I appreciate all the hard work",
            "This feature is exactly what I needed",
            "The user interface is very intuitive"
        ]

        messages = []
        for i in range(count):
            user = random.choice(users)
            template = random.choice(message_templates)

            # Add some variation
            if random.random() < 0.3:
                template += " " + "".join(random.choices(string.ascii_lowercase, k=random.randint(5, 20)))

            message = {
                "type": "chat",
                "timestamp": datetime.now().isoformat(),
                "user": user,
                "message": template,
                "message_id": f"msg_{i:06d}"
            }
            messages.append(json.dumps(message))

        return messages

    @staticmethod
    def generate_structured_data(count: int = 100) -> List[str]:
        """Generate structured data that should compress well."""
        data = []

        for i in range(count):
            record = {
                "id": i,
                "type": "structured_record",
                "metadata": {
                    "version": "1.0",
                    "created_by": "test_generator",
                    "tags": ["test", "structured", "compression"]
                },
                "content": {
                    "field1": f"value_{i}",
                    "field2": i * 10,
                    "field3": f"description for record {i}",
                    "field4": {
                        "nested_field": f"nested_value_{i}",
                        "array_field": list(range(i % 10 + 1))
                    }
                },
                "timestamps": {
                    "created": datetime.now().isoformat(),
                    "modified": datetime.now().isoformat(),
                    "expires": (datetime.now() + timedelta(days=30)).isoformat()
                }
            }
            data.append(json.dumps(record))

        return data

    @staticmethod
    def generate_random_text(count: int = 100, avg_length: int = 200) -> List[str]:
        """Generate random text data."""
        texts = []

        for _ in range(count):
            length = int(random.gauss(avg_length, avg_length * 0.2))
            length = max(10, min(length, avg_length * 2))

            words = []
            for _ in range(length // 5):  # Approximate words
                word_length = random.randint(3, 10)
                word = "".join(random.choices(string.ascii_lowercase, k=word_length))
                words.append(word)

            text = " ".join(words)
            texts.append(text)

        return texts

    @staticmethod
    def generate_compression_test_suite() -> Dict[str, List[str]]:
        """Generate a comprehensive test suite with various data types."""
        return {
            "api_responses": TestDataGenerator.generate_api_responses(50),
            "log_entries": TestDataGenerator.generate_log_entries(50),
            "chat_messages": TestDataGenerator.generate_chat_messages(50),
            "structured_data": TestDataGenerator.generate_structured_data(50),
            "random_text": TestDataGenerator.generate_random_text(50),
            "small_messages": ["Hi", "OK", "Yes", "No", "Thanks"] * 10,
            "large_messages": ["A" * 10000, "B" * 10000, "C" * 10000],
        }


class PerformanceBaseline:
    """Performance baseline tracking for regression detection."""

    def __init__(self, baseline_file: str = "performance_baseline.json"):
        self.baseline_file = baseline_file
        self.baselines = self._load_baselines()

    def _load_baselines(self) -> Dict[str, Any]:
        """Load existing performance baselines."""
        if os.path.exists(self.baseline_file):
            try:
                with open(self.baseline_file, 'r') as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_baselines(self):
        """Save current baselines."""
        with open(self.baseline_file, 'w') as f:
            json.dump(self.baselines, f, indent=2)

    def update_baseline(self, test_name: str, metric: str, value: float, threshold: float = 0.1):
        """Update baseline for a test metric."""
        key = f"{test_name}_{metric}"
        if key not in self.baselines:
            self.baselines[key] = {"value": value, "threshold": threshold, "updated": datetime.now().isoformat()}
        else:
            # Update if significantly different
            current_value = self.baselines[key]["value"]
            if abs(value - current_value) / current_value > threshold:
                self.baselines[key]["value"] = value
                self.baselines[key]["updated"] = datetime.now().isoformat()

        self._save_baselines()

    def check_regression(self, test_name: str, metric: str, value: float) -> Dict[str, Any]:
        """Check if current value indicates performance regression."""
        key = f"{test_name}_{metric}"

        if key not in self.baselines:
            return {"status": "no_baseline", "message": "No baseline established yet"}

        baseline_value = self.baselines[key]["value"]
        threshold = self.baselines[key]["threshold"]

        deviation = abs(value - baseline_value) / baseline_value

        if deviation > threshold:
            direction = "slower" if value > baseline_value else "faster"
            return {
                "status": "regression" if value > baseline_value else "improvement",
                "message": f"Performance {direction} by {deviation:.1%}",
                "baseline": baseline_value,
                "current": value,
                "deviation": deviation
            }
        else:
            return {"status": "normal", "deviation": deviation}


# Example usage and test
if __name__ == "__main__":
    # Generate test data
    test_suite = TestDataGenerator.generate_compression_test_suite()

    print("Generated test data:")
    for data_type, data in test_suite.items():
        print(f"  {data_type}: {len(data)} samples, avg length: {sum(len(s) for s in data) // len(data)} chars")

    # Example performance baseline usage
    baseline = PerformanceBaseline()

    # Simulate performance check
    baseline.update_baseline("compression", "speed_mbps", 150.5)
    result = baseline.check_regression("compression", "speed_mbps", 145.0)
    print(f"Performance check: {result}")