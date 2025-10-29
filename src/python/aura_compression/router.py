#!/usr/bin/env python3
"""
Production Router - Patent Claims 20, 26, 28
Routes messages using metadata without decompression
Measures fast-path usage percentage
"""
import time
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Callable
from enum import Enum


class RouteDecision(Enum):
    """Route decision result"""
    FAST_PATH = "fast_path"  # Routed using metadata only
    SLOW_PATH = "slow_path"  # Required decompression
    CACHED = "cached"  # Served from cache


@dataclass
class RoutingMetrics:
    """
    Metrics for measuring fast-path usage (Claim 20)
    Target: 60% of messages use metadata-only fast path
    """
    total_messages: int = 0
    fast_path_count: int = 0
    slow_path_count: int = 0
    cached_count: int = 0

    total_latency_ms: float = 0.0
    fast_path_latency_ms: float = 0.0
    slow_path_latency_ms: float = 0.0

    def get_fast_path_percentage(self) -> float:
        """Calculate percentage of messages using fast path (Claim 20)"""
        if self.total_messages == 0:
            return 0.0
        return (self.fast_path_count / self.total_messages) * 100

    def get_average_latency(self) -> float:
        """Get average latency across all paths"""
        if self.total_messages == 0:
            return 0.0
        return self.total_latency_ms / self.total_messages

    def get_speedup_factor(self) -> float:
        """Calculate speedup from fast-path routing"""
        if self.fast_path_count == 0 or self.slow_path_count == 0:
            return 1.0

        avg_fast = self.fast_path_latency_ms / self.fast_path_count
        avg_slow = self.slow_path_latency_ms / self.slow_path_count

        if avg_fast > 0:
            return avg_slow / avg_fast
        return 1.0

    def to_dict(self) -> Dict[str, Any]:
        """Export metrics as dictionary"""
        return {
            'total_messages': self.total_messages,
            'fast_path_count': self.fast_path_count,
            'slow_path_count': self.slow_path_count,
            'cached_count': self.cached_count,
            'fast_path_percentage': self.get_fast_path_percentage(),
            'average_latency_ms': self.get_average_latency(),
            'fast_path_latency_ms': self.fast_path_latency_ms / self.fast_path_count if self.fast_path_count > 0 else 0,
            'slow_path_latency_ms': self.slow_path_latency_ms / self.slow_path_count if self.slow_path_count > 0 else 0,
            'speedup_factor': self.get_speedup_factor(),
        }


@dataclass
class Route:
    """
    Routing configuration for a handler (Claim 26)
    """
    handler_name: str
    handler_function: Callable
    template_ids: List[int] = field(default_factory=list)
    function_ids: List[int] = field(default_factory=list)
    requires_decompression: bool = False


class ProductionRouter:
    """
    Production message router using metadata (Claims 20, 26, 28)

    Features:
    - Routes using metadata without decompression (Claim 26)
    - Measures fast-path usage percentage (Claim 20)
    - Load balancing based on metadata size estimates (Claim 28)
    """

    def __init__(self):
        self.routes: List[Route] = []
        self.metrics = RoutingMetrics()
        self.default_handler: Optional[Callable] = None

    def register_route(
        self,
        handler_name: str,
        handler_function: Callable,
        template_ids: Optional[List[int]] = None,
        function_ids: Optional[List[int]] = None,
        requires_decompression: bool = False,
    ):
        """
        Register route for metadata-based routing (Claim 26)

        Args:
            handler_name: Name of handler
            handler_function: Function to call
            template_ids: List of template IDs this handler accepts
            function_ids: List of function IDs this handler accepts
            requires_decompression: Whether handler needs full decompression
        """
        route = Route(
            handler_name=handler_name,
            handler_function=handler_function,
            template_ids=template_ids or [],
            function_ids=function_ids or [],
            requires_decompression=requires_decompression,
        )
        self.routes.append(route)
        print(f"Registered route: {handler_name}")

    def set_default_handler(self, handler: Callable):
        """Set default handler for unmatched routes"""
        self.default_handler = handler

    def route(self, metadata: Dict[str, Any], compressed_data: bytes, decompressor: Callable) -> Any:
        """
        Route message based on metadata (Claims 20, 26)

        Args:
            metadata: Extracted metadata (without decompression)
            compressed_data: Compressed message
            decompressor: Function to decompress if needed

        Returns:
            Handler result
        """
        start_time = time.time()

        # Find matching route
        matched_route = self._find_route(metadata)

        if matched_route:
            if matched_route.requires_decompression:
                # Slow path: decompress first
                plaintext = decompressor(compressed_data)
                result = matched_route.handler_function(plaintext, metadata)

                latency_ms = (time.time() - start_time) * 1000
                self._record_metrics(RouteDecision.SLOW_PATH, latency_ms)

                return result
            else:
                # Fast path: handler can work with metadata only
                result = matched_route.handler_function(metadata)

                latency_ms = (time.time() - start_time) * 1000
                self._record_metrics(RouteDecision.FAST_PATH, latency_ms)

                return result

        # No route matched, use default handler
        if self.default_handler:
            plaintext = decompressor(compressed_data)
            result = self.default_handler(plaintext, metadata)

            latency_ms = (time.time() - start_time) * 1000
            self._record_metrics(RouteDecision.SLOW_PATH, latency_ms)

            return result

        raise ValueError("No route matched and no default handler")

    def _find_route(self, metadata: Dict[str, Any]) -> Optional[Route]:
        """Find matching route based on metadata (Claim 26)"""
        template_ids = metadata.get('template_ids', [])
        function_id = metadata.get('function_id')

        for route in self.routes:
            # Match by template IDs
            if template_ids and route.template_ids:
                if any(tid in route.template_ids for tid in template_ids):
                    return route

            # Match by function ID
            if function_id and route.function_ids:
                if function_id in route.function_ids:
                    return route

        return None

    def _record_metrics(self, decision: RouteDecision, latency_ms: float):
        """Record routing metrics (Claim 20)"""
        self.metrics.total_messages += 1
        self.metrics.total_latency_ms += latency_ms

        if decision == RouteDecision.FAST_PATH:
            self.metrics.fast_path_count += 1
            self.metrics.fast_path_latency_ms += latency_ms
        elif decision == RouteDecision.SLOW_PATH:
            self.metrics.slow_path_count += 1
            self.metrics.slow_path_latency_ms += latency_ms
        elif decision == RouteDecision.CACHED:
            self.metrics.cached_count += 1

    def get_metrics(self) -> Dict[str, Any]:
        """Get routing metrics (Claim 20)"""
        return self.metrics.to_dict()

    def get_fast_path_percentage(self) -> float:
        """
        Get percentage of messages using fast path (Claim 20)
        Target: >= 60% for multi-agent scenarios
        """
        return self.metrics.get_fast_path_percentage()

    def estimate_message_size(self, metadata: Dict[str, Any]) -> int:
        """
        Estimate message size from metadata for load balancing (Claim 28)

        Args:
            metadata: Extracted metadata

        Returns:
            Estimated size in bytes
        """
        # Use metadata fields to estimate size
        compressed_size = metadata.get('compressed_size', 0)
        if compressed_size > 0:
            return compressed_size

        # Estimate from other metadata
        token_count = metadata.get('plain_token_length', 0)
        if token_count > 0:
            # Rough estimate: 4 bytes per token
            return token_count * 4

        # Default estimate
        return 1000


class LoadBalancer:
    """
    Load balancer using metadata size estimates (Claim 28)
    Routes to least-loaded worker based on metadata
    """

    def __init__(self, worker_count: int = 4):
        self.worker_count = worker_count
        self.worker_loads: List[int] = [0] * worker_count  # Current load per worker

    def select_worker(self, message_size: int) -> int:
        """
        Select least-loaded worker (Claim 28)

        Args:
            message_size: Estimated message size from metadata

        Returns:
            Worker index
        """
        # Find worker with minimum load
        min_load_idx = 0
        min_load = self.worker_loads[0]

        for i in range(1, self.worker_count):
            if self.worker_loads[i] < min_load:
                min_load = self.worker_loads[i]
                min_load_idx = i

        # Assign load to worker
        self.worker_loads[min_load_idx] += message_size

        return min_load_idx

    def release_worker(self, worker_idx: int, message_size: int):
        """Release worker after processing"""
        self.worker_loads[worker_idx] -= message_size
        if self.worker_loads[worker_idx] < 0:
            self.worker_loads[worker_idx] = 0

    def get_utilization(self) -> Dict[str, Any]:
        """Get load balancer utilization metrics (Claim 28)"""
        total_load = sum(self.worker_loads)
        avg_load = total_load / self.worker_count if self.worker_count > 0 else 0

        # Calculate load variance (uniformity metric)
        variance = sum((load - avg_load) ** 2 for load in self.worker_loads) / self.worker_count

        return {
            'worker_count': self.worker_count,
            'worker_loads': self.worker_loads,
            'total_load': total_load,
            'average_load': avg_load,
            'load_variance': variance,
            'uniformity_score': 1.0 / (1.0 + variance) if variance > 0 else 1.0,
        }
