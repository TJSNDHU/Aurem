"""
Public Audit Request Router — commercial-launch lead capture.

No authentication required. Anyone who submits the `/contact` form or clicks
"Get Free Audit" on the landing page lands here. Every submission:
  • Stores a document in `audit_leads` for admin review in Mission Control.
  • Is rate-limited per IP (10/hour) to block abuse.
  • Fires an email notification to the owner (best-effort, never blocks).

This is intentionally lightweight — no tenant scoping, no RBAC — because
the prospect has no account yet. Conversion happens when the admin follows
up and creates the real tenant.
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime, timezone
import logging
import uuid
import asyncio
import os

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/public", tags=["Public Lead Capture"])

db = None


def set_db(database):
    global db
    db = database


# ──────────────────────────────────────────────────────────────
# Simple per-IP rate limiter (in-process; sufficient for pre-scale)
# ──────────────────────────────────────────────────────────────
_ip_hits: dict = {}
_RATE_LIMIT = 10  # submissions
_WINDOW_S = 3600  # per hour


def _rate_limited(ip: str) -> bool:
    now = datetime.now(timezone.utc).timestamp()
    hits = [t for t in _ip_hits.get(ip, []) if now - t < _WINDOW_S]
    hits.append(now)
    _ip_hits[ip] = hits
    return len(hits) > _RATE_LIMIT


class AuditRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    website: Optional[str] = Field(default=None, max_length=300)
    message: Optional[str] = Field(default=None, max_length=2000)
    topic: str = Field(default="audit", max_length=40)  # quote|audit|support|partnership
    source: Optional[str] = Field(default="contact_form", max_length=80)
    phone: Optional[str] = Field(default=None, max_length=32)
    consent_email: bool = Field(default=False, description="CASL: opt-in to marketing email")
    consent_sms: bool = Field(default=False, description="CASL: opt-in to SMS / voice")


async def _notify_owner(lead: dict):
    """Best-effort email to ora@aurem.live. Never raises."""
    try:
        # Try Resend if available
        resend_key = os.environ.get("RESEND_API_KEY")
        if not resend_key:
            return
        import httpx
        async with httpx.AsyncClient(timeout=3.0) as client:
            await client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {resend_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": "AUREM Lead <noreply@aurem.live>",
                    "to": ["ora@aurem.live"],
                    "subject": f"[AUREM] New {lead['topic']} request — {lead['name']}",
                    "text": (
                        f"New lead captured from {lead.get('source')}:\n\n"
                        f"Name: {lead['name']}\n"
                        f"Email: {lead['email']}\n"
                        f"Website: {lead.get('website') or '-'}\n"
                        f"Topic: {lead['topic']}\n\n"
                        f"Message:\n{lead.get('message') or '-'}\n\n"
                        f"— ORA"
                    ),
                },
            )
    except Exception as e:  # pragma: no cover
        logger.warning(f"[audit_lead] owner email skipped: {e}")


@router.post("/audit-request")
async def submit_audit_request(req: AuditRequest, request: Request):
    """Capture a public audit/quote/support request. Stores to `audit_leads`."""
    if db is None:
        raise HTTPException(status_code=503, detail="service not ready")

    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "unknown").split(",")[0].strip()
    if _rate_limited(ip):
        raise HTTPException(status_code=429, detail="too many submissions, please try again later")

    lead_id = f"lead_{uuid.uuid4().hex[:16]}"
    doc = {
        "id": lead_id,
        "name": req.name.strip(),
        "email": req.email.lower().strip(),
        "phone": (req.phone or "").strip() or None,
        "website": (req.website or "").strip() or None,
        "message": (req.message or "").strip() or None,
        "topic": req.topic,
        "source": req.source or "contact_form",
        "ip": ip,
        "user_agent": request.headers.get("user-agent", "")[:300],
        "status": "new",
        "consent_email": bool(req.consent_email),
        "consent_sms": bool(req.consent_sms),
        "consent_captured_at": datetime.now(timezone.utc).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    # Run CASL-safe enrichment in background (NumVerify + IPStack)
    try:
        from services.lead_enrichment_casl import enrich_lead
        enrichment = await enrich_lead(doc.get("phone"), ip)
        if enrichment:
            doc["enrichment"] = enrichment
    except Exception as _enrich_err:
        logger.debug(f"[audit_lead] enrichment skipped: {_enrich_err}")

    try:
        await db.audit_leads.insert_one(doc)
        doc.pop("_id", None)
    except Exception as e:
        logger.error(f"[audit_lead] insert failed: {e}")
        raise HTTPException(status_code=500, detail="could not save request")

    # Fire owner notification in background (never blocks the response)
    asyncio.create_task(_notify_owner(doc))

    return {"ok": True, "id": lead_id, "message": "Request received. We'll respond within 2 business hours."}


@router.get("/audit-request/count")
async def count_audit_requests():
    """Tiny counter used by landing page social-proof. Public, anonymous."""
    if db is None:
        return {"count": 0}
    try:
        n = await db.audit_leads.estimated_document_count()
        return {"count": int(n)}
    except Exception:
        return {"count": 0}
