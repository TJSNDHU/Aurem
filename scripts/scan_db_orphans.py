"""AUREM — DB Orphan Scan — iter 266 (post-Big-Split cleanup audit)."""
import asyncio
import os

from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

# Graph-verified (gs_d0a9db97780c). Replaced 4 unconfirmed originals:
# blast_attempts, lead_interactions, email_queue, customer_audit_log
# → not in codebase. Actual names below.
COLLECTIONS = [
    "campaign_leads", "campaigns", "outreach_history", "outreach_log",
    "ora_leads", "do_not_contact", "email_log", "sms_log", "call_logs",
    "audit_log", "scan_history", "activity_feed", "tenant_customers",
    "pending_code_fixes", "repair_history", "known_fixes", "pixel_patches",
    "sentinel_alerts", "notifications", "token_vault", "api_keys",
    "platform_users", "business_profiles", "invoices", "payments",
]

LEGACY_FIELDS = [
    "blast_status_v1", "blast_result_v1", "outreach_v1",
    "sent_email_v1", "sent_sms_v1", "sent_whatsapp_v1",
    "old_schema_version", "legacy_outreach_log",
]

LEGACY_SUFFIXES = ("_v1", "_deprecated", "_old", "_legacy")


async def scan():
    # FIX 1: MONGODB_URL not MONGO_URL (original had wrong key — KeyError on start)
    client = AsyncIOMotorClient(os.environ["MONGODB_URL"])
    db = client[os.environ["DB_NAME"]]

    try:
        print(f"\n=== ORPHAN FIELD SCAN — {len(COLLECTIONS)} collections, "
              f"{len(LEGACY_FIELDS)} legacy fields ===\n")

        total_docs, total_orphans, found_any = 0, 0, False

        for coll_name in COLLECTIONS:
            try:
                coll_count = await db[coll_name].count_documents({})
                if coll_count == 0:
                    print(f"  · {coll_name:<28} (empty)")
                    continue
                total_docs += coll_count
                for field in LEGACY_FIELDS:
                    n = await db[coll_name].count_documents({field: {"$exists": True}})
                    if n:
                        print(f"  ⚠ {coll_name}.{field}  — {n}/{coll_count} docs affected")
                        total_orphans += n
                        found_any = True
            except Exception as e:
                print(f"  ✗ {coll_name}: {e}")

        if not found_any:
            print("  ✅ No orphan legacy fields found — DB is clean.\n")
        else:
            print(f"\n  TOTAL: {total_orphans} orphan entries across {total_docs} docs.\n")

        print("=== BONUS: legacy suffix scan (20-doc sample per collection) ===\n")

        for coll_name in COLLECTIONS:
            try:
                # FIX 2: $sample(20) not find_one() — find_one misses sparse fields
                # on minority docs (e.g. field on 5% of docs = ~0% hit rate)
                samples = await db[coll_name].aggregate(
                    [{"$sample": {"size": 20}}]
                ).to_list(20)
                if not samples:
                    continue
                all_keys = {k for doc in samples for k in doc.keys()}
                legacy_keys = sorted(k for k in all_keys if k.endswith(LEGACY_SUFFIXES))
                if legacy_keys:
                    print(f"  · {coll_name}: {legacy_keys}")
            except Exception:
                pass

        print()

    finally:
        # FIX 3: always close — prevents ResourceWarning + event loop hang on exit
        client.close()


asyncio.run(scan())