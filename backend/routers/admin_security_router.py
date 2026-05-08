"""
Admin Security Panel API
────────────────────────
Endpoints for the guardrail blocks feed + ORA eval runs.

Routes:
  GET  /api/admin/guardrail/recent-blocks  — recent malicious_events + suspected_jailbreak
  GET  /api/admin/guardrail/stats          — aggregate counts
  POST /api/admin/ora-evals/run            — execute eval suite against live ORA
  GET  /api/admin/ora-evals/recent         — last N eval run summaries
  GET  /api/admin/ora-evals/{run_id}       — full detail for one run
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["Admin Security"])

_db = None


def set_db(database):
    global _db
    _db = database


def _require_admin(authorization: Optional[str]) -> str:
    """Reject non-admin callers. Returns admin identifier."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing token")
    try:
        import jwt
        payload = jwt.decode(
            authorization.replace("Bearer ", ""),
            os.getenv("JWT_SECRET"),
            algorithms=["HS256"],
        )
    except Exception:
        raise HTTPException(401, "Invalid token")
    role = (payload.get("role") or "").lower()
    is_admin = bool(payload.get("is_admin") or payload.get("is_super_admin"))
    if role not in ("admin", "super_admin") and not is_admin:
        raise HTTPException(403, "Admin role required")
    return payload.get("user_id") or payload.get("email") or "admin"


# ──────────────────────────────────────────────────────────────
# Guardrail
# ──────────────────────────────────────────────────────────────

@router.get("/guardrail/recent-blocks")
async def recent_blocks(authorization: str = Header(None), limit: int = 30):
    _require_admin(authorization)
    if _db is None:
        return {"malicious_events": [], "suspected_jailbreak": [], "total": 0}

    mal_cursor = _db.malicious_events.find({}, {"_id": 0}).sort("timestamp", -1).limit(limit)
    sus_cursor = _db.suspected_jailbreak.find({}, {"_id": 0}).sort("timestamp", -1).limit(limit)
    mal = await mal_cursor.to_list(limit)
    sus = await sus_cursor.to_list(limit)
    return {
        "malicious_events": mal,
        "suspected_jailbreak": sus,
        "total": len(mal) + len(sus),
    }


@router.get("/guardrail/stats")
async def guardrail_stats(authorization: str = Header(None)):
    _require_admin(authorization)
    if _db is None:
        return {"total_blocks_24h": 0, "kill_24h": 0, "warn_24h": 0}

    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    kill_24h = await _db.malicious_events.count_documents({"timestamp": {"$gte": cutoff}})
    warn_24h = await _db.suspected_jailbreak.count_documents({"timestamp": {"$gte": cutoff}})

    # All-time
    kill_total = await _db.malicious_events.count_documents({})
    warn_total = await _db.suspected_jailbreak.count_documents({})

    return {
        "last_24h": {"kill": kill_24h, "warn": warn_24h, "total": kill_24h + warn_24h},
        "all_time": {"kill": kill_total, "warn": warn_total, "total": kill_total + warn_total},
    }


# ──────────────────────────────────────────────────────────────
# ORA Evals
# ──────────────────────────────────────────────────────────────

class EvalRunRequest(BaseModel):
    category: Optional[str] = "all"  # all|safety|on_topic|factuality|tool_discipline|helpfulness


@router.post("/ora-evals/run")
async def run_ora_eval(body: EvalRunRequest, authorization: str = Header(None)):
    """Execute ORA eval suite against the LIVE /api/aurem/chat endpoint.

    The scenarios test prompt-injection defence, off-topic drift, hallucination
    resistance, and tool-use discipline. Grades each response against an
    expected behaviour and returns a pass-rate summary.
    """
    # We need the caller's admin JWT to authenticate the downstream chat calls.
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Admin JWT required")
    token = authorization.split(None, 1)[1].strip()
    _require_admin(authorization)

    from services.ora_evals import run_eval_suite

    # Resolve our OWN backend URL for internal call. Prefer explicit env var
    # so deployment can set it to the internal K8s service name; fall back to
    # localhost (works in single-container dev).
    base_url = os.environ.get("INTERNAL_API_URL") or "http://localhost:8001"

    summary = await run_eval_suite(
        db=_db,
        category=body.category,
        admin_token=token,
        base_url=base_url,
    )
    return summary


@router.get("/ora-evals/recent")
async def recent_eval_runs(authorization: str = Header(None), limit: int = 10):
    _require_admin(authorization)
    from services.ora_evals import get_recent_runs
    runs = await get_recent_runs(_db, limit=limit)
    return {"runs": runs, "count": len(runs)}


@router.get("/ora-evals/{run_id}")
async def eval_run_detail(run_id: str, authorization: str = Header(None)):
    _require_admin(authorization)
    if _db is None:
        raise HTTPException(503, "DB unavailable")
    doc = await _db.ora_eval_runs.find_one({"run_id": run_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Run not found")
    return doc
