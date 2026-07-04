# AI-to-AI LAN Benchmark - Mac to Z6 and Jetson Nanos

Date: 2026-07-04

## Setup

The benchmark used `tools/stress_ai_wire_roundtrip_z6.py` in bidirectional
request/response mode. The Mac ran the client. Each target ran the server. Each
codec had a 5 second window with a modeled 10 Mbps egress link in each
direction and a pipeline window of 128 in-flight request frames.

Host-specific LAN addresses are intentionally omitted from this public report.
The topology was one Mac client, one workstation-class Z6 target, and four
Jetson Nano-class ARM64 edge targets on the same local network.

Command shape:

```bash
PYTHONPATH=src python tools/stress_ai_wire_roundtrip_z6.py client \
  --host <target-ip> \
  --seconds 5 \
  --exchanges 5000 \
  --pipeline-window 128 \
  --link-mbps 10 \
  --codecs raw,zlib,aura,aiwire
```

Codec definitions:

- `raw`: canonical structured AI JSON frames, uncompressed.
- `zlib`: stateless zlib level 3 per frame.
- `aura`: `ProductionHybridCompressor` AURA path, ML selection disabled for a
  deterministic benchmark, per-frame.
- `aiwire`: AURA AIWire session codec with static AI JSON dictionary and live
  deflate history.

## Results

`Completed 5s` is verified request/response exchanges completed before the 5
second deadline. `Framed MiB moved` includes the benchmark's 4 byte frame
headers.

| Target | Codec | Completed 5s | ex/s | vs raw | Framed MiB moved | Framed saved | p95 ms | Backend |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Z6 workstation | raw | 8,777 | 1,755.4 | 1.00x | 9.98 | -0.7% | 73.7 | raw |
| Z6 workstation | zlib | 14,952 | 2,990.4 | 1.70x | 10.00 | 40.5% | 43.0 | zlib |
| Z6 workstation | aura | 6,767 | 1,353.4 | 0.77x | 7.73 | -0.7% | 104.3 | aura |
| Z6 workstation | aiwire | 55,337 | 11,067.4 | 6.30x | 8.21 | 86.7% | 11.7 | python |
| Nano edge 1 | raw | 8,778 | 1,755.6 | 1.00x | 9.98 | -0.7% | 73.3 | raw |
| Nano edge 1 | zlib | 14,952 | 2,990.4 | 1.70x | 10.00 | 40.5% | 44.2 | zlib |
| Nano edge 1 | aura | 3,559 | 711.8 | 0.41x | 4.14 | -0.7% | 263.6 | aura |
| Nano edge 1 | aiwire | 20,204 | 4,040.8 | 2.30x | 3.01 | 86.7% | 45.1 | python |
| Nano edge 2 | raw | 8,777 | 1,755.4 | 1.00x | 9.98 | -0.7% | 73.2 | raw |
| Nano edge 2 | zlib | 14,951 | 2,990.2 | 1.70x | 10.00 | 40.5% | 43.0 | zlib |
| Nano edge 2 | aura | 3,642 | 728.4 | 0.41x | 4.23 | -0.7% | 227.9 | aura |
| Nano edge 2 | aiwire | 21,028 | 4,205.6 | 2.40x | 3.13 | 86.7% | 34.4 | python |
| Nano edge 3 | raw | 8,727 | 1,745.4 | 1.00x | 9.92 | -0.7% | 73.2 | raw |
| Nano edge 3 | zlib | 14,951 | 2,990.2 | 1.71x | 10.00 | 40.5% | 43.0 | zlib |
| Nano edge 3 | aura | 3,628 | 725.6 | 0.42x | 4.21 | -0.7% | 229.2 | aura |
| Nano edge 3 | aiwire | 19,882 | 3,976.4 | 2.28x | 2.96 | 86.7% | 40.8 | python |
| Nano edge 4 | raw | 8,724 | 1,744.8 | 1.00x | 9.92 | -0.7% | 73.3 | raw |
| Nano edge 4 | zlib | 14,951 | 2,990.2 | 1.71x | 10.00 | 40.5% | 43.0 | zlib |
| Nano edge 4 | aura | 3,617 | 723.4 | 0.41x | 4.20 | -0.7% | 217.8 | aura |
| Nano edge 4 | aiwire | 22,435 | 4,487.0 | 2.57x | 3.34 | 86.7% | 33.3 | python |

## Nano Average

| Codec | Completed 5s | vs raw | Framed MiB moved | Framed saved | p95 ms |
|---|---:|---:|---:|---:|---:|
| raw | 8,752 | 1.00x | 9.95 | -0.7% | 73.3 |
| zlib | 14,951 | 1.71x | 10.00 | 40.5% | 43.3 |
| aura | 3,612 | 0.41x | 4.19 | -0.7% | 234.6 |
| aiwire | 20,887 | 2.39x | 3.11 | 86.7% | 38.4 |

## Readout

AIWire is the clear winner for AI-to-AI structured message streams. On Z6, it
moved 55,337 verified exchanges in 5 seconds, 6.30x raw and 3.70x zlib. Across
the four Jetson Nanos, it averaged 20,887 verified exchanges in 5 seconds,
2.39x raw and 1.40x zlib.

The generic `aura` compressor path is not a good fit for this small-message
request/response workload as currently wired. It is effectively neutral on
wire size and CPU-bound on the Nanos. The specialized AIWire path is the
correct AURA method for high-volume AI-to-AI structured traffic.
