# AIWire Proxy Edge Readiness Runbook

This runbook prepares edge machines for explicit AIWire sidecar proxy
benchmarks without committing private lab details. It is designed for mixed edge
labs where different machines use different SSH users, checkout paths, and
dedicated public keys.

## Targets File

Keep real target files local or in `/tmp`; do not commit private hostnames,
addresses, usernames, or key paths. Start from the public-safe example:

```bash
cp deploy/aura-proxy/proxy-cluster.targets.example /tmp/aura-targets.txt
```

Each active line has this shape:

```text
edge-a=edge-a-ssh,proxy_host=edge-a-lan,remote_root=/home/edge-a/AURA,ssh_public_key=~/.ssh/id_edge_a.pub
```

Fields:

- `edge-a`: public label used in reports.
- `edge-a-ssh`: SSH alias or `user@host` used by the coordinator.
- `proxy_host`: LAN host/IP used by the ingress client to reach edge egress.
- `remote_root`: path to the target's `AURA` checkout.
- `ssh_public_key`: public key to install for that target's SSH user.

Leave blocked targets commented until they pass preflight. That keeps the
desired cluster shape visible while allowing clean runs on the ready subset.

## Readiness Report

Generate one dry-run report that includes both bootstrap commands and preflight
status:

```bash
python tools/run_aiwire_proxy_cluster.py \
  --targets-file /tmp/aura-targets.txt \
  --ssh-bootstrap \
  --preflight \
  --ready-targets-output /tmp/aura-ready-targets.txt \
  --seconds 60 \
  --connections 1 \
  --backend native \
  --fixture-variation-profile cluster \
  --target-parallelism 4 \
  --output /tmp/aura-edge-readiness.json \
  --summary-output /tmp/aura-edge-readiness.md
```

This command does not modify hosts or start sidecars. It writes:

- one `ssh-copy-id` command per target
- one console `authorized_keys` command per target
- one post-check command per target
- a preflight table covering SSH config, SSH TCP, batch auth, remote import,
  fixture corpus presence, and native backend readiness
- a ready-only targets file that contains only targets that passed preflight

## Interpreting Failures

`SSH TCP = False` means the coordinator cannot open the target's SSH port.
Check power, network attachment, IP/alias, firewall, and `sshd` on the target.

`SSH auth = False` with `SSH TCP = True` means the target is reachable but does
not accept the configured key. Use either the report's `ssh-copy-id` command
when password SSH is available, or paste the report's console command into a
local shell on the target. Then run the post-check command from the report.

`Remote env = False` with `SSH auth = True` means SSH works but the target is not
ready for native AIWire. On the target:

```bash
git clone https://github.com/H-XX-D/AURA.git "$HOME/AURA"
cd "$HOME/AURA"
git fetch origin main
git reset --hard origin/main
python3 tools/check_aiwire_native_backend.py --build --require-native --messages 64
```

Then rerun the readiness report.

## Smoke Then Sustained Run

After the readiness report, run a small smoke against the ready-only targets
file first:

```bash
python tools/run_aiwire_proxy_cluster.py \
  --targets-file /tmp/aura-ready-targets.txt \
  --preflight \
  --run \
  --seconds 10 \
  --max-exchanges 32 \
  --connections 1 \
  --backend native \
  --fixture-variation-profile cluster \
  --target-parallelism 4 \
  --output /tmp/aura-proxy-smoke.json \
  --summary-output /tmp/aura-proxy-smoke.md
```

Then run the sustained window:

```bash
python tools/run_aiwire_proxy_cluster.py \
  --targets-file /tmp/aura-ready-targets.txt \
  --preflight \
  --run \
  --seconds 60 \
  --connections 1 \
  --backend native \
  --fixture-variation-profile cluster \
  --target-parallelism 4 \
  --output /tmp/aura-proxy-60s.json \
  --summary-output /tmp/aura-proxy-60s.md
```

When `--preflight --run` is used, the runner exits before launching sidecars if
any active target fails readiness.

If you want a strict all-target run, omit `--ready-targets-output`, fix every
failure in `/tmp/aura-targets.txt`, and run directly from that file.

Increase `--connections` after the single-session run is stable. The runner
uses that value for each target's client sessions, local ingress sessions,
remote egress sessions, and remote fixture upstream sessions.

## Latest Public Validation

On 2026-07-07, this workflow was validated against a mixed six-target lab shape.
Preflight wrote a ready-only file with 3 of 6 targets: three targets were ready,
two were reachable but blocked on batch SSH authentication, and one was blocked
on SSH TCP reachability. A 60-second sustained run against the generated
ready-only file verified 4,076 exchanges across 3 targets at 67.9 group
exchanges/second, 2,311.7 raw framed bytes per exchange, 363.6 AIWire semantic
bytes per exchange, 84.3% semantic-byte savings, and 47.92 ms max p95.

A follow-up sweep on the same ready target shape used `--connections 2`, `4`,
and `8`, so each target carried two, four, and eight
client/ingress/egress/fixture sessions. The 60-second runs verified 8,150,
16,283, and 32,450 exchanges across 3 targets. Group throughput moved from
67.9 ex/s at one connection per target to 540.3 ex/s at eight connections per
target, while AIWire stayed near 366.8 semantic bytes per exchange, 84.4%
semantic-byte savings, and 48.16 ms max p95.

The runner now also supports `--connections-sweep`, which writes a single
combined sweep report. A 60-second saturation pass with `--connections-sweep
16,32` on the same ready target shape verified 64,914 and 128,739 exchanges
across 48 and 96 total sessions. Group throughput reached 1,080.6 and
2,142.2 ex/s, with AIWire still near 366.6 semantic bytes per exchange,
84.4% semantic-byte savings, 6.40x modeled capacity gain, and 48.61 ms max p95.
A later `--connections-sweep 64,128` pass identified the knee: 64 connections
per target verified 229,223 exchanges across 192 sessions at 3,802.8 ex/s and
59.81 ms max p95, while 128 connections per target still verified but fell to
161,648 exchanges, 2,562.6 ex/s, and 223.18 ms max p95. Use the higher level as
a saturation probe, not the default operating point.

The result is documented in
[AIWire Proxy Ready-Targets Run](perf/aiwire_proxy_ready_targets_2026-07-07.md).
The multi-connection scaling result is documented in
[AIWire Proxy Multi-Connection Scaling Run](perf/aiwire_proxy_multiconnection_2026-07-07.md).

## Safety Rules

- Commit only placeholder target files.
- Do not commit private hostnames, LAN addresses, usernames, private key paths,
  or run artifacts that contain them.
- Use `ssh_public_key`, never a private key path, in target files.
- Keep mission-critical control traffic outside the benchmark fixture path until
  the sidecar is explicitly designed for that safety class.
