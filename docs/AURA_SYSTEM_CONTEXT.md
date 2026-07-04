# AURA System Context

Date: 2026-07-04

This document is the public-facing project context for the current repository.
Older notes in this repo described broader economic projections and legacy file
layouts. The current repo should be understood more narrowly:

**AURA is an experimental compression toolkit whose strongest validated use case
is AIWire, a session codec for high-volume structured AI-to-AI messages over
normal networks.**

## Current Direction

AI systems increasingly exchange structured messages instead of plain text:

- MCP-style JSON-RPC tool calls
- A2A task and artifact updates
- OpenAI-style tool calls and structured outputs
- Local agent handoffs, traces, reviews, and memory messages
- Repeated operational logs and status events

Those messages repeat the same keys and shapes thousands of times. AIWire uses
that repetition through a static AI protocol dictionary plus live session
history.

## What Is Proven Right Now

The best-supported path is:

```text
structured message mapping
    -> canonical JSON bytes
    -> AIWire session encoder
    -> ordinary network transport
    -> AIWire session decoder
    -> original structured message
```

Verified local capabilities:

- AIWire round-trips ordered frame streams.
- AIWire accepts structured Python mappings and restores them through JSON
  decode helpers.
- AIWire beats stateless zlib on the generated AI protocol corpus.
- AIWire has a working handshake negotiation model.
- AIWire has optional native backend detection and interoperability tests.
- The LAN benchmark shows AIWire outperforming raw JSON and stateless zlib for
  high-volume request/response traffic.

See:

- [`tests/test_ai_wire.py`](../tests/test_ai_wire.py)
- [`docs/perf/ai_to_ai_lan_benchmark_2026-07-04.md`](perf/ai_to_ai_lan_benchmark_2026-07-04.md)

## Benchmark Summary

In a 5 second modeled 10 Mbps request/response benchmark:

- Z6 target: AIWire completed 55,337 exchanges versus 8,777 raw and 14,952 zlib.
- Jetson Nano average: AIWire completed 20,887 exchanges versus 8,752 raw and
  14,951 zlib.

This benchmark supports a specific conclusion: **AIWire is the right AURA path
for small, repetitive AI-to-AI messages.**

It does not prove that every AURA method is faster than standard compressors.
The generic `ProductionHybridCompressor` path was slower on this small-message
workload and should be treated as research infrastructure until improved.

## Main Components

### AIWire

Files:

- [`src/aura_compression/ai_wire.py`](../src/aura_compression/ai_wire.py)
- [`src/aura_compression/ai_wire_messages.py`](../src/aura_compression/ai_wire_messages.py)

Purpose:

- Session compression for AI protocol frames
- Canonical JSON message handling
- Dictionary negotiation
- Native backend interop when available

### Hybrid Compressor

Files:

- [`src/aura_compression/compressor.py`](../src/aura_compression/compressor.py)
- [`src/aura_compression/compressor_refactored.py`](../src/aura_compression/compressor_refactored.py)
- [`src/aura_compression/compression_strategy_manager.py`](../src/aura_compression/compression_strategy_manager.py)

Purpose:

- Research into template-based and semantic compression
- Large payloads, logs, and structured data experiments
- Strategy selection and metadata experiments

### Metadata and Routing

Files:

- [`src/aura_compression/metadata_sidechannel.py`](../src/aura_compression/metadata_sidechannel.py)
- [`src/aura_compression/router.py`](../src/aura_compression/router.py)

Purpose:

- Classify compressed messages
- Route or screen traffic using metadata
- Explore audit-friendly compression boundaries

### Benchmarks and Tools

Files:

- [`tools/stress_ai_wire_roundtrip_z6.py`](../tools/stress_ai_wire_roundtrip_z6.py)
- [`tools/benchmark_ai_wire_z6.py`](../tools/benchmark_ai_wire_z6.py)
- [`tools/compress_large_file.py`](../tools/compress_large_file.py)

Purpose:

- Measure AIWire versus raw, zlib, and generic AURA paths
- Run LAN request/response stress tests
- Exercise large-file container experiments

## What To Avoid Claiming

Do not present AURA as:

- A production-ready compression standard
- A drop-in gzip/zstd/brotli replacement
- A universally faster compressor
- A complete security layer
- A finished edge-device runtime

The strongest accurate claim is narrower and more useful:

> AURA AIWire is a working, benchmarked session codec for repetitive structured
> AI-to-AI messages over normal networks.

## Public Documentation Rule

Keep public docs focused on reproducible behavior, benchmark method, and code
entry points. Avoid publishing host-specific private details such as local IP
addresses, private usernames, private machine names, secrets, tokens, or
non-reproducible environment assumptions.
