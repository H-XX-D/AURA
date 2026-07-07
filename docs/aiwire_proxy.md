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

## Benchmark It

Use `aura-proxy-benchmark` to run a local end-to-end sidecar benchmark against
the public AIWire fixture corpus. The harness starts an upstream fixture
responder, an egress sidecar, an ingress sidecar, and a local client, then
replays request/response pairs through the full proxy path.

```bash
aura-proxy-benchmark \
  --seconds 60 \
  --backend native \
  --modeled-link-mbps 10 \
  --output /tmp/aura-proxy-benchmark.json \
  --replay-log-output /tmp/aura-proxy-benchmark.jsonl
```

For a quick smoke run:

```bash
aura-proxy-benchmark --seconds 0 --max-exchanges 32 --backend python
```

The report includes measured exchanges/second, raw framed bytes, AIWire tunnel
bytes, control overhead, p50/p95/p99 local round-trip latency, and modeled
10 Mbps raw-vs-tunnel capacity. This is useful for checking whether the
sidecar shape preserves the bandwidth-proportional benefit before moving the
same commands to the Z6 or Nano-class targets.

## Cross-Machine Benchmark

The cross-machine shape keeps the proxy path explicit:

```text
coordinator client -> coordinator ingress -> LAN -> edge egress -> edge fixture upstream
```

On an edge target, the upstream fixture responder speaks the same raw
uint32-length-prefixed frames as a local agent service:

```bash
aura-proxy-fixture-server \
  --listen-host 127.0.0.1 \
  --listen-port 9300 \
  --fixture-corpus fixtures/aiwire_sessions/public_session_corpus_v1.json \
  --fixture-variation-profile cluster \
  --fixture-peer-label edge-1 \
  --connections 1 \
  --metrics-output /tmp/aura-fixture.metrics.json
```

The egress sidecar runs beside it:

```bash
aura-proxy egress \
  --listen-host 0.0.0.0 \
  --listen-port 9200 \
  --upstream-host 127.0.0.1 \
  --upstream-port 9300 \
  --backend native \
  --connections 1 \
  --metrics-output /tmp/aura-egress.metrics.json
```

The coordinator can then run only the ingress/client half of the benchmark:

```bash
aura-proxy-benchmark \
  --egress-host <edge-host> \
  --egress-port 9200 \
  --seconds 60 \
  --backend native \
  --fixture-variation-profile cluster \
  --fixture-peer-label edge-1 \
  --output /tmp/aura-proxy-edge-1.json
```

For repeatable Z6-to-edge runs, use the SSH orchestrator. It defaults to a
dry-run plan; add `--run` only after checking the generated commands.

```bash
python tools/run_aiwire_proxy_cluster.py \
  --target edge-1=<edge-ssh-host> \
  --target edge-2=<edge-ssh-host> \
  --target edge-3=<edge-ssh-host> \
  --target edge-4=<edge-ssh-host> \
  --preflight \
  --seconds 60 \
  --backend native \
  --fixture-variation-profile cluster \
  --target-parallelism 4 \
  --output /tmp/aura-proxy-cluster.json \
  --summary-output /tmp/aura-proxy-cluster.md
```

For larger or mixed-user labs, keep targets in an untracked local file:

```bash
cp deploy/aura-proxy/proxy-cluster.targets.example /tmp/aura-targets.txt

python tools/run_aiwire_proxy_cluster.py \
  --targets-file /tmp/aura-targets.txt \
  --ssh-bootstrap \
  --preflight \
  --ready-targets-output /tmp/aura-ready-targets.txt \
  --seconds 60 \
  --backend native \
  --fixture-variation-profile cluster \
  --output /tmp/aura-edge-readiness.json \
  --summary-output /tmp/aura-edge-readiness.md
```

Target lines may include public labels and deployment-specific overrides:

```text
edge-1=<ssh-host>,proxy_host=<lan-host>,egress_port=9200,upstream_port=9300,remote_root=/home/<user>/AURA,ssh_public_key=/path/to/key.pub
```

The global `--remote-root` defaults to `~/AURA`. Use a per-target
`remote_root` only when a real lab has mixed SSH users or checkout paths.
The global `--ssh-public-key` remains the default for bootstrap reports; use a
per-target `ssh_public_key` when each edge has its own dedicated keypair.

If the edge hosts are reachable but fail batch SSH authentication, generate a
safe bootstrap report from the coordinator's public key:

```bash
python tools/run_aiwire_proxy_cluster.py \
  --target edge-1=<edge-ssh-host> \
  --target edge-2=<edge-ssh-host> \
  --ssh-bootstrap \
  --ssh-public-key ~/.ssh/id_ed25519.pub \
  --output /tmp/aura-proxy-bootstrap.json \
  --summary-output /tmp/aura-proxy-bootstrap.md
```

The bootstrap report is dry-run only. It emits one `ssh-copy-id` command for
targets where password SSH is available, one `authorized_keys` console command
for targets where SSH auth is not available yet, and one post-check command to
verify batch SSH from the coordinator. It does not copy keys or start services.

The `--preflight` mode checks the path before launching sidecars:

- local SSH config resolution, including aliases
- TCP reachability for the target SSH endpoint
- batch-mode SSH authentication
- remote `AURA` checkout importability
- fixture corpus presence
- native backend availability when `--backend native` is selected

When `--preflight --run` is used together, the runner exits before launching
remote processes unless every target is ready.

The edge readiness runbook expands the bootstrap and failure-recovery workflow:
[AIWire Proxy Edge Readiness Runbook](aiwire_proxy_edge_readiness.md).

The ready-target workflow has a public-safe 60-second validation report:
[AIWire Proxy Ready-Targets Run](perf/aiwire_proxy_ready_targets_2026-07-07.md).

The cluster variation profile deterministically changes role, workload, route,
epoch, queue depth, token window, telemetry, and trace identifiers per peer.
Both sides derive the same changed request/response bytes from the public
fixture corpus, so the run still verifies the actual bytes that crossed the
proxy path.

## Service Templates

The repo includes editable service-manager templates:

```text
deploy/aura-proxy/systemd/aura-proxy-ingress.service
deploy/aura-proxy/systemd/aura-proxy-egress.service
deploy/aura-proxy/launchd/org.aura.proxy.ingress.plist
deploy/aura-proxy/launchd/org.aura.proxy.egress.plist
```

Use the egress unit next to the upstream agent service and the ingress unit next
to the client. Edit hostnames, ports, backend, log paths, user, and any
transport-security wrapper before loading the units.

Systemd sketch:

```bash
sudo install -d /var/log/aura
sudo cp deploy/aura-proxy/systemd/aura-proxy-egress.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now aura-proxy-egress
```

Launchd sketch:

```bash
cp deploy/aura-proxy/launchd/org.aura.proxy.ingress.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/org.aura.proxy.ingress.plist
```

The templates intentionally do not set up TLS, WireGuard, firewall policy, or
agent authorization. Add those at the transport or service boundary for any
non-local trust boundary.

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
