#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# AUREM Production Startup Script — Stability Hardening v2
# Validates ENV, waits for DB/Redis, then starts uvicorn
# ═══════════════════════════════════════════════════════════════

set -eo pipefail

PORT=${PORT:-8001}
HOST=${HOST:-0.0.0.0}
LOG_PREFIX="[AUREM-STARTUP]"

log() { echo "$LOG_PREFIX $(date '+%H:%M:%S') $1"; }
log_ok() { log "OK — $1"; }
log_warn() { log "WARN — $1"; }
log_fail() { log "FAIL — $1"; }

# ─────────────────────────────────────────────────────────────
# STEP 1: Check critical ENV vars
# ─────────────────────────────────────────────────────────────
log "Step 1/4: Checking environment variables..."

CRITICAL_VARS="MONGO_URL DB_NAME JWT_SECRET"
IMPORTANT_VARS="EMERGENT_LLM_KEY OPENROUTER_API_KEY STRIPE_SECRET_KEY DEEPGRAM_API_KEY GOOGLE_PAGESPEED_API_KEY"
OPTIONAL_VARS="REDIS_URL TWILIO_ACCOUNT_SID SENDGRID_API_KEY CLOUDINARY_API_KEY WHAPI_API_TOKEN HF_TOKEN"

MISSING_CRITICAL=0
for var in $CRITICAL_VARS; do
    val=$(printenv "$var" 2>/dev/null || echo "")
    if [ -z "$val" ]; then
        log_fail "$var is NOT SET (critical)"
        MISSING_CRITICAL=$((MISSING_CRITICAL + 1))
    else
        log_ok "$var is set"
    fi
done

for var in $IMPORTANT_VARS; do
    val=$(printenv "$var" 2>/dev/null || echo "")
    if [ -z "$val" ]; then
        log_warn "$var is NOT SET (important — some features degraded)"
    else
        log_ok "$var is set"
    fi
done

OPTIONAL_SET=0
OPTIONAL_MISSING=0
for var in $OPTIONAL_VARS; do
    val=$(printenv "$var" 2>/dev/null || echo "")
    if [ -z "$val" ]; then
        OPTIONAL_MISSING=$((OPTIONAL_MISSING + 1))
    else
        OPTIONAL_SET=$((OPTIONAL_SET + 1))
    fi
done
log "Optional vars: $OPTIONAL_SET set, $OPTIONAL_MISSING missing (non-blocking)"

if [ $MISSING_CRITICAL -gt 0 ]; then
    log_fail "$MISSING_CRITICAL critical variables missing — aborting"
    exit 1
fi
log_ok "All critical env vars present"

# ─────────────────────────────────────────────────────────────
# STEP 2: Wait for MongoDB
# ─────────────────────────────────────────────────────────────
log "Step 2/4: Waiting for MongoDB connection..."

MONGO_WAIT=0
MONGO_MAX=30
MONGO_READY=false

while [ $MONGO_WAIT -lt $MONGO_MAX ]; do
    if python3 -c "
import os, sys
from pymongo import MongoClient
url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
client = MongoClient(url, serverSelectionTimeoutMS=3000)
client.admin.command('ping')
print('connected')
sys.exit(0)
" 2>/dev/null | grep -q "connected"; then
        MONGO_READY=true
        break
    fi
    sleep 2
    MONGO_WAIT=$((MONGO_WAIT + 2))
    log "MongoDB not ready yet... (${MONGO_WAIT}s/${MONGO_MAX}s)"
done

if [ "$MONGO_READY" = true ]; then
    log_ok "MongoDB connected after ${MONGO_WAIT}s"
else
    log_fail "MongoDB not reachable after ${MONGO_MAX}s — aborting"
    exit 1
fi

# ─────────────────────────────────────────────────────────────
# STEP 3: Check Redis (non-blocking)
# ─────────────────────────────────────────────────────────────
log "Step 3/4: Checking Redis connection..."

REDIS_URL=$(printenv REDIS_URL 2>/dev/null || echo "")
if [ -z "$REDIS_URL" ]; then
    log_warn "REDIS_URL not set — using in-memory fallback"
else
    if python3 -c "
import os, sys
try:
    import redis
    r = redis.from_url(os.environ['REDIS_URL'], socket_timeout=5)
    r.ping()
    print('connected')
except Exception as e:
    print(f'failed: {e}')
    sys.exit(1)
" 2>/dev/null | grep -q "connected"; then
        log_ok "Redis connected"
    else
        log_warn "Redis unreachable — using in-memory fallback (non-blocking)"
    fi
fi

# ─────────────────────────────────────────────────────────────
# STEP 4: Start uvicorn
# ─────────────────────────────────────────────────────────────
log "Step 4/4: Starting uvicorn on ${HOST}:${PORT}..."

cd /app/backend
exec uvicorn server:app --host ${HOST} --port ${PORT} --workers 1 --reload
