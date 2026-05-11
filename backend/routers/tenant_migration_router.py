"""
AUREM Tenant Backfill — Migration endpoint to stamp existing documents
with tenant_id so the ScopedDB proxy can filter them.
"""

import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["Tenant Migration"])

_db = None

def set_db(database):
    global _db
    _db = database


# Collections to backfill (everything that's NOT global)
BACKFILL_COLLECTIONS = [
    "leads", "acquisition_leads", "acquisition_campaigns", "acquisition_config",
    "voice_calls", "voice_interactions",
    "crm_contacts", "crm_connections", "crm_deals",
    "chat_sessions", "chat_messages",
    "system_scans", "auto_repair_log", "auto_heal_log", "auto_heal_runs",
    "automations",
    "webhooks", "api_request_logs",
    "api_keys", "api_keys_registry",
    "managed_clients",
    "crash_log",
    "secret_vault", "vault_audit_log",
    "panic_events",
    "gmail_tokens",
    "whatsapp_messages",
    "referral_profiles",
    "custom_subscriptions",
]


@router.post("/tenant-backfill")
async def backfill_tenant_ids(admin_key: str = ""):
    """
    One-time migration: stamps tenant_id on all existing documents
    that lack it. Uses the first admin user's ID as the tenant.
    """
    import os
    expected_key = os.environ.get("ADMIN_KEY", "")
    if not admin_key or admin_key != expected_key:
        raise HTTPException(403, "Invalid admin key")

    if _db is None:
        raise HTTPException(500, "Database not available")

    # Find the admin user to use as default tenant
    admin = await _db.users.find_one({"is_admin": True}, {"_id": 0, "id": 1})
    if not admin:
        raise HTTPException(404, "No admin user found")

    tenant_id = admin["id"]
    results = {}
    total_updated = 0

    for coll_name in BACKFILL_COLLECTIONS:
        try:
            coll = _db[coll_name]
            # Only update docs that don't have tenant_id
            result = await coll.update_many(
                {"tenant_id": {"$exists": False}},
                {"$set": {"tenant_id": tenant_id}},
            )
            count = result.modified_count
            results[coll_name] = count
            total_updated += count
        except Exception as e:
            results[coll_name] = f"error: {str(e)}"

    # Create migration log
    await _db.migration_log.insert_one({
        "migration": "tenant_backfill",
        "tenant_id": tenant_id,
        "results": results,
        "total_updated": total_updated,
        "ts": datetime.now(timezone.utc).isoformat(),
    })

    return {
        "success": True,
        "tenant_id": tenant_id,
        "total_documents_tagged": total_updated,
        "per_collection": results,
    }


@router.get("/tenant-status")
async def tenant_scoping_status():
    """Check how many documents have/lack tenant_id across collections."""
    if _db is None:
        raise HTTPException(500, "Database not available")

    status = {}
    for coll_name in BACKFILL_COLLECTIONS:
        try:
            coll = _db[coll_name]
            total = await coll.count_documents({})
            scoped = await coll.count_documents({"tenant_id": {"$exists": True}})
            status[coll_name] = {
                "total": total,
                "scoped": scoped,
                "unscoped": total - scoped,
                "coverage": f"{(scoped / total * 100):.0f}%" if total > 0 else "N/A",
            }
        except Exception:
            status[coll_name] = {"total": 0, "scoped": 0, "unscoped": 0, "coverage": "N/A"}

    return {"collections": status}
