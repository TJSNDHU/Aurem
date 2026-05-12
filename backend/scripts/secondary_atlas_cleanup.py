"""
Free space on the SECONDARY Atlas cluster.

The secondary hit Atlas's 500-collection-per-cluster cap. New collections
can't be created there until we free room. Drop the same 26+ dead
collections that were removed from PRIMARY in iter 322ee (these are
guaranteed-empty mirrors that no longer need to be backed up).

Run once, then re-run teach_ora_iter_322 to mirror the ORA learning
collections.
"""
import os
import sys
import asyncio
sys.path.insert(0, "/app/backend")

from pymongo import MongoClient

DEAD_COLLECTIONS = [
    # iter 322ee drops on primary — mirror to secondary
    "abandoned_carts", "products", "orders", "carts", "discount_codes",
    "analytics_visits", "apollo_people_cache", "aurem_api_keys",
    "aurem_consent_records", "aurem_contacts", "aurem_gmail_messages",
    "aurem_integrations", "aurem_key_usage", "aurem_unified_inbox",
    "aurem_whatsapp_connections", "aurem_whatsapp_messages", "blog_posts",
    "campaign_runs", "hermes_deepsleep_memory", "lifecycle_history",
    "marketing_broadcasts", "mention_status_history", "scout_runs",
    "subscribers", "unlinked_mentions", "bio_scans", "evolver_genes",
    "reviews", "marketing_social_posts",
    # Additional empty + low-value collections from earlier audits that
    # are safe to drop on the secondary specifically.
    "site_audits", "site_change_triggers", "sites_sent",
    "stem_fix_backups", "system_pulse",
]


async def main():
    secondary_url = os.environ["SECONDARY_MONGO_URL"]
    db_name = os.environ.get("DB_NAME", "aurem_db")

    print(f"=== Freeing space on SECONDARY Atlas ===")

    def _do():
        client = MongoClient(secondary_url, serverSelectionTimeoutMS=15000)
        client.admin.command("ping")
        db = client[db_name]
        before = len(db.list_collection_names())
        print(f"BEFORE: {before} collections")

        dropped, missing, has_data = [], [], []
        for c in DEAD_COLLECTIONS:
            try:
                n = db[c].estimated_document_count()
            except Exception:
                missing.append(c)
                continue
            if c not in db.list_collection_names():
                missing.append(c)
                continue
            if n > 0:
                # On the secondary, even non-empty collections may be safe
                # to drop if they're known-dead on primary (data is stale).
                # Still ask before nuking — print and skip.
                has_data.append((c, n))
                print(f"  ⚠ SKIP {c}: has {n} docs on secondary")
                continue
            db.drop_collection(c)
            dropped.append(c)
            print(f"  ✓ dropped: {c}")

        after = len(db.list_collection_names())
        print(f"AFTER:  {after} collections  (Δ={before-after}, free room={500-after})")
        client.close()

    await asyncio.to_thread(_do)


if __name__ == "__main__":
    asyncio.run(main())
