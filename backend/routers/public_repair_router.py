"""
Public Repair-Quote Lead Magnet (iter 281.4 / Phase 2.4)
=========================================================
Anonymous public endpoint — anyone can drop a website URL + email and get
a free 6-point audit + Claude diagnosis. Lead is auto-saved to MongoDB
`db.leads` and a follow-up email is queued via existing Resend wiring.

Endpoints:
  POST /api/public/repair-quote/audit  {url, email, business_name?}
  GET  /api/public/repair-quote/health  (liveness)

Rate-limited to 3 requests / minute per IP at the middleware layer.
NO auth — the lead magnet must be frictionless.
"""
from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/public/repair-quote", tags=["Public Repair Quote"])

_db = None
_URL_RE = re.compile(r"^https?://[^\s]+$", re.IGNORECASE)


def set_db(db):
    global _db
    _db = db


def _get_db():
    return _db


class QuoteRequest(BaseModel):
    url: str = Field(..., min_length=4, max_length=400)
    email: EmailStr
    business_name: Optional[str] = Field(None, max_length=200)
    contact_phone: Optional[str] = Field(None, max_length=32)
    consent: bool = True  # CASL-friendly default; UI must show consent copy


@router.get("/health")
async def health():
    return {"ok": True, "db_wired": _get_db() is not None}


@router.get("/{quote_id}")
async def get_shareable_report(quote_id: str):
    """Read-only public lookup — sanitized projection, safe to share via
    aurem.live/r/{quote_id}. Used by the ShareableReport React page.
    """
    db = _get_db()
    if db is None:
        raise HTTPException(503, "Database not wired")
    if quote_id == "audit":  # avoid clobbering POST /audit GET fallback
        raise HTTPException(404, "Not found")
    doc = await db.website_repair_reports.find_one({"report_id": quote_id})
    if not doc:
        raise HTTPException(404, "Report not found")
    out = {
        "quote_id": doc.get("report_id") or quote_id,
        "url": doc.get("url"),
        "business_name": doc.get("business_name"),
        "overall_score": doc.get("overall_score"),
        "score_breakdown": (doc.get("audit") or {}).get("score_breakdown", {}),
        "issues": ((doc.get("audit") or {}).get("issues") or [])[:8],
        "diagnosis": doc.get("diagnosis"),
        "repair_recommended": doc.get("repair_recommended"),
        "rebuild_recommended": doc.get("rebuild_recommended"),
        "created_at": doc.get("created_at"),
    }
    return {"ok": True, "report": out}


@router.post("/audit")
async def public_audit(req: QuoteRequest, request: Request):
    """Run the audit + diagnosis + persist a lead. No auth required."""
    db = _get_db()
    if db is None:
        raise HTTPException(503, "Database not wired")

    # Light URL hygiene — allow naked domains.
    url = req.url.strip()
    if not _URL_RE.match(url):
        url = "https://" + url
    if not _URL_RE.match(url):
        raise HTTPException(400, "Invalid URL")

    # Run the existing real audit (Playwright + PageSpeed + html probes)
    from services.website_audit_service import real_audit
    audit = await real_audit(url)
    if not audit.get("ok"):
        raise HTTPException(400, f"Audit failed: {audit.get('error', 'unknown')}")

    # Optional Claude diagnosis (graceful degradation if LLM down).
    diagnosis = ""
    try:
        from routers.website_repair_router import _generate_diagnosis
        diagnosis = await _generate_diagnosis(audit, req.business_name)
    except Exception as e:
        logger.debug(f"[public-repair] diagnosis skipped: {e}")

    quote_id = str(uuid.uuid4())
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent", "")[:200]

    # Persist lead — single source of truth `db.leads` (already used by
    # OpenFang + pipeline). Tag with source so sales can segment.
    lead_doc = {
        "lead_id": quote_id,
        "source": "public_repair_quote",
        "email": req.email,
        "business_name": req.business_name or url,
        "phone": req.contact_phone,
        "url": audit["url"],
        "score": audit.get("overall_score"),
        "issues_count": len(audit.get("issues") or []),
        "repair_recommended": audit.get("repair_recommended"),
        "rebuild_recommended": audit.get("rebuild_recommended"),
        "consent": bool(req.consent),
        "ip": ip,
        "user_agent": ua,
        "stage": "audited",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        await db.leads.insert_one(lead_doc)
    except Exception as e:
        logger.warning(f"[public-repair] lead save failed: {e}")
    lead_doc.pop("_id", None)

    # Also persist the full report into website_repair_reports for the
    # admin dashboard — this lets ORA "see" public-magnet leads alongside
    # admin-initiated audits.
    try:
        await db.website_repair_reports.insert_one({
            "report_id": quote_id,
            "url": audit["url"],
            "business_name": req.business_name or url,
            "contact_email": req.email,
            "contact_phone": req.contact_phone,
            "audit": audit,
            "diagnosis": diagnosis,
            "overall_score": audit.get("overall_score"),
            "repair_recommended": audit.get("repair_recommended"),
            "rebuild_recommended": audit.get("rebuild_recommended"),
            "status": "public_lead",
            "offer_sent_channels": [],
            "invoice_url": None,
            "stripe_session_id": None,
            "created_by": "public:repair-quote",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "lead_source": "public_repair_quote",
            "lead_id": quote_id,
        })
    except Exception as e:
        logger.debug(f"[public-repair] report mirror failed: {e}")

    # Fire-and-forget email to the lead with a copy of the report.
    try:
        from services.email_service_resend import send_email
        biz = req.business_name or audit["url"]
        score = audit.get("overall_score") or 0
        body = (
            f"<h2>Your AUREM Free Audit — {biz}</h2>"
            f"<p>Overall score: <b>{score}/100</b></p>"
            f"<pre style='font-family:system-ui;white-space:pre-wrap'>"
            f"{(diagnosis or 'Diagnosis pending — our team will follow up shortly.')[:4000]}"
            f"</pre>"
            f"<p>We'll reach out within 24 hours with a fixed-price repair quote. "
            f"Reply to this email for an instant quote.</p>"
            f"<p>— AUREM Repair Team</p>"
        )
        await send_email(
            to=req.email,
            subject=f"Free 6-point website audit — {biz}",
            html=body,
        )
    except Exception as e:
        logger.debug(f"[public-repair] email queue failed: {e}")

    return {
        "ok": True,
        "quote_id": quote_id,
        "url": audit["url"],
        "overall_score": audit.get("overall_score"),
        "issues": (audit.get("issues") or [])[:5],
        "score_breakdown": audit.get("score_breakdown", {}),
        "diagnosis": diagnosis,
        "next_step": "We've saved your audit. Watch your inbox for a full repair quote within 24h.",
    }
