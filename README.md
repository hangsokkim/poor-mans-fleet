# poor man's fleet — TPM-aware multi-host worker

A **poor man's** LLM API pacing & multi-host worker fleet. No Redis, no broker,
no Docker, no Kubernetes, no service mesh, no SaaS. Just a directory, `ssh`, `scp`,
`python3` (stdlib only), and `systemd --user`.

If Temporal / Celery / Nomad are a 747, this is a bicycle with a basket.
It still gets your groceries home.

## What it does

1. **Distributes jobs** across 2-3 Linux hosts over `ssh`+`scp`
2. **Paces LLM calls** so you stop getting `429 Too Many Requests` —
   60-second waits get spread out as `5 + 3 + 7 + 10` so the user sees
   "thinking" instead of "frozen"
3. **Watches peers** every 5 min; if a worker dies on host B, host A notices
   and tells you (the owner) within 5 min
4. **Restarts itself** when the OpenClaw / Codex sub-agent hangs
5. **Reports back** to the one machine you actually sit at

## Who this is for

- Owner-operators running 1-3 always-on Linux boxes
- LLM clients (Claude / GPT / Minimax) that bump into RPM/TPM limits
- People who said "I just want `ssh` to do the work" before reaching for
  Kubernetes
- A learner's repo: read `worker.py` (200 lines) and understand
  multi-host job queue + watchdog in one sitting

## Who this is NOT for

- >5 hosts (use Nomad / Kubernetes)
- Sub-second latency (use a broker in the same DC)
- DAGs / priorities / retries beyond timeout (use Temporal)
- Anyone with a budget (this is **poor man's** by design)

## Architecture (poor man's edition)

```
           owner (you)
                │  TUI / Telegram
                ▼
        ┌───────────────┐
        │  PM machine   │  ← off when you're away
        │  (laptop)     │
        │  inbox/       │
        │  outbox/      │
        │  dashboard    │
        └───────┬───────┘
                │ ssh
        ┌───────┴────────┐
        ▼                ▼
   ┌─────────┐      ┌─────────┐
   │  A      │◄────►│  B      │   ← always on
   │  24/7   │      │  24/7   │
   │         │      │         │
   │  worker │      │  worker │
   │  gw     │      │  gw     │
   │  watch  │      │  watch  │
   │  cross  │      │  cross  │
   └─────────┘      └─────────┘
```

## Why "poor man's"

| Real thing | Cost | Poor man's version | Cost |
|---|---|---|---|
| Redis | 1+ GB RAM, daemon | A directory | 0 |
| Celery | `pip install`, broker | `worker.py` (200 LoC) | 0 |
| Nomad | HashiCorp cluster | `ssh` + `scp` | 0 |
| Prometheus | TS database | `cat logs/worker.log` | 0 |
| Grafana | Docker stack | `fleet-status` (bash) | 0 |
| PagerDuty | $21/user/mo | `pending-alerts.jsonl` | 0 |
| mTLS service mesh | 3 certs per host | `StrictHostKeyChecking=accept-new` | 0 |
| L4 LB | nginx + keepalived | "ssh the less-busy box" | 0 |

## The trick that makes this nice

When you get a `429`, the **stupid** answer is `time.sleep(60)`. The user sees
a hard pause — feels like a hang.

The **poor man's atmospheric** answer is:

```python
sleep(randint(3, 10))   # 5
sleep(randint(3, 10))   # 3
sleep(randint(3, 10))   # 7
sleep(randint(3, 10))   # 10
# total: 25s, but spread out
```

Same token-bucket recovery, the user sees "AI thinking," not "AI frozen."

This is the whole repo's secret.

## What's in the box

| File | Purpose |
|---|---|
| `bin/worker.py` | Job worker (200 LoC, stdlib only) |
| `bin/cross-watchdog.py` | Per-node peer health check |
| `bin/openclaw-watchdog.sh` | Restart-on-3-fails health gate |
| `bin/fleet-submit` | `fleet-submit <host> <kind> [payload]` |
| `bin/fleet-pull-alerts` | PM pulls alerts from peers |
| `bin/fleet-status` | 1-line dashboard |
| `etc/protocol.md` | Job JSON schema + state machine |
| `etc/*.service, *.timer` | systemd user units (5-min cadence) |

## Install (poor man's edition)

```bash
# 0. prereqs: 2-3 Linux boxes, python3, systemd --user, ssh key auth
# 1. clone
git clone https://github.com/<you>/poor-mans-fleet
cd poor-mans-fleet

# 2. install on each box
./install.sh ~/fleet

# 3. cross-host ssh (run once per pair)
ssh-copy-id peer-a
ssh-copy-id peer-b

# 4. push your first job
./bin/fleet-submit peer-a ping

# 5. see it
ssh peer-a cat ~/fleet/queue/done/*.json
./bin/fleet-status
```

## Related / inspiration

- [Ameyanagi/LLMRateLimiter](https://github.com/Ameyanagi/LLMRateLimiter) — same TPM/RPM idea,
  but it's a *library* not an *operational system*
- [poor man's CI](https://en.wikipedia.org/wiki/Poor_man%27s_CI) — general anti-corporate
  tradition; cron + bash + a wiki page
- [systemd --user](https://wiki.archlinux.org/title/Systemd/User) — does a lot of what
  you'd want from a process supervisor
- `at(1)`, `cron(8)`, `inotifywait(1)` — the original "poor man's queue"

## License

MIT.
