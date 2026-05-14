"""
ghost_scout_router.py — admin trigger + status for IPRoyal-powered scout.
══════════════════════════════════════════════════════════════════════
Endpoints (all require admin JWT):

  POST /api/admin/ghost-scout/run
    body: {"query":"roofing contractor","location":"Toronto","country":"ca","limit":15}
    → triggers harvest_leads() immediately, returns inserted count

  GET /api/admin/ghost-scout/status
    → returns last 10 batches from ghost_scout_log + proxy reachability
"""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

logger = logging.getLogger("ghost_scout_router")
router = APIRouter(prefix="/api/admin/ghost-scout", tags=["admin", "ghost-scout"])

_db: AsyncIOMotorDatabase | None = None


def set_db(database: AsyncIOMotorDatabase) -> None:
    global _db
    _db = database


async def _require_admin(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "missing bearer token")
    token = auth[7:]
    try:
        import jwt as _jwt
        secret = (os.environ.get("JWT_SECRET") or (_ for _ in ()).throw(__import__("fastapi").HTTPException(status_code=500, detail="JWT not configured")))
        if not secret:
            raise HTTPException(500, "JWT_SECRET unset")
        claims = _jwt.decode(token, secret, algorithms=["HS256"])
        email = claims.get("email") or claims.get("sub") or ""
        if not email:
            raise HTTPException(401, "no email in token")
        return email
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(401, f"jwt invalid: {e}")


class RunRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=80)
    location: str = Field(..., min_length=2, max_length=80)
    country: str = Field("us", pattern="^(us|ca)$")
    limit: int = Field(15, ge=1, le=50)
    include_website_scrape: bool = True


@router.post("/run")
async def trigger_run(
    body: RunRequest,
    _email: str = Depends(_require_admin),
) -> dict[str, Any]:
    """Trigger a single Ghost Scout harvest cycle synchronously."""
    from services.ghost_scout_iproyal import harvest_leads
    res = await harvest_leads(
        body.query, body.location,
        country=body.country, limit=body.limit,
        include_website_scrape=body.include_website_scrape,
    )
    res["triggered_by"] = _email
    return res


@router.get("/status")
async def get_status(_email: str = Depends(_require_admin)) -> dict[str, Any]:
    if _db is None:
        raise HTTPException(503, "db not ready")
    # Proxy reachability
    proxy_url = os.environ.get("IPROYAL_PROXY_URL", "")
    proxy_ok = False
    proxy_ip = None
    if proxy_url:
        try:
            async with httpx.AsyncClient(proxy=proxy_url, timeout=10.0) as c:
                r = await c.get("https://ipv4.icanhazip.com")
                if r.status_code == 200:
                    proxy_ok = True
                    proxy_ip = r.text.strip()
        except Exception as e:
            logger.warning(f"[ghost-scout] proxy probe fail: {e}")

    # Last 10 batches
    history: list[dict] = []
    async for d in _db.ghost_scout_log.find({}, {"_id": 0}).sort("ts", -1).limit(10):
        history.append(d)

    # Total leads from this source
    total_from_scout = await _db.campaign_leads.count_documents(
        {"source": "ghost_scout_iproyal"}
    )

    return {
        "proxy": {
            "configured": bool(proxy_url),
            "reachable": proxy_ok,
            "current_ip": proxy_ip,
        },
        "capsolver": {
            "configured": bool(os.environ.get("CAPSOLVER_API_KEY")),
        },
        "totals": {
            "leads_from_ghost_scout": total_from_scout,
        },
        "recent_batches": history,
    }
