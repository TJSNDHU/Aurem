"""
D-81b data cleanup — two surgical mutations, idempotent, dry-run by default.

Mutation 1: 304 `website_url`-only legacy leads (campaign_id=None or tenant_id=global, no
            business_id) → assign to founder BIN AUR-FNDR-001 so the campaign funnel
            stops double-counting them as cross-tenant ghosts.

Mutation 2: 1,564 leads with missing country field → infer from city. Default to CA for
            known ON / QC / BC / AB / MB cities (case-insensitive). Anything else → leave
            untouched (we don't guess US/UK from an empty field — would create false data).

Run dry first: python backend/scripts/cleanup_d81b.py
Apply:        python backend/scripts/cleanup_d81b.py --apply
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "aurem_db")
FOUNDER_BIN = "AUR-FNDR-001"

# City → country inference table. Keys are lowercased.
CITY_COUNTRY = {}
for city in [
    # Ontario
    "toronto", "mississauga", "brampton", "hamilton", "ottawa", "london", "markham",
    "vaughan", "kitchener", "windsor", "richmond hill", "oakville", "burlington",
    "barrie", "whitby", "guelph", "cambridge", "waterloo", "ajax", "pickering",
    "oshawa", "milton", "kingston", "thunder bay", "sudbury", "st. catharines",
    "niagara falls", "newmarket", "scarborough", "north york", "etobicoke", "york",
    "east york", "ontario",
    # Quebec
    "montreal", "quebec city", "laval", "gatineau", "longueuil", "sherbrooke",
    "saguenay", "levis", "trois-rivieres",
    # BC
    "vancouver", "victoria", "burnaby", "surrey", "richmond", "coquitlam",
    "kelowna", "abbotsford", "saanich", "delta", "kamloops",
    # Alberta
    "calgary", "edmonton", "red deer", "lethbridge", "st. albert",
    # Manitoba
    "winnipeg", "brandon",
    # Sask
    "saskatoon", "regina",
    # Atlantic
    "halifax", "moncton", "fredericton", "st. john's", "charlottetown", "saint john",
]:
    CITY_COUNTRY[city] = "CA"


async def cleanup(apply: bool) -> dict:
    cli = AsyncIOMotorClient(MONGO_URL)
    db = cli[DB_NAME]
    summary = {"started_at": datetime.now(timezone.utc).isoformat(), "apply": apply}

    # ── Mutation 1: bulk leads without BIN → founder BIN ─────────────
    q1 = {
        "$and": [
            {"$or": [{"business_id": {"$exists": False}}, {"business_id": None}, {"business_id": ""}]},
            {"$or": [
                {"campaign_id": None},
                {"campaign_id": {"$exists": False}},
                {"tenant_id": "global"},
            ]},
            {"website_url": {"$exists": True, "$ne": ""}},
        ]
    }
    m1_count = await db.campaign_leads.count_documents(q1)
    summary["mutation_1_bulk_lead_assign"] = {"matched": m1_count, "target_bin": FOUNDER_BIN}
    if apply and m1_count > 0:
        r = await db.campaign_leads.update_many(
            q1,
            {"$set": {
                "business_id": FOUNDER_BIN,
                "tenant_id": FOUNDER_BIN,
                "backfilled_by": "cleanup_d81b",
                "backfilled_at": datetime.now(timezone.utc).isoformat(),
            }},
        )
        summary["mutation_1_bulk_lead_assign"]["modified"] = r.modified_count

    # ── Mutation 2: infer missing country from city ──────────────────
    cur = db.campaign_leads.find(
        {"$or": [{"country": {"$exists": False}}, {"country": None}, {"country": ""}]},
        {"_id": 1, "city": 1, "country": 1},
    )
    to_fix_ca: list = []
    no_match: list = []
    async for doc in cur:
        city = (doc.get("city") or "").strip().lower()
        if not city:
            no_match.append(doc["_id"])
            continue
        inferred = CITY_COUNTRY.get(city)
        if inferred == "CA":
            to_fix_ca.append(doc["_id"])
        else:
            no_match.append(doc["_id"])

    summary["mutation_2_country_infer"] = {
        "inferred_ca_count": len(to_fix_ca),
        "left_untouched_count": len(no_match),
    }
    if apply and to_fix_ca:
        # Chunked update — bulk_write is overkill for a single $set.
        CHUNK = 500
        modified = 0
        for i in range(0, len(to_fix_ca), CHUNK):
            r = await db.campaign_leads.update_many(
                {"_id": {"$in": to_fix_ca[i : i + CHUNK]}},
                {"$set": {
                    "country": "CA",
                    "country_backfilled_by": "cleanup_d81b",
                    "country_backfilled_at": datetime.now(timezone.utc).isoformat(),
                }},
            )
            modified += r.modified_count
        summary["mutation_2_country_infer"]["modified"] = modified

    # Audit row so the founder can grep the operation later.
    if apply:
        await db.audit_trail.insert_one({
            "event": "cleanup_d81b.applied",
            "business_id": FOUNDER_BIN,
            "summary": summary,
            "at": datetime.now(timezone.utc).isoformat(),
        })

    summary["finished_at"] = datetime.now(timezone.utc).isoformat()
    cli.close()
    return summary


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true", help="Actually write. Otherwise dry-run.")
    args = p.parse_args()
    out = asyncio.run(cleanup(args.apply))
    import json
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
