"""
AUREM SEO Audit Router — Phase 1 ($49 One-Time SKU)
====================================================
Public lead-magnet + paid teardown. Free summary → $49 full report.

Pipeline:
  1. User submits URL + email → run PageSpeed + Firecrawl + Places
  2. Free preview (score + 3 issues) emailed via Resend
  3. CTA to pay $49 via Stripe embedded checkout → full 20-issue report

Endpoints:
  POST /api/seo-audit/scan              — run audit (public, email-gated)
  GET  /api/seo-audit/report/{scan_id}  — fetch saved report
  POST /api/seo-audit/checkout          — create Stripe $49 session
  GET  /api/seo-audit/product           — Stripe price_id (auto-created on startup)
"""
from __future__ import annotations

import os
import uuid
import asyncio
import re
import httpx
import logging
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
import stripe

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/seo-audit", tags=["SEO Audit $49"])
_db = None

PAGESPEED_KEY = os.environ.get("GOOGLE_PAGESPEED_API_KEY", "")
PLACES_KEY = os.environ.get("GOOGLE_PLACES_API_KEY", "")
FIRECRAWL_KEY = os.environ.get("FIRECRAWL_API_KEY", "")
RESEND_KEY = os.environ.get("RESEND_API_KEY", "")
RESEND_FROM = os.environ.get("RESEND_FROM_EMAIL", "AUREM <ora@aurem.live>")
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")

SEO_AUDIT_PRICE_ID: Optional[str] = None  # auto-created on startup


def set_db(database):
    global _db
    _db = database


async def ensure_stripe_product():
    """Called from startup — creates $49 CAD one-time product if missing."""
    global SEO_AUDIT_PRICE_ID
    if not stripe.api_key:
        return
    # Check for existing via lookup_key
    try:
        existing = stripe.Price.list(lookup_keys=["aurem_seo_audit_49_cad"], limit=1)
        if existing.data:
            SEO_AUDIT_PRICE_ID = existing.data[0].id
            logger.info(f"[seo-audit] existing price: {SEO_AUDIT_PRICE_ID}")
            return
    except Exception as e:
        logger.warning(f"[seo-audit] price lookup failed: {e}")

    try:
        product = stripe.Product.create(
            name="AUREM SEO Audit — Full Teardown",
            description="20-issue technical SEO + local SEO + performance report. Delivered within 60 seconds.",
        )
        price = stripe.Price.create(
            product=product.id,
            unit_amount=4900,
            currency="cad",
            lookup_key="aurem_seo_audit_49_cad",
            nickname="SEO Audit One-Time $49 CAD",
        )
        SEO_AUDIT_PRICE_ID = price.id
        logger.info(f"[seo-audit] created price: {SEO_AUDIT_PRICE_ID}")
    except Exception as e:
        logger.error(f"[seo-audit] stripe product create failed: {e}")


# ═════ Models ═════
class ScanRequest(BaseModel):
    url: str = Field(..., min_length=4)
    email: EmailStr
    business_name: Optional[str] = None
    consent_marketing: bool = False   # CASL double opt-in


class ScanResponse(BaseModel):
    scan_id: str
    summary: dict
    top_issues: list
    full_report_locked: bool = True


# ═════ Pipeline helpers ═════
def _normalize_url(u: str) -> str:
    if not u.startswith(("http://", "https://")):
        u = "https://" + u
    return u.strip().rstrip("/")


async def _run_pagespeed(url: str) -> dict:
    if not PAGESPEED_KEY:
        return {"error": "pagespeed_key_missing"}
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.get(
                "https://www.googleapis.com/pagespeedonline/v5/runPagespeed",
                params={"url": url, "key": PAGESPEED_KEY, "strategy": "mobile",
                        "category": ["performance", "accessibility", "best-practices", "seo"]},
            )
            data = r.json()
            lh = data.get("lighthouseResult", {})
            cats = lh.get("categories", {})
            audits = lh.get("audits", {})
            opportunities = []
            for key, a in audits.items():
                if a.get("score") is not None and a.get("score") < 0.9 and a.get("details", {}).get("overallSavingsMs"):
                    opportunities.append({
                        "id": key, "title": a.get("title"),
                        "description": a.get("description", "")[:180],
                        "savings_ms": int(a["details"]["overallSavingsMs"]),
                    })
            return {
                "performance": int((cats.get("performance", {}).get("score") or 0) * 100),
                "accessibility": int((cats.get("accessibility", {}).get("score") or 0) * 100),
                "best_practices": int((cats.get("best-practices", {}).get("score") or 0) * 100),
                "seo": int((cats.get("seo", {}).get("score") or 0) * 100),
                "opportunities": sorted(opportunities, key=lambda x: -x["savings_ms"])[:20],
            }
    except Exception as e:
        logger.warning(f"[seo-audit] pagespeed: {e}")
        return {"error": str(e)}


async def _run_firecrawl(url: str) -> dict:
    if not FIRECRAWL_KEY:
        return {"error": "firecrawl_key_missing"}
    try:
        async with httpx.AsyncClient(timeout=25) as c:
            r = await c.post(
                "https://api.firecrawl.dev/v1/scrape",
                headers={"Authorization": f"Bearer {FIRECRAWL_KEY}"},
                json={"url": url, "formats": ["markdown"], "onlyMainContent": True},
            )
            data = r.json().get("data", {})
            md = data.get("markdown", "") or ""
            meta = data.get("metadata", {}) or {}
            return {
                "title": meta.get("title", ""),
                "description": meta.get("description", ""),
                "og_image": meta.get("ogImage", ""),
                "word_count": len(md.split()),
                "has_h1": "# " in md[:2000],
                "has_structured_data": "application/ld+json" in md[:5000],
            }
    except Exception as e:
        logger.warning(f"[seo-audit] firecrawl: {e}")
        return {"error": str(e)}


async def _run_places(business_name: Optional[str], url: str) -> dict:
    if not (business_name and PLACES_KEY):
        return {}
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(
                "https://maps.googleapis.com/maps/api/place/findplacefromtext/json",
                params={"input": business_name, "inputtype": "textquery",
                        "fields": "place_id,name,rating,user_ratings_total,formatted_address",
                        "key": PLACES_KEY},
            )
            cand = (r.json().get("candidates") or [None])[0]
            return cand or {}
    except Exception as e:
        logger.warning(f"[seo-audit] places: {e}")
        return {}


def _local_score_from_v2(v2: dict, head: dict, html: str) -> dict:
    """Derive a faithful 4-axis score when external scanners fail.

    Strategy:
      • SEO            ← seo_audit_v2 score (already 100-pen-based).
      • Best practices ← inverse of major+critical count, capped 100.
      • Accessibility  ← deterministic head heuristics
        (viewport ok + favicon + canonical + lang + alt-friendly markup).
      • Performance    ← page-size + bundle-count + preconnect/preload heuristic.

    Returns dict with same shape as `_run_pagespeed`, plus title/desc/h1
    drawn from the local head parse so Firecrawl-fallback works."""
    issues = v2.get("issues") or []
    sev_count = v2.get("issues_by_severity") or {}
    crit = int(sev_count.get("critical", 0))
    major = int(sev_count.get("major", 0))
    minor = int(sev_count.get("minor", 0))

    # SEO from v2 directly
    seo = int(v2.get("score") or 0)

    # Best practices — start at 100, dock for severity
    bp = max(0, 100 - (crit * 12 + major * 6 + minor * 2))

    # Accessibility heuristic
    a11y_score = 100
    if not head.get("viewport"): a11y_score -= 25
    if not head.get("canonical"): a11y_score -= 5
    if not head.get("favicon"):   a11y_score -= 5
    if not re.search(r"<html[^>]*\slang=", html or "", re.IGNORECASE):
        a11y_score -= 8
    if "user-scalable=no" in (html or "").lower():
        a11y_score -= 12  # max-scale violation
    a11y = max(0, a11y_score)

    # Performance heuristic
    size = len(html or "")
    js_count = len(re.findall(r'<script[^>]+src=', html or "",
                                re.IGNORECASE))
    css_count = len(re.findall(
        r'<link[^>]+rel=["\']stylesheet["\']', html or "", re.IGNORECASE,
    ))
    has_preconnect = bool(re.search(
        r'rel=["\']preconnect["\']', html or "", re.IGNORECASE,
    ))
    has_preload = bool(re.search(
        r'rel=["\']preload["\']', html or "", re.IGNORECASE,
    ))
    has_font_swap = "font-display: swap" in (html or "").lower() \
        or "font-display:swap" in (html or "").lower()
    perf = 100
    if size > 200_000: perf -= 25
    elif size > 80_000: perf -= 10
    if js_count > 12: perf -= 20
    elif js_count > 7: perf -= 10
    if css_count > 5: perf -= 8
    if not has_preconnect: perf -= 6
    if not has_preload: perf -= 4
    if not has_font_swap: perf -= 4
    perf = max(0, min(100, perf))

    overall = int((perf + seo + a11y + bp) / 4)

    # Top 3 actionable opportunities for the free preview
    opps: list[dict] = []
    for it in issues[:3]:
        opps.append({
            "id":          it.get("code"),
            "title":       it.get("message", "")[:120],
            "description": "Auto-fixable by AUREM" if it.get("auto_fix")
                           else "Manual review recommended",
            "savings_ms":  0,
        })

    return {
        "performance":         perf,
        "seo":                 seo,
        "accessibility":       a11y,
        "best_practices":      bp,
        "overall_score":       overall,
        "opportunities":       opps,
        "title":               head.get("title", ""),
        "description":         head.get("description", ""),
        "has_h1":              True if (
            re.search(r"<h1[\s>]", html or "", re.IGNORECASE)
        ) else False,
        "has_structured_data": int(head.get("schema_org_blocks") or 0) > 0,
    }


def _score_summary(ps: dict, fc: dict) -> dict:
    perf = ps.get("performance", 0) if isinstance(ps, dict) else 0
    seo = ps.get("seo", 0) if isinstance(ps, dict) else 0
    a11y = ps.get("accessibility", 0) if isinstance(ps, dict) else 0
    bp = ps.get("best_practices", 0) if isinstance(ps, dict) else 0
    overall = int((perf + seo + a11y + bp) / 4)
    grade = "A+" if overall >= 95 else "A" if overall >= 85 else "B" if overall >= 70 else "C" if overall >= 55 else "D"
    return {
        "overall_score": overall, "grade": grade,
        "performance": perf, "seo": seo, "accessibility": a11y, "best_practices": bp,
        "has_structured_data": bool(fc.get("has_structured_data")),
        "has_h1": bool(fc.get("has_h1")),
        "title": fc.get("title", ""),
        "description": fc.get("description", ""),
    }


async def _send_preview_email(to_email: str, url: str, summary: dict, scan_id: str):
    if not RESEND_KEY:
        return
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            await c.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {RESEND_KEY}"},
                json={
                    "from": RESEND_FROM, "to": [to_email],
                    "subject": f"Your AUREM SEO preview for {url} — Grade {summary.get('grade', 'N/A')}",
                    "html": f"""
                    <h2>Your AUREM SEO Audit is ready</h2>
                    <p><strong>Site:</strong> {url}<br/>
                    <strong>Overall Grade:</strong> {summary.get('grade', '-')}<br/>
                    <strong>Performance:</strong> {summary.get('performance', 0)}/100<br/>
                    <strong>SEO:</strong> {summary.get('seo', 0)}/100</p>
                    <p>Unlock your full 20-issue teardown for just <strong>$49 CAD</strong>:</p>
                    <p><a href="https://aurem.live/audit?scan={scan_id}" style="background:#C9A84C;color:#000;padding:12px 24px;text-decoration:none;border-radius:6px;font-weight:bold;">Unlock Full Report →</a></p>
                    <p style="color:#888;font-size:12px;">AUREM — Polaris Built Inc.</p>
                    """,
                },
            )
    except Exception as e:
        logger.warning(f"[seo-audit] email send: {e}")


# ═════ Endpoints ═════
@router.post("/scan", response_model=ScanResponse)
async def run_scan(body: ScanRequest, request: Request):
    """Public scan — no auth. Returns free preview + saves full report."""
    if _db is None:
        raise HTTPException(503, "DB not ready")

    url = _normalize_url(body.url)
    try:
        parsed = urlparse(url)
        if not parsed.netloc:
            raise HTTPException(400, "Invalid URL")
    except Exception:
        raise HTTPException(400, "Invalid URL")

    # Bug-fix 136 — netloc check alone passed `169.254.169.254` etc. Block
    # private / loopback / link-local / metadata hosts before issuing the
    # three concurrent fetches (PSI, Firecrawl, direct httpx).
    from routers.intelligence_router import _block_ssrf
    _block_ssrf(url)

    scan_id = f"seo_{uuid.uuid4().hex[:12]}"

    # Run external probes CONCURRENTLY — these are I/O bound and independent.
    # Sequential await took ~30s (PSI 25s + Firecrawl 5s + Places 2s) and made
    # the system-pulse QA bot time out. Concurrent gather caps total at the
    # slowest call (~PSI ≈ 25s) and adds a per-task safety timeout so a
    # hanging external never holds up the response.
    async def _safe(coro, name: str, timeout: float):
        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except asyncio.TimeoutError:
            return {"error": f"{name}_timeout"}
        except Exception as e:
            return {"error": f"{name}_failed", "detail": str(e)[:120]}

    pagespeed_task = _safe(_run_pagespeed(url), "pagespeed", timeout=28.0)
    firecrawl_task = _safe(_run_firecrawl(url), "firecrawl", timeout=15.0)
    if body.business_name:
        places_task = _safe(_run_places(body.business_name, url), "places", timeout=10.0)
    else:
        async def _empty(): return {}
        places_task = _empty()

    pagespeed, firecrawl, places = await asyncio.gather(
        pagespeed_task, firecrawl_task, places_task, return_exceptions=False
    )

    # iter 282al-9 — local fallback when PSI / Firecrawl error or quota'd.
    # PSI quota exhaustion was reporting aurem.live as 0/100 even though the
    # actual SEO build is excellent. Fall back to seo_audit_v2's deterministic
    # heuristic + an in-house performance proxy so the customer never sees a
    # garbage score.
    psi_failed = (not isinstance(pagespeed, dict)
                   or pagespeed.get("error")
                   or all(pagespeed.get(k, 0) == 0
                           for k in ("performance", "seo",
                                      "accessibility", "best_practices")))
    fc_failed = (not isinstance(firecrawl, dict)
                  or firecrawl.get("error")
                  or not firecrawl.get("title"))

    local_fallback = None
    if psi_failed or fc_failed:
        try:
            from services.seo_audit_v2 import (
                fetch_html, parse_head_tags, run_seo_audit_v2,
            )
            v2 = await asyncio.wait_for(run_seo_audit_v2(url), timeout=15.0)
            html = await asyncio.wait_for(fetch_html(url), timeout=10.0)
            head = parse_head_tags(html) if html else {}
            local_fallback = _local_score_from_v2(v2, head, html)
            logger.info(f"[seo-audit] {url} PSI quota'd; "
                         f"local fallback score={local_fallback['overall_score']}")
        except Exception as e:
            logger.warning(f"[seo-audit] local fallback failed: {e}")

    if local_fallback:
        if psi_failed:
            pagespeed = {**(pagespeed if isinstance(pagespeed, dict) else {}),
                          "performance":      local_fallback["performance"],
                          "seo":              local_fallback["seo"],
                          "accessibility":    local_fallback["accessibility"],
                          "best_practices":   local_fallback["best_practices"],
                          "opportunities":    local_fallback["opportunities"],
                          "fallback_used":    "local"}
        if fc_failed:
            firecrawl = {**(firecrawl if isinstance(firecrawl, dict) else {}),
                          "title":               local_fallback["title"],
                          "description":         local_fallback["description"],
                          "has_h1":              local_fallback["has_h1"],
                          "has_structured_data": local_fallback["has_structured_data"],
                          "fallback_used":       "local"}

    summary = _score_summary(pagespeed, firecrawl)
    opportunities = pagespeed.get("opportunities", []) if isinstance(pagespeed, dict) else []

    # Save
    doc = {
        "scan_id": scan_id,
        "url": url,
        "email": body.email.lower(),
        "business_name": body.business_name,
        "consent_marketing": body.consent_marketing,
        "ip": request.client.host if request.client else "unknown",
        "summary": summary,
        "full_report": {
            "pagespeed": pagespeed,
            "firecrawl": firecrawl,
            "places": places,
            "all_opportunities": opportunities,
        },
        "paid": False,
        "stripe_session_id": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await _db.seo_audits.insert_one(doc)

    # Fire-and-forget preview email
    try:
        await _send_preview_email(body.email, url, summary, scan_id)
    except Exception:
        pass

    return ScanResponse(
        scan_id=scan_id,
        summary=summary,
        top_issues=opportunities[:3],  # Free: top 3 only
        full_report_locked=True,
    )


@router.get("/report/{scan_id}")
async def get_report(scan_id: str):
    """Fetch report. Full detail only if paid=True."""
    if _db is None:
        raise HTTPException(503, "DB not ready")
    doc = await _db.seo_audits.find_one({"scan_id": scan_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Report not found")
    if not doc.get("paid"):
        # Preview mode
        return {
            "scan_id": scan_id,
            "url": doc.get("url"),
            "summary": doc.get("summary"),
            "top_issues": (doc.get("full_report", {}).get("all_opportunities", []) or [])[:3],
            "locked": True,
            "unlock_price_cad": 49,
        }
    return {
        "scan_id": scan_id,
        "url": doc.get("url"),
        "summary": doc.get("summary"),
        "full_report": doc.get("full_report"),
        "locked": False,
    }


class CheckoutBody(BaseModel):
    scan_id: str
    return_url: Optional[str] = None


@router.post("/checkout")
async def create_checkout(body: CheckoutBody, request: Request):
    """Create Stripe embedded checkout for $49 SEO audit unlock."""
    if not stripe.api_key:
        raise HTTPException(503, "Stripe not configured")
    if not SEO_AUDIT_PRICE_ID:
        await ensure_stripe_product()
    if not SEO_AUDIT_PRICE_ID:
        raise HTTPException(503, "SEO audit product not initialized")

    doc = await _db.seo_audits.find_one({"scan_id": body.scan_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Scan not found")
    if doc.get("paid"):
        return {"already_paid": True, "scan_id": body.scan_id}

    origin = (body.return_url or "").rstrip("/") or "https://aurem.live"
    try:
        # iter 280.8: gate automatic_tax behind env flag (default OFF)
        _seo_kwargs = dict(
            ui_mode="embedded",
            mode="payment",
            line_items=[{"price": SEO_AUDIT_PRICE_ID, "quantity": 1}],
            customer_email=doc.get("email"),
            return_url=f"{origin}/audit?scan={body.scan_id}&session_id={{CHECKOUT_SESSION_ID}}",
            metadata={"scan_id": body.scan_id, "product": "seo_audit_49"},
        )
        if os.environ.get("STRIPE_AUTOMATIC_TAX", "").strip().lower() in ("1", "true", "yes", "on"):
            _seo_kwargs["automatic_tax"] = {"enabled": True}
        session = stripe.checkout.Session.create(**_seo_kwargs)
    except Exception as e:
        logger.exception("[seo-audit] checkout failed")
        raise HTTPException(500, f"Stripe error: {e}")

    await _db.seo_audits.update_one(
        {"scan_id": body.scan_id},
        {"$set": {"stripe_session_id": session.id}},
    )
    return {"client_secret": session.client_secret, "session_id": session.id}


@router.get("/product")
async def get_product_info():
    return {
        "price_id": SEO_AUDIT_PRICE_ID,
        "amount_cad": 49,
        "ready": bool(SEO_AUDIT_PRICE_ID),
    }


# Called by stripe webhook handler when payment completes
async def mark_paid(session_id: str):
    if _db is None:
        return
    await _db.seo_audits.update_one(
        {"stripe_session_id": session_id},
        {"$set": {"paid": True, "paid_at": datetime.now(timezone.utc).isoformat()}},
    )


# ═════════════════════════════════════════════════════════
# V2: Deep Audit + Auto-Fix Engine
# ═════════════════════════════════════════════════════════

@router.post("/v2/scan")
async def deep_scan_v2(body: ScanRequest):
    """
    Run the 15-dimension deep audit (Schema.org, OG, Twitter, robots.txt AI bots,
    llms.txt, sitemap, canonical, viewport, etc.) — detects everything v1 missed.
    """
    from services.seo_audit_v2 import run_seo_audit_v2
    url = _normalize_url(body.url)
    # Bug-fix 136 — /v2/scan also fetched user-supplied URL with no IP guard.
    from routers.intelligence_router import _block_ssrf
    _block_ssrf(url)
    report = await run_seo_audit_v2(url)
    if _db is not None:
        await _db.seo_audits_v2.insert_one({
            **report,
            "email": body.email.lower(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    return report


@router.post("/v2/generate-fixes")
async def generate_fixes_endpoint(payload: dict):
    """
    Takes an audit report + optional business info, returns ready-to-deploy fixes.
    Body: { "audit": {...}, "business": {"name": "X", "url": "https://x.com", ...} }
    """
    from services.seo_autofix_engine import generate_fixes
    audit = payload.get("audit")
    if not audit:
        raise HTTPException(400, "Missing 'audit' in payload")
    business = payload.get("business")
    fixes = generate_fixes(audit, business)
    return {
        "fix_count": len(fixes),
        "fixes": fixes,
    }


@router.get("/self-health")
async def self_health():
    """
    AUTHENTICITY PROOF — runs the full v2 audit on aurem.live ITSELF.
    Public endpoint so anyone (customer, investor, skeptic) can verify
    AUREM practices what it preaches. No auth required.
    """
    from services.seo_audit_v2 import run_seo_audit_v2
    report = await run_seo_audit_v2("https://aurem.live")
    # Also run against the preview URL so we see the live serving version
    preview_url = os.environ.get("PUBLIC_APP_URL") or ""
    preview_report = None
    if preview_url and "aurem.live" not in preview_url:
        try:
            preview_report = await run_seo_audit_v2(preview_url)
        except Exception:
            preview_report = None
    return {
        "production": report,
        "preview": preview_report,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
