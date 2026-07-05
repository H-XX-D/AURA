"""Structured AI-to-AI message helpers for the AIWire codec."""

from __future__ import annotations

import json
import random
from collections.abc import Iterable, Mapping
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


def discover_ai_wire_session_templates(
    messages: Iterable[AIWireFrame],
    *,
    max_templates: int = 16,
    min_frequency: int = 2,
    compression_threshold: float = 1.01,
    similarity_threshold: float = 0.6,
    starting_template_id: int = 128,
) -> dict[int, str]:
    """Discover a bounded session template map from AIWire-shaped messages.

    The returned templates are intended for AIWire dictionary negotiation, not
    binary-semantic frame encoding.  They are conservative: deterministic IDs,
    no persistence, and a caller-specified cap so session handshakes stay small.
    """

    if max_templates <= 0:
        return {}

    from .discovery import TemplateDiscoveryEngine

    texts = [
        encode_ai_wire_message(message).decode("utf-8", errors="replace") for message in messages
    ]
    if not texts:
        return {}

    engine = TemplateDiscoveryEngine(
        min_frequency=min_frequency,
        compression_threshold=compression_threshold,
        similarity_threshold=similarity_threshold,
        starting_template_id=starting_template_id,
        max_template_id=starting_template_id + max_templates - 1,
    )
    candidates = engine.discover_templates(texts)
    candidates.sort(
        key=lambda candidate: (candidate.compression_ratio, candidate.frequency),
        reverse=True,
    )

    templates: dict[int, str] = {}
    for candidate in candidates[:max_templates]:
        template_id = engine.promote_template(candidate)
        templates[template_id] = candidate.pattern
    return templates


def _mcp_meta(i: int) -> dict[str, Any]:
    return {
        "io.modelcontextprotocol/protocolVersion": "2025-11-25",
        "io.modelcontextprotocol/clientInfo": {"name": "aura-corpus", "version": "0.1"},
        "io.modelcontextprotocol/clientCapabilities": {
            "roots": {"listChanged": True},
            "sampling": {},
            "elicitation": {},
        },
        "progressToken": f"progress-{i // 8:05d}",
    }


def _json_arguments(**values: Any) -> str:
    return json.dumps(values, sort_keys=True, separators=(",", ":"))


def _text_part(text: str) -> dict[str, str]:
    return {"kind": "text", "text": text}


def build_delta_structured_ai_messages(
    count: int,
    seed: int = 1729,
    *,
    session_id: str | None = None,
) -> list[dict[str, Any]]:
    """Build stable-session messages where mostly values change.

    The corpus models the hot path after two agents have handshaked structure:
    session, task, route, and template identifiers stay stable while status,
    token, argument, artifact, and trace values move across the wire.
    """

    rng = random.Random(seed)
    stable_session_id = session_id or f"delta-session-{seed:04d}"
    stable_task_id = f"delta-task-{seed % 10000:04d}"
    stable_context_id = f"delta-context-{seed % 4096:04d}"
    stable_trace_id = f"delta-trace-{seed:04d}"
    stable_response_id = f"delta-response-{seed % 10000:04d}"
    stable_item_id = f"delta-item-{seed % 10000:04d}"
    stable_artifact_id = f"delta-artifact-{seed % 10000:04d}"
    stable_route = "agents.delta-session.events"
    states = ["submitted", "working", "input_required", "working", "completed"]
    tokens = [
        "checking",
        "retrieval",
        "evidence",
        "patch",
        "validation",
        "handoff",
        "summary",
    ]
    tools = ["read_file", "search_logs", "run_shell", "write_patch"]
    repos = ["payments-api", "retrieval-worker", "aura-bridge"]
    messages: list[dict[str, Any]] = []

    def common_meta(index: int, changed_value: str) -> dict[str, Any]:
        return {
            "synthetic": True,
            "delta_corpus": True,
            "session_id": stable_session_id,
            "task_id": stable_task_id,
            "template_epoch": 1,
            "sequence": index + 1,
            "changed_value": changed_value,
        }

    for i in range(count):
        variant = i % 10
        step = i // 10
        state = states[i % len(states)]
        token = tokens[(i + rng.randrange(len(tokens))) % len(tokens)]
        tool = tools[i % len(tools)]
        repo = repos[i % len(repos)]
        progress = min(100, 5 + i * 3)
        elapsed_ms = 12 + ((seed + i * 7) % 89)
        payload: dict[str, Any]

        if variant == 0:
            payload = {
                "protocol": "mcp",
                "jsonrpc": "2.0",
                "id": i + 1,
                "method": "tools/call",
                "params": {
                    "name": tool,
                    "arguments": {
                        "session_id": stable_session_id,
                        "task_id": stable_task_id,
                        "repository": repo,
                        "query": f"{token} step:{step} status:{state}",
                        "limit": 10 + (i % 5),
                    },
                    "_meta": {
                        "trace_id": stable_trace_id,
                        "route": stable_route,
                        "template_epoch": 1,
                    },
                },
                "session": {"id": stable_session_id, "template_epoch": 1},
                "delta_profile": common_meta(i, "argument"),
            }
        elif variant == 1:
            payload = {
                "protocol": "mcp",
                "jsonrpc": "2.0",
                "id": i + 1,
                "result": {
                    "resultType": "complete",
                    "content": [_text_part(f"{token} result chunk {step}")],
                    "structuredContent": {
                        "session_id": stable_session_id,
                        "task_id": stable_task_id,
                        "status": state,
                        "elapsed_ms": elapsed_ms,
                        "matches": [
                            {"file": f"{repo}/handler.py", "line": 40 + step, "score": 0.91}
                        ],
                    },
                    "isError": False,
                },
                "session": {"id": stable_session_id, "template_epoch": 1},
                "delta_profile": common_meta(i, "status"),
            }
        elif variant == 2:
            payload = {
                "protocol": "a2a",
                "event": "TaskStatusUpdateEvent",
                "taskId": stable_task_id,
                "contextId": stable_context_id,
                "final": state == "completed",
                "status": {
                    "state": state,
                    "message": {
                        "messageId": f"delta-status-{i:06d}",
                        "role": "agent",
                        "parts": [_text_part(f"{token} progress {progress}%")],
                    },
                    "timestamp": f"2026-07-04T18:{i % 60:02d}:00Z",
                },
                "session": {"id": stable_session_id, "template_epoch": 1},
                "delta_profile": common_meta(i, "status"),
            }
        elif variant == 3:
            payload = {
                "protocol": "a2a",
                "event": "TaskArtifactUpdateEvent",
                "taskId": stable_task_id,
                "contextId": stable_context_id,
                "append": True,
                "lastChunk": i + 10 >= count,
                "artifact": {
                    "artifactId": stable_artifact_id,
                    "name": "delta-diagnostic-summary",
                    "parts": [
                        _text_part(f"{token} artifact chunk {step}"),
                        {
                            "kind": "data",
                            "data": {
                                "repository": repo,
                                "p95_delta_ms": 20 + (i % 17),
                                "sample": step,
                            },
                            "metadata": {"schema": "diagnostic_summary.delta.v1"},
                        },
                    ],
                },
                "session": {"id": stable_session_id, "template_epoch": 1},
                "delta_profile": common_meta(i, "artifact"),
            }
        elif variant == 4:
            payload = {
                "protocol": "openai.responses",
                "type": "response.output_text.delta",
                "trace_id": stable_trace_id,
                "response_id": stable_response_id,
                "item_id": stable_item_id,
                "output_index": 0,
                "content_index": i,
                "delta": f"{token} ",
                "session": {"id": stable_session_id, "template_epoch": 1},
                "delta_profile": common_meta(i, "token"),
            }
        elif variant == 5:
            payload = {
                "protocol": "openai.responses",
                "type": "function_call_output",
                "trace_id": stable_trace_id,
                "call_id": f"delta-call-{i % 4:02d}",
                "output": _json_arguments(
                    ok=True,
                    session_id=stable_session_id,
                    task_id=stable_task_id,
                    rows=3 + (i % 7),
                    status=state,
                    elapsed_ms=elapsed_ms,
                    summary=f"{tool} emitted {token} delta {step}",
                ),
                "session": {"id": stable_session_id, "template_epoch": 1},
                "delta_profile": common_meta(i, "argument"),
            }
        elif variant == 6:
            payload = {
                "protocol": "local.agent",
                "schema": "local.agent.delta.status.v1",
                "trace_id": stable_trace_id,
                "task_id": stable_task_id,
                "delta": {
                    "op": "replace",
                    "path": "/status/state",
                    "value": state,
                    "previous": states[(i - 1) % len(states)],
                },
                "clock": {"lamport": seed * 1000 + i, "source": "delta-agent"},
                "route": stable_route,
                "session": {"id": stable_session_id, "template_epoch": 1},
                "delta_profile": common_meta(i, "status"),
            }
        elif variant == 7:
            payload = {
                "protocol": "local.agent",
                "schema": "local.agent.delta.tool_result.v1",
                "trace_id": stable_trace_id,
                "tool_call_id": f"delta-call-{i % 4:02d}",
                "delta": {
                    "op": "append",
                    "path": "/tool_results/-",
                    "value": {
                        "name": tool,
                        "ok": True,
                        "elapsed_ms": elapsed_ms,
                        "summary": f"{token} evidence {step}",
                    },
                },
                "route": stable_route,
                "session": {"id": stable_session_id, "template_epoch": 1},
                "delta_profile": common_meta(i, "artifact"),
            }
        elif variant == 8:
            payload = {
                "protocol": "agent.trace",
                "event": "step.delta",
                "trace_id": stable_trace_id,
                "span_id": f"delta-span-{i % 6:02d}",
                "task": {"id": stable_task_id, "session_id": stable_session_id},
                "values": {
                    "token": token,
                    "status": state,
                    "progress": progress,
                    "elapsed_ms": elapsed_ms,
                },
                "session": {"id": stable_session_id, "template_epoch": 1},
                "delta_profile": common_meta(i, "trace"),
            }
        else:
            payload = {
                "protocol": "local.agent",
                "schema": "local.agent.route_hint.v1",
                "trace_id": stable_trace_id,
                "route": {
                    "topic": stable_route,
                    "shard": f"{repo}-{i % 3}",
                    "priority": "high" if state == "input_required" else "normal",
                    "requires_decompression": False,
                },
                "hash_modifiers": {
                    "tenant": "bench",
                    "session_bucket": seed % 16,
                    "task_bucket": step,
                },
                "session": {"id": stable_session_id, "template_epoch": 1},
                "delta_profile": common_meta(i, "route"),
            }

        messages.append(payload)

    return messages


def build_structured_ai_messages(count: int, seed: int = 1729) -> list[dict[str, Any]]:
    """Build realistic structured AI-to-AI protocol messages.

    The corpus is synthetic and public-safe, but intentionally mirrors the
    repetitive shapes used by current AI systems: MCP JSON-RPC tool/resource
    traffic, A2A task/message/artifact updates, OpenAI Responses tool and
    structured-output items, and local agent runtime envelopes.
    """

    rng = random.Random(seed)
    tools = [
        "web_search",
        "read_file",
        "write_patch",
        "run_shell",
        "vector_lookup",
        "search_logs",
    ]
    agents = ["planner", "researcher", "coder", "reviewer", "executor", "summarizer"]
    repos = ["payments-api", "retrieval-worker", "aura-bridge", "policy-gateway"]
    cities = ["Austin", "Seattle", "San Jose", "Chicago", "Boston", "Denver"]
    states = ["submitted", "working", "input_required", "completed"]
    topics = ["latency", "retrieval", "rollout", "policy", "memory", "tooling"]
    messages: list[dict[str, Any]] = []

    for i in range(count):
        tool = tools[i % len(tools)]
        agent = agents[i % len(agents)]
        repo = repos[i % len(repos)]
        city = cities[i % len(cities)]
        topic = topics[i % len(topics)]
        trace_id = f"trace-{seed}-{i:05d}"
        task_id = f"task-{(i // 4):04d}"
        context_id = f"ctx-{i // 12:04d}"
        call_id = f"call_{i:06d}"
        message_id = f"msg-{i:06d}"
        artifact_id = f"artifact-{i:06d}"
        variant = i % 30
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
                            f"Investigate {topic} regression in {repo} for the {city} "
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
                            "additionalProperties": False,
                        },
                    }
                ],
                "text": {
                    "format": {
                        "type": "json_schema",
                        "name": "agent_plan",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "properties": {
                                "finding": {"type": "string"},
                                "evidence": {"type": "array", "items": {"type": "string"}},
                                "next_action": {"type": "string"},
                                "confidence": {"type": "number"},
                            },
                            "required": ["finding", "evidence", "next_action", "confidence"],
                            "additionalProperties": False,
                        },
                    }
                },
                "metadata": {"tenant": "bench", "task_id": task_id, "priority": i % 5},
            }
        elif variant == 1:
            payload = {
                "protocol": "openai.responses",
                "type": "response.output_item.done",
                "trace_id": trace_id,
                "item": {
                    "id": f"fc_{i:06d}",
                    "type": "function_call",
                    "call_id": call_id,
                    "name": tool,
                    "arguments": _json_arguments(
                        repository=repo,
                        path=f"services/{repo}/src/handler_{i % 9}.py",
                        query=f"timeout OR retry OR p95 city:{city}",
                        limit=20 + (i % 7),
                    ),
                },
            }
        elif variant == 2:
            payload = {
                "protocol": "openai.responses",
                "type": "function_call_output",
                "trace_id": trace_id,
                "call_id": call_id,
                "output": _json_arguments(
                    ok=True,
                    rows=5,
                    summary=f"{repo} has retry fanout warnings in {city}",
                    elapsed_ms=18 + (i % 37),
                ),
            }
        elif variant == 3:
            payload = {
                "protocol": "openai.responses",
                "type": "response.completed",
                "trace_id": trace_id,
                "response": {
                    "id": f"resp_{i:06d}",
                    "status": "completed",
                    "output": [
                        {
                            "type": "message",
                            "role": "assistant",
                            "content": [
                                {
                                    "type": "output_json",
                                    "json": {
                                        "finding": f"{topic} regression isolated in {repo}",
                                        "evidence": [
                                            f"logs://{repo}/{city}/{i % 24:02d}",
                                            f"trace://{trace_id}",
                                        ],
                                        "next_action": "run canary replay",
                                        "confidence": round(0.78 + (i % 10) / 100, 3),
                                    },
                                }
                            ],
                        }
                    ],
                },
            }
        elif variant == 4:
            payload = {
                "protocol": "openai.responses",
                "type": "response.output_text.delta",
                "trace_id": trace_id,
                "response_id": f"resp_{i // 4:06d}",
                "item_id": f"msg_{i // 3:06d}",
                "output_index": 0,
                "content_index": i % 6,
                "delta": f"{agent} sees {topic} evidence in {repo}; ",
            }
        elif variant == 5:
            payload = {
                "protocol": "openai.responses",
                "type": "response.web_search_call.completed",
                "trace_id": trace_id,
                "item": {
                    "id": f"ws_{i:06d}",
                    "type": "web_search_call",
                    "status": "completed",
                    "queries": [f"{repo} {topic} canary rollback"],
                },
                "annotations": [
                    {
                        "type": "url_citation",
                        "title": "Internal synthetic incident note",
                        "url": f"https://example.invalid/{repo}/{topic}/{i}",
                    }
                ],
            }
        elif variant == 6:
            payload = {
                "protocol": "mcp",
                "jsonrpc": "2.0",
                "id": i,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-11-25",
                    "capabilities": {"roots": {"listChanged": True}, "sampling": {}},
                    "clientInfo": {"name": "aura-corpus", "version": "0.1"},
                    "_meta": _mcp_meta(i),
                },
            }
        elif variant == 7:
            payload = {
                "protocol": "mcp",
                "jsonrpc": "2.0",
                "id": i,
                "method": "tools/list",
                "params": {"cursor": f"page-{i % 3}", "_meta": _mcp_meta(i)},
                "result": {
                    "resultType": "complete",
                    "tools": [
                        {
                            "name": tool,
                            "title": f"{tool.replace('_', ' ').title()} Tool",
                            "description": f"Operate on synthetic {repo} {topic} data.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "repository": {"type": "string"},
                                    "query": {"type": "string"},
                                    "limit": {"type": "integer", "x-mcp-header": "limit"},
                                },
                                "required": ["repository", "query"],
                            },
                        }
                    ],
                    "ttlMs": 300000,
                    "cacheScope": "public",
                },
            }
        elif variant == 8:
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
                    "_meta": _mcp_meta(i),
                },
            }
        elif variant == 9:
            payload = {
                "protocol": "mcp",
                "jsonrpc": "2.0",
                "id": i,
                "result": {
                    "resultType": "complete",
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
        elif variant == 10:
            payload = {
                "protocol": "mcp",
                "jsonrpc": "2.0",
                "id": i,
                "method": "resources/read",
                "params": {
                    "uri": f"repo://{repo}/services/{agent}/incident.md",
                    "_meta": _mcp_meta(i),
                },
                "result": {
                    "contents": [
                        {
                            "uri": f"repo://{repo}/services/{agent}/incident.md",
                            "mimeType": "text/markdown",
                            "text": f"# {repo} {topic}\n\nSynthetic incident context for {city}.",
                        }
                    ]
                },
            }
        elif variant == 11:
            payload = {
                "protocol": "mcp",
                "jsonrpc": "2.0",
                "id": i,
                "method": "prompts/get",
                "params": {
                    "name": "incident_review",
                    "arguments": {"repository": repo, "city": city, "topic": topic},
                    "_meta": _mcp_meta(i),
                },
                "result": {
                    "description": "Review an incident using logs, traces, and repository diffs.",
                    "messages": [
                        {
                            "role": "user",
                            "content": {
                                "type": "text",
                                "text": f"Review {repo} {topic} regression in {city}.",
                            },
                        }
                    ],
                },
            }
        elif variant == 12:
            payload = {
                "protocol": "mcp",
                "jsonrpc": "2.0",
                "method": "notifications/tools/list_changed",
                "params": {"reason": "deployment", "repository": repo, "_meta": _mcp_meta(i)},
            }
        elif variant == 13:
            payload = {
                "protocol": "mcp",
                "jsonrpc": "2.0",
                "id": i,
                "method": "sampling/createMessage",
                "params": {
                    "messages": [
                        {
                            "role": "user",
                            "content": {
                                "type": "text",
                                "text": f"Draft a safe mitigation summary for {repo}.",
                            },
                        }
                    ],
                    "maxTokens": 192,
                    "includeContext": "thisServer",
                    "_meta": _mcp_meta(i),
                },
            }
        elif variant == 14:
            payload = {
                "protocol": "a2a",
                "jsonrpc": "2.0",
                "id": i,
                "method": "message/send",
                "params": {
                    "message": {
                        "messageId": message_id,
                        "contextId": context_id,
                        "taskId": task_id,
                        "role": "user",
                        "parts": [
                            _text_part(
                                f"Agent {agent}, produce a remediation plan for {repo} "
                                "using only verified evidence."
                            ),
                            {
                                "kind": "data",
                                "data": {"repository": repo, "city": city, "topic": topic},
                                "metadata": {"schema": "incident_input.v1"},
                            },
                        ],
                        "metadata": {"trace_id": trace_id, "task_id": task_id},
                    },
                    "configuration": {"historyLength": 6, "blocking": False},
                },
            }
        elif variant == 15:
            payload = {
                "protocol": "a2a",
                "jsonrpc": "2.0",
                "id": i,
                "method": "message/stream",
                "params": {
                    "message": {
                        "messageId": message_id,
                        "contextId": context_id,
                        "role": "user",
                        "parts": [_text_part(f"Stream status for {repo} {topic}.")],
                    },
                    "configuration": {"historyLength": 4, "acceptedOutputModes": ["text/plain"]},
                },
            }
        elif variant == 16:
            payload = {
                "protocol": "a2a",
                "jsonrpc": "2.0",
                "id": i,
                "result": {
                    "id": task_id,
                    "contextId": context_id,
                    "kind": "task",
                    "status": {
                        "state": states[i % len(states)],
                        "message": {
                            "messageId": message_id,
                            "role": "agent",
                            "parts": [
                                _text_part(
                                    f"{agent} completed evidence pass {i % 5}; "
                                    f"confidence={0.72 + (i % 9) / 100:.2f}"
                                )
                            ],
                        },
                        "timestamp": f"2026-07-04T18:{i % 60:02d}:00Z",
                    },
                    "history": [],
                    "metadata": {"trace_id": trace_id, "repository": repo},
                },
            }
        elif variant == 17:
            payload = {
                "protocol": "a2a",
                "event": "TaskArtifactUpdateEvent",
                "taskId": task_id,
                "contextId": context_id,
                "append": True,
                "lastChunk": i % 5 == 0,
                "artifact": {
                    "artifactId": artifact_id,
                    "name": "diagnostic-summary",
                    "parts": [
                        _text_part("p95 latency increased after retry fanout change"),
                        {
                            "kind": "data",
                            "data": {
                                "repository": repo,
                                "city": city,
                                "p95_delta_ms": 32 + (i % 9),
                            },
                            "metadata": {"schema": "diagnostic_summary.v1"},
                        },
                    ],
                },
            }
        elif variant == 18:
            payload = {
                "protocol": "a2a",
                "jsonrpc": "2.0",
                "id": i,
                "method": "tasks/get",
                "params": {"id": task_id, "historyLength": 10, "metadata": {"trace_id": trace_id}},
                "result": {
                    "id": task_id,
                    "contextId": context_id,
                    "status": {"state": "working"},
                    "artifacts": [{"artifactId": artifact_id, "name": "diagnostic-summary"}],
                },
            }
        elif variant == 19:
            payload = {
                "protocol": "a2a",
                "event": "TaskStatusUpdateEvent",
                "taskId": task_id,
                "contextId": context_id,
                "final": False,
                "status": {
                    "state": "input_required",
                    "message": {
                        "messageId": message_id,
                        "role": "agent",
                        "parts": [
                            _text_part(
                                f"Need approval before running canary replay for {repo} in {city}."
                            )
                        ],
                    },
                },
            }
        elif variant == 20:
            payload = {
                "protocol": "local.agent",
                "schema": "local.agent.broker.envelope.v1",
                "topic": f"agents.{agent}.inbox",
                "partition": i % 4,
                "offset": i,
                "headers": {
                    "trace_id": trace_id,
                    "task_id": task_id,
                    "route": f"{agent}.{topic}",
                    "codec": "aura.aiwire",
                },
                "body": {
                    "type": "command",
                    "name": "continue_task",
                    "arguments": {"repository": repo, "city": city, "topic": topic},
                },
            }
        elif variant == 21:
            payload = {
                "protocol": "local.agent",
                "schema": "local.agent.session.handshake.v1",
                "trace_id": trace_id,
                "peer": {"id": agent, "runtime": "python", "version": "0.1"},
                "capabilities": {
                    "templates": True,
                    "delta_frames": True,
                    "resume": True,
                    "route_before_decompress": True,
                },
                "session": {
                    "id": f"session-{seed}-{i // 8:05d}",
                    "dictionary_epoch": i % 6,
                    "template_sha256": f"{(seed + i) % (16 ** 8):08x}",
                },
            }
        elif variant == 22:
            payload = {
                "protocol": "local.agent",
                "schema": "local.agent.delta.status.v1",
                "trace_id": trace_id,
                "task_id": task_id,
                "delta": {
                    "op": "replace",
                    "path": "/status/state",
                    "value": states[i % len(states)],
                    "previous": states[(i - 1) % len(states)],
                },
                "clock": {"lamport": i + 1000, "source": agent},
            }
        elif variant == 23:
            payload = {
                "protocol": "local.agent",
                "schema": "local.agent.delta.tool_result.v1",
                "trace_id": trace_id,
                "tool_call_id": call_id,
                "delta": {
                    "op": "append",
                    "path": "/tool_results/-",
                    "value": {
                        "name": tool,
                        "ok": True,
                        "elapsed_ms": 18 + (i % 37),
                        "summary": f"{tool} found {topic} evidence for {repo}",
                    },
                },
            }
        elif variant == 24:
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
        elif variant == 25:
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
        elif variant == 26:
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
        elif variant == 27:
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
        elif variant == 28:
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
        else:
            payload = {
                "protocol": "local.agent",
                "schema": "local.agent.route_hint.v1",
                "trace_id": trace_id,
                "route": {
                    "topic": f"agents.{agent}.events",
                    "shard": f"{repo}-{i % 4}",
                    "priority": "high" if i % 7 == 0 else "normal",
                    "requires_decompression": False,
                },
                "hash_modifiers": {
                    "tenant": "bench",
                    "repository": repo,
                    "task_bucket": i // 16,
                },
                "control": {
                    "kind": "session_template_update",
                    "epoch": i % 11,
                    "reason": "recurring message shape crossed threshold",
                },
            }

        messages.append(payload)

    rng.shuffle(messages)
    return messages
