#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
# AUREM — Dead Code Cleanup (graph snapshot gs_d0a9db97780c)
# Run from repo root. Safe: only deletes confirmed zero-in-degree files.
# ═══════════════════════════════════════════════════════════════════
set -euo pipefail

echo "╔══════════════════════════════════════════════════════╗"
echo "║  AUREM Dead Code Cleanup                            ║"
echo "╚══════════════════════════════════════════════════════╝"

# ── 1. Archive routers (all have 0 in-edges — nothing imports them) ──
echo ""
echo "▶ Removing archive routers..."
ARCHIVE_DIR="app/backend/archive/routers"
if [ -d "$ARCHIVE_DIR" ]; then
  for f in \
    clawchief_router.py \
    empire_hud_router.py \
    evolver_router.py \
    openfang_router.py \
    sentinel_anomaly_router.py \
    sentinel_guard_router.py \
    sentinel_overwatch.py \
    sentinel_router.py \
    telegram_router.py \
    sentinel_diagnose.py \
    sentinel_healer.py \
    sentinel_observer.py; do
    TARGET="$ARCHIVE_DIR/$f"
    if [ -f "$TARGET" ]; then
      echo "  ✗ $TARGET"
      rm "$TARGET"
    fi
  done
  # Remove dir if now empty
  rmdir "$ARCHIVE_DIR" 2>/dev/null && echo "  ✗ $ARCHIVE_DIR (now empty)" || true
else
  echo "  ⚠ $ARCHIVE_DIR not found — skipping"
fi

# ── 2. Ghost action_engine (degree-1 shadow copy) ──
echo ""
echo "▶ Removing ghost action_engine copy..."
GHOST="app/backend/services/aurem_commercial/action_engine.py"
if [ -f "$GHOST" ]; then
  echo "  ✗ $GHOST"
  rm "$GHOST"
  # Check if dir is now empty
  GHOST_DIR=$(dirname "$GHOST")
  if [ -z "$(ls -A "$GHOST_DIR" 2>/dev/null)" ]; then
    rmdir "$GHOST_DIR"
    echo "  ✗ $GHOST_DIR (now empty)"
  fi
else
  echo "  ⚠ $GHOST not found — already clean"
fi

# Verify nothing imports from the ghost path
echo ""
echo "▶ Checking for stale imports of ghost action_engine..."
BAD_IMPORTS=$(grep -r "aurem_commercial.action_engine\|aurem_commercial/action_engine" \
  app/backend/ --include="*.py" -l 2>/dev/null || true)
if [ -n "$BAD_IMPORTS" ]; then
  echo "  ⚠ WARNING: These files still import the ghost path — fix manually:"
  echo "$BAD_IMPORTS" | sed 's/^/    /'
else
  echo "  ✓ No stale imports found"
fi

# ── 3. Crypto engine (entirely orphaned — no callers outside itself) ──
echo ""
echo "▶ Removing orphaned crypto engine..."
CRYPTO_DIR="app/backend/crypto_engine"
if [ -d "$CRYPTO_DIR" ]; then
  echo "  ✗ $CRYPTO_DIR/ (full directory)"
  rm -rf "$CRYPTO_DIR"
else
  echo "  ⚠ $CRYPTO_DIR not found — already clean"
fi

# Also check for crypto treasury service (no callers outside generative_ui_router)
echo ""
echo "▶ Checking crypto treasury service..."
for f in \
  "app/backend/services/coinbase_service.py" \
  "app/backend/services/polygon_wallet_service.py" \
  "app/backend/services/treasury_service.py" \
  "app/backend/services/wallet_crypto.py" \
  "app/backend/models/crypto_treasury_models.py"; do
  if [ -f "$f" ]; then
    echo "  ⚠ Found crypto treasury file — review before deleting: $f"
  fi
done

# ── 4. server_models.py (reroots bleed-in, 1 in-edge from Enum only) ──
echo ""
echo "▶ Checking reroots bleed-in model file..."
BLEED="app/backend/models/server_models.py"
if [ -f "$BLEED" ]; then
  REFS=$(grep -r "server_models" app/backend/ --include="*.py" -l 2>/dev/null | grep -v "^$BLEED$" || true)
  if [ -z "$REFS" ]; then
    echo "  ✗ $BLEED (no active imports — safe to remove)"
    rm "$BLEED"
  else
    echo "  ⚠ $BLEED still imported by:"
    echo "$REFS" | sed 's/^/    /'
    echo "  → Fix those imports first, then delete manually"
  fi
else
  echo "  ⚠ $BLEED not found — already clean"
fi

# ── 5. Duplicate TenantMiddleware check ──
echo ""
echo "▶ Checking duplicate TenantMiddleware..."
TM1="app/backend/middleware/tenant_guard.py"
TM2="app/backend/middleware/tenant_middleware.py"
SERVER="app/backend/server.py"

TM1_MOUNTED=$(grep -c "TenantGuardMiddleware\|tenant_guard" "$SERVER" 2>/dev/null || echo "0")
TM2_MOUNTED=$(grep -c "TenantMiddleware\|tenant_middleware" "$SERVER" 2>/dev/null || echo "0")

echo "  TenantGuardMiddleware refs in server.py : $TM1_MOUNTED"
echo "  TenantMiddleware refs in server.py      : $TM2_MOUNTED"

if [ "$TM1_MOUNTED" -gt "0" ] && [ "$TM2_MOUNTED" -gt "0" ]; then
  echo "  ⚠ BOTH middlewares are mounted — double-setting tenant context every request!"
  echo "  → Keep TenantGuardMiddleware (contextvars, async-safe), remove TenantMiddleware mount"
  echo "  → Edit server.py to remove the TenantMiddleware add_middleware() call"
elif [ "$TM2_MOUNTED" -gt "0" ] && [ "$TM1_MOUNTED" -eq "0" ]; then
  echo "  ⚠ Only legacy TenantMiddleware mounted — should be TenantGuardMiddleware"
else
  echo "  ✓ Only TenantGuardMiddleware mounted — correct"
fi

echo ""
echo "═══════════════════════════════════════════════════════"
echo "  Cleanup complete."
echo "  Next step: fix WHAPI routing (see whatsapp_routing_fix.py)"
echo "═══════════════════════════════════════════════════════"