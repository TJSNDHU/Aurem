"""
services/data_retention.py — iter 328b (PIPEDA compliance)

Canadian PIPEDA retention rules in code:

  • Leads older than 2 years (730 days) → moved from `leads`
    to `leads_archive` collection (status="archived_2y").
  • Customers with `deletion_requested_at` older than 30 days
    → personal fields hard-purged in place (status="purged",
    name/email/phone/address fields wiped, audit row written).
  • Every deletion / archive writes an audit row to
    `pipeda_audit_log` so compliance officer can reconstruct.

Public API
──────────
  run_retention_sweep(db) → dict (idempotent, safe to run daily)
  request_customer_deletion(db, customer_id, reason) → marks
    the customer with `deletion_requested_at`; the sweep does
    the actual purge after the 30-day cool-off so the user can
    cancel a mistaken request.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

LEADS_RETENTION_DAYS = 730        # 2 years
DELETION_COOL_OFF_DAYS = 30       # PIPEDA "reasonable period"
AUDIT_COLLECTION = "pipeda_audit_log"


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def archive_old_leads(db) -> dict:
    """Move leads older than 2y from `leads` → `leads_archive`."""
    if db is None:
        return {"ok": False, "error": "db not ready"}
    cutoff = _now() - timedelta(days=LEADS_RETENTION_DAYS)
    archived = 0
    failed = 0
    cur = db.leads.find(
        {"created_at": {"$lt": cutoff}, "status": {"$ne": "archived_2y"}},
        {"_id": 1, "email": 1, "created_at": 1},
    ).limit(500)
    async for lead in cur:
        try:
            full = await db.leads.find_one({"_id": lead["_id"]})
            if not full:
                continue
            full["archived_at"] = _now()
            full["status"] = "archived_2y"
            await db.leads_archive.update_one(
                {"_id": full["_id"]}, {"$set": full}, upsert=True,
            )
            await db.leads.delete_one({"_id": full["_id"]})
            await db[AUDIT_COLLECTION].insert_one({
                "action":    "archive_lead",
                "lead_id":   str(full["_id"]),
                "reason":    "PIPEDA 2-year retention reached",
                "ts":        _now(),
            })
            archived += 1
        except Exception as e:
            failed += 1
            logger.warning(f"[pipeda] archive failed for {lead.get('_id')}: {e}")
    return {"ok": True, "archived": archived, "failed": failed}


async def purge_due_deletions(db) -> dict:
    """Hard-purge customer PII for accounts past the 30-day cool-off."""
    if db is None:
        return {"ok": False, "error": "db not ready"}
    cutoff = _now() - timedelta(days=DELETION_COOL_OFF_DAYS)
    purged = 0
    failed = 0
    cur = db.users.find(
        {
            "deletion_requested_at": {"$lt": cutoff},
            "deletion_status":       {"$ne": "purged"},
        },
        {"_id": 1, "email": 1, "deletion_requested_at": 1},
    ).limit(500)
    async for u in cur:
        try:
            await db.users.update_one(
                {"_id": u["_id"]},
                {"$set": {
                    "email":          f"purged-{u['_id']}@deleted.local",
                    "name":           "[deleted]",
                    "phone":          None,
                    "address":        None,
                    "deletion_status": "purged",
                    "purged_at":      _now(),
                },
                 "$unset": {
                    "password_hash": "",
                    "billing_details": "",
                    "stripe_customer_id": "",
                }},
            )
            await db[AUDIT_COLLECTION].insert_one({
                "action":     "purge_user",
                "user_id":    str(u["_id"]),
                "original_email_hash": _hash_email(u.get("email")),
                "reason":     "PIPEDA deletion request (30-day cool-off passed)",
                "ts":         _now(),
            })
            purged += 1
        except Exception as e:
            failed += 1
            logger.warning(f"[pipeda] purge failed for {u.get('_id')}: {e}")
    return {"ok": True, "purged": purged, "failed": failed}


async def request_customer_deletion(db, customer_id: str, reason: str = "") -> dict:
    """Stamp `deletion_requested_at` — the actual purge runs in 30 days."""
    if db is None:
        return {"ok": False, "error": "db not ready"}
    if not customer_id:
        return {"ok": False, "error": "customer_id required"}
    res = await db.users.update_one(
        {"_id": customer_id},
        {"$set": {
            "deletion_requested_at": _now(),
            "deletion_reason":       (reason or "")[:500],
            "deletion_status":       "pending",
        }},
    )
    if res.matched_count == 0:
        return {"ok": False, "error": "customer not found"}
    await db[AUDIT_COLLECTION].insert_one({
        "action":     "request_deletion",
        "user_id":    str(customer_id),
        "reason":     (reason or "")[:500],
        "purge_at":   _now() + timedelta(days=DELETION_COOL_OFF_DAYS),
        "ts":         _now(),
    })
    return {
        "ok":             True,
        "purge_at":       (_now() + timedelta(days=DELETION_COOL_OFF_DAYS)).isoformat(),
        "cool_off_days":  DELETION_COOL_OFF_DAYS,
    }


async def run_retention_sweep(db) -> dict:
    """Run BOTH retention jobs. Designed for the daily APScheduler cron."""
    a = await archive_old_leads(db)
    p = await purge_due_deletions(db)
    logger.info(
        f"[pipeda] daily sweep — leads_archived={a.get('archived')} "
        f"users_purged={p.get('purged')}"
    )
    return {"ok": True, "archive": a, "purge": p}


def _hash_email(email: str | None) -> str | None:
    if not email:
        return None
    import hashlib
    return hashlib.sha256(email.lower().encode("utf-8")).hexdigest()[:16]
