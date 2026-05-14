"""
Truth Ledger Router — iter 283
═══════════════════════════════════════════════════════════════════════

Admin-only visibility + induction endpoint for new agents.

Endpoints:
  GET  /api/admin/truth-ledger/recent              — list recent entries
  GET  /api/admin/truth-ledger/stats               — 30-day rollup
  GET  /api/admin/truth-ledger/induction           — new-agent briefing
  POST /api/admin/truth-ledger/record              — manual record (admin)
  GET  /api/admin/truth-ledger/current-health      — ORA Truth-Sync hook
  GET  /api/admin/truth-ledger/health              — public probe
"""
from __future__ import annotations

import os
from typing import Optional

import jwt
from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/admin/truth-ledger", tags=["Truth Ledger"])

_db = None
_jwt_secret: Optional[str] = None
_jwt_alg: str = "HS256"


def set_db(db) -> None:
    global _db
    _db = db
    try:
        from services.truth_ledger import set_db as _svc_set_db
        _svc_set_db(db)
    except Exception:
        pass


def set_jwt(secret: str, algorithm: str = "HS256") -> None:
    global _jwt_secret, _jwt_alg
    _jwt_secret = secret
    _jwt_alg = algorithm


def _verify_admin(authorization: Optional[str]) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    try:
        payload = jwt.decode(
            authorization.split(" ", 1)[1],
            _jwt_secret or (os.environ.get("JWT_SECRET") or (_ for _ in ()).throw(__import__("fastapi").HTTPException(status_code=500, detail="JWT not configured"))),
            algorithms=[_jwt_alg],
        )
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")
    if not (payload.get("is_admin") or payload.get("is_super_admin")):
        raise HTTPException(status_code=403, detail="Admin access required")
    return payload


class ManualRecord(BaseModel):
    actor: str = Field(..., min_length=1, max_length=120)
    event_type: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1, max_length=1000)
    severity: str = Field(default="info")
    evidence: Optional[dict] = None
    outcome: Optional[str] = None


@router.get("/recent")
async def recent(
    limit: int = Query(50, ge=1, le=500),
    severity: Optional[str] = Query(None),
    actor: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
):
    _verify_admin(authorization)
    from services.truth_ledger import get_recent
    entries = await get_recent(
        limit=limit, severity=severity, actor=actor, event_type=event_type
    )
    return {"count": len(entries), "entries": entries}


@router.get("/stats")
async def stats(authorization: Optional[str] = Header(None)):
    _verify_admin(authorization)
    from services.truth_ledger import get_stats
    return await get_stats()


@router.get("/induction")
async def induction(authorization: Optional[str] = Header(None)):
    _verify_admin(authorization)
    from services.truth_ledger import get_induction_briefing
    return await get_induction_briefing()


@router.post("/record")
async def record_manual(
    body: ManualRecord, authorization: Optional[str] = Header(None)
):
    admin = _verify_admin(authorization)
    from services.truth_ledger import record
    ev = body.evidence or {}
    ev.setdefault("manual_recorded_by", admin.get("email") or admin.get("sub"))
    doc = await record(
        actor=body.actor,
        event_type=body.event_type,
        description=body.description,
        severity=body.severity,
        evidence=ev,
        outcome=body.outcome,
    )
    return {"ok": True, "log_id": doc["log_id"]}


@router.get("/current-health")
async def current_health(authorization: Optional[str] = Header(None)):
    """Truthful health snapshot. Used by ORA Truth-Sync to answer questions
    about system state honestly."""
    _verify_admin(authorization)
    from services.truth_ledger import current_truthful_health
    return await current_truthful_health()


@router.get("/health")
async def router_health():
    return {"status": "ok", "component": "truth_ledger", "db_ready": _db is not None}
