"""
Namecheap Domain Reseller — router (iter 311)
==============================================
POST /api/domain/check                   body: {domain_name}
POST /api/domain/register                body: {domain_name, lead_id, years?, registrant?}
GET  /api/domain/list/{lead_id}
POST /api/domain/renew                   body: {domain_name, years?}
GET  /api/domain/status/{domain}
POST /api/domain/dns/{domain}            body: {slug}
GET  /api/domain/health                  unauthenticated config check
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/domain", tags=["Domain Reseller"])

_db = None


def set_db(db):
    global _db
    _db = db


def _get_db():
    global _db
    if _db is None:
        try:
            import server
            _db = getattr(server, "db", None)
        except Exception:
            pass
    return _db


def _verify_admin(authorization: Optional[str]) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Admin authentication required")
    import jwt
    try:
        payload = jwt.decode(
            authorization.split(" ", 1)[1],
            os.environ.get("JWT_SECRET", ""),
            algorithms=["HS256"],
        )
        if payload.get("is_admin") or payload.get("role") == "admin" or payload.get("email"):
            return payload
        raise HTTPException(403, "Admin only")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(401, "Invalid token")


# ── Models ────────────────────────────────────────────────────────────────
class CheckBody(BaseModel):
    domain_name: str


class RegisterBody(BaseModel):
    domain_name: str
    lead_id: str
    years: Optional[int] = 1
    registrant: Optional[Dict[str, Any]] = None


class RenewBody(BaseModel):
    domain_name: str
    years: Optional[int] = 1


class DnsBody(BaseModel):
    slug: str


# ── Endpoints ─────────────────────────────────────────────────────────────
@router.get("/health")
async def health():
    from services.domain_reseller import _is_configured
    return {"ok": True, "configured": _is_configured()}


@router.post("/check")
async def check(body: CheckBody, authorization: Optional[str] = Header(None)):
    _verify_admin(authorization)
    from services.domain_reseller import check_availability
    return await check_availability(body.domain_name.strip().lower())


@router.post("/register")
async def register(body: RegisterBody,
                     authorization: Optional[str] = Header(None)):
    _verify_admin(authorization)
    db = _get_db()
    from services.domain_reseller import register_domain
    return await register_domain(db, body.domain_name.strip().lower(),
                                    body.lead_id, body.years or 1,
                                    body.registrant)


@router.get("/list/{lead_id}")
async def list_for_lead(lead_id: str,
                          authorization: Optional[str] = Header(None)):
    _verify_admin(authorization)
    db = _get_db()
    from services.domain_reseller import list_domains
    rows = await list_domains(db, lead_id)
    return {"ok": True, "domains": rows, "count": len(rows)}


@router.post("/renew")
async def renew(body: RenewBody, authorization: Optional[str] = Header(None)):
    _verify_admin(authorization)
    from services.domain_reseller import renew_domain
    return await renew_domain(body.domain_name.strip().lower(),
                                body.years or 1)


@router.get("/status/{domain}")
async def status(domain: str, authorization: Optional[str] = Header(None)):
    _verify_admin(authorization)
    from services.domain_reseller import get_status
    return await get_status(domain.strip().lower())


@router.post("/dns/{domain}")
async def configure_dns(domain: str, body: DnsBody,
                          authorization: Optional[str] = Header(None)):
    _verify_admin(authorization)
    from services.domain_reseller import configure_dns_to_aurem
    return await configure_dns_to_aurem(domain.strip().lower(),
                                          body.slug.strip())
