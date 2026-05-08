#!/usr/bin/env python3
"""
iter 305g — Backfill gold-particles canvas into every existing
rendered/published/deployed site in `db.auto_built_sites`.

Idempotent (sentinel-gated). Safe to re-run.

Run:   python3 /app/scripts/backfill_particles.py
       python3 /app/scripts/backfill_particles.py --dry-run
"""
import asyncio
import os
import sys

sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")

from motor.motor_asyncio import AsyncIOMotorClient

from services.awb_particles_injector import inject_particles, _SENTINEL  # noqa: E402

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


async def main(dry: bool) -> int:
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    q = {
        "status": {"$in": ["rendered", "published", "deployed"]},
        "rendered_html": {"$exists": True, "$ne": ""},
    }
    total = await db.auto_built_sites.count_documents(q)
    print(f"candidates: {total}")

    cur = db.auto_built_sites.find(q, {"_id": 0, "site_id": 1, "slug": 1, "rendered_html": 1})
    updated = skipped_already = unchanged = 0
    async for site in cur:
        sid = site.get("site_id")
        html = site.get("rendered_html") or ""
        if _SENTINEL in html:
            skipped_already += 1
            continue
        new_html = inject_particles(html)
        if new_html == html:
            unchanged += 1
            continue
        if not dry:
            await db.auto_built_sites.update_one(
                {"site_id": sid}, {"$set": {"rendered_html": new_html}}
            )
        updated += 1

    client.close()
    print(
        f"DONE · updated={updated} · already_injected={skipped_already} "
        f"· no_hero_container={unchanged} · dry={dry}"
    )
    return 0


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    sys.exit(asyncio.run(main(dry)))
