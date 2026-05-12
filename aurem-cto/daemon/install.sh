#!/usr/bin/env bash
# AUREM Legion Daemon Installer v1.0 (iter 322fa)
# Idempotent — safe to re-run.
#
# Usage:
#   curl -fsSL https://aurem.live/api/legion/install | sudo bash
#   -- or --
#   LEGION_DAEMON_TOKEN=xxx LEGION_QUEUE_URL=https://aurem.live ./install.sh

set -euo pipefail

G="\033[1;32m"; R="\033[1;31m"; Y="\033[1;33m"; B="\033[1;34m"; N="\033[0m"

banner() { echo -e "${B}═══ $* ═══${N}"; }
ok()     { echo -e "${G}✓ $*${N}"; }
warn()   { echo -e "${Y}! $*${N}"; }
fail()   { echo -e "${R}✗ $*${N}"; exit 1; }

trap 'fail "Install failed at line $LINENO. Check above for the error."' ERR

banner "AUREM Legion Daemon Installer v1.0"

# ── 1. OS check ─────────────────────────────────────────────────────
[[ "$(uname -s)" == "Linux" ]] || fail "This installer is Linux-only."

# ── 2. Need root for systemd / sudoers ──────────────────────────────
if [[ "$(id -u)" -ne 0 ]]; then
    fail "Please run as root (sudo)."
fi

# ── 3. System user ──────────────────────────────────────────────────
if id -u aurem-cto >/dev/null 2>&1; then
    ok "User aurem-cto already exists"
else
    useradd --system --shell /usr/sbin/nologin \
            --home-dir /opt/aurem-cto --create-home aurem-cto
    ok "Created system user aurem-cto"
fi

# ── 4. Directories ──────────────────────────────────────────────────
mkdir -p /opt/aurem-cto/daemon /var/log/aurem-cto
chown -R aurem-cto:aurem-cto /opt/aurem-cto /var/log/aurem-cto
ok "Directories ready"

# ── 5. Token + queue URL ────────────────────────────────────────────
: "${LEGION_QUEUE_URL:=https://aurem.live}"
if [[ -z "${LEGION_DAEMON_TOKEN:-}" ]]; then
    if [[ -t 0 ]]; then
        read -r -s -p "Paste LEGION_DAEMON_TOKEN (from /admin/legion-bridge): " LEGION_DAEMON_TOKEN
        echo
    else
        fail "LEGION_DAEMON_TOKEN not provided (set env var or run interactively)."
    fi
fi

cat > /opt/aurem-cto/daemon/.env <<EOF
LEGION_DAEMON_TOKEN=${LEGION_DAEMON_TOKEN}
LEGION_QUEUE_URL=${LEGION_QUEUE_URL}
LEGION_POLL_INTERVAL_S=5.0
EOF
chmod 600 /opt/aurem-cto/daemon/.env
chown aurem-cto:aurem-cto /opt/aurem-cto/daemon/.env
ok "Wrote /opt/aurem-cto/daemon/.env (chmod 600)"

# ── 6. Python + httpx ───────────────────────────────────────────────
command -v python3 >/dev/null || apt-get install -y python3 python3-pip
python3 -c "import httpx" 2>/dev/null || pip3 install --quiet httpx
ok "Python3 + httpx ready"

# ── 7. Pull the daemon source from the pod ──────────────────────────
if [[ -f "$(dirname "$0")/legion_daemon.py" ]]; then
    cp "$(dirname "$0")/legion_daemon.py" /opt/aurem-cto/daemon/legion_daemon.py
    ok "Copied local legion_daemon.py"
else
    curl -fsSL "${LEGION_QUEUE_URL}/api/legion/daemon-source" \
         -o /opt/aurem-cto/daemon/legion_daemon.py
    ok "Downloaded legion_daemon.py from ${LEGION_QUEUE_URL}"
fi
chown aurem-cto:aurem-cto /opt/aurem-cto/daemon/legion_daemon.py
chmod 755 /opt/aurem-cto/daemon/legion_daemon.py

# ── 8. Sudoers (NOPASSWD for specific commands only) ────────────────
cat > /etc/sudoers.d/aurem-cto <<'EOF'
# AUREM Legion Daemon — minimal passwordless sudo (iter 322fa)
aurem-cto ALL=(root) NOPASSWD: /usr/bin/docker, \
                                /usr/bin/docker-compose, \
                                /usr/bin/systemctl restart docker, \
                                /usr/bin/systemctl status docker, \
                                /usr/bin/apt-get update, \
                                /usr/bin/apt-get install -y *
EOF
chmod 0440 /etc/sudoers.d/aurem-cto
visudo -c >/dev/null
ok "Configured /etc/sudoers.d/aurem-cto"

# ── 9. systemd unit ─────────────────────────────────────────────────
cat > /etc/systemd/system/legion-daemon.service <<'EOF'
[Unit]
Description=AUREM Legion Reverse-Poll Daemon
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=aurem-cto
Group=aurem-cto
EnvironmentFile=/opt/aurem-cto/daemon/.env
ExecStart=/usr/bin/python3 /opt/aurem-cto/daemon/legion_daemon.py
Restart=on-failure
RestartSec=10
StandardOutput=append:/var/log/aurem-cto/daemon.log
StandardError=append:/var/log/aurem-cto/daemon.log

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now legion-daemon
ok "Enabled + started legion-daemon.service"

# ── 10. Verify ──────────────────────────────────────────────────────
sleep 6
if systemctl is-active --quiet legion-daemon; then
    ok "legion-daemon is RUNNING"
else
    warn "legion-daemon failed to start — see /var/log/aurem-cto/daemon.log"
    journalctl -u legion-daemon --no-pager -n 20
    exit 3
fi

echo
banner "Last 8 lines of daemon.log:"
tail -n 8 /var/log/aurem-cto/daemon.log 2>/dev/null || true

echo
banner "Health check against pod:"
curl -fsS "${LEGION_QUEUE_URL}/api/legion/queue/_/health" || warn "Pod unreachable — check token + URL"
echo

banner "Install COMPLETE"
echo -e "${G}Legion is now controllable by ORA via the queue.${N}"
echo -e "Logs:    ${B}tail -f /var/log/aurem-cto/daemon.log${N}"
echo -e "Status:  ${B}systemctl status legion-daemon${N}"
echo -e "Restart: ${B}sudo systemctl restart legion-daemon${N}"
