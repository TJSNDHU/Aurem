#!/usr/bin/env python3
"""
Apply AUREM Mission Control performance indexes to PROD Atlas.

Run on a machine that has access to your prod Atlas cluster (your local).
Idempotent — re-running is safe; MongoDB no-ops on existing index specs.

USAGE:
    export MONGO_URL="mongodb+srv://<...>"      # PROD connection string
    export DB_NAME="aurem_db"                   # PROD db name
    pip install motor python-dotenv             # if not already
    python3 apply_perf_indexes_PROD.py
"""
import asyncio
import os
import sys
from motor.motor_asyncio import AsyncIOMotorClient


# Same map that backend startup uses — see infra_settings_router._ensure_indexes
COMPOUND = {
    "pixel_verification_log": [("verified_at", -1), ("detected", 1), ("url", 1)],
    "aurem_onboarding": [("tenant_id", 1), ("pixel_installed", 1)],
}
SECONDARY = {
    "pixel_verification_log": [[("detected", 1)]],
    "aurem_onboarding": [[("pixel_installed", 1)]],
    "tenant_customers": [
        [("record_type", 1), ("pixel_installed", 1)],
        [("record_type", 1), ("status", 1)],
    ],
}


async def main() -> None:
    mongo_url = os.environ.get("MONGO_URL", "").strip()
    db_name = os.environ.get("DB_NAME", "").strip()
    if not mongo_url or not db_name:
        sys.exit("ERROR: set MONGO_URL and DB_NAME first")

    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    created = 0
    for coll, spec in COMPOUND.items():
        await db[coll].create_index(spec, background=True)
        print(f"  ✅ {coll}.{spec}")
        created += 1
    for coll, specs in SECONDARY.items():
        for s in specs:
            await db[coll].create_index(s, background=True)
            print(f"  ✅ {coll}.{s}")
            created += 1

    print(f"\n✅ Done — {created} indexes ensured on prod.")
    print("Mission Control queries (`/admin/mission-control/pixel-health`,")
    print("`/tenants-summary`) should now be 2-3x faster on cold-cache hits.")


if __name__ == "__main__":
    asyncio.run(main())
