"""
routers/autonomous_repair_admin_router.py — iter D-73.

Admin surface for the autonomous repair queue (`pending_approvals` +
`ora_cto_proposals`). Built after the D-71p audit + D-72 discovery
showed 442 rows piled up across 2 months because:

  * 428 rows were written by an OLDER schema (no `type`, no `tier`)
    so `services.ora_cto_repair_agent.run_repair_tick` quietly skipped
    them all → they aged out to >7 days with no action.

  * 14 newer Shannon security findings reached `awaiting_founder` but
    most target test-only domains (`*-test.com`, `test-target.com`)
    that nobody will ever approve fixes on, so they sit forever.

Endpoints (all admin-only, real Mongo writes, audit trail):

  GET  /api/admin/autonomous-repair/stats
       Breakdown by status / type / target / age. No mocks.

  POST /api/admin/autonomous-repair/archive-legacy
       Move rows with missing `type` (= pre-iter-325f schema) into
       `pending_approvals_archive`. Idempotent.

  POST /api/admin/autonomous-repair/archive-test-targets
       Reject + archive Shannon scans whose target host matches
       known-test domains (configurable env var). Idempotent.

  POST /api/admin/autonomous-repair/reject/{approval_id}
       Manually reject one row. Writes an audit row to
       `pending_approvals_archive`.

  POST /api/admin/autonomous-repair/ensure-ttl
       Best-effort creates a 60-day TTL index on
       `pending_approvals.created_at` and `pending_approvals_archive.
       archived_at`. Safety net so this never accumulates again.

Every mutation appends a row to `autonomous_repair_audit` describing
who did it, when, and what changed. No silent state changes.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Any, Optional
from urllib.parse import urlparse

import jwt
from fastapi import APIRouter, HTTPException, Header

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/autonomous-repair", tags=["Autonomous Repair Admin"])

_db = None


def set_db(database) -> None:
    global _db
    _db = database


# Default list of test-only domains whose Shannon scan findings should be
# rejected automatically. Customer can override via env var.
_DEFAULT_TEST_HOSTS = (
    "score-calc-test.com",
    "test-target.com",
    "example.com",
    "example.org",
    "example.net",
)


def _test_hosts() -> tuple[str, ...]:
    """Read AUREM_AUTO_REPAIR_TEST_HOSTS env var (comma-separated)
    falling back to the default. Always lowercased."""
    raw = (os.environ.get("AUREM_AUTO_REPAIR_TEST_HOSTS") or "").strip()
    if not raw:
        return _DEFAULT_TEST_HOSTS
    return tuple(h.strip().lower() for h in raw.split(",") if h.strip())


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


async def _require_admin(authorization: Optional[str]) -> str:
    """Reject non-admin callers. Returns the admin's email for audit."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Bearer token required")
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        raise HTTPException(status_code=503, detail="JWT_SECRET not configured")
    try:
        payload = jwt.decode(authorization[7:], secret, algorithms=["HS256"])
    except jwt.PyJWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}") from None
    is_admin = bool(
        payload.get("is_admin")
        or payload.get("is_super_admin")
        or payload.get("role") in ("admin", "super_admin")
    )
    if not is_admin:
        raise HTTPException(status_code=403, detail="Admin role required")
    return payload.get("email") or "unknown"


async def _audit(action: str, by: str, payload: dict) -> None:
    """Append one row to the audit log. Best-effort."""
    if _db is None:
        return
    try:
        await _db.autonomous_repair_audit.insert_one({
            "action": action,
            "by": by,
            "at": _now(),
            "payload": payload,
        })
    except Exception as e:
        logger.warning(f"[autonomous-repair-admin] audit write failed: {e}")


# ─── Stats ────────────────────────────────────────────────────────────

@router.get("/stats")
async def get_stats(authorization: str = Header(None)) -> dict[str, Any]:
    """Honest breakdown of the autonomous-repair queue. No mocks, all
    real Mongo aggregates."""
    await _require_admin(authorization)
    if _db is None:
        raise HTTPException(status_code=503, detail="db_unavailable")

    now = _now()
    week_ago = now - timedelta(days=7)
    day_ago = now - timedelta(days=1)

    # Total + by-status counts
    total = await _db.pending_approvals.count_documents({})
    by_status: dict[str, int] = {}
    async for grp in _db.pending_approvals.aggregate([
        {"$group": {"_id": "$status", "n": {"$sum": 1}}},
    ]):
        by_status[str(grp.get("_id") or "null")] = grp.get("n", 0)

    by_type: dict[str, int] = {}
    async for grp in _db.pending_approvals.aggregate([
        {"$group": {"_id": "$type", "n": {"$sum": 1}}},
    ]):
        by_type[str(grp.get("_id") or "null")] = grp.get("n", 0)

    # Legacy rows = no `type` field set (pre-iter-325f schema)
    legacy_count = await _db.pending_approvals.count_documents({"type": {"$exists": False}})

    # Stuck awaiting_founder >7 days (handle both BSON Date and ISO string)
    stale_awaiting = await _db.pending_approvals.count_documents({
        "status": "pending_approval",
        "cto_status": "awaiting_founder",
        "$or": [
            {"created_at": {"$lt": week_ago}},
            {"created_at": {"$lt": week_ago.isoformat()}},
        ],
    })

    # Last 24h activity (handle both Date and ISO string created_at)
    recent_24h = await _db.pending_approvals.count_documents({
        "$or": [
            {"created_at": {"$gte": day_ago}},
            {"created_at": {"$gte": day_ago.isoformat()}},
        ],
    })

    # Test-target findings (Shannon scans against unowned domains)
    test_hosts = _test_hosts()
    test_target_count = await _db.pending_approvals.count_documents({
        "source": "shannon",
        "metadata.target": {"$regex": "|".join(test_hosts), "$options": "i"},
    })

    # ora_cto_proposals state
    cto_total = await _db.ora_cto_proposals.count_documents({})
    cto_by_status: dict[str, int] = {}
    async for grp in _db.ora_cto_proposals.aggregate([
        {"$group": {"_id": "$status", "n": {"$sum": 1}}},
    ]):
        cto_by_status[str(grp.get("_id") or "null")] = grp.get("n", 0)

    # Archive collection size
    archived = await _db.pending_approvals_archive.count_documents({})

    # TTL index check
    ttl_present = False
    try:
        for idx in await _db.pending_approvals.list_indexes().to_list(50):
            if idx.get("expireAfterSeconds"):
                ttl_present = True
                break
    except Exception:
        ttl_present = False

    return {
        "ok": True,
        "fetched_at": _now_iso(),
        "pending_approvals": {
            "total": total,
            "by_status": by_status,
            "by_type": by_type,
            "legacy_no_type": legacy_count,
            "stale_awaiting_founder_gt_7d": stale_awaiting,
            "test_target_findings": test_target_count,
            "recent_24h": recent_24h,
        },
        "ora_cto_proposals": {
            "total": cto_total,
            "by_status": cto_by_status,
        },
        "archive": {
            "total": archived,
        },
        "ttl_index_present": ttl_present,
        "test_hosts": list(test_hosts),
    }


# ─── Archive legacy schema rows ──────────────────────────────────────

@router.post("/archive-legacy")
async def archive_legacy(authorization: str = Header(None)) -> dict[str, Any]:
    """Move rows without a `type` field into `pending_approvals_archive`.
    These are pre-iter-325f rows that the new repair agent can't read.
    Idempotent (run twice → second pass is a no-op)."""
    admin_email = await _require_admin(authorization)
    if _db is None:
        raise HTTPException(status_code=503, detail="db_unavailable")

    moved = 0
    sample_ids: list[str] = []
    legacy_filter = {"type": {"$exists": False}}
    async for doc in _db.pending_approvals.find(legacy_filter, {"_id": 0}):
        doc["archived_at"] = _now()
        doc["archived_by"] = admin_email
        doc["archive_reason"] = "legacy_schema_no_type_field"
        try:
            await _db.pending_approvals_archive.insert_one(doc)
            await _db.pending_approvals.delete_one(
                {"approval_id": doc.get("approval_id")}
            )
            moved += 1
            if len(sample_ids) < 5:
                sample_ids.append(str(doc.get("approval_id")))
        except Exception as e:
            logger.warning(f"[autonomous-repair-admin] archive-legacy: {e}")

    await _audit("archive-legacy", admin_email, {"moved": moved, "sample": sample_ids})
    return {"ok": True, "moved": moved, "sample_ids": sample_ids,
            "reason": "legacy_schema_no_type_field"}


# ─── Reject + archive test-target Shannon findings ───────────────────

@router.post("/archive-test-targets")
async def archive_test_targets(authorization: str = Header(None)) -> dict[str, Any]:
    """Reject + archive Shannon scan findings whose `metadata.target`
    points at a known-test domain. Real customer-domain findings stay
    in the queue for founder review."""
    admin_email = await _require_admin(authorization)
    if _db is None:
        raise HTTPException(status_code=503, detail="db_unavailable")

    test_hosts = _test_hosts()
    moved = 0
    sample_ids: list[str] = []

    # Iterate Shannon rows and host-match on target URL
    cursor = _db.pending_approvals.find(
        {"source": "shannon"}, {"_id": 0},
    )
    async for doc in cursor:
        target = (doc.get("metadata") or {}).get("target") or ""
        if not target:
            continue
        try:
            host = (urlparse(target).hostname or "").lower()
        except Exception:
            host = target.lower()
        if not any(th in host for th in test_hosts):
            continue
        # Move + delete
        doc["archived_at"] = _now()
        doc["archived_by"] = admin_email
        doc["archive_reason"] = f"test_target:{host}"
        try:
            await _db.pending_approvals_archive.insert_one(doc)
            await _db.pending_approvals.delete_one(
                {"approval_id": doc.get("approval_id")}
            )
            # Also mark the matching proposal as cancelled (if any)
            pid = doc.get("cto_proposal_id")
            if pid:
                await _db.ora_cto_proposals.update_one(
                    {"proposal_id": pid},
                    {"$set": {"status": "cancelled",
                              "cancelled_at": _now_iso(),
                              "cancelled_by": admin_email,
                              "cancelled_reason": "test_target"}},
                )
            moved += 1
            if len(sample_ids) < 5:
                sample_ids.append(str(doc.get("approval_id")))
        except Exception as e:
            logger.warning(f"[autonomous-repair-admin] archive-test-targets: {e}")

    await _audit("archive-test-targets", admin_email,
                 {"moved": moved, "sample": sample_ids, "hosts": list(test_hosts)})
    return {"ok": True, "moved": moved, "sample_ids": sample_ids,
            "test_hosts": list(test_hosts)}


# ─── Reject one specific approval ────────────────────────────────────

@router.post("/reject/{approval_id}")
async def reject_one(approval_id: str, authorization: str = Header(None)) -> dict[str, Any]:
    """Move one specific row to archive with `archive_reason='manual_reject'`.
    Also cancels the linked proposal."""
    admin_email = await _require_admin(authorization)
    if _db is None:
        raise HTTPException(status_code=503, detail="db_unavailable")

    doc = await _db.pending_approvals.find_one({"approval_id": approval_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail=f"approval_id {approval_id!r} not found")

    doc["archived_at"] = _now()
    doc["archived_by"] = admin_email
    doc["archive_reason"] = "manual_reject"
    await _db.pending_approvals_archive.insert_one(doc)
    await _db.pending_approvals.delete_one({"approval_id": approval_id})

    pid = doc.get("cto_proposal_id")
    if pid:
        await _db.ora_cto_proposals.update_one(
            {"proposal_id": pid},
            {"$set": {"status": "cancelled",
                      "cancelled_at": _now_iso(),
                      "cancelled_by": admin_email,
                      "cancelled_reason": "manual_reject"}},
        )

    await _audit("reject", admin_email, {"approval_id": approval_id})
    return {"ok": True, "approval_id": approval_id, "cancelled_proposal_id": pid}


# ─── Restore one specific approval from archive ──────────────────────

@router.post("/restore/{approval_id}")
async def restore_one(approval_id: str, authorization: str = Header(None)) -> dict[str, Any]:
    """Move a row from `pending_approvals_archive` back to
    `pending_approvals` so the founder can action it. Used when:
      * a bulk archive caught a real finding by mistake,
      * the founder wants to revisit an expired-by-no-response row.

    Resets `created_at` to NOW so it doesn't immediately re-expire,
    and clears the `cto_proposal_id` so the repair agent picks it up
    again on next tick if the proposal was cancelled."""
    admin_email = await _require_admin(authorization)
    if _db is None:
        raise HTTPException(status_code=503, detail="db_unavailable")

    doc = await _db.pending_approvals_archive.find_one(
        {"approval_id": approval_id}, {"_id": 0},
    )
    if not doc:
        raise HTTPException(
            status_code=404,
            detail=f"approval_id {approval_id!r} not in archive",
        )

    # Strip archive-only fields and restamp so it doesn't re-expire on
    # the next stale-sweep.
    restored = {k: v for k, v in doc.items()
                if k not in ("archived_at", "archived_by", "archive_reason")}
    restored["restored_at"] = _now_iso()
    restored["restored_by"] = admin_email
    restored["created_at"] = _now()  # fresh timestamp = fresh window
    restored["status"] = "pending_approval"
    # Drop the cancelled proposal pointer so the agent re-proposes on
    # the next tick (uses fresh LLM analysis instead of stale).
    restored.pop("cto_proposal_id", None)
    restored.pop("cto_status", None)
    restored.pop("cto_seen_at", None)

    pid = doc.get("cto_proposal_id")
    try:
        await _db.pending_approvals.insert_one(restored)
        await _db.pending_approvals_archive.delete_one(
            {"approval_id": approval_id},
        )
        # Re-open the linked proposal so it shows in the queue again
        if pid:
            await _db.ora_cto_proposals.update_one(
                {"proposal_id": pid},
                {"$set": {"status": "restored",
                          "restored_at": _now_iso(),
                          "restored_by": admin_email}},
            )
    except Exception as e:
        # Insert may have hit unique-index conflict — leave archive intact
        raise HTTPException(status_code=500, detail=f"restore failed: {e}") from None

    await _audit("restore", admin_email, {"approval_id": approval_id})
    return {"ok": True, "approval_id": approval_id, "restored_at": restored["restored_at"]}


# ─── Auto-expire stale awaiting_founder rows ─────────────────────────

@router.post("/expire-stale")
async def expire_stale(days: int = 14, authorization: str = Header(None)) -> dict[str, Any]:
    """Move `awaiting_founder` rows older than `days` to archive
    with `archive_reason='founder_no_response'`. Default 14 days.
    Founder can still find them in `pending_approvals_archive`."""
    admin_email = await _require_admin(authorization)
    if _db is None:
        raise HTTPException(status_code=503, detail="db_unavailable")
    days = max(1, min(int(days), 365))
    cutoff = _now() - timedelta(days=days)

    moved = 0
    sample_ids: list[str] = []
    # created_at may be stored as either ISO string or datetime — handle both
    iso_cut = cutoff.isoformat()
    cursor = _db.pending_approvals.find(
        {
            "status": "pending_approval",
            "cto_status": "awaiting_founder",
            "$or": [
                {"created_at": {"$lt": cutoff}},
                {"created_at": {"$lt": iso_cut}},
            ],
        },
        {"_id": 0},
    )
    async for doc in cursor:
        doc["archived_at"] = _now()
        doc["archived_by"] = admin_email
        doc["archive_reason"] = f"founder_no_response_gt_{days}d"
        try:
            await _db.pending_approvals_archive.insert_one(doc)
            await _db.pending_approvals.delete_one(
                {"approval_id": doc.get("approval_id")}
            )
            moved += 1
            if len(sample_ids) < 5:
                sample_ids.append(str(doc.get("approval_id")))
        except Exception as e:
            logger.warning(f"[autonomous-repair-admin] expire-stale: {e}")

    await _audit("expire-stale", admin_email,
                 {"days": days, "moved": moved, "sample": sample_ids})
    return {"ok": True, "moved": moved, "sample_ids": sample_ids,
            "older_than_days": days}


# ─── Ensure TTL index ─────────────────────────────────────────────────

@router.post("/ensure-ttl")
async def ensure_ttl(retention_days: int = 60,
                     authorization: str = Header(None)) -> dict[str, Any]:
    """Create (or replace) a TTL index on `pending_approvals.created_at`
    so rows automatically clear themselves after `retention_days`.
    Safety net only — primary cleanup is via the archive endpoints.

    Note: TTL only triggers when `created_at` is stored as BSON Date.
    Rows that store it as ISO string are skipped silently by Mongo —
    use the archive endpoints to clean those up."""
    admin_email = await _require_admin(authorization)
    if _db is None:
        raise HTTPException(status_code=503, detail="db_unavailable")
    days = max(1, min(int(retention_days), 3650))
    secs = days * 86400

    results = {}
    for coll, field in (
        ("pending_approvals", "created_at"),
        ("pending_approvals_archive", "archived_at"),
        ("ora_cto_proposals", "created_at"),
        ("autonomous_repair_audit", "at"),
    ):
        try:
            # If an index with the same key exists, drop+recreate to
            # apply the new TTL value.
            for idx in await _db[coll].list_indexes().to_list(100):
                key = idx.get("key", {})
                if list(key.keys()) == [field] and idx.get("expireAfterSeconds") is not None:
                    await _db[coll].drop_index(idx["name"])
                    break
            name = await _db[coll].create_index(
                [(field, 1)], expireAfterSeconds=secs,
                name=f"{field}_ttl_{days}d",
            )
            results[coll] = {"ok": True, "field": field, "name": name, "ttl_days": days}
        except Exception as e:
            results[coll] = {"ok": False, "error": str(e)[:200]}

    await _audit("ensure-ttl", admin_email,
                 {"days": days, "results": results})
    return {"ok": True, "retention_days": days, "results": results}
