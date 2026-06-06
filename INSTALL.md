# Install (poor man's edition)

## What you need

- 2-3 Linux boxes (Ubuntu, Debian, Fedora, Arch — anything with `systemd --user`)
- `python3` 3.10+ (stdlib only — no `pip install` anything)
- `ssh` + key auth between them (one `ssh-copy-id` per pair)
- A directory you can write to on each box (default: `~/fleet/`)

## 1. Clone

```bash
git clone https://github.com/<you>/poor-mans-fleet
cd poor-mans-fleet
```

## 2. Pick your FLEET_HOME

Default is `~/fleet/`. Override with the `FLEET_HOME` env var if you want
elsewhere (e.g. `$FLEET_HOME`).

## 3. Per-host install

Run on each box:

```bash
./install.sh                # installs to ~/fleet
FLEET_HOME=~/elsewhere ./install.sh
```

The installer:
- creates `$FLEET_HOME/{queue,inbox,outbox,state,logs,bin,etc}`
- copies `worker.py` and friends
- installs systemd `--user` units
- enables + starts `fleet-worker.service`
- enables `openclaw-watchdog.timer` and `cross-watchdog.timer`

## 4. Cross-host ssh

```bash
# from each box, trust the others
ssh-copy-id pm
ssh-copy-id worker-a
ssh-copy-id worker-b
```

## 5. Verify

From PM:
```bash
./bin/fleet-status
./bin/fleet-submit worker-a ping
sleep 5
./bin/fleet-status
```

You should see 1 in `done/` and a green `active` for `worker-a` on the dashboard.

## Customization

| Env var | Default | What |
|---|---|---|
| `TPM_BUDGET_PER_MIN` | 60000 | Token budget per worker |
| `MIN_JITTER` | 3 | Min seconds between jobs |
| `MAX_JITTER` | 10 | Max seconds between jobs |
| `COOLDOWN_JITTER_MIN` | 15 | Min seconds after each job |
| `COOLDOWN_JITTER_MAX` | 20 | Max seconds after each job |
| `FLEET_HOME` | `~/fleet` | Base directory |

Edit the systemd unit (`~/.config/systemd/user/fleet-worker.service`) to set them.

## What this won't do

- Won't survive a host disappearing mid-job (the job reaps back to `pending`
  on next worker boot — it doesn't auto-fail-over to another host)
- Won't deduplicate jobs you accidentally submit twice
- Won't give you pretty graphs

If you need any of that, this isn't the repo for you.
