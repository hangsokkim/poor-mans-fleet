#!/usr/bin/env bash
# install.sh — per-host setup
set -e
FLEET_HOME="${FLEET_HOME:-$HOME/fleet}"
HERE="$(cd "$(dirname "$0")" && pwd)"

echo "→ installing to $FLEET_HOME"
mkdir -p "$FLEET_HOME"/{queue/pending,queue/running,queue/done,queue/failed,queue/dlq,inbox,outbox,state,logs,bin}

# copy files
cp -r "$HERE/bin" "$FLEET_HOME/"
chmod +x "$FLEET_HOME"/bin/*

# systemd
mkdir -p ~/.config/systemd/user
cp "$HERE/etc"/fleet-worker.service "$HERE/etc"/cross-watchdog.{service,timer} ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now fleet-worker.service
systemctl --user enable --now cross-watchdog.timer

# linger (so it survives logout)
if command -v loginctl >/dev/null 2>&1; then
  loginctl enable-linger $USER 2>/dev/null || true
fi

echo "✓ done. check: systemctl --user status fleet-worker.service"
