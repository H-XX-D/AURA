# AIWire Replay Log

AIWire replay logs are deterministic JSONL audit artifacts for benchmark and
lab runs. They do not replace the transport. They capture the benchmark
settings, fixture digests, negotiated session state, peer probes, aggregate
rows, and per-codec result rows so a run can be inspected or compared offline.

Each line is one JSON object:

```json
{
  "schema": "aura.aiwire.replay_log.v1",
  "sequence": 0,
  "record_type": "header",
  "payload_sha256": "<sha256 of canonical payload>",
  "payload": {}
}
```

The payload hash is computed over canonical JSON using sorted keys and compact
separators. Readers should reject logs with sequence gaps, unsupported schema
values, or payload hash mismatches.

## Record Types

- `header`: source artifact identity, input kind, settings, and record counts.
- `fixture_replay`: public fixture corpus digests and template mode.
- `nary_negotiation`: accepted n-ary AIWire contract for a multi-peer run.
- `target`: target index and label.
- `peer_probe`: per-target handshake probe summary.
- `aggregate_result`: n-ary aggregate summary by codec.
- `result`: per-codec or per-target benchmark row, including a compact summary
  and the original row payload.

## Convert a Benchmark

```bash
PYTHONPATH=src python tools/write_aiwire_replay_log.py \
  /tmp/aura_nary_fixture_replay.json \
  --output /tmp/aura_nary_fixture_replay.jsonl
```

The converter accepts existing outputs from `tools/stress_ai_wire_roundtrip_z6.py`
and `tools/run_aiwire_network_suite.py`. The resulting JSONL file is stable
enough to diff across commits, archive with perf reports, or attach to a
cross-machine lab note.

Replay logs may contain hostnames, target labels, or private deployment paths
if the source artifact contains them. Keep public reports scrubbed before
committing logs.
