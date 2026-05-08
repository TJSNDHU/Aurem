"""
Sovereign Memory Guard router (iter 322k).
Exposed under `/api/sovereign/memory/*` — admin-only.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

import jwt
from fastapi import APIRouter, HTTPException, Query, Request

import os

from services import sovereign_memory as smg


router = APIRouter(prefix="/api/sovereign/memory", tags=["sovereign-memory"])

_db = None


def set_db(database) -> None:
    global _db
    _db = database


def _require_admin(request: Request) -> Dict[str, Any]:
    """Mirror the qa_bot_router admin-check so we don't import private state."""
    auth = request.headers.get("Authorization", "")
    token = auth[7:] if auth.startswith("Bearer ") else ""
    if not token:
        raise HTTPException(401, "Auth required")
    try:
        payload = jwt.decode(
            token,
            os.environ.get("JWT_SECRET", "aurem_default_secret"),
            algorithms=["HS256"],
        )
    except Exception:
        raise HTTPException(401, "Invalid token")
    if not (payload.get("is_admin") or payload.get("is_super_admin") or
            payload.get("role") in ("admin", "super_admin", "founder")):
        raise HTTPException(403, "Admin required")
    return payload


# ─── Submission ─────────────────────────────────────────────────────────
@router.post("/submit")
async def submit(request: Request):
    _require_admin(request)
    body = await request.json()
    try:
        learning_id = await smg.submit_learning(
            _db,
            agent_role=body.get("agent_role", ""),
            kind=body.get("kind", ""),
            payload=body.get("payload") or {},
            evidence=body.get("evidence") or {},
            confidence=float(body.get("confidence", 0.5)),
        )
        return {"ok": True, "id": learning_id}
    except (ValueError, RuntimeError) as e:
        raise HTTPException(400, str(e))


# ─── Review ─────────────────────────────────────────────────────────────
@router.post("/review")
async def review(request: Request):
    _require_admin(request)
    body = await request.json()
    learning_id = body.get("id") or body.get("learning_id")
    if not learning_id:
        raise HTTPException(400, "id required")
    try:
        result = await smg.review_learning(
            _db,
            learning_id=learning_id,
            reviewer_role=body.get("reviewer_role", ""),
            vote=body.get("vote", ""),
            notes=body.get("notes", ""),
        )
        return result
    except (ValueError, RuntimeError) as e:
        raise HTTPException(400, str(e))


# ─── Reads ──────────────────────────────────────────────────────────────
@router.get("/pending")
async def pending(request: Request, limit: int = Query(50, ge=1, le=200)):
    _require_admin(request)
    return {"ok": True, "items": await smg.get_pending_learnings(_db, limit=limit)}


@router.get("/promoted")
async def promoted(
    request: Request,
    kind: Optional[str] = None,
    limit: int = Query(20, ge=1, le=200),
):
    _require_admin(request)
    return {
        "ok": True,
        "items": await smg.get_promoted_learnings(_db, kind=kind, limit=limit),
    }


@router.get("/stats")
async def stats(request: Request):
    _require_admin(request)
    return await smg.get_memory_guard_stats(_db)


@router.get("/next-for-review/{role}")
async def next_for_review(role: str, request: Request, kind: Optional[str] = None):
    """Return the oldest pending learning that the given role hasn't already
    stamped (and didn't submit). Used by Council rotation jobs."""
    _require_admin(request)
    item = await smg.next_pending_for_review(_db, exclude_role=role, kind=kind)
    return {"ok": True, "item": item}
