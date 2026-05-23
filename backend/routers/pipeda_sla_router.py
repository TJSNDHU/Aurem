"""
routers/pipeda_sla_router.py — iter 328b + 328f

Founder-only endpoints:

  GET  /api/admin/sla/snapshot
      → 4-metric SLA snapshot (uptime, ORA p95, email%, campaign%).

  GET  /api/admin/pipeda/audit?limit=N
      → Last N rows from pipeda_audit_log.

  POST /api/admin/pipeda/sweep
      → Force the daily retention sweep right now (idempotent).

  POST /api/admin/pipeda/request-deletion
      → Mark a customer for deletion (30-day cool-off).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/admin", tags=["admin-compliance"])

_db = None


def set_db(database):
    global _db
    _db = database


def _admin_dep():
    from routers.ora_agent_router import get_admin_user
    return get_admin_user


# ── 328f SLA ───────────────────────────────────────────────────────


@router.get("/sla/snapshot")
async def sla_snapshot(user: dict = Depends(_admin_dep())):
    if _db is None:
        raise HTTPException(503, "db not ready")
    from services.sla_metrics import compute_sla_snapshot
    snap = await compute_sla_snapshot(_db)
    return snap


@router.get("/sla/history")
async def sla_history(limit: int = 14,
                          user: dict = Depends(_admin_dep())):
    if _db is None:
        raise HTTPException(503, "db not ready")
    limit = max(1, min(int(limit or 14), 90))
    cur = _db.sla_snapshots.find({}, {"_id": 0}).sort("ts", -1).limit(limit)
    rows = await cur.to_list(length=limit)
    return {"ok": True, "entries": rows, "count": len(rows)}


# ── 328b PIPEDA ────────────────────────────────────────────────────


@router.get("/pipeda/audit")
async def pipeda_audit(limit: int = 50,
                          user: dict = Depends(_admin_dep())):
    if _db is None:
        raise HTTPException(503, "db not ready")
    limit = max(1, min(int(limit or 50), 500))
    cur = _db.pipeda_audit_log.find({}, {"_id": 0}).sort("ts", -1).limit(limit)
    rows = await cur.to_list(length=limit)
    return {"ok": True, "entries": rows, "count": len(rows)}


@router.post("/pipeda/sweep")
async def pipeda_sweep(user: dict = Depends(_admin_dep())):
    if _db is None:
        raise HTTPException(503, "db not ready")
    from services.data_retention import run_retention_sweep
    out = await run_retention_sweep(_db)
    return out


class DeletionRequest(BaseModel):
    customer_id: str = Field(min_length=1, max_length=64)
    reason:      str = Field(default="", max_length=500)


@router.post("/pipeda/request-deletion")
async def pipeda_request_deletion(body: DeletionRequest,
                                       user: dict = Depends(_admin_dep())):
    if _db is None:
        raise HTTPException(503, "db not ready")
    from services.data_retention import request_customer_deletion
    out = await request_customer_deletion(_db, body.customer_id, body.reason)
    if not out.get("ok"):
        raise HTTPException(400, out.get("error") or "request failed")
    return out
