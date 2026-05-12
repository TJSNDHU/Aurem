#!/usr/bin/env bash
# bootstrap.sh — Idempotent installer for the Legion laptop.
# Sets up Docker + Cloudflared + brings the aurem-cto stack online.
# Safe to re-run; every step checks current state first.

set -euo pipefail

CTO_DIR="${CTO_DIR:-/opt/aurem-cto}"
COMPOSE_FILE="${COMPOSE_FILE:-${CTO_DIR}/docker-compose.yml}"

log() { echo -e "\033[1;36m[$(date +%H:%M:%S)] $*\033[0m"; }
ok()  { echo -e "\033[1;32m  ✓ $*\033[0m"; }
warn(){ echo -e "\033[1;33m  ! $*\033[0m"; }

# ── 1. Verify we're on Linux ────────────────────────────────────────
log "Bootstrap starting — target: ${CTO_DIR}"
if [[ "$(uname -s)" != "Linux" ]]; then
    echo "This script must run on Linux (Legion = Ubuntu)." >&2
    exit 1
fi

# ── 2. Install Docker if missing ────────────────────────────────────
if ! command -v docker >/dev/null 2>&1; then
    log "Docker not found — installing..."
    sudo apt-get update -y
    sudo apt-get install -y ca-certificates curl gnupg lsb-release
    sudo install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
        | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    sudo chmod a+r /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
        | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    sudo apt-get update -y
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io \
        docker-buildx-plugin docker-compose-plugin
    sudo systemctl enable --now docker
    ok "Docker installed"
else
    ok "Docker already present ($(docker --version))"
fi

# ── 3. Install cloudflared if missing ───────────────────────────────
if ! command -v cloudflared >/dev/null 2>&1; then
    log "cloudflared not found — installing..."
    curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg \
        | sudo tee /usr/share/keyrings/cloudflare-main.gpg > /dev/null
    echo "deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] \
https://pkg.cloudflare.com/cloudflared $(lsb_release -cs) main" \
        | sudo tee /etc/apt/sources.list.d/cloudflared.list > /dev/null
    sudo apt-get update -y
    sudo apt-get install -y cloudflared
    ok "cloudflared installed"
else
    ok "cloudflared already present"
fi

# ── 4. .env presence check ──────────────────────────────────────────
if [[ ! -f "${CTO_DIR}/.env" ]]; then
    warn "${CTO_DIR}/.env missing — copying template"
    cp "${CTO_DIR}/.env.example" "${CTO_DIR}/.env"
    echo
    echo "Edit ${CTO_DIR}/.env and fill in MONGO_URL, JWT_SECRET, etc."
    echo "Then re-run: $0"
    exit 0
fi
ok ".env present"

# ── 5. Build + start the stack ──────────────────────────────────────
log "Building containers..."
cd "${CTO_DIR}"
docker compose -f "${COMPOSE_FILE}" build
ok "Build complete"

log "Bringing services up..."
docker compose -f "${COMPOSE_FILE}" up -d
ok "Services started"

# ── 6. Health probe ─────────────────────────────────────────────────
log "Waiting for API to respond..."
for i in {1..30}; do
    if curl -fsS http://localhost:8002/api/health >/dev/null 2>&1; then
        ok "API healthy"
        curl -s http://localhost:8002/api/health
        echo
        break
    fi
    sleep 2
done

log "Bootstrap done. Next: configure cloudflared tunnel for cto.aurem.live."
echo "  cloudflared tunnel login"
echo "  cloudflared tunnel create aurem-cto-legion"
echo "  cloudflared tunnel route dns aurem-cto-legion cto.aurem.live"
echo "  sudo cp ${CTO_DIR}/cloudflared/config.yml /etc/cloudflared/"
echo "  sudo systemctl enable --now cloudflared"
