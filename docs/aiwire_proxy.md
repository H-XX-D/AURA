# AIWire Explicit Sidecar Proxy

`aura-proxy` is the first runnable sidecar shape for AURA. It lets existing
agent processes keep using raw length-prefixed frames locally while two sidecars
move the inter-machine hop as an AIWire session.

```text
agent client -> ingress sidecar -> AIWire tunnel -> egress sidecar -> upstream agent
```

This is not transparent OS interception. It is an explicit TCP proxy for
controlled peers and bounded frames.

## Wire Shape

The local client side and upstream side use simple raw frames:

```text
uint32_be payload_length
payload bytes
```

The sidecar-to-sidecar tunnel uses the same outer length prefix, then a one-byte
lane tag:

```text
uint32_be tunnel_frame_length
uint8 lane_tag
payload bytes
```

Lane tags:

| Tag | Lane | Payload |
|---:|---|---|
| `0x01` | `control` | Canonical JSON control frame |
| `0x02` | `semantic` | AIWire-compressed data frame |

The control lane carries an inspectable proxy handshake containing the normal
AIWire handshake and negotiation objects. The semantic lane carries the live
AIWire stream. Each direction has its own encoder/decoder state.

## Run It

Start the egress sidecar next to the upstream agent service:

```bash
aura-proxy egress \
  --listen-host 0.0.0.0 \
  --listen-port 9102 \
  --upstream-host 127.0.0.1 \
  --upstream-port 8765 \
  --backend native \
  --metrics-output /tmp/aura-egress.metrics.json
```

Start the ingress sidecar next to the client:

```bash
aura-proxy ingress \
  --listen-host 127.0.0.1 \
  --listen-port 9101 \
  --egress-host <egress-host-or-z6> \
  --egress-port 9102 \
  --backend native \
  --metrics-output /tmp/aura-ingress.metrics.json \
  --replay-log-output /tmp/aura-ingress.replay.jsonl
```

Then point the local client at `127.0.0.1:9101` and send the same
uint32-length-prefixed payload bytes it would have sent directly to the
upstream service.

For smoke tests or one-shot jobs, add `--once`. For service mode, omit
`--once` and `--connections`.

## What It Measures

Metrics JSON includes:

- accepted connections and handshakes
- raw request/response payload bytes
- raw framed bytes
- tunnel request/response framed bytes
- control framed bytes
- actual encoder/decoder backend
- selected AIWire negotiation codec/version
- `tunnel_saved_percent`
- `bandwidth_capacity_gain`

The replay-log option writes a deterministic AIWire replay-log JSONL artifact
with the proxy result row so sidecar runs can be archived beside benchmark
results.

## Safety Boundary

The proxy fails closed on:

- malformed length prefixes
- frames larger than `--max-frame-bytes`
- unsupported lane tags
- malformed control JSON
- failed AIWire handshake or dictionary negotiation
- non-AIWire negotiated codec

The proxy does not provide:

- TLS
- peer identity
- authorization
- transparent interception
- retries or durable queueing
- mission-critical control policy
- arbitrary TCP stream translation

Use TLS, WireGuard, SSH tunnels, firewalls, service auth, or a broker security
layer when the link crosses a trust boundary. Mission-critical control messages
should remain explicit system control messages at the agent/application layer.

## Where It Fits

Use `aura-proxy` when both sides are under your control and you can frame agent
messages explicitly. It is a practical deployment test for the sustained
AIWire idea: handshake once, then keep moving only the changed message bytes
through the inter-machine tunnel.

For native service managers, wrap the two commands above with launchd, systemd,
supervisord, or a container entrypoint. The proxy stays in user space and does
not require packet capture or kernel routing changes.
