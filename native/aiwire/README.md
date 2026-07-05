# Native AIWire Backend

This directory builds the optional C++ `libaura_aiwire` shared library used by
the Python AIWire backend when `use_native=True`, `--backend native`, or
`AURA_AIWIRE_NATIVE=1` is selected.

Build and install the library into the Python package tree:

```bash
make -C native/aiwire install
```

Build, install, and run native interop checks:

```bash
make -C native/aiwire check
```

The check target runs:

```bash
python tools/check_aiwire_native_backend.py --require-native
```

For machine-to-machine benchmark preparation on the Z6 or Jetson targets, use:

```bash
python tools/check_aiwire_native_backend.py --build --require-native --messages 32
```

The JSON report includes platform details, the loaded library path/version,
dictionary identity, native AIWire round-trip status, Python/native interop, and
native AIToken plus AIToken+AIWire checks.
