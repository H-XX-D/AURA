# CUDA, FPGA, and Solver Acceleration

AURA should keep acceleration split by what each device is good at:

- CUDA: bulk byte histograms, entropy scoring, vector/tensor quantization, and
  other high-throughput kernels that benefit from wide parallelism.
- FPGA: deterministic streaming primitives such as rolling hashes, chunk-boundary
  detection, LZ/Grain match candidates, byte histograms, and template-ID lookup.
- Solvers: policy optimization around the codecs, not inner-loop compression.
  Useful solver outputs include template subsets, chunk sizes, entropy thresholds,
  CPU/CUDA/FPGA routing rules, and latency-vs-ratio profiles.

The current CUDA backend starts with deterministic primitives that are easy to
verify against CPU reference output:

- byte histograms and entropy scoring for strategy selection
- 3-byte rolling hashes for chunk/match preprocessing
- bounded non-overlapping LZ match candidates for BRIO-compatible tokens

BRIO's CUDA LZ path is currently opt-in through `AURA_ENABLE_CUDA_BRIO=1`.
This keeps the default codec stable while the accelerated path is benchmarked
across more payload classes.

Z6 benchmark snapshot, using the RTX 5060 Ti with CUDA 13.3:

| Workload | CPU Python | CUDA native | Speedup |
| --- | ---: | ---: | ---: |
| rolling hash3, 1 MiB | 418.23 ms | 81.22 ms | 5.15x |
| LZ candidates, 64 KiB, window 1024 | 1172.60 ms | 14.10 ms | 83.18x |
| BRIO repeated records, 16 KiB | 34.59 ms | 5.20 ms | 6.65x |
| BRIO repeated records, 64 KiB | 277.76 ms | 17.19 ms | 16.16x |

The first entropy-only CUDA hook did not speed up full compression because
AURA sampled entropy on small buffers and still spent most compression time in
Python BRIO tokenization. Moving match candidate discovery to CUDA changes the
end-to-end behavior for repetitive data, but this is still workload-dependent.

Recommended next device ABI:

```text
AURA work unit
  input: payload bytes or shared buffer address
  features requested: histogram | entropy | rolling_hash | template_probe
  constraints: max_latency_us, max_device_memory, preserve_lossless
  output: feature vector + device timing + confidence/validity flags
```

The solver should emit a compression profile consumed by AURA's strategy manager:

```text
profile = {
  template_ids: [...],
  chunk_size: ...,
  entropy_cutoffs: {...},
  route: {small: cpu, medium: cuda, stream: fpga},
}
```

Do not move Python semantic orchestration wholesale into FPGA. Keep the Python
control plane, use CUDA/FPGA for narrow kernels, and let solvers tune policy.
