# AURA API Stability

AURA exposes two deliberate Python API levels.

## Stable AIWire v1 API

New protocol integrations should import from `aura_compression.aiwire`.
Symbols exported in that module follow semantic-versioning compatibility for
the AURA 2.x package line. AIWire's independent on-wire version remains
`AI_WIRE_VERSION`.

```python
from aura_compression.aiwire import AIWireSessionDecoder, AIWireSessionEncoder

encoder = AIWireSessionEncoder()
decoder = AIWireSessionDecoder()
frame = encoder.compress_frame(b'{"jsonrpc":"2.0","id":1}')
assert decoder.decompress_frame(frame) == b'{"jsonrpc":"2.0","id":1}'
```

The package-root imports, such as
`from aura_compression import AIWireSessionEncoder`, remain compatible aliases.
They are retained because earlier AURA releases documented them, but the root
also contains research APIs and is not the preferred discovery surface.

## Experimental Research API

BRIO, AIToken, generic hybrid compression, metadata sidechannels, template
discovery, ML strategy selection, and CUDA experiments are available from
`aura_compression.research`. Their formats, performance, and Python signatures
may change between minor releases as evidence develops.

An API moving from research into the stable facade requires:

1. A documented interoperability or behavioral contract.
2. Focused round-trip, failure-mode, and public-import tests.
3. Evidence on a deterministic public fixture.
4. An explicit compatibility and deprecation plan.

## Internal Modules

Modules with a leading underscore are implementation details. Direct imports
from historical modules such as `aura_compression.ai_wire` remain possible for
compatibility, but only the `aura_compression.aiwire` facade defines the stable
application contract.
