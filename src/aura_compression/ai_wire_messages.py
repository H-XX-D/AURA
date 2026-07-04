"""Structured AI-to-AI message helpers for the AIWire codec."""

from __future__ import annotations

import json
import random
from collections.abc import Mapping
from typing import Any

AIWireFrame = bytes | bytearray | memoryview | str | Mapping[str, Any]


def encode_ai_wire_message(message: AIWireFrame) -> bytes:
    """Encode a raw or structured message into canonical UTF-8 wire bytes."""

    if isinstance(message, bytes):
        return message
    if isinstance(message, (bytearray, memoryview)):
        return bytes(message)
    if isinstance(message, str):
        return message.encode("utf-8")
    if isinstance(message, Mapping):
        return json.dumps(
            message,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    raise TypeError(f"unsupported AIWire message type: {type(message).__name__}")


def decode_ai_wire_message(payload: bytes | bytearray | memoryview | str) -> Any:
    """Decode canonical AIWire JSON bytes back into a structured Python value."""

    if isinstance(payload, str):
        text = payload
    elif isinstance(payload, (bytes, bytearray, memoryview)):
        text = bytes(payload).decode("utf-8")
    else:
        raise TypeError(f"unsupported AIWire payload type: {type(payload).__name__}")
    return json.loads(text)


def build_ai_wire_messages(count: int, seed: int = 1729) -> list[bytes]:
    """Build encoded protocol-shaped AI/agent messages for tests and benchmarks."""

    return [
        encode_ai_wire_message(message)
        for message in build_structured_ai_messages(count=count, seed=seed)
    ]


def build_structured_ai_messages(count: int, seed: int = 1729) -> list[dict[str, Any]]:
    """Build realistic structured AI-to-AI protocol messages.

    Shapes cover common agent traffic: model requests, tool calls, JSON-RPC
    tool invocations, A2A task messages, tool results, memory writes, reviews,
    traces, and handoffs.
    """

    rng = random.Random(seed)
    tools = ["web_search", "read_file", "write_patch", "run_shell", "vector_lookup"]
    agents = ["planner", "researcher", "coder", "reviewer", "executor", "summarizer"]
    repos = ["payments-api", "retrieval-worker", "aura-bridge", "policy-gateway"]
    cities = ["Austin", "Seattle", "San Jose", "Chicago", "Boston", "Denver"]
    messages: list[dict[str, Any]] = []

    for i in range(count):
        tool = tools[i % len(tools)]
        agent = agents[i % len(agents)]
        repo = repos[i % len(repos)]
        city = cities[i % len(cities)]
        trace_id = f"trace-{seed}-{i:05d}"
        task_id = f"task-{(i // 4):04d}"
        call_id = f"call_{i:06d}"
        variant = i % 12
        payload: dict[str, Any]

        if variant == 0:
            payload = {
                "protocol": "openai.responses",
                "operation": "responses.create",
                "trace_id": trace_id,
                "model": "gpt-4.1-mini",
                "input": [
                    {
                        "role": "system",
                        "content": (
                            "You are the planner agent. Produce executable subgoals and "
                            "request tools only when needed."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Investigate latency regression in {repo} for the {city} "
                            "deployment."
                        ),
                    },
                ],
                "tools": [
                    {
                        "type": "function",
                        "name": "search_logs",
                        "description": "Search structured service logs by query and time range.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "service": {"type": "string"},
                                "query": {"type": "string"},
                                "since_minutes": {"type": "integer"},
                            },
                            "required": ["service", "query"],
                        },
                    }
                ],
                "metadata": {"tenant": "bench", "task_id": task_id, "priority": i % 5},
            }
        elif variant == 1:
            payload = {
                "protocol": "openai.responses",
                "type": "response.output_item.done",
                "trace_id": trace_id,
                "item": {
                    "type": "function_call",
                    "call_id": call_id,
                    "name": tool,
                    "arguments": {
                        "repository": repo,
                        "path": f"services/{repo}/src/handler_{i % 9}.py",
                        "query": f"timeout OR retry OR p95 city:{city}",
                        "limit": 20 + (i % 7),
                    },
                },
            }
        elif variant == 2:
            payload = {
                "protocol": "mcp",
                "jsonrpc": "2.0",
                "id": i,
                "method": "tools/call",
                "params": {
                    "name": tool,
                    "arguments": {
                        "session_id": task_id,
                        "uri": f"repo://{repo}/services/{agent}/config.yaml",
                        "line_start": 10 + i % 40,
                        "line_end": 35 + i % 80,
                    },
                },
            }
        elif variant == 3:
            payload = {
                "protocol": "mcp",
                "jsonrpc": "2.0",
                "id": i,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                f"{agent} found repeated retry budget exhaustion in "
                                f"{repo}; next action is patch validation."
                            ),
                        }
                    ],
                    "isError": False,
                    "structuredContent": {
                        "matches": [
                            {
                                "file": f"{repo}/handler.py",
                                "line": 42 + j,
                                "score": round(0.91 - j * 0.07, 3),
                            }
                            for j in range(3)
                        ],
                        "trace_id": trace_id,
                    },
                },
            }
        elif variant == 4:
            payload = {
                "protocol": "a2a",
                "jsonrpc": "2.0",
                "id": i,
                "method": "message/send",
                "params": {
                    "message": {
                        "messageId": f"msg-{i:06d}",
                        "role": "user",
                        "parts": [
                            {
                                "kind": "text",
                                "text": (
                                    f"Agent {agent}, produce a remediation plan for {repo} "
                                    "using only verified evidence."
                                ),
                            }
                        ],
                        "metadata": {"trace_id": trace_id, "task_id": task_id},
                    }
                },
            }
        elif variant == 5:
            payload = {
                "protocol": "a2a",
                "jsonrpc": "2.0",
                "id": i,
                "result": {
                    "id": task_id,
                    "contextId": f"ctx-{i // 12:04d}",
                    "status": {
                        "state": "working" if i % 3 else "completed",
                        "message": {
                            "role": "agent",
                            "parts": [
                                {
                                    "kind": "text",
                                    "text": (
                                        f"{agent} completed evidence pass {i % 5}; "
                                        f"confidence={0.72 + (i % 9) / 100:.2f}"
                                    ),
                                }
                            ],
                        },
                    },
                    "artifacts": [
                        {
                            "artifactId": f"artifact-{i:06d}",
                            "name": "diagnostic-summary",
                            "parts": [
                                {
                                    "kind": "text",
                                    "text": "p95 latency increased after retry fanout change",
                                }
                            ],
                        }
                    ],
                },
            }
        elif variant == 6:
            payload = {
                "protocol": "agent.trace",
                "event": "plan.created",
                "trace_id": trace_id,
                "agent": agent,
                "task": {
                    "id": task_id,
                    "objective": f"Reduce {repo} tail latency without increasing error budget burn.",
                    "constraints": [
                        "no schema migration",
                        "rollback must be single commit",
                        "verify with replay",
                    ],
                    "subgoals": [
                        "read deployment diff",
                        "inspect retry policy",
                        "run focused load probe",
                        "draft patch",
                    ],
                },
            }
        elif variant == 7:
            payload = {
                "protocol": "agent.handoff",
                "from": "planner",
                "to": agent,
                "trace_id": trace_id,
                "handoff": {
                    "task_id": task_id,
                    "working_memory": {
                        "facts": [
                            f"{repo} p95 increased in {city}",
                            "no database saturation observed",
                            "retry fanout changed in latest deploy",
                        ],
                        "open_questions": [
                            "does circuit breaker trip before retry budget?",
                            "are cache misses correlated with provider region?",
                        ],
                    },
                    "requested_output_schema": {
                        "type": "object",
                        "required": ["finding", "evidence", "next_action", "confidence"],
                    },
                },
            }
        elif variant == 8:
            payload = {
                "protocol": "tool.result",
                "trace_id": trace_id,
                "tool_call_id": call_id,
                "name": tool,
                "ok": True,
                "elapsed_ms": 18 + (i % 37),
                "output": {
                    "rows": [
                        {
                            "timestamp": (
                                f"2026-06-29T18:{(i + j) % 60:02d}:" f"{(11 + j) % 60:02d}Z"
                            ),
                            "service": repo,
                            "level": "WARN" if j % 2 else "INFO",
                            "message": (
                                f"retry budget consumed for shard={j} city={city} "
                                f"attempt={1 + j}"
                            ),
                        }
                        for j in range(5)
                    ]
                },
            }
        elif variant == 9:
            payload = {
                "protocol": "memory.write",
                "trace_id": trace_id,
                "kind": "observation",
                "title": f"{repo} retry fanout suspected",
                "body": (
                    f"{agent} observed matching latency spike and retry count increase in "
                    f"{city}."
                ),
                "confidence": round(0.74 + (i % 11) / 100, 3),
                "evidence": {
                    "source_refs": [
                        f"logs://{repo}/{city}/{i % 24:02d}",
                        f"repo://{repo}/deploy/{i % 13}",
                    ],
                    "supports": [],
                    "contradicts": [],
                },
            }
        elif variant == 10:
            payload = {
                "protocol": "agent.review",
                "trace_id": trace_id,
                "reviewer": "reviewer",
                "patch": {
                    "repo": repo,
                    "files_changed": [
                        f"services/{repo}/retry.py",
                        f"services/{repo}/tests/test_retry_policy.py",
                    ],
                    "diff_summary": [
                        "cap retry fanout per upstream request",
                        "add histogram bucket for retry exhaustion",
                        "preserve existing timeout envelope",
                    ],
                },
                "verdict": "request_changes" if i % 4 == 0 else "approve",
                "comments": [
                    {
                        "line": 58,
                        "severity": "medium",
                        "text": "Add replay test for retry budget boundary.",
                    },
                    {"line": 91, "severity": "low", "text": "Name the metric with service prefix."},
                ],
            }
        else:
            payload = {
                "protocol": "agent.final",
                "trace_id": trace_id,
                "task_id": task_id,
                "agent": "summarizer",
                "status": "completed",
                "answer": {
                    "summary": (
                        f"Root cause likely retry fanout in {repo}; mitigation is bounded "
                        "retries plus replay verification."
                    ),
                    "actions": [
                        {"owner": "coder", "action": "apply retry cap", "state": "ready"},
                        {"owner": "executor", "action": "run canary replay", "state": "queued"},
                    ],
                    "confidence": round(0.81 + (i % 13) / 100, 3),
                },
            }

        messages.append(payload)

    rng.shuffle(messages)
    return messages
