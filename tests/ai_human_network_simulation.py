#!/usr/bin/env python3
"""
AI-to-Human Communication Network Traffic Simulation

Simulates realistic network traffic patterns between AI and human communications
over 30 seconds, repeated 3 times to measure consistency and performance.
Tests AURA compression system under realistic AI conversation workloads.
"""

import argparse
import sys
import os
import time
import json
import random
import statistics
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict, Counter

# Add src to path (go up one level from tests to project root, then to src)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'src'))

from aura_compression.compressor_refactored import ProductionHybridCompressor
from aura_compression.enums import CompressionMethod


class AIHumanNetworkSimulator:
    """
    Simulates realistic AI-to-human communication network traffic
    """

    def __init__(self, duration_seconds: int = 30, enable_scorer: Optional[bool] = None):
        self.duration = timedelta(seconds=duration_seconds)
        self.enable_scorer = enable_scorer
        self.test_results = []  # Store results from each test run
        
        # Initialize compressor with optimized settings for simulation
        self.compressor = ProductionHybridCompressor(
            binary_advantage_threshold=1.01,
            min_compression_size=10,
            enable_aura=False,
            enable_audit_logging=True,
            audit_log_directory="./simulation_audit_logs",
            template_cache_size=256,
            enable_scorer=enable_scorer,
            template_sync_interval_seconds=None,
        )

        # AI-to-Human message patterns (realistic conversation data)
        self.ai_responses = [
            # Short confirmations/acknowledgments
            "I understand your question. Let me help you with that.",
            "That's a great question!",
            "I can help you with that.",
            "Let me explain that for you.",
            "Sure, I'd be happy to assist.",
            
            # Medium explanations
            "Based on your input, I would recommend {recommendation}. This approach has proven effective in similar scenarios and should address your needs.",
            "The key difference between {concept_a} and {concept_b} is that {explanation}. Both have their use cases depending on your specific requirements.",
            "To accomplish this task, you'll need to: 1) {step_1}, 2) {step_2}, 3) {step_3}. Each step is important for the overall process.",
            
            # Long detailed responses
            "Great question! Let me provide a comprehensive explanation. {topic} is a complex subject with multiple facets. First, consider {aspect_1}, which deals with {detail_1}. Additionally, {aspect_2} plays a crucial role in {detail_2}. When implementing this, you should be aware of {consideration_1} and {consideration_2}. Many developers find that {tip_1} helps improve {outcome_1}, while {tip_2} can optimize {outcome_2}.",
            "I analyzed your code and found several areas for improvement. Here's a detailed breakdown:\n\n1. Performance: {perf_issue} could be optimized by {perf_solution}.\n2. Code Quality: {quality_issue} should be refactored to {quality_solution}.\n3. Best Practices: Consider {best_practice} to improve {improvement_area}.\n\nImplementing these changes will result in {expected_benefit}.",
            
            # Code examples and technical responses
            "Here's an example implementation:\n\n```python\ndef {function_name}({params}):\n    {implementation}\n    return {return_value}\n```\n\nThis approach uses {technique} which is efficient for {use_case}.",
            
            # Error explanations
            "I see the issue. The error '{error_message}' typically occurs when {cause}. To fix this, try {solution_1} or {solution_2}. If the problem persists, you may need to {fallback_solution}.",
            
            # JSON responses (API-like)
            '{{"response": "{response}", "confidence": {confidence}, "suggestions": ["{suggestion_1}", "{suggestion_2}"], "metadata": {{"timestamp": "{timestamp}", "model": "{model}", "tokens": {tokens}}}}}',
        ]

        self.human_queries = [
            # Short questions
            "How do I {action}?",
            "What is {concept}?",
            "Can you help me with {task}?",
            "Why does {thing} happen?",
            "Is {option_a} better than {option_b}?",
            
            # Medium questions with context
            "I'm working on {project} and I need to {requirement}. What's the best way to approach this?",
            "I tried {attempted_solution} but it didn't work. Can you suggest an alternative?",
            "My code is throwing an error: '{error}'. What could be causing this?",
            
            # Long detailed queries
            "I'm building a {project_type} application and I need help with {feature}. I've already implemented {existing_features}, but I'm stuck on {problem}. Here's what I've tried so far: {attempts}. Can you provide guidance?",
            "Can you explain the difference between {technology_a} and {technology_b}? I understand that {known_fact}, but I'm confused about {confusion_point}. Which one should I use for {use_case}?",
        ]

        # Real-world variable pools for message generation
        self.variable_pools = {
            'action': ['optimize performance', 'fix this bug', 'implement authentication', 'set up a database', 'deploy to production'],
            'concept': ['machine learning', 'API design', 'compression algorithms', 'async programming', 'data structures'],
            'task': ['debugging', 'optimization', 'refactoring', 'testing', 'documentation'],
            'thing': ['memory leak', 'slow performance', 'compilation error', 'network timeout', 'race condition'],
            'option_a': ['REST', 'async/await', 'SQL', 'microservices', 'functional programming'],
            'option_b': ['GraphQL', 'callbacks', 'NoSQL', 'monolith', 'OOP'],
            'project': ['a web application', 'a machine learning model', 'a REST API', 'a data pipeline', 'a mobile app'],
            'requirement': ['implement caching', 'handle large files', 'improve response time', 'add real-time features', 'scale horizontally'],
            'attempted_solution': ['using a different library', 'refactoring the code', 'changing the algorithm', 'adding more memory', 'optimizing queries'],
            'error': ['TypeError: Cannot read property', 'IndexError: list index out of range', 'ConnectionError: timeout', 'ValueError: invalid literal', 'KeyError: key not found'],
            'project_type': ['web', 'mobile', 'data science', 'DevOps', 'machine learning'],
            'feature': ['user authentication', 'data compression', 'real-time updates', 'search functionality', 'payment processing'],
            'existing_features': ['user registration, login system', 'basic CRUD operations', 'data validation', 'API endpoints', 'front-end UI'],
            'problem': ['performance optimization', 'error handling', 'data persistence', 'security concerns', 'scalability'],
            'attempts': ['refactoring functions, adding caching', 'using different libraries', 'optimizing database queries', 'implementing async operations', 'adding error handling'],
            'technology_a': ['Docker', 'Kubernetes', 'PostgreSQL', 'Redis', 'RabbitMQ'],
            'technology_b': ['VM', 'Docker Swarm', 'MongoDB', 'Memcached', 'Kafka'],
            'known_fact': ['both are used for containerization', 'both handle data persistence', 'both provide caching', 'both enable messaging', 'both support scaling'],
            'confusion_point': ['their performance characteristics', 'when to use each', 'deployment complexity', 'resource requirements', 'learning curve'],
            'use_case': ['microservices architecture', 'real-time analytics', 'caching layer', 'message queue', 'distributed system'],
            'recommendation': ['using a caching layer', 'implementing async processing', 'optimizing database indexes', 'using a CDN', 'load balancing'],
            'concept_a': ['synchronous processing', 'SQL databases', 'monolithic architecture', 'REST APIs', 'functional programming'],
            'concept_b': ['asynchronous processing', 'NoSQL databases', 'microservices', 'GraphQL', 'object-oriented programming'],
            'explanation': ['one blocks while the other doesn\'t', 'they use different data models', 'they have different scaling patterns', 'they handle state differently', 'they have different paradigms'],
            'step_1': ['initialize the project', 'set up dependencies', 'create the database schema', 'configure the environment', 'define the API endpoints'],
            'step_2': ['implement core logic', 'add error handling', 'write tests', 'set up authentication', 'create the user interface'],
            'step_3': ['deploy to staging', 'run integration tests', 'optimize performance', 'document the code', 'monitor in production'],
            'topic': ['Compression algorithms', 'API design patterns', 'Database optimization', 'Asynchronous programming', 'Caching strategies'],
            'aspect_1': ['algorithm selection', 'data structure choice', 'query optimization', 'error handling', 'cache invalidation'],
            'detail_1': ['choosing the right algorithm for your data type', 'using appropriate data structures for performance', 'indexing strategies and query patterns', 'graceful degradation and recovery', 'maintaining consistency'],
            'aspect_2': ['performance tuning', 'scalability', 'reliability', 'maintainability', 'security'],
            'detail_2': ['optimizing critical paths', 'horizontal scaling strategies', 'fault tolerance mechanisms', 'code organization patterns', 'authentication and authorization'],
            'consideration_1': ['memory usage', 'CPU overhead', 'network latency', 'disk I/O', 'concurrency'],
            'consideration_2': ['code complexity', 'maintainability', 'testing coverage', 'documentation', 'monitoring'],
            'tip_1': ['profiling your application', 'using connection pooling', 'implementing caching', 'batch processing', 'lazy loading'],
            'outcome_1': ['response times', 'throughput', 'resource utilization', 'user experience', 'system reliability'],
            'tip_2': ['monitoring metrics', 'load testing', 'code reviews', 'automated testing', 'continuous integration'],
            'outcome_2': ['code quality', 'scalability', 'maintainability', 'deployment frequency', 'error rates'],
            'perf_issue': ['inefficient database queries', 'N+1 query problem', 'unnecessary computations', 'large memory allocations', 'blocking I/O operations'],
            'perf_solution': ['adding indexes', 'using eager loading', 'caching results', 'using object pooling', 'implementing async I/O'],
            'quality_issue': ['duplicated code', 'complex functions', 'tight coupling', 'lack of error handling', 'poor naming'],
            'quality_solution': ['extracting common functions', 'breaking into smaller functions', 'dependency injection', 'adding try-catch blocks', 'using descriptive names'],
            'best_practice': ['following SOLID principles', 'writing unit tests', 'documenting APIs', 'using version control', 'code reviews'],
            'improvement_area': ['code maintainability', 'test coverage', 'developer experience', 'collaboration', 'code quality'],
            'expected_benefit': ['faster performance and better user experience', 'easier maintenance and fewer bugs', 'better team collaboration', 'improved system reliability'],
            'function_name': ['process_data', 'calculate_metrics', 'handle_request', 'validate_input', 'optimize_query'],
            'params': ['data: List[str]', 'value: int, threshold: float', 'request: Request', 'user_input: str', 'query: str, params: Dict'],
            'implementation': ['    # Process input data\n    result = [item.strip() for item in data]\n    return result', '    # Calculate with threshold\n    return sum([v for v in data if v > threshold])', '    # Validate and process\n    if not request.is_valid():\n        raise ValueError()\n    return request.process()', '    # Check input\n    if not user_input:\n        return False\n    return validate(user_input)', '    # Execute query\n    cursor.execute(query, params)\n    return cursor.fetchall()'],
            'return_value': ['result', 'calculated_value', 'response', 'is_valid', 'query_results'],
            'technique': ['list comprehension', 'lazy evaluation', 'caching', 'async/await', 'connection pooling'],
            'use_case': ['data transformation', 'performance optimization', 'repeated calculations', 'I/O operations', 'database access'],
            'error_message': ['Connection refused', 'Out of memory', 'Timeout exceeded', 'Permission denied', 'Resource not found'],
            'cause': ['the service is not running', 'memory leak or large allocation', 'slow network or overloaded server', 'insufficient permissions', 'incorrect path or deleted resource'],
            'solution_1': ['restart the service', 'increase memory limits', 'increase timeout value', 'check file permissions', 'verify the path exists'],
            'solution_2': ['check firewall settings', 'optimize memory usage', 'optimize the operation', 'run with elevated privileges', 'recreate the resource'],
            'fallback_solution': ['check the logs for more details', 'contact system administrator', 'try alternative approach', 'restart the application', 'check documentation'],
            'response': ['Successfully processed your request', 'Here are the results', 'Task completed', 'Error occurred', 'Processing in progress'],
            'confidence': ['0.95', '0.87', '0.92', '0.78', '0.99'],
            'suggestion_1': ['optimize database queries', 'add error handling', 'implement caching', 'use async operations', 'add monitoring'],
            'suggestion_2': ['improve code documentation', 'write unit tests', 'refactor complex functions', 'add logging', 'implement rate limiting'],
            'timestamp': [datetime.now().isoformat()],
            'model': ['gpt-4', 'claude-3', 'gemini-pro', 'llama-3', 'mistral-large'],
            'tokens': ['1024', '2048', '512', '768', '1536'],
        }

    def generate_ai_message(self) -> str:
        """Generate realistic AI response message"""
        template = random.choice(self.ai_responses)
        return self._fill_template(template)

    def generate_human_message(self) -> str:
        """Generate realistic human query message"""
        template = random.choice(self.human_queries)
        return self._fill_template(template)

    def _fill_template(self, template: str) -> str:
        """Fill template with random values from variable pools"""
        message = template
        for key, values in self.variable_pools.items():
            placeholder = f'{{{key}}}'
            if placeholder in message:
                message = message.replace(placeholder, random.choice(values))
        return message

    def generate_conversation_pair(self) -> Tuple[str, str]:
        """Generate a realistic conversation exchange (human query + AI response)"""
        human_msg = self.generate_human_message()
        ai_msg = self.generate_ai_message()
        return human_msg, ai_msg

    def process_message(self, message: str, message_type: str) -> Dict[str, Any]:
        """Process a single message through compression and collect metrics"""
        try:
            start_time = time.time()
            
            # Compress the message
            compressed_data, compression_method, metadata = self.compressor.compress(message)
            
            processing_time = time.time() - start_time
            
            # Extract compression info
            compression_ratio = metadata.get('ratio', 1.0)
            method_name = compression_method.value if hasattr(compression_method, 'value') else str(compression_method)
            
            # Calculate network metrics
            latency_ms = processing_time * 1000  # milliseconds
            throughput_bps = len(message) / processing_time if processing_time > 0 else 0  # bytes/sec
            bandwidth_saved_bytes = len(message) - len(compressed_data)
            bandwidth_saved_percent = (bandwidth_saved_bytes / len(message)) * 100 if len(message) > 0 else 0
            
            return {
                'message_type': message_type,
                'original_size': len(message),
                'compressed_size': len(compressed_data),
                'compression_method': method_name,
                'compression_ratio': compression_ratio,
                'processing_time_sec': processing_time,
                'latency_ms': latency_ms,
                'throughput_bps': throughput_bps,
                'bandwidth_saved_bytes': bandwidth_saved_bytes,
                'bandwidth_saved_percent': bandwidth_saved_percent,
                'timestamp': datetime.now().isoformat(),
            }
            
        except Exception as e:
            return {
                'error': str(e),
                'message_type': message_type,
                'timestamp': datetime.now().isoformat(),
            }

    def run_single_test(self, test_number: int) -> Dict[str, Any]:
        """Run a single 30-second test"""
        print(f"\n{'='*60}")
        print(f"Starting Test Run #{test_number}")
        print(f"{'='*60}")
        
        start_time = datetime.now()
        end_time = start_time + self.duration
        
        stats = {
            'messages_processed': 0,
            'human_messages': 0,
            'ai_messages': 0,
            'total_bytes_original': 0,
            'total_bytes_compressed': 0,
            'compression_ratios': [],
            'latencies': [],
            'throughputs': [],
            'bandwidth_saved': [],
            'compression_methods': Counter(),
            'processing_times': [],
            'message_sizes': [],
            'errors': 0,
            'conversations': 0,
        }
        
        message_count = 0
        conversation_count = 0
        
        print(f"Duration: {self.duration.total_seconds()} seconds")
        print(f"Simulating AI-Human conversations...")
        
        while datetime.now() < end_time:
            try:
                # Generate conversation pair
                human_msg, ai_msg = self.generate_conversation_pair()
                conversation_count += 1
                
                # Process human message
                human_result = self.process_message(human_msg, 'human_query')
                if 'error' not in human_result:
                    stats['human_messages'] += 1
                    stats['messages_processed'] += 1
                    stats['total_bytes_original'] += human_result['original_size']
                    stats['total_bytes_compressed'] += human_result['compressed_size']
                    stats['compression_ratios'].append(human_result['compression_ratio'])
                    stats['latencies'].append(human_result['latency_ms'])
                    stats['throughputs'].append(human_result['throughput_bps'])
                    stats['bandwidth_saved'].append(human_result['bandwidth_saved_bytes'])
                    stats['compression_methods'][human_result['compression_method']] += 1
                    stats['processing_times'].append(human_result['processing_time_sec'])
                    stats['message_sizes'].append(human_result['original_size'])
                else:
                    stats['errors'] += 1
                
                # Process AI response
                ai_result = self.process_message(ai_msg, 'ai_response')
                if 'error' not in ai_result:
                    stats['ai_messages'] += 1
                    stats['messages_processed'] += 1
                    stats['total_bytes_original'] += ai_result['original_size']
                    stats['total_bytes_compressed'] += ai_result['compressed_size']
                    stats['compression_ratios'].append(ai_result['compression_ratio'])
                    stats['latencies'].append(ai_result['latency_ms'])
                    stats['throughputs'].append(ai_result['throughput_bps'])
                    stats['bandwidth_saved'].append(ai_result['bandwidth_saved_bytes'])
                    stats['compression_methods'][ai_result['compression_method']] += 1
                    stats['processing_times'].append(ai_result['processing_time_sec'])
                    stats['message_sizes'].append(ai_result['original_size'])
                else:
                    stats['errors'] += 1
                
                message_count += 2  # human + AI
                stats['conversations'] = conversation_count
                
                # Progress indicator every 50 messages
                if message_count % 50 == 0:
                    elapsed = (datetime.now() - start_time).total_seconds()
                    progress = (elapsed / self.duration.total_seconds()) * 100
                    print(f"  Progress: {message_count} messages ({conversation_count} conversations) - {progress:.1f}% complete")
                
                # Simulate realistic timing between messages (10-100ms)
                time.sleep(random.uniform(0.01, 0.1))
                
            except KeyboardInterrupt:
                print("\n  Test interrupted by user")
                break
            except Exception as e:
                print(f"  Error in test loop: {e}")
                stats['errors'] += 1
                continue
        
        actual_end_time = datetime.now()
        actual_duration = (actual_end_time - start_time).total_seconds()
        
        # Calculate summary statistics
        result = {
            'test_number': test_number,
            'start_time': start_time.isoformat(),
            'end_time': actual_end_time.isoformat(),
            'duration_seconds': actual_duration,
            'total_messages': stats['messages_processed'],
            'human_messages': stats['human_messages'],
            'ai_messages': stats['ai_messages'],
            'conversations': stats['conversations'],
            'errors': stats['errors'],
            'messages_per_second': stats['messages_processed'] / actual_duration if actual_duration > 0 else 0,
            'conversations_per_second': stats['conversations'] / actual_duration if actual_duration > 0 else 0,
            
            'compression_stats': {
                'total_original_bytes': stats['total_bytes_original'],
                'total_compressed_bytes': stats['total_bytes_compressed'],
                'total_bandwidth_saved_bytes': stats['total_bytes_original'] - stats['total_bytes_compressed'],
                'total_bandwidth_saved_mb': (stats['total_bytes_original'] - stats['total_bytes_compressed']) / (1024 * 1024),
                'overall_compression_ratio': stats['total_bytes_original'] / stats['total_bytes_compressed'] if stats['total_bytes_compressed'] > 0 else 1.0,
                'avg_compression_ratio': statistics.mean(stats['compression_ratios']) if stats['compression_ratios'] else 1.0,
                'median_compression_ratio': statistics.median(stats['compression_ratios']) if stats['compression_ratios'] else 1.0,
                'min_compression_ratio': min(stats['compression_ratios']) if stats['compression_ratios'] else 1.0,
                'max_compression_ratio': max(stats['compression_ratios']) if stats['compression_ratios'] else 1.0,
                'compression_ratio_stddev': statistics.stdev(stats['compression_ratios']) if len(stats['compression_ratios']) > 1 else 0.0,
                'methods_used': dict(stats['compression_methods']),
            },
            
            'network_performance': {
                'avg_latency_ms': statistics.mean(stats['latencies']) if stats['latencies'] else 0.0,
                'median_latency_ms': statistics.median(stats['latencies']) if stats['latencies'] else 0.0,
                'min_latency_ms': min(stats['latencies']) if stats['latencies'] else 0.0,
                'max_latency_ms': max(stats['latencies']) if stats['latencies'] else 0.0,
                'p95_latency_ms': statistics.quantiles(stats['latencies'], n=20)[18] if len(stats['latencies']) >= 20 else max(stats['latencies']) if stats['latencies'] else 0.0,
                'latency_stddev_ms': statistics.stdev(stats['latencies']) if len(stats['latencies']) > 1 else 0.0,
                
                'avg_throughput_bps': statistics.mean(stats['throughputs']) if stats['throughputs'] else 0.0,
                'avg_throughput_kbps': statistics.mean(stats['throughputs']) / 1024 if stats['throughputs'] else 0.0,
                'avg_throughput_mbps': statistics.mean(stats['throughputs']) / (1024 * 1024) if stats['throughputs'] else 0.0,
                'median_throughput_bps': statistics.median(stats['throughputs']) if stats['throughputs'] else 0.0,
                'total_bandwidth_saved_bytes': sum(stats['bandwidth_saved']),
                'total_bandwidth_saved_kb': sum(stats['bandwidth_saved']) / 1024,
                'total_bandwidth_saved_mb': sum(stats['bandwidth_saved']) / (1024 * 1024),
                'avg_bandwidth_saved_per_message': statistics.mean(stats['bandwidth_saved']) if stats['bandwidth_saved'] else 0.0,
                'bandwidth_efficiency_percent': ((stats['total_bytes_original'] - stats['total_bytes_compressed']) / stats['total_bytes_original'] * 100) if stats['total_bytes_original'] > 0 else 0.0,
            },
            
            'message_stats': {
                'avg_message_size_bytes': statistics.mean(stats['message_sizes']) if stats['message_sizes'] else 0.0,
                'median_message_size_bytes': statistics.median(stats['message_sizes']) if stats['message_sizes'] else 0.0,
                'min_message_size_bytes': min(stats['message_sizes']) if stats['message_sizes'] else 0.0,
                'max_message_size_bytes': max(stats['message_sizes']) if stats['message_sizes'] else 0.0,
                'total_data_processed_mb': stats['total_bytes_original'] / (1024 * 1024),
                'total_data_compressed_mb': stats['total_bytes_compressed'] / (1024 * 1024),
            },
        }
        
        # Print test summary
        print(f"\nTest #{test_number} Completed:")
        print(f"  Messages: {result['total_messages']} ({result['human_messages']} human, {result['ai_messages']} AI)")
        print(f"  Conversations: {result['conversations']}")
        print(f"  Throughput: {result['messages_per_second']:.2f} msg/sec, {result['conversations_per_second']:.2f} conv/sec")
        print(f"  Compression: {result['compression_stats']['avg_compression_ratio']:.3f}x average ratio")
        print(f"  Latency: {result['network_performance']['avg_latency_ms']:.2f}ms average, {result['network_performance']['p95_latency_ms']:.2f}ms p95")
        print(f"  Bandwidth Saved: {result['network_performance']['total_bandwidth_saved_kb']:.2f} KB ({result['network_performance']['bandwidth_efficiency_percent']:.1f}%)")
        print(f"  Data Processed: {result['message_stats']['total_data_processed_mb']:.3f} MB original, {result['message_stats']['total_data_compressed_mb']:.3f} MB compressed")
        
        return result

    def run_all_tests(self, num_tests: int = 3) -> Dict[str, Any]:
        """Run multiple test iterations and aggregate results"""
        print(f"\nAI-Human Communication Network Traffic Simulation")
        print(f"{'='*60}")
        print(f"Configuration:")
        print(f"  Duration per test: {self.duration.total_seconds()} seconds")
        print(f"  Number of test runs: {num_tests}")
        print(f"  Scorer enabled: {self.enable_scorer}")
        print(f"{'='*60}")
        
        all_results = []
        
        for i in range(1, num_tests + 1):
            result = self.run_single_test(i)
            all_results.append(result)
            
            # Brief pause between tests
            if i < num_tests:
                print(f"\nPausing 2 seconds before next test...")
                time.sleep(2)
        
        # Aggregate results across all tests
        aggregate = self._aggregate_results(all_results)
        
        return {
            'summary': aggregate,
            'individual_tests': all_results,
            'configuration': {
                'duration_seconds': self.duration.total_seconds(),
                'num_tests': num_tests,
                'scorer_enabled': self.enable_scorer,
                'timestamp': datetime.now().isoformat(),
            }
        }

    def _aggregate_results(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate statistics across multiple test runs"""
        print(f"\n{'='*60}")
        print(f"Aggregating Results Across All Tests")
        print(f"{'='*60}")
        
        # Extract metrics from all tests
        total_messages = [r['total_messages'] for r in results]
        conversations = [r['conversations'] for r in results]
        compression_ratios = [r['compression_stats']['avg_compression_ratio'] for r in results]
        latencies = [r['network_performance']['avg_latency_ms'] for r in results]
        throughputs = [r['network_performance']['avg_throughput_kbps'] for r in results]
        bandwidth_saved_mb = [r['network_performance']['total_bandwidth_saved_mb'] for r in results]
        
        aggregate = {
            'total_tests': len(results),
            'total_messages_all_tests': sum(total_messages),
            'total_conversations_all_tests': sum(conversations),
            
            'messages_per_test': {
                'avg': statistics.mean(total_messages),
                'min': min(total_messages),
                'max': max(total_messages),
                'stddev': statistics.stdev(total_messages) if len(total_messages) > 1 else 0.0,
                'consistency_percent': (1 - (statistics.stdev(total_messages) / statistics.mean(total_messages))) * 100 if len(total_messages) > 1 and statistics.mean(total_messages) > 0 else 100.0,
            },
            
            'conversations_per_test': {
                'avg': statistics.mean(conversations),
                'min': min(conversations),
                'max': max(conversations),
                'stddev': statistics.stdev(conversations) if len(conversations) > 1 else 0.0,
            },
            
            'compression_performance': {
                'avg_ratio_across_tests': statistics.mean(compression_ratios),
                'min_ratio': min(compression_ratios),
                'max_ratio': max(compression_ratios),
                'ratio_stddev': statistics.stdev(compression_ratios) if len(compression_ratios) > 1 else 0.0,
                'ratio_consistency_percent': (1 - (statistics.stdev(compression_ratios) / statistics.mean(compression_ratios))) * 100 if len(compression_ratios) > 1 and statistics.mean(compression_ratios) > 0 else 100.0,
            },
            
            'network_performance': {
                'avg_latency_ms_across_tests': statistics.mean(latencies),
                'min_avg_latency_ms': min(latencies),
                'max_avg_latency_ms': max(latencies),
                'latency_stddev': statistics.stdev(latencies) if len(latencies) > 1 else 0.0,
                
                'avg_throughput_kbps_across_tests': statistics.mean(throughputs),
                'min_throughput_kbps': min(throughputs),
                'max_throughput_kbps': max(throughputs),
                
                'total_bandwidth_saved_mb_all_tests': sum(bandwidth_saved_mb),
                'avg_bandwidth_saved_mb_per_test': statistics.mean(bandwidth_saved_mb),
            },
            
            'consistency_analysis': {
                'message_count_variance': statistics.variance(total_messages) if len(total_messages) > 1 else 0.0,
                'compression_ratio_variance': statistics.variance(compression_ratios) if len(compression_ratios) > 1 else 0.0,
                'latency_variance': statistics.variance(latencies) if len(latencies) > 1 else 0.0,
                'overall_consistency_score': self._calculate_consistency_score(total_messages, compression_ratios, latencies),
            },
        }
        
        # Print aggregate summary
        print(f"\nAggregate Summary:")
        print(f"  Total Tests: {aggregate['total_tests']}")
        print(f"  Total Messages: {aggregate['total_messages_all_tests']}")
        print(f"  Total Conversations: {aggregate['total_conversations_all_tests']}")
        print(f"  Avg Messages/Test: {aggregate['messages_per_test']['avg']:.1f} (±{aggregate['messages_per_test']['stddev']:.1f})")
        print(f"  Message Count Consistency: {aggregate['messages_per_test']['consistency_percent']:.1f}%")
        print(f"\nCompression Performance:")
        print(f"  Avg Compression Ratio: {aggregate['compression_performance']['avg_ratio_across_tests']:.3f}x")
        print(f"  Ratio Range: {aggregate['compression_performance']['min_ratio']:.3f}x - {aggregate['compression_performance']['max_ratio']:.3f}x")
        print(f"  Ratio Consistency: {aggregate['compression_performance']['ratio_consistency_percent']:.1f}%")
        print(f"\nNetwork Performance:")
        print(f"  Avg Latency: {aggregate['network_performance']['avg_latency_ms_across_tests']:.2f}ms")
        print(f"  Avg Throughput: {aggregate['network_performance']['avg_throughput_kbps_across_tests']:.2f} KB/s")
        print(f"  Total Bandwidth Saved: {aggregate['network_performance']['total_bandwidth_saved_mb_all_tests']:.2f} MB")
        print(f"\nConsistency Score: {aggregate['consistency_analysis']['overall_consistency_score']:.1f}/100")
        
        return aggregate

    def _calculate_consistency_score(self, messages: List[int], ratios: List[float], latencies: List[float]) -> float:
        """Calculate overall consistency score (0-100) based on variance across tests"""
        if len(messages) <= 1:
            return 100.0
        
        # Calculate coefficient of variation (CV) for each metric
        msg_cv = statistics.stdev(messages) / statistics.mean(messages) if statistics.mean(messages) > 0 else 0
        ratio_cv = statistics.stdev(ratios) / statistics.mean(ratios) if statistics.mean(ratios) > 0 else 0
        latency_cv = statistics.stdev(latencies) / statistics.mean(latencies) if statistics.mean(latencies) > 0 else 0
        
        # Convert CV to consistency score (lower CV = higher consistency)
        # Penalize high variance more heavily
        msg_score = max(0, 100 - (msg_cv * 200))  # CV of 0.5 = 0 score
        ratio_score = max(0, 100 - (ratio_cv * 500))  # More sensitive to compression ratio changes
        latency_score = max(0, 100 - (latency_cv * 300))
        
        # Weighted average (compression ratio and latency are more important)
        consistency_score = (msg_score * 0.3 + ratio_score * 0.4 + latency_score * 0.3)
        
        return consistency_score

    def save_results(self, results: Dict[str, Any], filename: str = None):
        """Save test results to JSON file"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"ai_human_network_test_{timestamp}.json"
        
        output_path = Path(filename)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with output_path.open('w') as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"\nResults saved to: {output_path}")
        return str(output_path)


def main():
    """Main function to run AI-Human network simulation"""
    parser = argparse.ArgumentParser(
        description="Simulate AI-to-Human communication network traffic"
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=30,
        help="Duration of each test in seconds (default: 30)",
    )
    parser.add_argument(
        "--tests",
        type=int,
        default=3,
        help="Number of test iterations (default: 3)",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output JSON file path (default: timestamped filename)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        help="Random seed for reproducibility",
    )
    parser.add_argument(
        "--scorer",
        dest="enable_scorer",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable or disable the scorer (--scorer / --no-scorer)",
    )
    
    args = parser.parse_args()
    
    if args.seed is not None:
        random.seed(args.seed)
        print(f"Using random seed: {args.seed}")
    
    try:
        # Create simulator
        simulator = AIHumanNetworkSimulator(
            duration_seconds=args.duration,
            enable_scorer=args.enable_scorer
        )
        
        # Run all tests
        results = simulator.run_all_tests(num_tests=args.tests)
        
        # Save results
        output_file = simulator.save_results(results, filename=args.output)
        
        print(f"\n{'='*60}")
        print(f"All tests completed successfully!")
        print(f"Results saved to: {output_file}")
        print(f"{'='*60}")
        
    except KeyboardInterrupt:
        print("\n\nSimulation interrupted by user")
    except Exception as e:
        print(f"\nError running simulation: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
