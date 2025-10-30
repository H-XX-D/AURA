#!/usr/bin/env python3
"""
AURA Compression Monitoring System
Tracks compression ratios by data type, template coverage, and performance metrics.
Provides insights for optimization and troubleshooting.
"""

import json
import time
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict, Counter
import argparse
import threading
from pathlib import Path


class CompressionMonitor:
    """Monitors AURA compression performance and provides optimization insights."""

    def __init__(self, log_file: str = './compression_monitor.log'):
        self.log_file = Path(log_file)
        self.metrics = {
            'start_time': datetime.now(),
            'total_messages': 0,
            'total_original_bytes': 0,
            'total_compressed_bytes': 0,
            'compression_ratios_by_type': defaultdict(list),
            'template_coverage_by_type': defaultdict(list),
            'performance_metrics': [],
            'memory_usage': [],
            'error_counts': defaultdict(int),
            'fuzzy_match_stats': defaultdict(int),
        }
        self.lock = threading.Lock()

    def log_compression_event(self, message: str, message_type: str,
                            original_size: int, compressed_size: int,
                            method: str, template_id: Optional[int] = None,
                            fuzzy_matched: bool = False, similarity: float = 0.0):
        """Log a compression event for monitoring."""
        with self.lock:
            self.metrics['total_messages'] += 1
            self.metrics['total_original_bytes'] += original_size
            self.metrics['total_compressed_bytes'] += compressed_size

            # Calculate ratio
            ratio = original_size / compressed_size if compressed_size > 0 else 1.0

            # Track by message type
            self.metrics['compression_ratios_by_type'][message_type].append(ratio)

            # Track template coverage
            has_template = template_id is not None or fuzzy_matched
            self.metrics['template_coverage_by_type'][message_type].append(has_template)

            # Track fuzzy matching
            if fuzzy_matched:
                self.metrics['fuzzy_match_stats']['total'] += 1
                self.metrics['fuzzy_match_stats'][f'similarity_{int(similarity * 10)}'] += 1

            # Performance metrics (sample every 100 messages)
            if self.metrics['total_messages'] % 100 == 0:
                self._record_performance_metrics()

    def log_error(self, error_type: str, message: str):
        """Log compression errors."""
        with self.lock:
            self.metrics['error_counts'][error_type] += 1

    def _record_performance_metrics(self):
        """Record current performance metrics."""
        if not HAS_PSUTIL:
            return

        process = psutil.Process()
        memory_mb = process.memory_info().rss / 1024 / 1024

        self.metrics['performance_metrics'].append({
            'timestamp': datetime.now().isoformat(),
            'messages_processed': self.metrics['total_messages'],
            'memory_usage_mb': memory_mb,
            'cpu_percent': process.cpu_percent(),
        })

        self.metrics['memory_usage'].append(memory_mb)

    def get_compression_summary(self) -> Dict[str, Any]:
        """Get comprehensive compression summary."""
        with self.lock:
            total_ratio = (self.metrics['total_original_bytes'] /
                         self.metrics['total_compressed_bytes']
                         if self.metrics['total_compressed_bytes'] > 0 else 1.0)

            space_saved = ((self.metrics['total_original_bytes'] - self.metrics['total_compressed_bytes']) /
                          self.metrics['total_original_bytes'] * 100
                          if self.metrics['total_original_bytes'] > 0 else 0)

            # Calculate per-type statistics
            type_summaries = {}
            for msg_type, ratios in self.metrics['compression_ratios_by_type'].items():
                if ratios:
                    avg_ratio = sum(ratios) / len(ratios)
                    coverage = sum(self.metrics['template_coverage_by_type'][msg_type]) / len(ratios)
                    type_summaries[msg_type] = {
                        'average_ratio': avg_ratio,
                        'message_count': len(ratios),
                        'template_coverage': coverage,
                        'ratios': ratios[:10],  # Sample of ratios
                    }

            # Memory usage stats
            memory_stats = {}
            if self.metrics['memory_usage']:
                memory_stats = {
                    'current_mb': self.metrics['memory_usage'][-1],
                    'peak_mb': max(self.metrics['memory_usage']),
                    'average_mb': sum(self.metrics['memory_usage']) / len(self.metrics['memory_usage']),
                }

            return {
                'overall_stats': {
                    'total_messages': self.metrics['total_messages'],
                    'total_original_bytes': self.metrics['total_original_bytes'],
                    'total_compressed_bytes': self.metrics['total_compressed_bytes'],
                    'overall_ratio': total_ratio,
                    'space_saved_percent': space_saved,
                    'runtime_seconds': (datetime.now() - self.metrics['start_time']).total_seconds(),
                },
                'by_message_type': type_summaries,
                'fuzzy_matching': dict(self.metrics['fuzzy_match_stats']),
                'errors': dict(self.metrics['error_counts']),
                'memory_stats': memory_stats,
                'performance_trend': self.metrics['performance_metrics'][-5:] if self.metrics['performance_metrics'] else [],
            }

    def get_optimization_recommendations(self) -> List[str]:
        """Generate optimization recommendations based on monitoring data."""
        recommendations = []
        summary = self.get_compression_summary()

        # Overall performance
        overall_ratio = summary['overall_stats']['overall_ratio']
        if overall_ratio < 1.2:
            recommendations.append("⚠️  Overall compression ratio is low (< 1.2:1)")
            recommendations.append("   Consider enabling more aggressive compression thresholds")
        elif overall_ratio > 2.0:
            recommendations.append("🎉 Excellent overall compression ratio (> 2.0:1)")
            recommendations.append("   Current settings are working well")

        # Per-type analysis
        for msg_type, stats in summary['by_message_type'].items():
            ratio = stats['average_ratio']
            coverage = stats['template_coverage']

            if ratio < 1.1 and coverage < 0.5:
                recommendations.append(f"🔍 {msg_type}: Low compression and poor template coverage")
                recommendations.append(f"   Add more {msg_type} templates to improve ratios")
            elif ratio < 1.2:
                recommendations.append(f"📈 {msg_type}: Moderate compression ({ratio:.2f}:1)")
                recommendations.append(f"   Template coverage: {coverage:.1%}")
            elif ratio > 2.0:
                recommendations.append(f"⭐ {msg_type}: Excellent compression ({ratio:.2f}:1)")

        # Fuzzy matching analysis
        fuzzy_total = summary['fuzzy_matching'].get('total', 0)
        if fuzzy_total > 0:
            fuzzy_rate = fuzzy_total / summary['overall_stats']['total_messages']
            recommendations.append(f"🧬 Fuzzy matching used in {fuzzy_rate:.1%} of messages")
            if fuzzy_rate > 0.3:
                recommendations.append("   High fuzzy matching usage - consider expanding exact templates")
        else:
            recommendations.append("🧬 No fuzzy matching detected - templates may be sufficient")

        # Memory analysis
        memory = summary['memory_stats']
        if memory and memory['peak_mb'] > 500:
            recommendations.append(f"🧠 High memory usage (peak: {memory['peak_mb']:.0f}MB)")
            recommendations.append("   Consider reducing template cache size or using memory-mapped templates")

        # Error analysis
        if summary['errors']:
            total_errors = sum(summary['errors'].values())
            error_rate = total_errors / summary['overall_stats']['total_messages']
            if error_rate > 0.01:
                recommendations.append(f"❌ High error rate ({error_rate:.1%})")
                recommendations.append("   Review error types and improve error handling")

        return recommendations

    def save_report(self, output_file: str = './compression_report.json'):
        """Save comprehensive monitoring report."""
        report = {
            'generated_at': datetime.now().isoformat(),
            'monitoring_period': {
                'start': self.metrics['start_time'].isoformat(),
                'end': datetime.now().isoformat(),
                'duration_seconds': (datetime.now() - self.metrics['start_time']).total_seconds(),
            },
            'summary': self.get_compression_summary(),
            'recommendations': self.get_optimization_recommendations(),
        }

        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)

        print(f"📊 Compression report saved to {output_file}")

    def print_summary(self):
        """Print human-readable summary."""
        summary = self.get_compression_summary()

        print("📊 AURA Compression Monitoring Summary")
        print("=" * 50)

        overall = summary['overall_stats']
        print(f"Total Messages: {overall['total_messages']:,}")
        print(f"Overall Ratio: {overall['overall_ratio']:.2f}:1")
        print(f"Space Saved: {overall['space_saved_percent']:.1f}%")
        print(f"Runtime: {overall['runtime_seconds']:.1f} seconds")

        print("\n📈 By Message Type:")
        for msg_type, stats in summary['by_message_type'].items():
            print(f"  {msg_type}: {stats['average_ratio']:.2f}:1 "
                  f"({stats['message_count']} msgs, {stats['template_coverage']:.1%} coverage)")

        if summary['fuzzy_matching']:
            fuzzy_total = summary['fuzzy_matching'].get('total', 0)
            print(f"\n🧬 Fuzzy Matching: {fuzzy_total} matches")

        if summary['errors']:
            print(f"\n❌ Errors: {dict(summary['errors'])}")

        print("\n💡 Recommendations:")
        for rec in self.get_optimization_recommendations():
            print(f"   {rec}")


class CompressionOptimizer:
    """Provides optimization tools for AURA compression."""

    def __init__(self, monitor: CompressionMonitor):
        self.monitor = monitor

    def analyze_template_coverage(self) -> Dict[str, Any]:
        """Analyze which message types need more templates."""
        summary = self.monitor.get_compression_summary()

        coverage_analysis = {}
        for msg_type, stats in summary['by_message_type'].items():
            coverage = stats['template_coverage']
            avg_ratio = stats['average_ratio']

            if coverage < 0.6 or avg_ratio < 1.3:
                coverage_analysis[msg_type] = {
                    'coverage': coverage,
                    'avg_ratio': avg_ratio,
                    'priority': 'high' if coverage < 0.3 else 'medium',
                    'recommendation': self._get_template_recommendation(msg_type, coverage, avg_ratio)
                }

        return coverage_analysis

    def _get_template_recommendation(self, msg_type: str, coverage: float, avg_ratio: float) -> str:
        """Get specific template expansion recommendations."""
        if coverage < 0.3:
            return f"Add 50+ {msg_type} templates - coverage is critically low"
        elif coverage < 0.6:
            return f"Add 20-30 {msg_type} templates to improve coverage"
        elif avg_ratio < 1.3:
            return f"Review existing {msg_type} templates - may need pattern refinement"
        else:
            return f"{msg_type} templates are adequate"

    def optimize_fuzzy_matching(self) -> Dict[str, Any]:
        """Analyze and recommend fuzzy matching optimizations."""
        summary = self.monitor.get_compression_summary()

        fuzzy_stats = summary['fuzzy_matching']
        total_messages = summary['overall_stats']['total_messages']

        if not fuzzy_stats or total_messages == 0:
            return {'recommendation': 'Enable fuzzy matching for better coverage'}

        fuzzy_rate = fuzzy_stats.get('total', 0) / total_messages

        # Analyze similarity distribution
        similarity_distribution = {}
        for key, count in fuzzy_stats.items():
            if key.startswith('similarity_'):
                bucket = int(key.split('_')[1]) / 10.0  # Convert back to decimal
                similarity_distribution[bucket] = count

        # Calculate average similarity
        total_weighted = sum(bucket * count for bucket, count in similarity_distribution.items())
        total_count = sum(similarity_distribution.values())
        avg_similarity = total_weighted / total_count if total_count > 0 else 0

        recommendations = []

        if fuzzy_rate > 0.4:
            recommendations.append("High fuzzy matching usage - consider expanding exact templates")
        elif fuzzy_rate < 0.05:
            recommendations.append("Low fuzzy matching usage - templates may be sufficient")

        if avg_similarity < 0.8:
            recommendations.append("Low average similarity - consider reducing min_similarity threshold")
        elif avg_similarity > 0.95:
            recommendations.append("High similarity matches - fuzzy matching is very effective")

        return {
            'fuzzy_rate': fuzzy_rate,
            'avg_similarity': avg_similarity,
            'similarity_distribution': similarity_distribution,
            'recommendations': recommendations
        }

    def optimize_memory_usage(self) -> Dict[str, Any]:
        """Analyze memory usage and provide optimization recommendations."""
        summary = self.monitor.get_compression_summary()
        memory_stats = summary['memory_stats']

        if not memory_stats:
            return {'recommendation': 'Enable memory monitoring to track usage'}

        current_mb = memory_stats['current_mb']
        peak_mb = memory_stats['peak_mb']
        avg_mb = memory_stats['average_mb']

        recommendations = []

        if peak_mb > 1000:
            recommendations.append("High memory usage - consider memory-mapped template storage")
            recommendations.append("Reduce template cache size (current: 256)")
        elif peak_mb > 500:
            recommendations.append("Moderate memory usage - monitor template cache size")
        else:
            recommendations.append("Memory usage is acceptable")

        # Template cache recommendations
        total_messages = summary['overall_stats']['total_messages']
        if total_messages > 10000:
            recommendations.append("High message volume - consider increasing template cache size")
        elif total_messages < 1000:
            recommendations.append("Low message volume - consider reducing template cache size")

        return {
            'current_mb': current_mb,
            'peak_mb': peak_mb,
            'avg_mb': avg_mb,
            'recommendations': recommendations
        }

    def generate_optimization_report(self) -> Dict[str, Any]:
        """Generate comprehensive optimization report."""
        return {
            'generated_at': datetime.now().isoformat(),
            'template_coverage_analysis': self.analyze_template_coverage(),
            'fuzzy_matching_analysis': self.optimize_fuzzy_matching(),
            'memory_optimization': self.optimize_memory_usage(),
            'overall_recommendations': self._get_overall_recommendations()
        }

    def _get_overall_recommendations(self) -> List[str]:
        """Get overall optimization recommendations."""
        recommendations = []

        # Template coverage
        coverage_analysis = self.analyze_template_coverage()
        if coverage_analysis:
            high_priority = [k for k, v in coverage_analysis.items() if v['priority'] == 'high']
            if high_priority:
                recommendations.append(f"High priority: Expand templates for {', '.join(high_priority)}")

        # Fuzzy matching
        fuzzy_analysis = self.optimize_fuzzy_matching()
        recommendations.extend(fuzzy_analysis.get('recommendations', []))

        # Memory
        memory_analysis = self.optimize_memory_usage()
        recommendations.extend(memory_analysis.get('recommendations', []))

        return recommendations


def main():
    """Main monitoring and optimization function."""
    parser = argparse.ArgumentParser(description='AURA Compression Monitoring and Optimization')
    parser.add_argument('--monitor', action='store_true', help='Run monitoring mode')
    parser.add_argument('--analyze', action='store_true', help='Run optimization analysis')
    parser.add_argument('--report', type=str, default='./compression_report.json', help='Report output file')
    parser.add_argument('--log-file', type=str, default='./compression_monitor.log', help='Monitor log file')

    args = parser.parse_args()

    monitor = CompressionMonitor(args.log_file)
    optimizer = CompressionOptimizer(monitor)

    if args.monitor:
        # In a real implementation, this would integrate with the compression system
        print("📊 Monitoring mode - integrate with compression pipeline")
        print("Use CompressionMonitor.log_compression_event() in your compression code")

    if args.analyze:
        print("🔍 Running optimization analysis...")

        # Generate sample data for demonstration (in real usage, this would come from actual compression)
        for i in range(100):
            # Simulate different message types with realistic ratios
            msg_types = ['api', 'logs', 'metrics', 'events', 'messages']
            msg_type = msg_types[i % len(msg_types)]

            # Simulate compression ratios based on message type
            base_ratios = {'api': 1.8, 'logs': 1.3, 'metrics': 1.0, 'events': 1.0, 'messages': 1.0}
            ratio_variation = (i % 20 - 10) / 100.0  # +/- 0.1 variation
            ratio = base_ratios[msg_type] + ratio_variation

            original_size = 200 + (i % 300)
            compressed_size = int(original_size / ratio)

            monitor.log_compression_event(
                message=f"Sample {msg_type} message {i}",
                message_type=msg_type,
                original_size=original_size,
                compressed_size=compressed_size,
                method='template' if ratio > 1.2 else 'uncompressed',
                template_id=i % 50 if ratio > 1.2 else None,
                fuzzy_matched=ratio > 1.1 and ratio <= 1.2,
                similarity=0.85 if ratio > 1.1 and ratio <= 1.2 else 0.0
            )

        # Print analysis
        monitor.print_summary()

        # Save detailed report
        monitor.save_report(args.report)

        # Generate optimization report
        opt_report = optimizer.generate_optimization_report()
        opt_file = args.report.replace('.json', '_optimization.json')
        with open(opt_file, 'w') as f:
            json.dump(opt_report, f, indent=2)

        print(f"\n🔧 Optimization report saved to {opt_file}")
        print("\n💡 Key Optimization Recommendations:")
        for rec in opt_report['overall_recommendations']:
            print(f"   {rec}")


if __name__ == "__main__":
    main()