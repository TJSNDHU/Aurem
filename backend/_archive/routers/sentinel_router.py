"""
AUREM Sentinel — API Router + Background Loop
================================================
Starts the infinite self-healing loop as a background task.
Exposes dashboard API endpoints for the Sentinel admin tab.
"""

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Header
import jwt as pyjwt

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sentinel", tags=["Sentinel"])

# Global state
_sentinel_task: Optional[asyncio.Task] = None
_sentinel_running = False
_current_cycle = 0
_last_pulse = None


def _get_db():
    try:
        from server import db
        return db
    except Exception:
        return None


# ═══════════════════════════════════════
# INFINITE LOOP
# ═══════════════════════════════════════

async def sentinel_loop():
    """The infinite self-healing loop. Runs 24/7."""
    global _sentinel_running, _current_cycle, _last_pulse
    _sentinel_running = True

    from services.sentinel_observer import observe_all_systems
    from services.sentinel_diagnose import diagnose_issues
    from services.sentinel_healer import apply_auto_fixes
    from services.sentinel_verifier import verify_fixes

    logger.info("[Sentinel] Loop started — running 24/7")

    while _sentinel_running:
        _current_cycle += 1
        db = _get_db()

        try:
            # STAGE 1: OBSERVE
            pulse = await observe_all_systems(db, _current_cycle)
            _last_pulse = pulse
            issues = pulse.get("issues_found", [])

            diagnosed = []
            fix_results = []
            verified = []

            if issues:
                # STAGE 2: DIAGNOSE
                diagnosed = await diagnose_issues(db, issues)

                # STAGE 3: AUTO-FIX
                if diagnosed:
                    safe_fixes = [d for d in diagnosed if d.get("proposed_fix") not in ("manual", "human_required")]
                    if safe_fixes:
                        fix_results = await apply_auto_fixes(db, safe_fixes)

                        # STAGE 4: VERIFY (only for applied fixes)
                        applied = [f for f in fix_results if f.get("success")]
                        if applied:
                            async def recheck(svc):
                                from services.sentinel_observer import observe_all_systems as obs
                                p = await obs(db, _current_cycle)
                                svc_issues = [i for i in p.get("issues_found", []) if i.get("service") == svc]
                                return {"issues": svc_issues}
                            verified = await verify_fixes(db, applied, recheck)

            # Update dashboard state
            try:
                if db is not None:
                    await db.sentinel_dashboard.update_one(
                        {"_id": "current"},
                        {"$set": {
                            "cycle_number": _current_cycle,
                            "health_score": pulse.get("health_score", 0),
                            "issues_count": len(issues),
                            "fixes_applied": len([f for f in fix_results if f.get("success")]),
                            "last_check": datetime.now(timezone.utc).isoformat(),
                            "last_issue": issues[0] if issues else None,
                            "last_fix": fix_results[0] if fix_results else None,
                            "status": "active",
                        }},
                        upsert=True,
                    )
            except Exception as e:
                logger.warning(f"[Sentinel] Dashboard update failed: {e}")

            # Determine wait time (longer in prod to reduce noise)
            has_p0 = any(i.get("severity") == "P0" for i in issues)
            wait_time = 30 if has_p0 else 120

            # Self-repair: every 10th cycle, run AUREM's own repair pipeline
            if _current_cycle % 10 == 0:
                try:
                    from services.self_scan_automation import run_full_self_repair
                    self_result = await run_full_self_repair()
                    total = self_result.get("scan", {}).get("total_fixes", 0)
                    logger.info(f"[Sentinel] Self-repair cycle: {total} fixes processed")
                except Exception as e:
                    logger.warning(f"[Sentinel] Self-repair failed: {e}")

            logger.info(
                f"[Sentinel] Cycle {_current_cycle} done — "
                f"health: {pulse.get('health_score', 0)}/100, "
                f"issues: {len(issues)}, "
                f"fixes: {len(fix_results)}, "
                f"next check: {wait_time}s"
            )

        except Exception as e:
            logger.error(f"[Sentinel] Cycle {_current_cycle} error: {e}")
            wait_time = 30  # Back off on errors

        await asyncio.sleep(wait_time)


def start_sentinel():
    """Start the sentinel loop as a background task."""
    global _sentinel_task
    if _sentinel_task is None or _sentinel_task.done():
        _sentinel_task = asyncio.create_task(sentinel_loop())
        logger.info("[Sentinel] Background task started")


def stop_sentinel():
    """Stop the sentinel loop."""
    global _sentinel_running
    _sentinel_running = False
    logger.info("[Sentinel] Stop requested")


# ═══════════════════════════════════════
# DASHBOARD API ENDPOINTS
# ═══════════════════════════════════════

@router.get("/status")
@router.get("/health")
async def sentinel_status():
    """Current sentinel status for dashboard."""
    db = _get_db()
    dashboard = None
    if db is not None:
        dashboard = await db.sentinel_dashboard.find_one({"_id": "current"})

    # Get stats
    total_fixes = 0
    known_fixes_count = 0
    if db is not None:
        try:
            total_fixes = await db.auto_heal_log.count_documents({"check_name": {"$regex": "^sentinel_"}})
            known_fixes_count = await db.known_fixes.count_documents({})
        except Exception:
            pass

    return {
        "running": _sentinel_running,
        "cycle_number": _current_cycle,
        "health_score": dashboard.get("health_score", 0) if dashboard else 0,
        "issues_count": dashboard.get("issues_count", 0) if dashboard else 0,
        "last_check": dashboard.get("last_check") if dashboard else None,
        "last_issue": dashboard.get("last_issue") if dashboard else None,
        "last_fix": dashboard.get("last_fix") if dashboard else None,
        "total_auto_fixes": total_fixes,
        "known_fixes_count": known_fixes_count,
        "status": "active" if _sentinel_running else "stopped",
    }


@router.get("/pulse-history")
async def sentinel_pulse_history(limit: int = 50):
    """Recent system pulse history for charts."""
    db = _get_db()
    if db is None:
        return {"pulses": []}
    try:
        cursor = db.system_pulse.find(
            {}, {"_id": 0, "timestamp": 1, "cycle_number": 1, "health_score": 1, "issues_found": 1, "duration_ms": 1, "healthy_checks": 1, "total_checks": 1}
        ).sort("cycle_number", -1).limit(limit)
        pulses = await cursor.to_list(length=limit)
        return {"pulses": list(reversed(pulses))}
    except Exception as e:
        return {"pulses": [], "error": str(e)}


@router.get("/fixes-log")
async def sentinel_fixes_log(limit: int = 20):
    """Recent auto-fix log."""
    db = _get_db()
    if db is None:
        return {"fixes": []}
    try:
        cursor = db.auto_heal_log.find(
            {"check_name": {"$regex": "^sentinel_"}},
            {"_id": 0}
        ).sort("timestamp", -1).limit(limit)
        fixes = await cursor.to_list(length=limit)
        return {"fixes": fixes}
    except Exception as e:
        return {"fixes": [], "error": str(e)}


@router.get("/known-fixes")
async def sentinel_known_fixes():
    """Known fixes database."""
    db = _get_db()
    if db is None:
        return {"fixes": []}
    try:
        cursor = db.known_fixes.find({}, {"_id": 0}).sort("times_applied", -1).limit(50)
        fixes = await cursor.to_list(length=50)
        return {"fixes": fixes}
    except Exception as e:
        return {"fixes": [], "error": str(e)}


@router.get("/alerts")
async def sentinel_alerts(limit: int = 20):
    """Recent alerts (human-required and escalations)."""
    db = _get_db()
    if db is None:
        return {"alerts": []}
    try:
        cursor = db.sentinel_alerts.find({}, {"_id": 0}).sort("timestamp", -1).limit(limit)
        alerts = await cursor.to_list(length=limit)
        return {"alerts": alerts}
    except Exception as e:
        return {"alerts": [], "error": str(e)}


@router.post("/trigger-cycle")
@router.post("/scan")
async def trigger_manual_cycle():
    """Manually trigger a sentinel cycle (for testing)."""
    from services.sentinel_observer import observe_all_systems
    from services.sentinel_diagnose import diagnose_issues

    db = _get_db()
    pulse = await observe_all_systems(db, _current_cycle)
    issues = pulse.get("issues_found", [])
    diagnosed = await diagnose_issues(db, issues) if issues else []

    return {
        "cycle": _current_cycle,
        "health_score": pulse.get("health_score", 0),
        "issues_found": len(issues),
        "issues": issues,
        "diagnosed": len(diagnosed),
        "diagnoses": diagnosed[:5],
    }


@router.get("/search-stats")
async def sentinel_search_stats():
    """ScoutSearch health stats for dashboard."""
    try:
        from services.scout_search import get_search_stats
        return get_search_stats()
    except Exception as e:
        return {"error": str(e)}


@router.get("/model-routing")
async def sentinel_model_routing():
    """Current sovereign model routing configuration."""
    try:
        from services.openrouter_client import get_routing_table
        return get_routing_table()
    except Exception as e:
        return {"error": str(e)}


# ═══════════════════════════════════════════════════
# COST SAVINGS ENDPOINTS
# ═══════════════════════════════════════════════════

@router.get("/cost/today")
async def cost_savings_today():
    """Today's cost savings."""
    from services.cost_savings_tracker import get_today_savings
    return await get_today_savings()


@router.get("/cost/month")
async def cost_savings_month():
    """This month's cost savings."""
    from services.cost_savings_tracker import get_month_savings
    return await get_month_savings()


@router.get("/cost/alltime")
async def cost_savings_alltime():
    """All-time savings + model performance rankings."""
    from services.cost_savings_tracker import get_alltime_savings
    return await get_alltime_savings()


@router.get("/cost/chart")
async def cost_savings_chart(days: int = 7):
    """7-day free vs paid chart data."""
    from services.cost_savings_tracker import get_daily_chart
    return await get_daily_chart(days)


@router.get("/cost/alert-check")
async def cost_alert_check():
    """Check if paid usage exceeds 10% threshold."""
    from services.cost_savings_tracker import check_paid_alert_threshold
    alert = await check_paid_alert_threshold()
    return {"alert": alert, "threshold_exceeded": alert is not None}


@router.get("/cost/morning-brief")
async def cost_morning_brief():
    """Savings summary for morning brief."""
    from services.cost_savings_tracker import get_morning_brief_savings
    brief = await get_morning_brief_savings()
    return {"brief": brief}


@router.get("/git-backup")
async def get_git_backup_status():
    """Get GitHub auto-backup status for Sentinel dashboard."""
    from services.flow_coordinator import get_backup_status
    return await get_backup_status()
