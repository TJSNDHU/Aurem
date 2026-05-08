#!/usr/bin/env bash
# AUREM — iter 305f dedup & DNS cleanup orchestrator
#
# Runs, in order:
#   FIX 1  Backfill dedup keys on db.auto_built_sites         (safe / idempotent)
#   FIX 2  Reports dedup patch status                         (read-only)
#   FIX 3  Cloudflare DNS orphan CNAME cleanup                (interactive)
#   FIX 4  Prune duplicate archived/draft site docs            (interactive)
#
# Run:  bash /app/scripts/run_all_fixes.sh
#       bash /app/scripts/run_all_fixes.sh --yes   # non-interactive

set -e
AUTO=""
[[ "$1" == "--yes" || "$1" == "-y" ]] && AUTO="--yes"

echo "========================================"
echo "  AUREM Dedup & DNS Fix Suite (305f)"
echo "========================================"

# ── env ─────────────────────────────────────
if [ ! -f /app/backend/.env ]; then
  echo "ERR: /app/backend/.env missing"; exit 1
fi

# ── Fix 1 ───────────────────────────────────
echo ""
echo "--- FIX 1: Backfill dedup keys ------------------------"
python3 /app/scripts/backfill_dedup_keys.py

# ── Fix 2 (status report) ──────────────────
echo ""
echo "--- FIX 2: Dedup patch verification --------------------"
if grep -q '"drafting"' /app/backend/services/lead_dedup.py; then
  echo "  OK  find_existing_site now includes 'drafting' in block list."
else
  echo "  FAIL  lead_dedup.py is NOT patched. Edit manually."
  exit 1
fi

# ── Fix 3 (DNS) ─────────────────────────────
echo ""
echo "--- FIX 3: Cloudflare DNS cleanup ----------------------"
if [ -z "${CF_API_TOKEN:-}" ]; then
  echo "  SKIP  CF_API_TOKEN not set."
  echo "        Get a token (Edit zone DNS on aurem.live) and re-run:"
  echo "        export CF_API_TOKEN=... && bash $0 ${AUTO}"
else
  python3 /app/scripts/cf_dns_cleanup.py ${AUTO}
fi

# ── Fix 4 ───────────────────────────────────
echo ""
echo "--- FIX 4: Prune duplicate archived site docs ----------"
python3 /app/scripts/prune_archived_sites.py ${AUTO}

echo ""
echo "========================================"
echo "  All safe fixes completed."
echo "========================================"
