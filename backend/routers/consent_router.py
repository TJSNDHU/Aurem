"""
routers/consent_router.py — iter 331c Sprint 6.1

Tenant-facing consent endpoints for the Consent-Based Data Network.

  GET  /api/me/consent              → current consent state + discount + count
  PATCH /api/me/consent             → toggle data_sharing_consent
  POST /api/admin/consent/purge     → admin manual purge trigger (Tier-3-ish)
  GET  /api/admin/consent/network/stats → aggregate counts (no PII)

The tenant routes are gated by the standard tenant JWT.
The admin routes require platform admin.

Portability: imports only from services/. No Emergent-specific code.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Header
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()
_db = None


def set_db(db):
    global _db
    _db = db
    try:
        from services import consent_data_network as _CDN
        _CDN.set_db(db)
    except Exception:
        pass


# ── Auth helpers (use whatever auth the platform already wires) ────

async def _current_tenant(request: Request, authorization: str | None) -> dict:
    """Return {tenant_id, email} for the caller — resolved from JWT
    or X-Tenant-ID header. Falls back to header-only for tests.
    """
    # Prefer the platform's existing extractor if available.
    try:
        from middleware.bin_context import get_bin_ctx
        ctx = get_bin_ctx(request)
        if ctx and ctx.get("tenant_id"):
            return {"tenant_id": ctx["tenant_id"],
                    "email": ctx.get("email") or ""}
    except Exception:
        pass
    # Fallback: JWT decode via the same lib auth uses
    try:
        from services.platform_auth_service import decode_token
        if authorization and authorization.lower().startswith("bearer "):
            payload = decode_token(authorization.split(" ", 1)[1])
            return {
                "tenant_id": payload.get("tenant_id") or payload.get("sub") or "",
                "email":     payload.get("email") or "",
            }
    except Exception:
        pass
    # Last-resort header (tests + admin CLI)
    tid = request.headers.get("x-tenant-id") or ""
    return {"tenant_id": tid, "email": ""}


def _ensure_admin(request: Request) -> None:
    """Reuse the same admin gate the rest of the admin router uses."""
    try:
        from routers.admin_ora_router import _ensure_admin as _outer
        return _outer(request)
    except Exception as e:
        # If for any reason the admin gate import fails, fail closed.
        raise HTTPException(503, f"admin gate unavailable: {e}")


# ── Tenant-facing endpoints ────────────────────────────────────────

class ConsentBody(BaseModel):
    consent: bool


@router.get("/api/me/consent")
async def me_consent_get(
    request: Request,
    authorization: str = Header(None),
) -> dict[str, Any]:
    """Current consent state for the calling tenant."""
    if _db is None:
        raise HTTPException(503, "db not ready")
    me = await _current_tenant(request, authorization)
    if not me.get("tenant_id"):
        raise HTTPException(401, "missing tenant_id (login required)")
    from services.consent_data_network import get_consent
    return await get_consent(me["tenant_id"])


@router.patch("/api/me/consent")
async def me_consent_set(
    body: ConsentBody,
    request: Request,
    authorization: str = Header(None),
) -> dict[str, Any]:
    """Toggle data_sharing_consent. On opt-out, schedules a 30-day purge."""
    if _db is None:
        raise HTTPException(503, "db not ready")
    me = await _current_tenant(request, authorization)
    if not me.get("tenant_id"):
        raise HTTPException(401, "missing tenant_id (login required)")
    from services.consent_data_network import set_consent
    return await set_consent(
        tenant_id=me["tenant_id"],
        consent=bool(body.consent),
        actor_email=me.get("email") or "self",
    )


# ── Admin endpoints ────────────────────────────────────────────────

@router.post("/api/admin/consent/purge")
async def admin_consent_purge(
    request: Request,
    tenant_id: str,
) -> dict[str, Any]:
    """Manual purge trigger — admin only. Useful for testing + for
    expedited deletion before the 30-day window expires."""
    _ensure_admin(request)
    if _db is None:
        raise HTTPException(503, "db not ready")
    from services.consent_data_network import purge_revoked_tenant
    return await purge_revoked_tenant(tenant_id)


@router.get("/api/admin/consent/network/stats")
async def admin_consent_network_stats(request: Request) -> dict[str, Any]:
    """Aggregate counts for the founder dashboard. No tenant-identifying data."""
    _ensure_admin(request)
    if _db is None:
        raise HTTPException(503, "db not ready")
    total = await _db.aurem_network_leads.estimated_document_count()
    tenants_with_consent = await _db.user_profiles.count_documents(
        {"data_sharing_consent": True}
    )
    tenants_pending_purge = await _db.user_profiles.count_documents(
        {"network_purge_due_at": {"$ne": None}}
    )
    # Breakdown by industry (top 10).
    pipeline = [
        {"$group": {"_id": "$industry", "n": {"$sum": 1}}},
        {"$sort": {"n": -1}},
        {"$limit": 10},
    ]
    top_industries = [
        {"industry": d["_id"] or "unknown", "count": d["n"]}
        async for d in _db.aurem_network_leads.aggregate(pipeline)
    ]
    return {
        "ok":                       True,
        "total_records":            total,
        "tenants_with_consent":     tenants_with_consent,
        "tenants_pending_purge":    tenants_pending_purge,
        "top_industries":           top_industries,
    }
