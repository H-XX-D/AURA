# AIWire Session Fixtures

The public fixture corpus is a deterministic set of synthetic AIWire sessions:

```text
fixtures/aiwire_sessions/public_session_corpus_v1.json
```

It exists so benchmarks, tests, and future non-Python implementations can replay
the same negotiated AI-to-AI session shape instead of relying only on generated
messages.

## What Is Included

Each session includes:

- A forced AIWire handshake with session templates enabled
- Initial session templates separate from the static AIWire dictionary
- A template discovery preview from `discover_ai_wire_session_templates`
- A session-template update signal
- An authenticated append-only session dictionary diff
- A matching dictionary ACK
- A future-connection resume hello/response
- Synthetic MCP, A2A, OpenAI Responses, local agent, trace, review, handoff,
  and memory-write messages
- Canonical JSON byte counts and SHA-256 hashes for every message
- Per-epoch AIWire round-trip byte stats using the Python backend

The committed corpus currently contains two sessions, 18 request/response
exchanges per session, and 72 total message frames.

## Safety Model

The fixture data is public-safe:

- All messages are generated from deterministic synthetic builders.
- There are no private hosts, usernames, tokens, credentials, or production
  payloads.
- The HMAC key used by the fixture generator is a fixed public test key. The
  saved JSON records only `key_id` and explicitly marks secret material as not
  included.
- The dictionary diff is append-only. Existing template IDs are not overwritten.
- Receivers verify the previous state hash, next state hash, diff ID, HMAC tag,
  ACK, and resume response before using the updated dictionary state.

## Regenerate

From the repo root:

```bash
PYTHONPATH=src python tools/build_aiwire_session_fixture_corpus.py
```

Custom size:

```bash
PYTHONPATH=src python tools/build_aiwire_session_fixture_corpus.py \
  --sessions 3 \
  --exchanges-per-session 24 \
  --seed 7201 \
  --output /tmp/public_session_corpus_v1.json
```

The default command rewrites
`fixtures/aiwire_sessions/public_session_corpus_v1.json` with stable sorted
JSON. Tests compare the committed file with the generator output so accidental
fixture drift is visible.

## Validate

```bash
PYTHONPATH=src pytest tests/test_aiwire_session_fixtures.py -q
```

The tests verify:

- The generator is deterministic
- The saved JSON matches the generated fixture
- Handshake negotiation accepts only the expected session templates
- Template updates and append-only dictionary diffs apply cleanly
- ACK and resume authentication validates
- Message hashes match canonical JSON bytes
- Each template epoch round-trips through AIWire

## How To Use

Use this fixture when a change touches AIWire handshake, dictionary evolution,
session-template discovery, resume negotiation, or benchmark corpus logic. It is
also a starting point for other runtimes: implement the AIWire v1 handshake and
dictionary diff rules, load the fixture, and verify the same canonical message
hashes and side-channel state transitions.
