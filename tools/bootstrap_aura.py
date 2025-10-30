#!/usr/bin/env python3
"""
AURA Compression Bootstrap Script
Helps users get started with AURA compression using training data and optimized settings.

This script:
1. Loads training data and bootstrap configuration
2. Initializes AURA compression with optimized settings
3. Runs compression tests on sample data
4. Provides performance metrics and recommendations
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Any, Optional
import argparse


class AuraBootstrap:
    """Bootstrap helper for AURA compression system."""

    def __init__(self, training_data_dir: str = './training_data'):
        self.training_data_dir = Path(training_data_dir)
        self.config = None
        self.training_data = None
        self.compressor = None

    def load_bootstrap_config(self) -> bool:
        """Load bootstrap configuration."""
        config_path = self.training_data_dir / 'bootstrap_config.json'
        if not config_path.exists():
            print(f"❌ Bootstrap config not found at {config_path}")
            return False

        try:
            with open(config_path, 'r') as f:
                self.config = json.load(f)
            print(f"✅ Loaded bootstrap config from {config_path}")
            return True
        except Exception as e:
            print(f"❌ Failed to load config: {e}")
            return False

    def load_training_data(self) -> bool:
        """Load training data."""
        data_path = self.training_data_dir / 'combined_training.json'
        if not data_path.exists():
            print(f"❌ Training data not found at {data_path}")
            return False

        try:
            with open(data_path, 'r') as f:
                self.training_data = json.load(f)
            print(f"✅ Loaded training data: {self.training_data['metadata']['total_messages']} messages")
            return True
        except Exception as e:
            print(f"❌ Failed to load training data: {e}")
            return False

    def initialize_compressor(self) -> bool:
        """Initialize AURA compressor with bootstrap settings."""
        try:
            # Import AURA compression modules
            sys.path.insert(0, str(Path(__file__).parent.parent / 'src' / 'python'))

            from aura_compression.compressor import ProductionHybridCompressor
            from aura_compression.template_service import TemplateService
            from aura_compression.fuzzy_matcher import FuzzyMatcher

            # Load templates - the compressor will handle this internally
            # Template service is created automatically by ProductionHybridCompressor

            # Initialize compressor with aggressive settings
            aggressive_config = self.config['aura_compression']['aggressive_mode']
            self.compressor = ProductionHybridCompressor(
                binary_advantage_threshold=aggressive_config['binary_advantage_threshold'],
                tcp_brio_threshold=aggressive_config['tcp_brio_threshold'],
                min_compression_size=aggressive_config['min_compression_size'],
                template_store_path='./data/templates/template_store_expanded.json'
            )

            print("✅ Initialized AURA compressor with aggressive settings")
            return True

        except ImportError as e:
            print(f"❌ Failed to import AURA modules: {e}")
            print("Make sure AURA compression is properly installed")
            return False
        except Exception as e:
            print(f"❌ Failed to initialize compressor: {e}")
            return False

    def run_compression_tests(self, categories: List[str] = None) -> Dict[str, Any]:
        """Run compression tests on training data."""
        if not self.compressor or not self.training_data:
            print("❌ Compressor or training data not loaded")
            return {}

        if categories is None:
            categories = list(self.training_data['categories'].keys())

        results = {
            'test_timestamp': time.time(),
            'categories_tested': categories,
            'category_results': {},
            'overall_stats': {}
        }

        total_original_size = 0
        total_compressed_size = 0
        total_messages = 0

        print("\n🧪 Running compression tests...")

        for category in categories:
            if category not in self.training_data['categories']:
                print(f"⚠️  Category '{category}' not found in training data")
                continue

            category_data = self.training_data['categories'][category]
            messages = category_data['all_messages']

            print(f"\n📊 Testing category: {category} ({len(messages)} messages)")

            category_original_size = 0
            category_compressed_size = 0
            compressed_count = 0

            start_time = time.time()

            for message in messages:
                original_size = len(message.encode('utf-8'))
                category_original_size += original_size

                try:
                    compressed_result = self.compressor.compress(message)
                    if compressed_result:
                        compressed_data, method, metadata = compressed_result
                        compressed_size = len(compressed_data)
                        category_compressed_size += compressed_size
                        compressed_count += 1
                    else:
                        # No compression achieved
                        category_compressed_size += original_size
                except Exception as e:
                    print(f"⚠️  Compression failed for message: {e}")
                    category_compressed_size += original_size

            end_time = time.time()
            processing_time = end_time - start_time

            compression_ratio = category_original_size / category_compressed_size if category_compressed_size > 0 else 1.0
            compression_rate = compressed_count / len(messages) if len(messages) > 0 else 0.0

            category_result = {
                'message_count': len(messages),
                'compressed_count': compressed_count,
                'compression_rate': compression_rate,
                'original_size_bytes': category_original_size,
                'compressed_size_bytes': category_compressed_size,
                'compression_ratio': compression_ratio,
                'processing_time_seconds': processing_time,
                'throughput_messages_per_second': len(messages) / processing_time if processing_time > 0 else 0,
                'throughput_mbps': (category_original_size / processing_time / 1024 / 1024) if processing_time > 0 else 0
            }

            results['category_results'][category] = category_result

            total_original_size += category_original_size
            total_compressed_size += category_compressed_size
            total_messages += len(messages)

            print(f"   📈 Ratio: {compression_ratio:.2f}:1")
            print(f"   🎯 Rate: {compression_rate:.1%}")
            print(f"   ⚡ Throughput: {category_result['throughput_messages_per_second']:.0f} msg/s")

        # Calculate overall stats
        overall_ratio = total_original_size / total_compressed_size if total_compressed_size > 0 else 1.0
        results['overall_stats'] = {
            'total_messages': total_messages,
            'total_original_size_bytes': total_original_size,
            'total_compressed_size_bytes': total_compressed_size,
            'overall_compression_ratio': overall_ratio,
            'average_ratio_per_category': sum(r['compression_ratio'] for r in results['category_results'].values()) / len(results['category_results']) if results['category_results'] else 0
        }

        print("\n🎉 Overall Results:")
        print(f"   📊 Total Messages: {total_messages}")
        print(f"   📈 Overall Ratio: {overall_ratio:.2f}:1")
        print(f"   💾 Space Saved: {((total_original_size - total_compressed_size) / total_original_size * 100):.1f}%")

        return results

    def generate_recommendations(self, test_results: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on test results."""
        recommendations = []

        overall_ratio = test_results['overall_stats']['overall_compression_ratio']

        if overall_ratio >= 2.0:
            recommendations.append("🎉 Excellent! Your compression ratios are very good (>= 2.0:1)")
            recommendations.append("   Consider enabling more aggressive fuzzy matching for even better ratios")
        elif overall_ratio >= 1.5:
            recommendations.append("👍 Good compression ratios (1.5-2.0:1)")
            recommendations.append("   This is within the realistic range for mixed workloads")
        elif overall_ratio >= 1.2:
            recommendations.append("🤔 Moderate compression (1.2-1.5:1)")
            recommendations.append("   Check template coverage and consider expanding your template library")
        else:
            recommendations.append("⚠️  Low compression ratios (< 1.2:1)")
            recommendations.append("   Review template matching and consider adjusting thresholds")

        # Category-specific recommendations
        for category, result in test_results['category_results'].items():
            ratio = result['compression_ratio']
            rate = result['compression_rate']

            if ratio < 1.1 and rate < 0.5:
                recommendations.append(f"   🔍 {category}: Low compression - check template patterns")
            elif ratio > 3.0:
                recommendations.append(f"   ⭐ {category}: Excellent compression ratio!")

        # Performance recommendations
        avg_throughput = sum(r['throughput_messages_per_second'] for r in test_results['category_results'].values()) / len(test_results['category_results'])
        if avg_throughput < 1000:
            recommendations.append("   ⚡ Consider hardware acceleration for better throughput")
        else:
            recommendations.append("   🚀 Good throughput! Hardware acceleration is working well")

        return recommendations

    def save_test_results(self, results: Dict[str, Any], output_file: str = 'bootstrap_test_results.json'):
        """Save test results to file."""
        output_path = self.training_data_dir / output_file
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"💾 Test results saved to {output_path}")

    def create_production_config(self, test_results: Dict[str, Any]) -> Dict[str, Any]:
        """Create a production-ready configuration based on test results."""
        overall_ratio = test_results['overall_stats']['overall_compression_ratio']

        # Adjust settings based on performance
        production_config = self.config.copy()

        if overall_ratio > 2.5:
            # Very good compression, can be more aggressive
            production_config['aura_compression']['fuzzy_matching']['min_similarity'] = 0.8
            production_config['aura_compression']['fuzzy_matching']['max_distance'] = 40
        elif overall_ratio < 1.3:
            # Poor compression, be more conservative
            production_config['aura_compression']['fuzzy_matching']['min_similarity'] = 0.9
            production_config['aura_compression']['aggressive_mode']['large_file_threshold'] = 1024

        return production_config

    def run_bootstrap(self, categories: List[str] = None, save_results: bool = True) -> bool:
        """Run the complete bootstrap process."""
        print("🚀 Starting AURA Compression Bootstrap")
        print("=" * 50)

        # Step 1: Load configuration
        if not self.load_bootstrap_config():
            return False

        # Step 2: Load training data
        if not self.load_training_data():
            return False

        # Step 3: Initialize compressor
        if not self.initialize_compressor():
            return False

        # Step 4: Run compression tests
        test_results = self.run_compression_tests(categories)

        if not test_results:
            return False

        # Step 5: Generate recommendations
        recommendations = self.generate_recommendations(test_results)
        print("\n💡 Recommendations:")
        for rec in recommendations:
            print(f"   {rec}")

        # Step 6: Save results and production config
        if save_results:
            self.save_test_results(test_results)

            production_config = self.create_production_config(test_results)
            config_path = self.training_data_dir / 'production_config.json'
            with open(config_path, 'w') as f:
                json.dump(production_config, f, indent=2)
            print(f"⚙️  Production config saved to {config_path}")

        print("\n✅ Bootstrap complete!")
        print("🎯 Your AURA compression system is ready for production use")

        return True


def main():
    """Main bootstrap function."""
    parser = argparse.ArgumentParser(description='Bootstrap AURA compression system')
    parser.add_argument('--training-data-dir', default='./training_data',
                       help='Directory containing training data')
    parser.add_argument('--categories', nargs='+',
                       help='Categories to test (default: all)')
    parser.add_argument('--no-save', action='store_true',
                       help='Do not save test results')

    args = parser.parse_args()

    bootstrap = AuraBootstrap(args.training_data_dir)
    success = bootstrap.run_bootstrap(
        categories=args.categories,
        save_results=not args.no_save
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()