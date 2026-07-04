# AIWire Session Dictionary Safety

AIWire treats discovered structure as replicated session state. A discovered
template is not usable on the wire until both peers have validated and ACKed the
same session dictionary diff.

This document explains the safety model. The normative protocol fields and
wire-level contract are in [AIWire v1 Protocol Spec](aiwire_v1_spec.md).

## State Model

AIWire has two structure layers:

- Static dictionary: protocol terms built into the runtime.
- Session dictionary: templates discovered during a live agent exchange.

The session dictionary is addressed by:

```text
epoch
state_hash = sha256(canonical(session_dictionary_state))
```

The canonical state includes the AURA protocol version, delta version, static
dictionary hash, epoch, template IDs, template patterns, and per-template
pattern hashes.

## Safe Update Flow

When discovery identifies recurring structure, the sender proposes an
append-only diff:

```text
DICT_DIFF
  session_id
  epoch = current_epoch + 1
  previous_state_hash
  next_state_hash
  additions[]
  nonce
  diff_id
  auth_tag optional
```

The receiver validates:

- The previous hash matches its current session dictionary.
- The epoch increments by exactly one.
- The diff only adds new template IDs.
- Existing template IDs are never overwritten.
- Template and total dictionary byte limits are respected.
- The canonical next-state hash matches the proposal.
- The nonce/diff has not been replayed.
- The optional auth tag matches when a shared auth key is configured.

If valid, the receiver replies:

```text
DICT_ACK
  accepted = true
  diff_id
  previous_state_hash
  state_hash = next_state_hash
  nonce
  auth_tag optional
```

Only after the sender verifies the ACK may future deltas reference the new
template IDs.

## Invariants

- No acknowledged hash, no delta.
- Hash mismatch, no delta.
- Structural change creates a new template ID.
- A delta may only reference structure both peers have ACKed.
- Dictionary updates are bounded and append-only inside a session.
- If peers disagree, stop delta use and resync or fall back to whole frames.

## Future Connection Resume

For a later connection to the same peer, the client sends a resume hello:

```text
RESUME_HELLO
  peer_id
  app_namespace
  static_dictionary_sha256
  cached_state_hashes[]
  supported_delta_versions[]
  nonce
  auth_tag optional
```

The receiver accepts only if it recognizes one of the offered state hashes and
the static dictionary and delta version match. Otherwise it rejects resume and
the peers must perform a fresh structure handshake.

This prevents silent reuse of stale structure while still letting recurring
agent relationships avoid relearning the same templates every session.

## Python API

```python
from aura_compression import (
    apply_aiwire_session_dictionary_diff,
    build_aiwire_session_dictionary_diff,
    build_aiwire_session_resume_hello,
    negotiate_aiwire_session_resume,
    verify_aiwire_session_dictionary_ack,
    verify_aiwire_session_resume_response,
)

current = {128: "agent {0} calls tool {1}"}
discovered = {129: "task {0} status {1}"}

diff = build_aiwire_session_dictionary_diff(
    current,
    discovered,
    session_id="session-1",
    epoch=2,
    auth_key=b"shared-session-key",
)

next_templates, ack = apply_aiwire_session_dictionary_diff(
    current,
    diff.to_dict(),
    current_epoch=2,
    auth_key=b"shared-session-key",
)

verify_aiwire_session_dictionary_ack(
    diff,
    ack,
    auth_key=b"shared-session-key",
)
```
