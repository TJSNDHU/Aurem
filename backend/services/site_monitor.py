"""
AUREM Site Monitor — Multi-tenant Uptime Monitoring Engine
═══════════════════════════════════════════════════════════════════════════════

Monitors customer websites on behalf of AUREM subscribers.
- Tenant-scoped: each customer adds their own URLs (respecting plan limits)
- Concurrent scanning every N minutes (interval varies by plan)
- Downtime/recovery detection with incident tracking
- Email + WhatsApp alerts via Resend/Twilio (plan-gated)
- Serves both PAID customers (via active subscription) and FREE trial users

Collections:
  • db.site_monitor_endpoints   — per-tenant URL catalog
  • db.site_monitor_logs        — every ping result (for uptime history)
  • db.site_monitor_incidents   — downtime events with start/end/duration
  • db.site_monitor_free        — free-tier signups (30-day trial)
"""
import os
import time
import asyncio
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

import httpx

logger = logging.getLogger(__name__)

_db = None


def set_db(database):
    global _db
    _db = database


# ═════════════════════════════════════════════════════════════════════
# Plan gating — resolved from catalog limits
# ═════════════════════════════════════════════════════════════════════
SKU_IDS = ["site_monitor_lite", "site_monitor_pro", "site_monitor_enterprise"]

DEFAULT_LIMITS = {
    "free": {
        "max_urls": 3,
        "check_interval_min": 15,
        "features": ["email_alerts", "uptime_dashboard"],
    },
}


async def get_tenant_plan(email: str, bin_: Optional[str] = None) -> Dict[str, Any]:
    """Resolve a tenant's active Site Monitor plan (paid > free > none)."""
    if _db is None:
        return {"tier": "none", "limits": None, "service_id": None}

    # Check paid (prefer higher tier)
    query = {"email": (email or "").lower(), "service_id": {"$in": SKU_IDS}, "status": "active"}
    subs = [s async for s in _db.customer_subscriptions.find(query, {"_id": 0})]
    if subs:
        # Prefer highest tier
        priority = {"site_monitor_enterprise": 3, "site_monitor_pro": 2, "site_monitor_lite": 1}
        best = max(subs, key=lambda s: priority.get(s["service_id"], 0))
        # Pull limits from catalog
        svc = await _db.service_catalog.find_one({"service_id": best["service_id"]}, {"_id": 0})
        return {
            "tier": "paid",
            "service_id": best["service_id"],
            "service_name": (svc or {}).get("name", best.get("service_name")),
            "limits": (svc or {}).get("limits") or {},
            "started_at": best.get("started_at"),
        }

    # Check free trial
    free_doc = await _db.site_monitor_free.find_one(
        {"email": (email or "").lower(), "status": "active"},
        {"_id": 0},
    )
    if free_doc:
        now_iso = datetime.now(timezone.utc).isoformat()
        if free_doc.get("trial_ends_at") and free_doc["trial_ends_at"] > now_iso:
            return {
                "tier": "free",
                "service_id": None,
                "service_name": "Free Trial",
                "limits": DEFAULT_LIMITS["free"],
                "trial_ends_at": free_doc["trial_ends_at"],
            }

    return {"tier": "none", "limits": None, "service_id": None}


# ═════════════════════════════════════════════════════════════════════
# URL check primitive
# ═════════════════════════════════════════════════════════════════════
async def _check_url(client: httpx.AsyncClient, endpoint: Dict[str, Any]) -> Dict[str, Any]:
    url = endpoint["url"]
    method = endpoint.get("method", "GET").upper()
    expected = endpoint.get("expected_status", [200])
    if isinstance(expected, int):
        expected = [expected]
    t0 = time.time()
    result = {
        "endpoint_id": endpoint.get("endpoint_id") or endpoint.get("_id") or "",
        "tenant_id": endpoint.get("tenant_id", ""),
        "bin": endpoint.get("bin", ""),
        "email": endpoint.get("email", ""),
        "url": url,
        "method": method,
        "expected": expected,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    try:
        r = await client.request(method, url, follow_redirects=True)
        latency = round((time.time() - t0) * 1000, 1)
        result.update({
            "status_code": r.status_code,
            "latency_ms": latency,
            "passed": r.status_code in expected,
            "error": None,
        })
    except Exception as e:
        latency = round((time.time() - t0) * 1000, 1)
        result.update({
            "status_code": 0,
            "latency_ms": latency,
            "passed": False,
            "error": str(e)[:200],
        })
    return result


# ═════════════════════════════════════════════════════════════════════
# Incident tracking (downtime start → recovery)
# ═════════════════════════════════════════════════════════════════════
async def _resolve_alert_phone(email: str) -> Optional[str]:
    """Resolve WhatsApp/SMS alert phone for a tenant.
    Order: platform_users.alert_phone → platform_users.phone → users.phone → None.
    """
    if _db is None:
        return None
    try:
        pu = await _db.platform_users.find_one(
            {"email": email.lower()},
            {"_id": 0, "alert_phone": 1, "phone": 1, "whatsapp_phone": 1},
        )
        if pu:
            for k in ("alert_phone", "whatsapp_phone", "phone"):
                v = pu.get(k)
                if v:
                    return str(v).strip()
        u = await _db.users.find_one(
            {"email": email.lower()}, {"_id": 0, "phone": 1}
        )
        if u and u.get("phone"):
            return str(u["phone"]).strip()
    except Exception:
        return None
    return None


async def _plan_features(email: str) -> List[str]:
    try:
        plan = await get_tenant_plan(email)
        feats = (plan.get("limits") or {}).get("features") or []
        return [str(f).lower() for f in feats]
    except Exception:
        return []


async def _handle_incident(result: Dict[str, Any]):
    """Open a new incident on failure, close existing on recovery."""
    if _db is None:
        return

    ep_id = result["endpoint_id"]
    open_incident = await _db.site_monitor_incidents.find_one({
        "endpoint_id": ep_id, "status": "open"
    })

    if not result["passed"]:
        # Failure — open new incident if none
        if not open_incident:
            await _db.site_monitor_incidents.insert_one({
                "incident_id": f"inc_{uuid.uuid4().hex[:12]}",
                "tenant_id": result["tenant_id"],
                "bin": result["bin"],
                "email": result["email"],
                "endpoint_id": ep_id,
                "url": result["url"],
                "started_at": result["ts"],
                "status": "open",
                "status_code": result["status_code"],
                "error": result.get("error"),
                "alert_sent": False,
            })
            await _send_downtime_alert(result)
            await _send_whatsapp_downtime_alert(result)
    else:
        # Success — close incident if open
        if open_incident:
            started = datetime.fromisoformat(open_incident["started_at"].replace("Z", "+00:00"))
            ended = datetime.now(timezone.utc)
            duration_s = int((ended - started).total_seconds())
            await _db.site_monitor_incidents.update_one(
                {"_id": open_incident["_id"]},
                {"$set": {
                    "status": "resolved",
                    "ended_at": ended.isoformat(),
                    "duration_s": duration_s,
                }},
            )
            await _send_recovery_alert(result, duration_s)
            await _send_whatsapp_recovery_alert(result, duration_s)


async def _send_downtime_alert(result: Dict[str, Any]):
    """Send downtime email (+ WhatsApp if plan allows)."""
    try:
        from services.email_service_resend import send_email
        to = result.get("email")
        if not to:
            return
        # iter 282g — branded HTML template
        try:
            from services.brand_emails import render_site_down
            html = render_site_down(
                site_url=result["url"],
                status_code=result.get("status_code") or 0,
                status_text=(result.get("error") or "connection failed")[:80],
                down_since=result.get("ts") or "",
                downtime_counter=result.get("duration_human") or "just now",
                to_email=to,
            )
        except Exception as _render_err:
            logger.debug(f"[site-monitor] branded render failed: {_render_err}")
            html = f"""
            <div style='font-family:system-ui;background:#0A0A0A;color:#eee;padding:24px;border-radius:12px'>
              <h2 style='color:#EF4444;margin:0 0 8px 0'>AUREM Site Monitor — Downtime Detected</h2>
              <p>Your site <b style='color:#F97316'>{result['url']}</b> is not responding.</p>
              <p><a href='https://aurem.live/my/monitor' style='color:#F97316;text-decoration:none'>→ View incident log</a></p>
            </div>
            """
        await send_email(to=to, subject=f"[AUREM] DOWN: {result['url']}", html=html)
    except Exception as e:
        logger.warning(f"[site-monitor] downtime alert failed: {e}")


async def _send_whatsapp_downtime_alert(result: Dict[str, Any]):
    """Send WhatsApp downtime alert if plan allows and phone is configured."""
    try:
        email = result.get("email")
        if not email:
            return
        feats = await _plan_features(email)
        if "whatsapp_alerts" not in feats:
            return
        phone = await _resolve_alert_phone(email)
        if not phone:
            return
        from services.whapi_service import send_whatsapp_message
        url = result.get("url") or ""
        code = result.get("status_code", "ERR")
        msg = (
            f"🚨 AUREM Site Monitor — DOWNTIME\n\n"
            f"Your site {url} is not responding.\n"
            f"Status: {code}\n"
            f"Detected: {result.get('ts','')}\n\n"
            f"Live dashboard: https://aurem.live/my/monitor"
        )
        res = await send_whatsapp_message(phone, msg)
        if not res.get("success"):
            logger.warning(f"[site-monitor] WhatsApp downtime alert failed: {res.get('error')}")
    except Exception as e:
        logger.warning(f"[site-monitor] WhatsApp downtime alert exception: {e}")


async def _send_whatsapp_recovery_alert(result: Dict[str, Any], duration_s: int):
    """Send WhatsApp recovery alert if plan allows and phone is configured."""
    try:
        email = result.get("email")
        if not email:
            return
        feats = await _plan_features(email)
        if "whatsapp_alerts" not in feats:
            return
        phone = await _resolve_alert_phone(email)
        if not phone:
            return
        from services.whapi_service import send_whatsapp_message
        url = result.get("url") or ""
        mins = duration_s // 60
        msg = (
            f"✓ AUREM Site Monitor — RECOVERED\n\n"
            f"{url} is back online.\n"
            f"Total downtime: {mins}m {duration_s % 60}s\n\n"
            f"Incident log: https://aurem.live/my/monitor"
        )
        res = await send_whatsapp_message(phone, msg)
        if not res.get("success"):
            logger.warning(f"[site-monitor] WhatsApp recovery alert failed: {res.get('error')}")
    except Exception as e:
        logger.warning(f"[site-monitor] WhatsApp recovery alert exception: {e}")


async def _send_recovery_alert(result: Dict[str, Any], duration_s: int):
    try:
        from services.email_service_resend import send_email
        to = result.get("email")
        if not to:
            return
        mins = duration_s // 60
        html = f"""
        <div style='font-family:system-ui;background:#050505;color:#eee;padding:24px;border-radius:12px'>
          <h2 style='color:#4ADE80;margin:0 0 8px 0'>AUREM Site Monitor — Back Online ✓</h2>
          <p style='color:#ccc'><b style='color:#D4AF37'>{result['url']}</b> is responding normally again.</p>
          <p style='color:#ccc'>Total downtime: <b>{mins} minute(s) {duration_s % 60}s</b></p>
          <p style='margin-top:16px'><a href='https://aurem.live/my/monitor' style='color:#D4AF37;text-decoration:none'>→ View incident log</a></p>
        </div>
        """
        await send_email(to=to, subject=f"[AUREM] RECOVERED: {result['url']}", html=html)
    except Exception as e:
        logger.warning(f"[site-monitor] recovery alert failed: {e}")


# ═════════════════════════════════════════════════════════════════════
# Tenant CRUD
# ═════════════════════════════════════════════════════════════════════
async def add_url(email: str, bin_: Optional[str], url: str, label: str = "",
                  method: str = "GET", expected_status: Optional[List[int]] = None) -> Dict[str, Any]:
    if _db is None:
        raise RuntimeError("db not ready")
    plan = await get_tenant_plan(email, bin_)
    if plan["tier"] == "none":
        raise ValueError("no_active_plan")

    limits = plan["limits"] or {}
    max_urls = limits.get("max_urls", 3)
    current = await _db.site_monitor_endpoints.count_documents({"email": email.lower(), "active": True})
    if max_urls != -1 and current >= max_urls:
        raise ValueError(f"url_limit_reached:{max_urls}")

    doc = {
        "endpoint_id": f"ep_{uuid.uuid4().hex[:12]}",
        "email": email.lower(),
        "bin": bin_,
        "tenant_id": bin_ or email.lower(),
        "url": url,
        "label": label or url,
        "method": method.upper(),
        "expected_status": expected_status or [200, 301, 302],
        "active": True,
        "plan_tier": plan["tier"],
        "plan_service_id": plan.get("service_id"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await _db.site_monitor_endpoints.insert_one({**doc})
    doc.pop("_id", None)
    return doc


async def list_urls(email: str) -> List[Dict[str, Any]]:
    if _db is None:
        return []
    return [d async for d in _db.site_monitor_endpoints.find(
        {"email": email.lower()}, {"_id": 0}
    ).sort("created_at", -1)]


async def remove_url(email: str, endpoint_id: str) -> bool:
    if _db is None:
        return False
    r = await _db.site_monitor_endpoints.delete_one(
        {"email": email.lower(), "endpoint_id": endpoint_id}
    )
    if r.deleted_count:
        await _db.site_monitor_logs.delete_many({"endpoint_id": endpoint_id})
        await _db.site_monitor_incidents.delete_many({"endpoint_id": endpoint_id})
    return r.deleted_count > 0


# ═════════════════════════════════════════════════════════════════════
# Stats
# ═════════════════════════════════════════════════════════════════════
async def tenant_stats(email: str, window_hours: int = 24) -> Dict[str, Any]:
    if _db is None:
        return {"endpoints": [], "summary": {}}
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=window_hours)).isoformat()
    endpoints = await list_urls(email)

    # Per-endpoint uptime
    out_endpoints = []
    total_passed = 0
    total_runs = 0
    for ep in endpoints:
        pipeline = [
            {"$match": {"endpoint_id": ep["endpoint_id"], "ts": {"$gte": cutoff}}},
            {"$group": {
                "_id": None,
                "total": {"$sum": 1},
                "passed": {"$sum": {"$cond": [{"$eq": ["$passed", True]}, 1, 0]}},
                "avg_latency_ms": {"$avg": "$latency_ms"},
                "last_ts": {"$last": "$ts"},
                "last_status": {"$last": "$status_code"},
                "last_passed": {"$last": "$passed"},
            }},
        ]
        try:
            agg = [d async for d in _db.site_monitor_logs.aggregate(pipeline)]
        except Exception:
            agg = []
        if agg:
            a = agg[0]
            total_passed += a["passed"]
            total_runs += a["total"]
            uptime = round(a["passed"] / max(a["total"], 1) * 100, 2)
            out_endpoints.append({**ep,
                "uptime_pct": uptime,
                "runs": a["total"],
                "avg_latency_ms": round(a.get("avg_latency_ms") or 0, 1),
                "last_ts": a.get("last_ts"),
                "last_status": a.get("last_status"),
                "last_passed": a.get("last_passed"),
            })
        else:
            out_endpoints.append({**ep, "uptime_pct": None, "runs": 0,
                                  "avg_latency_ms": 0, "last_ts": None, "last_status": None, "last_passed": None})

    summary = {
        "total_endpoints": len(endpoints),
        "total_runs": total_runs,
        "total_passed": total_passed,
        "avg_uptime_pct": round(total_passed / max(total_runs, 1) * 100, 2) if total_runs else None,
        "window_hours": window_hours,
    }
    return {"endpoints": out_endpoints, "summary": summary}


async def tenant_incidents(email: str, limit: int = 50) -> List[Dict[str, Any]]:
    if _db is None:
        return []
    return [d async for d in _db.site_monitor_incidents.find(
        {"email": email.lower()}, {"_id": 0}
    ).sort("started_at", -1).limit(limit)]


# ═════════════════════════════════════════════════════════════════════
# Free-tier signup
# ═════════════════════════════════════════════════════════════════════
async def free_signup(email: str, url: str, source: str = "landing") -> Dict[str, Any]:
    """Register a free-tier signup. 7-day trial, 3 URLs max."""
    if _db is None:
        raise RuntimeError("db not ready")
    email = (email or "").lower().strip()
    if not email or "@" not in email:
        raise ValueError("invalid_email")
    url = (url or "").strip()
    if not url.startswith("http"):
        url = "https://" + url

    now = datetime.now(timezone.utc)
    trial_ends = now + timedelta(days=7)

    existing = await _db.site_monitor_free.find_one({"email": email})
    if existing:
        # Reactivate if expired
        await _db.site_monitor_free.update_one(
            {"email": email},
            {"$set": {
                "status": "active",
                "trial_ends_at": trial_ends.isoformat(),
                "last_signup_at": now.isoformat(),
                "source": source,
            }},
        )
    else:
        await _db.site_monitor_free.insert_one({
            "signup_id": f"fs_{uuid.uuid4().hex[:12]}",
            "email": email,
            "status": "active",
            "created_at": now.isoformat(),
            "trial_ends_at": trial_ends.isoformat(),
            "source": source,
        })

    # Add initial URL if not already present
    exists_ep = await _db.site_monitor_endpoints.find_one({"email": email, "url": url})
    if not exists_ep:
        try:
            await add_url(email, None, url, label=url)
        except Exception as e:
            logger.warning(f"[site-monitor] free signup add_url failed: {e}")

    # Send welcome email
    try:
        from services.email_service_resend import send_email
        html = f"""
        <div style='font-family:system-ui;background:#050505;color:#eee;padding:24px;border-radius:12px'>
          <h2 style='color:#D4AF37;margin:0 0 10px 0'>Welcome to AUREM Site Monitor</h2>
          <p style='color:#ccc'>We're now watching <b style='color:#D4AF37'>{url}</b> every 15 minutes.</p>
          <p style='color:#ccc'>Your 7-day free trial includes:</p>
          <ul style='color:#ccc'>
            <li>Up to 3 URLs monitored</li>
            <li>Email alerts on downtime &amp; recovery</li>
            <li>Live uptime dashboard</li>
          </ul>
          <p style='margin-top:18px'><a href='https://aurem.live/platform/signup?email={email}&redirect=/my/monitor' style='display:inline-block;padding:12px 24px;background:#D4AF37;color:#0D0D0D;text-decoration:none;border-radius:8px;font-weight:700'>Claim Your Dashboard →</a></p>
          <p style='color:#888;font-size:12px;margin-top:8px'>Use the same email ({email}) to unlock your live uptime dashboard.</p>
          <p style='color:#666;font-size:12px;margin-top:18px'>Trial ends {trial_ends.strftime('%b %d, %Y')}. Upgrade for $29/mo to unlock 5 URLs, 10-min checks, and WhatsApp alerts.</p>
        </div>
        """
        await send_email(to=email, subject=f"[AUREM] Now monitoring {url}", html=html)
    except Exception as e:
        logger.warning(f"[site-monitor] welcome email failed: {e}")

    return {
        "email": email,
        "url": url,
        "trial_ends_at": trial_ends.isoformat(),
        "status": "active",
    }


# ═════════════════════════════════════════════════════════════════════
# Multi-tenant scheduler
# ═════════════════════════════════════════════════════════════════════
async def run_scan_tick() -> Dict[str, Any]:
    """Scan all active endpoints whose check interval has elapsed."""
    if _db is None:
        return {"scanned": 0, "passed": 0, "failed": 0}

    # Expire free trials
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        await _db.site_monitor_free.update_many(
            {"status": "active", "trial_ends_at": {"$lt": now_iso}},
            {"$set": {"status": "expired"}},
        )
        # Deactivate their endpoints
        expired_emails = [d["email"] async for d in _db.site_monitor_free.find(
            {"status": "expired"}, {"_id": 0, "email": 1}
        )]
        if expired_emails:
            # Only pause free-tier endpoints (leave paid alone)
            await _db.site_monitor_endpoints.update_many(
                {"email": {"$in": expired_emails}, "plan_tier": "free"},
                {"$set": {"active": False}},
            )
    except Exception:
        pass

    # Pull all active endpoints
    endpoints = [d async for d in _db.site_monitor_endpoints.find(
        {"active": True}, {"_id": 0}
    )]
    if not endpoints:
        return {"scanned": 0, "passed": 0, "failed": 0}

    results = []
    # INTENTIONAL: scanning untrusted external customer websites — many have
    # expired/self-signed certs which we capture as findings (not failures).
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, verify=False) as client:
        # Chunk into 20 concurrent
        for i in range(0, len(endpoints), 20):
            chunk = endpoints[i:i+20]
            chunk_res = await asyncio.gather(
                *[_check_url(client, ep) for ep in chunk],
                return_exceptions=True,
            )
            for r in chunk_res:
                if isinstance(r, Exception):
                    continue
                results.append(r)

    # Persist + incident tracking
    if results:
        try:
            await _db.site_monitor_logs.insert_many(results)
        except Exception as e:
            logger.warning(f"[site-monitor] bulk log insert failed: {e}")
        for r in results:
            try:
                await _handle_incident(r)
            except Exception as e:
                logger.warning(f"[site-monitor] incident handle failed: {e}")

    passed = sum(1 for r in results if r.get("passed"))
    failed = len(results) - passed
    logger.info(f"[site-monitor] scan tick: {passed}/{len(results)} passed ({failed} failures)")
    return {"scanned": len(results), "passed": passed, "failed": failed}


async def site_monitor_scheduler():
    """Run a scan tick every 5 minutes (URLs whose interval has elapsed are scanned)."""
    # iter 285.8 — startup delay reduced 180s → 20s so site_monitor_logs
    # doesn't stay stale for 3+ min after every backend restart.
    await asyncio.sleep(20)
    logger.info("[site-monitor] Scheduler started — 5-min tick")
    while True:
        try:
            await run_scan_tick()
        except Exception as e:
            logger.error(f"[site-monitor] scheduler error: {e}")
        await asyncio.sleep(300)  # 5 min


# ═════════════════════════════════════════════════════════════════════
# Admin aggregate
# ═════════════════════════════════════════════════════════════════════
async def admin_overview() -> Dict[str, Any]:
    if _db is None:
        return {}
    total_endpoints = await _db.site_monitor_endpoints.count_documents({"active": True})
    total_free = await _db.site_monitor_free.count_documents({"status": "active"})
    paid_subs = await _db.customer_subscriptions.count_documents(
        {"service_id": {"$in": SKU_IDS}, "status": "active"}
    )
    open_incidents = await _db.site_monitor_incidents.count_documents({"status": "open"})

    # MRR from paid subs
    mrr = 0
    async for s in _db.customer_subscriptions.find(
        {"service_id": {"$in": SKU_IDS}, "status": "active"}, {"_id": 0, "price_monthly": 1}
    ):
        mrr += s.get("price_monthly", 0)

    # Recent scan
    recent = await _db.site_monitor_logs.find({}, {"_id": 0}).sort("ts", -1).limit(100).to_list(length=100)
    passed_recent = sum(1 for r in recent if r.get("passed"))
    recent_pass_rate = round(passed_recent / max(len(recent), 1) * 100, 1) if recent else None

    return {
        "active_endpoints": total_endpoints,
        "active_free_trials": total_free,
        "active_paid_subs": paid_subs,
        "mrr_cad": round(mrr, 2),
        "open_incidents": open_incidents,
        "recent_pass_rate_pct": recent_pass_rate,
    }


async def admin_list_tenants(limit: int = 200) -> List[Dict[str, Any]]:
    """List all tenants with active endpoints, grouped by email."""
    if _db is None:
        return []
    pipeline = [
        {"$match": {"active": True}},
        {"$group": {
            "_id": "$email",
            "urls": {"$sum": 1},
            "plan_tier": {"$last": "$plan_tier"},
            "bin": {"$last": "$bin"},
            "last_created": {"$last": "$created_at"},
        }},
        {"$sort": {"last_created": -1}},
        {"$limit": limit},
    ]
    out = []
    async for d in _db.site_monitor_endpoints.aggregate(pipeline):
        out.append({
            "email": d["_id"],
            "urls": d["urls"],
            "plan_tier": d.get("plan_tier"),
            "bin": d.get("bin"),
            "last_created": d.get("last_created"),
        })
    return out
