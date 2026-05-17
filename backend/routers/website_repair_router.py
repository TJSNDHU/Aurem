"""
Client Website Repair Service Router (iter 281.3 — Phase 2.5 preview)
=====================================================================
Wires together existing pieces (no new infra):
  - website_audit_service.real_audit() — SSL, speed, mobile, broken links,
    contact form, social links, copyright year (Playwright + PageSpeed)
  - Emergent LLM (Claude Sonnet 4.5) — turns audit JSON into a
    human-readable diagnosis report
  - email_service_resend.send_email + twilio_whatsapp.send_whatsapp
    — auto-send repair offer
  - Stripe Checkout via existing service_catalog flow — invoice trigger

Endpoints (all admin-gated):
  POST /api/admin/website-repair/audit        run audit + diagnosis
  GET  /api/admin/website-repair/reports      list recent reports
  GET  /api/admin/website-repair/reports/{id} fetch one
  POST /api/admin/website-repair/{id}/send-offer {channel: email|whatsapp|both}
  POST /api/admin/website-repair/{id}/create-invoice {amount_cents, currency}
  GET  /api/admin/website-repair/health       public probe
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from utils.admin_guard import verify_admin

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/website-repair", tags=["Client Website Repair"])

_db = None


def set_db(db):
    global _db
    _db = db


def _get_db():
    return _db


# ─── Models ─────────────────────────────────────────────────────────
class AuditRequest(BaseModel):
    url: str = Field(..., min_length=4, max_length=400)
    business_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None  # E.164 format e.g. +14165551234
    notes: Optional[str] = None


class SendOfferRequest(BaseModel):
    channel: str = Field("email", pattern="^(email|whatsapp|both)$")
    custom_intro: Optional[str] = None


class CreateInvoiceRequest(BaseModel):
    amount_cents: int = Field(..., ge=2000, le=500000)  # CAD $20 → $5000
    currency: str = Field("cad", pattern="^[a-z]{3}$")
    description: Optional[str] = None


# ─── Diagnosis (Claude via Emergent LLM) ────────────────────────────
async def _generate_diagnosis(audit: Dict[str, Any], business_name: Optional[str]) -> str:
    """Turn raw audit JSON into a human-friendly diagnosis report."""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        prompt = (
            f"Website audit for **{business_name or audit.get('url')}** "
            f"(score {audit.get('overall_score', 0)}/100). "
            f"Issues:\n"
            + "\n".join(
                f"- [{i.get('severity', 'low')}] {i.get('title')}: {i.get('detail')}"
                for i in (audit.get("issues") or [])[:10]
            )
            + f"\n\nRaw signals: SSL={audit.get('ssl', {}).get('valid')}, "
            f"PageSpeed={audit.get('pagespeed', {}).get('score')}, "
            f"Mobile={audit.get('mobile', {}).get('ok')}, "
            f"BrokenLinks={audit.get('broken_links', {}).get('count', 0)}, "
            f"ContactForm={audit.get('contact_form')}, "
            f"CopyrightYear={audit.get('copyright_year')}. "
        )
        chat = LlmChat(
            api_key=os.environ.get("EMERGENT_LLM_KEY", ""),
            session_id=f"webrepair_{uuid.uuid4()}",
            system_message=(
                "You are AUREM's website diagnosis writer. Given an audit summary, "
                "produce a short report (~120-180 words) for the business owner: "
                "(1) one-paragraph plain-English summary of the problem, "
                "(2) bulleted top 3 fixes ranked by revenue-impact, "
                "(3) one-line CTA pitching AUREM Repair Service. "
                "Tone: confident, practical, no jargon, no emoji walls. "
                "Hinglish allowed if naturally appropriate."
            ),
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")
        out = await chat.send_message(UserMessage(text=prompt))
        return (out or "").strip() or "Diagnosis pending — Claude returned empty."
    except Exception as e:
        logger.warning(f"[website-repair] diagnosis LLM failed: {e}")
        # Graceful degradation — synthesize a deterministic summary.
        issues = audit.get("issues") or []
        bullets = "\n".join(f"- {i.get('title')}" for i in issues[:3])
        score = audit.get("overall_score", 0)
        return (
            f"Audit Summary — {business_name or audit.get('url')}\n\n"
            f"Overall score: {score}/100. Key issues found:\n{bullets or '- (no critical issues)'}\n\n"
            "AUREM Repair Service can fix these issues in 48 hours."
        )


# ─── Endpoints ──────────────────────────────────────────────────────
@router.get("/health")
async def health():
    return {"ok": True, "db_wired": _get_db() is not None}


@router.post("/audit")
async def run_audit(req: AuditRequest, authorization: Optional[str] = Header(None)):
    payload = verify_admin(authorization)
    db = _get_db()
    if db is None:
        raise HTTPException(503, "Database not wired")

    from services.website_audit_service import real_audit
    audit = await real_audit(req.url)
    if not audit.get("ok"):
        raise HTTPException(400, f"Audit failed: {audit.get('error', 'unknown')}")

    diagnosis = await _generate_diagnosis(audit, req.business_name)

    report_id = str(uuid.uuid4())
    doc = {
        "report_id": report_id,
        "url": audit["url"],
        "business_name": req.business_name,
        "contact_email": req.contact_email,
        "contact_phone": req.contact_phone,
        "notes": req.notes,
        "audit": audit,
        "diagnosis": diagnosis,
        "overall_score": audit.get("overall_score"),
        "repair_recommended": audit.get("repair_recommended"),
        "rebuild_recommended": audit.get("rebuild_recommended"),
        "status": "audited",
        "offer_sent_channels": [],
        "invoice_url": None,
        "stripe_session_id": None,
        "created_by": payload.get("email") or "admin",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.website_repair_reports.insert_one(doc)
    doc.pop("_id", None)
    return {"ok": True, "report": doc}


@router.get("/reports")
async def list_reports(authorization: Optional[str] = Header(None)):
    verify_admin(authorization)
    db = _get_db()
    if db is None:
        raise HTTPException(503, "Database not wired")
    items: List[Dict[str, Any]] = []
    cursor = db.website_repair_reports.find().sort("created_at", -1).limit(50)
    async for d in cursor:
        d.pop("_id", None)
        # Keep the response light — strip raw audit, leave summary only.
        d["audit_summary"] = {
            "issues_count": len(d.get("audit", {}).get("issues", []) or []),
            "score": d.get("overall_score"),
        }
        d.pop("audit", None)
        items.append(d)
    return {"ok": True, "count": len(items), "items": items}


@router.get("/reports/{report_id}")
async def get_report(report_id: str, authorization: Optional[str] = Header(None)):
    verify_admin(authorization)
    db = _get_db()
    if db is None:
        raise HTTPException(503, "Database not wired")
    doc = await db.website_repair_reports.find_one({"report_id": report_id})
    if not doc:
        raise HTTPException(404, "Report not found")
    doc.pop("_id", None)
    return {"ok": True, "report": doc}


def _offer_text(report: Dict[str, Any], custom_intro: Optional[str]) -> str:
    biz = report.get("business_name") or report.get("url")
    score = report.get("overall_score") or 0
    intro = custom_intro or (
        f"Hi {biz}, AUREM ran a free 6-point audit on your website "
        f"({report.get('url')}). Overall score: {score}/100."
    )
    return (
        f"{intro}\n\n"
        f"{report.get('diagnosis', '')}\n\n"
        "Reply YES to get the full repair plan + a fixed-price quote in 24h."
    )


@router.post("/{report_id}/send-offer")
async def send_offer(
    report_id: str,
    req: SendOfferRequest,
    authorization: Optional[str] = Header(None),
):
    payload = verify_admin(authorization)
    db = _get_db()
    if db is None:
        raise HTTPException(503, "Database not wired")
    report = await db.website_repair_reports.find_one({"report_id": report_id})
    if not report:
        raise HTTPException(404, "Report not found")

    text = _offer_text(report, req.custom_intro)
    sent: Dict[str, Any] = {}

    if req.channel in ("email", "both"):
        to_email = report.get("contact_email")
        if not to_email:
            sent["email"] = {"ok": False, "error": "no_contact_email"}
        else:
            try:
                from services.email_service_resend import send_email
                ok = await send_email(
                    to=to_email,
                    subject=f"Free website audit — {report.get('business_name') or report.get('url')}",
                    html=f"<pre style='font-family:system-ui;white-space:pre-wrap'>{text}</pre>",
                )
                sent["email"] = {"ok": bool(ok)}
            except Exception as e:
                logger.warning(f"[website-repair] email send failed: {e}")
                sent["email"] = {"ok": False, "error": str(e)[:120]}

    if req.channel in ("whatsapp", "both"):
        to_phone = report.get("contact_phone")
        if not to_phone:
            sent["whatsapp"] = {"ok": False, "error": "no_contact_phone"}
        else:
            try:
                from services.twilio_whatsapp import send_whatsapp
                res = await send_whatsapp(to_phone=to_phone, body=text[:1500])
                sent["whatsapp"] = {"ok": bool(res and res.get("sid")), "sid": (res or {}).get("sid")}
            except Exception as e:
                logger.warning(f"[website-repair] whatsapp send failed: {e}")
                sent["whatsapp"] = {"ok": False, "error": str(e)[:120]}

    channels_ok = [c for c, v in sent.items() if v.get("ok")]
    await db.website_repair_reports.update_one(
        {"report_id": report_id},
        {
            "$addToSet": {"offer_sent_channels": {"$each": channels_ok}},
            "$set": {
                "last_offer_at": datetime.now(timezone.utc).isoformat(),
                "last_offer_by": payload.get("email") or "admin",
                "status": "offer_sent" if channels_ok else "offer_failed",
            },
        },
    )

    return {"ok": bool(channels_ok), "sent": sent}


@router.post("/{report_id}/create-invoice")
async def create_invoice(
    report_id: str,
    req: CreateInvoiceRequest,
    authorization: Optional[str] = Header(None),
):
    """Create a Stripe Checkout session for the repair fee.

    Reuses existing Stripe LIVE keys from the platform — no new wiring.
    The checkout URL is stored on the report so the admin can forward
    it to the customer (or include it in the next offer message).
    """
    payload = verify_admin(authorization)
    db = _get_db()
    if db is None:
        raise HTTPException(503, "Database not wired")
    report = await db.website_repair_reports.find_one({"report_id": report_id})
    if not report:
        raise HTTPException(404, "Report not found")

    try:
        from emergentintegrations.payments.stripe.checkout import StripeCheckout, CheckoutSessionRequest
        sk = os.environ.get("STRIPE_SECRET_KEY", "")
        if not sk:
            raise HTTPException(503, "Stripe key not configured")
        host_url = os.environ.get("AUREM_PUBLIC_URL", "https://aurem.live").rstrip("/")
        checkout = StripeCheckout(api_key=sk, webhook_url=f"{host_url}/api/stripe/webhook")
        biz = report.get("business_name") or report.get("url") or "Customer"
        desc = req.description or f"AUREM Website Repair — {biz}"
        session = await checkout.create_checkout_session(CheckoutSessionRequest(
            amount=req.amount_cents / 100.0,
            currency=req.currency.lower(),
            success_url=f"{host_url}/repair/thank-you?report={report_id}",
            cancel_url=f"{host_url}/repair/cancelled?report={report_id}",
            metadata={
                "kind": "website_repair",
                "report_id": report_id,
                "url": report.get("url") or "",
                "description": desc[:200],
            },
        ))
        await db.website_repair_reports.update_one(
            {"report_id": report_id},
            {"$set": {
                "invoice_url": session.url,
                "stripe_session_id": session.session_id,
                "invoice_amount_cents": req.amount_cents,
                "invoice_currency": req.currency.lower(),
                "invoice_created_by": payload.get("email") or "admin",
                "invoice_created_at": datetime.now(timezone.utc).isoformat(),
                "status": "invoice_created",
            }},
        )
        return {
            "ok": True,
            "checkout_url": session.url,
            "session_id": session.session_id,
            "amount_cents": req.amount_cents,
            "currency": req.currency.lower(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[website-repair] invoice create failed: {e}")
        raise HTTPException(500, f"Stripe error: {e}")
