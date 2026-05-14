"""
ora_agent_router.py — REST surface for autonomous CTO mode (iter 322fi).

Endpoints (all admin JWT):
    POST /api/ora/agent/run          — send user message, get reply or pending action
    POST /api/ora/agent/approve      — approve a pending action, get next turn
    POST /api/ora/agent/reject       — reject a pending action, get next turn
    GET  /api/ora/agent/pending      — list pending actions (founder cockpit)
    GET  /api/ora/agent/history/{sid}— last 40 messages
    POST /api/ora/agent/clear/{sid}  — wipe a thread (server-side memory)
    GET  /api/ora/agent/_/health     — pipeline health
"""
from __future__ import annotations

import logging
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
import jwt

from services import ora_agent

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ora/agent", tags=["ora-agent"])
security = HTTPBearer(auto_error=False)

_db = None


def set_db(database):
    global _db
    _db = database
    ora_agent.set_db(database)
    # Wire the async-job queue (CF 524 fix) to the same DB. Worker is
    # started by server.py once the asyncio loop is alive.
    try:
        from services import ora_agent_jobs
        ora_agent_jobs.set_db(database)
    except Exception as e:
        logger.warning("[ora-agent-router] could not wire ora_agent_jobs: %s", e)


async def get_admin_user(creds: HTTPAuthorizationCredentials = Depends(security)):
    """Resolve admin from JWT.

    Production token shapes vary across login endpoints:
      • /api/auth/admin/login  → {user_id, is_admin, is_super_admin, role, exp}  (NO email)
      • /api/auth/login        → {user_id, is_admin, email, exp}
      • /api/platform/auth/login → {email, role, jti, user_id, is_admin, ...}

    We accept ANY of: email / sub / user_id. If only user_id is present,
    we hydrate the email from the users collection.
    """
    if not creds:
        raise HTTPException(401, "Missing bearer token")
    secret = os.environ.get("JWT_SECRET") or os.environ.get("JWT_SECRET_KEY") or ""
    if not secret:
        raise HTTPException(500, "Server config error")
    try:
        payload = jwt.decode(creds.credentials, secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")

    email = (payload.get("email") or payload.get("sub") or "").lower()
    user_id = payload.get("user_id") or payload.get("uid") or ""
    is_admin_claim = bool(
        payload.get("is_admin")
        or payload.get("is_super_admin")
        or payload.get("role") in ("admin", "super_admin")
    )

    # Hydrate email from DB if missing but user_id is present (admin/login tokens).
    if not email and user_id:
        if _db is None:
            raise HTTPException(500, "DB not wired")
        row = await _db.users.find_one(
            {"id": user_id},
            {"_id": 0, "email": 1, "is_admin": 1, "is_super_admin": 1, "role": 1},
        )
        if row:
            email = (row.get("email") or "").lower()
            is_admin_claim = is_admin_claim or bool(
                row.get("is_admin")
                or row.get("is_super_admin")
                or row.get("role") in ("admin", "super_admin")
            )

    if not email:
        raise HTTPException(401, "Invalid token claims")

    if is_admin_claim:
        return {"email": email, "is_admin": True}

    # No admin flag in token — last-chance DB check by email.
    if _db is None:
        raise HTTPException(500, "DB not wired")
    user = await _db.users.find_one(
        {"email": email},
        {"_id": 0, "is_admin": 1, "is_super_admin": 1, "role": 1},
    )
    if not user or not (
        user.get("is_admin")
        or user.get("is_super_admin")
        or user.get("role") in ("admin", "super_admin")
    ):
        raise HTTPException(403, "Admin access required")
    return {"email": email, "is_admin": True}


class RunBody(BaseModel):
    session_id: str = Field(min_length=3, max_length=120)
    text:       str = Field(min_length=1, max_length=4000)


class DecideBody(BaseModel):
    session_id: str
    action_id:  str
    note:       Optional[str] = Field(default="", max_length=400)


@router.get("/_/health")
async def health():
    return {
        "ok":              True,
        "service":         "ora-agent",
        "iter":            "322fi",
        "tier1_auto":      sorted(ora_agent.TIER_1_AUTO),
        "tier2_approve":   sorted(ora_agent.TIER_2_APPROVE),
        "tier3_high_risk": sorted(ora_agent.TIER_3_HIGH_RISK),
        "expiry_minutes":  ora_agent.EXPIRY_MINUTES,
    }


@router.post("/run")
async def agent_run(body: RunBody, user: dict = Depends(get_admin_user)):
    return await ora_agent.run_turn(
        body.session_id, body.text, founder_email=user["email"]
    )


# ─── Async job pattern (CF 524 fix, sovereign + free) ─────────────────
# Cloudflare Free plan kills any HTTP request lingering >100 s. Tool-call
# loops against the user's local Ollama daemon routinely exceed that on
# multi-step queries ("System Overview", "diagnose backend"). Instead of
# paying for a CF plan upgrade we split the slow path into two short
# requests:
#
#   POST /run-async      → returns job_id in <100 ms (never times out)
#   GET  /status/<jobid> → returns {status, result?} in <50 ms; client
#                          polls every 2-3 s
#
# The actual ora_agent.run_turn() executes inside a background worker
# spawned by server.py. Jobs persist in Mongo so an unfortunate pod
# restart never loses an in-flight conversation (the "never offline"
# mandate). See services/ora_agent_jobs.py for details.

@router.post("/run-async")
async def agent_run_async(body: RunBody, user: dict = Depends(get_admin_user)):
    from services import ora_agent_jobs
    return await ora_agent_jobs.enqueue(
        session_id=body.session_id,
        text=body.text,
        founder_email=user["email"],
    )


@router.get("/status/{job_id}")
async def agent_status(job_id: str, user: dict = Depends(get_admin_user)):
    from services import ora_agent_jobs
    return await ora_agent_jobs.get_status(job_id, founder_email=user["email"])


@router.post("/approve")
async def agent_approve(body: DecideBody, user: dict = Depends(get_admin_user)):
    return await ora_agent.resume_after_decision(
        body.session_id,
        action_id=body.action_id,
        approved=True,
        note=body.note or "",
        founder_email=user["email"],
    )


@router.post("/reject")
async def agent_reject(body: DecideBody, user: dict = Depends(get_admin_user)):
    return await ora_agent.resume_after_decision(
        body.session_id,
        action_id=body.action_id,
        approved=False,
        note=body.note or "",
        founder_email=user["email"],
    )


@router.get("/pending")
async def agent_pending(session_id: Optional[str] = None,
                         _user: dict = Depends(get_admin_user)):
    rows = await ora_agent.list_pending(session_id)
    return {"ok": True, "rows": rows, "count": len(rows)}


@router.get("/history/{session_id}")
async def agent_history(session_id: str, _user: dict = Depends(get_admin_user)):
    msgs = await ora_agent._load_history(session_id)
    # Strip system prompt before sending to UI
    visible = [m for m in msgs if m.get("role") != "system"]
    return {"ok": True, "messages": visible, "count": len(visible)}


@router.post("/clear/{session_id}")
async def agent_clear(session_id: str, _user: dict = Depends(get_admin_user)):
    if _db is None:
        raise HTTPException(500, "DB not wired")
    await _db[ora_agent.HISTORY_COLLECTION].delete_one({"_id": session_id})
    await _db[ora_agent.PENDING_COLLECTION].update_many(
        {"session_id": session_id, "status": "pending"},
        {"$set": {"status": "cancelled", "decided_at": ora_agent._now(),
                  "decided_by": "founder_clear"}},
    )
    return {"ok": True, "cleared": session_id}
