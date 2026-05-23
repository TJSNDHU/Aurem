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


@router.post("/leads/track")
async def track_enterprise_interest(
    request: Request,
) -> dict[str, Any]:
    """Public — tracks anonymous interest signals on /enterprise
    (scroll depth, tier-card hovers, time on page) BEFORE the form
    is submitted. Lightweight ping; failures never surface."""
    if _db is None:
        return {"ok": False, "error": "db not ready"}
    try:
        body = await request.json()
    except Exception:
        return {"ok": False, "error": "invalid_json"}
    row = {
        "ts":          datetime.now(timezone.utc).isoformat(),
        "ip_address":  request.client.host if request.client else None,
        "user_agent":  request.headers.get("user-agent", "")[:200],
        "session_id":  (body.get("session_id") or "")[:40],
        "event":       (body.get("event") or "unknown")[:40],
        "tier":        (body.get("tier") or "")[:40],
        "depth_pct":   int(body.get("depth_pct") or 0),
        "ms_on_page":  int(body.get("ms_on_page") or 0),
    }
    try:
        await _db.enterprise_interest_signals.insert_one(row)
    except Exception as e:
        logger.debug(f"[enterprise/track] insert failed: {e}")
        return {"ok": False, "error": "insert_failed"}
    return {"ok": True}


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


# ── iter 332b A-2b — API Key CRUD (admin) ────────────────────────────

class ApiKeyCreateBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    scope: str = Field("read", max_length=40)


def _generate_api_key() -> str:
    return "aurem_" + uuid.uuid4().hex + uuid.uuid4().hex[:8]


@router.get("/keys")
async def list_api_keys(request: Request) -> dict[str, Any]:
    _ensure_admin(request)
    if _db is None:
        return {"ok": False, "rows": []}
    cursor = _db.enterprise_api_keys.find(
        {}, {"_id": 0, "key": 0},   # never return the full key after creation
    ).sort("created_at", -1).limit(100)
    rows = await cursor.to_list(length=100)
    return {"ok": True, "rows": rows}


@router.post("/keys")
async def create_api_key(
    body: ApiKeyCreateBody, request: Request,
) -> dict[str, Any]:
    _ensure_admin(request)
    if _db is None:
        raise HTTPException(503, "db not ready")
    key = _generate_api_key()
    key_id = uuid.uuid4().hex
    doc = {
        "key_id":      key_id,
        "key":         key,
        "key_preview": key[:14] + "…",
        "name":        body.name.strip(),
        "scope":       body.scope.strip(),
        "active":      True,
        "created_at":  datetime.now(timezone.utc).isoformat(),
        "last_used_at": None,
        "use_count":   0,
    }
    await _db.enterprise_api_keys.insert_one(doc)
    try:
        from services.unified_audit import write_event
        await write_event(
            action="api_key_created", resource=f"key:{body.name}",
            result="ok", source_collection="enterprise_api_keys",
            extra={"key_id": key_id, "scope": body.scope},
        )
    except Exception:
        pass
    return {"ok": True, "key_id": key_id,
             "key": key, "key_preview": doc["key_preview"],
             "warning": "This is the only time the full key is shown — save it now."}


@router.post("/keys/{key_id}/rotate")
async def rotate_api_key(key_id: str, request: Request) -> dict[str, Any]:
    _ensure_admin(request)
    if _db is None:
        raise HTTPException(503, "db not ready")
    new_key = _generate_api_key()
    r = await _db.enterprise_api_keys.find_one_and_update(
        {"key_id": key_id, "active": True},
        {"$set": {"key": new_key,
                   "key_preview": new_key[:14] + "…",
                   "rotated_at": datetime.now(timezone.utc).isoformat()}},
        projection={"_id": 0, "key": 0},
        return_document=True,
    )
    if not r:
        raise HTTPException(404, "key_not_found_or_inactive")
    try:
        from services.unified_audit import write_event
        await write_event(
            action="api_key_rotated", resource=f"key:{r.get('name')}",
            result="ok", source_collection="enterprise_api_keys",
            extra={"key_id": key_id},
        )
    except Exception:
        pass
    return {"ok": True, "key_id": key_id, "key": new_key,
             "key_preview": new_key[:14] + "…",
             "warning": "This is the only time the new key is shown — save it now."}


@router.delete("/keys/{key_id}")
async def revoke_api_key(key_id: str, request: Request) -> dict[str, Any]:
    _ensure_admin(request)
    if _db is None:
        raise HTTPException(503, "db not ready")
    r = await _db.enterprise_api_keys.update_one(
        {"key_id": key_id, "active": True},
        {"$set": {"active": False,
                   "revoked_at": datetime.now(timezone.utc).isoformat()}},
    )
    if r.matched_count == 0:
        raise HTTPException(404, "key_not_found_or_already_revoked")
    try:
        from services.unified_audit import write_event
        await write_event(
            action="api_key_revoked", resource=f"key:{key_id}",
            result="ok", source_collection="enterprise_api_keys",
            extra={"key_id": key_id},
        )
    except Exception:
        pass
    return {"ok": True, "key_id": key_id, "revoked": True}


# ── White-label config (admin) — thin wrapper around services/white_label.py

class BrandingBody(BaseModel):
    tenant_id:     str = Field("default", max_length=80)
    logo_url:      str = Field("", max_length=400)
    primary_color: str = Field("", max_length=20)
    company_name:  str = Field("", max_length=120)


@router.get("/branding")
async def get_branding(request: Request,
                        tenant_id: str = "default") -> dict[str, Any]:
    _ensure_admin(request)
    if _db is None:
        return {"ok": True, "branding": None}
    row = await _db.enterprise_branding.find_one(
        {"tenant_id": tenant_id}, {"_id": 0},
    )
    return {"ok": True, "branding": row}


@router.put("/branding")
async def set_branding(body: BrandingBody,
                        request: Request) -> dict[str, Any]:
    _ensure_admin(request)
    if _db is None:
        raise HTTPException(503, "db not ready")
    doc = {
        "tenant_id":     body.tenant_id,
        "logo_url":      body.logo_url.strip(),
        "primary_color": body.primary_color.strip(),
        "company_name":  body.company_name.strip(),
        "updated_at":    datetime.now(timezone.utc).isoformat(),
    }
    await _db.enterprise_branding.update_one(
        {"tenant_id": body.tenant_id},
        {"$set": doc},
        upsert=True,
    )
    try:
        from services.unified_audit import write_event
        await write_event(
            action="branding_updated", resource=f"tenant:{body.tenant_id}",
            result="ok", source_collection="enterprise_branding",
            extra={"company_name": body.company_name},
        )
    except Exception:
        pass
    return {"ok": True, "branding": doc}


@router.get("/branding/public/{tenant_id}")
async def get_branding_public(tenant_id: str) -> dict[str, Any]:
    """PUBLIC — used by the React shell to swap branding at runtime."""
    if _db is None:
        return {"ok": False, "branding": None}
    row = await _db.enterprise_branding.find_one(
        {"tenant_id": tenant_id}, {"_id": 0},
    )
    return {"ok": True, "branding": row}


# ── Custom domain wizard (admin) ─────────────────────────────────────

class DomainBody(BaseModel):
    tenant_id: str = Field("default", max_length=80)
    domain:    str = Field(..., min_length=4, max_length=120)


@router.post("/domain")
async def register_custom_domain(body: DomainBody,
                                   request: Request) -> dict[str, Any]:
    _ensure_admin(request)
    if _db is None:
        raise HTTPException(503, "db not ready")
    domain = body.domain.lower().strip()
    if not all(c.isalnum() or c in ".-" for c in domain):
        raise HTTPException(400, "invalid_domain")
    doc = {
        "tenant_id":   body.tenant_id,
        "domain":      domain,
        "status":      "pending_verification",
        "cname_target": "aurem.live",
        "created_at":  datetime.now(timezone.utc).isoformat(),
    }
    await _db.enterprise_domains.update_one(
        {"tenant_id": body.tenant_id, "domain": domain},
        {"$setOnInsert": doc},
        upsert=True,
    )
    return {
        "ok":           True,
        "domain":       domain,
        "cname_target": "aurem.live",
        "instructions": (
            f"Add a CNAME record on {domain} pointing to aurem.live, "
            f"then hit Verify."
        ),
    }


@router.post("/domain/verify")
async def verify_custom_domain(body: DomainBody,
                                 request: Request) -> dict[str, Any]:
    """Verify the CNAME is in place. Uses socket DNS resolution —
    no external DNS provider dependency."""
    _ensure_admin(request)
    if _db is None:
        raise HTTPException(503, "db not ready")
    domain = body.domain.lower().strip()
    verified = False
    detail = ""
    try:
        import socket
        # CNAME → an A record on aurem.live, both should resolve to
        # the same set of IPs. We accept that as "verified".
        their_ips = sorted({ai[4][0] for ai in socket.getaddrinfo(domain, None)})
        ours_ips  = sorted({ai[4][0] for ai in socket.getaddrinfo("aurem.live", None)})
        verified = bool(set(their_ips) & set(ours_ips))
        detail = f"resolved={their_ips} expected={ours_ips}"
    except Exception as e:
        detail = f"dns_error: {str(e)[:120]}"

    new_status = "active" if verified else "pending_verification"
    await _db.enterprise_domains.update_one(
        {"tenant_id": body.tenant_id, "domain": domain},
        {"$set": {"status": new_status,
                   "last_check_at": datetime.now(timezone.utc).isoformat(),
                   "last_check_detail": detail}},
    )
    return {"ok": True, "verified": verified,
             "status": new_status, "detail": detail}
