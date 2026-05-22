"""
Scout Replenish Cron
=====================
Background job that auto-tops the `campaign_leads` queue using the OSM-only
hunt path. Designed to keep auto_blast_engine fed without the user having to
fire `/api/admin/scout/run-osm-hunt` manually each day.

Behaviour:
  • Runs every CRON_INTERVAL_MINUTES (default 120).
  • Checks how many leads are currently "queued" (eligible for blast).
  • If queue depth >= QUEUE_TARGET, skips. Otherwise replenishes one
    (city, industry) tuple per tick and walks through the matrix.
  • Each run logged to `scout_replenish_runs` collection so the admin can
    audit what happened.
  • Apollo enrichment is fired-and-forgotten per inserted lead (handled by
    the underlying _run_osm_hunt_core).

Config (overridable via env):
  • AUREM_SCOUT_CRON_INTERVAL_MIN   (default 120)
  • AUREM_SCOUT_QUEUE_TARGET        (default 80)
  • AUREM_SCOUT_PER_RUN_CAP         (default 20 leads per industry per run)
  • AUREM_SCOUT_CITIES              (comma-separated, default GTA set)
  • AUREM_SCOUT_INDUSTRIES          (comma-separated, default 8-vertical set)
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_db = None


def set_db(db):
    global _db
    _db = db


# ──────────────────────────────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────────────────────────────
def _cfg_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "") or default)
    except Exception:
        return default


def _cfg_list(name: str, default: list) -> list:
    raw = (os.environ.get(name, "") or "").strip()
    if not raw:
        return list(default)
    return [x.strip() for x in raw.split(",") if x.strip()]


DEFAULT_CITIES = [
    "Mississauga, ON",
    "Toronto, ON",
    "Brampton, ON",
    "Oakville, ON",
    "Hamilton, ON",
    "Burlington, ON",
    "Vaughan, ON",
    "Markham, ON",
]

DEFAULT_INDUSTRIES = [
    # ── Trades (always converts well, high SMB pain) ─────────────
    "plumber",
    "electrician",
    "hvac",
    "locksmith",
    "pest_control",
    "landscape",
    "lawn_care",
    # ── Personal services ─────────────────────────────────────────
    "hair_salon",
    "barber",
    "beauty_salon",
    # ── Auto ──────────────────────────────────────────────────────
    "auto_repair",
    "car_wash",
    # ── Healthcare (high-LTV) ─────────────────────────────────────
    "dental",
    "chiropractor",
    "physiotherapy",
    "optometrist",
    # ── Professional services ─────────────────────────────────────
    "lawyer",
    "accountant",
    "real_estate_agent",
    "marketing_agency",
    # ── Home services ─────────────────────────────────────────────
    "cleaning_services",
    "janitorial",
    "moving_company",
    # ── Hospitality / B2C SMB ─────────────────────────────────────
    "photographer",
    "daycare",
    "personal_trainer",
    "yoga_studio",
]


def _cities() -> list:
    return _cfg_list("AUREM_SCOUT_CITIES", DEFAULT_CITIES)


def _industries() -> list:
    return _cfg_list("AUREM_SCOUT_INDUSTRIES", DEFAULT_INDUSTRIES)


def _interval_min() -> int:
    # iter 326p — was 120 (every 2 hours), which caused multi-hour
    # queue droughts when consecutive (city, industry) cells returned
    # 0 leads. New default 15 min — well under the OSM/Apollo rate
    # limits and tight enough that the founder never sees an empty
    # queue overnight. Adaptive logic in `replenish_tick` further tunes
    # the next-run interval based on the last tick's outcome.
    return _cfg_int("AUREM_SCOUT_CRON_INTERVAL_MIN", 15)


def _queue_target() -> int:
    return _cfg_int("AUREM_SCOUT_QUEUE_TARGET", 80)


def _per_run_cap() -> int:
    return _cfg_int("AUREM_SCOUT_PER_RUN_CAP", 20)


# ──────────────────────────────────────────────────────────────────────
# Cursor — walks through (city, industry) matrix one cell per tick
# ──────────────────────────────────────────────────────────────────────
async def _get_cursor() -> Dict[str, int]:
    if _db is None:
        return {"city_idx": 0, "ind_idx": 0}
    doc = await _db.scout_replenish_cursor.find_one(
        {"_id": "cursor"}, {"_id": 0}
    )
    if not doc:
        doc = {"city_idx": 0, "ind_idx": 0}
        await _db.scout_replenish_cursor.update_one(
            {"_id": "cursor"}, {"$set": doc}, upsert=True
        )
    return doc


async def _advance_cursor(cities: list, industries: list) -> Dict[str, int]:
    """Move cursor to next (city, industry) cell, wrapping at end."""
    cursor = await _get_cursor()
    city_idx = cursor["city_idx"]
    ind_idx = cursor["ind_idx"] + 1
    if ind_idx >= len(industries):
        ind_idx = 0
        city_idx += 1
        if city_idx >= len(cities):
            city_idx = 0
    if _db is not None:
        await _db.scout_replenish_cursor.update_one(
            {"_id": "cursor"},
            {"$set": {"city_idx": city_idx, "ind_idx": ind_idx}},
            upsert=True,
        )
    return {"city_idx": city_idx, "ind_idx": ind_idx}


async def _current_queue_depth() -> int:
    if _db is None:
        return 0
    try:
        # Count leads that the auto-blast engine considers "eligible-ish".
        # Mirrors the gating used by why-not-sending: status='queued' AND
        # at least one contact field present AND not on do_not_contact.
        return await _db.campaign_leads.count_documents({
            "status": "queued",
            "noise_flag": {"$ne": True},
            "$or": [
                {"email": {"$nin": ["", None]}},
                {"phone": {"$nin": ["", None]}},
                {"website_url": {"$nin": ["", None]}},
            ],
        })
    except Exception as e:
        logger.warning(f"[scout-cron] queue depth check failed: {e}")
        return 0


# ──────────────────────────────────────────────────────────────────────
# Public API — single tick + scheduler hook
# ──────────────────────────────────────────────────────────────────────
async def replenish_tick(force: bool = False) -> Dict[str, Any]:
    """One tick of the cron. Returns a dict suitable for HTTP response."""
    started = datetime.now(timezone.utc).isoformat()
    run_id = f"replenish-{uuid.uuid4().hex[:10]}"

    if _db is None:
        return {"ok": False, "error": "db_not_wired", "run_id": run_id,
                "started_at": started}

    queue_depth = await _current_queue_depth()
    target = _queue_target()
    cities = _cities()
    industries = _industries()

    if not force and queue_depth >= target:
        result = {
            "ok": True,
            "run_id": run_id,
            "skipped": True,
            "reason": f"queue_depth {queue_depth} >= target {target}",
            "queue_depth": queue_depth,
            "queue_target": target,
            # iter 326p — coast on the skip path. Queue is already full,
            # so the next tick can wait. We use max() with the configured
            # interval so a founder who deliberately sets a longer cadence
            # is respected.
            "next_run_in_minutes": max(60, _interval_min()),
            "started_at": started,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        await _db.scout_replenish_runs.insert_one({**result, "_id": run_id})
        logger.info(f"[scout-cron] skip: {result['reason']}")
        return result

    cursor = await _get_cursor()
    city = cities[cursor["city_idx"] % len(cities)]
    industry = industries[cursor["ind_idx"] % len(industries)]

    logger.info(
        f"[scout-cron] tick: queue_depth={queue_depth} target={target} "
        f"→ replenish {industry!r}@{city!r}"
    )

    # Delegate to the shared core that handles OSM + Apollo enrichment.
    try:
        from routers.scout_diagnose_router import _run_osm_hunt_core
        summary = await _run_osm_hunt_core(
            ind_list=[industry],
            city=city,
            per_industry_cap=_per_run_cap(),
        )
    except Exception as e:
        logger.exception(f"[scout-cron] core hunt failed: {e}")
        summary = {"success": False, "error": f"{type(e).__name__}: {str(e)[:200]}",
                   "leads_written_total": 0}

    # Move cursor regardless (failure on one cell shouldn't lock it).
    await _advance_cursor(cities, industries)

    result = {
        "ok": bool(summary.get("success")),
        "run_id": run_id,
        "skipped": False,
        "queue_depth_before": queue_depth,
        "queue_target": target,
        "city": city,
        "industry": industry,
        "leads_written": summary.get("leads_written_total", 0),
        "raw_returned": summary.get("raw_returned_total", 0),
        "skipped_duplicate": summary.get("skipped_duplicate_total", 0),
        "skipped_no_contact": summary.get("skipped_no_contact_total", 0),
        "summary": summary,
        "started_at": started,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    # iter 326p — adaptive interval. When the queue is hungry, the cron
    # used to wait the full 1 hour for the next attempt — and if that
    # cell happened to return 0 leads, the founder waited another full
    # hour for the next try. Now we record a `next_run_in_minutes` hint
    # on every result so the scheduler hook (below) can reschedule the
    # job dynamically: tight loop when starving, slow loop when full.
    if result.get("skipped"):
        # Queue already healthy. Coast for a while.
        result["next_run_in_minutes"] = max(60, _interval_min())
    elif result["leads_written"] > 0:
        # Just got some leads in. Run again sooner — campaigns are eating.
        result["next_run_in_minutes"] = 20
    else:
        # Ran but cell was a dud. Retry FAST with the next (city, industry).
        result["next_run_in_minutes"] = 5

    # iter 326p — founder notification. When real leads actually land
    # (>0), send a single concise Telegram ping so the founder knows the
    # queue is being topped up without having to dashboard-watch. Failures
    # (creds missing, network) are swallowed silently — notification is
    # nice-to-have, not load-bearing.
    if result["leads_written"] > 0:
        try:
            from services.autopilot_brief_notifier import _send_telegram
            await _send_telegram(
                f"AUREM auto-refill: +{result['leads_written']} fresh leads "
                f"({industry} in {city}). Queue was {queue_depth}, now "
                f"{queue_depth + result['leads_written']}. "
                f"Auto-blast will pick them up on the next cycle."
            )
        except Exception as e:
            logger.debug(f"[scout-cron] telegram ping skipped: {e}")

    try:
        await _db.scout_replenish_runs.insert_one({**result, "_id": run_id})
    except Exception:
        pass
    return result


def install_scheduler(scheduler) -> Optional[str]:
    """Hook the cron job into the existing AsyncIOScheduler.

    iter 326p — wraps `replenish_tick` so that after each run we
    re-schedule the NEXT run based on the result's adaptive hint
    (`next_run_in_minutes`). Effect:
      • Queue healthy / skipped       → 60+ min until next tick (cheap)
      • Tick wrote ≥1 lead            → 20 min until next tick (warm)
      • Tick ran but cell was a dud   → 5 min until next tick (hunt mode)
    """
    try:
        from apscheduler.triggers.interval import IntervalTrigger
        from apscheduler.triggers.date import DateTrigger
        from datetime import timedelta
    except Exception as e:
        logger.warning(f"[scout-cron] apscheduler not importable: {e}")
        return None

    interval = _interval_min()

    async def _adaptive_tick() -> None:
        result = await replenish_tick()
        # Pick the recommended next-run window; fall back to the
        # baseline interval if the result didn't carry a hint (e.g. on
        # an unexpected error).
        next_min = int(result.get("next_run_in_minutes") or interval)
        try:
            scheduler.reschedule_job(
                "scout_replenish_cron",
                trigger=IntervalTrigger(minutes=next_min),
            )
            logger.info(
                f"[scout-cron] adaptive reschedule → next tick in "
                f"{next_min} min (last result: "
                f"{'skipped' if result.get('skipped') else 'ran'}, "
                f"leads={result.get('leads_written', 0)})"
            )
        except Exception as e:
            logger.warning(f"[scout-cron] reschedule failed: {e}")

    job = scheduler.add_job(
        _adaptive_tick,
        IntervalTrigger(minutes=interval),
        id="scout_replenish_cron",
        name="Scout Replenish Cron",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    logger.info(
        f"[scout-cron] scheduled — initial every {interval} min, "
        f"adaptive thereafter ({len(_cities())} cities × "
        f"{len(_industries())} industries cycle)"
    )
    return job.id
