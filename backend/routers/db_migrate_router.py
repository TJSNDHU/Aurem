"""
db_migrate_router.py — One-shot ops endpoints for production data migrations.
═══════════════════════════════════════════════════════════════════════════
Founder-only. Idempotent. Use sparingly — these mutate production data.

Endpoints:
  POST /api/admin/db-migrate/iter322-cleanup
       Replays the iter-322 cleanup against the connected DB:
         1. Hard-delete known test/E2E account patterns
         2. Merge admin@aurem.live → teji.ss1986+dogfood@gmail.com
         3. Hard-delete pawandeep19may1985@gmail.com
       Returns a JSON summary of every collection touched.

  GET /api/admin/db-migrate/iter322-cleanup/preview
       Dry-run — same logic but no writes. Returns counts only.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Tuple

from fastapi import APIRouter, HTTPException, Request

logger = logging.getLogger(__name__)
router = APIRouter()

_db = None


def set_db(db) -> None:
    global _db
    _db = db


# ─── Configuration ──────────────────────────────────────────────────────────
KEEP_EMAILS = {
    "teji.ss1986@gmail.com",
    "teji.ss1986+dogfood@gmail.com",
    "admin@reroots.ca",
}

SRC_EMAIL = "admin@aurem.live"
DST_EMAIL = "teji.ss1986+dogfood@gmail.com"
EXTRA_DELETE = ["pawandeep19may1985@gmail.com"]

# iter 322 — final BIN renames. cleanup endpoint cascade-replaces these
# everywhere (auth collections + every BIN-scoped collection in the DB).
BIN_RENAMES = {
    "AURE-FNDR-001": "AURE-ADMIN",   # founder admin
    "AURE-FNDR-002": "AURE-SUPER",   # dogfood
    "AURE-3M4G":     "AURE-SUPER",   # legacy dogfood (pre-merge) → consolidate
}

EMAIL_FIELDS = [
    "email", "owner_email", "user_email", "to", "recipient", "contact_email",
    "customer_email", "sender_email", "from", "from_email", "client_email",
    "lead_email", "applicant_email", "subscriber_email",
]
ID_FIELDS = ["user_id", "owner_id", "tenant_id", "business_id", "customer_id", "plat_user_id"]
BIN_FIELDS = ["business_id", "tenant_id", "tenant_bin", "owner_business_id", "bin"]


def _is_test_email(email: str) -> bool:
    """Patterns we recognize as auto-generated E2E test accounts."""
    if not email:
        return False
    e = email.lower()
    if e in {x.lower() for x in KEEP_EMAILS}:
        return False
    return (
        e.endswith("@aurem-test.com") or e.endswith("@aurem.test")
        or e.startswith("funnel-") or e.startswith("e2e-")
        or e.startswith("iter") or e.startswith("tester-")
        or e.startswith("p0-") or e.startswith("diag-")
        or e.startswith("hidden-") or e.startswith("ora-ctx-")
        or e.startswith("deploy-smoke") or e.startswith("stripe-checkout-")
        or e.startswith("stripe-final-") or e.startswith("customer-luxe-test")
    )


async def _require_founder(request: Request) -> None:
    """Founder-only auth gate. Reuse the platform's admin auth helper.
    Falls back to JWT inspection if helper not present."""
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "auth required")
    token = auth.split(" ", 1)[1]
    try:
        import jwt
        secret = os.environ.get("JWT_SECRET", "")
        if not secret:
            raise HTTPException(500, "JWT_SECRET not configured")
        payload = jwt.decode(token, secret, algorithms=["HS256"])
    except Exception as e:
        raise HTTPException(401, f"invalid token: {e}")
    email = (payload.get("email") or "").lower()
    is_admin = bool(payload.get("is_admin") or payload.get("is_super_admin"))
    if not is_admin or email not in {x.lower() for x in KEEP_EMAILS}:
        raise HTTPException(403, "founder-only")


async def _gather_test_emails(db) -> List[str]:
    """Scan auth collections for emails matching the test patterns."""
    found: set = set()
    for coll in ("users", "platform_users", "aurem_users"):
        async for d in db[coll].find({}, {"_id": 0, "email": 1}):
            e = (d.get("email") or "").lower()
            if e and _is_test_email(e):
                found.add(e)
    return sorted(found)


async def _gather_cascade_keys(db, emails: List[str]) -> Tuple[set, set]:
    """Collect user_ids + business_ids tied to the given emails."""
    user_ids: set = set()
    biz_ids: set = set()
    if not emails:
        return user_ids, biz_ids
    for coll in ("users", "platform_users", "aurem_users"):
        async for d in db[coll].find(
            {"email": {"$in": emails}},
            {"_id": 0, "id": 1, "user_id": 1, "business_id": 1, "tenant_id": 1},
        ):
            for k in ("id", "user_id", "business_id", "tenant_id"):
                v = d.get(k)
                # Skip generic placeholders that are SHARED globally
                if v and isinstance(v, str) and v not in ("system", "global", "default", ""):
                    user_ids.add(v)
            if d.get("business_id"):
                biz_ids.add(d["business_id"])
    return user_ids, biz_ids


async def _purge_emails(db, emails: List[str], user_ids: set, dry: bool) -> Dict[str, int]:
    """Delete every doc referencing any of these emails / cascade ids.
    Returns {collection: count}."""
    if not emails:
        return {}
    log: Dict[str, int] = {}
    all_colls = await db.list_collection_names()
    id_list = list(user_ids)
    for c in all_colls:
        ors = [{f: {"$in": emails}} for f in EMAIL_FIELDS]
        if id_list:
            ors.extend([{f: {"$in": id_list}} for f in ID_FIELDS])
        try:
            if dry:
                n = await db[c].count_documents({"$or": ors})
            else:
                n = (await db[c].delete_many({"$or": ors})).deleted_count
            if n > 0:
                log[c] = n
        except Exception:
            try:
                if dry:
                    n = await db[c].count_documents({"email": {"$in": emails}})
                else:
                    n = (await db[c].delete_many({"email": {"$in": emails}})).deleted_count
                if n > 0:
                    log[c] = n
            except Exception:
                pass
    return log


async def _merge_admin_to_dogfood(db, dry: bool) -> Dict[str, Any]:
    """Reassign admin@aurem.live → teji.ss1986+dogfood@gmail.com identity.
    Source row is then deleted from auth collections."""
    src_plat = await db.platform_users.find_one({"email": SRC_EMAIL}, {"_id": 0})
    src_users = await db.users.find_one({"email": SRC_EMAIL}, {"_id": 0})
    src_aurem = await db.aurem_users.find_one({"email": SRC_EMAIL}, {"_id": 0})
    if not src_plat:
        return {"merged": False, "reason": f"{SRC_EMAIL} not in platform_users"}

    dst_plat = await db.platform_users.find_one({"email": DST_EMAIL}, {"_id": 0})
    cascade_changes: Dict[str, int] = {}
    src_user_id = src_plat.get("user_id")
    src_biz_id = src_plat.get("business_id")

    if not dry:
        # Inherit full source identity into target row in platform_users
        merged = dict(src_plat)
        merged["email"] = DST_EMAIL
        if dst_plat:
            for k in (
                "pin_hash", "pin_set_at", "onboarding_wizard_step",
                "onboarding_wizard_complete", "smart_onboarding_complete",
                "wizard", "wizard_complete", "terms_accepted",
                "terms_accepted_at", "terms_version", "is_active", "plan", "role",
            ):
                if dst_plat.get(k) is not None and not merged.get(k):
                    merged[k] = dst_plat[k]
        await db.platform_users.delete_one({"email": DST_EMAIL})
        await db.platform_users.update_one(
            {"email": DST_EMAIL}, {"$set": merged}, upsert=True
        )
        if src_users:
            mu = dict(src_users)
            mu["email"] = DST_EMAIL
            await db.users.delete_one({"email": DST_EMAIL})
            await db.users.update_one({"email": DST_EMAIL}, {"$set": mu}, upsert=True)
        if src_aurem:
            ma = dict(src_aurem)
            ma["email"] = DST_EMAIL
            await db.aurem_users.delete_one({"email": DST_EMAIL})
            await db.aurem_users.update_one({"email": DST_EMAIL}, {"$set": ma}, upsert=True)

        # Cascade reassign every email field across all collections
        all_colls = await db.list_collection_names()
        for c in all_colls:
            if c in ("users", "platform_users", "aurem_users"):
                continue
            for f in EMAIL_FIELDS:
                try:
                    res = await db[c].update_many(
                        {f: SRC_EMAIL}, {"$set": {f: DST_EMAIL}}
                    )
                    if res.modified_count > 0:
                        cascade_changes[f"{c}.{f}"] = res.modified_count
                except Exception:
                    pass

        # Drop source rows from auth collections
        await db.users.delete_many({"email": SRC_EMAIL})
        await db.platform_users.delete_many({"email": SRC_EMAIL})
        await db.aurem_users.delete_many({"email": SRC_EMAIL})

    return {
        "merged": True,
        "source": SRC_EMAIL,
        "target": DST_EMAIL,
        "preserved_user_id": src_user_id,
        "preserved_business_id": src_biz_id,
        "cascade_reassigned": cascade_changes,
    }


# ─── Routes ─────────────────────────────────────────────────────────────────
@router.get("/api/admin/db-migrate/iter322-cleanup/preview")
async def preview_cleanup(request: Request):
    await _require_founder(request)
    if _db is None:
        raise HTTPException(503, "db not ready")
    test_emails = await _gather_test_emails(_db)
    user_ids, biz_ids = await _gather_cascade_keys(_db, test_emails)
    purge_log = await _purge_emails(_db, test_emails, user_ids, dry=True)

    extra_log: Dict[str, int] = {}
    for em in EXTRA_DELETE:
        sub_ids, _ = await _gather_cascade_keys(_db, [em])
        sub = await _purge_emails(_db, [em], sub_ids, dry=True)
        for k, v in sub.items():
            extra_log[k] = extra_log.get(k, 0) + v

    src_present = await _db.platform_users.count_documents({"email": SRC_EMAIL})
    return {
        "ok": True, "dry_run": True,
        "test_emails": test_emails,
        "purge_estimate": purge_log,
        "purge_total": sum(purge_log.values()),
        "extra_delete_estimate": extra_log,
        "merge_pending": bool(src_present),
    }


@router.post("/api/admin/db-migrate/iter322-cleanup")
async def run_cleanup(request: Request):
    await _require_founder(request)
    if _db is None:
        raise HTTPException(503, "db not ready")

    test_emails = await _gather_test_emails(_db)
    user_ids, biz_ids = await _gather_cascade_keys(_db, test_emails)
    purge_log = await _purge_emails(_db, test_emails, user_ids, dry=False)
    test_total = sum(purge_log.values())

    merge_summary = await _merge_admin_to_dogfood(_db, dry=False)

    extra_log: Dict[str, int] = {}
    for em in EXTRA_DELETE:
        sub_ids, _ = await _gather_cascade_keys(_db, [em])
        sub = await _purge_emails(_db, [em], sub_ids, dry=False)
        for k, v in sub.items():
            extra_log[k] = extra_log.get(k, 0) + v

    # Verify zero traces
    leaks: Dict[str, int] = {}
    all_colls = await _db.list_collection_names()
    leak_emails = test_emails + [SRC_EMAIL] + EXTRA_DELETE
    for c in all_colls:
        try:
            n = await _db[c].count_documents({
                "$or": [{f: {"$in": leak_emails}} for f in EMAIL_FIELDS]
            })
            if n > 0:
                leaks[c] = n
        except Exception:
            pass

    final_counts = {
        "users": await _db.users.count_documents({}),
        "platform_users": await _db.platform_users.count_documents({}),
        "aurem_users": await _db.aurem_users.count_documents({}),
    }
    remaining_emails: set = set()
    for coll in ("users", "platform_users", "aurem_users"):
        async for d in _db[coll].find({}, {"_id": 0, "email": 1}):
            if d.get("email"):
                remaining_emails.add(d["email"])

    logger.info(
        f"[db-migrate] iter322-cleanup ran: tests={test_total} extra={sum(extra_log.values())} "
        f"merge={merge_summary.get('merged')} leaks={len(leaks)}"
    )

    # iter 322 — BIN rename cascade. Replaces every reference to the old
    # FNDR-style BINs and the legacy AURE-3M4G dogfood BIN with the final
    # AURE-ADMIN / AURE-SUPER identifiers across all collections + fields.
    rename_summary = await _cascade_rename_bins(_db)

    return {
        "ok": True,
        "test_purge": {"emails": test_emails, "by_collection": purge_log, "total": test_total},
        "merge": merge_summary,
        "extra_delete": {"emails": EXTRA_DELETE, "by_collection": extra_log, "total": sum(extra_log.values())},
        "bin_rename": rename_summary,
        "leaks_after": leaks,
        "final": {
            "auth_counts": final_counts,
            "remaining_emails": sorted(remaining_emails),
        },
    }


async def _cascade_rename_bins(db) -> Dict[str, Any]:
    """Replace every occurrence of an old BIN id across every collection
    and every BIN-bearing field. Idempotent — safe to re-run."""
    summary: Dict[str, int] = {}
    if db is None:
        return {"renamed": 0}
    all_colls = await db.list_collection_names()
    for old_bin, new_bin in BIN_RENAMES.items():
        if old_bin == new_bin:
            continue
        for c in all_colls:
            for f in BIN_FIELDS:
                try:
                    res = await db[c].update_many(
                        {f: old_bin}, {"$set": {f: new_bin}}
                    )
                    if res.modified_count > 0:
                        key = f"{c}.{f}: {old_bin}->{new_bin}"
                        summary[key] = res.modified_count
                except Exception:
                    pass
    return {"renamed_total": sum(summary.values()), "by_path": summary}


# iter 322 — Phase E support endpoint: backfill business_id everywhere it
# is missing (BIN-scoped collections only). Idempotent and safe to re-run.
@router.post("/api/admin/db-migrate/backfill-business-id")
async def backfill_bin_endpoint(request: Request):
    await _require_founder(request)
    if _db is None:
        raise HTTPException(503, "db not ready")
    from services.backfill_business_id import backfill_business_id
    return await backfill_business_id(_db)


@router.post("/api/admin/db-migrate/ensure-indexes")
async def ensure_indexes_endpoint(request: Request):
    await _require_founder(request)
    if _db is None:
        raise HTTPException(503, "db not ready")
    from services.db_indexes import ensure_bin_indexes
    return await ensure_bin_indexes(_db)
