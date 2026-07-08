# AIWire Dictionary Evolution

AIWire dictionary evolution has two separate jobs:

1. Prove that peers agree on the current protocol, static dictionary, zlib
   parameters, delta version, session dictionary state, and control LUT.
2. Add new session-local structure only through explicit diffs that are ACKed
   before either side encodes against the new state.

The first job is handled by an AIWire compatibility manifest. The manifest is a
stable JSON record with:

- AIWire protocol versions and delta versions
- static dictionary catalog version, catalog hash, SHA-256, byte size, and
  FNV-1a64
- zlib window, memory level, and flush mode
- fallback codecs
- session template catalog version, catalog hash, template hash, count, epoch,
  and session dictionary state hash
- routine-control LUT hash, count, and epoch
- hard safety limits for template count, template bytes, total session
  dictionary bytes, diff additions, and LUT entries

Generate the local manifest:

```bash
aura-aiwire-compatibility --output /tmp/aura-aiwire-compat.json
```

Include a known session dictionary:

```bash
cat > /tmp/session-templates.json <<'JSON'
{
  "128": "agent {0} calls tool {1}",
  "129": "task {0} status {1}"
}
JSON

aura-aiwire-compatibility \
  --session-templates /tmp/session-templates.json \
  --session-template-epoch 1 \
  --session-template-catalog-version tenant-alpha-templates-v1 \
  --output /tmp/aura-aiwire-session-compat.json
```

Compare a peer manifest:

```bash
aura-aiwire-compatibility \
  --session-templates /tmp/session-templates.json \
  --session-template-epoch 1 \
  --session-template-catalog-version tenant-alpha-templates-v1 \
  --peer-manifest /tmp/peer-aiwire-compat.json \
  --no-fallback
```

The checker selects `aiwire` only when the compatibility state matches. If
fallback is allowed and both peers advertise a common fallback, it selects the
first local fallback codec and records the AIWire rejection reason. With
`--no-fallback`, mismatches return exit code `2`.

Static dictionary and session-template catalog versions are operator-facing
labels carried beside content hashes. They let a deployment fail closed when a
peer is on a different release catalog even if the raw hashes are otherwise
inspectable. Session-template catalog metadata is digest-only; template patterns
remain in the explicit `--session-templates` input and are not duplicated in the
catalog hash fields.

The manifest does not replace the live handshake. It is a release, deployment,
and startup preflight artifact. `aura-aiwire-compatibility` can compare manifests
offline, while the explicit `aura-proxy` startup path and transport examples now
exchange and verify the manifest before semantic frames move. The live handshake
still proves the session before data flows, and session dictionary updates still
require the diff/ACK path described in
[AIWire session dictionary safety](aiwire_session_dictionary.md).

## Corpus-Driven Dictionary Candidates

Static dictionary changes remain compatibility breaks, so generation is a
proposal step, not an automatic protocol mutation. The package installs
`aura-aiwire-dictionary-generate` to analyze the public fixture corpus and emit
a deterministic candidate artifact:

```bash
aura-aiwire-dictionary-generate \
  --fixture-corpus fixtures/aiwire_sessions/public_session_corpus_v1.json \
  --max-entries 128 \
  --output /tmp/aura-aiwire-dictionary-candidates.json \
  --dictionary-output /tmp/aura-aiwire-candidate.dict
```

The JSON report records:

- source fixture schema, session count, message count, and corpus summary
- the current pinned AIWire v1 static dictionary SHA-256, FNV-1a64, and byte size
- ranked candidate terms with byte length, occurrence count, frame count,
  estimated saved bytes, source handles, and whether the term already exists in
  the pinned static dictionary
- candidate dictionary byte size, SHA-256, FNV-1a64, and term count

The raw `.dict` file is suitable for offline zlib experiments and future
combined-vs-protocol-specific dictionary benchmarks. It is intentionally not
wired into `AI_WIRE_STATIC_DICTIONARY`; a new static dictionary still needs a
versioned compatibility manifest, benchmark evidence, and an explicit release
decision.

Compare generated dictionaries against the pinned v1 static dictionary:

```bash
PYTHONPATH=src python tools/compare_aiwire_dictionaries.py \
  --fixture-corpus fixtures/aiwire_sessions/public_session_corpus_v1.json \
  --json-output docs/perf/aiwire_dictionary_matrix_2026-07-08.json \
  --markdown-output docs/perf/aiwire_dictionary_matrix_2026-07-08.md
```

The first matrix report is
[AIWire Dictionary Comparison Matrix](perf/aiwire_dictionary_matrix_2026-07-08.md).
It compares the current static dictionary, a combined generated candidate
dictionary, and protocol-specific generated dictionaries. Candidate dictionaries
are marked as candidate-only in the compatibility matrix until a release pins a
new dictionary hash.

## Private Application Dictionary Extensions

Private deployments can add local zlib dictionary bytes without committing those
terms to the public repo. The extension bytes stay local; compatibility
manifests and live handshakes carry only digest metadata:

```bash
aura-aiwire-compatibility \
  --dictionary-extension /etc/aura/tenant-alpha.dict \
  --output /tmp/aura-aiwire-tenant-alpha-compat.json
```

Each extension record includes a name, byte size, SHA-256, and FNV-1a64. The
manifest also includes a canonical hash of the extension metadata list. Peers
must advertise the same extension metadata before AIWire is selected; otherwise
the checker returns a `dictionary_extension_*` mismatch reason and either fails
closed or selects an explicit fallback if one is allowed.

Runtime callers pass the same private bytes to both sides of the session:

```python
from pathlib import Path

from aura_compression import AIWireSessionDecoder, AIWireSessionEncoder

extension = Path("/etc/aura/tenant-alpha.dict").read_bytes()

encoder = AIWireSessionEncoder(dictionary_extension_bytes=[extension])
decoder = AIWireSessionDecoder(dictionary_extension_bytes=[extension])
```

This is intentionally deployment-local. Promoting an extension into the public
static dictionary still requires a versioned compatibility manifest, benchmark
evidence, and an explicit release decision.

## Safety Rules

- Static dictionary changes are compatibility breaks unless the peer explicitly
  selects a fallback.
- Static dictionary and session-template catalog versions must match for AIWire
  selection when those catalogs are required.
- Private dictionary extensions are selected only when extension metadata
  matches; extension bytes are never serialized into compatibility artifacts.
- Matching template hashes are not enough for resume; the session dictionary
  state hash also includes the epoch, static dictionary hash, and delta version.
- A template ID is append-only within a session dictionary. Changing a shape
  requires a new ID.
- Senders must not encode against a proposed dictionary diff until the receiver
  ACK verifies the exact next state hash.
- Mission-critical control remains explicit system control and is not folded
  into routine LUT entries.
