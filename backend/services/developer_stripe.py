"""
services/developer_stripe.py — iter 331g Batch C

Stripe Checkout integration for the AUREM CTO developer portal.

Three packages, all one-time payment for simplicity (subscription
recurrence is out of scope this iter — Pro buys 30 days of unlimited):

  starter  $9   → +10,000 tokens on the developer account
  builder  $39  → +50,000 tokens
  pro      $99  → 30 days of subscription_status="paid"
                  (existing token-wall logic already unlocks unlimited
                   for paid status; BYOK calls bypass deductions)

Persisted state:
  - developer_accounts.stripe_customer_id (added on first checkout)
  - developer_accounts.subscription_status / .subscription_paid_until
  - payment_transactions (one row per checkout, idempotent on session_id)
  - stripe_events_processed (webhook idempotency, one row per event.id)

Library: `emergentintegrations.payments.stripe.checkout` (per the
integration playbook). The library wraps the Stripe SDK and returns
typed `CheckoutSessionResponse` / `CheckoutStatusResponse` objects.

Idempotency contract:
  - credit_for_session(session_id) refuses to credit twice for the
    same session, even when called from BOTH the polling status route
    AND the webhook handler.
  - process_webhook_event(event) refuses to process the same event.id
    twice.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

# ── Packages (fixed amounts; NEVER trust the frontend) ──────────────
PACKAGES: dict[str, dict[str, Any]] = {
    "starter": {
        "label":         "Starter",
        "amount_usd":    9.0,
        "currency":      "usd",
        "kind":          "tokens",
        "tokens_grant":  10_000,
    },
    "builder": {
        "label":         "Builder",
        "amount_usd":    39.0,
        "currency":      "usd",
        "kind":          "tokens",
        "tokens_grant":  50_000,
    },
    "pro": {
        "label":         "Pro",
        "amount_usd":    99.0,
        "currency":      "usd",
        "kind":          "subscription",
        "days_paid":     30,
    },
}


_db = None
_stripe_client = None


def set_db(database) -> None:
    global _db
    _db = database


def _get_client(host_url: str | None = None):
    """Lazy-load StripeCheckout. host_url is the request origin used by
    the library to build webhook URLs."""
    global _stripe_client
    if _stripe_client is not None:
        return _stripe_client
    try:
        from emergentintegrations.payments.stripe.checkout import StripeCheckout
    except ImportError:
        logger.error("[dev-stripe] emergentintegrations.payments.stripe not installed")
        return None
    api_key = os.environ.get("STRIPE_SECRET_KEY") or os.environ.get("STRIPE_API_KEY")
    if not api_key:
        logger.error("[dev-stripe] STRIPE_SECRET_KEY not set")
        return None
    webhook_url = (
        (os.environ.get("FRONTEND_URL") or os.environ.get("REACT_APP_BACKEND_URL")
         or "https://aurem.live").rstrip("/") + "/api/webhook/stripe"
    )
    _stripe_client = StripeCheckout(api_key=api_key, webhook_url=webhook_url)
    return _stripe_client


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def package_table() -> list[dict[str, Any]]:
    """Public-safe view of the packages — used by the /tokens page."""
    out = []
    for tier, p in PACKAGES.items():
        out.append({
            "id":          tier,
            "label":       p["label"],
            "amount_usd":  p["amount_usd"],
            "kind":        p["kind"],
            "tokens_grant": p.get("tokens_grant"),
            "days_paid":   p.get("days_paid"),
        })
    return out


async def start_checkout(*, user_id: str, email: str, tier: str,
                          origin_url: str) -> dict[str, Any]:
    """Create a Stripe Checkout Session for the requested tier.

    Returns `{ok, url, session_id}` on success, or `{ok: False, error}`.
    The amount is determined SERVER-SIDE from the PACKAGES dict.
    """
    if _db is None:
        return {"ok": False, "error": "db not ready"}
    if tier not in PACKAGES:
        return {"ok": False, "error": "unknown_package"}
    pkg = PACKAGES[tier]
    client = _get_client()
    if client is None:
        return {"ok": False, "error": "stripe_unavailable"}

    origin = (origin_url or "").rstrip("/") or "https://aurem.live"
    success_url = f"{origin}/developers/tokens?success=1&session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url  = f"{origin}/developers/tokens?cancelled=1"

    from emergentintegrations.payments.stripe.checkout import CheckoutSessionRequest

    req = CheckoutSessionRequest(
        amount=float(pkg["amount_usd"]),
        currency=pkg["currency"],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={
            "user_id":     user_id,
            "tier":        tier,
            "package_kind": pkg["kind"],
            "email":       email or "",
        },
    )
    try:
        session = await client.create_checkout_session(req)
    except Exception as e:
        logger.exception("[dev-stripe] create_checkout_session failed")
        return {"ok": False, "error": str(e)[:120]}

    # Persist a pending payment_transactions row BEFORE redirecting.
    try:
        await _db.payment_transactions.insert_one({
            "session_id":   session.session_id,
            "user_id":      user_id,
            "email":        email,
            "tier":         tier,
            "amount_usd":   float(pkg["amount_usd"]),
            "currency":     pkg["currency"],
            "payment_status": "pending",
            "credited":     False,
            "metadata": {
                "user_id":      user_id,
                "tier":         tier,
                "package_kind": pkg["kind"],
            },
            "created_at":   _now_iso(),
            "updated_at":   _now_iso(),
        })
    except Exception as e:
        logger.warning(f"[dev-stripe] could not persist pending row: {e}")

    return {"ok": True, "url": session.url, "session_id": session.session_id}


async def get_status(session_id: str) -> dict[str, Any]:
    """Poll Stripe for current session status. Idempotently credits the
    developer's account once `payment_status == 'paid'`. Safe to call
    repeatedly from the frontend success page."""
    if _db is None:
        return {"ok": False, "error": "db not ready"}
    client = _get_client()
    if client is None:
        return {"ok": False, "error": "stripe_unavailable"}
    try:
        status = await client.get_checkout_status(session_id)
    except Exception as e:
        logger.exception("[dev-stripe] get_checkout_status failed")
        return {"ok": False, "error": str(e)[:120]}

    # Update local row with the latest status
    await _db.payment_transactions.update_one(
        {"session_id": session_id},
        {"$set": {
            "payment_status": status.payment_status,
            "status_value":   status.status,
            "amount_total":   status.amount_total,
            "updated_at":     _now_iso(),
        }},
    )

    credited = False
    grant_info: dict[str, Any] = {}
    if status.payment_status == "paid":
        c = await credit_for_session(session_id)
        credited = c.get("credited", False)
        grant_info = c

    return {
        "ok":             True,
        "session_id":     session_id,
        "payment_status": status.payment_status,
        "status":         status.status,
        "amount_total":   status.amount_total,
        "currency":       status.currency,
        "credited":       credited,
        **{k: v for k, v in grant_info.items() if k != "ok"},
    }


async def credit_for_session(session_id: str) -> dict[str, Any]:
    """Idempotently grant tokens or paid days based on the session's
    package_kind. Uses Mongo `findAndModify`-style atomic update so
    concurrent calls (webhook + poll race) only credit once.
    """
    if _db is None:
        return {"ok": False, "error": "db not ready", "credited": False}
    # Atomic flip of credited: pending → True. Only the winner gets the
    # filter match and proceeds to grant.
    row = await _db.payment_transactions.find_one_and_update(
        {"session_id": session_id, "credited": {"$ne": True},
         "payment_status": "paid"},
        {"$set": {"credited": True, "credited_at": _now_iso()}},
        return_document=True,
        projection={"_id": 0},
    )
    if not row:
        # Either already credited or not yet paid
        existing = await _db.payment_transactions.find_one(
            {"session_id": session_id}, {"_id": 0},
        )
        return {
            "ok": True,
            "credited": False,
            "reason": "already_credited" if existing and existing.get("credited")
                       else "not_paid_yet",
        }

    tier = row["tier"]
    pkg = PACKAGES.get(tier) or {}
    user_id = row["user_id"]

    if pkg.get("kind") == "tokens":
        grant = int(pkg.get("tokens_grant") or 0)
        await _db.developer_accounts.update_one(
            {"user_id": user_id},
            {"$inc": {"tokens_remaining": grant}},
        )
        result = {"ok": True, "credited": True, "kind": "tokens",
                  "tokens_granted": grant, "tier": tier}
    elif pkg.get("kind") == "subscription":
        days = int(pkg.get("days_paid") or 30)
        ends = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
        await _db.developer_accounts.update_one(
            {"user_id": user_id},
            {"$set": {
                "subscription_status":   "paid",
                "subscription_paid_until": ends,
            }},
        )
        result = {"ok": True, "credited": True, "kind": "subscription",
                  "days_paid": days, "paid_until": ends, "tier": tier}
    else:
        result = {"ok": True, "credited": True, "kind": "unknown", "tier": tier}

    # Fire receipt email best-effort
    try:
        from services.email_service_resend import send_email
        email = row.get("email") or ""
        if email:
            subject = f"AUREM CTO — Receipt for your {pkg.get('label', tier)} purchase"
            label = pkg.get("label", tier.title())
            kind_line = (
                f"{result.get('tokens_granted', 0):,} tokens added to your account."
                if result.get("kind") == "tokens"
                else f"30 days of unlimited usage active until {result.get('paid_until', '')[:10]}."
            )
            text = (
                f"Thanks for buying {label}.\n\n"
                f"{kind_line}\n\n"
                f"Session: {session_id}\n"
                f"Amount:  ${row.get('amount_usd', 0):.2f} USD\n\n"
                f"Open your dashboard: "
                f"{(os.environ.get('FRONTEND_URL') or 'https://aurem.live').rstrip('/')}/developers/dashboard\n"
            )
            html = (
                f"<p>Thanks for buying <strong>{label}</strong>.</p>"
                f"<p>{kind_line}</p>"
                f"<p style='color:#888;font-size:12px'>Session: {session_id} "
                f"&middot; ${row.get('amount_usd', 0):.2f} USD</p>"
            )
            await send_email(to=email, subject=subject, html=html, text=text)
    except Exception as e:
        logger.warning(f"[dev-stripe] receipt email skipped: {e}")

    return result


async def process_webhook_event(event_id: str, event_type: str,
                                  session_id: str | None,
                                  raw_event: dict | None = None) -> dict[str, Any]:
    """Idempotent webhook router. Returns `{ok, processed, action}`.
    Refuses to process the same event.id twice.
    """
    if _db is None:
        return {"ok": False, "error": "db not ready"}
    # Try to claim this event.id — atomic insert with unique key.
    try:
        await _db.stripe_events_processed.insert_one({
            "event_id":   event_id,
            "event_type": event_type,
            "session_id": session_id,
            "received_at": _now_iso(),
        })
    except Exception:
        # Duplicate — already processed
        return {"ok": True, "processed": False, "reason": "duplicate"}

    action = "noop"
    if event_type == "checkout.session.completed" and session_id:
        r = await credit_for_session(session_id)
        action = "credit" if r.get("credited") else r.get("reason", "skip")
    elif event_type == "invoice.payment_succeeded":
        # Receipt was sent at credit time; nothing further.
        action = "receipt_already_sent"
    elif event_type in ("invoice.payment_failed",
                         "customer.subscription.deleted"):
        action = await _handle_payment_failed(raw_event or {})

    return {"ok": True, "processed": True, "action": action,
            "event_id": event_id, "event_type": event_type}


async def _handle_payment_failed(raw_event: dict) -> str:
    """3-day grace logic: first failure stamps `grace_period_ends_at`.
    Second failure after grace expiry flips `subscription_status` back
    to "free" and emails the customer to update the card."""
    try:
        obj = ((raw_event.get("data") or {}).get("object") or {})
        customer_id = obj.get("customer")
        if not customer_id:
            return "no_customer"
        acc = await _db.developer_accounts.find_one(
            {"stripe_customer_id": customer_id}, {"_id": 0},
        )
        if not acc:
            return "no_account"
        now = datetime.now(timezone.utc)
        grace_iso = acc.get("grace_period_ends_at")
        if not grace_iso:
            # First failure — start 3-day grace
            ends = (now + timedelta(days=3)).isoformat()
            await _db.developer_accounts.update_one(
                {"user_id": acc["user_id"]},
                {"$set": {"grace_period_ends_at": ends,
                           "payment_failed_at":    now.isoformat()}},
            )
            # Email warning
            try:
                from services.email_service_resend import send_email
                site = (os.environ.get("FRONTEND_URL") or "https://aurem.live").rstrip("/")
                await send_email(
                    to=acc["email"],
                    subject="AUREM CTO — Payment failed, please update your card",
                    text=(
                        f"Your last payment failed. Update your card at "
                        f"{site}/developers/tokens within 3 days to keep Pro access.\n"
                    ),
                    html=(
                        f"<p>Your last payment failed.</p>"
                        f"<p>Update your card at <a href='{site}/developers/tokens'>"
                        f"{site}/developers/tokens</a> within 3 days to keep Pro access.</p>"
                    ),
                )
            except Exception:
                pass
            return "grace_started"
        # Grace exists — check if expired
        try:
            grace_end = datetime.fromisoformat(grace_iso.replace("Z", "+00:00"))
            if grace_end.tzinfo is None:
                grace_end = grace_end.replace(tzinfo=timezone.utc)
        except Exception:
            grace_end = now
        if grace_end < now:
            await _db.developer_accounts.update_one(
                {"user_id": acc["user_id"]},
                {"$set": {"subscription_status": "free"},
                 "$unset": {"grace_period_ends_at": "",
                             "subscription_paid_until": ""}},
            )
            return "downgraded"
        return "in_grace"
    except Exception as e:
        logger.warning(f"[dev-stripe] _handle_payment_failed error: {e}")
        return "error"


__all__ = [
    "set_db", "PACKAGES", "package_table",
    "start_checkout", "get_status",
    "credit_for_session", "process_webhook_event",
]
