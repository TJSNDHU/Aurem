"""
Payment Funnel Audit (iter 315e)
=================================
Nightly watchdog that catches silent payment failures and abandoned
checkouts in the repair funnel.

Core logic:
  1. Pull every db.repair_orders row with status='pending_payment'
     and a `stripe_session_id` set (only Stripe-flow orders, skip stubs).
  2. For each, retrieve the Stripe Checkout Session live.
  3. If Stripe says paid but DB still pending → SILENT PAYMENT:
       · auto-fix status='paid' + paid_at + payment_intent
       · fire _kick_repair_build(order)
       · WhatsApp alert TJ at FOUNDER_PHONE
  4. If DB says pending and Stripe still un-paid AND order ≥48h old →
     ABANDONED CHECKOUT:
       · WhatsApp alert (one-shot via abandoned_alerted_at flag)
  5. Persist a daily summary in db.payment_audits.

Public:
  await run_payment_audit(db) -> dict
  await payment_audit_scheduler() -> never returns (midnight America/Toronto)
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

ABANDONED_AGE_HOURS = int(os.environ.get("PAYMENT_AUDIT_ABANDONED_HOURS", "48"))
MAX_ORDERS_PER_RUN = int(os.environ.get("PAYMENT_AUDIT_MAX_ORDERS", "200"))
ALERT_PHONE = os.environ.get("FOUNDER_PHONE", "+16134000000")


def _stripe_key() -> str:
    """Mirror stripe_payment_router._get_stripe_key() (placeholder-safe)."""
    sec = os.environ.get("STRIPE_SECRET_KEY") or ""
    api = os.environ.get("STRIPE_API_KEY") or ""
    if sec:
        return sec
    if api and len(api) >= 30 and api.startswith(("sk_live_", "sk_test_")):
        return api
    return api or sec


async def _wa_alert(body: str) -> bool:
    try:
        from routers.whatsapp_alerts import send_whatsapp
        out = await send_whatsapp(ALERT_PHONE, body)
        return bool(out and out.get("ok"))
    except Exception as e:
        logger.debug(f"[payment-audit] wa alert failed: {e}")
        return False


def _fmt_cad(cents: int) -> str:
    return f"${(cents or 0) / 100:.2f} CAD"


async def _fix_silent_payment(db, order: Dict[str, Any],
                                  sess_obj: Dict[str, Any]) -> Dict[str, Any]:
    """Mark order paid + queue AWB build (mirrors stripe_payment_router)."""
    paid_at = datetime.now(timezone.utc).isoformat()
    pi = sess_obj.get("payment_intent")
    if hasattr(pi, "id"):
        pi = pi.id
    await db.repair_orders.update_one(
        {"order_id": order["order_id"]},
        {"$set": {
            "status": "paid", "paid_at": paid_at,
            "stripe_payment_intent": pi,
            "audit_recovered_at": paid_at,
            "audit_recovery_source": "payment_funnel_audit",
        }},
    )
    try:
        from routers.repair_checkout_router import _kick_repair_build
        asyncio.create_task(_kick_repair_build(order))
    except Exception as e:
        logger.warning(f"[payment-audit] build kick failed: {e}")
    # Outcome attribution mirror
    try:
        from services.attribution import attribute_lead_outcome
        if order.get("lead_id"):
            asyncio.create_task(attribute_lead_outcome(
                db, order["lead_id"], "paid",
                revenue_cad=float(order.get("amount_cad", 0)) / 100.0,
                source_hint="payment_audit",
                extra={"order_id": order["order_id"],
                        "tier": order.get("tier")},
            ))
    except Exception:
        pass

    biz = ""
    try:
        if order.get("lead_id"):
            lead = await db.campaign_leads.find_one(
                {"lead_id": order["lead_id"]},
                {"_id": 0, "business_name": 1}) or {}
            biz = lead.get("business_name") or ""
    except Exception:
        pass

    body = (
        f"🚨 Silent payment found!\n"
        f"Order {order['order_id']} · {_fmt_cad(order.get('amount_cad', 0))}\n"
        f"{biz} · tier={order.get('tier')}\n"
        f"Auto-fixed + build triggered."
    )
    wa_ok = await _wa_alert(body)
    return {"order_id": order["order_id"], "amount_cad": order.get("amount_cad"),
            "wa_ok": wa_ok, "biz": biz}


async def _flag_abandoned(db, order: Dict[str, Any]) -> Dict[str, Any]:
    if order.get("abandoned_alerted_at"):
        return {"order_id": order["order_id"], "skipped": "already_flagged"}
    biz = ""
    try:
        if order.get("lead_id"):
            lead = await db.campaign_leads.find_one(
                {"lead_id": order["lead_id"]},
                {"_id": 0, "business_name": 1}) or {}
            biz = lead.get("business_name") or ""
    except Exception:
        pass
    age_h = 0.0
    try:
        age_h = (datetime.now(timezone.utc)
                  - datetime.fromisoformat(order["created_at"])
                  ).total_seconds() / 3600.0
    except Exception:
        pass
    body = (
        f"⚠️ Abandoned checkout: {order['order_id']}\n"
        f"Lead: {biz or order.get('lead_id') or '?'}\n"
        f"Tier: {order.get('tier')} · {_fmt_cad(order.get('amount_cad', 0))}\n"
        f"Pending {age_h:.0f}h. Consider manual follow-up."
    )
    wa_ok = await _wa_alert(body)
    await db.repair_orders.update_one(
        {"order_id": order["order_id"]},
        {"$set": {
            "abandoned_alerted_at": datetime.now(timezone.utc).isoformat(),
            "abandoned_age_hours": round(age_h, 1),
        }},
    )
    return {"order_id": order["order_id"], "wa_ok": wa_ok,
            "biz": biz, "age_hours": round(age_h, 1)}


async def run_payment_audit(db) -> Dict[str, Any]:
    """One full audit pass. Safe to invoke on-demand or via scheduler."""
    started_at = datetime.now(timezone.utc)
    api_key = _stripe_key()
    if not api_key or len(api_key) < 30:
        logger.warning("[payment-audit] no usable Stripe key — skipping")
        return {"ok": False, "error": "no_stripe_key"}

    try:
        import stripe
        stripe.api_key = api_key
    except Exception as e:
        logger.warning(f"[payment-audit] stripe import failed: {e}")
        return {"ok": False, "error": "stripe_import_failed"}

    cur = db.repair_orders.find(
        {"status": "pending_payment",
          "stripe_session_id": {"$nin": [None, ""], "$exists": True}},
        {"_id": 0},
    ).sort("created_at", -1).limit(MAX_ORDERS_PER_RUN)
    orders: List[Dict[str, Any]] = await cur.to_list(MAX_ORDERS_PER_RUN)

    silent_recovered: List[Dict[str, Any]] = []
    abandoned: List[Dict[str, Any]] = []
    still_open: int = 0
    stripe_errors: List[Dict[str, Any]] = []
    cutoff = (started_at - timedelta(hours=ABANDONED_AGE_HOURS)).isoformat()

    for order in orders:
        sid = order.get("stripe_session_id")
        sess_obj: Optional[Dict[str, Any]] = None
        try:
            sess = stripe.checkout.Session.retrieve(sid)
            sess_obj = sess if isinstance(sess, dict) else dict(sess)
        except Exception as e:
            stripe_errors.append({"order_id": order["order_id"],
                                    "err": f"{type(e).__name__}: {e}"[:160]})
            # Don't `continue` — fall through to abandoned check below.
            # A fake/expired session id on a 48h+ pending order is the
            # classic abandoned-checkout pattern.

        pay_status = (sess_obj or {}).get("payment_status") or ""
        if pay_status == "paid":
            try:
                rec = await _fix_silent_payment(db, order, sess_obj)
                silent_recovered.append(rec)
            except Exception as e:
                logger.warning(
                    f"[payment-audit] fix failed {order['order_id']}: {e}")
                stripe_errors.append({"order_id": order["order_id"],
                                        "err": f"fix:{e}"[:160]})
            continue

        # Still pending — abandoned threshold check
        created = order.get("created_at", "")
        if created and created <= cutoff:
            try:
                rec = await _flag_abandoned(db, order)
                abandoned.append(rec)
            except Exception as e:
                logger.warning(
                    f"[payment-audit] abandon flag failed "
                    f"{order['order_id']}: {e}")
        else:
            still_open += 1

    summary = {
        "audit_id": __import__("uuid").uuid4().hex[:12],
        "started_at": started_at.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "scanned": len(orders),
        "silent_recovered": silent_recovered,
        "silent_recovered_count": len(silent_recovered),
        "abandoned": abandoned,
        "abandoned_count": len(abandoned),
        "still_open": still_open,
        "stripe_errors": stripe_errors,
        "stripe_error_count": len(stripe_errors),
    }
    try:
        await db.payment_audits.insert_one(dict(summary))
    except Exception as e:
        logger.warning(f"[payment-audit] persist failed: {e}")

    logger.info(
        f"[payment-audit] scanned={summary['scanned']} "
        f"silent_recovered={summary['silent_recovered_count']} "
        f"abandoned={summary['abandoned_count']} "
        f"still_open={still_open} errors={summary['stripe_error_count']}"
    )
    return {"ok": True, **summary}


async def payment_audit_scheduler() -> None:
    """Run nightly at 00:00 America/Toronto."""
    try:
        import pytz
        tz = pytz.timezone("America/Toronto")
    except Exception:
        tz = timezone.utc

    await asyncio.sleep(60)
    while True:
        try:
            now = datetime.now(tz)
            target = now.replace(hour=0, minute=0, second=0, microsecond=0)
            if now >= target:
                target += timedelta(days=1)
            wait = (target - now).total_seconds()
            logger.info(
                f"[payment-audit] next run {target} (in {wait/3600:.1f}h)")
            await asyncio.sleep(wait)
            try:
                import server
                db = getattr(server, "db", None)
            except Exception:
                db = None
            if db is None:
                logger.warning("[payment-audit] db unavailable, skipping")
                await asyncio.sleep(3600)
                continue
            await run_payment_audit(db)
        except Exception as e:
            logger.warning(f"[payment-audit] scheduler tick failed: {e}")
            await asyncio.sleep(3600)
