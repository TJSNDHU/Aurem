"""
Active Site Change Watcher — iter 282ag (Prompt 4).

Weekly cron (Saturday 7 AM UTC) that sweeps active leads, diffs their
websites, and fires priority outreach the moment a change is detected —
so AUREM beats competitors to the inbox when a lead redecorates their
site. Credit-bounded (max 50 leads per run).

Public surface:
  • run_weekly_site_watch(db)   — scheduled entrypoint
  • watcher_health(db)          — chip probe

Unit-testable helpers (pure, no DB):
  • build_watcher_summary(...)
  • build_trigger_doc(...)
  • run_weekly_site_watch_sync(db) — sync wrapper for pytest monkeypatch

Collections:
  • site_change_triggers — log of every fired trigger (TTL 30 days)
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

MAX_LEADS_PER_RUN = 50
MAX_PRIORITY_LEADS_PER_RUN = 10
TRIGGER_RETENTION_SECONDS = 30 * 24 * 3600  # 30 days
SKIP_STATUSES = frozenset({"closed", "closed_won", "closed_lost",
                             "lost", "unsubscribed", "do_not_contact"})

# Priority-tier gate: Yelp-star ≥4.5 OR review_count ≥50. Top-shelf prospects
# get daily coverage instead of weekly so site-update triggers fire within 24h.
PRIORITY_RATING_MIN = 4.5
PRIORITY_REVIEWS_MIN = 50


# ─────────────────────────────────────────────────────────────────────
# Pure helpers (unit-tested)
# ─────────────────────────────────────────────────────────────────────
def build_watcher_summary(leads_checked: int, changes_detected: int,
                           outreach_fired: int, skipped: int) -> dict:
    """Shape the summary returned from `run_weekly_site_watch`. Pure."""
    return {
        "leads_checked":     int(leads_checked),
        "changes_detected":  int(changes_detected),
        "outreach_fired":    int(outreach_fired),
        "skipped":           int(skipped),
        "ts":                datetime.now(timezone.utc),
    }


def build_trigger_doc(lead_id: str, url: str, preview: str,
                      outreach_fired: bool) -> dict:
    """Shape the doc persisted to db.site_change_triggers. Pure."""
    now = datetime.now(timezone.utc)
    return {
        "lead_id":        lead_id,
        "url":            url,
        "preview":        (preview or "")[:400],
        "outreach_fired": bool(outreach_fired),
        "ts":             now,
        "date":           now.strftime("%Y-%m-%d"),
    }


def run_weekly_site_watch_sync(db) -> dict:
    """Synchronous wrapper for pytest monkeypatch tests.

    Runs the async entrypoint on a fresh event loop when none is active,
    otherwise schedules it on the existing loop and blocks.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If inside an already-running loop (rare in tests), defer to a
            # new loop in a thread.
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                fut = ex.submit(lambda: asyncio.run(run_weekly_site_watch(db)))
                return fut.result()
    except RuntimeError:
        pass
    return asyncio.run(run_weekly_site_watch(db))


# ─────────────────────────────────────────────────────────────────────
# Priority outreach dispatch — thin wrapper over existing channels
# ─────────────────────────────────────────────────────────────────────
async def _fire_priority_outreach(db, lead: dict, context: str) -> bool:
    """Send a single priority outreach. Returns True iff at least one
    channel succeeded. Never raises.

    Prefers email (highest deliverability) → WhatsApp fallback. SMS is
    skipped here since A2P campaign status is still being resolved.
    """
    email = (lead.get("email") or "").strip()
    phone = (lead.get("phone") or "").strip()
    biz = lead.get("business_name") or "there"

    fired = False

    # Email via Resend (matches followup_ora pattern)
    if email:
        try:
            import os
            from services.email_engine import resend  # iter 326x defensive
            from services.casl_compliance import wrap_email_html
            resend.api_key = os.environ.get("RESEND_API_KEY", "")
            html = wrap_email_html(
                f'<p><strong>Noticed you just updated your site.</strong></p>'
                f'<p>{context}</p>'
                f'<p>Following up on AUREM for {biz} — '
                f'worth a 5-minute call to talk about what changed?</p>',
                lead_id=lead.get("lead_id", ""),
            )
            resend.Emails.send({
                "from": "ORA <ora@aurem.live>",
                "to": [email],
                "subject": f"Saw the update to {biz}'s site",
                "html": html,
            })
            fired = True
        except Exception as e:
            logger.debug(f"[site_watcher] email fire failed for {lead.get('lead_id')}: {e}")

    # WhatsApp fallback / parallel
    if phone:
        try:
            from services.casl_compliance import wrap_whatsapp
            from services.twilio_service import send_whatsapp_message
            body = wrap_whatsapp(
                f"Hi — noticed {biz}'s site was just updated. "
                "AUREM ORA here, 30 seconds to show what we spotted?"
            )
            await send_whatsapp_message(phone, body)
            fired = True
        except Exception as e:
            logger.debug(f"[site_watcher] whatsapp fire failed for {lead.get('lead_id')}: {e}")

    return fired


# ─────────────────────────────────────────────────────────────────────
# Main entrypoint
# ─────────────────────────────────────────────────────────────────────
async def run_weekly_site_watch(db) -> dict:
    """Full sweep (Saturday 7 AM UTC). Capped at MAX_LEADS_PER_RUN."""
    return await _run_watch(db, mode="weekly",
                              query=None,
                              cap=MAX_LEADS_PER_RUN)


async def run_daily_priority_watch(db) -> dict:
    """Tighter, daily sweep (Mon-Fri 6 AM UTC) — top-tier leads only.

    Gate: yelp_rating >= PRIORITY_RATING_MIN OR review_count >= PRIORITY_REVIEWS_MIN.
    Capped at MAX_PRIORITY_LEADS_PER_RUN (10) to protect webclaw credits while
    still giving high-value prospects 24h trigger latency.
    """
    query = {
        "website_url": {"$exists": True, "$nin": [None, ""]},
        "$or": [
            {"yelp_rating": {"$gte": PRIORITY_RATING_MIN}},
            {"rating":      {"$gte": PRIORITY_RATING_MIN}},
            {"review_count": {"$gte": PRIORITY_REVIEWS_MIN}},
            {"reviews":      {"$gte": PRIORITY_REVIEWS_MIN}},
        ],
    }
    return await _run_watch(db, mode="daily_priority", query=query,
                              cap=MAX_PRIORITY_LEADS_PER_RUN)


async def _run_watch(db, mode: str, query: dict | None, cap: int) -> dict:
    """Shared sweep core used by both weekly and daily_priority variants."""
    # Gate on webclaw configuration — no key means legacy httpx fallback only,
    # which returns no real change signal.
    try:
        from services.webclaw_client import is_configured
        if not is_configured():
            return {"skipped": "webclaw_not_configured",
                    "mode": mode,
                    "ts": datetime.now(timezone.utc)}
    except Exception:
        return {"skipped": "webclaw_not_configured",
                "mode": mode,
                "ts": datetime.now(timezone.utc)}

    if db is None:
        return {"skipped": "db_unavailable", "mode": mode,
                "ts": datetime.now(timezone.utc)}

    checked = 0
    changes = 0
    fired = 0
    skipped = 0

    try:
        from services.website_diff import diff_lead_site
    except Exception as e:
        logger.warning(f"[site_watcher] diff import failed: {e}")
        return build_watcher_summary(0, 0, 0, 0)

    try:
        cursor = db.campaign_leads.find(
            query or {"website_url": {"$exists": True, "$nin": [None, ""]}},
            {
                "_id": 0, "lead_id": 1, "website_url": 1,
                "status": 1, "stage": 1, "email": 1, "phone": 1,
                "business_name": 1, "yelp_rating": 1, "rating": 1,
                "review_count": 1, "reviews": 1,
            },
        ).limit(cap * 2)
        leads = await cursor.to_list(length=cap * 2)
    except Exception as e:
        logger.warning(f"[site_watcher] lead cursor failed: {e}")
        leads = []

    for lead in leads:
        if checked >= cap:
            break
        status = (lead.get("status") or "").lower()
        stage = (lead.get("stage") or "").lower()
        if status in SKIP_STATUSES or stage in SKIP_STATUSES:
            skipped += 1
            continue
        url = (lead.get("website_url") or "").strip()
        lead_id = lead.get("lead_id")
        if not url.startswith(("http://", "https://")) or not lead_id:
            skipped += 1
            continue

        checked += 1
        try:
            diff = await diff_lead_site(db, lead_id, url)
        except Exception as e:
            logger.debug(f"[site_watcher] diff failed for {lead_id}: {e}")
            continue

        if not diff.get("changed"):
            continue

        changes += 1
        preview = (diff.get("new_content_preview") or "").strip()

        # Persist change-flag on the lead
        try:
            await db.campaign_leads.update_one(
                {"lead_id": lead_id},
                {"$set": {
                    "site_changed":         True,
                    "site_changed_at":      datetime.now(timezone.utc),
                    "site_change_preview":  preview[:400],
                }},
            )
        except Exception as e:
            logger.debug(f"[site_watcher] lead flag update failed: {e}")

        # Fire priority outreach
        context = (
            f"PRIORITY: This lead just updated their website. "
            f"New content: {preview[:150]}. "
            "Reference this in your outreach."
        )
        ok = await _fire_priority_outreach(db, lead, context)
        if ok:
            fired += 1

        # Log trigger
        try:
            doc = build_trigger_doc(lead_id, url, preview, ok)
            doc["mode"] = mode
            await db.site_change_triggers.insert_one(dict(doc))
        except Exception as e:
            logger.debug(f"[site_watcher] trigger log failed: {e}")

    summary = build_watcher_summary(checked, changes, fired, skipped)
    summary["mode"] = mode
    logger.info(f"[site_watcher] {mode} run complete: {summary}")
    # Heartbeat so chip can show last-run time (per-mode key)
    try:
        await db.site_change_triggers_meta.update_one(
            {"_id": f"watcher_heartbeat_{mode}"},
            {"$set": {"last_run": summary["ts"], "last_summary": summary}},
            upsert=True,
        )
        # Also keep the legacy composite key up-to-date so existing watcher
        # chip tooltip (iter 282ag) keeps working without a schema dance.
        await db.site_change_triggers_meta.update_one(
            {"_id": "watcher_heartbeat"},
            {"$set": {"last_run": summary["ts"], "last_summary": summary}},
            upsert=True,
        )
    except Exception:
        pass
    return summary


# ─────────────────────────────────────────────────────────────────────
# Pillars Map chip probe
# ─────────────────────────────────────────────────────────────────────
async def watcher_health(db) -> dict:
    """Green iff we can reach site_change_triggers. Surfaces last-run ts."""
    if db is None:
        return {"ok": False, "status": "red", "detail": "db unavailable"}
    try:
        await db.site_change_triggers.count_documents({}, limit=1)
    except Exception as e:
        return {"ok": False, "status": "red",
                "detail": f"site_change_triggers unreachable: {type(e).__name__}: {str(e)[:120]}"}

    last_run = None
    try:
        meta = await db.site_change_triggers_meta.find_one(
            {"_id": "watcher_heartbeat"}, projection={"_id": 0})
        if meta and meta.get("last_run"):
            last_run = meta["last_run"]
            if isinstance(last_run, datetime):
                last_run = last_run.isoformat()
    except Exception:
        pass

    detail = "site_change_triggers reachable"
    if last_run:
        detail += f" · last_run={last_run}"
    else:
        detail += " · never run yet (fires Saturdays 7 AM UTC)"
    return {"ok": True, "status": "green", "detail": detail,
            "last_run": last_run}


# ─────────────────────────────────────────────────────────────────────
# TTL init — called by services.website_diff.init_indexes_and_cleanup
# ─────────────────────────────────────────────────────────────────────
async def ensure_trigger_indexes(db) -> None:
    """TTL 30 days on site_change_triggers.ts. Safe to call repeatedly."""
    if db is None:
        return
    try:
        await db.site_change_triggers.create_index(
            [("ts", 1)],
            expireAfterSeconds=TRIGGER_RETENTION_SECONDS,
            name="ts_ttl_30d",
        )
        await db.site_change_triggers.create_index(
            [("lead_id", 1), ("ts", -1)], name="lead_ts",
        )
    except Exception as e:
        logger.debug(f"[site_watcher] trigger index skipped: {e}")
    # One-off belt-and-suspenders purge
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=TRIGGER_RETENTION_SECONDS)
        await db.site_change_triggers.delete_many({"ts": {"$lt": cutoff}})
    except Exception:
        pass


__all__ = [
    "run_weekly_site_watch",
    "run_daily_priority_watch",
    "run_weekly_site_watch_sync",
    "watcher_health",
    "ensure_trigger_indexes",
    "build_watcher_summary",
    "build_trigger_doc",
    "MAX_LEADS_PER_RUN",
    "MAX_PRIORITY_LEADS_PER_RUN",
    "TRIGGER_RETENTION_SECONDS",
]
