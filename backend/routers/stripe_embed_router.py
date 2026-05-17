"""
Stripe Embedded Checkout Router — Iteration 202
================================================
Embedded (zero-redirect) Stripe Checkout for subscriptions.

Apple Pay + Google Pay are automatically shown by Stripe when the browser
supports them (Safari on iOS/macOS, Chrome with Google Pay) — no extra config
required beyond enabling them in the Stripe dashboard.

Endpoints:
  POST /api/stripe-embed/create-session   — {plan} → {client_secret, session_id}
  GET  /api/stripe-embed/session-status/{session_id}
  GET  /api/stripe-embed/publishable-key
"""
from __future__ import annotations

import os
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
import jwt
import stripe

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/stripe-embed", tags=["Stripe Embedded Checkout"])

JWT_SECRET = os.environ.get("JWT_SECRET")
if not JWT_SECRET:
    raise RuntimeError("CRITICAL: JWT_SECRET not set.")

STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")
stripe.api_key = STRIPE_SECRET_KEY

PLAN_PRICES = {
    "starter":    os.environ.get("STRIPE_PRICE_STARTER", ""),
    "growth":     os.environ.get("STRIPE_PRICE_GROWTH", ""),
    "enterprise": os.environ.get("STRIPE_PRICE_ENTERPRISE", ""),
}

# Annual variants (optional — fallback to monthly price with metadata flag if unset).
# Customers get 20% off when choosing annual.
ANNUAL_PLAN_PRICES = {
    "starter":    os.environ.get("STRIPE_PRICE_STARTER_ANNUAL", ""),
    "growth":     os.environ.get("STRIPE_PRICE_GROWTH_ANNUAL", ""),
    "enterprise": os.environ.get("STRIPE_PRICE_ENTERPRISE_ANNUAL", ""),
}

_db = None


def set_db(db):
    global _db
    _db = db


def _get_db():
    if _db is None:
        raise HTTPException(503, "DB not available")
    return _db


async def _auth(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Auth required")
    try:
        return jwt.decode(auth.split(" ", 1)[1], JWT_SECRET, algorithms=["HS256"])
    except Exception:
        raise HTTPException(401, "Invalid token")


class CreateSessionBody(BaseModel):
    plan: str                   # starter | growth | enterprise
    return_url: Optional[str] = None   # Frontend origin; completion handled inline
    annual: bool = False        # 20% off when annual=true (requires annual price IDs in env)


@router.get("/publishable-key")
async def publishable_key():
    """Return the Stripe publishable key + the mode our backend secret key
    is in. Frontend calls this before booting Stripe.js so it can refuse to
    render Apple Pay if the two halves are mismatched.
    """
    if not STRIPE_PUBLISHABLE_KEY:
        raise HTTPException(503, "Stripe publishable key not configured")
    secret_mode = "live" if STRIPE_SECRET_KEY.startswith("sk_live_") else (
        "test" if STRIPE_SECRET_KEY.startswith("sk_test_") else "unknown"
    )
    publishable_mode = "live" if STRIPE_PUBLISHABLE_KEY.startswith("pk_live_") else (
        "test" if STRIPE_PUBLISHABLE_KEY.startswith("pk_test_") else "unknown"
    )
    return {
        "publishable_key": STRIPE_PUBLISHABLE_KEY,
        "mode": secret_mode,
        "publishable_mode": publishable_mode,
        "in_sync": secret_mode == publishable_mode,
    }


@router.post("/create-session")
async def create_session(body: CreateSessionBody, request: Request):
    """Create an embedded checkout session for a subscription plan."""
    payload = await _auth(request)
    db = _get_db()

    if not STRIPE_SECRET_KEY:
        raise HTTPException(503, "Stripe not configured")

    plan = (body.plan or "").strip().lower()
    # Annual → 20% off via a dedicated annual price ID in Stripe.
    # If the annual price isn't configured, we fall back to the monthly price
    # (Stripe will surface the configured promotion codes instead).
    price_id = (ANNUAL_PLAN_PRICES.get(plan) if body.annual else PLAN_PRICES.get(plan)) \
               or PLAN_PRICES.get(plan)
    if not price_id:
        raise HTTPException(400, f"Unknown plan: {plan}")

    email = (payload.get("email") or payload.get("sub") or "").lower()
    if not email:
        raise HTTPException(401, "Invalid token")

    user = await db.platform_users.find_one({"email": email}, {"_id": 0}) \
        or await db.users.find_one({"email": email}, {"_id": 0})
    tenant_id = (user or {}).get("id") or (user or {}).get("tenant_id") or email

    # Build a return URL on the customer's own origin (zero-redirect pattern:
    # we still pass a return_url as Stripe requires, but session embeds inline.)
    origin = (body.return_url or "").rstrip("/") or "https://aurem.live"
    return_url = f"{origin}/my/billing?session_id={{CHECKOUT_SESSION_ID}}"

    try:
        # Stripe Python SDK uses a module-level api_key — re-bind on every
        # call so any other router that flipped it (e.g. legacy stripe.api_key
        # = sk_test_…) doesn't leak across this critical path.
        stripe.api_key = STRIPE_SECRET_KEY

        # Pre-flight key/price mode sanity check. The Stripe error for a
        # mode-mismatched price is opaque ("No such price") — surface a
        # clearer signal here so the founder sees the real cause.
        secret_mode = "live" if STRIPE_SECRET_KEY.startswith("sk_live_") else (
            "test" if STRIPE_SECRET_KEY.startswith("sk_test_") else "unknown"
        )
        publishable_mode = "live" if STRIPE_PUBLISHABLE_KEY.startswith("pk_live_") else (
            "test" if STRIPE_PUBLISHABLE_KEY.startswith("pk_test_") else "unknown"
        )
        if secret_mode != publishable_mode:
            raise HTTPException(
                500,
                f"Stripe key mode mismatch: secret={secret_mode} publishable={publishable_mode}. "
                f"Update env vars so both keys belong to the same mode."
            )

        # Build session params; gate automatic_tax behind env flag (iter 280.8)
        # — see service_catalog_router for full rationale.
        _auto_tax = os.environ.get("STRIPE_AUTOMATIC_TAX", "").strip().lower() in ("1", "true", "yes", "on")
        session_kwargs = dict(
            ui_mode="embedded",
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            customer_email=email,
            return_url=return_url,
            metadata={
                "tenant_id": str(tenant_id),
                "plan": plan,
                "annual": "true" if body.annual else "false",
                "email": email,
            },
            allow_promotion_codes=True,
            # Apple Pay / Google Pay are auto-detected for card payment method
            payment_method_types=["card"],
        )
        if _auto_tax:
            # Canadian HST/GST handled automatically when origin_address is
            # configured in the Stripe dashboard.
            session_kwargs["automatic_tax"] = {"enabled": True}
        session = stripe.checkout.Session.create(**session_kwargs)
    except HTTPException:
        raise
    except stripe.error.InvalidRequestError as e:  # type: ignore[attr-defined]
        # Translate Stripe's most common deployment-time errors into
        # actionable founder-facing messages.
        msg = str(e)
        hint = ""
        if "No such price" in msg:
            hint = (
                f" — Price `{price_id}` not found in {secret_mode} mode. "
                "Either switch STRIPE_SECRET_KEY to the matching mode or "
                "create this price in the current Stripe account/mode."
            )
        elif "head office" in msg.lower() or "automatic tax" in msg.lower():
            hint = (
                " — Stripe Tax requires a head-office address in this mode. "
                "Set it at https://dashboard.stripe.com/"
                f"{'test/' if secret_mode == 'test' else ''}settings/tax"
            )
        logger.warning(f"[StripeEmbed] InvalidRequestError: {msg}{hint}")
        raise HTTPException(400, f"Stripe error: {msg}{hint}")
    except Exception as e:
        logger.exception("[StripeEmbed] create session failed")
        raise HTTPException(500, f"Stripe error: {e}")

    # Persist transaction record BEFORE returning (idempotency baseline)
    try:
        await db.payment_transactions.insert_one({
            "session_id": session.id,
            "email": email,
            "tenant_id": tenant_id,
            "plan": plan,
            "annual": bool(body.annual),
            "price_id": price_id,
            "amount": None,  # subscription price — filled on webhook
            "currency": "usd",
            "status": "initiated",
            "payment_status": "pending",
            "mode": "subscription_embedded",
            "metadata": {"source": "embedded_checkout", "plan": plan, "annual": body.annual},
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        logger.warning(f"[StripeEmbed] persist txn failed: {e}")

    return {
        "client_secret": session.client_secret,
        "session_id": session.id,
    }


@router.get("/session-status/{session_id}")
async def session_status(session_id: str, request: Request):
    """Poll session status (idempotent — never credits twice)."""
    payload = await _auth(request)
    db = _get_db()

    if not STRIPE_SECRET_KEY:
        raise HTTPException(503, "Stripe not configured")

    try:
        session = stripe.checkout.Session.retrieve(session_id)
    except Exception as e:
        raise HTTPException(404, f"Session not found: {e}")

    _auth_email = (payload.get("email") or payload.get("sub") or "").lower()
    _ = _auth_email  # future: verify requester owns this session_id
    status_str = session.get("status") if isinstance(session, dict) else getattr(session, "status", None)
    payment_status = session.get("payment_status") if isinstance(session, dict) else getattr(session, "payment_status", None)

    # Idempotent DB update
    try:
        existing = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
        if existing and existing.get("payment_status") != "paid":
            await db.payment_transactions.update_one(
                {"session_id": session_id},
                {"$set": {
                    "status": status_str,
                    "payment_status": payment_status,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }},
            )
    except Exception as e:
        logger.warning(f"[StripeEmbed] status update failed: {e}")

    return {
        "session_id": session_id,
        "status": status_str,
        "payment_status": payment_status,
        "customer_email": (session.get("customer_details") or {}).get("email") if isinstance(session, dict) else None,
        "amount_total": session.get("amount_total") if isinstance(session, dict) else None,
    }


@router.get("/health")
async def health():
    # Re-read from os.environ at request time (NOT module-level) so this
    # endpoint reflects the *currently injected* runtime env vars rather
    # than whatever was loaded at process startup. Useful to verify
    # Emergent UI env-var updates landed without needing a full restart.
    runtime_sk = os.environ.get("STRIPE_SECRET_KEY", "")
    runtime_pk = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")
    secret_mode = "live" if runtime_sk.startswith("sk_live_") else (
        "test" if runtime_sk.startswith("sk_test_") else "unknown"
    )
    publishable_mode = "live" if runtime_pk.startswith("pk_live_") else (
        "test" if runtime_pk.startswith("pk_test_") else "unknown"
    )
    # ── TEMPORARY DEBUG (iter 280.10/.11) ───────────────────────────
    # Diagnose why prod was reading TEST mode despite Emergent UI vars
    # being set to live. Returns: prefix of each runtime key, whether
    # module-level cache (loaded at import) matches, and whether
    # /app/backend/.env.production exists with what mode of keys.
    # REMOVE after prod confirms `secret_mode: live`.
    import os.path as _ospath

    def _key_mode(s: str) -> str:
        if not s:
            return "EMPTY"
        if s.startswith("sk_live_") or s.startswith("pk_live_"):
            return "live"
        if s.startswith("sk_test_") or s.startswith("pk_test_"):
            return "test"
        return "unknown"

    def _file_mode(path: str) -> str:
        if not _ospath.exists(path):
            return "missing"
        try:
            with open(path) as f:
                t = f.read()
            if "STRIPE_SECRET_KEY=sk_live_" in t:
                return "live"
            if "STRIPE_SECRET_KEY=sk_test_" in t:
                return "test"
            return "unset_in_file"
        except Exception:
            return "unreadable"

    debug = {
        "runtime_sk_prefix": runtime_sk[:10] if runtime_sk else "EMPTY",
        "runtime_pk_prefix": runtime_pk[:10] if runtime_pk else "EMPTY",
        "module_sk_prefix": STRIPE_SECRET_KEY[:10] if STRIPE_SECRET_KEY else "EMPTY",
        "module_matches_runtime": STRIPE_SECRET_KEY == runtime_sk,
        "env_production_file_mode": _file_mode("/app/backend/.env.production"),
        "env_dot_file_mode": _file_mode("/app/backend/.env"),
        "app_env_dot_mode": _file_mode("/app/.env"),
        "all_stripe_env_modes": {
            k: _key_mode(v)[:10] for k, v in os.environ.items()
            if k.startswith("STRIPE_") and (
                v.startswith("sk_") or v.startswith("pk_")
            )
        },
        "aurem_env": os.environ.get("AUREM_ENV", "unset"),
        "current_pid": os.getpid(),
    }
    return {
        "status": "ok",
        "service": "stripe-embedded-checkout",
        "configured": bool(runtime_sk and runtime_pk),
        "secret_mode": secret_mode,
        "publishable_mode": publishable_mode,
        "in_sync": secret_mode == publishable_mode,
        "plans": {k: bool(v) for k, v in PLAN_PRICES.items()},
        "annual_plans": {k: bool(v) for k, v in ANNUAL_PLAN_PRICES.items()},
        "_debug": debug,
    }

