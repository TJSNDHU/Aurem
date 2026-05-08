"""Backfill enrichment for leads with website but no email — iter 288.6.
Run:  python -m backend.tools.backfill_lead_enrichment   (or import as module)
"""
import asyncio, os, logging
from dotenv import load_dotenv
load_dotenv('/app/backend/.env')
from motor.motor_asyncio import AsyncIOMotorClient

logging.basicConfig(level=logging.INFO)


async def main(limit: int = 50):
    db = AsyncIOMotorClient(os.environ['MONGO_URL'])[os.environ['DB_NAME']]
    from services.apollo_enrichment import enrich_lead_with_apollo_diy

    cur = db.campaign_leads.find(
        {"website_url": {"$ne": "", "$exists": True},
         "$or": [{"email": ""}, {"email": {"$exists": False}}]},
        {"_id": 0, "lead_id": 1, "website_url": 1, "business_name": 1},
    ).limit(limit)
    todo = await cur.to_list(length=limit)
    print(f"Backfilling {len(todo)} leads")

    ok, fail = 0, 0
    for i, l in enumerate(todo, 1):
        try:
            r = await enrich_lead_with_apollo_diy(db, l["lead_id"], l["website_url"])
            email = r.get("email")
            if email:
                ok += 1
                print(f"  [{i}/{len(todo)}] ✅ {l['business_name'][:30]:30s} → {email}")
            else:
                fail += 1
                print(f"  [{i}/{len(todo)}] ⏳ {l['business_name'][:30]:30s} → no email")
        except Exception as e:
            fail += 1
            print(f"  [{i}/{len(todo)}] ❌ {l['business_name'][:30]:30s} → {e}")
    print(f"\nDone. {ok} enriched, {fail} skipped/failed.")


if __name__ == "__main__":
    asyncio.run(main())
