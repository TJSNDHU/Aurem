"""
Customer Repair Pipeline — Phase 2
===================================
Maps failed health checks to known fixes, gates unsafe fixes through
Council deliberation, applies safe fixes immediately, then re-verifies.

Design rules:
- Safe + confidence ≥ 0.90 → auto-apply
- Otherwise → council.deliberate(required=qa+security, advisory=pricing)
- Unknown failure pattern → ORA alert only (no destructive guesses)
- Every fix is logged to customer_repair_log + emits A2A events
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


KNOWN_FIXES: Dict[str, Dict[str, Any]] = {
    "db_billing": {
        "description": "aurem_billing record missing",
        "fix": "seed_billing_record",
        "confidence": 0.95,
        "safe": True,
    },
    "db_workspace": {
        "description": "aurem_workspaces record missing",
        "fix": "create_workspace",
        "confidence": 0.95,
        "safe": True,
    },
    "db_onboarding": {
        "description": "aurem_onboarding record missing",
        "fix": "init_onboarding",
        "confidence": 0.95,
        "safe": True,
    },
    "stripe_seeded": {
        "description": "Stripe customer not created",
        "fix": "create_stripe_customer",
        "confidence": 0.90,
        "safe": True,
    },
    "jwt_works": {
        "description": "JWT generation broken",
        "fix": "reset_auth_tokens",
        "confidence": 0.70,
        "safe": False,  # invalidates active sessions → council
    },
    "route_my": {
        "description": "/my route returning 5xx",
        "fix": "diagnose_frontend_route",
        "confidence": 0.60,
        "safe": False,
    },
    "route_onboarding": {
        "description": "/api/onboarding/status returning 5xx",
        "fix": "diagnose_frontend_route",
        "confidence": 0.60,
        "safe": False,
    },
    "route_billing": {
        "description": "/api/aurem-billing/status returning 5xx",
        "fix": "diagnose_frontend_route",
        "confidence": 0.60,
        "safe": False,
    },
    "route_bin": {
        "description": "/api/business-id/mine returning 5xx",
        "fix": "diagnose_frontend_route",
        "confidence": 0.60,
        "safe": False,
    },
    "db_tenant": {
        "description": "tenant_customers record missing",
        "fix": "seed_tenant_record",
        "confidence": 0.95,
        "safe": True,
    },
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _get_db():
    try:
        import server
        return getattr(server, "db", None)
    except Exception:
        return None


async def _ora_alert(message: str) -> None:
    """Best-effort founder alert via Twilio SMS + A2A bus."""
    try:
        from services.a2a_bus import bus
        await bus.emit("customer_repair", "CUSTOMER_REPAIR_ALERT",
                       {"message": message, "ts": _utc_now().isoformat()})
    except Exception:
        pass

    phone = (os.environ.get("ADMIN_ALERT_PHONE")
             or os.environ.get("FOUNDER_PHONE") or "").strip()
    if not phone:
        return
    try:
        from services.fallback_monitor import _send_sms_alert
        await _send_sms_alert(phone, f"[AUREM] {message[:150]}")
    except Exception as e:
        logger.debug(f"[customer-repair] alert SMS failed: {e}")


async def _log_repair(business_id: str, fix: Dict[str, Any], outcome: str,
                      extra: Dict[str, Any] = None) -> None:
    db = _get_db()
    if db is None:
        return
    try:
        await db.customer_repair_log.insert_one({
            "business_id": business_id,
            "fix_name": fix.get("fix"),
            "description": fix.get("description"),
            "confidence": fix.get("confidence"),
            "safe": fix.get("safe"),
            "outcome": outcome,
            "extra": extra or {},
            "ts": _utc_now(),
        })
    except Exception as e:
        logger.debug(f"[customer-repair] log insert failed: {e}")


async def trigger_repair_pipeline(
    business_id: str,
    checks: Dict[str, bool],
    status: str,
) -> Dict[str, Any]:
    """Diagnose → council vote (if needed) → apply → verify."""
    failed = [k for k, v in checks.items() if not v]
    fixes_needed: List[Dict[str, Any]] = [
        {**KNOWN_FIXES[f], "key": f} for f in failed if f in KNOWN_FIXES
    ]

    if not fixes_needed:
        await _ora_alert(
            f"⚠️ {business_id} {status} — unknown cause: {failed[:5]}"
        )
        await _log_repair(business_id, {"fix": "unknown"}, "unknown_pattern",
                          {"failed": failed})
        return {"business_id": business_id, "outcome": "unknown_pattern",
                "failed": failed}

    applied: List[str] = []
    rejected: List[str] = []
    for fix in fixes_needed:
        if fix["safe"] and fix["confidence"] >= 0.90:
            ok = await _apply_safe(business_id, fix)
            if ok:
                applied.append(fix["fix"])
                await _log_repair(business_id, fix, "auto_applied")
            else:
                await _log_repair(business_id, fix, "auto_apply_failed")
            continue

        # Unsafe → council deliberate
        try:
            from services.council_deliberate import deliberate
            verdict = await deliberate(
                action="customer_repair",
                agent="customer_repair_pipeline",
                payload={
                    "business_id": business_id,
                    "fix": fix["fix"],
                    "description": fix["description"],
                    "confidence": fix["confidence"],
                },
                required=["qa", "security"],
                advisory=["pricing"],
            )
        except Exception as e:
            logger.warning(f"[customer-repair] council failed: {e}")
            verdict = {"verdict": "REJECTED", "votes": {}, "confidence": 0.0}

        if verdict.get("verdict") == "APPROVED":
            ok = await _apply_safe(business_id, fix)
            if ok:
                applied.append(fix["fix"])
                await _log_repair(business_id, fix, "council_approved",
                                  {"votes": verdict.get("votes")})
            else:
                await _log_repair(business_id, fix, "council_apply_failed",
                                  {"votes": verdict.get("votes")})
        else:
            rejected.append(fix["fix"])
            await _log_repair(business_id, fix, "council_rejected",
                              {"votes": verdict.get("votes")})
            await _ora_alert(
                f"🔴 {business_id}: {fix['description']} — Council rejected. "
                "Manual fix needed."
            )

    # ─── VERIFY ─────────────────────────────────────────────
    await asyncio.sleep(5)
    try:
        from services.customer_health_monitor import check_tenant
        new_summary = await check_tenant(business_id)
        new_status = new_summary.get("status", "unknown")
        still_failing = new_summary.get("failed", [])
    except Exception as e:
        logger.warning(f"[customer-repair] verify failed: {e}")
        new_status, still_failing = "unknown", failed

    if new_status == "healthy":
        try:
            from services.a2a_bus import bus
            await bus.emit("customer_repair", "CUSTOMER_HEALED", {
                "business_id": business_id,
                "fixes_applied": applied,
            })
        except Exception:
            pass
        await _log_repair(business_id, {"fix": "all"}, "verified_fixed",
                          {"applied": applied})
    else:
        await _ora_alert(
            f"🚨 {business_id} still {new_status} after auto-fix: "
            f"{still_failing[:5]}"
        )
        try:
            from services.a2a_bus import bus
            await bus.emit("customer_repair", "CODE_FIX_NEEDED", {
                "business_id": business_id,
                "still_failing": still_failing,
                "applied": applied,
                "rejected": rejected,
            })
        except Exception:
            pass

    return {
        "business_id": business_id,
        "applied": applied,
        "rejected": rejected,
        "post_status": new_status,
        "still_failing": still_failing,
    }


async def _apply_safe(business_id: str, fix: Dict[str, Any]) -> bool:
    """Wrapper around customer_fix_executors with crash isolation."""
    try:
        from services.customer_fix_executors import apply_customer_fix
        return await apply_customer_fix(business_id, fix["fix"])
    except Exception as e:
        logger.warning(
            f"[customer-repair] apply {fix.get('fix')} for {business_id} crashed: {e}"
        )
        return False
