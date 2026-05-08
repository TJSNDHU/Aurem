"""
Anomaly Detector — Iteration 207
=================================
Runs every 5 minutes on the scheduler. Compares current platform state to
the previous baseline snapshot. Fires a WhatsApp alert when ANY of:

  • cache hit rate dropped by ≥ 20 absolute percentage points
  • pixel buffer flush_failures > 0 (any new failures since last check)
  • system verdict transitioned from healthy → degraded/critical

Throttling: each anomaly type has a 60-minute cooldown so we never spam.
State persisted in `aurem_anomaly_state` collection.

Every alert also logs to `aurem_anomaly_log` for the Control Center history.
"""
from __future__ import annotations

import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

CACHE_DROP_THRESHOLD_PP = 20        # percentage points
ALERT_COOLDOWN_MIN = 60             # one alert per anomaly type per hour
_STATE_KEY = "aurem_anomaly_state"   # single-doc collection

_db = None


def set_db(db):
    global _db
    _db = db


async def _admin_phone() -> Optional[str]:
    ph = (os.environ.get("ADMIN_ALERT_PHONE") or "").strip()
    if ph:
        return ph
    if _db is None:
        return None
    try:
        u = await _db.platform_users.find_one(
            {"role": "admin", "phone": {"$exists": True, "$ne": ""}},
            {"_id": 0, "phone": 1},
        )
        return (u or {}).get("phone")
    except Exception:
        return None


async def _load_state() -> Dict[str, Any]:
    if _db is None:
        return {}
    doc = await _db.aurem_anomaly_state.find_one({"_key": _STATE_KEY}, {"_id": 0}) or {}
    return doc


async def _save_state(state: Dict[str, Any]) -> None:
    if _db is None:
        return
    try:
        state["_key"] = _STATE_KEY
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        await _db.aurem_anomaly_state.update_one(
            {"_key": _STATE_KEY}, {"$set": state}, upsert=True,
        )
    except Exception as e:
        logger.debug(f"[Anomaly] state save failed: {e}")


async def _log_alert(kind: str, detail: Dict[str, Any]) -> None:
    if _db is None:
        return
    try:
        await _db.aurem_anomaly_log.insert_one({
            "kind": kind,
            "detail": detail,
            "fired_at": datetime.now(timezone.utc).isoformat(),
            "ttl_at": datetime.now(timezone.utc),   # picks up 30-day TTL if index exists
        })
    except Exception as e:
        logger.debug(f"[Anomaly] alert log failed: {e}")


def _cooldown_elapsed(last_iso: Optional[str]) -> bool:
    if not last_iso:
        return True
    try:
        last = datetime.fromisoformat(last_iso.replace("Z", "+00:00"))
        return datetime.now(timezone.utc) - last > timedelta(minutes=ALERT_COOLDOWN_MIN)
    except Exception:
        return True


async def _send_wa(phone: str, msg: str) -> bool:
    try:
        from routers.whatsapp_alerts import send_whatsapp
        await send_whatsapp(phone, msg)
        return True
    except Exception as e:
        logger.warning(f"[Anomaly] WA send failed: {e}")
        return False


async def detect_anomalies() -> Dict[str, Any]:
    """Main entrypoint — called by scheduler every 5 minutes."""
    if _db is None:
        return {"skipped": True, "reason": "no_db"}

    # Fetch current stats internally (avoid HTTP round-trip)
    try:
        from services.aurem_cache import get_stats as cache_get_stats
        from services.pixel_event_buffer import get_stats as pixel_get_stats
    except Exception:
        return {"skipped": True, "reason": "services_unavailable"}

    cache_stats = cache_get_stats()
    pixel_stats = pixel_get_stats()

    # Fetch system verdict via the existing system_audit logic
    try:
        from routers.system_audit_router import _env_status, REQUIRED_INTEGRATIONS
        required = _env_status(REQUIRED_INTEGRATIONS)
        missing_required = [r["name"] for r in required if not r["present"]]
        # Re-derive verdict same way as the audit endpoint
        red_flags = []
        if missing_required:
            red_flags.append(f"Missing required secrets: {', '.join(missing_required)}")
        verdict = "healthy" if not red_flags else "degraded" if len(red_flags) < 3 else "critical"
    except Exception:
        verdict = "unknown"
        red_flags = []

    current = {
        "cache_hit_rate_pct": cache_stats.get("hit_rate_pct", 0.0),
        "cache_total_lookups": cache_stats.get("total_lookups", 0),
        "pixel_flush_failures": pixel_stats.get("flush_failures", 0),
        "verdict": verdict,
        "red_flags_count": len(red_flags),
    }

    state = await _load_state()
    baseline = state.get("baseline", {})
    last_alerts = state.get("last_alerts", {})

    phone = await _admin_phone()
    fired: Dict[str, Any] = {}
    now_iso = datetime.now(timezone.utc).isoformat()

    # ── 1. Cache hit-rate drop ─────────────────────────
    base_hit = baseline.get("cache_hit_rate_pct")
    cur_hit = current["cache_hit_rate_pct"]
    # Only alert once we have a meaningful sample size on both sides
    if (
        base_hit is not None
        and baseline.get("cache_total_lookups", 0) >= 20
        and current["cache_total_lookups"] >= 20
        and (base_hit - cur_hit) >= CACHE_DROP_THRESHOLD_PP
        and _cooldown_elapsed(last_alerts.get("cache_drop"))
    ):
        detail = {"baseline_pct": base_hit, "current_pct": cur_hit, "drop_pp": round(base_hit - cur_hit, 1)}
        if phone:
            await _send_wa(
                phone,
                f"⚠️ AUREM Anomaly — Cache hit rate dropped\n\n"
                f"Baseline: {base_hit}% → Now: {cur_hit}% (−{detail['drop_pp']} pp)\n"
                f"Check Redis: /admin/control-center",
            )
        await _log_alert("cache_drop", detail)
        fired["cache_drop"] = detail
        last_alerts["cache_drop"] = now_iso

    # ── 2. Pixel buffer flush failures ─────────────────
    base_fail = baseline.get("pixel_flush_failures", 0)
    cur_fail = current["pixel_flush_failures"]
    new_failures = cur_fail - base_fail
    if new_failures > 0 and _cooldown_elapsed(last_alerts.get("pixel_fail")):
        detail = {"new_failures": new_failures, "total_failures": cur_fail}
        if phone:
            await _send_wa(
                phone,
                f"🚨 AUREM Anomaly — Pixel buffer flush failures\n\n"
                f"+{new_failures} new flush failures (total: {cur_fail})\n"
                f"Check: /admin/control-center → Pixel Event Buffer",
            )
        await _log_alert("pixel_fail", detail)
        fired["pixel_fail"] = detail
        last_alerts["pixel_fail"] = now_iso

    # ── 3. System verdict transition ───────────────────
    prev_verdict = baseline.get("verdict")
    if (
        prev_verdict == "healthy"
        and current["verdict"] in ("degraded", "critical")
        and _cooldown_elapsed(last_alerts.get("verdict_drop"))
    ):
        detail = {"from": prev_verdict, "to": current["verdict"], "red_flags_count": current["red_flags_count"]}
        if phone:
            await _send_wa(
                phone,
                f"🚨 AUREM Anomaly — System verdict degraded\n\n"
                f"healthy → {current['verdict'].upper()} "
                f"({current['red_flags_count']} red flags)\n"
                f"Audit: /admin/system-audit",
            )
        await _log_alert("verdict_drop", detail)
        fired["verdict_drop"] = detail
        last_alerts["verdict_drop"] = now_iso

    # Always update baseline to current (rolling window)
    await _save_state({
        "baseline": current,
        "last_alerts": last_alerts,
        "last_run_at": now_iso,
    })

    result = {
        "ran_at": now_iso,
        "current": current,
        "fired": fired,
        "cooldown_min": ALERT_COOLDOWN_MIN,
        "threshold_pp": CACHE_DROP_THRESHOLD_PP,
    }
    if fired:
        logger.info(f"[Anomaly] fired={list(fired.keys())}")
    return result
