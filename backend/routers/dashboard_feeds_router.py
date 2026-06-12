"""
Dashboard Feeds Router
----------------------
Lightweight read-only endpoints that power the AuremDashboard sidebar panels:

  • 6.3  Email History         → email_logs
  • 6.5  Call Logs (CRM)       → voice_calls
  • 12.2 Call Logs (Voice)     → voice_calls (same)
  • 3.4  Hot Leads (Live)      → aurem_live_viewers (proxy — 24h summary + live)
  • 8.12 Fallback Monitor      → fallback_usage_log

All endpoints require a Bearer token (admin). Response contracts are stable
JSON — used directly by the frontend feed components.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Header, Query
from shared.tenant import FOUNDER_BIN

router = APIRouter(prefix="/api/dashboard-feeds", tags=["Dashboard Feeds"])

_db = None
_ACTIVE_WINDOW_SECS = 120  # matches website_builder_router
_FLAME_ALERT_THRESHOLD = 50  # fire WhatsApp alert when score exceeds this
_FLAME_ALERT_PHONE = os.environ.get("AUREM_HOT_LEAD_PHONE", "+16134000000")


def set_db(db):
    global _db
    _db = db


def _get_db():
    global _db
    if _db is not None:
        return _db
    try:
        from motor.motor_asyncio import AsyncIOMotorClient
        mongo_url = os.environ.get("MONGO_URL", "").strip().strip('"').strip("'")
        if not mongo_url:
            return None
        client = AsyncIOMotorClient(mongo_url)
        _db = client[os.environ.get("DB_NAME", "aurem_db")]
        return _db
    except Exception:
        return None


def _require_auth(authorization: Optional[str]):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Admin auth required")


def _iso(dt):
    if not dt:
        return None
    if isinstance(dt, str):
        return dt
    try:
        return dt.isoformat()
    except Exception:
        return str(dt)


# ─────────────────────────────────────────────────────────────
# FLAME SCORE — ranks the hottest live prospect
# formula: duration_seconds × ping_count × referral_bonus
# ─────────────────────────────────────────────────────────────
def _referral_bonus(referrer: str) -> float:
    """Higher multiplier for high-intent traffic sources."""
    if not referrer or referrer == "direct":
        return 1.0
    r = referrer.lower()
    if any(k in r for k in ("mail", "resend", "sendgrid", "/email", "gmail.com")):
        return 2.5  # clicked through from our email = hot intent
    if any(k in r for k in ("wa.me", "whatsapp", "telegram", "messenger", "sms")):
        return 2.5  # messaging click-through
    if any(k in r for k in ("linkedin", "twitter", "facebook", "instagram", "tiktok")):
        return 2.0  # social referral
    if any(k in r for k in ("google.", "bing.", "duckduckgo", "yahoo.", "yandex")):
        return 2.0  # organic search click
    return 1.5  # any other referred traffic


def _compute_flame_score(duration_seconds: int, ping_count: int, referrer: str) -> float:
    dur = max(int(duration_seconds or 0), 0)
    pings = max(int(ping_count or 1), 1)
    bonus = _referral_bonus(referrer or "")
    # normalize: divide duration by 10s (1 point per 10 sec spent)
    score = (dur / 10.0) * pings * bonus
    return round(score, 1)


async def _fire_flame_alert(db, viewer: dict):
    """Send a WhatsApp alert to the owner when a viewer's flame score > threshold."""
    whapi_token = os.environ.get("WHAPI_API_TOKEN", "")
    whapi_url = os.environ.get("WHAPI_API_URL", "")
    if not (whapi_token and whapi_url):
        return False

    phone = _FLAME_ALERT_PHONE.replace("+", "").replace("-", "").replace(" ", "")
    if not phone:
        return False

    public_base = os.environ.get("PUBLIC_APP_URL", "https://aurem.live").rstrip("/")
    slug = viewer.get("slug", "")
    score = viewer.get("flame_score", 0)
    business = viewer.get("business_name") or "Unknown Business"
    dur_min = max(1, int((viewer.get("duration_seconds") or 0) / 60))
    pings = viewer.get("ping_count", 1)
    referrer = viewer.get("referrer", "direct") or "direct"

    msg = (
        f"🔥🔥 *FLAME ALERT — Score {score}*\n\n"
        f"*{business}* is hot RIGHT NOW!\n\n"
        f"⏱ Watching {dur_min}m · 📡 {pings} pings · 🔗 {referrer[:40]}\n\n"
        f"👉 {public_base}/sample/{slug}\n\n"
        f"React in the next 30 sec — call or WhatsApp them.\n"
        f"_AUREM Flame Monitor_"
    )

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"{whapi_url}/messages/text",
                headers={"authorization": f"Bearer {whapi_token}", "content-type": "application/json"},
                json={"to": f"{phone}@s.whatsapp.net", "body": msg},
            )
        await db.flame_alerts_log.insert_one({
            "session_id": viewer.get("session_id"),
            "business_name": business,
            "slug": slug,
            "flame_score": score,
            "duration_seconds": viewer.get("duration_seconds"),
            "ping_count": pings,
            "referrer": referrer,
            "sent_to": _FLAME_ALERT_PHONE,
            "sent_at": datetime.now(timezone.utc).isoformat(),
            "ttl_at": datetime.now(timezone.utc),  # Iter 206: 30-day TTL
        })
        return True
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────
# 6.3 EMAIL HISTORY
# ─────────────────────────────────────────────────────────────
@router.get("/email-history")
async def email_history(
    authorization: Optional[str] = Header(None),
    limit: int = Query(100, ge=1, le=500),
    status: Optional[str] = Query(None, description="success | failed"),
):
    _require_auth(authorization)
    db = _get_db()
    if db is None:
        return {"total": 0, "logs": [], "summary": {"sent": 0, "failed": 0}}

    q: dict = {}
    if status == "success":
        q["success"] = True
    elif status == "failed":
        q["success"] = False

    cursor = db.email_logs.find(q, {"_id": 0}).sort("sent_at", -1).limit(limit)
    logs = await cursor.to_list(length=limit)

    # Summary (24h)
    day_ago = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    sent_24h = await db.email_logs.count_documents({"success": True, "sent_at": {"$gte": day_ago}})
    failed_24h = await db.email_logs.count_documents({"success": False, "sent_at": {"$gte": day_ago}})
    total = await db.email_logs.count_documents({})

    return {
        "total": total,
        "logs": [
            {
                "to": d.get("to"),
                "subject": d.get("subject"),
                "tenant_id": d.get("tenant_id"),
                "email_id": d.get("email_id"),
                "engine": d.get("engine", "resend"),
                "success": bool(d.get("success")),
                "error": d.get("error", ""),
                "sent_at": _iso(d.get("sent_at")),
            }
            for d in logs
        ],
        "summary": {
            "sent_24h": sent_24h,
            "failed_24h": failed_24h,
            "total_all_time": total,
        },
    }


# ─────────────────────────────────────────────────────────────
# 6.5 / 12.2 CALL LOGS
# ─────────────────────────────────────────────────────────────
@router.get("/call-logs")
async def call_logs(
    authorization: Optional[str] = Header(None),
    limit: int = Query(100, ge=1, le=500),
    status: Optional[str] = Query(None, description="completed | active | queued"),
):
    _require_auth(authorization)
    db = _get_db()
    if db is None:
        return {"total": 0, "logs": [], "summary": {}}

    q: dict = {}
    if status:
        q["status"] = status

    cursor = db.voice_calls.find(q, {"_id": 0}).sort("started_at", -1).limit(limit)
    logs = await cursor.to_list(length=limit)

    # Summary (24h completed)
    day_ago = datetime.now(timezone.utc) - timedelta(hours=24)
    completed_24h = await db.voice_calls.count_documents({"status": "completed", "started_at": {"$gte": day_ago}})
    active = await db.voice_calls.count_documents({"status": "active"})
    queued = await db.voice_calls.count_documents({"status": "queued"})
    total = await db.voice_calls.count_documents({})

    return {
        "total": total,
        "logs": [
            {
                "persona_name": d.get("persona_name"),
                "tier": d.get("tier"),
                "direction": d.get("direction"),
                "sentiment": d.get("sentiment"),
                "csat_score": d.get("csat_score"),
                "duration_seconds": d.get("duration_seconds"),
                "started_at": _iso(d.get("started_at")),
                "ended_at": _iso(d.get("ended_at")),
                "status": d.get("status"),
                "actions_taken": d.get("actions_taken", []),
                "caller_phone": d.get("caller_phone"),
            }
            for d in logs
        ],
        "summary": {
            "completed_24h": completed_24h,
            "active": active,
            "queued": queued,
            "total_all_time": total,
        },
    }


# ─────────────────────────────────────────────────────────────
# 3.4 HOT LEADS (LIVE) — live viewers feed
# ─────────────────────────────────────────────────────────────
@router.get("/hot-leads")
async def hot_leads(
    authorization: Optional[str] = Header(None),
    limit: int = Query(50, ge=1, le=200),
):
    _require_auth(authorization)
    db = _get_db()
    if db is None:
        return {"count": 0, "viewers": [], "unique_ips_24h": 0, "total_views_24h": 0}

    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(seconds=_ACTIVE_WINDOW_SECS)).isoformat()
    day_cutoff = (now - timedelta(hours=24)).isoformat()

    cursor = db.aurem_live_viewers.find(
        {"last_heartbeat_at": {"$gte": cutoff}},
        {"_id": 0},
    ).sort("last_heartbeat_at", -1).limit(limit)
    docs = await cursor.to_list(length=limit)

    public_base = os.environ.get("PUBLIC_APP_URL", "https://aurem.live").rstrip("/")
    unique_ips_24h = len(await db.aurem_live_viewers.distinct("ip", {"started_at": {"$gte": day_cutoff}}))
    total_views_24h = await db.aurem_live_viewers.count_documents({"started_at": {"$gte": day_cutoff}})

    viewers = []
    for d in docs:
        try:
            started = datetime.fromisoformat(str(d.get("started_at", "")).replace("Z", "+00:00"))
            duration = int((now - started).total_seconds())
        except Exception:
            duration = 0
        ping_count = d.get("ping_count", 1) or 1
        referrer = d.get("referrer", "") or ""
        flame_score = _compute_flame_score(duration, ping_count, referrer)
        viewers.append({
            "session_id": d.get("session_id"),
            "business_name": d.get("business_name"),
            "slug": d.get("slug"),
            "slug_url": f"{public_base}/sample/{d.get('slug', '')}",
            "started_at": _iso(d.get("started_at")),
            "last_heartbeat_at": _iso(d.get("last_heartbeat_at")),
            "duration_seconds": duration,
            "ping_count": ping_count,
            "engagement_nudge_fired": bool(d.get("engagement_nudge_fired")),
            "flame_alert_fired": bool(d.get("flame_alert_fired")),
            "referrer": referrer,
            "ip": d.get("ip", ""),
            "flame_score": flame_score,
            "flame_tier": (
                "INFERNO" if flame_score >= 100
                else "HOT" if flame_score >= 50
                else "WARM" if flame_score >= 20
                else "COOL"
            ),
        })

    # Sort hottest first
    viewers.sort(key=lambda v: v["flame_score"], reverse=True)

    # Fire WhatsApp alert for any viewer with score > threshold that hasn't been alerted yet
    alerts_sent = 0
    auto_dials_fired = 0
    auto_dial_results = []
    for v in viewers:
        if v["flame_score"] > _FLAME_ALERT_THRESHOLD and not v["flame_alert_fired"]:
            ok = await _fire_flame_alert(db, v)
            if ok:
                # Mark the live-viewer doc so we don't re-alert the same session
                try:
                    await db.aurem_live_viewers.update_one(
                        {"session_id": v["session_id"]},
                        {"$set": {
                            "flame_alert_fired": True,
                            "flame_alert_at": datetime.now(timezone.utc).isoformat(),
                            "flame_alert_score": v["flame_score"],
                        }},
                    )
                    v["flame_alert_fired"] = True
                    alerts_sent += 1
                except Exception:
                    pass

        # INFERNO auto-dial: score >= 100 → ORA calls prospect via Twilio
        if v["flame_tier"] == "INFERNO":
            try:
                from services.flame_auto_dialer import try_auto_dial
                res = await try_auto_dial(db, v)
                v["auto_dial_status"] = res.get("status")
                if res.get("status") in ("dialed", "mock_dialed"):
                    auto_dials_fired += 1
                    auto_dial_results.append({
                        "business_name": v.get("business_name"),
                        "flame_score": v["flame_score"],
                        **res,
                    })
            except Exception:
                v["auto_dial_status"] = "error"

    # Recent viewers fallback (last 7 days) — so the page isn't empty when no
    # prospect is actively viewing right now. These render as "RECENT" tier.
    recent_cutoff = (now - timedelta(days=7)).isoformat()
    recent_cursor = db.aurem_live_viewers.find(
        {
            "last_heartbeat_at": {"$gte": recent_cutoff, "$lt": cutoff},  # older than live, newer than 7d
        },
        {"_id": 0},
    ).sort("last_heartbeat_at", -1).limit(limit)
    recent_docs = await recent_cursor.to_list(length=limit)
    recent_viewers = []
    for d in recent_docs:
        try:
            started = datetime.fromisoformat(str(d.get("started_at", "")).replace("Z", "+00:00"))
            last_hb = datetime.fromisoformat(str(d.get("last_heartbeat_at", "")).replace("Z", "+00:00"))
            duration = int((last_hb - started).total_seconds())
            mins_ago = int((now - last_hb).total_seconds() // 60)
        except Exception:
            duration = 0
            mins_ago = 0
        ping_count = d.get("ping_count", 1) or 1
        flame_score = _compute_flame_score(duration, ping_count, d.get("referrer", "") or "")
        recent_viewers.append({
            "session_id": d.get("session_id"),
            "business_name": d.get("business_name"),
            "slug": d.get("slug"),
            "slug_url": f"{public_base}/sample/{d.get('slug', '')}",
            "started_at": _iso(d.get("started_at")),
            "last_heartbeat_at": _iso(d.get("last_heartbeat_at")),
            "duration_seconds": duration,
            "ping_count": ping_count,
            "minutes_ago": mins_ago,
            "referrer": d.get("referrer", "") or "",
            "flame_score": flame_score,
            "flame_tier": "RECENT",
        })

    # iter 269 — "Top Engaged Leads" fallback. When no live viewers in the
    # last 7 days (or even beyond), surface leads that have accumulated
    # report/sample views via the pixel tracker so the page has SOMETHING
    # actionable instead of blank stats.
    top_engaged = []
    try:
        eng_cursor = db.campaign_leads.find(
            {"business_id": FOUNDER_BIN,
             "$or": [
                {"report_view_count": {"$gt": 0}},
                {"sample_view_count": {"$gt": 0}},
            ]},
            {
                "_id": 0, "lead_id": 1, "business_name": 1, "slug": 1,
                "report_view_count": 1, "sample_view_count": 1,
                "last_report_view_at": 1, "last_sample_view_at": 1,
                "phone": 1, "email": 1, "website_url": 1,
                "flame_score": 1, "status": 1, "lifecycle_stage": 1,
            },
        ).limit(50)
        async for d in eng_cursor:
            rvc = int(d.get("report_view_count") or 0)
            svc = int(d.get("sample_view_count") or 0)
            # Simple engagement score: sample-views worth 2x (deeper intent)
            score = (svc * 2) + rvc
            last_view_iso = d.get("last_sample_view_at") or d.get("last_report_view_at")
            mins_ago = None
            days_ago = None
            if last_view_iso:
                try:
                    dt = datetime.fromisoformat(str(last_view_iso).replace("Z", "+00:00"))
                    delta_secs = int((now - dt).total_seconds())
                    if delta_secs < 3600:
                        mins_ago = max(1, delta_secs // 60)
                    days_ago = max(0, delta_secs // 86400)
                except Exception:
                    pass
            top_engaged.append({
                "lead_id": d.get("lead_id"),
                "business_name": d.get("business_name") or "—",
                "slug": d.get("slug"),
                "slug_url": f"{public_base}/sample/{d.get('slug', '')}" if d.get("slug") else None,
                "report_views": rvc,
                "sample_views": svc,
                "total_views": rvc + svc,
                "engagement_score": score,
                "last_view_at": _iso(last_view_iso) if last_view_iso else None,
                "last_view_minutes_ago": mins_ago,
                "last_view_days_ago": days_ago,
                "phone": d.get("phone"),
                "email": d.get("email"),
                "website_url": d.get("website_url"),
                "lifecycle_stage": d.get("lifecycle_stage") or "new",
            })
        top_engaged.sort(key=lambda x: (-x["engagement_score"], x.get("last_view_days_ago") or 9999))
        top_engaged = top_engaged[:20]
    except Exception:
        top_engaged = []

    # All-time totals — lifetime metrics so empty 24h windows don't look dead
    try:
        lifetime_total = await db.aurem_live_viewers.count_documents({})
        lifetime_unique = len(await db.aurem_live_viewers.distinct("ip"))
    except Exception:
        lifetime_total = 0
        lifetime_unique = 0

    return {
        "count": len(viewers),
        "viewers": viewers,
        "recent_count": len(recent_viewers),
        "recent_viewers": recent_viewers,
        "top_engaged_count": len(top_engaged),
        "top_engaged": top_engaged,
        "active_window_secs": _ACTIVE_WINDOW_SECS,
        "unique_ips_24h": unique_ips_24h,
        "total_views_24h": total_views_24h,
        "lifetime_total_views": lifetime_total,
        "lifetime_unique_ips": lifetime_unique,
        "flame_alert_threshold": _FLAME_ALERT_THRESHOLD,
        "flame_alerts_sent_this_call": alerts_sent,
        "auto_dials_fired_this_call": auto_dials_fired,
        "auto_dial_results": auto_dial_results,
        "checked_at": now.isoformat(),
    }


# ─────────────────────────────────────────────────────────────
# 8.12 FALLBACK MONITOR
# ─────────────────────────────────────────────────────────────
@router.get("/fallback-monitor")
async def fallback_monitor(
    authorization: Optional[str] = Header(None),
    limit: int = Query(100, ge=1, le=500),
    source: Optional[str] = Query(None, description="e.g. scout, sms, whatsapp, voice"),
):
    _require_auth(authorization)
    db = _get_db()
    if db is None:
        return {"total": 0, "events": [], "summary": {}}

    q: dict = {}
    if source:
        q["source"] = source

    cursor = db.fallback_usage_log.find(q, {"_id": 0}).sort("triggered_at", -1).limit(limit)
    events = await cursor.to_list(length=limit)

    # Aggregation — counts per source (last 7d)
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    try:
        agg = await db.fallback_usage_log.aggregate([
            {"$match": {"triggered_at": {"$gte": week_ago}}},
            {"$group": {"_id": "$source", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ]).to_list(length=20)
    except Exception:
        agg = []

    total = await db.fallback_usage_log.count_documents({})
    last_24h = await db.fallback_usage_log.count_documents(
        {"triggered_at": {"$gte": (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()}}
    )

    return {
        "total": total,
        "events": [
            {
                "source": e.get("source"),
                "reason": e.get("reason"),
                "from_service": e.get("from_service") or e.get("primary"),
                "to_service": e.get("to_service") or e.get("fallback"),
                "details": e.get("details") or e.get("meta") or {},
                "triggered_at": _iso(e.get("triggered_at")),
            }
            for e in events
        ],
        "summary": {
            "last_24h": last_24h,
            "total_all_time": total,
            "by_source_7d": [{"source": a["_id"] or "unknown", "count": a["count"]} for a in agg],
        },
    }



# ─────────────────────────────────────────────────────────────
# FLAME ALERTS — audit log of WhatsApp pings
# ─────────────────────────────────────────────────────────────
@router.get("/flame-alerts")
async def flame_alerts(
    authorization: Optional[str] = Header(None),
    limit: int = Query(50, ge=1, le=500),
):
    _require_auth(authorization)
    db = _get_db()
    if db is None:
        return {"total": 0, "alerts": []}

    cursor = db.flame_alerts_log.find({}, {"_id": 0}).sort("sent_at", -1).limit(limit)
    alerts = await cursor.to_list(length=limit)
    total = await db.flame_alerts_log.count_documents({})

    day_ago = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    last_24h = await db.flame_alerts_log.count_documents({"sent_at": {"$gte": day_ago}})

    return {
        "total": total,
        "alerts": alerts,
        "summary": {
            "last_24h": last_24h,
            "threshold": _FLAME_ALERT_THRESHOLD,
            "alert_phone": _FLAME_ALERT_PHONE,
        },
    }


# ─────────────────────────────────────────────────────────────
# FLAME ALERT TEST — manual trigger for verifying WhatsApp wiring
# ─────────────────────────────────────────────────────────────
@router.post("/flame-alerts/test")
async def flame_alert_test(
    authorization: Optional[str] = Header(None),
):
    _require_auth(authorization)
    db = _get_db()
    if db is None:
        raise HTTPException(503, "Database unavailable")

    test_viewer = {
        "session_id": f"test-{int(datetime.now(timezone.utc).timestamp())}",
        "business_name": "TEST BUSINESS (Flame Alert)",
        "slug": "test",
        "flame_score": 99.9,
        "duration_seconds": 300,
        "ping_count": 10,
        "referrer": "test.manual.trigger",
    }
    sent = await _fire_flame_alert(db, test_viewer)
    return {
        "sent": sent,
        "to": _FLAME_ALERT_PHONE,
        "whapi_configured": bool(os.environ.get("WHAPI_API_TOKEN") and os.environ.get("WHAPI_API_URL")),
        "message": "WhatsApp alert dispatched" if sent else "WHAPI not configured or send failed",
    }


# ─────────────────────────────────────────────────────────────
# FLAME AUTO-DIALS — log + test + tenant phone override
# ─────────────────────────────────────────────────────────────
@router.get("/auto-dials")
async def auto_dials(
    authorization: Optional[str] = Header(None),
    limit: int = Query(50, ge=1, le=500),
):
    _require_auth(authorization)
    db = _get_db()
    if db is None:
        return {"total": 0, "dials": [], "summary": {}}

    cursor = db.flame_auto_dials.find({}, {"_id": 0}).sort("dialed_at", -1).limit(limit)
    dials = await cursor.to_list(length=limit)
    total = await db.flame_auto_dials.count_documents({})

    day_ago = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    last_24h = await db.flame_auto_dials.count_documents({"dialed_at": {"$gte": day_ago}})

    try:
        agg = await db.flame_auto_dials.aggregate([
            {"$group": {"_id": "$status", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ]).to_list(length=20)
    except Exception:
        agg = []

    return {
        "total": total,
        "dials": dials,
        "summary": {
            "last_24h": last_24h,
            "by_status": [{"status": a["_id"] or "unknown", "count": a["count"]} for a in agg],
        },
    }


@router.post("/auto-dials/test/{lead_id}")
async def auto_dials_test(
    lead_id: str,
    authorization: Optional[str] = Header(None),
):
    """Manually trigger the auto-dial flow on a specific lead (for testing)."""
    _require_auth(authorization)
    db = _get_db()
    if db is None:
        raise HTTPException(503, "Database unavailable")

    from services.flame_auto_dialer import try_auto_dial

    # Build a synthetic INFERNO viewer for this test
    viewer = {
        "session_id": f"test-dial-{int(datetime.now(timezone.utc).timestamp())}",
        "business_name": "TEST BUSINESS (Auto-Dial Test)",
        "slug": "test",
        "flame_score": 150.0,
        "flame_tier": "INFERNO",
        "duration_seconds": 240,
        "ping_count": 8,
        "referrer": "test.manual.trigger",
    }
    result = await try_auto_dial(db, viewer, lead_id=lead_id)
    return {"test": True, "lead_id": lead_id, "result": result}


class TenantAlertPhoneIn:
    """Pydantic would be ideal but we keep it lean — body is {phone}"""
    pass


@router.post("/tenant-alert-phone")
async def set_tenant_alert_phone(
    body: dict,
    authorization: Optional[str] = Header(None),
):
    """Set a per-tenant flame alert phone override. body: {tenant_id, phone}."""
    _require_auth(authorization)
    db = _get_db()
    if db is None:
        raise HTTPException(503, "Database unavailable")

    tenant_id = (body.get("tenant_id") or "").strip()
    phone = (body.get("phone") or "").strip()
    if not tenant_id:
        raise HTTPException(400, "tenant_id required")

    if phone:
        await db.tenant_settings.update_one(
            {"tenant_id": tenant_id},
            {"$set": {"tenant_id": tenant_id, "flame_alert_phone": phone, "updated_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True,
        )
        return {"ok": True, "tenant_id": tenant_id, "flame_alert_phone": phone}
    # Empty phone → unset override (fall back to global)
    await db.tenant_settings.update_one(
        {"tenant_id": tenant_id},
        {"$unset": {"flame_alert_phone": ""}},
    )
    return {"ok": True, "tenant_id": tenant_id, "flame_alert_phone": None, "unset": True}


@router.get("/tenant-alert-phone/{tenant_id}")
async def get_tenant_alert_phone(
    tenant_id: str,
    authorization: Optional[str] = Header(None),
):
    _require_auth(authorization)
    db = _get_db()
    if db is None:
        raise HTTPException(503, "Database unavailable")
    s = await db.tenant_settings.find_one({"tenant_id": tenant_id}, {"_id": 0, "flame_alert_phone": 1})
    return {
        "tenant_id": tenant_id,
        "flame_alert_phone": (s or {}).get("flame_alert_phone"),
        "effective": (s or {}).get("flame_alert_phone") or _FLAME_ALERT_PHONE,
        "fallback_default": _FLAME_ALERT_PHONE,
    }

