"""
ORA Knowledge Router — Phase 3
================================
Read-only query endpoints for the Tier-3 permanent knowledge store.

  GET  /api/admin/ora/knowledge?kind=&pattern=&limit=
  GET  /api/admin/ora/knowledge/top?kind=&limit=
  GET  /api/admin/ora/knowledge/summary?hours=24
  GET  /api/admin/ora/knowledge/digest/latest
  GET  /api/admin/ora/knowledge/assessment/latest
  POST /api/admin/ora/knowledge/digest/run-now
  POST /api/admin/ora/knowledge/assessment/run-now
"""
from __future__ import annotations

import os
import logging
from typing import Any, Dict, Optional

import jwt
from fastapi import APIRouter, HTTPException, Query, Request

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/ora/knowledge", tags=["admin-ora-knowledge"])

_db = None


def set_db(database) -> None:
    global _db
    _db = database


def _require_admin(request: Request) -> None:
    auth = request.headers.get("Authorization", "")
    token = auth[7:] if auth.startswith("Bearer ") else ""
    if not token:
        raise HTTPException(401, "Auth required")
    try:
        payload = jwt.decode(
            token,
            (os.environ.get("JWT_SECRET") or (_ for _ in ()).throw(__import__("fastapi").HTTPException(status_code=500, detail="JWT not configured"))),
            algorithms=["HS256"],
        )
    except Exception:
        raise HTTPException(401, "Invalid token")
    if not (payload.get("is_admin") or payload.get("is_super_admin")
            or payload.get("role") in ("admin", "super_admin", "founder")):
        raise HTTPException(403, "Admin required")


@router.get("")
async def query(
    request: Request,
    kind: Optional[str] = Query(None),
    pattern: Optional[str] = Query(None),
    min_confidence: float = Query(0.5, ge=0.0, le=1.0),
    limit: int = Query(20, ge=1, le=200),
) -> Dict[str, Any]:
    _require_admin(request)
    if _db is None:
        raise HTTPException(503, "database unavailable")
    from services.ora_knowledge_base import query_knowledge
    items = await query_knowledge(
        _db, kind=kind, pattern=pattern,
        min_confidence=min_confidence, limit=limit,
    )
    return {"ok": True, "count": len(items), "items": items}


@router.get("/top")
async def top(
    request: Request,
    kind: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=100),
) -> Dict[str, Any]:
    _require_admin(request)
    if _db is None:
        raise HTTPException(503, "database unavailable")
    from services.ora_knowledge_base import top_patterns
    items = await top_patterns(_db, kind=kind, limit=limit)
    return {"ok": True, "count": len(items), "items": items}


@router.get("/summary")
async def summary(
    request: Request, hours: int = Query(24, ge=1, le=720),
) -> Dict[str, Any]:
    _require_admin(request)
    if _db is None:
        raise HTTPException(503, "database unavailable")
    from services.ora_knowledge_base import summarize_period
    return await summarize_period(_db, hours=hours)


@router.get("/digest/latest")
async def latest_digest(request: Request) -> Dict[str, Any]:
    _require_admin(request)
    if _db is None:
        raise HTTPException(503, "database unavailable")
    doc = await _db.ora_learning_digests.find_one({}, {"_id": 0}, sort=[("ts", -1)])
    return {"ok": True, "digest": doc or None}


@router.get("/assessment/latest")
async def latest_assessment(request: Request) -> Dict[str, Any]:
    _require_admin(request)
    if _db is None:
        raise HTTPException(503, "database unavailable")
    doc = await _db.ora_self_assessments.find_one({}, {"_id": 0}, sort=[("ts", -1)])
    return {"ok": True, "assessment": doc or None}


@router.post("/digest/run-now")
async def run_digest(request: Request) -> Dict[str, Any]:
    _require_admin(request)
    from services.ora_knowledge_base import write_nightly_digest
    res = await write_nightly_digest()
    return {"ok": True, "digest": res}


@router.post("/assessment/run-now")
async def run_assessment(request: Request) -> Dict[str, Any]:
    _require_admin(request)
    from services.ora_knowledge_base import write_self_assessment
    res = await write_self_assessment()
    return {"ok": True, "assessment": res}
