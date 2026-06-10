"""
services/scout_autotopup.py — iter D-71e

Background job that keeps the eligible lead pool above a floor so the
founder never sees a "no_eligible_leads" yellow on Campaign Health.

How it works
------------
Every `RUN_EVERY_MIN` minutes:
 1. Run the SAME eligibility query that `auto_blast_engine._eligible_leads`
    uses (mirrored from `services/campaign_health._check_lead_pool`).
 2. If count >= `FLOOR_LEADS` → no-op.
 3. Otherwise call `apollo_discovery.discover_for_default_targets(...)`
    with a small `max_combos` sample (random Canada-wide rotation).
 4. Persist each fresh lead into `campaign_leads` (upsert by lead_id).
 5. Log the topup in `scout_autotopup_log` for the founder timeline.

Guardrails
----------
- Cooldown: max 1 topup per `COOLDOWN_MIN` minutes (default 60).
- Daily ceiling: max `MAX_TOPUPS_PER_DAY` topups (default 6 → 240 leads).
- Off switch: env `SCOUT_AUTOTOPUP_DISABLED=true` halts everything.
- Apollo key absent → graceful no-op with reason logged.

The function is also exposed as an HTTP endpoint
`POST /api/admin/scout-autotopup/trigger` for manual one-shot use and
`GET  /api/admin/scout-autotopup/status` for read-only health.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ── Tunables (override via env) ───────────────────────────────────────
FLOOR_LEADS         = int(os.environ.get("SCOUT_AUTOTOPUP_FLOOR", "50"))
TOPUP_TARGET        = int(os.environ.get("SCOUT_AUTOTOPUP_TARGET", "100"))   # aim above floor so we don't trigger again immediately
MAX_COMBOS_PER_RUN  = int(os.environ.get("SCOUT_AUTOTOPUP_MAX_COMBOS", "10"))
PER_COMBO_RESULTS   = int(os.environ.get("SCOUT_AUTOTOPUP_PER_COMBO", "10"))
COOLDOWN_MIN        = int(os.environ.get("SCOUT_AUTOTOPUP_COOLDOWN_MIN", "60"))
MAX_TOPUPS_PER_DAY  = int(os.environ.get("SCOUT_AUTOTOPUP_MAX_PER_DAY", "6"))
RUN_EVERY_MIN       = int(os.environ.get("SCOUT_AUTOTOPUP_INTERVAL_MIN", "15"))

# Internal-test filters must match auto_blast_engine + lead_pool exactly.
_INTERNAL_TEST_SOURCES = (
    "no_website_signup", "awb_e2e_test", "a2a_e2e_test",
    "playwright_test", "qa_smoke", "agent2agent_test",
    "builder_e2e", "qa_harness", "internal_test", "prod_smoke_test",
)
_TEST_EMAIL_RE = r"@(aurem-test|test|example)\."


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _is_disabled() -> bool:
    return (os.environ.get("SCOUT_AUTOTOPUP_DISABLED", "false")
            .strip().lower() in ("1", "true", "yes"))


# ── Core eligibility count (single SSOT) ─────────────────────────────

async def count_eligible(db) -> int:
    """Count leads that pass the SAME filter the auto-blast runner uses.
    If this number is < FLOOR_LEADS, we need a topup."""
    return await db.campaign_leads.count_documents({
        "last_blast_at": {"$exists": False},
        "noise_flag":    {"$ne": True},
        "source":        {"$nin": list(_INTERNAL_TEST_SOURCES)},
        "$or": [
            {"email": {"$nin": ["", None]}},
            {"phone": {"$nin": ["", None]}},
        ],
        "email":  {"$not": {"$regex": _TEST_EMAIL_RE, "$options": "i"}},
        "status": {"$nin": ["signed_up", "not_interested", "unsubscribed"]},
    })


# ── Guardrails ───────────────────────────────────────────────────────

async def _hit_cooldown(db) -> bool:
    """Returns True if last topup was within COOLDOWN_MIN minutes."""
    cutoff = (_now() - timedelta(minutes=COOLDOWN_MIN)).isoformat()
    last = await db.scout_autotopup_log.find_one(
        {"started_at": {"$gte": cutoff}, "outcome": "topup_fired"},
        sort=[("started_at", -1)],
    )
    return last is not None


async def _hit_daily_ceiling(db) -> bool:
    """Returns True if MAX_TOPUPS_PER_DAY have already fired today."""
    start_of_day = _now().replace(hour=0, minute=0, second=0, microsecond=0)
    fired_today = await db.scout_autotopup_log.count_documents({
        "started_at": {"$gte": start_of_day.isoformat()},
        "outcome": "topup_fired",
    })
    return fired_today >= MAX_TOPUPS_PER_DAY


# ── Topup primitive ─────────────────────────────────────────────────

async def _persist_lead(db, lead: Dict[str, Any]) -> bool:
    """Upsert one Apollo-discovered lead into campaign_leads. Returns
    True if a NEW document was inserted (vs. an existing match found)."""
    now_iso = _now().isoformat()
    lead_id = lead.get("lead_id")
    if not lead_id:
        return False
    # Idempotency: don't overwrite an existing lead that may have been
    # touched already (last_blast_at, status, etc.).
    existing = await db.campaign_leads.find_one(
        {"lead_id": lead_id}, {"_id": 1},
    )
    if existing:
        return False
    doc = {
        **lead,
        "tenant_id":  "global",
        "created_at": now_iso,
        "updated_at": now_iso,
        "status":     "queued",
        "discovered_via": "scout_autotopup",
    }
    await db.campaign_leads.update_one(
        {"lead_id": lead_id}, {"$setOnInsert": doc}, upsert=True,
    )
    return True


async def trigger_topup(db, *, reason: str = "manual") -> Dict[str, Any]:
    """Force one Apollo Canada-wide batch right now.

    Returns a structured outcome dict suitable for storing in the log
    AND returning to the manual-trigger HTTP route.
    """
    started_at = _now().isoformat()
    doc: Dict[str, Any] = {
        "started_at":  started_at,
        "reason":      reason,
        "floor":       FLOOR_LEADS,
        "target":      TOPUP_TARGET,
        "max_combos":  MAX_COMBOS_PER_RUN,
    }
    if _is_disabled():
        doc["outcome"] = "disabled"
        doc["detail"]  = "SCOUT_AUTOTOPUP_DISABLED=true"
        await db.scout_autotopup_log.insert_one(dict(doc))
        return doc
    if not os.environ.get("APOLLO_API_KEY", "").strip():
        doc["outcome"] = "no_apollo_key"
        doc["detail"]  = "APOLLO_API_KEY not set on host"
        await db.scout_autotopup_log.insert_one(dict(doc))
        return doc

    try:
        from services.apollo_discovery import discover_for_default_targets
        rows = await discover_for_default_targets(
            per_combo=PER_COMBO_RESULTS,
            max_combos=MAX_COMBOS_PER_RUN,
        )
    except Exception as e:
        logger.exception("[scout-autotopup] discovery crashed")
        doc["outcome"] = "discovery_error"
        doc["detail"]  = str(e)[:300]
        await db.scout_autotopup_log.insert_one(dict(doc))
        return doc

    inserted = 0
    for lead in (rows or []):
        try:
            if await _persist_lead(db, lead):
                inserted += 1
        except Exception as e:
            logger.warning(f"[scout-autotopup] persist failed for {lead.get('lead_id')}: {e}")
    new_eligible = await count_eligible(db)
    doc["outcome"]        = "topup_fired"
    doc["leads_returned"] = len(rows or [])
    doc["leads_inserted"] = inserted
    doc["eligible_after"] = new_eligible
    doc["finished_at"]    = _now().isoformat()
    await db.scout_autotopup_log.insert_one(dict(doc))
    logger.info(
        f"[scout-autotopup] reason={reason} inserted={inserted}/{len(rows or [])} "
        f"eligible_after={new_eligible}"
    )
    return doc


# ── Check loop (used by the background scheduler) ───────────────────

async def check_and_topup(db) -> Dict[str, Any]:
    """One pass of the auto-topup loop. Cheap if no action needed.

    Order:
      1. Disabled? Skip.
      2. Eligible ≥ FLOOR? Skip with `floor_met`.
      3. Cooldown active? Skip with `cooldown_active`.
      4. Daily ceiling hit? Skip with `daily_ceiling`.
      5. Fire `trigger_topup(reason="floor_breached")`.
    """
    if _is_disabled():
        return {"outcome": "disabled"}
    elig = await count_eligible(db)
    if elig >= FLOOR_LEADS:
        return {"outcome": "floor_met", "eligible": elig, "floor": FLOOR_LEADS}
    if await _hit_cooldown(db):
        return {"outcome": "cooldown_active",
                "eligible": elig, "cooldown_min": COOLDOWN_MIN}
    if await _hit_daily_ceiling(db):
        return {"outcome": "daily_ceiling",
                "eligible": elig, "max_per_day": MAX_TOPUPS_PER_DAY}
    # Conditions met — fire.
    return await trigger_topup(
        db, reason=f"floor_breached_{elig}lt{FLOOR_LEADS}",
    )


# ── Background scheduler loop (started from p1-worker) ──────────────

async def autotopup_scheduler(db_getter):
    """Forever-loop launched at boot. `db_getter` is a callable returning
    the live Mongo db (so it can lazy-resolve after server.py finishes
    wiring set_db). Sleeps `RUN_EVERY_MIN` minutes between passes.
    """
    logger.info(
        f"[scout-autotopup] scheduler alive — floor={FLOOR_LEADS} "
        f"target={TOPUP_TARGET} interval={RUN_EVERY_MIN}m "
        f"cooldown={COOLDOWN_MIN}m max/day={MAX_TOPUPS_PER_DAY}"
    )
    # 60s grace so other boot tasks finish first
    await asyncio.sleep(60)
    while True:
        try:
            db = db_getter()
            if db is not None:
                outcome = await check_and_topup(db)
                if outcome.get("outcome") not in ("floor_met", "cooldown_active"):
                    logger.info(f"[scout-autotopup] pass: {outcome}")
        except Exception:
            logger.exception("[scout-autotopup] pass crashed — sleeping then retrying")
        await asyncio.sleep(RUN_EVERY_MIN * 60)


# ── Status (for the HTTP endpoint) ───────────────────────────────────

async def status(db) -> Dict[str, Any]:
    elig = await count_eligible(db)
    start_of_day = _now().replace(hour=0, minute=0, second=0, microsecond=0)
    fired_today = await db.scout_autotopup_log.count_documents({
        "started_at": {"$gte": start_of_day.isoformat()},
        "outcome": "topup_fired",
    })
    last = await db.scout_autotopup_log.find_one(
        {}, {"_id": 0}, sort=[("started_at", -1)],
    )
    return {
        "disabled":          _is_disabled(),
        "eligible_now":      elig,
        "floor":             FLOOR_LEADS,
        "target":            TOPUP_TARGET,
        "topups_today":      fired_today,
        "max_per_day":       MAX_TOPUPS_PER_DAY,
        "cooldown_min":      COOLDOWN_MIN,
        "interval_min":      RUN_EVERY_MIN,
        "last_run":          last,
        "would_fire_now":    (not _is_disabled())
                              and (elig < FLOOR_LEADS)
                              and (not await _hit_cooldown(db))
                              and (not await _hit_daily_ceiling(db)),
    }
