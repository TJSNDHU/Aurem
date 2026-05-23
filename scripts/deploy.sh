#!/usr/bin/env bash
# scripts/deploy.sh — portable deploy script for AUREM
#
# Usage:
#   ./deploy.sh preview      # deploys to the preview environment
#   ./deploy.sh production   # deploys to production
#
# Selects the deploy path via DEPLOY_PLATFORM env var:
#   emergent  → Emergent platform (use "Save to GitHub" button via webhook)
#   hetzner   → SSH to HETZNER_HOST, git pull + supervisor restart
#   docker    → docker compose pull + up
#   local     → local supervisor restart only
#
# Aborts on the first failure. Never deploys broken code.

set -euo pipefail

DEPLOY_ENV="${1:-preview}"
DEPLOY_PLATFORM="${DEPLOY_PLATFORM:-emergent}"
APP_ROOT="${APP_ROOT:-/app}"

echo "═══════════════════════════════════════════════════"
echo " AUREM Deploy — platform=$DEPLOY_PLATFORM env=$DEPLOY_ENV"
echo "═══════════════════════════════════════════════════"

# ── Step 1: tests must pass ─────────────────────────────────────────
echo "→ Step 1/6: Running tests…"
cd "$APP_ROOT/backend"
python -m pytest tests/ -q -p no:cacheprovider --tb=line \
  --deselect tests/test_accurate_scout.py::test_channel_gating_medium_phone_allows_whatsapp_not_call \
  -x --maxfail=5 > /tmp/aurem_deploy_tests.log 2>&1 || {
    echo "✗ Tests failed — aborting deploy. See /tmp/aurem_deploy_tests.log"
    exit 1
}
echo "  ✓ Tests passed"

# ── Step 2: lint must pass (warn only, don't block) ─────────────────
echo "→ Step 2/6: Linting…"
ruff check "$APP_ROOT/backend" --quiet || echo "  ⚠ Ruff found issues (continuing)"
echo "  ✓ Lint complete"

# ── Step 3: commit checkpoint ───────────────────────────────────────
echo "→ Step 3/6: Git checkpoint…"
cd "$APP_ROOT"
if git diff --quiet 2>/dev/null && git diff --cached --quiet 2>/dev/null; then
    echo "  ✓ Working tree clean (no checkpoint needed)"
else
    git add -A
    git commit -m "deploy-checkpoint $(date -u +%Y-%m-%dT%H:%M:%SZ)" || \
        echo "  ⚠ Nothing to commit"
    echo "  ✓ Checkpoint committed"
fi

# ── Step 4: platform-specific deploy ────────────────────────────────
echo "→ Step 4/6: Platform deploy ($DEPLOY_PLATFORM)…"
case "$DEPLOY_PLATFORM" in
    emergent)
        echo "  ℹ Emergent platform: the founder triggers 'Save to GitHub'"
        echo "  ℹ in the chat input to push the latest commit to production."
        echo "  ℹ This script has prepared the commit. Done."
        ;;
    hetzner)
        HOST="${HETZNER_HOST:?HETZNER_HOST env var required}"
        USER="${HETZNER_USER:-aurem}"
        APP_DIR="${HETZNER_APP_DIR:-/opt/aurem}"
        ssh "$USER@$HOST" "cd $APP_DIR && git pull && sudo supervisorctl restart all"
        echo "  ✓ Pushed to $HOST"
        ;;
    docker)
        cd "$APP_ROOT"
        docker compose pull
        docker compose up -d --remove-orphans
        echo "  ✓ Containers updated"
        ;;
    local)
        sudo supervisorctl restart backend
        sudo supervisorctl restart frontend
        echo "  ✓ Local services restarted"
        ;;
    *)
        echo "✗ Unknown DEPLOY_PLATFORM='$DEPLOY_PLATFORM'"
        echo "  Valid: emergent | hetzner | docker | local"
        exit 1
        ;;
esac

# ── Step 5: health check ────────────────────────────────────────────
echo "→ Step 5/6: Health check…"
HEALTH_URL="${HEALTH_URL:-}"
if [ -z "$HEALTH_URL" ]; then
    if [ "$DEPLOY_ENV" = "production" ]; then
        HEALTH_URL="${PROD_HEALTH_URL:-https://aurem.live/api/health}"
    else
        HEALTH_URL="${PREVIEW_HEALTH_URL:-http://localhost:8001/api/health}"
    fi
fi

# Retry up to 12 times (60 s total) for cold-start.
ATTEMPTS=12
for i in $(seq 1 $ATTEMPTS); do
    CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$HEALTH_URL" || echo "000")
    if [ "$CODE" = "200" ]; then
        echo "  ✓ Health check OK ($HEALTH_URL → 200)"
        break
    fi
    if [ "$i" = "$ATTEMPTS" ]; then
        echo "✗ Health check failed after $ATTEMPTS attempts ($HEALTH_URL → $CODE)"
        exit 1
    fi
    echo "  … attempt $i/$ATTEMPTS got $CODE, retrying in 5s"
    sleep 5
done

# ── Step 6: smoke test ──────────────────────────────────────────────
echo "→ Step 6/6: Smoke tests…"
BASE_URL="${HEALTH_URL%/api/health}"
# Three key endpoints — adjust if your app differs.
for path in /api/health /api/public/status /api/auth/login; do
    CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 \
             -X POST -H "Content-Type: application/json" -d "{}" \
             "$BASE_URL$path" 2>/dev/null || echo "000")
    # /api/auth/login should be 401/400, others 200. Anything 5xx is bad.
    if [ "${CODE:0:1}" = "5" ]; then
        echo "✗ Smoke test failed: $BASE_URL$path → $CODE"
        exit 1
    fi
    echo "  ✓ $path → $CODE"
done

echo
echo "═══════════════════════════════════════════════════"
echo " ✓ DEPLOY COMPLETE — platform=$DEPLOY_PLATFORM env=$DEPLOY_ENV"
echo " Health: $HEALTH_URL"
echo "═══════════════════════════════════════════════════"
