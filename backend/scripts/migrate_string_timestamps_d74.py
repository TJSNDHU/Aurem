"""
scripts/migrate_string_timestamps_d74.py — iter D-74

Single-pass migration of string-stored timestamp fields → BSON Date.

REAL FIX, NO MOCKS. This is the script the founder will run during a
quiet maintenance window per the D-74 plan.

Behavior
--------
* Reads the 359 collection-field pairs from the live `aurem_db` (NOT
  hardcoded — fresh scan each run so it stays correct as schema
  evolves).
* For each pair: bulk converts string `created_at`/`ts`/`timestamp`/
  etc to BSON `Date` via a `$set` aggregation pipeline (1 round trip
  per collection, no per-doc query).
* Skips and LOGS rows where the value is missing, empty, or
  unparseable (so a single malformed doc doesn't kill the migration).
* Dry-run mode (`AUREM_TS_MIGRATION_DRY_RUN=true`) — prints what
  WOULD change without writing.
* Single mongodump call covers all collections — the founder runs it
  BEFORE this script.

Run
---
    # 1. mongodump first (founder side)
    mongodump --uri="$MONGO_URL" --db="$DB_NAME" \\
              --out=/tmp/aurem_db_pre_d74_$(date +%Y%m%d_%H%M).dump

    # 2. dry-run to verify counts
    AUREM_TS_MIGRATION_DRY_RUN=true python3 \\
       /app/backend/scripts/migrate_string_timestamps_d74.py

    # 3. real migration
    AUREM_TS_MIGRATION_DRY_RUN=false python3 \\
       /app/backend/scripts/migrate_string_timestamps_d74.py

    # 4. verify TTL indexes are now firing (counts drop)
    python3 -c "import asyncio; ..."   # see D-74 verification section
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
from datetime import datetime

from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

sys.path.insert(0, "/app/backend")
load_dotenv("/app/backend/.env")

TIMESTAMP_FIELDS = (
    "created_at", "updated_at", "ts", "timestamp",
    "at", "last_seen", "completed_at", "archived_at",
    "started_at", "ended_at", "logged_at", "fired_at",
    "expires_at", "deleted_at",
)

DRY_RUN = (os.environ.get("AUREM_TS_MIGRATION_DRY_RUN") or "").lower() in (
    "1", "true", "yes",
)


async def _discover_pairs(db) -> list[tuple[str, str, int]]:
    """Walk every collection. For each timestamp field present, count
    how many rows store it as a string. Returns (coll, field, str_count)."""
    pairs = []
    colls = await db.list_collection_names()
    for c in sorted(colls):
        # Skip system collections
        if c.startswith("system."):
            continue
        try:
            sample = await db[c].find_one({}, {})
        except Exception:
            continue
        if not sample:
            continue
        for field in TIMESTAMP_FIELDS:
            if field not in sample:
                continue
            try:
                n = await db[c].count_documents({field: {"$type": "string"}})
            except Exception:
                continue
            if n > 0:
                pairs.append((c, field, n))
    return pairs


async def _migrate_pair(db, coll: str, field: str, expected: int) -> dict:
    """Cast `coll.field` from string → BSON Date in one aggregation
    pipeline update. Skips blank/unparseable values."""
    started = time.time()

    # Mongo 4.2+ supports update-with-aggregation-pipeline. We use
    # $dateFromString with onError + onNull = REMOVE so bad values
    # are silently dropped instead of nuking the whole field.
    pipeline = [
        {"$set": {
            field: {
                "$dateFromString": {
                    "dateString": f"${field}",
                    "onError": f"${field}",  # keep original on parse error
                    "onNull":  f"${field}",  # keep null/missing as-is
                },
            },
        }},
    ]
    flt = {field: {"$type": "string"}}

    if DRY_RUN:
        # Aggregation that PROJECTS what WOULD change — does not write
        sample_cur = db[coll].aggregate([
            {"$match": flt},
            {"$limit": 5},
            {"$project": {
                "_id": 1,
                field: 1,
                f"_new_{field}": {
                    "$dateFromString": {
                        "dateString": f"${field}",
                        "onError": None,
                        "onNull": None,
                    },
                },
            }},
        ])
        sample = await sample_cur.to_list(5)
        unparseable_count = 0
        try:
            unparseable_count = await db[coll].count_documents({
                field: {"$type": "string"},
                "$expr": {
                    "$eq": [
                        {"$dateFromString": {
                            "dateString": f"${field}",
                            "onError": None,
                            "onNull": None,
                        }},
                        None,
                    ],
                },
            })
        except Exception as e:
            print(f"      [DRY] could not count unparseable: {e}")
        elapsed = (time.time() - started) * 1000
        return {
            "coll": coll,
            "field": field,
            "matched": expected,
            "modified": 0,
            "unparseable": unparseable_count,
            "elapsed_ms": elapsed,
            "dry_run": True,
            "sample": sample[:2],
        }

    try:
        result = await db[coll].update_many(flt, pipeline)
    except Exception as e:
        return {
            "coll": coll,
            "field": field,
            "matched": expected,
            "modified": 0,
            "error": str(e)[:200],
            "elapsed_ms": (time.time() - started) * 1000,
        }

    elapsed = (time.time() - started) * 1000
    # Re-count surviving strings — any non-zero is unparseable rows
    surviving = await db[coll].count_documents({field: {"$type": "string"}})
    return {
        "coll": coll,
        "field": field,
        "matched": result.matched_count,
        "modified": result.modified_count,
        "surviving_strings": surviving,
        "elapsed_ms": elapsed,
    }


async def main():
    cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = cli[os.environ["DB_NAME"]]
    mode = "DRY-RUN" if DRY_RUN else "LIVE"
    print(f"=== D-74 string-timestamp migration — {mode} ===")
    print(f"Started at {datetime.utcnow().isoformat()}Z")
    print()

    pairs = await _discover_pairs(db)
    total_rows = sum(n for *_, n in pairs)
    print(f"Discovered {len(pairs)} (coll, field) pairs holding {total_rows:,} string timestamps")
    print()

    # Sort largest first so the biggest wins land early
    pairs.sort(key=lambda p: -p[2])

    by_status = {"ok": 0, "partial": 0, "error": 0}
    summary_rows = []
    for i, (coll, field, expected) in enumerate(pairs, 1):
        print(f"  [{i}/{len(pairs)}] {coll}.{field}  ({expected:,} rows)", flush=True)
        result = await _migrate_pair(db, coll, field, expected)
        if "error" in result:
            by_status["error"] += 1
            print(f"      ERROR: {result['error']}")
        elif result.get("surviving_strings", 0) > 0:
            by_status["partial"] += 1
            print(f"      modified {result.get('modified',0):,}, "
                  f"{result.get('surviving_strings',0):,} unparseable left")
        else:
            by_status["ok"] += 1
            if DRY_RUN:
                print(f"      DRY: would migrate {result['matched']:,}, "
                      f"{result.get('unparseable',0):,} unparseable")
            else:
                print(f"      migrated {result.get('modified',0):,} in "
                      f"{result.get('elapsed_ms',0):.0f}ms")
        summary_rows.append(result)

    print()
    print("=== summary ===")
    for status, n in by_status.items():
        print(f"  {status}: {n}")
    total_modified = sum(r.get("modified", 0) for r in summary_rows)
    total_surviving = sum(r.get("surviving_strings", 0) for r in summary_rows)
    print(f"  total modified: {total_modified:,}")
    print(f"  unparseable left: {total_surviving:,}")
    print()
    print(f"Finished at {datetime.utcnow().isoformat()}Z")


if __name__ == "__main__":
    asyncio.run(main())
