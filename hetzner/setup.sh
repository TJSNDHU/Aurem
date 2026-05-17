#!/usr/bin/env bash
# ════════════════════════════════════════════════════════════════════════
# AUREM — Hetzner one-shot bootstrap
# iter 323i
#
# Run as root on a fresh Ubuntu 24.04 server:
#   curl -fsSL https://raw.githubusercontent.com/<YOUR_REPO>/main/hetzner/setup.sh | bash
# OR after `git clone`:
#   sudo bash /opt/aurem/hetzner/setup.sh
# ════════════════════════════════════════════════════════════════════════
set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
ok()    { echo -e "${GREEN}✓${NC} $1"; }
info()  { echo -e "${YELLOW}▸${NC} $1"; }
fail()  { echo -e "${RED}✗${NC} $1"; exit 1; }

[[ $EUID -eq 0 ]] || fail "Run as root (sudo bash $0)"

REPO_DIR="${REPO_DIR:-/opt/aurem}"
DOMAIN="${DOMAIN:-aurem.live}"
EMAIL="${EMAIL:-tj@aurem.live}"
REPO_URL="${REPO_URL:-}"

echo "════════════════════════════════════════════════════════════════════"
echo " AUREM Hetzner bootstrap"
echo " domain=$DOMAIN  repo_dir=$REPO_DIR"
echo "════════════════════════════════════════════════════════════════════"

# ── 1. System update ──────────────────────────────────────────────────
info "[1/8] apt update + base packages"
apt-get update -qq
apt-get upgrade -y -qq
apt-get install -y -qq \
    docker.io docker-compose-v2 \
    git curl wget jq htop \
    nginx certbot python3-certbot-nginx \
    ufw fail2ban \
    unattended-upgrades
ok "base packages installed"

# ── 2. Firewall ───────────────────────────────────────────────────────
info "[2/8] ufw firewall"
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp comment 'SSH'
ufw allow 80/tcp comment 'HTTP'
ufw allow 443/tcp comment 'HTTPS'
ufw --force enable
ok "firewall up (22, 80, 443 only)"

# ── 3. Docker ─────────────────────────────────────────────────────────
info "[3/8] Docker"
systemctl enable --now docker
docker --version | sed 's/^/  /'
ok "Docker running"

# ── 4. Repo clone ─────────────────────────────────────────────────────
info "[4/8] Repo at $REPO_DIR"
if [[ -d "$REPO_DIR/.git" ]]; then
    cd "$REPO_DIR"
    git pull --ff-only
    ok "repo updated"
else
    if [[ -z "$REPO_URL" ]]; then
        fail "REPO_URL must be set on first run, e.g. REPO_URL=git@github.com:tj/aurem.git bash $0"
    fi
    git clone "$REPO_URL" "$REPO_DIR"
    cd "$REPO_DIR"
    ok "repo cloned"
fi

# ── 5. .env files ─────────────────────────────────────────────────────
info "[5/8] .env scaffolding"
if [[ ! -f "$REPO_DIR/backend/.env" ]]; then
    cat > "$REPO_DIR/backend/.env" <<EOF
# AUREM backend .env — Hetzner production
# Fill these from your existing Emergent production env
MONGO_URL=mongodb://aurem:CHANGE_ME@mongo-internal.aurem.live:27017/aurem_db?authSource=admin
DB_NAME=aurem_db
REDIS_URL=redis://aurem-redis:6379
JWT_SECRET=CHANGE_ME
ENCRYPTION_KEY=CHANGE_ME
AUREM_MASTER_KEY=CHANGE_ME
AUREM_ENV=production
SOVEREIGN_NODE_URL=https://sovereign.aurem.live
LOCAL_LLM_ENABLED=true
LOCAL_LLM_MODEL=llama3.1
EMERGENT_LLM_KEY=CHANGE_ME
GROQ_API_KEY=CHANGE_ME
STRIPE_SECRET_KEY=CHANGE_ME
STRIPE_PUBLISHABLE_KEY=CHANGE_ME
STRIPE_WEBHOOK_SECRET=CHANGE_ME
RESEND_API_KEY=CHANGE_ME
RESEND_FROM_EMAIL=noreply@aurem.live
TWILIO_ACCOUNT_SID=CHANGE_ME
TWILIO_AUTH_TOKEN=CHANGE_ME
TELEGRAM_BOT_TOKEN=CHANGE_ME
TELEGRAM_CHAT_ID=CHANGE_ME
EOF
    echo -e "${YELLOW}!! Created backend/.env with placeholders — edit before docker compose up${NC}"
fi
[[ -f "$REPO_DIR/frontend/.env" ]] || cat > "$REPO_DIR/frontend/.env" <<EOF
REACT_APP_BACKEND_URL=https://$DOMAIN
EOF
ok ".env files ready"

# ── 6. Nginx ──────────────────────────────────────────────────────────
info "[6/8] Nginx + SSL"
cp "$REPO_DIR/hetzner/nginx.conf" /etc/nginx/sites-available/aurem
ln -sf /etc/nginx/sites-available/aurem /etc/nginx/sites-enabled/aurem
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx

# Issue cert if not present
if [[ ! -d "/etc/letsencrypt/live/$DOMAIN" ]]; then
    info "Requesting Let's Encrypt cert for $DOMAIN"
    certbot --nginx \
        -d "$DOMAIN" -d "www.$DOMAIN" \
        --email "$EMAIL" --agree-tos --non-interactive --redirect || \
        echo -e "${YELLOW}!! certbot failed — DNS may not be pointed yet. Re-run later:${NC}"
fi
ok "Nginx + SSL configured"

# ── 7. Docker compose up ──────────────────────────────────────────────
info "[7/8] docker compose up -d (this builds images — takes a few minutes)"
cd "$REPO_DIR"
docker compose -f hetzner/docker-compose.yml --env-file backend/.env up -d --build
ok "containers up"

# ── 8. Health check ───────────────────────────────────────────────────
info "[8/8] Waiting 60s then checking /api/health"
sleep 60
if curl -fsS "http://localhost:8001/health" >/dev/null; then
    ok "backend /health → 200"
else
    fail "backend /health failed — check: docker compose -f hetzner/docker-compose.yml logs backend"
fi

echo ""
echo "════════════════════════════════════════════════════════════════════"
echo -e " ${GREEN}✓ BOOTSTRAP COMPLETE${NC}"
echo "════════════════════════════════════════════════════════════════════"
echo ""
echo "Next steps:"
echo "  1. Cloudflare DNS:  A  $DOMAIN  →  <this server IP>"
echo "  2. Edit backend/.env with real secrets (currently CHANGE_ME)"
echo "  3. docker compose -f hetzner/docker-compose.yml restart backend"
echo "  4. https://$DOMAIN should resolve"
echo ""
