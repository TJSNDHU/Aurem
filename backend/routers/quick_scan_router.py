"""Quick Website Scanner — public endpoint for /demo widget.

Quota model:
  - 3 scans per (ip + device_id) — hard cap, no unlock
  - After 3 → lock; CTA = start free trial for unlimited scans
  - 5-min per-domain cache prevents abuse + improves UX
  - Separate email-capture path: "email me this report" → Envoy follow-up
"""
from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr

logger = logging.getLogger("quick-scan")

router = APIRouter(prefix="/api/scan", tags=["scan"])

BASE_QUOTA = 3            # baseline daily quota — no unlock available
CACHE_TTL_MIN = 5         # per-domain cache window


def _get_db():
    try:
        from server import db as _db
        return _db
    except Exception:
        return None


def _client_id(request: Request, device_id: str) -> str:
    ip = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    if not ip and request.client:
        ip = request.client.host or ""
    raw = f"{ip}|{device_id}".encode()
    return hashlib.sha256(raw).hexdigest()[:24]


async def _quota_state(db, cid: str) -> dict:
    if db is None:
        return {"used": 0, "remaining": BASE_QUOTA, "limit": BASE_QUOTA}
    since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    used = await db.quick_scans.count_documents({"cid": cid, "ts": {"$gte": since}})
    return {"used": used, "remaining": max(0, BASE_QUOTA - used), "limit": BASE_QUOTA}


class _ScanBody(BaseModel):
    domain: str
    device_id: str = ""


@router.post("/quick")
async def quick_scan_endpoint(body: _ScanBody, request: Request):
    db = _get_db()
    if not body.domain.strip():
        raise HTTPException(400, "domain required")

    cid = _client_id(request, body.device_id or "anon")
    state = await _quota_state(db, cid)
    if state["remaining"] <= 0:
        return {
            "ok": False,
            "rate_limited": True,
            "quota": state,
            "trial_cta": "Start your free 7-day trial for unlimited scans + automatic fixes.",
            "trial_url": os.environ.get("AUREM_TRIAL_URL", "https://aurem.live/signup"),
        }

    # 5-min per-domain cache (per cid) — replays don't burn quota
    if db is not None:
        cache_since = (datetime.now(timezone.utc) - timedelta(minutes=CACHE_TTL_MIN)).isoformat()
        cached = await db.quick_scans.find_one(
            {"cid": cid, "domain_norm": body.domain.lower().strip(), "ts": {"$gte": cache_since}},
            {"_id": 0, "result": 1},
        )
        if cached and cached.get("result"):
            return {"ok": True, "cached": True, "quota": state, **cached["result"]}

    from services.quick_scanner import quick_scan as _scan
    result = await _scan(body.domain)
    if not result.get("ok"):
        return {"ok": False, "error": result.get("error", "scan failed"), "quota": state}

    # Persist for cache + analytics
    if db is not None:
        try:
            await db.quick_scans.insert_one({
                "cid": cid,
                "domain": result.get("domain"),
                "domain_norm": body.domain.lower().strip(),
                "score": result.get("score"),
                "critical_issues": result.get("critical_issues"),
                "result": dict(result),  # copy
                "ts": datetime.now(timezone.utc).isoformat(),
            })
            from services.agent_ledger import record_cost
            await record_cost(db, "scout_ora", "apollo_enrich", 0,
                              meta={"kind": "quick_scan", "domain": result.get("domain")})
        except Exception as e:
            logger.warning(f"[quick-scan] persist failed: {e}")

    new_state = await _quota_state(db, cid)
    return {"ok": True, "quota": new_state, **result}


class _EmailReportBody(BaseModel):
    device_id: str = ""
    email: EmailStr
    domain: str
    score: int = 0
    critical_issues: int = 0


@router.post("/quick/email-report")
async def email_report(body: _EmailReportBody, request: Request):
    """Capture lead + email the scan report. Drops into Envoy follow-up sequence."""
    db = _get_db()
    if db is None:
        raise HTTPException(503, "DB unavailable")

    cid = _client_id(request, body.device_id or "anon")

    # Idempotency: same (email, domain) within 1h returns silently OK
    one_hour = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    dup = await db.scan_email_captures.find_one(
        {"email": str(body.email), "domain": body.domain, "ts": {"$gte": one_hour}},
        {"_id": 1},
    )
    if dup:
        return {"ok": True, "deduped": True}

    capture_doc = {
        "cid": cid,
        "email": str(body.email),
        "domain": body.domain,
        "score": body.score,
        "critical_issues": body.critical_issues,
        "source": "quick_scan_email_report",
        "ts": datetime.now(timezone.utc).isoformat(),
        "ip": request.headers.get("x-forwarded-for", "") or (request.client.host if request.client else ""),
    }
    await db.scan_email_captures.insert_one(capture_doc)

    # Send report via Resend (best-effort)
    sent_via_resend = False
    resend_key = os.environ.get("RESEND_API_KEY", "").strip()
    from_email = os.environ.get("RESEND_FROM_EMAIL", "").strip() or "ora@aurem.live"
    if resend_key:
        try:
            import httpx
            html = (
                f"<h2 style='font-family:serif;color:#D4AF37'>AUREM Scan Report — {body.domain}</h2>"
                f"<p style='color:#333'>Overall score: <b>{body.score}/100</b><br>"
                f"Critical issues: <b style='color:#EF4444'>{body.critical_issues}</b></p>"
                "<p>The full breakdown of your meta tags, schema, page speed, broken links and mobile-friendliness "
                "is on your AUREM dashboard. AUREM fixes every red item automatically — no developer needed.</p>"
                f"<p><a href='{os.environ.get('AUREM_TRIAL_URL', 'https://aurem.live/signup')}' "
                "style='display:inline-block;padding:14px 28px;background:linear-gradient(135deg,#D4AF37,#8B7355);"
                "color:#0a0a0a;text-decoration:none;border-radius:10px;font-weight:600'>"
                "Start my free 7-day trial →</a></p>"
                "<p style='color:#999;font-size:12px'>You're receiving this because you requested a website scan from AUREM. "
                "Reply STOP to opt out.</p>"
            )
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.post(
                    "https://api.resend.com/emails",
                    headers={"Authorization": f"Bearer {resend_key}", "Content-Type": "application/json"},
                    json={
                        "from": f"AUREM <{from_email}>",
                        "to": [str(body.email)],
                        "subject": f"Your AUREM scan: {body.domain} — score {body.score}/100",
                        "html": html,
                    },
                )
                sent_via_resend = r.status_code in (200, 202)
                if not sent_via_resend:
                    logger.warning(f"[quick-scan] resend HTTP {r.status_code}: {r.text[:200]}")
        except Exception as e:
            logger.warning(f"[quick-scan] email send failed: {e}")

    # Push into campaign_leads so Envoy / Closer pick it up
    try:
        await db.campaign_leads.update_one(
            {"email": str(body.email)},
            {"$set": {
                "email": str(body.email),
                "email_source": "quick_scan",
                "domain": body.domain,
                "scan_score": body.score,
                "scan_critical": body.critical_issues,
                "stage": "scan_lead",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }},
            upsert=True,
        )
    except Exception as e:
        logger.warning(f"[quick-scan] lead upsert failed: {e}")

    return {"ok": True, "report_sent": sent_via_resend}


@router.get("/quick/quota")
async def get_quota(request: Request, device_id: str = ""):
    db = _get_db()
    cid = _client_id(request, device_id or "anon")
    return {"quota": await _quota_state(db, cid)}
