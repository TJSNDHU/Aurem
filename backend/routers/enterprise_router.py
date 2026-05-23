"""
routers/enterprise_router.py — iter 332b Batch A

Two surfaces shipped this iter:

  • GET  /api/enterprise/audit          — unified audit query (admin)
  • GET  /api/enterprise/audit/export   — CSV export for auditors (admin)
  • POST /api/enterprise/leads          — Contact Sales form ingest (PUBLIC)

The rest of the Batch A spec (RBAC complete wiring + white-label UI +
custom domain UI + API key UI + enterprise dashboard) is queued for
iter 332b-2 because each is a multi-hour slice.
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/enterprise", tags=["enterprise"])

_db = None


def set_db(database):
    global _db
    _db = database
    try:
        from services.unified_audit import set_db as _set_ua_db
        _set_ua_db(database)
    except Exception as e:
        logger.warning(f"[enterprise] unified_audit wiring failed: {e}")


def _ensure_admin(request: Request) -> None:
    try:
        from services.admin_security import ensure_admin
        ensure_admin(request)
    except HTTPException:
        raise
    except Exception:
        auth = request.headers.get("authorization") or ""
        if not auth.lower().startswith("bearer "):
            raise HTTPException(401, "auth required")


# ── Unified audit query ─────────────────────────────────────────────

@router.get("/audit")
async def audit_query(
    request: Request,
    user_id:           Optional[str] = None,
    action:            Optional[str] = None,
    resource:          Optional[str] = None,
    result:            Optional[str] = None,
    source_collection: Optional[str] = None,
    date_from:         Optional[str] = None,
    date_to:           Optional[str] = None,
    limit:             int = 100,
    offset:            int = 0,
) -> dict[str, Any]:
    _ensure_admin(request)
    from services.unified_audit import query_events, set_db as _set_db
    if _db is not None:
        _set_db(_db)
    return await query_events(
        user_id=user_id, action=action, resource=resource,
        result=result, source_collection=source_collection,
        date_from=date_from, date_to=date_to,
        limit=limit, offset=offset,
    )


@router.get("/audit/export")
async def audit_export(
    request: Request,
    user_id:           Optional[str] = None,
    action:            Optional[str] = None,
    date_from:         Optional[str] = None,
    date_to:           Optional[str] = None,
):
    _ensure_admin(request)
    from services.unified_audit import export_events_csv, set_db as _set_db
    if _db is not None:
        _set_db(_db)
    csv_text = await export_events_csv(
        user_id=user_id, action=action,
        date_from=date_from, date_to=date_to,
    )
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={
            "Content-Disposition":
                f'attachment; filename="audit_export_{datetime.now(timezone.utc).strftime("%Y%m%d")}.csv"',
        },
    )


# ── Contact Sales (PUBLIC) ──────────────────────────────────────────

class EnterpriseLeadBody(BaseModel):
    company:    str = Field(..., min_length=1, max_length=120)
    email:      str = Field(..., max_length=160)
    team_size:  str = Field(..., max_length=40)
    intent:     str = Field("", max_length=2000)


@router.post("/leads")
async def submit_enterprise_lead(
    body: EnterpriseLeadBody,
    request: Request,
) -> dict[str, Any]:
    """Public — no auth. Founder gets a Telegram alert; prospect gets
    an auto-reply email. Lead row stored in db.enterprise_leads."""
    if _db is None:
        raise HTTPException(503, "db not ready")
    if "@" not in body.email:
        raise HTTPException(400, "invalid_email")

    lead_id = uuid.uuid4().hex
    row = {
        "lead_id":    lead_id,
        "company":    body.company.strip(),
        "email":      body.email.strip().lower(),
        "team_size":  body.team_size.strip(),
        "intent":     body.intent.strip(),
        "ip_address": (request.client.host if request.client else None),
        "user_agent": request.headers.get("user-agent", "")[:200],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status":     "new",
    }
    await _db.enterprise_leads.insert_one(row)

    # Audit row
    try:
        from services.unified_audit import write_event
        await write_event(
            action="enterprise_lead_submitted",
            resource=f"company:{body.company}",
            result="ok",
            user_id=None,
            ip_address=row["ip_address"],
            user_agent=row["user_agent"],
            source_collection="enterprise_leads",
            extra={"team_size": body.team_size, "email": row["email"]},
        )
    except Exception as e:
        logger.debug(f"[enterprise/leads] audit write skipped: {e}")

    # Telegram alert (best-effort)
    try:
        from services.telegram_bot_service import send_telegram_alert
        msg = (
            f"🎯 ENTERPRISE LEAD\n"
            f"Company: {body.company}\n"
            f"Email:   {row['email']}\n"
            f"Size:    {body.team_size}\n"
        )
        if body.intent:
            msg += f"\nNeed: {body.intent[:400]}"
        await send_telegram_alert(msg)
    except Exception as e:
        logger.debug(f"[enterprise/leads] telegram alert skipped: {e}")

    # Auto-reply email (best-effort)
    try:
        from services.email_service_resend import send_email
        site = (os.environ.get("FRONTEND_URL") or "https://aurem.live").rstrip("/")
        await send_email(
            to=row["email"],
            subject="AUREM CTO — We got your note",
            text=(
                f"Thanks for reaching out, {body.company}.\n\n"
                f"A real human at AUREM will read your message and reply within "
                f"one business day. Usually faster — we're based in Canada and "
                f"this inbox pings me on my phone.\n\n"
                f"In the meantime, the docs are at {site}/developers/docs and "
                f"the SLA page lives at {site}/developers/status.\n\n"
                f"— Pratham\n"
            ),
            html=(
                f"<p>Thanks for reaching out, <strong>{body.company}</strong>.</p>"
                f"<p>A real human at AUREM will read your message and reply "
                f"within one business day. Usually faster — we're based in "
                f"Canada and this inbox pings me on my phone.</p>"
                f"<p>In the meantime, the docs are at "
                f"<a href='{site}/developers/docs'>{site}/developers/docs</a> "
                f"and the SLA page lives at "
                f"<a href='{site}/developers/status'>{site}/developers/status</a>.</p>"
                f"<p style='margin-top:18px'>— Pratham</p>"
            ),
        )
    except Exception as e:
        logger.debug(f"[enterprise/leads] auto-reply email skipped: {e}")

    return {"ok": True, "lead_id": lead_id, "status": "received"}
