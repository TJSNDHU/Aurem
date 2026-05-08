#!/usr/bin/env python3
"""
FIX 4 — iter 305f
Delete archived / draft / failed duplicate site docs from
`db.auto_built_sites`, keeping only the latest active one per business.

"Active" = status in (rendered, published, deployed)
"Deletable" = status in (archived, draft, drafting, failed)

Dry-run by default. Pass `--yes` to actually delete.

Safety:
  - Never deletes if NO active sibling exists for the business (so we
    don't accidentally orphan a business with only a `drafting` row).
  - Groups by business_name_normalized + phone_normalized.
"""
import asyncio
import os
import sys

sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")

from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

ACTIVE = {"rendered", "published", "deployed"}
DELETABLE = {"archived", "draft", "drafting", "failed"}


async def main(auto: bool) -> int:
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    # Find business-key groups with >1 doc
    pipe = [
        {"$match": {"business_name_normalized": {"$exists": True, "$ne": ""}}},
        {"$group": {
            "_id": {
                "name": "$business_name_normalized",
                "phone": {"$ifNull": ["$phone_normalized", ""]},
            },
            "docs": {"$push": {
                "_id": "$_id", "slug": "$slug",
                "status": "$status", "site_id": "$site_id",
                "created_at": "$created_at",
            }},
            "n": {"$sum": 1},
        }},
        {"$match": {"n": {"$gt": 1}}},
    ]

    deletable_ids: list = []
    groups_touched = 0
    async for g in db.auto_built_sites.aggregate(pipe):
        docs = g["docs"]
        has_active = any(d.get("status") in ACTIVE for d in docs)
        if not has_active:
            continue  # don't orphan — skip this group
        for d in docs:
            if d.get("status") in DELETABLE:
                deletable_ids.append(d["_id"])
        groups_touched += 1

    print(f"Groups with duplicates + an active doc: {groups_touched}")
    print(f"Deletable (archived/draft/drafting/failed) docs: {len(deletable_ids)}")

    if not deletable_ids:
        client.close()
        return 0

    if not auto:
        # Show a preview
        async for d in db.auto_built_sites.find(
            {"_id": {"$in": deletable_ids}},
            {"_id": 0, "slug": 1, "status": 1, "business_name": 1},
        ).limit(30):
            print(f"  del  slug={str(d.get('slug') or '<none>'):50s} status={d.get('status')}")
        if len(deletable_ids) > 30:
            print(f"  ... +{len(deletable_ids) - 30} more")
        ans = input(f"\nDelete {len(deletable_ids)} docs? (yes/no): ").strip().lower()
        if ans != "yes":
            print("Aborted.")
            client.close()
            return 0

    res = await db.auto_built_sites.delete_many({"_id": {"$in": deletable_ids}})
    print(f"DONE · deleted={res.deleted_count}")
    client.close()
    return 0


if __name__ == "__main__":
    auto = "--yes" in sys.argv or "-y" in sys.argv
    sys.exit(asyncio.run(main(auto)))
