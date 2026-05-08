"""
AUREM Site Monitor Router
═══════════════════════════════════════════════════════════════════════════════
Public + Customer + Admin endpoints for the Site Monitor product (MVP + Growth hybrid).

Public (lead magnet):
  POST /api/site-monitor/free/signup      — email + url → 30-day free trial

Customer (JWT authenticated):
  GET  /api/site-monitor/me/plan          — current plan tier & limits
  GET  /api/site-monitor/me/endpoints     — my monitored URLs with live stats
  POST /api/site-monitor/me/endpoints     — add URL (respects plan limits)
  DELETE /api/site-monitor/me/endpoints/{id}
  GET  /api/site-monitor/me/incidents     — downtime history
  POST /api/site-monitor/me/upgrade       — Stripe checkout for paid tier

Admin (super_admin JWT):
  GET  /api/admin/site-monitor/overview   — aggregate MRR + counts
  GET  /api/admin/site-monitor/tenants    — all monitored tenants
  POST /api/admin/site-monitor/scan-now   — trigger immediate scan
"""
import os
import logging
from datetime import datetime, timezone
from typing import Optional, List

import jwt
from fastapi import APIRouter, HTTPException, Request, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Site Monitor"])

_db = None


def set_db(database):
    global _db
    _db = database
    try:
        from services.site_monitor import set_db as _sm_set_db
        _sm_set_db(database)
    except Exception:
        pass


# ═════════════════════════════════════════════════════════════════════
# Auth helpers
# ═════════════════════════════════════════════════════════════════════
def _decode_jwt(request: Request) -> dict:
    auth = request.headers.get("authorization") or request.headers.get("Authorization") or ""
    token = auth.split(" ", 1)[1] if auth.startswith("Bearer ") else None
    if not token:
        raise HTTPException(401, "Auth required")
    try:
        return jwt.decode(token, os.environ.get("JWT_SECRET", ""), algorithms=["HS256"])
    except Exception:
        raise HTTPException(401, "Invalid token")


async def _require_platform_user(request: Request) -> dict:
    payload = _decode_jwt(request)
    email = (payload.get("email") or "").lower()
    if not email:
        raise HTTPException(401, "email missing in token")
    if _db is None:
        raise HTTPException(503, "db not ready")
    user = await _db.platform_users.find_one({"email": email}, {"_id": 0, "password_hash": 0})
    if not user:
        # Fallback — users collection (admin path)
        user = await _db.users.find_one({"email": email}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(404, "user not found")
    user["email"] = email
    user["bin"] = user.get("bin") or user.get("business_id") or user.get("tenant_id")
    return user


async def _require_admin(request: Request) -> dict:
    payload = _decode_jwt(request)
    role = (payload.get("role") or "").lower()
    if role not in ("admin", "super_admin") and not (payload.get("is_admin") or payload.get("is_super_admin")):
        raise HTTPException(403, "Admin role required")
    return payload


# ═════════════════════════════════════════════════════════════════════
# Public — Free Lead Magnet
# ═════════════════════════════════════════════════════════════════════
class FreeSignupBody(BaseModel):
    email: str = Field(..., min_length=3, max_length=200)
    url: str = Field(..., min_length=4, max_length=500)


@router.post("/api/site-monitor/free/signup")
async def public_free_signup(body: FreeSignupBody, request: Request):
    """Public lead magnet — no auth required. Rate limited by IP + email."""
    from services.site_monitor import free_signup
    # Simple IP/email-based rate limit (3 signups per hour per email)
    if _db is not None:
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        recent = await _db.site_monitor_free.count_documents(
            {"email": body.email.lower(), "last_signup_at": {"$gte": cutoff}}
        )
        if recent >= 3:
            raise HTTPException(429, "too many signups, please try again later")
    try:
        result = await free_signup(body.email, body.url, source=request.headers.get("referer", "direct"))
        return {"ok": True, **result}
    except ValueError as ve:
        raise HTTPException(400, str(ve))
    except Exception as e:
        logger.exception(f"[free-signup] failed: {e}")
        raise HTTPException(500, "signup failed")


# ═════════════════════════════════════════════════════════════════════
# Customer — Plan, URLs, Incidents, Upgrade
# ═════════════════════════════════════════════════════════════════════
@router.get("/api/site-monitor/me/plan")
async def me_plan(request: Request):
    user = await _require_platform_user(request)
    from services.site_monitor import get_tenant_plan
    plan = await get_tenant_plan(user["email"], user.get("bin"))
    plan["bin"] = user.get("bin") or user["email"]
    plan["email"] = user["email"]
    return {"ok": True, "plan": plan}


@router.get("/api/site-monitor/me/endpoints")
async def me_endpoints(request: Request, window_hours: int = Query(24, ge=1, le=720)):
    user = await _require_platform_user(request)
    from services.site_monitor import tenant_stats
    stats = await tenant_stats(user["email"], window_hours)
    return {"ok": True, **stats}


class AddUrlBody(BaseModel):
    url: str = Field(..., min_length=4, max_length=500)
    label: Optional[str] = ""
    method: str = "GET"
    expected_status: Optional[List[int]] = None


@router.post("/api/site-monitor/me/endpoints")
async def me_add_url(body: AddUrlBody, request: Request):
    user = await _require_platform_user(request)
    from services.site_monitor import add_url
    try:
        url = body.url if body.url.startswith("http") else f"https://{body.url}"
        doc = await add_url(user["email"], user.get("bin"), url, body.label or "",
                            body.method, body.expected_status)
        return {"ok": True, "endpoint": doc}
    except ValueError as ve:
        raise HTTPException(400, str(ve))
    except Exception as e:
        logger.exception(f"[add-url] failed: {e}")
        raise HTTPException(500, "add failed")


@router.delete("/api/site-monitor/me/endpoints/{endpoint_id}")
async def me_remove_url(endpoint_id: str, request: Request):
    user = await _require_platform_user(request)
    from services.site_monitor import remove_url
    ok = await remove_url(user["email"], endpoint_id)
    if not ok:
        raise HTTPException(404, "endpoint not found")
    return {"ok": True}


@router.get("/api/site-monitor/me/incidents")
async def me_incidents(request: Request, limit: int = Query(50, ge=1, le=500)):
    user = await _require_platform_user(request)
    from services.site_monitor import tenant_incidents
    incidents = await tenant_incidents(user["email"], limit)
    return {"ok": True, "count": len(incidents), "incidents": incidents}


class UpgradeBody(BaseModel):
    service_id: str
    origin_url: Optional[str] = None


@router.post("/api/site-monitor/me/upgrade")
async def me_upgrade(body: UpgradeBody, request: Request):
    """Create a Stripe checkout session for upgrade. Uses existing /api/customer/subscriptions/subscribe flow."""
    from services.site_monitor import SKU_IDS
    if body.service_id not in SKU_IDS:
        raise HTTPException(400, f"invalid service_id. Must be one of {SKU_IDS}")
    user = await _require_platform_user(request)

    svc = await _db.service_catalog.find_one({"service_id": body.service_id, "status": "live"}, {"_id": 0})
    if not svc:
        raise HTTPException(404, "service not available")

    existing = await _db.customer_subscriptions.find_one({
        "email": user["email"], "service_id": body.service_id, "status": "active"
    })
    if existing:
        raise HTTPException(409, "already subscribed")

    api_key = os.environ.get("STRIPE_SECRET_KEY", "")
    if not api_key:
        raise HTTPException(500, "Stripe not configured")

    try:
        import stripe as stripe_lib
        stripe_lib.api_key = api_key
        # iter 280.12 — per-mode price caching (mirrors service_catalog_router)
        _mode = "live" if api_key.startswith("sk_live_") else (
            "test" if api_key.startswith("sk_test_") else "unknown"
        )
        price_field = f"stripe_price_id_{_mode}"
        product_field = f"stripe_product_id_{_mode}"
        price_id = svc.get(price_field) or (
            svc.get("stripe_price_id")
            if _mode != "unknown"
               and not svc.get(f"stripe_price_id_{('live' if _mode == 'test' else 'test')}")
            else None
        )

        async def _mint_fresh_site_mon_price():
            new_product = stripe_lib.Product.create(
                name=svc["name"],
                description=svc.get("description", ""),
                metadata={"service_id": svc["service_id"], "mode": _mode},
            )
            new_price = stripe_lib.Price.create(
                product=new_product.id,
                unit_amount=int(svc["price_monthly"] * 100),
                currency="cad",
                recurring={"interval": "month"},
                tax_behavior="inclusive",
            )
            await _db.service_catalog.update_one(
                {"service_id": body.service_id},
                {"$set": {
                    product_field: new_product.id,
                    price_field: new_price.id,
                    "stripe_product_id": new_product.id,
                    "stripe_price_id": new_price.id,
                    "stripe_active_mode": _mode,
                }},
            )
            return new_price.id

        if not price_id:
            price_id = await _mint_fresh_site_mon_price()
        else:
            try:
                stripe_lib.Price.retrieve(price_id)
            except stripe_lib.error.InvalidRequestError as e:
                if "No such price" in str(e):
                    logger.warning(
                        f"[site-monitor subscribe] cached {price_field}={price_id} "
                        f"not found in {_mode} mode — re-minting"
                    )
                    price_id = await _mint_fresh_site_mon_price()
                else:
                    raise
        origin = (body.origin_url or "https://aurem.live").rstrip("/")
        # iter 280.8: gate automatic_tax behind env flag (default OFF)
        _site_mon_kwargs = dict(
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=f"{origin}/my/monitor?upgrade_success={body.service_id}&session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{origin}/my/monitor?upgrade_cancel={body.service_id}",
            customer_email=user["email"],
            allow_promotion_codes=True,
            metadata={
                "service_id": body.service_id,
                "tenant_bin": user.get("bin", ""),
                "user_email": user["email"],
                "type": "site_monitor_upgrade",
            },
        )
        if os.environ.get("STRIPE_AUTOMATIC_TAX", "").strip().lower() in ("1", "true", "yes", "on"):
            _site_mon_kwargs["automatic_tax"] = {"enabled": True}
        session = stripe_lib.checkout.Session.create(**_site_mon_kwargs)
        # Log pending subscription
        import uuid as _uuid
        await _db.customer_subscriptions.insert_one({
            "sub_id": f"sub_{_uuid.uuid4().hex[:14]}",
            "tenant_bin": user.get("bin", ""),
            "email": user["email"],
            "service_id": body.service_id,
            "service_name": svc["name"],
            "price_monthly": svc["price_monthly"],
            "status": "pending",
            "stripe_session_id": session.id,
            "started_at": datetime.now(timezone.utc).isoformat(),
        })
        return {"ok": True, "url": session.url, "session_id": session.id}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[upgrade] failed: {e}")
        raise HTTPException(500, f"checkout failed: {e}")


class AlertPhoneBody(BaseModel):
    phone: str = Field(..., min_length=6, max_length=25)


@router.get("/api/site-monitor/me/alert-phone")
async def me_get_alert_phone(request: Request):
    """Return current WhatsApp/SMS alert phone and whether plan supports it."""
    user = await _require_platform_user(request)
    from services.site_monitor import _resolve_alert_phone, _plan_features
    phone = await _resolve_alert_phone(user["email"])
    feats = await _plan_features(user["email"])
    return {
        "ok": True,
        "phone": phone,
        "whatsapp_enabled": "whatsapp_alerts" in feats,
        "sms_enabled": "sms_alerts" in feats,
        "plan_features": feats,
    }


@router.post("/api/site-monitor/me/alert-phone")
async def me_set_alert_phone(body: AlertPhoneBody, request: Request):
    """Set the WhatsApp/SMS alert phone on the tenant's profile."""
    user = await _require_platform_user(request)
    phone = (body.phone or "").strip()
    if not phone:
        raise HTTPException(400, "phone required")
    # Normalize via twilio helper (best-effort)
    try:
        from services.twilio_service import normalize_phone_number
        norm = normalize_phone_number(phone) or phone
    except Exception:
        norm = phone
    if _db is None:
        raise HTTPException(503, "db not ready")
    await _db.platform_users.update_one(
        {"email": user["email"]},
        {"$set": {"alert_phone": norm, "alert_phone_updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    return {"ok": True, "phone": norm}


@router.post("/api/site-monitor/me/test-whatsapp")
async def me_test_whatsapp(request: Request):
    """Send a test WhatsApp alert to verify wiring (plan-gated)."""
    user = await _require_platform_user(request)
    from services.site_monitor import _resolve_alert_phone, _plan_features
    feats = await _plan_features(user["email"])
    if "whatsapp_alerts" not in feats:
        raise HTTPException(402, "whatsapp_alerts not enabled on your plan. Upgrade to Site Monitor Pro or Enterprise.")
    phone = await _resolve_alert_phone(user["email"])
    if not phone:
        raise HTTPException(400, "no alert phone configured — POST /api/site-monitor/me/alert-phone first")
    try:
        from services.twilio_service import send_whatsapp_message
        msg = (
            "✅ AUREM Site Monitor — test alert.\n\n"
            "WhatsApp alerts are wired up correctly. "
            "You'll get downtime + recovery pings here when your sites blip."
        )
        res = await send_whatsapp_message(phone, msg)
        return {"ok": bool(res.get("success")), "result": res, "phone": phone}
    except Exception as e:
        logger.exception(f"[test-whatsapp] failed: {e}")
        raise HTTPException(500, f"send failed: {e}")


# ═════════════════════════════════════════════════════════════════════
# Public — Trust Badge + Status Page (VIRAL + TRUST signals, no auth)
# ═════════════════════════════════════════════════════════════════════
@router.get("/api/public/site-monitor/status/{bin}")
async def public_status_page(bin: str):
    """Tenant-scoped public status page JSON. No auth required — shareable trust signal."""
    if _db is None:
        raise HTTPException(503, "db not ready")

    # Find tenant by bin
    endpoints = [d async for d in _db.site_monitor_endpoints.find(
        {"bin": bin, "active": True}, {"_id": 0}
    )]
    if not endpoints:
        raise HTTPException(404, "status page not found for this BIN")

    email = endpoints[0].get("email", "")
    # Resolve tenant display name (platform_users or users)
    user = await _db.platform_users.find_one({"email": email}, {"_id": 0, "full_name": 1, "company_name": 1})
    if not user:
        user = await _db.users.find_one({"email": email}, {"_id": 0, "full_name": 1, "first_name": 1, "company_name": 1})
    business_name = (user or {}).get("company_name") or (user or {}).get("full_name") or email.split("@")[0]

    # 30-day aggregate stats
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    pipeline = [
        {"$match": {"email": email, "ts": {"$gte": cutoff}}},
        {"$group": {
            "_id": "$endpoint_id",
            "url": {"$last": "$url"},
            "total": {"$sum": 1},
            "passed": {"$sum": {"$cond": [{"$eq": ["$passed", True]}, 1, 0]}},
            "avg_latency_ms": {"$avg": "$latency_ms"},
            "last_ts": {"$last": "$ts"},
            "last_passed": {"$last": "$passed"},
            "last_status": {"$last": "$status_code"},
        }},
    ]
    try:
        stats_by_ep = {d["_id"]: d async for d in _db.site_monitor_logs.aggregate(pipeline)}
    except Exception:
        stats_by_ep = {}

    out_endpoints = []
    total_pings = 0
    total_passed = 0
    for ep in endpoints:
        s = stats_by_ep.get(ep["endpoint_id"], {})
        total_pings += s.get("total", 0)
        total_passed += s.get("passed", 0)
        uptime = round(s.get("passed", 0) / max(s.get("total", 1), 1) * 100, 2) if s.get("total") else None
        out_endpoints.append({
            "url": ep["url"],
            "label": ep.get("label") or ep["url"],
            "uptime_30d_pct": uptime,
            "avg_latency_ms": round(s.get("avg_latency_ms") or 0, 1) if s else 0,
            "last_status": s.get("last_status"),
            "last_passed": s.get("last_passed"),
            "last_check": s.get("last_ts"),
        })

    overall_uptime = round(total_passed / max(total_pings, 1) * 100, 2) if total_pings else None

    # Open incident count
    open_incidents = await _db.site_monitor_incidents.count_documents({
        "email": email, "status": "open"
    })

    return {
        "ok": True,
        "bin": bin,
        "business_name": business_name,
        "overall_uptime_30d_pct": overall_uptime,
        "total_pings_30d": total_pings,
        "open_incidents": open_incidents,
        "endpoints": out_endpoints,
        "powered_by": "AUREM",
        "powered_by_url": "https://aurem.live/monitor-free",
    }


@router.get("/api/public/site-monitor/badge-data/{bin}")
async def public_badge_data(bin: str):
    """Lightweight badge data — returns uptime % + status for the floating badge JS."""
    if _db is None:
        raise HTTPException(503, "db not ready")
    endpoints = [d async for d in _db.site_monitor_endpoints.find(
        {"bin": bin, "active": True}, {"_id": 0, "endpoint_id": 1, "email": 1}
    )]
    if not endpoints:
        return {"ok": False, "error": "not_found"}
    email = endpoints[0]["email"]

    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    total = await _db.site_monitor_logs.count_documents({"email": email, "ts": {"$gte": cutoff}})
    passed = await _db.site_monitor_logs.count_documents({"email": email, "ts": {"$gte": cutoff}, "passed": True})
    uptime = round(passed / max(total, 1) * 100, 2) if total else 100.0

    open_inc = await _db.site_monitor_incidents.count_documents({"email": email, "status": "open"})
    status = "up" if open_inc == 0 else "down"

    return {
        "ok": True,
        "bin": bin,
        "uptime_pct": uptime,
        "status": status,
        "endpoints_count": len(endpoints),
    }


# ═════════════════════════════════════════════════════════════════════
# Admin
# ═════════════════════════════════════════════════════════════════════
@router.get("/api/admin/site-monitor/overview")
async def admin_overview_endpoint(request: Request):
    await _require_admin(request)
    from services.site_monitor import admin_overview
    return {"ok": True, "overview": await admin_overview()}


@router.get("/api/admin/site-monitor/tenants")
async def admin_list_tenants_endpoint(request: Request, limit: int = Query(200, ge=1, le=1000)):
    await _require_admin(request)
    from services.site_monitor import admin_list_tenants
    tenants = await admin_list_tenants(limit)
    return {"ok": True, "count": len(tenants), "tenants": tenants}


@router.post("/api/admin/site-monitor/scan-now")
async def admin_scan_now(request: Request):
    await _require_admin(request)
    from services.site_monitor import run_scan_tick
    result = await run_scan_tick()
    return {"ok": True, **result}
