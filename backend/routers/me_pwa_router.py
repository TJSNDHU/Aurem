"""
ORA PWA — per-BIN scoped data router (iter 282o)
=================================================
All endpoints gated by JWT. The decoded user determines scope:

    • admin / super_admin  → platform-wide aggregates
    • customer (BIN owner) → only that BIN's data

Endpoints
---------
  GET /api/me/identity            — who am I + BIN + plan + trial days
  GET /api/me/leads/today         — today's leads (admin: all, cust: their inbound)
  GET /api/me/scout/status        — scout activity (admin only data; customers see empty placeholder)
  GET /api/me/billing/summary     — Stripe sub status (admin: platform MRR; cust: their sub)
  GET /api/me/history?days=7      — daily_verification_log filtered by scope
  GET /api/me/notifications/today — bell items scoped by role
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/me", tags=["ORA PWA — Me Scoped"])

_TZ_EST = ZoneInfo("America/Toronto")
_db = None


def set_db(database) -> None:
    global _db
    _db = database


def _today_iso_est() -> str:
    return datetime.now(_TZ_EST).replace(
        hour=0, minute=0, second=0, microsecond=0,
    ).isoformat()


def _today_date_str() -> str:
    return datetime.now(_TZ_EST).date().isoformat()


# ─── Auth resolver (returns user context or 401) ─────────────────────
async def _require_user(authorization: Optional[str]) -> Dict[str, Any]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Missing token")
    token = authorization.split(" ", 1)[1].strip()
    if not token or _db is None:
        raise HTTPException(503, "Auth not ready")
    try:
        import jwt  # type: ignore
        secret = os.environ.get("JWT_SECRET", "")
        if not secret:
            raise HTTPException(503, "JWT secret missing")
        payload = jwt.decode(token, secret, algorithms=["HS256"])
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(401, "Invalid token")

    email = payload.get("email") or payload.get("sub")
    user_id = payload.get("user_id")
    role = payload.get("role")

    if email:
        u = await _db.platform_users.find_one(
            {"email": email},
            {"_id": 0, "email": 1, "user_id": 1, "first_name": 1,
             "business_name": 1, "bin": 1, "plan_label": 1, "plan": 1,
             "role": 1, "trial_ends_at": 1, "subscription_status": 1,
             "stripe_customer_id": 1, "stripe_subscription_id": 1,
             "created_at": 1, "must_set_password": 1,
             "onboarding_wizard_complete": 1},
        )
        if u:
            is_admin = (u.get("role") in ("admin", "super_admin")) or (
                role in ("admin", "super_admin"))
            return {
                "scope": "admin" if is_admin else "customer",
                "bin": u.get("bin") or "AURE-CUSTOMER",
                "user_id": u.get("user_id") or email,
                "email": email,
                "name": u.get("first_name") or u.get("business_name") or email.split("@")[0],
                "business_name": u.get("business_name"),
                "plan": u.get("plan_label") or u.get("plan") or "Free",
                "is_admin": is_admin,
                "trial_ends_at": u.get("trial_ends_at"),
                "subscription_status": u.get("subscription_status"),
                "stripe_customer_id": u.get("stripe_customer_id"),
                "stripe_subscription_id": u.get("stripe_subscription_id"),
            }
    # Admin record fallback
    admin_q: Dict[str, Any] = {}
    if user_id:
        admin_q = {"$or": [{"user_id": user_id}, {"id": user_id}]}
    elif email:
        admin_q = {"email": email}
    if admin_q:
        a = await _db.users.find_one(
            admin_q, {"_id": 0, "email": 1, "user_id": 1, "name": 1, "role": 1},
        )
        if a:
            return {
                "scope": "admin",
                "bin": "AURE-ADMIN",
                "user_id": a.get("user_id") or "admin",
                "email": a.get("email") or email,
                "name": a.get("name") or "Founder",
                "business_name": "AUREM (Founder)",
                "plan": "Founder",
                "is_admin": True,
                "trial_ends_at": None,
                "subscription_status": "active",
                "stripe_customer_id": None,
                "stripe_subscription_id": None,
            }
    raise HTTPException(401, "User not found")


def _trial_days_left(trial_ends_at: Optional[str]) -> Optional[int]:
    if not trial_ends_at:
        return None
    try:
        end = datetime.fromisoformat(trial_ends_at.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        return max(0, int((end - now).total_seconds() // 86400))
    except Exception:
        return None


# ─── Endpoints ───────────────────────────────────────────────────────
@router.get("/identity")
async def me_identity(
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    u = await _require_user(authorization)
    return {
        "ok": True,
        "scope": u["scope"],
        "bin": u["bin"],
        "name": u["name"],
        "business_name": u["business_name"],
        "email": u["email"],
        "plan": u["plan"],
        "is_admin": u["is_admin"],
        "trial_days_left": _trial_days_left(u.get("trial_ends_at")),
        "subscription_status": u.get("subscription_status"),
    }


@router.get("/leads/today")
async def me_leads_today(
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    u = await _require_user(authorization)
    iso = _today_iso_est()
    if u["is_admin"]:
        # Admin sees platform-wide outreach prospects
        cur = _db.campaign_leads.find(
            {"created_at": {"$gte": iso}},
            {"_id": 0, "lead_id": 1, "business_name": 1, "city": 1,
             "address": 1, "discovered_emails": 1, "discovered_emails_count": 1,
             "awb_built_at": 1, "awb_slug": 1, "logo_url": 1},
        ).sort("_id", -1).limit(50)
        leads = await cur.to_list(50)
        total = await _db.campaign_leads.count_documents(
            {"created_at": {"$gte": iso}})
        return {"ok": True, "scope": "admin", "leads": leads, "total": total}
    # Customer: their inbound leads (form submissions, lead-magnet, repair-quote)
    bin_ = u["bin"]
    cur = _db.customer_leads.find(
        {"$or": [{"bin": bin_}, {"customer_bin": bin_}],
         "created_at": {"$gte": iso}},
        {"_id": 0, "lead_id": 1, "name": 1, "email": 1, "phone": 1,
         "source": 1, "status": 1, "message": 1, "created_at": 1},
    ).sort("created_at", -1).limit(50) if hasattr(_db, "customer_leads") else None
    leads: List[Dict[str, Any]] = []
    total = 0
    if cur is not None:
        try:
            leads = await cur.to_list(50)
            total = await _db.customer_leads.count_documents({
                "$or": [{"bin": bin_}, {"customer_bin": bin_}],
                "created_at": {"$gte": iso},
            })
        except Exception:
            leads, total = [], 0
    return {"ok": True, "scope": "customer", "bin": bin_,
            "leads": leads, "total": total}


@router.get("/scout/status")
async def me_scout_status(
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    u = await _require_user(authorization)
    if not u["is_admin"]:
        # Customers don't run AUREM Scout — that's the founder's outreach engine.
        # Return a placeholder + their own review-monitoring stats.
        bin_ = u["bin"]
        review_count = 0
        try:
            review_count = await _db.reviews.count_documents({"bin": bin_})
        except Exception:
            pass
        return {
            "ok": True, "scope": "customer", "bin": bin_,
            "scout_running": False,
            "message": "AUREM Scout is the founder's lead-discovery engine. "
                       "Your account uses it for your own SEO/review monitoring.",
            "your_reviews_total": review_count,
            "next_run": "9:00 AM EST tomorrow",
        }
    today = _today_date_str()
    cur = _db.daily_verification_log.find(
        {"date": today,
         "event": {"$in": ["scout_complete", "morning_armed"]}},
        {"_id": 0},
    ).sort("ts_utc", -1).limit(5)
    events = await cur.to_list(5)
    last = events[0] if events else None
    leads_today = 0
    if last:
        leads_today = last.get("leads_real_count") or last.get("leads_today") or 0
    return {
        "ok": True, "scope": "admin",
        "scout_running": bool(last),
        "last_event": last,
        "leads_today": leads_today,
        "next_run": "9:00 AM EST",
    }


@router.get("/billing/summary")
async def me_billing(
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    u = await _require_user(authorization)
    api_key = os.environ.get("STRIPE_SECRET_KEY") or os.environ.get("STRIPE_API_KEY")
    if not api_key:
        return {"ok": True, "scope": u["scope"], "bin": u["bin"],
                "stripe_configured": False,
                "revenue_today": 0, "active_subscribers": 0}
    try:
        import stripe  # type: ignore
        stripe.api_key = api_key
    except ImportError:
        return {"ok": True, "scope": u["scope"], "bin": u["bin"],
                "stripe_configured": False}

    if u["is_admin"]:
        # Platform-wide
        revenue = 0.0
        active_subs = 0
        try:
            ts = int(datetime.now(_TZ_EST).replace(
                hour=0, minute=0, second=0, microsecond=0).timestamp())
            charges = stripe.Charge.list(created={"gte": ts}, limit=100)
            for ch in charges.auto_paging_iter():
                if ch.get("paid") and ch.get("status") == "succeeded":
                    revenue += (ch.get("amount", 0) / 100.0)
            subs = stripe.Subscription.list(status="active", limit=100)
            active_subs = sum(1 for _ in subs.auto_paging_iter())
        except Exception as e:
            logger.warning(f"[me/billing] stripe admin fetch: {e}")
        return {
            "ok": True, "scope": "admin", "bin": u["bin"],
            "stripe_configured": True,
            "revenue_today": round(revenue, 2),
            "active_subscribers": active_subs,
            "mrr_estimate": round(active_subs * 47.0, 2),
        }
    # Customer: their own subscription
    sub_status = u.get("subscription_status") or "trial"
    plan = u["plan"]
    last_payment = None
    try:
        if u.get("stripe_customer_id"):
            charges = stripe.Charge.list(
                customer=u["stripe_customer_id"], limit=1)
            arr = list(charges.auto_paging_iter())
            if arr:
                ch = arr[0]
                last_payment = {
                    "amount": ch.get("amount", 0) / 100.0,
                    "currency": (ch.get("currency") or "usd").upper(),
                    "ts": ch.get("created"),
                }
    except Exception as e:
        logger.warning(f"[me/billing] stripe cust fetch: {e}")
    return {
        "ok": True, "scope": "customer", "bin": u["bin"],
        "stripe_configured": True,
        "subscription_status": sub_status,
        "plan": plan,
        "trial_days_left": _trial_days_left(u.get("trial_ends_at")),
        "last_payment": last_payment,
    }


@router.get("/history")
async def me_history(
    days: int = 7,
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    u = await _require_user(authorization)
    days = max(1, min(30, days))
    if u["is_admin"]:
        cur = _db.daily_verification_log.find(
            {}, {"_id": 0},
        ).sort("ts_utc", -1).limit(days * 20)
        rows = await cur.to_list(days * 20)
    else:
        # Customers don't have aggregated daily logs scoped to them yet.
        # Surface their own activity: reviews requested, emails sent, signups, payments.
        bin_ = u["bin"]
        rows = []
        try:
            r_reviews = await _db.reviews.find(
                {"bin": bin_}, {"_id": 0, "created_at": 1, "rating": 1, "reviewer_name": 1},
            ).sort("created_at", -1).limit(20).to_list(20)
            for r in r_reviews:
                rows.append({
                    "date": (r.get("created_at") or "")[:10],
                    "event": "review_received",
                    "ts_utc": r.get("created_at"),
                    "detail": f"{r.get('rating', '?')}★ from {r.get('reviewer_name', 'someone')}",
                })
        except Exception:
            pass
    by_date: Dict[str, list] = {}
    for r in rows:
        d = r.get("date") or (r.get("ts_utc") or "")[:10]
        if not d:
            continue
        by_date.setdefault(d, []).append(r)
    days_out = [
        {"date": d, "events": evs, "event_count": len(evs)}
        for d, evs in sorted(by_date.items(), reverse=True)[:days]
    ]
    return {"ok": True, "scope": u["scope"], "days": days_out}


@router.get("/notifications/today")
async def me_notifications_today(
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    u = await _require_user(authorization)
    today = _today_date_str()
    if u["is_admin"]:
        cur = _db.daily_verification_log.find(
            {"date": today}, {"_id": 0},
        ).sort("ts_utc", -1).limit(50)
        events = await cur.to_list(50)
        return {"ok": True, "scope": "admin", "events": events,
                "count": len(events)}
    # Customer: build from their own activity surface
    bin_ = u["bin"]
    iso = _today_iso_est()
    events: List[Dict[str, Any]] = []
    # Trial-ending reminder
    days_left = _trial_days_left(u.get("trial_ends_at"))
    if days_left is not None and days_left <= 3:
        events.append({
            "event": "trial_warning",
            "date": today,
            "ts_utc": datetime.now(timezone.utc).isoformat(),
            "detail": f"Trial ends in {days_left} day{'s' if days_left != 1 else ''}",
        })
    try:
        recent_reviews = await _db.reviews.find(
            {"bin": bin_, "created_at": {"$gte": iso}},
            {"_id": 0, "rating": 1, "reviewer_name": 1, "created_at": 1},
        ).sort("created_at", -1).limit(20).to_list(20)
        for r in recent_reviews:
            events.append({
                "event": "review_received",
                "date": today,
                "ts_utc": r.get("created_at"),
                "detail": f"{r.get('rating', '?')}★ — {r.get('reviewer_name', 'someone')}",
            })
    except Exception:
        pass
    return {"ok": True, "scope": "customer", "bin": bin_,
            "events": events, "count": len(events)}
