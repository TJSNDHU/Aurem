"""
Nightly Health Check — Iteration 202
=====================================
Runs the onboarding-test chain in dry-run mode every night.
If ANY step fails, sends a WhatsApp alert to the admin.

Registered in nightly_cycle.register_nightly_jobs() at 02:30 AM.

Reads admin phone from `ADMIN_ALERT_PHONE` or falls back to the primary admin.
"""
from __future__ import annotations

import os
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_db = None


def set_db(db):
    global _db
    _db = db


async def _run_dry_onboarding(db) -> Dict[str, Any]:
    """Invoke the same flow as POST /api/admin/onboarding-test with dry_run=True."""
    import services.whapi_service as _whapi
    import services.twilio_service as _twilio
    orig_whapi = getattr(_whapi, "send_whatsapp_message", None)
    orig_twilio = getattr(_twilio, "send_sms", None)

    async def _noop(phone, message, *a, **kw):
        return {"success": True, "dry_run": True, "would_send_to": phone}

    if orig_whapi:
        _whapi.send_whatsapp_message = _noop
    if orig_twilio:
        _twilio.send_sms = _noop

    try:
        from services.aurem_post_payment_onboarding import run_post_payment_flow
        summary = await run_post_payment_flow(
            db=db,
            tenant_id="healthcheck-nightly",
            customer_email="healthcheck@aurem.live",
            plan="starter",
            amount=97.0,
            lead_ref="",
        )
        steps = summary.get("steps", {})
        checklist = [
            {"step": "tenant_created",          "ok": bool((steps.get("onboarding_record") or {}).get("created"))},
            {"step": "google_scan_queued",      "ok": bool(steps.get("google_scan_queued"))},
            {"step": "website_draft_queued",    "ok": bool(steps.get("website_draft_queued"))},
            {"step": "welcome_whatsapp_called", "ok": (steps.get("welcome_whatsapp") or {}).get("sent") is not None},
            {"step": "admin_alert_called",      "ok": (steps.get("admin_alert") or {}).get("sent") is not None},
        ]
        overall = "PASS" if all(c["ok"] for c in checklist) else "PARTIAL"
        return {"overall": overall, "checklist": checklist}
    except Exception as e:
        logger.exception("[HealthCheck] dry onboarding failed")
        return {"overall": "FAIL", "error": str(e), "checklist": []}
    finally:
        if orig_whapi:
            _whapi.send_whatsapp_message = orig_whapi
        if orig_twilio:
            _twilio.send_sms = orig_twilio


async def _admin_phone(db) -> Optional[str]:
    """Return first admin phone for alert, env override wins."""
    ph = (os.environ.get("ADMIN_ALERT_PHONE") or "").strip()
    if ph:
        return ph
    try:
        u = await db.platform_users.find_one(
            {"role": "admin", "phone": {"$exists": True, "$ne": ""}},
            {"_id": 0, "phone": 1},
        )
        if u and u.get("phone"):
            return u["phone"]
    except Exception:
        pass
    return None


async def nightly_health_check() -> Dict[str, Any]:
    """Top-level scheduler entry. Runs onboarding dry-run + WA alert on failure."""
    if _db is None:
        logger.warning("[HealthCheck] db not set — skipping")
        return {"skipped": True}

    now = datetime.now(timezone.utc).isoformat()
    result = await _run_dry_onboarding(_db)
    result["ran_at"] = now

    # Persist history (keep small TTL-like window via bounded retention)
    try:
        await _db.aurem_health_checks.insert_one({**result, "created_at": now})
        await _db.aurem_health_checks.delete_many(
            {"created_at": {"$lt": datetime.now(timezone.utc).replace(microsecond=0).isoformat()[:10]}}
        )
    except Exception as e:
        logger.debug(f"[HealthCheck] persist failed: {e}")

    # Alert on failure
    if result.get("overall") != "PASS":
        phone = await _admin_phone(_db)
        if phone:
            failed = [c["step"] for c in result.get("checklist", []) if not c.get("ok")]
            try:
                from routers.whatsapp_alerts import send_whatsapp
                await send_whatsapp(
                    phone,
                    "🚨 AUREM Nightly Health Check FAILED\n\n"
                    f"Status: {result.get('overall')}\n"
                    f"Failed: {', '.join(failed) or 'unknown'}\n\n"
                    f"Ran at: {now[:19]}Z\n"
                    f"Dashboard: https://aurem.live/admin/system-audit",
                )
                result["alerted"] = phone
            except Exception as e:
                logger.warning(f"[HealthCheck] alert failed: {e}")

    logger.info(f"[HealthCheck] overall={result.get('overall')} alerted={result.get('alerted', False)}")
    return result
