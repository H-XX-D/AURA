# AURA CUDA Native Backend

This backend builds a small CUDA C shared library used by AURA's optional
`CudaNativeBackend`. It is intentionally dependency-free: Python loads the
library with `ctypes`, so AURA still imports and runs on machines without CUDA.

Current native primitives:

- `byte_histogram(data)`: 256-bin byte histogram.
- `shannon_entropy(data)`: byte-level Shannon entropy.
- `rolling_hash3(data)`: FNV-1a hashes for every 3-byte window.
- `lz_match_candidates(data, window_size, min_match, max_match)`: bounded,
  non-overlapping LZ candidates compatible with BRIO's decoder.

Build on a CUDA host:

```bash
cd native/cuda
NVCC=/usr/local/cuda-13.3/bin/nvcc make install
```

Runtime loading order:

1. `AURA_CUDA_LIBRARY=/path/to/libaura_cuda.so`
2. `src/aura_compression/native/libaura_cuda.so`
3. `libaura_cuda.so` from the platform dynamic linker path

Set `AURA_DISABLE_CUDA=1` to force CPU fallback.

BRIO's CUDA LZ path is opt-in while it remains experimental:

```bash
AURA_ENABLE_CUDA_BRIO=1 \
AURA_CUDA_BRIO_MIN_BYTES=8192 \
AURA_CUDA_BRIO_WINDOW_SIZE=1024 \
PYTHONPATH=src python3 your_script.py
```

`AURA_CUDA_BRIO_WINDOW_SIZE` defaults to BRIO's 32 KiB window and is capped at
that value. Smaller windows reduce GPU work and can be faster for repeated
record-style data.
