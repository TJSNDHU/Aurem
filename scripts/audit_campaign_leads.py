"""Deep schema health check on campaign_leads — iter 265."""
import asyncio
import os
from collections import Counter

from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402


async def audit():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]

    count = await db.campaign_leads.count_documents({})
    print(f"\ncampaign_leads total: {count}")
    if count == 0:
        print("(empty collection)\n")
        return

    # Tally every field that appears across the sample
    sample = await db.campaign_leads.find({}, limit=500).to_list(500)
    field_counter = Counter()
    for doc in sample:
        for k in doc.keys():
            field_counter[k] += 1

    print(f"\nField frequency across {len(sample)} sampled docs:")
    for field, freq in sorted(field_counter.items(), key=lambda x: -x[1]):
        pct = round(100 * freq / len(sample), 1)
        flag = " ⚠ RARE" if pct < 10 else ("" if pct >= 50 else " (partial)")
        print(f"  {field:<30}  {freq}/{len(sample)}  ({pct}%){flag}")

    # Lifecycle stage distribution
    print("\nLifecycle stage distribution:")
    pipeline = [{"$group": {"_id": "$lifecycle_stage", "n": {"$sum": 1}}}]
    async for row in db.campaign_leads.aggregate(pipeline):
        print(f"  {row['_id']}: {row['n']}")

    # Indexes
    print("\nIndexes:")
    for k, v in (await db.campaign_leads.index_information()).items():
        print(f"  {k}: {v.get('key', [])}")

    print()


asyncio.run(audit())
