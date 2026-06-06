# Architecture (poor man's edition)

## Design constraints (the "poor" part)

1. **No external broker.** Queue is a directory + atomic rename. Survives restarts.
2. **No root, no Docker, no sudo.** All systemd units are `user/` units.
3. **No new languages.** Python 3 stdlib, bash, and a tiny systemd unit.
4. **No `pip install`.** The worker is 200 LoC and uses only `os`, `json`, `time`,
   `subprocess`, `pathlib`, `random`, `socket`, `datetime`.
5. **3 hosts max.** Beyond that, ssh+scp is your bottleneck.
6. **Failure is normal.** A host can vanish at any time. Watchdogs must not deadlock.

## Components

### worker.py (the only Python)

```python
# pseudo-flow
while True:
    reap_stale()                            # running/* > timeout_s → pending
    job = claim_job()                       # pending/* → running/* (atomic)
    if job:
        run_job(job)                        # shell | status | ping | alert | ...
        cooldown(randint(15, 20))           # TPM-aware
    else:
        sleep(5)
```

That's the whole worker. Read it in 5 minutes.

### Job lifecycle

```
pending  ─claim─►  running  ─ok─►  done
                       │
                       ├──fail──►  failed
                       │
                       ├──stale(timeout)──►  pending
                       │
                       └──unknown kind──►  dlq
```

Claim = `os.rename(pending/X, running/X)`. Atomic on POSIX.

### Watchdogs (the "always running" part)

| Timer | Cadence | Job |
|---|---|---|
| `openclaw-watchdog.timer` | 5 min | 3 fails → restart gateway/worker |
| `cross-watchdog.timer` | 5 min | ssh peer; if down → alert |

### TPM policy (the "atmosphere" part)

```python
MIN_JITTER = 3
MAX_JITTER = 10
COOLDOWN_MIN = 15
COOLDOWN_MAX = 20

# between jobs
sleep(randint(MIN_JITTER, MAX_JITTER))

# after each job
sleep(randint(COOLDOWN_MIN, COOLDOWN_MAX))
```

Why jittered? When you have 2-3 workers, non-jittered sleeps sync up
("thundering herd" on the API). Random spread prevents that.

## Data flow

### Submit a job

```
PM:   ./bin/fleet-submit worker-a shell '{"cmd":"uptime"}'
  ↓ ssh + scp
Worker-A:  ~/fleet/queue/pending/<id>.json
  ↓ claim
Worker-A:  ~/fleet/queue/running/<id>.json
  ↓ run
Worker-A:  ~/fleet/outbox/<id>.stdout
Worker-A:  ~/fleet/outbox/<id>.stderr
  ↓ ack
Worker-A:  ~/fleet/queue/done/<id>.json
```

### Pull a result

```bash
ssh worker-a cat ~/fleet/outbox/<id>.json
```

### Get an alert

```
Worker-A detects: worker-b is down
  ↓
Worker-A: ~/fleet/inbox/pending-alerts.jsonl
  ↓
PM (next turn): ./bin/fleet-pull-alerts
  ↓
PM: ~/fleet/inbox/pending-alerts.jsonl
  ↓
You: "1 new alert" on next TUI session
```

## Security

- `ssh` only, key auth, `BatchMode=yes`
- `StrictHostKeyChecking=accept-new` for first-time peer
- All shell jobs run with `timeout 240`
- `~/fleet/` is `0700`
- No privileged operations, no root, no containers

## Comparison: when to leave poor man's land

| Symptom | You need |
|---|---|
| 5+ hosts | Nomad / k3s |
| Sub-second latency | In-process queue (Celery) |
| DAGs / retries / priorities | Temporal |
| Pretty graphs | Prometheus + Grafana |
| SLA dashboards for clients | PagerDuty + Datadog |
| Auto-failover mid-job | Raft / etcd / Postgres |

If none of those apply, you can stay poor man's for a long time.
