"""
Customer Site Audit Router — $49/mo upsell endpoints.

All endpoints require a customer JWT (Bearer token). Customer can:
  - POST /api/customer/audit/run    — fire a fresh audit for their site
  - GET  /api/customer/audit/latest — get the most-recent completed audit
  - GET  /api/customer/audit/history?limit=10
  - GET  /api/customer/audit/{audit_id}

Auto-trigger on signup is handled separately by `services.customer_audit_service`
via `asyncio.create_task(run_audit(...))` called from the signup flow.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field, HttpUrl

from services.customer_audit_service import (
    run_audit, get_latest_audit, list_audits, ensure_indexes,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/customer/audit", tags=["customer-audit"])

_db = None
_jwt_secret: str = ""
_jwt_algo: str = "HS256"


def set_db(database):
    global _db
    _db = database
    if database is not None:
        asyncio.create_task(ensure_indexes(database))


def set_jwt(secret: str, algo: str = "HS256"):
    global _jwt_secret, _jwt_algo
    _jwt_secret = secret
    _jwt_algo = algo


# ─── Auth ─────────────────────────────────────────────────────────────
async def _current_customer(authorization: Optional[str] = Header(None)) -> dict:
    if _db is None:
        raise HTTPException(503, "DB not initialised")
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = jwt.decode(token, _jwt_secret, algorithms=[_jwt_algo])
    except Exception as e:  # noqa: BLE001
        raise HTTPException(401, f"Invalid token: {str(e)[:120]}")
    cid = (
        payload.get("sub")
        or payload.get("email")
        or payload.get("customer_id")
        or payload.get("user_id")
    )
    if not cid:
        raise HTTPException(401, "Token has no subject")
    return {"customer_id": cid, "bin": payload.get("bin"), "claims": payload}


# ─── Models ───────────────────────────────────────────────────────────
class RunAuditRequest(BaseModel):
    url: HttpUrl
    strategy: str = Field("mobile", pattern="^(mobile|desktop)$")


# ─── Routes ───────────────────────────────────────────────────────────
@router.post("/run")
async def run(req: RunAuditRequest, user: dict = Depends(_current_customer)):
    """Trigger a fresh audit. Runs synchronously up to PageSpeed timeout (~60s)."""
    a = await run_audit(
        str(req.url), customer_id=user["customer_id"],
        bin=user.get("bin"), strategy=req.strategy, db=_db,
    )
    return a.model_dump()


@router.get("/latest")
async def latest(user: dict = Depends(_current_customer)):
    doc = await get_latest_audit(_db, user["customer_id"])
    return doc or {"audit": None, "message": "No audit yet — run /api/customer/audit/run"}


@router.get("/history")
async def history(limit: int = 20, user: dict = Depends(_current_customer)):
    if limit < 1 or limit > 100:
        limit = 20
    return {"items": await list_audits(_db, user["customer_id"], limit=limit)}


@router.get("/{audit_id}")
async def get_one(audit_id: str, user: dict = Depends(_current_customer)):
    doc = await _db.customer_audits.find_one(
        {"id": audit_id, "customer_id": user["customer_id"]}, {"_id": 0},
    )
    if not doc:
        raise HTTPException(404, "Audit not found")
    return doc


# ─── Public health (so Pillars Map can grid-check us) ────────────────
@router.get("/_/health", include_in_schema=False)
async def health():
    has_key = bool((
        os.environ.get("GOOGLE_PSI_API_KEY")
        or os.environ.get("GOOGLE_PAGESPEED_API_KEY")
        or os.environ.get("GOOGLE_API_KEY")
        or ""
    ).strip())
    return {
        "ok": True,
        "service": "customer-audit",
        "psi_key_configured": has_key,
    }
