#!/usr/bin/env python3
"""
AURA Fuzzy Matching Optimizer
Analyzes and optimizes fuzzy matching sensitivity for best compression performance.
"""

import json
import time
import sys
from typing import Dict, List, Any, Tuple
from pathlib import Path
import argparse

# Add src/python to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src' / 'python'))


class FuzzyMatchingOptimizer:
    """Optimizes fuzzy matching parameters for AURA compression."""

    def __init__(self, template_store_path: str = './data/templates/template_store_expanded.json'):
        self.template_store_path = Path(template_store_path)
        self.templates = self._load_templates()

    def _load_templates(self) -> Dict[str, List[str]]:
        """Load templates from the expanded store."""
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

            return templates_by_category

        except Exception as e:
            print(f"Failed to load templates: {e}")
            return {}

    def analyze_similarity_distribution(self, test_messages: List[str]) -> Dict[str, Any]:
        """Analyze how different similarity thresholds affect matching."""
        from aura_compression.fuzzy_matcher import FuzzyMatcher

        # Test different similarity thresholds
        thresholds = [0.7, 0.75, 0.8, 0.85, 0.9, 0.95]
        max_distances = [20, 30, 50]

        results = {}

        for threshold in thresholds:
            for max_dist in max_distances:
                matcher = FuzzyMatcher(
                    min_similarity=threshold,
                    max_distance=max_dist
                )

                matches = 0
                total_similarity = 0.0
                processing_time = 0.0

                for message in test_messages:
                    start_time = time.time()

                    # Get all template patterns for fuzzy matching
                    template_patterns = []
                    for patterns in self.templates.values():
                        template_patterns.extend(patterns)

                    result = matcher.compress_similar_message(message, template_patterns[:100])  # Limit for performance

                    processing_time += time.time() - start_time

                    if result:
                        matches += 1
                        total_similarity += result['similarity']

                avg_similarity = total_similarity / matches if matches > 0 else 0
                match_rate = matches / len(test_messages)
                avg_time = processing_time / len(test_messages) * 1000  # ms per message

                key = f"sim_{threshold}_dist_{max_dist}"
                results[key] = {
                    'min_similarity': threshold,
                    'max_distance': max_dist,
                    'match_rate': match_rate,
                    'matches': matches,
                    'avg_similarity': avg_similarity,
                    'avg_time_ms': avg_time,
                    'compression_potential': self._estimate_compression_potential(match_rate, avg_similarity)
                }

        return results

    def _estimate_compression_potential(self, match_rate: float, avg_similarity: float) -> float:
        """Estimate compression ratio improvement from fuzzy matching."""
        # Rough estimation: higher match rate and similarity = better compression
        base_improvement = match_rate * 0.3  # Up to 30% improvement from matches
        similarity_bonus = (avg_similarity - 0.8) * 0.2 if avg_similarity > 0.8 else 0
        return base_improvement + similarity_bonus

    def find_optimal_parameters(self, test_messages: List[str]) -> Dict[str, Any]:
        """Find optimal fuzzy matching parameters."""
        results = self.analyze_similarity_distribution(test_messages)

        # Score each configuration
        scored_configs = []
        for config_key, config_data in results.items():
            # Score based on compression potential vs performance cost
            compression_score = config_data['compression_potential'] * 100  # 0-50 points
            performance_penalty = config_data['avg_time_ms'] * 2  # Penalty for slow matching
            match_rate_bonus = config_data['match_rate'] * 20  # Bonus for coverage

            total_score = compression_score + match_rate_bonus - performance_penalty

            scored_configs.append({
                'config': config_key,
                'score': total_score,
                'data': config_data
            })

        # Sort by score (highest first)
        scored_configs.sort(key=lambda x: x['score'], reverse=True)

        optimal_config = scored_configs[0]['data']

        return {
            'optimal_parameters': {
                'min_similarity': optimal_config['min_similarity'],
                'max_distance': optimal_config['max_distance']
            },
            'expected_performance': {
                'match_rate': optimal_config['match_rate'],
                'avg_similarity': optimal_config['avg_similarity'],
                'avg_time_ms': optimal_config['avg_time_ms'],
                'compression_improvement': optimal_config['compression_potential']
            },
            'all_configs': {c['config']: c['data'] for c in scored_configs[:5]},  # Top 5
            'recommendations': self._generate_recommendations(optimal_config)
        }

    def _generate_recommendations(self, optimal_config: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on optimal configuration."""
        recommendations = []

        match_rate = optimal_config['match_rate']
        avg_time = optimal_config['avg_time_ms']
        compression = optimal_config['compression_potential']

        if match_rate > 0.3:
            recommendations.append("High match rate - fuzzy matching will significantly improve compression")
        elif match_rate < 0.1:
            recommendations.append("Low match rate - consider expanding exact templates instead")

        if avg_time > 10:
            recommendations.append("Slow fuzzy matching - consider GPU acceleration or caching")
        elif avg_time < 1:
            recommendations.append("Fast fuzzy matching - performance impact is minimal")

        if compression > 0.2:
            recommendations.append(f"Significant compression improvement ({compression:.2f}) - fuzzy matching is highly effective")
        elif compression < 0.05:
            recommendations.append("Minimal compression improvement - fuzzy matching may not be worth the overhead")

        return recommendations

    def benchmark_fuzzy_vs_exact(self, test_messages: List[str]) -> Dict[str, Any]:
        """Compare fuzzy matching vs exact template matching performance."""
        from aura_compression.fuzzy_matcher import FuzzyMatcher

        # Load template service for exact matching
        try:
            from aura_compression.template_service import create_template_service
            template_service = create_template_service()
        except Exception:
            return {'error': 'Could not load template service'}

        fuzzy_matcher = FuzzyMatcher(min_similarity=0.85, max_distance=30)

        results = {
            'exact_matches': 0,
            'fuzzy_matches': 0,
            'no_matches': 0,
            'exact_time': 0.0,
            'fuzzy_time': 0.0,
            'compression_ratios': {'exact': [], 'fuzzy': [], 'none': []}
        }

        for message in test_messages[:50]:  # Limit for performance
            # Test exact matching
            start_time = time.time()
            exact_match = template_service.find_template_match(message)
            results['exact_time'] += time.time() - start_time

            if exact_match:
                results['exact_matches'] += 1
                # Estimate compression ratio (simplified)
                ratio = len(message) / max(len(message) * 0.3, 50)  # Rough estimate
                results['compression_ratios']['exact'].append(ratio)

            # Test fuzzy matching
            start_time = time.time()
            template_patterns = []
            for patterns in self.templates.values():
                template_patterns.extend(patterns[:10])  # Limit patterns

            fuzzy_result = fuzzy_matcher.compress_similar_message(message, template_patterns)
            results['fuzzy_time'] += time.time() - start_time

            if fuzzy_result:
                results['fuzzy_matches'] += 1
                ratio = len(message) / max(len(message) * 0.4, 40)  # Rough estimate
                results['compression_ratios']['fuzzy'].append(ratio)
            elif not exact_match:
                results['no_matches'] += 1
                results['compression_ratios']['none'].append(1.0)  # No compression

        # Calculate averages
        for method in ['exact', 'fuzzy', 'none']:
            ratios = results['compression_ratios'][method]
            if ratios:
                results[f'avg_ratio_{method}'] = sum(ratios) / len(ratios)
            else:
                results[f'avg_ratio_{method}'] = 1.0

        results['avg_time_exact_ms'] = results['exact_time'] / len(test_messages) * 1000
        results['avg_time_fuzzy_ms'] = results['fuzzy_time'] / len(test_messages) * 1000

        return results

    def generate_fuzzy_config(self, test_messages: List[str] = None) -> Dict[str, Any]:
        """Generate optimal fuzzy matching configuration."""
        if test_messages is None:
            # Generate sample messages for testing
            test_messages = self._generate_sample_messages(100)

        print("🔍 Analyzing fuzzy matching parameters...")
        optimal_params = self.find_optimal_parameters(test_messages)

        print("⚡ Benchmarking fuzzy vs exact matching...")
        benchmark_results = self.benchmark_fuzzy_vs_exact(test_messages)

        config = {
            'fuzzy_matching_config': {
                'enabled': True,
                'min_similarity': optimal_params['optimal_parameters']['min_similarity'],
                'max_distance': optimal_params['optimal_parameters']['max_distance'],
                'cache_enabled': True,
                'gpu_accelerated': True,
            },
            'performance_projections': optimal_params['expected_performance'],
            'benchmark_results': benchmark_results,
            'recommendations': optimal_params['recommendations'],
            'generated_at': time.time(),
        }

        return config

    def _generate_sample_messages(self, count: int) -> List[str]:
        """Generate sample messages for testing."""
        messages = []

        # Mix of messages that should and shouldn't match templates
        templates = []
        for patterns in self.templates.values():
            templates.extend(patterns[:5])  # Take first 5 from each category

        for i in range(count):
            if i % 3 == 0 and templates:
                # Use a template (should match)
                template = templates[i % len(templates)]
                # Slightly modify to test fuzzy matching
                if len(template) > 10:
                    template = template.replace('request', 'req', 1)
                messages.append(template)
            else:
                # Generate non-matching message
                messages.append(f"Custom message {i} with random content {i*42}")

        return messages

    def save_config(self, config: Dict[str, Any], output_file: str = './fuzzy_config_optimized.json'):
        """Save optimized fuzzy configuration."""
        with open(output_file, 'w') as f:
            json.dump(config, f, indent=2)
        print(f"💾 Fuzzy configuration saved to {output_file}")


def main():
    """Main fuzzy optimization function."""
    parser = argparse.ArgumentParser(description='Optimize AURA fuzzy matching parameters')
    parser.add_argument('--analyze', action='store_true', help='Run parameter analysis')
    parser.add_argument('--benchmark', action='store_true', help='Run fuzzy vs exact benchmark')
    parser.add_argument('--generate-config', action='store_true', help='Generate optimal configuration')
    parser.add_argument('--output', type=str, default='./fuzzy_config_optimized.json', help='Output file')
    parser.add_argument('--test-messages', type=int, default=100, help='Number of test messages')

    args = parser.parse_args()

    optimizer = FuzzyMatchingOptimizer()

    if args.analyze:
        print("🔍 Analyzing fuzzy matching parameters...")
        test_messages = optimizer._generate_sample_messages(args.test_messages)
        results = optimizer.analyze_similarity_distribution(test_messages)

        print("📊 Top 5 Configurations:")
        sorted_configs = sorted(results.items(), key=lambda x: x[1]['compression_potential'], reverse=True)
        for i, (config_key, data) in enumerate(sorted_configs[:5]):
            print(f"{i+1}. {config_key}: {data['match_rate']:.1%} matches, "
                  f"{data['compression_potential']:.1%} improvement, "
                  f"{data['avg_time_ms']:.1f}ms avg")

    if args.benchmark:
        print("⚡ Running fuzzy vs exact matching benchmark...")
        test_messages = optimizer._generate_sample_messages(min(args.test_messages, 50))
        results = optimizer.benchmark_fuzzy_vs_exact(test_messages)

        print("📊 Benchmark Results:")
        print(f"  Exact matches: {results['exact_matches']}")
        print(f"  Fuzzy matches: {results['fuzzy_matches']}")
        print(f"  No matches: {results['no_matches']}")
        print(f"  Avg ratio exact: {results['avg_ratio_exact']:.2f}:1")
        print(f"  Avg ratio fuzzy: {results['avg_ratio_fuzzy']:.2f}:1")
        print(f"  Time exact: {results['avg_time_exact_ms']:.2f}ms")
        print(f"  Time fuzzy: {results['avg_time_fuzzy_ms']:.2f}ms")

    if args.generate_config:
        print("🔧 Generating optimal fuzzy configuration...")
        config = optimizer.generate_fuzzy_config()
        optimizer.save_config(config, args.output)

        print("\n💡 Recommendations:")
        for rec in config['recommendations']:
            print(f"   {rec}")

        perf = config['performance_projections']
        print("\n📈 Expected Performance:")
        print(f"   Match Rate: {perf['match_rate']:.1%}")
        print(f"   Avg Similarity: {perf['avg_similarity']:.2f}")
        print(f"   Processing Time: {perf['avg_time_ms']:.1f}ms per message")
        print(f"   Compression Improvement: {perf['compression_improvement']:.1%}")


if __name__ == "__main__":
    main()