# AIWire Resume Cache

AIWire resume is the future-connection handshake for peers that have already
agreed on session dictionary structure. The wire protocol is defined in
[AIWire v1 Protocol Spec](aiwire_v1_spec.md); this page covers the persistent
local cache used by AURA's Python implementation.

## Purpose

During a long agent relationship, peers discover recurring message shapes and
ACK append-only session dictionary diffs. A later connection to the same peer
can skip relearning that structure if both sides can prove they still recognize
the same dictionary state hash.

The resume cache stores:

- Peer ID and app namespace.
- Session dictionary epoch.
- Static dictionary SHA-256 and delta version.
- Canonical session template shapes.
- The resulting session dictionary state hash.
- Local metadata such as label and update timestamp.

It does not store auth keys, credentials, transport tokens, or message payloads.
Authenticated deployments pass the shared auth key into the Python API when
building or verifying resume messages.

## Safety Rules

- Resume is only an optimization. A failed resume falls back to a fresh
  structure handshake.
- A selected `resume_state_hash` must resolve to exactly one local cache entry
  for the offered `peer_id` and `app_namespace`.
- Static dictionary hash and delta version must match before the cache entry is
  usable.
- Cache writes are local JSON files written atomically with `0600` file mode on
  supported platforms.
- Mission-critical control messages stay explicit system messages; they are not
  hidden inside cached session dictionary entries.

## Python API

```python
from aura_compression import AIWireResumeCache

auth_key = b"shared-session-key"
templates = {128: "agent {0} calls tool {1}", 129: "task {0} status {1}"}

client_cache = AIWireResumeCache("client-resume-cache.json")
server_cache = AIWireResumeCache("server-resume-cache.json")

client_cache.put_state(
    peer_id="nano-engineer",
    app_namespace="aura-cluster",
    session_templates=templates,
    epoch=2,
)
server_cache.put_state(
    peer_id="nano-engineer",
    app_namespace="aura-cluster",
    session_templates=templates,
    epoch=2,
)

hello = client_cache.build_resume_hello(
    peer_id="nano-engineer",
    app_namespace="aura-cluster",
    auth_key=auth_key,
)
response = server_cache.negotiate_resume(hello, auth_key=auth_key)
entry = client_cache.verify_resume_response(hello, response, auth_key=auth_key)
```

After `verify_resume_response` returns an entry, the caller may rebuild its
AIWire session encoders/decoders using `entry.session_templates` and
`entry.epoch`. If verification fails, the caller must discard resume and run the
normal handshake/dictionary-diff path.

## CLI

The package installs `aura-aiwire-resume-cache`:

```bash
aura-aiwire-resume-cache --cache ./resume.json put \
  --peer-id nano-engineer \
  --app-namespace aura-cluster \
  --session-templates ./templates.json \
  --epoch 2

aura-aiwire-resume-cache --cache ./resume.json hello \
  --peer-id nano-engineer \
  --app-namespace aura-cluster \
  --output hello.json

aura-aiwire-resume-cache --cache ./resume.json negotiate \
  --hello hello.json \
  --output response.json

aura-aiwire-resume-cache --cache ./resume.json verify \
  --hello hello.json \
  --response response.json
```

The CLI intentionally omits auth-key arguments so secrets are not exposed in
shell history or process listings. Use the Python API when the resume messages
need HMAC protection.

By default, the cache path is:

```text
$AURA_AIWIRE_RESUME_CACHE
$XDG_CACHE_HOME/aura/aiwire_resume_cache.json
~/.cache/aura/aiwire_resume_cache.json
```

The first configured/default path in that order is used.
