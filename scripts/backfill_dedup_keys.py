#!/usr/bin/env python3
"""
FIX 1 — iter 305f
Backfill dedup keys on `db.auto_built_sites` so find_existing_site()
actually has something to match against.

Fields populated (only if missing):
  - phone_normalized          ← normalized from lead.phone / business_phone
  - website_domain            ← normalized from lead.website(_url)
  - business_name_normalized  ← a-z0-9 slug of business_name
  - city                      ← lowercased trimmed lead.city

Run:  python3 /app/scripts/backfill_dedup_keys.py
Safe to re-run; skips docs that already have all 4 fields.
"""
import asyncio
import os
import re
import sys

sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")

from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


def norm_phone(raw: str) -> str | None:
    if not raw:
        return None
    digits = re.sub(r"\D", "", str(raw))
    if len(digits) == 10:
        digits = "1" + digits
    return digits if 10 <= len(digits) <= 15 else None


def norm_name(name: str) -> str | None:
    if not name:
        return None
    out = re.sub(r"[^a-z0-9]", "", name.lower().strip())
    return out or None


def extract_domain(url: str) -> str | None:
    if not url:
        return None
    u = re.sub(r"^https?://", "", str(url).lower().strip())
    u = u.split("/")[0]
    u = u.removeprefix("www.")
    return u or None


async def backfill():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    q = {
        "$or": [
            {"phone_normalized": {"$in": [None, ""]}},
            {"phone_normalized": {"$exists": False}},
            {"website_domain": {"$in": [None, ""]}},
            {"website_domain": {"$exists": False}},
            {"business_name_normalized": {"$in": [None, ""]}},
            {"business_name_normalized": {"$exists": False}},
            {"city": {"$exists": False}},
        ]
    }

    total_sites = await db.auto_built_sites.count_documents({})
    candidates = await db.auto_built_sites.count_documents(q)
    print(f"auto_built_sites total={total_sites} candidates={candidates}")

    updated = 0
    skipped = 0
    leads_missing = 0

    cursor = db.auto_built_sites.find(q, {
        "_id": 1, "lead_id": 1, "business_name": 1,
        "phone_normalized": 1, "website_domain": 1,
        "business_name_normalized": 1, "city": 1,
    })

    async for site in cursor:
        patch = {}
        # Name is on the site doc itself; fall back to lead if needed.
        biz_name = site.get("business_name")
        phone = None
        website = None
        city = None

        # Pull from the source lead doc (has phone + website + city)
        lead_id = site.get("lead_id")
        lead = None
        if lead_id:
            lead = await db.campaign_leads.find_one(
                {"lead_id": lead_id},
                {"_id": 0, "phone": 1, "business_phone": 1,
                 "website": 1, "website_url": 1, "city": 1,
                 "business_name": 1},
            )
        if lead:
            phone = lead.get("phone") or lead.get("business_phone") or ""
            website = lead.get("website") or lead.get("website_url") or ""
            city = (lead.get("city") or "").strip()
            biz_name = biz_name or lead.get("business_name")
        else:
            leads_missing += 1

        # Build patch only for fields that are empty on the site.
        pn = norm_phone(phone)
        if pn and not site.get("phone_normalized"):
            patch["phone_normalized"] = pn

        dom = extract_domain(website)
        if dom and not site.get("website_domain"):
            patch["website_domain"] = dom

        nn = norm_name(biz_name or "")
        if nn and not site.get("business_name_normalized"):
            patch["business_name_normalized"] = nn

        if city and not site.get("city"):
            patch["city"] = city.lower()

        if patch:
            await db.auto_built_sites.update_one(
                {"_id": site["_id"]}, {"$set": patch}
            )
            updated += 1
        else:
            skipped += 1

    client.close()
    print(
        f"DONE · updated={updated} · skipped={skipped} · leads_missing={leads_missing}"
    )


if __name__ == "__main__":
    asyncio.run(backfill())
