# AIWire Dictionary Evolution

AIWire dictionary evolution has two separate jobs:

1. Prove that peers agree on the current protocol, static dictionary, zlib
   parameters, delta version, session dictionary state, and control LUT.
2. Add new session-local structure only through explicit diffs that are ACKed
   before either side encodes against the new state.

The first job is handled by an AIWire compatibility manifest. The manifest is a
stable JSON record with:

- AIWire protocol versions and delta versions
- static dictionary SHA-256, byte size, and FNV-1a64
- zlib window, memory level, and flush mode
- fallback codecs
- session template hash, count, epoch, and session dictionary state hash
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
  --output /tmp/aura-aiwire-session-compat.json
```

Compare a peer manifest:

```bash
aura-aiwire-compatibility \
  --session-templates /tmp/session-templates.json \
  --session-template-epoch 1 \
  --peer-manifest /tmp/peer-aiwire-compat.json \
  --no-fallback
```

The checker selects `aiwire` only when the compatibility state matches. If
fallback is allowed and both peers advertise a common fallback, it selects the
first local fallback codec and records the AIWire rejection reason. With
`--no-fallback`, mismatches return exit code `2`.

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

## Safety Rules

- Static dictionary changes are compatibility breaks unless the peer explicitly
  selects a fallback.
- Matching template hashes are not enough for resume; the session dictionary
  state hash also includes the epoch, static dictionary hash, and delta version.
- A template ID is append-only within a session dictionary. Changing a shape
  requires a new ID.
- Senders must not encode against a proposed dictionary diff until the receiver
  ACK verifies the exact next state hash.
- Mission-critical control remains explicit system control and is not folded
  into routine LUT entries.
