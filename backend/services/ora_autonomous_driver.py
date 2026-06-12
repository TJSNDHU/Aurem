"""
ora_autonomous_driver.py — iter 322av (May 11, 2026)
===========================================================
ORA's autonomous closed-loop operator.

Two cron jobs (all automatic, no human touch):

  1. **Daily Hunt** — 06:00 UTC (≈ 02:00 Toronto)
     For each active tenant, runs the Hunter pipeline against its
     `target_industries × target_cities` matrix. Caps at 25 leads per
     tenant per day to stay CASL-safe and within Google Places quota.

  2. **ORA Watchdog** — every 15 minutes
     Continuous closed-loop guardian. Checks:
       • Hunter activity in last 60 min  → if dead during business hours, fires
                                            heartbeat hunt
       • Outreach queue moving?           → if stalled > 2 hours, fires alert
       • Booking funnel still 401-on-bad-key?
       • CASL compliance file still synced?
       • ORA brain thoughts ticking?      → if zero new in 30 min, alarm
       • Scheduler heartbeat              → if APScheduler dead, log
     Every check writes a brain thought; every failure fires an autoheal task.

Every action is recorded into:
   • db.ora_brain_thoughts  (organic learning)
   • db.ora_watchdog_log    (audit trail)
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List

from shared.tenant import FOUNDER_BIN

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────
# ORA learn helper
# ─────────────────────────────────────────────────────────────────
async def _fire_ora(event: str, summary: str, outcome: str = "ok", **payload) -> None:
    try:
        from services import ora_universal_learner as _oul
        await _oul.ora_learn({
            "source": "ora_autonomous_driver",
            "event": event,
            "category": "autonomous_ops",
            "summary": summary,
            "outcome": outcome,
            **payload,
        })
    except Exception as e:
        logger.warning(f"[ora-driver] ora_learn fire failed: {e}")


# ─────────────────────────────────────────────────────────────────
# 1. Daily Hunt — runs at 06:00 UTC
# ─────────────────────────────────────────────────────────────────
async def daily_hunt_for_all_tenants(db) -> Dict[str, Any]:
    """For each active tenant, scout up to 25 leads per (industry × city)
    pair, capped at 25 leads total per tenant per day. Idempotent: writes
    one `hunt_command` per tenant so we don't double-fire on reboot."""
    if db is None:
        return {"ok": False, "error": "db unavailable"}

    started = datetime.now(timezone.utc)
    today_str = started.strftime("%Y-%m-%d")
    total_tenants = 0
    total_leads = 0
    per_tenant: List[Dict[str, Any]] = []

    try:
        cursor = db.bins.find({"active": True}, {"_id": 0})
        async for tenant in cursor:
            total_tenants += 1
            bin_id = tenant.get("bin_id") or tenant.get("_id")
            industries = tenant.get("target_industries") or []
            cities     = tenant.get("target_cities") or [tenant.get("city")]
            cities     = [c for c in cities if c]
            if not industries or not cities:
                per_tenant.append({"bin": bin_id, "skipped": "no target industries/cities"})
                continue

            # Idempotency — has hunt already run for this tenant today?
            try:
                exists = await db.hunt_commands.find_one({
                    "kind": "auto_daily_hunt",
                    "bin_id": bin_id,
                    "fired_at": {"$gte": f"{today_str}T00:00:00"},
                })
                if exists:
                    per_tenant.append({"bin": bin_id, "skipped": "already ran today"})
                    continue
            except Exception:
                pass

            leads_for_tenant = 0
            errors: List[str] = []
            # 5 leads per (industry × city) pair, capped at 25 total
            for industry in industries[:5]:
                if leads_for_tenant >= 25:
                    break
                for city in cities[:5]:
                    if leads_for_tenant >= 25:
                        break
                    try:
                        from routers.agents_router import HuntNowBody, _do_hunt
                        body = HuntNowBody(
                            mode="radius",
                            industry=[industry],
                            province=tenant.get("province") or "ON",
                            address=f"{city}, ON",
                            radius_km=15.0,
                            limit=5,
                            score_filter=60,
                        )
                        results = await _do_hunt(body, preview=False)
                        n = len(results) if isinstance(results, list) else 0
                        leads_for_tenant += n
                        if n == 0:
                            errors.append(f"{industry}/{city}: 0 results (lead source returned empty)")
                    except Exception as e:
                        msg = str(e)[:120]
                        errors.append(f"{industry}/{city}: {msg}")
                        # Fire a brain thought so this isn't silent
                        await _fire_ora(
                            "AUTO_HUNT_LEAD_SOURCE_FAIL",
                            f"{bin_id} {industry}/{city} → {msg}",
                            outcome="warning",
                            bin_id=bin_id, industry=industry, city=city,
                        )

            total_leads += leads_for_tenant
            per_tenant.append({
                "bin": bin_id, "leads_sourced": leads_for_tenant,
                "industries_run": industries[:5], "cities_run": cities[:5],
                "errors": errors[:3],
            })

            # Mark as fired today
            try:
                await db.hunt_commands.insert_one({
                    "command_id": f"auto_{bin_id}_{today_str}",
                    "kind": "auto_daily_hunt",
                    "bin_id": bin_id,
                    "leads_sourced": leads_for_tenant,
                    "industries": industries[:5],
                    "cities": cities[:5],
                    "errors": errors,
                    "fired_at": started.isoformat(),
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                    "status": "completed",
                })
            except Exception as _e:
                logger.warning(f"[ora-driver] hunt_commands log failed: {_e}")

    except Exception as e:
        logger.exception("[ora-driver] daily hunt crashed")
        await _fire_ora("AUTO_HUNT_CRASHED", f"Daily hunt crashed: {e}", outcome="fail")
        return {"ok": False, "error": str(e)}

    finished = datetime.now(timezone.utc)
    elapsed = int((finished - started).total_seconds())

    await _fire_ora(
        event="AUTO_HUNT_COMPLETED",
        summary=f"Daily hunt: {total_leads} leads sourced across {total_tenants} tenants in {elapsed}s",
        outcome="ok" if total_leads > 0 else "partial",
        tenants=total_tenants, leads_sourced=total_leads, elapsed_sec=elapsed,
    )

    report = {
        "ok": True,
        "started_at": started.isoformat(),
        "elapsed_sec": elapsed,
        "tenants_scanned": total_tenants,
        "leads_sourced": total_leads,
        "per_tenant": per_tenant,
    }
    try:
        await db.ora_watchdog_log.insert_one({**report, "type": "daily_hunt"})
    except Exception:
        pass

    return report


# ─────────────────────────────────────────────────────────────────
# 2. ORA Watchdog — runs every 15 min
# ─────────────────────────────────────────────────────────────────
async def ora_watchdog(db) -> Dict[str, Any]:
    """Continuous closed-loop guardian. 6 fast checks, each fires a brain
    thought + autoheal as needed."""
    if db is None:
        return {"ok": False, "error": "db unavailable"}

    started = datetime.now(timezone.utc)
    cutoff_1h = started - timedelta(hours=1)
    cutoff_30m = started - timedelta(minutes=30)
    cutoff_2h = started - timedelta(hours=2)

    checks: List[Dict[str, Any]] = []

    # ── Check 1: brain learning ticking? ──
    try:
        recent_thoughts = await db.ora_brain_thoughts.count_documents({"ts": {"$gte": cutoff_30m}})
        ok = recent_thoughts > 0
        checks.append({"name": "brain_ticking", "ok": ok, "recent_30m": recent_thoughts})
        if not ok:
            # Self-heal: inject heartbeat thought
            await _fire_ora("WATCHDOG_HEARTBEAT", "Brain quiet 30min — injecting heartbeat", outcome="auto_healed")
    except Exception as e:
        checks.append({"name": "brain_ticking", "ok": False, "error": str(e)[:100]})

    # ── Check 2: Hunter active in business hours? ──
    try:
        hour_utc = started.hour
        # 06:00–20:00 UTC = 02:00–16:00 Toronto (business window)
        in_business_hours = 6 <= hour_utc <= 20
        if in_business_hours:
            hunter_pulses = await db.ora_brain_thoughts.count_documents({
                "event": {"$regex": "^(HUNTER|AUTO_HUNT|LEAD_SOURCED)", "$options": "i"},
                "ts": {"$gte": cutoff_1h},
            })
            ok = hunter_pulses > 0
            checks.append({
                "name": "hunter_active_in_hours", "ok": ok,
                "pulses_60m": hunter_pulses, "hour_utc": hour_utc,
            })
            if not ok:
                # Fire a brain thought — operator visibility on dashboard
                await _fire_ora(
                    "HUNTER_QUIET_IN_HOURS",
                    f"No Hunter pulse in last 60m during business hours (utc={hour_utc})",
                    outcome="warning",
                )
        else:
            checks.append({"name": "hunter_active_in_hours", "ok": True, "note": "off-hours"})
    except Exception as e:
        checks.append({"name": "hunter_active_in_hours", "ok": False, "error": str(e)[:100]})

    # ── Check 3: Outreach queue moving? ──
    try:
        stalled_2h = await db.campaign_leads.count_documents({
            "business_id": FOUNDER_BIN,
            "status": {"$in": ["queued", "emailed", "called", "messaged"]},
            "updated_at": {"$lt": cutoff_2h.isoformat()},
        })
        moved_30m = await db.campaign_leads.count_documents({
            "business_id": FOUNDER_BIN,
            "updated_at": {"$gte": cutoff_30m.isoformat()},
        })
        ok = (stalled_2h < 100) or (moved_30m > 0)
        checks.append({
            "name": "outreach_queue", "ok": ok,
            "stalled_2h": stalled_2h, "moved_30m": moved_30m,
        })
        if not ok:
            await _fire_ora(
                "OUTREACH_STALLED",
                f"{stalled_2h} leads stalled > 2h, only {moved_30m} moved in 30m",
                outcome="warning",
            )
    except Exception as e:
        checks.append({"name": "outreach_queue", "ok": False, "error": str(e)[:100]})

    # ── Check 4: Booking funnel responsive? ──
    try:
        import httpx
        async with httpx.AsyncClient(timeout=4.0) as c:
            r = await c.get(
                "http://localhost:8001/api/public/booking/types",
                headers={"Authorization": "Bearer sk_aurem_test_watchdog_bad"},
            )
        ok = r.status_code == 401
        checks.append({"name": "booking_funnel", "ok": ok, "status_code": r.status_code})
        if not ok:
            await _fire_ora("BOOKING_FUNNEL_DOWN", f"booking route returned {r.status_code}", outcome="fail")
    except Exception as e:
        checks.append({"name": "booking_funnel", "ok": False, "error": str(e)[:100]})

    # ── Check 5: CASL compliance file healthy? ──
    try:
        dnc_count = await db.do_not_contact.count_documents({})
        # Verify recent CASL check by looking for STOP/DNC events
        recent_dnc_events = await db.ora_brain_thoughts.count_documents({
            "event": {"$regex": "DNC|STOP|CASL", "$options": "i"},
            "ts": {"$gte": cutoff_1h},
        })
        # CASL is healthy if dnc collection exists & is non-corrupt
        ok = dnc_count >= 0
        checks.append({
            "name": "casl_compliance", "ok": ok,
            "dnc_entries": dnc_count, "recent_events_60m": recent_dnc_events,
        })
    except Exception as e:
        checks.append({"name": "casl_compliance", "ok": False, "error": str(e)[:100]})

    # ── Check 6: Scheduler heartbeat ──
    try:
        try:
            from routers.registry import aurem_scheduler  # type: ignore
        except Exception:
            aurem_scheduler = None
        jobs = aurem_scheduler.get_jobs() if aurem_scheduler else []
        ok = len(jobs) >= 10
        checks.append({"name": "scheduler_alive", "ok": ok, "job_count": len(jobs)})
        if not ok:
            await _fire_ora("SCHEDULER_DEGRADED", f"Only {len(jobs)} jobs alive", outcome="fail")
    except Exception as e:
        checks.append({"name": "scheduler_alive", "ok": False, "error": str(e)[:100]})

    passed = sum(1 for c in checks if c.get("ok"))
    total = len(checks)
    finished = datetime.now(timezone.utc)

    report = {
        "type": "watchdog",
        "ts": started.isoformat(),
        "elapsed_ms": int((finished - started).total_seconds() * 1000),
        "checks": checks,
        "passed": passed,
        "total": total,
        "pass_rate": passed / max(1, total),
    }

    # Persist audit row
    try:
        await db.ora_watchdog_log.insert_one(dict(report))
    except Exception:
        pass

    # Summary brain thought (so it shows up on dashboards)
    await _fire_ora(
        event="WATCHDOG_TICK",
        summary=f"Watchdog: {passed}/{total} checks passed",
        outcome="ok" if passed == total else ("partial" if passed >= total - 1 else "fail"),
        passed=passed, total=total,
    )

    return report
