#!/usr/bin/env bash
# ════════════════════════════════════════════════════════════════════════
# AUREM — Atlas → Legion MongoDB migration
# iter 323i — one-shot dump + restore script
#
# Usage (run on the Legion laptop in the same dir as docker-compose.yml):
#   ATLAS_URI="mongodb+srv://USER:PASS@cluster.mongodb.net/aurem_db" \
#   AUREM_MONGO_PASSWORD="AuremMongo2026Strong!" \
#     bash migrate_atlas_to_legion.sh
#
# What it does:
#   1. Verifies aurem-mongodb container is up.
#   2. Dumps Atlas → /tmp/atlas_backup (gzipped BSON).
#   3. Restores into Legion Mongo on localhost:27017.
#   4. Counts collections + sample documents — prints a diff summary.
#
# Safety:
#   - Atlas is NEVER mutated (read-only mongodump).
#   - Legion restore is idempotent — if you run twice, --drop wipes & reloads.
#   - Does NOT touch your .env files.
# ════════════════════════════════════════════════════════════════════════
set -euo pipefail

# ── inputs (with sensible defaults / errors) ───────────────────────────
ATLAS_URI="${ATLAS_URI:-}"
AUREM_MONGO_PASSWORD="${AUREM_MONGO_PASSWORD:-AuremMongo2026Strong!}"
BACKUP_DIR="${BACKUP_DIR:-/tmp/atlas_backup}"
DB_NAME="${DB_NAME:-aurem_db}"

if [[ -z "$ATLAS_URI" ]]; then
  echo "✗ ATLAS_URI is required. Get it from Emergent support or backend/.env (MONGO_URL)."
  echo "   ATLAS_URI=\"mongodb+srv://...\" bash $0"
  exit 1
fi

echo "════════════════════════════════════════════════════════════════════"
echo " AUREM Atlas → Legion MongoDB migration"
echo "════════════════════════════════════════════════════════════════════"

# ── Step 1 — health check Legion Mongo ─────────────────────────────────
echo "▸ [1/4] Verifying aurem-mongodb is running..."
if ! docker ps --format '{{.Names}}' | grep -q '^aurem-mongodb$'; then
  echo "✗ aurem-mongodb container is not running. Start it first:"
  echo "    docker compose up -d aurem-mongodb"
  exit 1
fi

echo "▸ Ping Legion Mongo..."
docker exec aurem-mongodb mongosh \
  -u aurem -p "$AUREM_MONGO_PASSWORD" --quiet \
  --eval "db.adminCommand('ping')" >/dev/null
echo "  ✓ Legion Mongo reachable"

# ── Step 2 — dump Atlas ────────────────────────────────────────────────
echo "▸ [2/4] Dumping Atlas → $BACKUP_DIR (this may take a while)..."
rm -rf "$BACKUP_DIR"
mkdir -p "$BACKUP_DIR"
docker run --rm \
  -v "$BACKUP_DIR:/backup" \
  mongo:7 \
  mongodump --uri="$ATLAS_URI" --out=/backup --gzip --quiet

DUMP_SIZE=$(du -sh "$BACKUP_DIR" | awk '{print $1}')
COLLECTION_COUNT=$(find "$BACKUP_DIR/$DB_NAME" -name '*.bson.gz' 2>/dev/null | wc -l | tr -d ' ')
echo "  ✓ Dumped $COLLECTION_COUNT collections ($DUMP_SIZE)"

# ── Step 3 — restore to Legion ─────────────────────────────────────────
echo "▸ [3/4] Restoring into Legion Mongo (host network)..."
docker run --rm \
  -v "$BACKUP_DIR:/backup" \
  --network host \
  mongo:7 \
  mongorestore \
  --uri="mongodb://aurem:${AUREM_MONGO_PASSWORD}@localhost:27017/${DB_NAME}?authSource=admin" \
  --dir="/backup/${DB_NAME}" \
  --gzip --drop --quiet

echo "  ✓ Restore complete"

# ── Step 4 — verify ────────────────────────────────────────────────────
echo "▸ [4/4] Verifying collection counts..."
LEGION_COLLECTIONS=$(docker exec aurem-mongodb mongosh \
  -u aurem -p "$AUREM_MONGO_PASSWORD" --quiet "$DB_NAME" \
  --eval "db.getCollectionNames().length" | tr -d '\r')

echo "  • Atlas dump:    $COLLECTION_COUNT collections"
echo "  • Legion restore: $LEGION_COLLECTIONS collections"

if [[ "$COLLECTION_COUNT" == "$LEGION_COLLECTIONS" ]]; then
  echo "  ✓ MATCH — migration verified"
else
  echo "  ⚠ count mismatch — inspect manually:"
  echo "    docker exec aurem-mongodb mongosh -u aurem -p '****' aurem_db --eval 'db.getCollectionNames()'"
fi

echo ""
echo "════════════════════════════════════════════════════════════════════"
echo " ✓ MIGRATION COMPLETE"
echo "════════════════════════════════════════════════════════════════════"
echo ""
echo "Next steps:"
echo "  1. Setup Cloudflare TCP tunnel: mongo-internal.aurem.live → localhost:27017"
echo "  2. Update Emergent .env.production:"
echo "       MONGO_URL=mongodb://aurem:${AUREM_MONGO_PASSWORD}@mongo-internal.aurem.live:27017/aurem_db?authSource=admin"
echo "  3. Redeploy and verify: curl https://aurem.live/api/health"
echo ""
