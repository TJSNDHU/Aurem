"""
Migration: campaign_leads — v1 cleanup (iter 265).

Idempotent — running twice is a no-op. Safe for both sandbox Mongo and
production Atlas.

Fixes:
  1. Drop orphan ``stage`` field where it duplicates ``lifecycle_stage``.
  2. Backfill ``blast_count=0`` and ``last_blasted_at=None`` for pre-pipeline
     leads that predate those fields.
  3. Remove any known legacy ``_v1`` suffixed fields if they ever appeared
     in a prior build (defensive — preview shows 0, but Atlas may differ).

Run:
    python3 scripts/migrate_campaign_leads_v1.py
    python3 scripts/migrate_campaign_leads_v1.py --dry-run
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402


LEGACY_FIELDS = [
    "blast_status_v1",
    "blast_result_v1",
    "outreach_v1",
    "sent_email_v1",
    "sent_sms_v1",
    "sent_whatsapp_v1",
    "old_schema_version",
    "legacy_outreach_log",
]


async def run(dry_run: bool = False) -> int:
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    leads = db.campaign_leads

    total = await leads.count_documents({})
    if total == 0:
        print("campaign_leads is empty — nothing to migrate.")
        return 0

    report = {"fix1": 0, "fix2": 0, "fix3": 0}
    mode = "DRY-RUN" if dry_run else "APPLY"
    print(f"\n🔧 migrate_campaign_leads_v1 ({mode}) — {total} leads\n")

    # ── Fix 1: drop orphan `stage` when `lifecycle_stage` already set ──
    q1 = {"stage": {"$exists": True}, "lifecycle_stage": {"$exists": True}}
    fix1 = await leads.count_documents(q1)
    report["fix1"] = fix1
    print(f"  1. Orphan `stage` field (duplicate of lifecycle_stage): {fix1} docs")
    if fix1 and not dry_run:
        r = await leads.update_many(q1, {"$unset": {"stage": ""}})
        print(f"     ✓ unset on {r.modified_count} docs")

    # ── Fix 2: backfill blast_count=0 / last_blasted_at=None ──
    q2 = {
        "$or": [
            {"blast_count": {"$exists": False}},
            {"last_blasted_at": {"$exists": False}},
        ]
    }
    fix2 = await leads.count_documents(q2)
    report["fix2"] = fix2
    print(f"  2. Missing `blast_count` / `last_blasted_at`:            {fix2} docs")
    if fix2 and not dry_run:
        # Use two targeted updates so we only set the missing field on each doc.
        r1 = await leads.update_many(
            {"blast_count": {"$exists": False}},
            {"$set": {"blast_count": 0}},
        )
        r2 = await leads.update_many(
            {"last_blasted_at": {"$exists": False}},
            {"$set": {"last_blasted_at": None}},
        )
        print(
            f"     ✓ blast_count backfilled on {r1.modified_count} docs, "
            f"last_blasted_at on {r2.modified_count} docs"
        )

    # ── Fix 3: strip any known legacy _v1 fields (defensive) ──
    q3 = {"$or": [{f: {"$exists": True}} for f in LEGACY_FIELDS]}
    fix3 = await leads.count_documents(q3)
    report["fix3"] = fix3
    print(f"  3. Known legacy `_v1` fields (defensive sweep):         {fix3} docs")
    if fix3 and not dry_run:
        unset = {f: "" for f in LEGACY_FIELDS}
        r = await leads.update_many(q3, {"$unset": unset})
        print(f"     ✓ stripped {len(LEGACY_FIELDS)} fields on {r.modified_count} docs")

    # ── Migration marker ──
    if not dry_run:
        await db.migrations.update_one(
            {"_id": "campaign_leads_v1_cleanup"},
            {
                "$set": {
                    "ran_at": datetime.now(timezone.utc).isoformat(),
                    "report": report,
                    "total_leads": total,
                }
            },
            upsert=True,
        )
        print("\n  ℹ  migration marker saved to db.migrations")

    touched = sum(report.values())
    print(
        f"\n{'✅ Dry-run complete' if dry_run else '✅ Migration complete'} — "
        f"{touched} total touch-points across {total} leads.\n"
    )
    return 0 if touched >= 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    return asyncio.run(run(dry_run=args.dry_run))


if __name__ == "__main__":
    sys.exit(main())
