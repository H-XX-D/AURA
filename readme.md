# AURA Compression Toolkit

AURA is an experimental, Python-first playground for hybrid compression. It mixes
template‑aware encoders, semantic heuristics, and audit-friendly metadata so you
can explore how structured traffic (API chatter, AI↔AI messages, log streams)
behaves under different strategies. The project is **not production-ready**, but
it now ships with a lean test suite and CLI tooling that make local experiments
straightforward.

---

## TL;DR

|                       | Status                                                                 |
|-----------------------|------------------------------------------------------------------------|
| Vision                | Efficient, auditable compression tuned for repetitive, structured text |
| Current maturity      | Alpha — safe for prototyping only                                      |
| Runtime support       | CPython ≥ 3.10 (pure Python, no native deps)                           |
| Test coverage         | ~44 % (core pipelines + CLI smoke tests)                               |
| License               | Apache 2.0 (see LICENSE for patent notice)                             |

---

## Installation

```bash
git clone https://github.com/hendrixx-cnc/AURA.git
cd AURA
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

The `dev` extra installs `pytest`, coverage tooling, and linters.

---

## Quick Start (Python API)

```python
from aura_compression.compressor_refactored import ProductionHybridCompressor

compressor = ProductionHybridCompressor(
    enable_aura=False,          # disable background discovery worker
    enable_fast_path=True,
    enable_audit_logging=False,
    template_sync_interval_seconds=None,
)

message = "Order 42: status=ready"
payload, method, metadata = compressor.compress(message)
restored = compressor.decompress(payload)

assert restored == message
print(method.name, metadata["ratio"])
```

### When does it shine?

- You control both ends of the link (AI ↔ AI, microservices, etc.)
- Payloads are verbose but structured (logs, JSON, templated replies)
- You’re comfortable tuning template libraries / cache policy

### When to avoid it

- Need wire compatibility with gzip/zstd/brotli
- Response time budgets are tight (large-file compression is slow)
- You cannot ship persistent template state alongside payloads

---

## Large-File CLI

The `tools/compress_large_file.py` script provides a streaming container format.
It records chunk metadata (including template usage) so decompression works on a
fresh machine.

```bash
# Compress with a progress bar and write stats to JSON
python tools/compress_large_file.py compress \
  --input "/path/to/enwik8" \
  --output "/path/to/enwik8.aura" \
  --chunk-size 64K \
  --progress bar \
  --stats-format json \
  --stats-file stats/compress.json

# Round-trip integrity check without writing output
python tools/compress_large_file.py verify \
  --input "/path/to/enwik8.aura" \
  --progress percent

# Inspect container metadata (headers, sample chunks, template IDs)
python tools/compress_large_file.py info \
  --input "/path/to/enwik8.aura" \
  --max-chunks 5 \
  --stats-format table
```

Key switches:

| Flag               | Description                                            |
|--------------------|--------------------------------------------------------|
| `--chunk-size`     | Bytes or suffixed value (`256K`, `4M`, …)              |
| `--progress`       | `auto`, `bar`, `percent`, `none`                       |
| `--stats-format`   | `table` (default) or `json`                            |
| `--stats-file`     | Path to persist stats output (useful in CI)            |

---

## Synthetic Network Smoke Test

To sanity-check the compressor against AI‑style traffic:

```bash
pytest tests/test_network_simulation_smoke.py -q
```

The generator streams ~120 messages (API calls, logs, chat replies, binary blobs)
and asserts:

- Round-trip fidelity for every payload
- Multiple compression strategies selected
- Binary semantic templates triggered at least once
- Average compression ratio stays sensible (>0.5)

Use this as a starting point when tailoring the system to your own message mix.

---

## Testing & Coverage

```bash
pytest -q                # fast path (~40 s)
pytest --cov=src --cov=tools --cov-report=term-missing
```

Current suite highlights:

- `tests/test_cli_utilities.py` — input parsing, progress modes, container inspection
- `tests/test_core_components.py` — basic round-trip compressor + template matching
- `tests/test_network_simulation_smoke.py` — synthetic AI/network workload

Large areas of the codebase remain untested (BRIO internals, ML selector, legacy
tools). Treat reported coverage as a proxy for explored functionality, not as a
production safety net.

---

## Roadmap Snapshot

- ✅ Streamlined large-file CLI with inspect/verify subcommands
- ✅ Lean regression tests to keep core behavior honest
- 🔜 Refactor BRIO and ML pipelines into testable, modular units
- 🔜 Benchmark suite vs. gzip/zstd/brotli on realistic corpora
- 🔜 Documentation on template discovery + SQLite persistence internals

---

## Contributing

1. Open an issue describing your proposal.
2. Fork the repo and create a feature branch.
3. Keep changes focused; add tests when practical.
4. Run `pytest -q` before submitting your PR.

Helpful areas:

- Improving template discovery robustness (error handling, logging)
- Instrumentation and profiling of large-file compression
- Type hints / static analysis for critical modules
- Benchmarks and data-driven comparisons

---

## License & Patents

Licensed under Apache 2.0. The project references patent-pending techniques; the
open-source distribution grants a royalty-free license for evaluation and
non-commercial use. See `LICENSE` for full text and obligations.

---

## Contact

- Author: Todd Hendricks — `todd@auraprotocol.org`
- Issues & discussions: [GitHub Issues](https://github.com/hendrixx-cnc/AURA/issues)

If you do end up using AURA in research or prototyping, feedback on data sets,
compression ratios, and pain points is greatly appreciated.
