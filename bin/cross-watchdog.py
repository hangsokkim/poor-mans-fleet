#!/usr/bin/env python3
"""Cross-watchdog: peer health check + alert routing."""
import os, json, time, subprocess
from pathlib import Path
from datetime import datetime, timezone

HOSTNAME = os.uname().nodename
FLEET = Path(os.environ.get("FLEET_HOME", os.path.expanduser("~/fleet")))
INBOX = FLEET / "inbox" / "pending-alerts.jsonl"
STATE = FLEET / "state" / "cross-watchdog.json"

# ssh aliases to peers. Configure in ~/.ssh/config.
PEERS = ["pm", "worker-a", "worker-b"]

# Self-detection
SHORT = HOSTNAME.split(".")[0]
SELF = {HOSTNAME, SHORT, "pm" if "pm" in SHORT.lower() else None,
        "worker-a" if "a" == SHORT[-1:] else None,
        "worker-b" if "b" == SHORT[-1:] else None}
PEERS = [p for p in PEERS if p not in SELF and p is not None]


def ts():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def check_peer(alias):
    try:
        r = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=3", "-o", "BatchMode=yes",
             "-o", "StrictHostKeyChecking=accept-new", alias,
             "systemctl --user is-active fleet-worker.service"],
            capture_output=True, text=True, timeout=8,
        )
        return r.stdout.strip() == "active"
    except Exception:
        return None  # unknown, skip


def main():
    state = {"last_alert_ts": {}}
    if STATE.exists():
        try:
            state = json.loads(STATE.read_text())
        except Exception:
            pass

    alerts = []
    for alias in PEERS:
        ok = check_peer(alias)
        if ok is False:
            last = state["last_alert_ts"].get(alias, "")
            now_ts = time.time()
            if not last or (now_ts - _parse_ts(last)) > 300:
                alerts.append({"ts": ts(), "severity": "critical", "from": HOSTNAME,
                               "msg": f"PEER DOWN: {alias} worker inactive"})
                state["last_alert_ts"][alias] = ts()
        elif ok is True:
            state["last_alert_ts"].pop(alias, None)

    if alerts:
        INBOX.parent.mkdir(parents=True, exist_ok=True)
        with INBOX.open("a") as f:
            for a in alerts:
                f.write(json.dumps(a) + "\n")
        print(f"[{ts()}] alerts pushed: {len(alerts)}")

    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2))


def _parse_ts(s):
    try:
        return datetime.fromisoformat(s).timestamp()
    except Exception:
        return 0


if __name__ == "__main__":
    main()
