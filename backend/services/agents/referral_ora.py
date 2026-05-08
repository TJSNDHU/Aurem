"""
AUREM Referral ORA — Phase 1 (T1 Pipeline)
============================================
Subscribes to SUBSCRIPTION_CREATED — schedules a Day 7 referral nudge SMS.
Fires daily tick that processes due referrals.

Public:
  await arm(payload)
  await tick()
  register_subscriptions()
  referral_tick_scheduler()
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

REFERRAL_DELAY_DAYS = 7


def _get_db():
    try:
        import server
        return getattr(server, "db", None)
    except Exception:
        return None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ─────────────────────────────────────────────────────────────────────
# arm — runs on SUBSCRIPTION_CREATED
# ─────────────────────────────────────────────────────────────────────

async def arm(payload: Dict[str, Any]) -> Dict[str, Any]:
    db = _get_db()
    if db is None:
        return {"ok": False, "error": "db unavailable"}

    try:
        from services.agent_registry import heartbeat, log_action
        await heartbeat("referral")
    except Exception:
        log_action = None

    customer_id = (payload.get("customer_id") or payload.get("user_id")
                   or payload.get("email") or "").strip()
    if not customer_id:
        return {"ok": False, "error": "customer_id missing"}

    # Idempotent — one referral per customer
    existing = await db.scheduled_referrals.find_one(
        {"customer_id": customer_id}, {"_id": 0})
    if existing:
        return {"ok": True, "already_scheduled": True}

    scheduled_for = _utc_now() + timedelta(days=REFERRAL_DELAY_DAYS)
    await db.scheduled_referrals.insert_one({
        "customer_id": customer_id,
        "email": payload.get("email", ""),
        "phone": payload.get("phone", ""),
        "business_name": payload.get("business_name", ""),
        "scheduled_for": scheduled_for,
        "armed_at": _utc_now(),
        "status": "pending",
    })

    if log_action:
        await log_action("referral", "REFERRAL_SCHEDULED",
                         f"Day {REFERRAL_DELAY_DAYS} armed",
                         metadata={"customer_id": customer_id})
    return {"ok": True, "scheduled_for": scheduled_for.isoformat()}


# ─────────────────────────────────────────────────────────────────────
# tick — fires due referrals
# ─────────────────────────────────────────────────────────────────────

REFERRAL_SMS = (
    "Hey {name} — TJ from AUREM. You're a week in — hope your AI "
    "agents are pulling weight! 🔥 Quick ask: know any other Canadian "
    "trades who'd benefit? Send them my way → https://aurem.live/refer "
    "and you both get $50 off. (Reply STOP to opt out.)"
)


async def tick() -> Dict[str, Any]:
    db = _get_db()
    if db is None:
        return {"ok": False, "error": "db unavailable"}

    try:
        from services.agent_registry import heartbeat, log_action
        await heartbeat("referral")
    except Exception:
        log_action = None

    now = _utc_now()
    cur = db.scheduled_referrals.find(
        {"scheduled_for": {"$lte": now}, "status": "pending"},
        {"_id": 1, "customer_id": 1, "phone": 1,
         "business_name": 1, "email": 1},
    ).limit(50)
    rows: List[Dict[str, Any]] = await cur.to_list(50)
    if not rows:
        return {"ok": True, "checked": 0, "sent": 0}

    sent = 0
    try:
        from services.a2a_bus import bus
    except Exception:
        bus = None

    for row in rows:
        phone = (row.get("phone") or "").strip()
        if not phone:
            await db.scheduled_referrals.update_one(
                {"_id": row["_id"]},
                {"$set": {"status": "skipped_no_phone", "checked_at": now}},
            )
            continue
        # Council gate
        try:
            from services.council_deliberate import deliberate
            verdict = await deliberate(
                "referral_sms", "referral",
                {"phone_e164": phone, "email": row.get("email", ""),
                 "blast_sms_body": REFERRAL_SMS[:160]},
                required=["casl", "qa"], advisory=[],
            )
        except Exception as e:
            verdict = {"verdict": "APPROVED",
                       "_council_error": str(e)}
        if verdict.get("verdict") == "REJECTED":
            await db.scheduled_referrals.update_one(
                {"_id": row["_id"]},
                {"$set": {"status": "rejected", "checked_at": now,
                          "votes": verdict.get("votes")}},
            )
            continue

        # Fire SMS via twilio_service
        body = REFERRAL_SMS.format(
            name=(row.get("business_name") or "there").split()[0]
        )
        ok = False
        try:
            from services.twilio_service import send_sms
            res = await send_sms(phone, body)
            ok = bool(res and res.get("ok", True))
        except Exception as e:
            logger.warning(f"[referral] sms send failed for {phone}: {e}")

        await db.scheduled_referrals.update_one(
            {"_id": row["_id"]},
            {"$set": {"status": "sent" if ok else "failed",
                      "sent_at": now}},
        )
        if ok:
            sent += 1
            if bus is not None:
                try:
                    await bus.emit("referral", "REFERRAL_SENT", {
                        "customer_id": row["customer_id"],
                        "phone": phone,
                    })
                except Exception:
                    pass

    if log_action and sent:
        await log_action("referral", "REFERRAL_TICK",
                         f"checked={len(rows)} sent={sent}")
    return {"ok": True, "checked": len(rows), "sent": sent}


# ─────────────────────────────────────────────────────────────────────
# Subscription + scheduler
# ─────────────────────────────────────────────────────────────────────

def register_subscriptions() -> None:
    from services.a2a_bus import bus
    bus.subscribe("SUBSCRIPTION_CREATED", arm)
    logger.info("[referral] subscribed to SUBSCRIPTION_CREATED")


async def referral_tick_scheduler():
    """Forever loop — every 1 hour, fire due referrals."""
    print("[referral] tick scheduler alive — 90s grace", flush=True)
    await asyncio.sleep(90)
    while True:
        try:
            res = await tick()
            if (res.get("sent") or 0) > 0:
                print(f"[referral] tick: {res}", flush=True)
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"[referral] tick error: {e}", exc_info=True)
            await asyncio.sleep(300)
