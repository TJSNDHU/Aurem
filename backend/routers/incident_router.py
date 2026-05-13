"""
incident_router.py — REST surface for the AUREM incident pipeline (iter 322ff).

Endpoints:
  POST /api/incident/report           — public (rate-limited) ingest
  GET  /api/incident/list             — admin list (filter by status/severity/category)
  GET  /api/incident/status/{id}      — single row
  POST /api/incident/triage/{id}      — admin trigger triage (idempotent)
  POST /api/incident/resolve/{id}     — admin mark resolved + learn fingerprint
  GET  /api/incident/fingerprints     — admin: recurring patterns library
  GET  /api/incident/_/health         — public health probe

Auth model:
  - /report is OPEN (frontend window.onerror needs to call it). Rate-limited
    per-IP via simple in-memory bucket so a buggy page can't DoS Mongo.
  - All other endpoints require admin JWT.
"""
from __future__ import annotations

import logging
import os
import time
from collections import defaultdict, deque
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
import jwt

from services import incident_bus
from services.triage_brain import triage as run_triage, PLAYBOOKS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/incident", tags=["incident-pipeline"])
security = HTTPBearer(auto_error=False)

_db = None


def set_db(database):
    global _db
    _db = database
    incident_bus.set_db(database)


# ── In-memory per-IP rate limit for the open /report endpoint ────────
# Allow 30 reports / 60s / IP — enough for a burst, not enough for DoS.
_RL_WINDOW_S = 60
_RL_MAX      = 30
_rl_buckets: dict[str, deque[float]] = defaultdict(deque)


def _rate_limit(ip: str) -> bool:
    """Return True if the request is allowed, False if rate-limited."""
    now = time.time()
    q = _rl_buckets[ip]
    while q and (now - q[0]) > _RL_WINDOW_S:
        q.popleft()
    if len(q) >= _RL_MAX:
        return False
    q.append(now)
    return True


async def get_admin_user(creds: HTTPAuthorizationCredentials = Depends(security)):
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
    if not email:
        raise HTTPException(401, "Invalid token claims")
    if payload.get("is_admin") or payload.get("is_super_admin"):
        return {"email": email, "is_admin": True}
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


# ── Models ───────────────────────────────────────────────────────────
class ReportRequest(BaseModel):
    category:    str  = Field(default="unknown", max_length=64)
    signature:   str  = Field(default="",        max_length=240)
    severity:    Optional[str] = Field(default="P2")
    source:      str  = Field(default="unknown", max_length=80)
    title:       str  = Field(default="",        max_length=240)
    detail:      str  = Field(default="",        max_length=4000)
    metadata:    dict = Field(default_factory=dict)
    customer_id: Optional[str] = None


class TriageBody(BaseModel):
    auto_run_playbook: bool = False  # Phase 1: descriptive only


class ResolveBody(BaseModel):
    note:            str = Field(default="", max_length=400)
    learn:           bool = True
    learned_playbook: Optional[str] = None  # If omitted, uses category as default


# ── Endpoints ────────────────────────────────────────────────────────
@router.get("/_/health")
async def health():
    return {
        "ok":             True,
        "service":        "incident-pipeline",
        "iter":           "322ff",
        "categories":     sorted(incident_bus.CATEGORIES),
        "severities":     sorted(incident_bus.SEVERITIES),
        "playbooks":      sorted(PLAYBOOKS.keys()),
        "dedup_window_s": incident_bus.DEDUP_WINDOW_S,
    }


@router.post("/report")
async def report_incident(req: ReportRequest, request: Request):
    """Open ingest — frontend errors land here.

    Stripped-down auth: rate-limit by IP, never reflect server internals,
    return only the canonical incident_id.
    """
    ip = request.client.host if request.client else "0.0.0.0"
    if not _rate_limit(ip):
        raise HTTPException(429, "Too many reports — slow down.")

    res = await incident_bus.report(
        category=req.category,
        signature=req.signature,
        severity=req.severity,
        source=req.source,
        title=req.title,
        detail=req.detail,
        metadata=req.metadata or {},
        customer_id=req.customer_id,
        actor=f"ip:{ip}",
    )
    if not res.get("ok"):
        raise HTTPException(500, res.get("error", "ingest failed"))

    # Trim what the open endpoint returns (don't leak full row)
    return {
        "ok":          True,
        "incident_id": res["incident_id"],
        "deduped":     bool(res.get("deduped")),
        "occurrences": res.get("occurrences", 1),
        "status":      res.get("status", "open"),
    }


@router.get("/list")
async def list_incidents(
    limit: int = 50,
    status: Optional[str] = None,
    severity: Optional[str] = None,
    category: Optional[str] = None,
    since_hours: Optional[int] = None,
    _user: dict = Depends(get_admin_user),
):
    return await incident_bus.list_recent(
        limit=limit, status=status, severity=severity,
        category=category, since_hours=since_hours,
    )


@router.get("/status/{incident_id}")
async def get_incident(incident_id: str, _user: dict = Depends(get_admin_user)):
    res = await incident_bus.get(incident_id)
    if not res.get("ok"):
        raise HTTPException(404, res.get("error", "not found"))
    return res


@router.post("/triage/{incident_id}")
async def trigger_triage(
    incident_id: str,
    _body: TriageBody,
    _user: dict = Depends(get_admin_user),
):
    inc = await incident_bus.get(incident_id)
    if not inc.get("ok"):
        raise HTTPException(404, inc.get("error", "not found"))
    summary = await run_triage(_db, inc)
    await incident_bus.update_status(
        incident_id,
        status="triaged",
        playbook=summary.get("playbook"),
        auto_fixable=summary.get("auto_fixable"),
        triage_summary=summary,
    )
    return {"ok": True, "incident_id": incident_id, "summary": summary}


@router.post("/resolve/{incident_id}")
async def resolve_incident(
    incident_id: str,
    body: ResolveBody,
    user: dict = Depends(get_admin_user),
):
    inc = await incident_bus.get(incident_id)
    if not inc.get("ok"):
        raise HTTPException(404, "not found")

    updated = await incident_bus.update_status(
        incident_id, status="resolved",
        fix_step={"step": "manual_resolve", "actor": user["email"],
                  "note": body.note[:400], "ok": True},
    )

    # Learning loop — promote successful playbook into fingerprint library
    if body.learn and _db is not None:
        fp = inc.get("fingerprint")
        if fp:
            pb = body.learned_playbook or inc.get("playbook") or inc.get("category")
            if pb in PLAYBOOKS:
                await _db.incident_fingerprints.update_one(
                    {"_id": fp},
                    {"$set": {"known_playbook": pb, "last_resolved_at": incident_bus._now()}},
                )

    return updated


@router.get("/fingerprints")
async def fingerprint_library(_user: dict = Depends(get_admin_user)):
    return await incident_bus.fingerprint_stats()


@router.get("/playbooks")
async def list_playbooks(_user: dict = Depends(get_admin_user)):
    return {"ok": True, "playbooks": PLAYBOOKS}
