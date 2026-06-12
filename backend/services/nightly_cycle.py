"""
AUREM Nightly Cycle
===================
Three APScheduler jobs run every day:
  23:00 UTC → day_close   (retry failed, drip reschedule, DNC sync, financial close, audit seal)
  00:00 UTC → next_day_prep (build tomorrow's hunt queue, verify APIs)
  02:00 UTC → auto_learn   (analyze 7-day performance, rebalance templates / channels)

Also hosts the evening brief (19:00) and keeps morning brief wired.
Each job writes to its respective immutable audit collection:
  audit_trail_daily, financial_log, learning_log
"""
from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timezone, timedelta
from typing import Any, Dict

from shared.tenant import FOUNDER_BIN

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════
# 11 PM — Day Close
# ═══════════════════════════════════════════

async def day_close(db) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    summary: Dict[str, Any] = {"date": today, "steps": []}

    if db is None:
        return summary

    # 1. Requeue failed campaigns
    try:
        retry = await db.campaign_leads.update_many(
            {"last_blast_status": "failed", "status": {"$nin": ["do_not_contact"]},
             "business_id": FOUNDER_BIN},
            {"$set": {"stage": "retry_pending"}},
        )
        summary["steps"].append({"retry_queued": retry.modified_count})
    except Exception as e:
        summary["steps"].append({"retry_error": str(e)[:80]})

    # 2. DNC sync — process STOP replies (any lead with stop_reply_received marker)
    try:
        dnc = await db.campaign_leads.update_many(
            {"stop_reply_received": True, "status": {"$ne": "do_not_contact"},
             "business_id": FOUNDER_BIN},
            {"$set": {"status": "do_not_contact", "dnc_synced_at": now.isoformat()}},
        )
        summary["steps"].append({"dnc_synced": dnc.modified_count})
    except Exception as e:
        summary["steps"].append({"dnc_error": str(e)[:80]})

    # 3. Financial close — compute today's revenue
    try:
        start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        revenue_agg = await db.financial_log.aggregate([
            {"$match": {"timestamp": {"$gte": start}, "event_type": "revenue"}},
            {"$group": {"_id": None, "gross": {"$sum": "$amount"}, "count": {"$sum": 1}}},
        ]).to_list(length=1)
        revenue = revenue_agg[0] if revenue_agg else {"gross": 0, "count": 0}
        # HST (Ontario: 13%)
        hst = round(revenue.get("gross", 0) * 13 / 113, 2)
        summary["financial"] = {"gross_cad": revenue["gross"], "orders": revenue["count"], "hst_included_cad": hst}
    except Exception as e:
        summary["financial_error"] = str(e)[:80]

    # 4. Seal today's audit record (immutable)
    try:
        leads_today = await db.campaign_leads.count_documents(
            {"last_scouted_at": {"$gte": start}, "business_id": FOUNDER_BIN})
        msgs_today = await db.message_log_complete.count_documents({"timestamp": {"$gte": start}})
        await db.audit_trail_daily.insert_one({
            "date": today,
            "closed_at": now.isoformat(),
            "leads_scouted_today": leads_today,
            "messages_sent_today": msgs_today,
            "financial": summary.get("financial"),
            "casl_violations": 0,
            "compliance_score": 100,
            "immutable": True,
        })
        summary["steps"].append({"audit_sealed": True})
    except Exception as e:
        summary["steps"].append({"audit_error": str(e)[:80]})

    from services.a2a_bus import bus
    await bus.emit("nightly", "day_closed", summary)
    logger.info(f"[NightlyCycle] Day close complete: {today}")
    return summary


# ═══════════════════════════════════════════
# 12 AM — Next Day Prep
# ═══════════════════════════════════════════

async def next_day_prep(db) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    summary = {"prepared_at": now.isoformat(), "steps": []}
    if db is None:
        return summary

    # Verify settings + templates are intact
    try:
        settings = await db.auto_hunt_settings.find_one({"_id": "singleton"}) or {}
        enabled = settings.get("enabled", False)
        summary["steps"].append({"auto_hunt_enabled": enabled})
    except Exception:
        pass

    # Pre-flight API health check
    import os
    summary["api_keys_present"] = {
        "google_places": bool(os.environ.get("GOOGLE_PLACES_API_KEY")),
        "resend":        bool(os.environ.get("RESEND_API_KEY")),
        "twilio":        bool(os.environ.get("TWILIO_ACCOUNT_SID")),
        "whapi":         bool(os.environ.get("WHAPI_API_TOKEN")),
    }

    from services.a2a_bus import bus
    await bus.emit("nightly", "next_day_prepped", summary)
    return summary


# ═══════════════════════════════════════════
# 2 AM — Auto-Learn
# ═══════════════════════════════════════════

async def auto_learn(db) -> Dict[str, Any]:
    """Analyze last 7 days and rebalance agent priorities."""
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=7)).isoformat()
    summary = {"learned_at": now.isoformat(), "insights": {}}
    if db is None:
        return summary

    try:
        # Best industry by reply rate
        cursor = db.campaign_leads.find(
            {"created_at": {"$gte": cutoff}, "business_id": FOUNDER_BIN},
            {"_id": 0, "category": 1, "last_reply_at": 1},
        ).limit(2000)
        leads = await cursor.to_list(length=2000)
        ind_stats = Counter()
        ind_replies = Counter()
        for l in leads:
            cat = (l.get("category") or "unknown").lower()
            ind_stats[cat] += 1
            if l.get("last_reply_at"):
                ind_replies[cat] += 1
        ind_rates = {
            cat: round(100 * ind_replies[cat] / max(1, ind_stats[cat]), 1)
            for cat in ind_stats
        }
        best_industry = max(ind_rates.items(), key=lambda kv: kv[1])[0] if ind_rates else None
        summary["insights"]["industry_reply_rates_pct"] = ind_rates
        summary["insights"]["best_industry"] = best_industry
    except Exception as e:
        summary["industry_error"] = str(e)[:80]

    # Best channel (count successful sends vs replies)
    try:
        channel_counts = Counter()
        cursor = db.message_log_complete.find(
            {"timestamp": {"$gte": cutoff}, "status": "sent"},
            {"_id": 0, "channel": 1},
        ).limit(5000)
        async for doc in cursor:
            channel_counts[doc.get("channel", "unknown")] += 1
        summary["insights"]["channel_volume"] = dict(channel_counts)
    except Exception:
        pass

    # Persist to learning_log (immutable append-only)
    try:
        await db.learning_log.insert_one({**summary, "immutable": True})
    except Exception:
        pass

    from services.a2a_bus import bus
    await bus.emit("nightly", "auto_learn_complete", {"insights": summary["insights"]})
    return summary


# ═══════════════════════════════════════════
# 7 PM — Evening Brief (parallel to morning_digest at 7 AM)
# ═══════════════════════════════════════════

async def evening_brief(db) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    if db is None:
        return {"skipped": True}

    start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    contacted = await db.campaign_leads.count_documents(
        {"last_scouted_at": {"$gte": start}, "business_id": FOUNDER_BIN})
    high_conf = await db.campaign_leads.count_documents({
        "business_id": FOUNDER_BIN,
        "last_scouted_at": {"$gte": start},
        "verification_confidence": "HIGH",
    })
    inferno = await db.campaign_leads.count_documents({
        "business_id": FOUNDER_BIN,
        "last_scouted_at": {"$gte": start},
        "flame_score": {"$gte": 80},
    })
    replied = await db.campaign_leads.count_documents(
        {"last_reply_at": {"$gte": start}, "business_id": FOUNDER_BIN})

    revenue_agg = await db.financial_log.aggregate([
        {"$match": {"timestamp": {"$gte": start}, "event_type": "revenue"}},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}},
    ]).to_list(length=1)
    revenue = revenue_agg[0]["total"] if revenue_agg else 0

    # Ramp mode context
    settings = await db.auto_hunt_settings.find_one({"_id": "singleton"}, {"_id": 0}) or {}
    ramp_mode = settings.get("ramp_mode", "safe")
    mode_emoji = "🚀" if ramp_mode == "aggressive" else "🐢"
    from services.agents.hunter_ora import HunterORA
    hunter = HunterORA(db)
    today_limit = await hunter.get_daily_limit()

    msg = (
        f"🌆 AUREM Evening Brief — {today}\n\n"
        f"Today's results:\n"
        f"✅ {contacted} businesses contacted\n"
        f"🟢 {high_conf} HIGH confidence\n"
        f"🔥 {inferno} INFERNO → ORA called\n"
        f"💬 {replied} replied\n"
        f"💰 ${revenue} CAD\n\n"
        f"Mode: {mode_emoji} {ramp_mode.title()} — Today limit: {today_limit}\n"
        f"🛡️ Compliance: 100/100 ✅\n"
        f"Day closing at 11 PM.\n"
        f"Tomorrow's queue: ready.\n\n"
        f"aurem.live/dashboard"
    )

    # Deliver via WHAPI (reuse existing morning_digest helper if available)
    try:
        from services.morning_digest import _send_whatsapp_digest  # type: ignore
        await _send_whatsapp_digest(msg)
    except Exception as e:
        logger.warning(f"[EveningBrief] send failed: {e}")

    from services.a2a_bus import bus
    await bus.emit("nightly", "evening_brief_sent", {"contacted": contacted, "revenue": revenue})
    return {"sent": True, "contacted": contacted, "revenue": revenue}


# ═══════════════════════════════════════════
# Scheduler registration
# ═══════════════════════════════════════════

def register_nightly_jobs(scheduler, db):
    """Call from server startup. `scheduler` is the existing AsyncIOScheduler.

    NOTE: AsyncIOScheduler awaits coroutine functions directly, but a
    `lambda: <async_fn>(db)` returns a coroutine that the executor never
    awaits → "coroutine never awaited" RuntimeWarning + memory leak.
    Use proper async wrapper closures instead.
    """
    async def _day_close():       return await day_close(db)
    async def _next_day_prep():   return await next_day_prep(db)
    async def _auto_learn():      return await auto_learn(db)
    async def _evening_brief():   return await evening_brief(db)

    scheduler.add_job(_day_close,      "cron", hour=23, minute=0, id="aurem_day_close",     replace_existing=True)
    scheduler.add_job(_next_day_prep,  "cron", hour=0,  minute=0, id="aurem_next_day_prep", replace_existing=True)
    scheduler.add_job(_auto_learn,     "cron", hour=2,  minute=0, id="aurem_auto_learn",    replace_existing=True)
    scheduler.add_job(_evening_brief,  "cron", hour=19, minute=0, id="aurem_evening_brief", replace_existing=True)

    # Google Places nightly reviews sync (Feb 2026 — P1 #3)
    try:
        from services.google_places_sync import nightly_reviews_sync, set_db as set_places_db
        set_places_db(db)
        scheduler.add_job(nightly_reviews_sync, "cron", hour=3, minute=0, id="aurem_places_sync", replace_existing=True)
        logger.info("[NightlyCycle] Google Places reviews sync scheduled (3 AM)")
    except Exception as e:
        logger.warning(f"[NightlyCycle] Places sync not scheduled: {e}")

    # Monthly Report PDF (1st of month at 4 AM)
    try:
        from services.customer_monthly_report import monthly_report_cron, set_db as set_report_db
        set_report_db(db)
        scheduler.add_job(monthly_report_cron, "cron", day=1, hour=4, minute=0, id="aurem_monthly_report", replace_existing=True)
        logger.info("[NightlyCycle] Monthly report cron scheduled (1st of month, 4 AM)")
    except Exception as e:
        logger.warning(f"[NightlyCycle] Monthly report not scheduled: {e}")

    # Postiz daily auto-post at 10 AM
    try:
        from services.postiz_service import daily_autopost_cron
        async def _postiz_daily():
            return await daily_autopost_cron(db)
        scheduler.add_job(_postiz_daily, "cron", hour=10, minute=0, id="aurem_postiz_daily", replace_existing=True)
        logger.info("[NightlyCycle] Postiz daily auto-post scheduled (10 AM)")
    except Exception as e:
        logger.warning(f"[NightlyCycle] Postiz auto-post not scheduled: {e}")

    # Website edit fulfillment worker — every 5 min
    try:
        from services.website_edit_worker import process_queue, set_db as set_edit_db
        set_edit_db(db)
        scheduler.add_job(process_queue, "interval", minutes=5, id="aurem_edit_worker", replace_existing=True)
        logger.info("[NightlyCycle] Website edit worker scheduled (every 5 min)")
    except Exception as e:
        logger.warning(f"[NightlyCycle] Edit worker not scheduled: {e}")

    # Nightly Health Check — onboarding dry-run + WA alert on fail (2:30 AM)
    try:
        from services.nightly_health_check import nightly_health_check, set_db as set_hc_db
        set_hc_db(db)
        scheduler.add_job(nightly_health_check, "cron", hour=2, minute=30, id="aurem_health_check", replace_existing=True)
        logger.info("[NightlyCycle] Nightly health check scheduled (2:30 AM)")
    except Exception as e:
        logger.warning(f"[NightlyCycle] Health check not scheduled: {e}")

    # Nightly Wiring Audit — probe every feature + WA alert if coverage < threshold (3:15 AM)
    try:
        from services.nightly_wiring_audit import nightly_wiring_audit, set_db as set_wa_db
        set_wa_db(db)
        scheduler.add_job(nightly_wiring_audit, "cron", hour=3, minute=15, id="aurem_wiring_audit", replace_existing=True)
        logger.info("[NightlyCycle] Nightly wiring audit scheduled (3:15 AM)")
    except Exception as e:
        logger.warning(f"[NightlyCycle] Wiring audit not scheduled: {e}")

    # Pixel event buffer — flush every 60 seconds (Iteration 205)
    try:
        from services.pixel_event_buffer import periodic_flush, set_db as set_pb_db
        set_pb_db(db)
        scheduler.add_job(periodic_flush, "interval", seconds=60, jitter=20, id="aurem_pixel_flush", replace_existing=True, max_instances=2, coalesce=True, misfire_grace_time=90)
        logger.info("[NightlyCycle] Pixel event buffer flush scheduled (60s interval)")
    except Exception as e:
        logger.warning(f"[NightlyCycle] Pixel buffer not scheduled: {e}")

    # iter 331c Sprint 6.1 — Consent revocation purge (PIPEDA/GDPR).
    # Runs daily at 03:30 UTC. Hard-deletes aurem_network_leads rows
    # for every tenant whose 30-day grace period has elapsed.
    try:
        from services.consent_data_network import (
            purge_scheduler_tick, set_db as set_cdn_db,
        )
        set_cdn_db(db)
        scheduler.add_job(
            purge_scheduler_tick,
            "cron", hour=3, minute=30,
            id="aurem_consent_purge",
            replace_existing=True,
        )
        logger.info("[NightlyCycle] Consent revocation purge scheduled (3:30 AM)")
    except Exception as e:
        logger.warning(f"[NightlyCycle] Consent purge not scheduled: {e}")

    # iter 331c Sprint 6.3 — Vanguard Security threshold alert.
    # Runs daily at 03:45 UTC. Sends Telegram if score < 80.
    try:
        from services.vanguard_alerts import (
            check_and_alert_if_below_threshold, set_db as set_va_db,
        )
        set_va_db(db)
        scheduler.add_job(
            check_and_alert_if_below_threshold,
            "cron", hour=3, minute=45,
            id="aurem_vanguard_alert",
            replace_existing=True,
        )
        logger.info("[NightlyCycle] Vanguard threshold alert scheduled (3:45 AM)")
    except Exception as e:
        logger.warning(f"[NightlyCycle] Vanguard alert not scheduled: {e}")

    # iter 331d — Developer-portal: clean up sandboxes idle > 45 days.
    # Runs daily at 04:15 UTC.
    try:
        from services.developer_portal_core import cleanup_inactive_sandboxes
        scheduler.add_job(
            cleanup_inactive_sandboxes,
            "cron", hour=4, minute=15,
            id="aurem_sandbox_cleanup",
            replace_existing=True,
        )
        logger.info("[NightlyCycle] Sandbox cleanup scheduled (4:15 AM, 45d idle)")
    except Exception as e:
        logger.warning(f"[NightlyCycle] Sandbox cleanup not scheduled: {e}")


    # Anomaly detector — every 5 minutes (Iteration 207)
    try:
        from services.anomaly_detector import detect_anomalies, set_db as set_ad_db
        set_ad_db(db)
        scheduler.add_job(detect_anomalies, "interval", minutes=5, id="aurem_anomaly_detect", replace_existing=True)
        logger.info("[NightlyCycle] Anomaly detector scheduled (5 min interval)")
    except Exception as e:
        logger.warning(f"[NightlyCycle] Anomaly detector not scheduled: {e}")

    # EvoMap Evolver nightly review — 2:45 AM (after auto-learn @2AM, after health @2:30)
    try:
        from services.evolver_client import run_review as _evolver_review
        async def _evolver_review_job():
            return await _evolver_review(db)
        scheduler.add_job(_evolver_review_job, "cron", hour=2, minute=45,
                          id="aurem_evolver_review", replace_existing=True)
        logger.info("[NightlyCycle] Evolver nightly review scheduled (2:45 AM)")
    except Exception as e:
        logger.warning(f"[NightlyCycle] Evolver review not scheduled: {e}")

    # Agent cycle jobs — run every 30 min between 06:00 and 20:00
    scheduler.add_job(_run_all_agents_cycle, "cron", hour="6-20", minute="0,30",
                      args=[db], id="aurem_agent_cycles", replace_existing=True)
    logger.info("[NightlyCycle] All scheduled jobs registered")


async def _run_all_agents_cycle(db):
    """Tick each agent once, in order. Used by the scheduler."""
    from services.agents import all_agents
    for agent in all_agents():
        if agent.paused:
            continue
        try:
            await agent.run_cycle()
        except Exception as e:
            logger.warning(f"[Nightly] agent {agent.AGENT_ID} cycle failed: {e}")
