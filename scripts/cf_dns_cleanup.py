#!/usr/bin/env python3
"""
FIX 3 — iter 305f
Cloudflare DNS cleanup for aurem.live.

Compares live CNAME records in the aurem.live zone against `slug`
values in `db.auto_built_sites` (published/deployed/rendered) and
offers to delete orphan CNAMEs — the records that once pointed to a
generated site but whose DB row is gone / archived.

SAFEGUARDS
  • Dry-run by default; requires `--yes` or interactive "yes" confirm.
  • PROTECTED set: core infra hostnames are NEVER deleted regardless.
  • Only touches CNAME records; A/AAAA/MX/TXT are left alone.

Env:
  CF_API_TOKEN   — Cloudflare API token with "Edit zone DNS" on aurem.live
  CF_ZONE_ID     — zone id (falls back to the known prod zone)
  MONGO_URL      — from /app/backend/.env (auto-loaded)
  DB_NAME        — from /app/backend/.env (auto-loaded)

Run:   export CF_API_TOKEN=...  &&  python3 /app/scripts/cf_dns_cleanup.py
Auto:  python3 /app/scripts/cf_dns_cleanup.py --yes
"""
import asyncio
import os
import sys

sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")

import httpx
from motor.motor_asyncio import AsyncIOMotorClient

CF_TOKEN = os.environ.get("CF_API_TOKEN", "").strip()
CF_ZONE = os.environ.get("CF_ZONE_ID", "").strip() or "a9e16b58047f9d60953377f37030b332"
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

# Hostnames to NEVER delete regardless of DB state.
PROTECTED = {
    "@", "aurem.live", "www", "n8n", "voice", "social", "sovereign",
    "img", "send", "api", "dashboard", "admin", "platform", "auth",
    "app", "mail", "email", "status", "docs", "blog", "go", "cdn",
    "static", "assets",
}

CF_BASE = "https://api.cloudflare.com/client/v4"


async def cf_list_cnames() -> list[dict]:
    recs: list[dict] = []
    async with httpx.AsyncClient(
        headers={"Authorization": f"Bearer {CF_TOKEN}"},
        timeout=30,
    ) as hc:
        page = 1
        while True:
            r = await hc.get(
                f"{CF_BASE}/zones/{CF_ZONE}/dns_records",
                params={"type": "CNAME", "per_page": 100, "page": page},
            )
            r.raise_for_status()
            d = r.json()
            recs.extend(d.get("result") or [])
            pages = (d.get("result_info") or {}).get("total_pages") or 1
            if page >= pages:
                break
            page += 1
    return recs


async def cf_delete(client: httpx.AsyncClient, record_id: str) -> bool:
    r = await client.delete(f"{CF_BASE}/zones/{CF_ZONE}/dns_records/{record_id}")
    return r.status_code == 200


async def db_live_slugs() -> set[str]:
    slugs: set[str] = set()
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    cur = db.auto_built_sites.find(
        {"status": {"$in": ["rendered", "published", "deployed"]}},
        {"_id": 0, "slug": 1},
    )
    async for row in cur:
        s = (row.get("slug") or "").strip().lower()
        if s:
            slugs.add(s)
    client.close()
    return slugs


async def main(auto: bool) -> int:
    if not CF_TOKEN:
        print("ERR: CF_API_TOKEN not set. Run:")
        print("     export CF_API_TOKEN=<your_token>")
        return 2

    print("· fetching Cloudflare CNAMEs ...")
    recs = await cf_list_cnames()
    print(f"  {len(recs)} CNAME records in zone")

    print("· fetching live slugs from db.auto_built_sites ...")
    slugs = await db_live_slugs()
    print(f"  {len(slugs)} live slugs in DB")

    orphans: list[dict] = []
    for rec in recs:
        full = (rec.get("name") or "").lower()
        host = full.removesuffix(".aurem.live")
        if host in PROTECTED or host == full:
            continue
        if host in slugs:
            continue
        orphans.append(rec)

    print(f"\n· orphan CNAMEs: {len(orphans)}")
    if not orphans:
        print("NOTHING TO CLEAN — all CNAMEs match live slugs.")
        return 0

    # Always print preview
    for rec in orphans[:80]:
        print(f"    {rec['name']}")
    if len(orphans) > 80:
        print(f"    ... +{len(orphans) - 80} more")

    if not auto:
        ans = input(f"\nDelete {len(orphans)} orphan CNAMEs? (yes/no): ").strip().lower()
        if ans != "yes":
            print("Aborted.")
            return 0

    deleted = failed = 0
    async with httpx.AsyncClient(
        headers={"Authorization": f"Bearer {CF_TOKEN}"},
        timeout=30,
    ) as hc:
        for rec in orphans:
            ok = await cf_delete(hc, rec["id"])
            if ok:
                deleted += 1
            else:
                failed += 1

    print(f"\nDONE · deleted={deleted} · failed={failed}")
    remaining = len(recs) - deleted
    print(f"Cloudflare zone now has ~{remaining} CNAMEs.")
    return 0


if __name__ == "__main__":
    auto = "--yes" in sys.argv or "-y" in sys.argv
    sys.exit(asyncio.run(main(auto)))
