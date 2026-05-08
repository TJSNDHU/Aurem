"""
Schema Drift Migration — iter 282ah (Prompt 5, Task C1).

Normalises two long-standing inconsistencies spotted in the 282ab audit:

1. `council_decisions` — lead_id lived nested at `payload_summary.lead_id`
   and timestamp was only on `ts` (ISO string). Analytics queries looking
   for top-level `lead_id`/`created_at` returned None. Promote both to
   canonical top-level fields.

2. `campaign_leads.outreach_history[]` — writers used mixed keys
   (`type` vs `channel`, `timestamp`/`sent_at` vs `dispatched_at`).
   Normalise into canonical `channel` + `dispatched_at` + `status`
   so Prompt 1 (readiness report) and Morning Brief can filter cleanly.

Idempotent: uses `migrations` collection to track completion. Re-running
a completed migration is a no-op returning `{"skipped": "already_applied"}`.

Public surface:
  • fix_schema_drift(db)            — async, safe at startup
  • fix_schema_drift_sync(db)       — sync wrapper for pytest

Also creates the analytics index `{lead_id: 1, ts: -1}` on council_decisions.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

MIGRATION_ID = "282ah_schema_drift_v1"


# ─────────────────────────────────────────────────────────────────────
# Pure guards used by live writers
# ─────────────────────────────────────────────────────────────────────
def guard_council_record(record: dict) -> dict:
    """Fill required council_decisions fields before insert. Pure."""
    r = dict(record or {})
    if not r.get("ts"):
        r["ts"] = datetime.now(timezone.utc).isoformat()
    if not r.get("created_at"):
        r["created_at"] = r["ts"]
    if not r.get("agent"):
        r["agent"] = "ora"
    if not r.get("action"):
        r["action"] = r.get("action_kind") or "unknown"
    if not r.get("status"):
        r["status"] = r.get("decision") or "unknown"
    if not r.get("lead_id"):
        ps = r.get("payload_summary") or {}
        r["lead_id"] = ps.get("lead_id") or r.get("decision_id") or "unknown"
    return r


def guard_outreach_entry(entry: dict) -> dict:
    """Fill required outreach_history[] fields before push. Pure."""
    e = dict(entry or {})
    # Channel canonicalisation (legacy writers used `type`)
    if not e.get("channel"):
        e["channel"] = e.get("type") or "unknown"
    # Dispatch timestamp canonicalisation
    if not e.get("dispatched_at"):
        e["dispatched_at"] = (
            e.get("sent_at") or e.get("timestamp")
            or e.get("at") or datetime.now(timezone.utc).isoformat()
        )
    if not e.get("status"):
        e["status"] = "unknown"
    return e


# ─────────────────────────────────────────────────────────────────────
# One-off migration (idempotent)
# ─────────────────────────────────────────────────────────────────────
async def _already_applied(db) -> bool:
    try:
        doc = await db.migrations.find_one({"_id": MIGRATION_ID})
        return doc is not None
    except Exception as e:
        logger.debug(f"[schema-migrate] migrations check failed: {e}")
        return False


async def _mark_applied(db, stats: dict) -> None:
    try:
        await db.migrations.update_one(
            {"_id": MIGRATION_ID},
            {"$set": {
                "applied_at": datetime.now(timezone.utc).isoformat(),
                "stats": stats,
            }},
            upsert=True,
        )
    except Exception as e:
        logger.debug(f"[schema-migrate] mark applied failed: {e}")


async def _backfill_council(db) -> int:
    """Promote payload_summary.lead_id → lead_id; ts → created_at.
    Returns count of docs touched."""
    fixed = 0
    try:
        cursor = db.council_decisions.find(
            {"$or": [{"lead_id": {"$exists": False}},
                      {"lead_id": None},
                      {"created_at": {"$exists": False}},
                      {"created_at": None}]},
            {"_id": 1, "payload_summary": 1, "ts": 1, "decision": 1,
             "action_kind": 1, "decision_id": 1, "lead_id": 1, "created_at": 1},
        )
        async for d in cursor:
            set_doc = {}
            if not d.get("lead_id"):
                ps = d.get("payload_summary") or {}
                set_doc["lead_id"] = ps.get("lead_id") or d.get("decision_id") or "unknown"
            if not d.get("created_at"):
                set_doc["created_at"] = d.get("ts") or datetime.now(timezone.utc).isoformat()
            if not d.get("agent"):
                set_doc["agent"] = "ora"
            if not d.get("action"):
                set_doc["action"] = d.get("action_kind") or "unknown"
            if not d.get("status"):
                set_doc["status"] = d.get("decision") or "unknown"
            if set_doc:
                try:
                    await db.council_decisions.update_one(
                        {"_id": d["_id"]}, {"$set": set_doc},
                    )
                    fixed += 1
                except Exception as e:
                    logger.debug(f"[schema-migrate] council update failed: {e}")
    except Exception as e:
        logger.warning(f"[schema-migrate] council backfill failed: {e}")
    return fixed


async def _backfill_outreach_history(db) -> int:
    """Normalise each campaign_leads.outreach_history[] entry in place.
    Returns count of leads (not entries) touched."""
    fixed = 0
    try:
        cursor = db.campaign_leads.find(
            {"outreach_history.0": {"$exists": True}},
            {"_id": 1, "lead_id": 1, "outreach_history": 1},
        )
        async for d in cursor:
            history = d.get("outreach_history") or []
            new_history = []
            dirty = False
            for e in history:
                if not isinstance(e, dict):
                    # Garbage entry — replace with minimal canonical shape
                    new_history.append({
                        "channel": "unknown", "status": "unknown",
                        "dispatched_at": datetime.now(timezone.utc).isoformat(),
                    })
                    dirty = True
                    continue
                fixed_entry = guard_outreach_entry(e)
                if fixed_entry != e:
                    dirty = True
                new_history.append(fixed_entry)
            if dirty:
                try:
                    await db.campaign_leads.update_one(
                        {"_id": d["_id"]},
                        {"$set": {"outreach_history": new_history}},
                    )
                    fixed += 1
                except Exception as ex:
                    logger.debug(f"[schema-migrate] outreach update failed: {ex}")
    except Exception as e:
        logger.warning(f"[schema-migrate] outreach backfill failed: {e}")
    return fixed


async def _ensure_indexes(db) -> None:
    try:
        await db.council_decisions.create_index(
            [("lead_id", 1), ("ts", -1)], name="lead_ts", background=True,
        )
        await db.council_decisions.create_index(
            [("created_at", -1)], name="created_at_desc", background=True,
        )
    except Exception as e:
        logger.debug(f"[schema-migrate] index skipped: {e}")


async def fix_schema_drift(db) -> dict:
    """Run the one-off migration. Idempotent: returns `skipped` if already applied.

    Returns: {"fixed": N_council+N_outreach, "council": N, "outreach_leads": N,
              "skipped": "already_applied" | None}
    """
    if db is None:
        return {"fixed": 0, "skipped": "db_unavailable"}

    if await _already_applied(db):
        # Still re-assert indexes (cheap, idempotent) in case of DB reset.
        await _ensure_indexes(db)
        return {"fixed": 0, "skipped": "already_applied"}

    council_fixed = await _backfill_council(db)
    outreach_fixed = await _backfill_outreach_history(db)
    await _ensure_indexes(db)

    stats = {
        "council_fixed":       council_fixed,
        "outreach_leads_fixed": outreach_fixed,
        "fixed":               council_fixed + outreach_fixed,
    }
    await _mark_applied(db, stats)
    logger.info(f"[schema-migrate] {MIGRATION_ID} applied: {stats}")
    return stats


def fix_schema_drift_sync(db) -> dict:
    """Sync wrapper for pytest."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                return ex.submit(lambda: asyncio.run(fix_schema_drift(db))).result()
    except RuntimeError:
        pass
    return asyncio.run(fix_schema_drift(db))


__all__ = [
    "fix_schema_drift",
    "fix_schema_drift_sync",
    "guard_council_record",
    "guard_outreach_entry",
    "MIGRATION_ID",
]
