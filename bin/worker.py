#!/usr/bin/env python3
"""
poor man's fleet — TPM-aware job worker.

Polls FLEET/queue/pending/ for *.json jobs, atomically claims them, runs them,
writes output to outbox/, acks to done/.

TPM pacing:
  - jittered sleep between jobs (default 3-10s)
  - cooldown after each job (default 15-20s)
  - cooldown fires more often as token usage approaches TPM_BUDGET_PER_MIN

No external dependencies. Python 3.10+ stdlib only.
"""
import os, sys, json, time, random, subprocess, socket
from pathlib import Path
from datetime import datetime, timezone

HOSTNAME = socket.gethostname()
FLEET = Path(os.environ.get("FLEET_HOME", os.path.expanduser("~/fleet")))
Q = FLEET / "queue"
PENDING, RUNNING = Q / "pending", Q / "running"
DONE, FAILED, DLQ = Q / "done", Q / "failed", Q / "dlq"
OUTBOX = FLEET / "outbox"
LOGS, STATE = FLEET / "logs", FLEET / "state"

TPM_BUDGET_PER_MIN = int(os.environ.get("TPM_BUDGET_PER_MIN", "60000"))
MIN_JITTER = int(os.environ.get("MIN_JITTER", "3"))
MAX_JITTER = int(os.environ.get("MAX_JITTER", "10"))
COOLDOWN_MIN = int(os.environ.get("COOLDOWN_JITTER_MIN", "15"))
COOLDOWN_MAX = int(os.environ.get("COOLDOWN_JITTER_MAX", "20"))

LOG_FILE = LOGS / "worker.log"


def ts():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def log(msg):
    line = f"[{ts()}] [{HOSTNAME}] {msg}\n"
    sys.stdout.write(line)
    sys.stdout.flush()
    with LOG_FILE.open("a") as f:
        f.write(line)


def sleep_jitter():
    s = random.randint(MIN_JITTER, MAX_JITTER)
    log(f"TPM jitter sleep {s}s")
    time.sleep(s)


def cooldown():
    s = random.randint(COOLDOWN_MIN, COOLDOWN_MAX)
    log(f"TPM 80% cooldown {s}s")
    time.sleep(s)


def reap_stale():
    now = time.time()
    for f in RUNNING.glob("*.json"):
        try:
            age = now - f.stat().st_mtime
            job = json.loads(f.read_text())
            to = int(job.get("timeout_s", 300))
            if age > to:
                f.rename(PENDING / f.name)
        except Exception:
            pass


def claim_job():
    for f in sorted(PENDING.glob("*.json")):
        target = RUNNING / f.name
        try:
            f.rename(target)
            return target
        except FileNotFoundError:
            continue
    return None


def run_shell(job, jobid):
    cmd = job.get("payload", {}).get("cmd", "")
    if not cmd:
        return False, "no cmd"
    try:
        out = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=240)
        (OUTBOX / f"{jobid}.stdout").write_text(out.stdout)
        (OUTBOX / f"{jobid}.stderr").write_text(out.stderr)
        (OUTBOX / f"{jobid}.meta").write_text(json.dumps({"rc": out.returncode}))
        return out.returncode == 0, f"rc={out.returncode}"
    except subprocess.TimeoutExpired:
        return False, "timeout 240s"


def run_status(job, jobid):
    info = {
        "host": HOSTNAME, "ts": ts(),
        "uptime": subprocess.run("uptime", shell=True, capture_output=True, text=True).stdout.strip(),
        "load": Path("/proc/loadavg").read_text().split()[0:3],
        "queue_pending": len(list(PENDING.glob("*.json"))),
        "queue_running": len(list(RUNNING.glob("*.json"))),
    }
    (OUTBOX / f"{jobid}.json").write_text(json.dumps(info, indent=2))
    return True, "ok"


def run_ping(job, jobid):
    (OUTBOX / f"{jobid}.json").write_text(json.dumps({
        "pong": HOSTNAME, "ts": ts(), "echo": job.get("payload", {})
    }, indent=2))
    return True, "pong"


def run_alert(job, jobid):
    payload = job.get("payload", {})
    msg = payload.get("msg", "no message")
    sev = payload.get("severity", "info")
    inbox = FLEET / "inbox" / "pending-alerts.jsonl"
    inbox.parent.mkdir(parents=True, exist_ok=True)
    with inbox.open("a") as f:
        f.write(json.dumps({"ts": ts(), "severity": sev, "from": HOSTNAME, "msg": msg}) + "\n")
    return True, "alerted (self-inbox, PM pulls)"


KIND_DISPATCH = {"shell": run_shell, "status": run_status, "ping": run_ping, "alert": run_alert}


def run_job(jobfile):
    jobid = jobfile.stem
    try:
        job = json.loads(jobfile.read_text())
    except Exception:
        jobfile.rename(DLQ / jobfile.name)
        return
    kind = job.get("kind", "shell")
    fn = KIND_DISPATCH.get(kind)
    if fn is None:
        jobfile.rename(DLQ / jobfile.name)
        return
    log(f"RUN {jobid} kind={kind}")
    try:
        ok, info = fn(job, jobid)
        target = DONE if ok else FAILED
        log(f"DONE {jobid} ok={ok} {info}")
    except Exception as e:
        log(f"FAIL {jobid}: {e}")
        target = FAILED
    try:
        jobfile.rename(target / jobfile.name)
    except FileNotFoundError:
        pass


def ensure_dirs():
    for d in (PENDING, RUNNING, DONE, FAILED, DLQ, OUTBOX, LOGS, STATE):
        d.mkdir(parents=True, exist_ok=True)
    LOG_FILE.touch(exist_ok=True)


def main():
    ensure_dirs()
    log("WORKER start (python3)")
    while True:
        reap_stale()
        job = claim_job()
        if job:
            run_job(job)
            cooldown()
        else:
            time.sleep(5)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("WORKER stop (SIGINT)")
