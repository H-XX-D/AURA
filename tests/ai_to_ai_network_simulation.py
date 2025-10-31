#!/usr/bin/env python3
"""
AI-to-AI Structured Traffic Simulation

Models:
- Coordination layer emitting structured JSON job requests
- Specialized AI worker returning large structured analytics payloads
- Realistic network with latency, jitter, and throughput variance
- 1 minute duration with batching cadence

Demonstrates AURA compression behaviour on high-similarity AI-to-AI exchanges.
"""

import json
import random
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from aura_compression.compressor_refactored import ProductionHybridCompressor


@dataclass
class NetworkMetrics:
    direction: str
    original_size: int
    compressed_size: int
    compression_ratio: float
    compression_time_ms: float
    decompression_time_ms: float
    network_latency_ms: float
    method: str
    partial_match: bool = False
    match_coverage: float = 0.0


class SimulatedNetwork:
    def __init__(self, base_latency_ms: float = 28.0, jitter_ms: float = 6.0, throughput_kbps: float = 512.0):
        self.base_latency_ms = base_latency_ms
        self.jitter_ms = jitter_ms
        self.throughput_kbps = throughput_kbps

    def transmit(self, data: bytes) -> Tuple[bytes, float]:
        payload_kb = max(len(data) / 1024.0, 0.0001)
        serialization_ms = (payload_kb / max(self.throughput_kbps, 0.001)) * 1000
        latency_ms = self.base_latency_ms + random.uniform(-self.jitter_ms, self.jitter_ms) + serialization_ms
        time.sleep(latency_ms * 0.001)
        return data, latency_ms


def _json_to_template_pattern(json_text: str) -> Tuple[str, List[str]]:
    """Derive a TemplateLibrary pattern and slot list from a JSON payload."""
    data = json.loads(json_text)
    slots: List[str] = []

    def encode(value: object) -> str:
        if isinstance(value, dict):
            parts: List[str] = ["{{"]
            for idx, (key, inner) in enumerate(value.items()):
                if idx:
                    parts.append(",")
                parts.append(json.dumps(key))
                parts.append(":")
                parts.append(encode(inner))
            parts.append("}}")
            return "".join(parts)
        if isinstance(value, list):
            parts: List[str] = ["["]
            for idx, item in enumerate(value):
                if idx:
                    parts.append(",")
                parts.append(encode(item))
            parts.append("]")
            return "".join(parts)
        if isinstance(value, str):
            slot_index = len(slots)
            slots.append(value)
            return f"\"{{{slot_index}}}\""
        if isinstance(value, (int, float)):
            slot_index = len(slots)
            slots.append(json.dumps(value))
            return f"{{{slot_index}}}"
        if isinstance(value, bool):
            return "true" if value else "false"
        if value is None:
            return "null"
        slot_index = len(slots)
        slots.append(json.dumps(value))
        return f"{{{slot_index}}}"

    pattern = encode(data)
    return pattern, slots


def _register_template_from_payload(compressor: ProductionHybridCompressor, payload: str, label: str) -> None:
    """Register a dynamic template derived from a representative payload."""
    library = compressor.template_library
    pattern, _ = _json_to_template_pattern(payload)
    if pattern in library.list_templates().values():
        return
    try:
        template_id = library.allocate_dynamic_id()
    except RuntimeError as exc:
        print(f"Template allocation failed for {label}: {exc}")
        return
    library.add(template_id, pattern)
    library.clear_match_cache()
    match = library.match(payload)
    if match is None:
        print(f"Warning: newly registered template for {label} did not match sample payload")
    else:
        library.record_use(match.template_id)
        print(f"Primed template {template_id} for {label} with {len(match.slots)} slots")


def _prime_template_library(compressor: ProductionHybridCompressor,
                            orchestrator: 'AIOrchestrator',
                            worker: 'AIWorker') -> None:
    """Seed the template library with deterministic orchestrator and worker patterns."""
    sample_request = orchestrator.build_job_request()
    sample_response = worker.build_response()
    _register_template_from_payload(compressor, sample_request, "orchestrator request")
    _register_template_from_payload(compressor, sample_response, "worker response")


def _random_seed_words(source: Iterable[str], count: int) -> List[str]:
    choices = list(source)
    return random.sample(choices, min(count, len(choices)))


class AIOrchestrator:
    def __init__(self, taxonomy: Dict[str, List[str]]):
        self.taxonomy = taxonomy
        self.seq_id = 0

    def build_job_request(self) -> str:
        self.seq_id += 1
        objectives = _random_seed_words(self.taxonomy["objectives"], 2)
        datasets = _random_seed_words(self.taxonomy["datasets"], 3)
        constraints = _random_seed_words(self.taxonomy["constraints"], 3)
        payload = {
            "job_id": f"workflow-{time.strftime('%Y%m%d')}-{self.seq_id:06d}",
            "timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            "priority": random.choice(["background", "interactive", "slo-critical"]),
            "objectives": objectives,
            "datasets": [{"name": ds, "version": random.randint(2, 7)} for ds in datasets],
            "hyperparameters": {
                "temperature": round(random.uniform(0.1, 0.4), 2),
                "top_k": random.choice([16, 32, 64]),
                "max_tokens": random.choice([2048, 3072, 4096]),
            },
            "constraints": constraints,
            "expected_artifacts": ["plan", "analysis", "risks", "next_steps"],
            "handoff": {
                "channel": "event-stream",
                "ack_deadline_ms": random.choice([250, 500, 750]),
                "retry": {"max_attempts": 3, "backoff_ms": 1200},
            },
        }
        return json.dumps(payload, separators=(",", ":"))


class AIWorker:
    def __init__(self, taxonomy: Dict[str, List[str]]):
        self.taxonomy = taxonomy
        self.task_templates = self._build_templates()

    def _build_templates(self) -> List[Dict[str, object]]:
        templates: List[Dict[str, object]] = []
        for capability in self.taxonomy["objectives"]:
            templates.append(
                {
                    "capability": capability,
                    "analysis": {
                        "summary": """The system evaluated contextual signals, applied constraint-aware planning, and produced detailed recommendations.""",
                        "scoring": {
                            "confidence": round(random.uniform(0.82, 0.97), 3),
                            "risk_index": round(random.uniform(0.08, 0.21), 3),
                        },
                        "signals": random.sample(self.taxonomy["signals"], 5),
                    },
                    "plan": [
                        {
                            "step": idx + 1,
                            "action": action,
                            "owner": random.choice(self.taxonomy["agents"]),
                            "eta_minutes": random.choice([5, 10, 15, 20]),
                        }
                        for idx, action in enumerate(random.sample(self.taxonomy["actions"], 6))
                    ],
                    "risks": [
                        {
                            "id": f"risk-{random.randint(100, 999)}",
                            "description": desc,
                            "mitigation": random.choice(self.taxonomy["mitigations"]),
                        }
                        for desc in random.sample(self.taxonomy["risks"], 4)
                    ],
                    "next_steps": {
                        "handoff": random.choice(self.taxonomy["agents"]),
                        "channels": random.sample(["slack", "pager", "ops-dashboard", "email"], 2),
                        "checkpoint": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(time.time() + 900)),
                    },
                }
            )
        return templates

    def build_response(self) -> str:
        template = random.choice(self.task_templates)
        augmented = {
            "capability": template["capability"],
            "analysis": template["analysis"],
            "plan": template["plan"],
            "risks": template["risks"],
            "next_steps": template["next_steps"],
            "telemetry": {
                "tokens_consumed": random.randint(1200, 2400),
                "latency_ms": random.uniform(180.0, 420.0),
                "cache_hits": random.randint(32, 128),
                "rerank_passes": random.choice([1, 2, 3]),
            },
            "audit": {
                "template_version": random.choice(["2025.09", "2025.10"]),
                "policy_checks": {
                    "privacy": True,
                    "safety": True,
                    "compliance": True,
                },
                "trace_id": f"trace-{random.randint(10_000, 99_999)}",
            },
        }
        return json.dumps(augmented, separators=(",", ":"))


def run_simulation(duration_seconds: int = 60) -> None:
    print("=" * 88)
    print("AI-TO-AI STRUCTURED NETWORK SIMULATION")
    print("=" * 88)
    print()
    print(f"Duration: {duration_seconds} seconds")
    print("Simulating: Orchestrator ↔ Worker with structured JSON artifacts")
    print()

    taxonomy = {
        "objectives": [
            "multi-agent coordination",
            "knowledge distillation",
            "threat triage",
            "document synthesis",
            "customer journey analysis",
            "release readiness",
        ],
        "datasets": [
            "activity-feed",
            "usage-telemetry",
            "incident-history",
            "infra-metrics",
            "knowledge-base",
            "customer-feedback",
            "experiment-results",
        ],
        "constraints": [
            "respect data residency",
            "cap cold-start latency at 250ms",
            "enforce privacy filters",
            "prefer cached embeddings",
            "disable speculative expansion",
            "share optimized prompt",
        ],
        "signals": [
            "latency_spike",
            "retrieval_cache_hit",
            "feature_flag_active",
            "usage_drop",
            "response_quality",
            "security_event",
            "regression_detected",
            "capacity_alert",
            "link_clicked",
            "sentiment_shift",
        ],
        "actions": [
            "validate_context_window",
            "refresh_embedding_cache",
            "broadcast_action_plan",
            "update_service_catalog",
            "hydrate_vector_store",
            "notify_incident_commander",
            "escalate_to_tier2",
            "rollout_canary_patch",
            "generate_executive_summary",
            "enrich_alert_payload",
        ],
        "risks": [
            "Missing telemetry for region",
            "Model drift impacting accuracy",
            "Downstream API rate limiting",
            "Overlapping incident coordination",
            "Cache invalidation lag",
            "Unverified remediation playbook",
            "Incomplete audit metadata",
            "External dependency saturation",
        ],
        "mitigations": [
            "Fallback to archived embeddings",
            "Trigger adaptive sampling",
            "Request manual approval",
            "Enable high-availability route",
            "Schedule follow-up validation",
            "Publish mitigation summary",
        ],
        "agents": [
            "orchestrator-alpha",
            "analytics-beta",
            "remediator-gamma",
            "observer-delta",
            "synthesis-epsilon",
        ],
    }

    orchestrator = AIOrchestrator(taxonomy)
    worker = AIWorker(taxonomy)
    network = SimulatedNetwork(base_latency_ms=32.0, jitter_ms=8.0, throughput_kbps=1024.0)
    compressor = ProductionHybridCompressor(
        binary_advantage_threshold=1.02,
        min_compression_size=64,
        enable_aura=True,
        enable_audit_logging=False,
        enable_scorer=False,
    )

    _prime_template_library(compressor, orchestrator, worker)

    orchestrator_metrics: List[NetworkMetrics] = []
    worker_metrics: List[NetworkMetrics] = []

    start_time = time.time()
    exchanges = 0
    print("Starting AI-to-AI traffic...")
    print()

    while time.time() - start_time < duration_seconds:
        exchanges += 1
        request_payload = orchestrator.build_job_request()
        t0 = time.time()
        compressed_req, req_method, req_meta = compressor.compress(request_payload)
        compress_time = (time.time() - t0) * 1000
        transmitted_req, latency_req = network.transmit(compressed_req)
        t1 = time.time()
        decompressed_req = compressor.decompress(transmitted_req)
        decompress_time = (time.time() - t1) * 1000
        orchestrator_metrics.append(
            NetworkMetrics(
                direction="orchestrator→worker",
                original_size=len(request_payload),
                compressed_size=len(compressed_req),
                compression_ratio=req_meta.get("ratio", 1.0),
                compression_time_ms=compress_time,
                decompression_time_ms=decompress_time,
                network_latency_ms=latency_req,
                method=req_method.name,
                partial_match=req_meta.get("partial_match", False),
                match_coverage=req_meta.get("match_coverage", 0.0),
            )
        )

        # Worker processes request into structured response
        _ = json.loads(decompressed_req)
        response_payload = worker.build_response()
        t2 = time.time()
        compressed_res, res_method, res_meta = compressor.compress(response_payload)
        compress_time_res = (time.time() - t2) * 1000
        transmitted_res, latency_res = network.transmit(compressed_res)
        t3 = time.time()
        _ = compressor.decompress(transmitted_res)
        decompress_time_res = (time.time() - t3) * 1000
        worker_metrics.append(
            NetworkMetrics(
                direction="worker→orchestrator",
                original_size=len(response_payload),
                compressed_size=len(compressed_res),
                compression_ratio=res_meta.get("ratio", 1.0),
                compression_time_ms=compress_time_res,
                decompression_time_ms=decompress_time_res,
                network_latency_ms=latency_res,
                method=res_method.name,
                partial_match=res_meta.get("partial_match", False),
                match_coverage=res_meta.get("match_coverage", 0.0),
            )
        )

        if exchanges % 8 == 0:
            elapsed = time.time() - start_time
            print(f"Exchange {exchanges}: {elapsed:.1f}s elapsed, latest ratio {res_meta.get('ratio', 1.0):.2f}x")

        time.sleep(random.uniform(0.15, 0.3))

    elapsed = time.time() - start_time
    print()
    print("=" * 88)
    print("SIMULATION RESULTS")
    print("=" * 88)
    print()
    print(f"Duration: {elapsed:.2f} seconds")
    print(f"Total exchanges: {exchanges}")
    print(f"Throughput: {exchanges / elapsed:.2f} exchanges/sec")
    print()

    def summarise(metrics: List[NetworkMetrics], title: str) -> Tuple[int, int, List[float]]:
        original = sum(m.original_size for m in metrics)
        compressed = sum(m.compressed_size for m in metrics)
        ratios = [m.compression_ratio for m in metrics]
        latencies = [m.network_latency_ms for m in metrics]
        methods: Dict[str, int] = {}
        for m in metrics:
            methods[m.method] = methods.get(m.method, 0) + 1
        print("-" * 88)
        print(title)
        print("-" * 88)
        print(f"Payload: {original:,} bytes → {compressed:,} bytes")
        print(f"Average ratio: {statistics.mean(ratios):.3f}x")
        print(f"Median ratio: {statistics.median(ratios):.3f}x")
        print(f"Average network latency: {statistics.mean(latencies):.2f}ms")
        print("Compression mix:")
        for method, count in sorted(methods.items(), key=lambda x: x[1], reverse=True):
            pct = (count / len(metrics)) * 100
            print(f"  {method}: {count} ({pct:.1f}%)")
        if original > compressed:
            savings = original - compressed
            print(f"✓ Bandwidth saved: {savings:,} bytes ({(savings / original) * 100:.1f}%)")
        else:
            expansion = compressed - original
            print(f"⚠ Expanded: {expansion:,} bytes ({(expansion / original) * 100:.1f}%)")
        print()
        return original, compressed, ratios

    req_original, req_compressed, req_ratios = summarise(orchestrator_metrics, "ORCHESTRATOR → WORKER")
    res_original, res_compressed, res_ratios = summarise(worker_metrics, "WORKER → ORCHESTRATOR")

    total_original = req_original + res_original
    total_compressed = req_compressed + res_compressed
    overall_ratio = total_original / total_compressed if total_compressed else 1.0

    print("=" * 88)
    print("OVERALL")
    print("=" * 88)
    print(f"Total bytes: {total_original:,} → {total_compressed:,}")
    print(f"Overall ratio: {overall_ratio:.3f}x")

    avg_request_size = statistics.mean([m.original_size for m in orchestrator_metrics])
    avg_response_size = statistics.mean([m.original_size for m in worker_metrics])
    print(f"Average request size: {avg_request_size:.1f} bytes")
    print(f"Average response size: {avg_response_size:.1f} bytes")
    print(f"Responses are {avg_response_size / max(avg_request_size, 1):.1f}× larger than requests")

    if total_original > total_compressed:
        saved = total_original - total_compressed
        print(f"Total saved: {saved:,} bytes ({(saved / total_original) * 100:.1f}%)")
    else:
        expanded = total_compressed - total_original
        print(f"Net expansion: {expanded:,} bytes ({(expanded / total_original) * 100:.1f}%)")

    print()
    print("=" * 88)
    print("HONEST ASSESSMENT")
    print("=" * 88)
    if overall_ratio > 1.6:
        print("✓ OUTSTANDING: Compression thrives on structured coordination traffic")
    elif overall_ratio > 1.2:
        print("✓ STRONG: Structured exchanges benefit meaningfully from AURA")
    elif overall_ratio > 1.0:
        print("✓ MODEST: Savings are present but consider template tuning")
    else:
       print("⚠ LIMITED: Compression underperforms—inspect template coverage")
    print()


if __name__ == "__main__":
    duration = 60
    if len(sys.argv) > 1:
        try:
            duration = int(sys.argv[1])
        except ValueError:
            print(f"Invalid duration: {sys.argv[1]}, defaulting to 60 seconds")
    run_simulation(duration_seconds=duration)
