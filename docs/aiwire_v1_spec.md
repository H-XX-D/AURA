# AIWire v1 Protocol Spec

Status: implementation contract for the current Python and native C++ AIWire
semantic/control paths, plus the v1 blob descriptor lane contract.

AIWire v1 is a session-oriented structure side channel for repetitive
AI-to-AI messages. It is designed for controlled peers that already have a
normal transport such as TCP, WebSocket, HTTP streaming, a broker frame, or a
replay log. AIWire does not define that transport. It defines the handshake,
compression parameters, session structure state, and safety checks that both
peers must share before compact frames are exchanged.

AIWire has three logical lanes over that transport:

- A semantic/message lane for structured agent messages and deltas.
- A control/session lane for handshake, routing, safety, template, dictionary,
  ACK, and resume state.
- A blob descriptor lane for opaque payload metadata, hashes, chunk manifests,
  route hints, and transfer status.

Normative words such as MUST, MUST NOT, SHOULD, and MAY are used intentionally.

## Scope

AIWire v1 covers:

- Protocol identity and version negotiation.
- Static dictionary agreement.
- Optional routine-control LUT agreement.
- Semantic/message lane framing for canonical structured messages.
- Control/session lane messages for connection, state, and safety management.
- Mission-critical system control messages.
- Blob descriptor lane messages for opaque payload metadata.
- Optional session-template agreement.
- Ordered data frames encoded with a live raw-deflate stream.
- Session-template update signals for future compression epochs.
- Append-only session dictionary diffs, ACKs, and resume handshakes.
- Fallback negotiation to non-AIWire codecs when explicitly allowed.

AIWire v1 does not cover:

- Transport security, peer authentication, retries, or backpressure.
- Message authorization or policy.
- Cross-transport framing.
- Encryption.
- Bulk opaque binary byte transfer.
- Media, tensor, model-weight, archive, or file compression formats.
- Loss recovery inside the compressed stream.

Those concerns belong at the transport or application layer.

## Protocol Constants

| Name | Value |
|---|---|
| Protocol | `aura.aiwire` |
| Version | `1` |
| Supported versions | `[1]` |
| Delta version | `1` |
| Handshake schema | `aura.aiwire.handshake.v1` |
| Negotiation schema | `aura.aiwire.negotiation.v1` |
| N-ary negotiation schema | `aura.aiwire.nary_negotiation.v1` |
| Compatibility manifest schema | `aura.aiwire.compatibility_manifest.v1` |
| Control LUT schema | `aura.aiwire.control_lut.v1` |
| System control schema | `aura.aiwire.system_control.v1` |
| Blob descriptor schema | `aura.aiwire.blob_descriptor.v1` |
| Template update schema | `aura.aiwire.session_templates.update.v1` |
| Dictionary state schema | `aura.aiwire.session_dictionary.state.v1` |
| Dictionary diff schema | `aura.aiwire.session_dictionary.diff.v1` |
| Dictionary ACK schema | `aura.aiwire.session_dictionary.ack.v1` |
| Resume hello schema | `aura.aiwire.session_resume.hello.v1` |
| Resume response schema | `aura.aiwire.session_resume.response.v1` |
| Raw deflate window bits | `-15` |
| zlib memory level | `8` |
| Default compression level | `3` |
| Flush mode | `z_sync_flush` |
| Static dictionary size | `32768` bytes |
| Static dictionary SHA-256 | `f5c9d524606a4cec9c397cb7ae177a8e1ec87f9819c749f6fd0b24a155313117` |
| Static dictionary FNV-1a64 | `94dd21718372952e` |
| Sync-flush frame suffix | `00 00 ff ff` |
| Fallback codecs | `zlib`, `raw` |
| Max session templates | `4096` |
| Max template bytes | `4096` |
| Max session dictionary bytes | `262144` |
| Max diff additions | `128` |
| Max routine-control LUT entries | `1024` |
| Nonce bytes | `16`, encoded as 32 lowercase hex characters |

The static dictionary is implementation-versioned by SHA-256. Peers MUST compare
the static dictionary SHA-256 and byte size when `use_static_dictionary` is
true.

Implementations SHOULD also be able to emit and verify an
`aura.aiwire.compatibility_manifest.v1` record for release, deployment, and
transport startup preflight. The manifest pins protocol versions, delta
versions, static dictionary identity, zlib parameters, fallback codecs, session
dictionary state, routine-control LUT state, and hard safety limits. It does
not replace the live handshake; it is an inspectable compatibility matrix that
lets operators or sidecars reject or fall back before moving data.

## Serialization

Structured messages crossing the AIWire boundary MUST be converted to canonical
UTF-8 JSON bytes before compression:

```python
json.dumps(message, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
```

Raw bytes MAY be compressed directly only for small agreed payloads where both
peers agree the payload is not structured JSON. Large opaque binaries SHOULD be
represented by blob descriptor frames and moved through an explicit byte stream,
file path, object store, shared-memory path, media channel, or other
application-chosen blob transport. String payloads are UTF-8 encoded.

AIWire control messages are JSON mappings. Hashes and auth tags are computed
over canonical JSON bytes using the same compact sorted-key encoding unless a
field definition below states otherwise.

## Logical Lanes

AIWire v1 defines three logical lanes. A carrier MAY multiplex them explicitly
or carry them as ordered JSON control frames plus ordered data frames. Lane
identity is semantic unless the carrier defines its own lane ID.

### Semantic/Message Lane

The semantic/message lane carries structured AI messages and deltas:

- `lane`: `semantic`.
- Payloads are canonical JSON bytes, AIToken frames, or AIWire-compressed
  frames produced from canonical JSON bytes.
- Typical messages include JSON-RPC requests and responses, MCP tool calls,
  A2A task and artifact updates, OpenAI-style tool calls, local agent traces,
  reviews, memory writes, and result messages.
- The lane is optimized by the static dictionary, session templates, append-only
  session dictionary state, and live compression history.
- Frames inside one compression epoch MUST preserve order.

### Control/Session Lane

The control/session lane carries state needed to keep the semantic lane safe and
recoverable:

- `lane`: `control`.
- Messages include handshakes, negotiations, template updates, dictionary
  state, dictionary diffs, ACK/NACK, resume hello/response, reset requests,
  heartbeats, route status, safety status, congestion hints, retry hints, and
  fallback decisions.
- Routine control messages MAY use compact hexadecimal LUT entries after the
  handshake proves both peers agree on the LUT hash, count, and epoch.
- Mission-critical control messages MUST remain system control messages and
  MUST NOT be represented only by mutable session dictionary entries or routine
  LUT codes.
- Control messages MUST be decodable without inflating the semantic/message
  lane.
- State-changing control messages SHOULD be idempotent by session ID, epoch,
  nonce, state hash, or sequence number.
- Control messages that mutate session structure MUST be bounded by the limits
  in this document and MUST fail closed on hash mismatch.

### Blob Descriptor Lane

The blob descriptor lane carries metadata for opaque bytes. It lets peers route,
schedule, verify, resume, and account for binary payloads without sending those
payloads through the structured-message codec:

- `lane`: `blob_descriptor`.
- Blob descriptor frames are canonical JSON control frames using
  `aura.aiwire.blob_descriptor.v1`.
- Descriptors MAY reference bytes moving over the same transport, a separate
  byte stream, a file path, shared memory, an object store, a media transport,
  or an application-defined blob broker.
- Descriptor processors MAY inspect route, type, priority, status, and digest
  fields without decompressing or loading the referenced blob bytes.
- Complete blob descriptors MUST include a content digest. Resumable chunked
  transfers SHOULD include chunk digests.
- Descriptor frames MUST NOT carry plaintext encryption keys or unbounded
  application metadata.
- Large opaque binaries SHOULD NOT be inserted into the semantic/message lane.

## Routine Control LUT

The routine-control LUT is a handshake-pinned lookup table for compact,
non-mission-critical control messages. It exists so routine control can cross
the wire as a small hexadecimal entry while both peers still agree on what that
entry means.

Each LUT entry is canonical JSON before hashing:

| Field | Required | Meaning |
|---|---:|---|
| `code` | yes | Hexadecimal uint16 string, for example `0x0010` |
| `meaning` | yes | Stable control meaning, for example `heartbeat` or `route_status` |
| `payload_schema` | no | Schema for any payload that follows the compact code |
| `criticality` | yes | `routine` or `important` |

The LUT state hash is:

```text
sha256(canonical_json({
  "schema": "aura.aiwire.control_lut.v1",
  "protocol": "aura.aiwire",
  "entries": [normalized_entry, ...]
}))
```

Control LUT rules:

- Entries are sorted by numeric `code` before hashing.
- Codes and meanings MUST be unique.
- A LUT MUST contain at most 1024 entries.
- `criticality="mission_critical"` is invalid in the routine-control LUT.
- If either peer requires or advertises a non-empty control LUT, peers MUST
  compare `control_lut_sha256` and `control_lut_count` during handshake.
- A peer MUST NOT interpret an unknown LUT code as mission-critical control.
  Unknown routine codes SHOULD be ignored, NACKed, or cause a resync request by
  application policy.

Routine-control compact frame wire form:

```text
uint16_be code
optional canonical_json_payload_mapping
```

The carrier transport preserves frame boundaries, so no internal payload length
is required. A payload is omitted when empty. When present, the payload MUST be a
canonical JSON mapping, not a scalar or array. Debugging and text transports MAY
represent the same frame as hexadecimal bytes, for example `0x0011` for a
payload-free `route_status` frame. The receiver decodes the first two bytes,
looks up the code in the handshaked LUT, and then parses any remaining bytes
against that entry's payload schema.

## System Control Messages

Mission-critical control messages stay in a self-describing system-control
envelope. They do not depend on the semantic compression stream, the session
template dictionary, or the routine-control LUT.

| Field | Required | Meaning |
|---|---:|---|
| `schema` | yes | `aura.aiwire.system_control.v1` |
| `protocol` | yes | `aura.aiwire` |
| `lane` | yes | `control` |
| `criticality` | yes | `mission_critical` |
| `control_type` | yes | Known mission-critical control type |
| `session_id` | yes | Session being controlled |
| `epoch` | yes | Non-negative session epoch |
| `sequence` | yes | Non-negative control sequence number |
| `nonce` | yes | 16 random bytes encoded as 32 lowercase hex characters |
| `state_hash` | no | Related dictionary, LUT, or safety state hash |
| `payload` | yes | Bounded canonical JSON mapping |
| `auth_tag` | no | HMAC over the unsigned canonical JSON payload when an auth key is configured |

Mission-critical control types include:

- `handshake_accept`
- `handshake_reject`
- `dictionary_update`
- `epoch_reset`
- `resync_required`
- `auth_failure`
- `safety_policy`
- `key_rotation`
- `emergency_stop`
- `critical_route_authority`
- `critical_verification_failure`

System control rules:

- A receiver MUST fail closed on an unknown mission-critical `control_type`.
- A receiver MUST reject malformed nonce, epoch, sequence, or hash fields.
- A receiver with an auth key MUST verify `auth_tag` before applying the
  message.
- System control messages MUST NOT be compressed into session templates or
  represented only as routine-control LUT codes.
- System control messages SHOULD be prioritized ahead of semantic messages,
  routine control, and bulk blob bytes.

## Blob Descriptor Frame

A blob descriptor frame is a canonical JSON mapping:

| Field | Required | Meaning |
|---|---:|---|
| `schema` | yes | `aura.aiwire.blob_descriptor.v1` |
| `protocol` | yes | `aura.aiwire` |
| `lane` | yes | `blob_descriptor` |
| `blob_id` | yes | Stable application or session identifier for this blob |
| `session_id` | no | AIWire session identifier, when the carrier has one |
| `semantic_role` | no | Role such as `image`, `audio_frame`, `tensor_chunk`, `model_artifact`, `log_archive`, `tool_file`, or `trace_bundle` |
| `content_type` | yes | MIME type or application media type |
| `byte_length` | yes | Non-negative byte length of the complete blob |
| `digest` | yes | Object with `algorithm` and `value`, for example SHA-256 or BLAKE3 |
| `chunk` | no | Object with `size`, `count`, optional `index`, and optional chunk `digest` |
| `route` | no | Object with application-defined `source`, `destination`, `next_hop`, `channel`, and `priority` fields |
| `status` | yes | `pending`, `available`, `in_flight`, `complete`, `failed`, or `cancelled` |
| `encryption` | no | Object with non-secret mode and key identifier metadata |
| `compression` | no | Opaque compression label or object for the blob byte stream |
| `dependencies` | no | Message IDs, blob IDs, or content hashes required before use |
| `ttl_ms` | no | Time-to-live hint for routing and cache policy |
| `metadata` | no | Bounded application metadata |

Blob descriptor rules:

- `blob_id` plus `digest` SHOULD identify immutable bytes. If a mutable name is
  needed, applications SHOULD put the mutable name in `metadata` or `route`, not
  in the digest identity.
- Receivers MUST NOT report `status="complete"` until byte length and digest
  verification have succeeded.
- Resent descriptors MUST be safe to apply more than once when `blob_id`,
  `digest`, `chunk`, and `status` match.
- A descriptor that changes `digest` for the same immutable `blob_id` MUST be
  rejected or treated as a new blob by application policy.
- Descriptor `metadata` MUST be bounded by application policy and SHOULD avoid
  private host details in persisted public logs.

## Lane Safety

The three lanes share a session but must not depend on hidden decoder state:

- Control/session lane messages MUST remain independently parseable while the
  semantic/message compression stream is healthy, resyncing, or failed.
- Blob descriptor lane messages MUST remain parseable without the referenced
  blob bytes.
- Blob descriptors MUST NOT mutate the session dictionary. Dictionary changes
  must use the explicit template update or dictionary diff/ACK flows.
- Mission-critical system control messages MUST remain parseable without the
  session dictionary, semantic compression stream, or routine-control LUT.
- Routine LUT control messages MUST NOT be used for emergency stop, auth
  failure, epoch reset, dictionary mutation, key rotation, or critical
  verification failure.
- Under congestion, peers SHOULD prioritize control/session lane messages ahead
  of semantic messages and bulk blob bytes.
- A semantic lane reset SHOULD NOT invalidate completed digest-addressed blob
  transfers.

## Transport Binding Guidance

AIWire does not standardize a transport envelope, but each binding MUST preserve
enough information for the receiver to choose the right lane decoder before it
touches the payload:

- A carrier that multiplexes semantic, control, and blob descriptor frames
  SHOULD include a lane discriminator outside the AIWire payload.
- Raw TCP bindings need an explicit length prefix or equivalent delimiter for
  every carrier frame.
- Raw TCP receivers MUST treat short `recv()` results as normal partial reads,
  continue until the complete carrier frame is assembled, and fail closed if the
  connection closes before the declared length is satisfied.
- WebSocket, broker, and replay-log bindings MAY use one transport message per
  carrier frame.
- HTTP streaming bindings MAY use one event per carrier frame and SHOULD name
  control events separately from semantic events when the platform exposes event
  names.
- Transport bindings SHOULD exchange a control payload containing an
  `aura.aiwire.compatibility_manifest.v1` manifest before semantic data frames.
  Bindings MUST fail closed when required dictionary, delta-version,
  session-template, session-dictionary, or routine-control LUT state does not
  match and no explicit fallback was selected.
- A routine-control LUT frame MAY be as small as two bytes after the carrier
  lane discriminator. It MUST NOT be appended to a semantic deflate frame.
- Mission-critical system control messages SHOULD be sent on the control lane
  with priority ahead of semantic frames and routine LUT frames.

The reference `aura-proxy` sidecar uses a simple TCP binding for controlled
links: `uint32_be length`, one lane byte, then payload bytes. Lane `0x01` is
inspectable canonical JSON control, and lane `0x02` is an AIWire semantic data
frame. This binding is explicit sidecar traffic, not OS-level transparent
interception.

## Ordered Data Frames

An AIWire data frame is the compressed byte output from one call to the session
encoder. It has no built-in length prefix, magic byte, or per-frame metadata.
The carrier transport MUST preserve frame boundaries and ordering.

The encoder uses one live raw-deflate stream per direction:

```text
raw = canonical_message_bytes
compressed = deflate(raw) + Z_SYNC_FLUSH
```

The decoder uses the matching live inflate stream and consumes one compressed
frame at a time. A frame MUST NOT contain unused compressed data after inflate.
Reference bindings SHOULD reject frames that do not end with the raw-deflate
Z_SYNC_FLUSH suffix `00 00 ff ff`; otherwise a truncated frame can sometimes
produce partial output before the missing flush boundary is detected.

Because the stream is stateful, data frames are not independently decodable.
Peers MUST NOT reorder, drop, duplicate, or replay data frames inside a live
AIWire stream. A transport that can lose or reorder messages must add its own
ordering and recovery layer or must reset and rehandshake after disruption.
Reference decoders SHOULD mark a stream as interrupted after the first
data-frame error and reject later frames on that decoder until a fresh handshake
creates new encoder/decoder state.

For bidirectional agent communication, each direction SHOULD use its own encoder
and decoder state.

## Benchmark Stats

Reference bindings SHOULD expose stable per-session counters for benchmark and
regression tooling. The Python `AIWireStats.as_dict()` schema is:

| Field | Meaning |
| --- | --- |
| `frames` | Number of frames accepted by the encoder or decoder |
| `bytes_in` | Bytes consumed by that direction |
| `bytes_out` | Bytes emitted by that direction |
| `ratio` | `bytes_in / bytes_out`, or `0.0` when `bytes_out == 0` |
| `average_bytes_in` | `bytes_in / frames`, or `0.0` for empty sessions |
| `average_bytes_out` | `bytes_out / frames`, or `0.0` for empty sessions |

Tools MAY add transport-specific fields, latency, elapsed time, or legacy
aliases, but these six fields SHOULD remain stable for longitudinal comparison.

## Session Dictionary Construction

The compression dictionary is built from:

1. The static AIWire dictionary, when `use_static_dictionary=true`.
2. Optional session templates, serialized as newline-separated
   `template_id:pattern` terms and repeated near the end of the zlib window.

The final dictionary passed to zlib is the last 32768 bytes of that combined
dictionary. This matters because zlib weights dictionary terms near the end of
the window most strongly.

Session template IDs are unsigned 16-bit integers in the range `0..65535`.
Patterns MUST be non-empty strings. Template maps are normalized by sorting
ascending by `template_id`.

`session_template_sha256` is:

```text
sha256(
  json.dumps(
    [{"template_id": id, "pattern": pattern}, ...],
    ensure_ascii=False,
    separators=(",", ":")
  ).encode("utf-8")
)
```

For an empty template set, `session_template_sha256` is the empty string.

## Initial Handshake

Before sending AIWire data frames, a peer sends an `AIWireHandshake` object:

| Field | Required | Meaning |
|---|---:|---|
| `schema` | yes | `aura.aiwire.handshake.v1` |
| `protocol` | yes | `aura.aiwire` |
| `versions` | yes | Supported AIWire versions |
| `preferred_version` | yes | Preferred version, currently `1` |
| `dictionary_sha256` | yes | Static dictionary SHA-256, or empty when disabled |
| `dictionary_size` | yes | Static dictionary byte size, or `0` when disabled |
| `wbits` | yes | Raw deflate window bits, currently `-15` |
| `mem_level` | yes | zlib memory level, currently `8` |
| `flush_mode` | yes | Currently `z_sync_flush` |
| `level` | yes | zlib compression level `0..9` |
| `use_static_dictionary` | yes | Whether the static dictionary is enabled |
| `backend` | yes | Informational backend name, for example `python` or `native` |
| `native_version` | no | Informational native backend version |
| `fallback_codecs` | yes | Ordered fallback codecs the peer can accept |
| `session_templates` | yes | Template objects with `template_id` and `pattern` |
| `session_template_sha256` | yes | Hash of normalized session templates |
| `session_template_count` | yes | Number of templates |
| `session_template_epoch` | yes | Template epoch, initially usually `0` |
| `require_session_templates` | yes | If true, fail unless templates match |
| `control_lut` | conditional | Routine-control LUT entries; omitted when empty and not required |
| `control_lut_sha256` | conditional | Hash of normalized routine-control LUT |
| `control_lut_count` | conditional | Number of routine-control LUT entries |
| `control_lut_epoch` | conditional | Routine-control LUT epoch |
| `require_control_lut` | conditional | If true, fail unless routine-control LUTs match |

The receiver MUST parse and validate:

- `schema` and `protocol`.
- Version intersection.
- Session template count and hash when templates are required or either side
  sends a non-empty template set.
- Static dictionary mode, hash, and size.
- `wbits`, `mem_level`, and `flush_mode`.
- Session template payload hash and count.
- Routine-control LUT payload hash and count when required or either side sends
  a non-empty LUT.

The receiver responds with an `AIWireNegotiation` object:

| Field | Meaning |
|---|---|
| `schema` | `aura.aiwire.negotiation.v1` |
| `accepted` | Whether the negotiated codec can be used |
| `codec` | `aiwire`, a fallback codec, or empty on hard reject |
| `version` | Selected AIWire version, or null for fallback |
| `reason` | Null on success, otherwise a reason code |
| `server` | The receiver's `AIWireHandshake` |

When negotiation succeeds with `codec="aiwire"`, peers MUST create fresh encoder
and decoder state using the negotiated parameters before sending data frames.

## N-Ary Handshake

Multi-agent sessions MAY use a coordinator to negotiate one shared AIWire
contract across more than two peers. The coordinator evaluates each peer's
`AIWireHandshake` against the same local dictionary, session-template,
control-LUT, fallback, and zlib settings, then emits an
`AIWireNaryNegotiation` object:

| Field | Meaning |
|---|---|
| `schema` | `aura.aiwire.nary_negotiation.v1` |
| `accepted` | Whether every peer can join the shared session |
| `codec` | Shared codec, or empty on reject |
| `version` | Shared AIWire version, or null for fallback/reject |
| `reason` | Null on success, otherwise a group failure reason |
| `peer_count` | Number of peer handshakes evaluated by the coordinator |
| `coordinator` | The coordinator's `AIWireHandshake` |
| `peers` | Per-peer negotiation summaries in deterministic order |

N-ary negotiation MUST fail closed if any peer rejects, or if accepted peers
would require mixed codecs, versions, dictionary state, template state, or
control-LUT state. On peer-specific rejection, the reason SHOULD identify the
failing peer index and the pairwise reason, for example
`peer_2_dictionary_sha256_mismatch`. A successful n-ary negotiation means all
participants can use the same sustained session structure; it does not replace
transport authentication, membership authorization, or application-level group
policy.

## Handshake Failure And Fallback

Known hard-failure reason codes include:

- `no_common_aiwire_version`
- `session_template_count_mismatch`
- `session_template_sha256_mismatch`
- `session_templates_required`
- `static_dictionary_mode_mismatch`
- `dictionary_sha256_mismatch`
- `dictionary_size_mismatch`
- `zlib_window_mismatch`
- `flush_mode_mismatch`
- `mem_level_mismatch`

If `allow_fallback=true`, the receiver MAY accept the first local fallback codec
also present in the peer handshake. Current fallback codecs are usually `zlib`
and `raw`. Fallback acceptance sets `accepted=true`, `codec=<fallback>`,
`version=null`, and `reason=<aiwire failure reason>`.

If fallback is not allowed or no fallback matches, the receiver MUST return
`accepted=false`, `codec=""`, `version=null`, and the reason.

## Fallback Codec Frames

Fallback frames do not use the live AIWire compression stream and do not use the
AIWire static or session dictionaries. They are one-frame-at-a-time recovery
paths after negotiation accepts a non-AIWire codec:

- `raw`: canonical AIWire message bytes.
- `zlib`: a standalone zlib frame over canonical AIWire message bytes.

Receivers MUST NOT feed fallback frames into the AIWire session decoder.
Receivers SHOULD reject unsupported fallback codec labels and zlib fallback
frames with trailing unused compressed data. Structured fallback messages are
decoded from the restored canonical bytes with the same JSON rules as normal
AIWire messages.

## Session Template Update Signal

`AIWireSessionTemplateUpdate` signals a transition from one template set to
another:

| Field | Meaning |
|---|---|
| `schema` | `aura.aiwire.session_templates.update.v1` |
| `protocol` | `aura.aiwire` |
| `previous_sha256` | Hash of the current normalized template set |
| `next_sha256` | Hash of the desired normalized template set |
| `previous_count` | Current template count |
| `next_count` | Desired template count |
| `add_or_update` | Template objects to add or replace |
| `remove` | Template IDs to remove |
| `epoch` | Caller-managed template epoch |
| `requires_session_reset` | Currently true |

The receiver MUST verify the previous hash and count, apply removals and
additions, then verify the next hash and count.

Because zlib dictionaries are fixed when a stream starts, a successful template
update is for the next compression epoch. Peers MUST reset and recreate encoder
and decoder state before using frames encoded against the updated dictionary.

## Session Dictionary State Hash

The safer update path is the append-only session dictionary diff and ACK flow.
It addresses a dictionary state by:

```text
state_hash = sha256(canonical_json(session_dictionary_state))
```

The state payload is:

| Field | Meaning |
|---|---|
| `schema` | `aura.aiwire.session_dictionary.state.v1` |
| `protocol` | `aura.aiwire` |
| `version` | AIWire version |
| `delta_version` | Delta version |
| `static_dictionary_sha256` | Static dictionary SHA-256 |
| `epoch` | Non-negative dictionary epoch |
| `templates` | Normalized template objects with `pattern_sha256` |

Template bounds MUST be enforced before hashing:

- At most 4096 templates.
- Each UTF-8 template pattern at most 4096 bytes.
- Total UTF-8 template bytes at most 262144 bytes.

## Append-Only Dictionary Diff

A dictionary diff proposes new template IDs for the next epoch. It is only a
proposal until the receiver validates it and returns a matching ACK.

| Field | Meaning |
|---|---|
| `schema` | `aura.aiwire.session_dictionary.diff.v1` |
| `protocol` | `aura.aiwire` |
| `session_id` | Application session identifier |
| `epoch` | Must equal current epoch + 1 |
| `previous_state_hash` | Current state hash |
| `next_state_hash` | Proposed next state hash |
| `previous_count` | Current template count |
| `next_count` | Proposed next template count |
| `additions` | New template objects with `pattern_sha256` |
| `nonce` | Fresh 32-character lowercase hex nonce |
| `diff_id` | SHA-256 identity of the unsigned diff payload without `diff_id` |
| `delta_version` | Delta version |
| `auth_tag` | Optional HMAC-SHA256 tag |

The receiver MUST reject a diff if:

- The schema, protocol, or delta version is unsupported.
- `diff_id` does not match the canonical unsigned diff payload.
- A configured auth key is present and `auth_tag` is missing or invalid.
- `diff_id` or `nonce` has already been accepted in the replay cache.
- `previous_state_hash` or `previous_count` does not match local state.
- `epoch` is not exactly current epoch + 1.
- There are no additions.
- Additions exceed the per-diff limit.
- An addition repeats an already accepted template ID.
- An addition attempts to overwrite an existing template ID with a different
  pattern.
- Any template bound is exceeded.
- The computed next state hash or next count does not match the diff.

Senders MUST NOT encode deltas against `next_state_hash` until the matching ACK
has been verified.

## Dictionary ACK

The receiver replies with an `AIWireSessionDictionaryAck`:

| Field | Meaning |
|---|---|
| `schema` | `aura.aiwire.session_dictionary.ack.v1` |
| `protocol` | `aura.aiwire` |
| `session_id` | Same session as the diff |
| `epoch` | Same epoch as the diff |
| `accepted` | Boolean decision |
| `diff_id` | Same diff ID |
| `previous_state_hash` | Same previous state hash |
| `state_hash` | Accepted next state hash |
| `reason` | Null on accept, reason text on reject |
| `nonce` | Fresh 32-character lowercase hex nonce |
| `delta_version` | Delta version |
| `auth_tag` | Optional HMAC-SHA256 tag |

The sender MUST verify:

- ACK schema, protocol, and delta version.
- ACK auth tag when an auth key is configured.
- `accepted=true`.
- Session ID, epoch, diff ID, previous hash, and next hash match the diff.

Only after this verification may future deltas reference the new template IDs.

## Resume Handshake

For a later connection to the same peer, a client MAY offer cached session
dictionary states with an `AIWireSessionResumeHello`:

| Field | Meaning |
|---|---|
| `schema` | `aura.aiwire.session_resume.hello.v1` |
| `protocol` | `aura.aiwire` |
| `peer_id` | Caller-defined peer identity |
| `app_namespace` | Caller-defined namespace, default `default` |
| `static_dictionary_sha256` | Static dictionary hash |
| `cached_state_hashes` | Cached session dictionary states |
| `supported_delta_versions` | Supported delta versions |
| `nonce` | Fresh nonce |
| `auth_tag` | Optional HMAC-SHA256 tag |

The receiver responds with `AIWireSessionResumeResponse`:

| Field | Meaning |
|---|---|
| `schema` | `aura.aiwire.session_resume.response.v1` |
| `protocol` | `aura.aiwire` |
| `accepted` | Whether resume is accepted |
| `reason` | Null on accept, otherwise reason code |
| `resume_state_hash` | Selected cached state hash, or null |
| `static_dictionary_sha256` | Receiver static dictionary hash |
| `selected_delta_version` | Selected delta version, or null |
| `hello_nonce` | Nonce from the hello |
| `nonce` | Fresh response nonce |
| `auth_tag` | Optional HMAC-SHA256 tag |

Resume acceptance requires:

- Valid hello auth when configured.
- Matching static dictionary SHA-256.
- Common delta version.
- At least one offered state hash known to the receiver.

Known rejection reasons are:

- `static_dictionary_sha256_mismatch`
- `no_common_delta_version`
- `no_shared_session_dictionary`

The client MUST verify response auth when configured, `hello_nonce`, static
dictionary hash, selected delta version, and that `resume_state_hash` was one of
the offered hashes.

Implementations MAY persist known peer state hashes and session templates in a
local resume cache, but the cache itself is not a wire artifact. A peer MUST
still verify the resume hello/response and fail closed if the selected state hash
does not resolve to a trusted local entry.

## Auth Tags

Dictionary diffs, ACKs, resume hellos, and resume responses MAY be protected by
HMAC-SHA256. When an auth key is configured:

```text
auth_tag = hmac_sha256(auth_key, canonical_json(unsigned_payload)).hexdigest()
```

The canonical JSON form uses sorted keys, compact separators, UTF-8 encoding,
and `ensure_ascii=False`.

When no auth key is configured, `auth_tag` is the empty string and receivers do
not verify it. This is acceptable only inside an already authenticated transport
or local trust boundary.

## Resync And Error Handling

If a peer detects any of the following, it MUST stop using the current AIWire
stream:

- Handshake rejection without accepted fallback.
- Missing data-frame sync-flush marker.
- Data-frame inflate error.
- Unused compressed data after inflate.
- Dictionary/template hash mismatch.
- Template update validation failure.
- Dictionary diff or ACK validation failure.
- Resume validation failure.
- Transport ordering loss, duplication, replay, or gap.

The recovery behavior is one of:

1. Perform a fresh AIWire handshake and start a new compression stream.
2. Fall back to `raw` or `zlib` if fallback was negotiated and application
   policy allows it.
3. Abort the application session.

Peers MUST NOT continue sending compact deltas against uncertain structure.
After a data-frame error, receivers MUST treat the current decoder state as
interrupted even if a later frame appears syntactically valid, because the
raw-deflate history may no longer match the sender.

## Reference Implementation

The Python reference implementation lives in:

- [`src/aura_compression/ai_wire.py`](../src/aura_compression/ai_wire.py)
- [`src/aura_compression/ai_wire_messages.py`](../src/aura_compression/ai_wire_messages.py)
- [`src/aura_compression/ai_wire_token.py`](../src/aura_compression/ai_wire_token.py)

The native C++ backend lives in:

- [`native/aiwire/aura_aiwire.cpp`](../native/aiwire/aura_aiwire.cpp)

Interoperability and safety tests live in:

- [`tests/test_ai_wire.py`](../tests/test_ai_wire.py)
- [`tests/test_ai_wire_token.py`](../tests/test_ai_wire_token.py)
- [`tests/test_aiwire_transport_examples.py`](../tests/test_aiwire_transport_examples.py)

Transport examples live in:

- [`examples/aiwire_tcp_transport.py`](../examples/aiwire_tcp_transport.py)
- [`examples/aiwire_websocket_transport.py`](../examples/aiwire_websocket_transport.py)
- [`examples/aiwire_http_streaming_transport.py`](../examples/aiwire_http_streaming_transport.py)
- [`examples/aiwire_local_broker.py`](../examples/aiwire_local_broker.py)
