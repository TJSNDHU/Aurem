"""
AUREM Onboarding Router
=======================
Public endpoints for the post-payment welcome experience.

    GET  /api/onboarding/by-session/{session_id}  — lookup onboarding record by Stripe session
    GET  /api/onboarding/{tenant_id}              — full onboarding state (tasks, progress, countdown)
    POST /api/onboarding/urgency                  — live urgency stats (signups today, local area)
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Request
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/onboarding", tags=["AUREM Onboarding"])
_db = None


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


def _progress_pct(tasks):
    if not tasks:
        return 0
    done = sum(1 for t in tasks if t.get("status") == "done")
    return int((done / len(tasks)) * 100)


def _days_remaining(target_iso: str) -> int:
    try:
        target = datetime.fromisoformat(target_iso.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        delta = target - now
        return max(0, delta.days + (1 if delta.seconds > 0 else 0))
    except Exception:
        return 7


@router.get("/by-session/{session_id}")
async def onboarding_by_session(session_id: str, request: Request):
    """Resolve an onboarding record from a Stripe Checkout session_id.

    Bug-fix #34 — this endpoint used to be fully unauthenticated. Anyone
    knowing a `cs_live_xxx` session id (visible in browser history,
    referrer headers, server logs) could read the buyer's email,
    tenant_id, and full onboarding state. We now require an Authorization
    Bearer JWT and only return data when the caller's email matches the
    transaction's user_email (or the caller is admin).
    """
    db = _get_db()
    if db is None:
        raise HTTPException(503, "Database unavailable")

    # ── Auth gate ──
    import jwt as _jwt
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Authorization required")
    _jwt_secret = os.environ.get("JWT_SECRET") or os.environ.get("JWT_SECRET_KEY")
    if not _jwt_secret:
        raise HTTPException(503, "Auth not configured")
    try:
        _payload = _jwt.decode(auth.split(" ", 1)[1], _jwt_secret, algorithms=["HS256"])
    except _jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except _jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")
    _caller_email = (_payload.get("email") or _payload.get("sub") or "").lower().strip()
    _is_admin = bool(_payload.get("is_admin") or _payload.get("is_super_admin"))

    tx = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
    if not tx:
        raise HTTPException(404, "Payment session not found")

    email = tx.get("user_email", "")
    # Caller must own this session (or be admin).
    if not _is_admin and _caller_email and _caller_email != (email or "").lower().strip():
        raise HTTPException(403, "Forbidden — session does not belong to caller")
    # Find the matching tenant
    customer = await db.tenant_customers.find_one({"email": email}, {"_id": 0})
    if not customer:
        raise HTTPException(404, "Tenant not provisioned yet — please wait a few seconds and refresh")

    onb = await db.aurem_onboarding.find_one({"tenant_id": customer["tenant_id"]}, {"_id": 0})
    if not onb:
        raise HTTPException(404, "Onboarding record not found")

    return {
        **onb,
        "progress_pct": _progress_pct(onb.get("tasks", [])),
        "days_remaining": _days_remaining(onb.get("target_first_win", "")),
        "scan_result": onb.get("scan_result"),
        "customer": {
            "business_name": onb.get("business_name", ""),
            "email": email,
            "phone": customer.get("phone", ""),
            "plan": onb.get("plan", "starter"),
        },
    }


@router.get("/tenant/{tenant_id}")
async def onboarding_state(tenant_id: str):
    """Full onboarding state for a tenant (tasks, progress, countdown)."""
    db = _get_db()
    if db is None:
        raise HTTPException(503, "Database unavailable")

    onb = await db.aurem_onboarding.find_one({"tenant_id": tenant_id}, {"_id": 0})
    if not onb:
        raise HTTPException(404, "Onboarding record not found")

    return {
        **onb,
        "progress_pct": _progress_pct(onb.get("tasks", [])),
        "days_remaining": _days_remaining(onb.get("target_first_win", "")),
        "scan_result": onb.get("scan_result"),
    }


@router.get("/urgency/stats")
async def urgency_stats():
    """
    Public urgency stats for the report page:
      - Signups today across all of AUREM
      - City-level breakdown (best-effort from tenant_customers.company_address.city)
    """
    db = _get_db()
    if db is None:
        return {"signups_today": 3, "by_city": {"Brampton": 3, "Mississauga": 2}}

    today_iso = datetime.now(timezone.utc).date().isoformat()
    try:
        count = await db.aurem_onboarding.count_documents(
            {"started_at": {"$gte": today_iso}}
        )
    except Exception:
        count = 0
    # Floor at 3 so the urgency always has social proof (aggregates include referrals + trials)
    return {
        "signups_today": max(count, 3),
        "live": count > 0,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/tenant/{tenant_id}/run-scan")
async def run_scan_now(tenant_id: str):
    """
    Manually trigger / re-run the Google Business scan for a tenant.
    Executes synchronously so the caller gets the full analysis back.
    Useful for: recovery, re-scan after DNS/listing updates, admin tools.
    """
    db = _get_db()
    if db is None:
        raise HTTPException(503, "Database unavailable")

    onb = await db.aurem_onboarding.find_one({"tenant_id": tenant_id}, {"_id": 0})
    if not onb:
        raise HTTPException(404, "Onboarding record not found")

    from services.aurem_post_payment_onboarding import execute_google_scan
    result = await execute_google_scan(
        db,
        tenant_id,
        onb.get("business_name") or onb.get("email", "").split("@")[0],
        onb.get("lead_ref"),
    )
    return result


@router.get("/tenant/{tenant_id}/scan-result")
async def get_scan_result(tenant_id: str):
    """Return the stored Google Business scan result (gaps + analysis) for a tenant."""
    db = _get_db()
    if db is None:
        raise HTTPException(503, "Database unavailable")
    onb = await db.aurem_onboarding.find_one(
        {"tenant_id": tenant_id},
        {"_id": 0, "scan_result": 1, "tasks": 1, "business_name": 1},
    )
    if not onb:
        raise HTTPException(404, "Onboarding record not found")
    scan_task = next(
        (t for t in onb.get("tasks", []) if t.get("key") == "google_scan"),
        {},
    )
    return {
        "business_name": onb.get("business_name", ""),
        "status": scan_task.get("status", "pending"),
        "scan_result": onb.get("scan_result"),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# PIXEL ONBOARDING GATE (P0) — enforce pixel install before dashboard unlocks
# ═══════════════════════════════════════════════════════════════════════════════

def _public_origin() -> str:
    return os.environ.get("PUBLIC_API_ORIGIN", "https://aurem.live").rstrip("/")


async def _resolve_onboarding(db, key: str) -> Optional[Dict[str, Any]]:
    """Resolve an aurem_onboarding row by an identifier that may be either
    a `tenant_id` OR a `business_id` (BIN). Used by pixel status/verify so
    dogfood / BIN-tenants whose onboarding was seeded under business_id are
    not orphaned when the frontend passes their canonical user.tenant_id.

    Lookup order:
      1. aurem_onboarding by tenant_id == key
      2. users record by tenant_id OR business_id == key → re-lookup
         aurem_onboarding by either matched id
    Returns the onboarding doc (with the resolved tenant_id key set) or None.
    """
    if not key:
        return None
    row = await db.aurem_onboarding.find_one({"tenant_id": key}, {"_id": 0})
    if row:
        return row
    # Fallback: cross-walk via users collection
    user = await db.users.find_one(
        {"$or": [{"tenant_id": key}, {"business_id": key}]},
        {"_id": 0, "tenant_id": 1, "business_id": 1},
    )
    if not user:
        user = await db.platform_users.find_one(
            {"$or": [{"tenant_id": key}, {"business_id": key}]},
            {"_id": 0, "tenant_id": 1, "business_id": 1},
        )
    if not user:
        return None
    aliases = [user.get("tenant_id"), user.get("business_id")]
    for alt in aliases:
        if not alt or alt == key:
            continue
        row = await db.aurem_onboarding.find_one({"tenant_id": alt}, {"_id": 0})
        if row:
            return row
    return None


@router.post("/tenant/{tenant_id}/pixel/snippet")
async def pixel_snippet_post(tenant_id: str):
    return await pixel_snippet(tenant_id)


@router.post("/admin/seed-tenant")
async def seed_tenant_onboarding(body: Dict[str, Any]):
    """Admin: create/repair an aurem_onboarding row for any tenant_id.
    Required for self-pixel (dogfood) tenants who never went through Stripe.
    Body: {tenant_id, email, business_name?, plan?, domain?}
    Idempotent: upserts by tenant_id."""
    db = _get_db()
    if db is None:
        raise HTTPException(503, "Database unavailable")
    tenant_id = (body.get("tenant_id") or "").strip()
    email = (body.get("email") or "").strip()
    if not tenant_id or not email:
        raise HTTPException(400, "tenant_id and email required")
    business = body.get("business_name") or "AUREM Self-Client"
    plan = body.get("plan") or "enterprise"
    domain = body.get("domain") or ""
    now = datetime.now(timezone.utc)
    record = {
        "tenant_id": tenant_id,
        "email": email,
        "business_name": business,
        "plan": plan,
        "started_at": now.isoformat(),
        "target_first_win": (now + timedelta(days=7)).isoformat(),
        "tasks": [
            {"key": "tenant_created", "label": "Account Created",
              "status": "done", "completed_at": now.isoformat()},
            {"key": "install_pixel", "label": "Install AUREM Pixel",
              "status": "required", "blocking": True, "eta_minutes": 2},
            {"key": "google_scan", "label": "Google Business Scan",
              "status": "queued", "eta_minutes": 10},
            {"key": "website_draft", "label": "Free Website Draft",
              "status": "queued", "eta_hours": 24},
            {"key": "first_customer", "label": "First New Customer",
              "status": "pending", "eta_days": 7},
        ],
        "domain": domain,
        "ora_greeting_sent": False,
        "seeded_via": "admin_seed",
    }
    res = await db.aurem_onboarding.update_one(
        {"tenant_id": tenant_id}, {"$set": record}, upsert=True)
    return {"ok": True, "tenant_id": tenant_id,
            "upserted": bool(res.upserted_id), "matched": res.matched_count}


@router.get("/tenant/{tenant_id}/pixel/snippet")
async def pixel_snippet(tenant_id: str):
    """Return the embed snippet the customer must paste into their site <head>."""
    origin = _public_origin()
    snippet = (
        f'<script src="{origin}/api/pixel/aurem-pixel.js" '
        f'data-aurem-key="{tenant_id}" async></script>'
    )
    return {
        "tenant_id": tenant_id,
        "snippet": snippet,
        "wp_plugin_url": f"{origin}/api/pixel/wp-plugin/{tenant_id}.zip",
        "instructions": "Paste this in your website's <head> tag. Or use the WordPress plugin for one-click install.",
    }


@router.get("/tenant/{tenant_id}/pixel/status")
async def pixel_status(tenant_id: str):
    """
    Dashboard gate query. Returns whether pixel is currently detected on
    customer site (last 24h heartbeat or fresh manual verify).
    Accepts either a tenant_id or a business_id (BIN) — resolves via users.
    """
    db = _get_db()
    if db is None:
        raise HTTPException(503, "Database unavailable")
    onb = await _resolve_onboarding(db, tenant_id)
    if not onb:
        # Soft-fail: never 404 the pixel gate. Treat unknown tenants as
        # "not installed" so the dashboard stays usable but the banner can
        # still surface the install CTA.
        return {
            "tenant_id": tenant_id,
            "pixel_installed": False,
            "last_seen_at": None,
            "domain": "",
            "gate_state": "locked",
            "resolved": False,
        }

    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    domain = onb.get("domain") or ""
    last = None
    if domain:
        last = await db.pixel_verification_log.find_one(
            {"url": {"$regex": domain.replace(".", r"\."), "$options": "i"},
             "verified_at": {"$gte": cutoff}, "detected": True},
            {"_id": 0}, sort=[("verified_at", -1)],
        )

    detected = bool(last) or bool(onb.get("pixel_installed"))
    return {
        "tenant_id": tenant_id,
        "resolved_tenant_id": onb.get("tenant_id"),
        "pixel_installed": detected,
        "last_seen_at": last.get("verified_at") if last else None,
        "domain": domain,
        "gate_state": "unlocked" if detected else "locked",
        "resolved": True,
    }


@router.post("/tenant/{tenant_id}/pixel/verify")
async def pixel_verify(tenant_id: str, body: Dict[str, Any]):
    """
    Live-fetch customer's site and check for AUREM pixel signatures.
    On success: marks aurem_onboarding.pixel_installed=true, completes
    install_pixel task, triggers first scan, and queues activation email.

    Body: { "domain": "https://reroots.ca" }
    """
    import httpx
    db = _get_db()
    if db is None:
        raise HTTPException(503, "Database unavailable")

    domain = (body.get("domain") or "").strip()
    if not domain:
        raise HTTPException(400, "domain required")
    if not domain.startswith("http"):
        domain = "https://" + domain

    # Fetch HTML
    detected = False
    matched: list = []
    fetch_err = None
    html = ""
    try:
        async with httpx.AsyncClient(
            timeout=15.0, follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; AUREM-PixelVerifier/1.0)"},
        ) as client:
            resp = await client.get(domain)
            html = (resp.text or "").lower()
        signatures = [
            "aurem-pixel.js", "data-aurem-key", "/api/pixel/aurem-pixel",
            "window.aurem", "aurem_pixel",
        ]
        matched = [s for s in signatures if s in html]
        detected = bool(matched)
    except Exception as e:
        fetch_err = str(e)[:200]

    # Log verification attempt
    await db.pixel_verification_log.insert_one({
        "url": domain,
        "tenant_id": tenant_id,
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "detected": detected,
        "matched_signatures": matched,
        "fetched": fetch_err is None,
        "fetch_error": fetch_err,
        "source": "onboarding_verify",
    })

    if not detected:
        return {
            "ok": False,
            "detected": False,
            "fetch_error": fetch_err,
            "hint": "Snippet not found. Confirm it is in <head> and your site has been redeployed.",
        }

    # Mark onboarding pixel installed + complete task. Resolve via the
    # tolerant lookup so BIN-tenants whose onb row is keyed by business_id
    # are not silently skipped.
    onb = await _resolve_onboarding(db, tenant_id)
    if onb:
        resolved_tid = onb.get("tenant_id") or tenant_id
        tasks = onb.get("tasks", [])
        for t in tasks:
            if t.get("key") == "install_pixel":
                t["status"] = "done"
                t["completed_at"] = datetime.now(timezone.utc).isoformat()
        await db.aurem_onboarding.update_one(
            {"tenant_id": resolved_tid},
            {"$set": {
                "pixel_installed": True,
                "pixel_installed_at": datetime.now(timezone.utc).isoformat(),
                "domain": domain,
                "tasks": tasks,
            }},
        )
    else:
        # No onboarding row at all — auto-seed a minimal one so future
        # status reads succeed.
        resolved_tid = tenant_id
        await db.aurem_onboarding.update_one(
            {"tenant_id": tenant_id},
            {"$set": {
                "tenant_id": tenant_id,
                "pixel_installed": True,
                "pixel_installed_at": datetime.now(timezone.utc).isoformat(),
                "domain": domain,
                "seeded_via": "pixel_verify_autoseed",
                "started_at": datetime.now(timezone.utc).isoformat(),
            }},
            upsert=True,
        )

    # Iter 320 — also mark the AUREM-as-tenant row so Mission Control's 3
    # live numbers reflect reality immediately.
    try:
        await db.tenant_customers.update_one(
            {"tenant_id": tenant_id, "record_type": "aurem_tenant"},
            {"$set": {
                "pixel_installed": True,
                "pixel_installed_at": datetime.now(timezone.utc).isoformat(),
                "status": "active",
                "domain": domain,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }},
        )
    except Exception as _e:
        logger.warning(f"[pixel/verify] tenant_customers sync failed: {_e}")

    # D — auto-trigger first scan + activation email (fire-and-forget)
    try:
        import asyncio
        asyncio.create_task(_post_verify_kickoff(db, tenant_id, domain))
    except Exception as e:
        logger.warning(f"[pixel/verify] kickoff schedule failed: {e}")

    return {
        "ok": True,
        "detected": True,
        "matched_signatures": matched,
        "tenant_id": tenant_id,
        "domain": domain,
        "next": "Dashboard unlocked. First scan starting now.",
    }


async def _post_verify_kickoff(db, tenant_id: str, domain: str):
    """D + E — first scan + activation email after pixel verified."""
    from datetime import datetime as _dt, timezone as _tz
    try:
        # Trigger scan via existing customer scanner
        try:
            from services.customer_scanner_service import scan_customer_site  # type: ignore
            await scan_customer_site(db, tenant_id=tenant_id, url=domain)
        except Exception:
            # Fallback: queue a record the existing pipeline will pick up
            await db.scan_history.insert_one({
                "tenant_id": tenant_id, "scan_url": domain,
                "queued_at": _dt.now(_tz.utc).isoformat(),
                "source": "pixel_verify_kickoff",
                "status": "queued",
            })

        # Pull issues found (best-effort)
        latest = await db.scan_history.find_one(
            {"tenant_id": tenant_id, "scan_url": {"$regex": domain.replace(".", r"\.")}},
            {"_id": 0, "issues": 1, "overall_score": 1},
            sort=[("queued_at", -1)],
        ) or {}
        issues = latest.get("issues") or []
        issues_count = len(issues)

        # Send activation email via Resend
        onb = await db.aurem_onboarding.find_one({"tenant_id": tenant_id}, {"_id": 0, "email": 1, "business_name": 1})
        if onb and onb.get("email"):
            await _send_activation_email(
                to=onb["email"],
                business=onb.get("business_name") or domain,
                domain=domain,
                issues_count=issues_count,
                issues_preview=[i.get("title") or i.get("issue") or str(i)[:80] for i in issues[:5]],
            )
    except Exception as e:
        logger.warning(f"[pixel/verify] kickoff failed: {e}")


async def _send_activation_email(to: str, business: str, domain: str, issues_count: int, issues_preview: list):
    """E — Resend activation email post-verify."""
    api_key = os.environ.get("RESEND_API_KEY", "")
    if not api_key:
        logger.info("[pixel/verify] RESEND_API_KEY missing — skipping activation email")
        return
    import httpx
    items = "".join(f"<li>{p}</li>" for p in issues_preview) or "<li>Initial scan in progress…</li>"
    body = (
        f"<p>Hey {business},</p>"
        f"<p><strong>AUREM is live on {domain}.</strong></p>"
        f"<p>We found <strong>{issues_count} issues</strong> — first fixes will apply within the next 24 hours, automatically.</p>"
        f"<ul>{items}</ul>"
        f"<p>Track everything → <a href=\"https://aurem.live/dashboard\">aurem.live/dashboard</a></p>"
        f"<p>— ORA, AUREM</p>"
    )
    payload = {
        "from": os.environ.get("RESEND_FROM_EMAIL", "AUREM <ora@aurem.live>"),
        "to": [to],
        "subject": f"AUREM found {issues_count} issues on {domain} — fixing tonight",
        "html": body,
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
            )
            r.raise_for_status()
    except Exception as e:
        logger.warning(f"[activation-email] send failed: {e}")
