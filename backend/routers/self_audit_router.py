"""Self-Audit chip + manual trigger — iter 282al-10."""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Header, HTTPException

from services.self_audit import (
    DEFAULT_TARGET, DEFAULT_THRESHOLD,
    get_latest_self_audit, run_self_audit,
)

logger = logging.getLogger(__name__)
router = APIRouter()

_db = None


def set_db(database):
    global _db
    _db = database


def _get_db():
    global _db
    if _db is not None:
        return _db
    try:
        import server  # noqa: WPS433
        if hasattr(server, "db") and server.db is not None:
            _db = server.db
    except Exception:
        pass
    return _db


def _verify_admin(authorization: Optional[str]) -> None:
    if not authorization:
        raise HTTPException(status_code=401, detail="missing token")
    try:
        import jwt
        token = authorization.replace("Bearer ", "").strip()
        secret = (os.environ.get("JWT_SECRET") or (_ for _ in ()).throw(__import__("fastapi").HTTPException(status_code=500, detail="JWT not configured")))
        if not secret:
            raise HTTPException(status_code=500, detail="JWT_SECRET unset")
        decoded = jwt.decode(token, secret, algorithms=["HS256"])
        if not decoded.get("is_admin"):
            raise HTTPException(status_code=403, detail="admin only")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="invalid token")


# ─────────────────────────────────────────────────────────────────────
@router.get("/api/self-audit/health")
async def self_audit_health() -> dict:
    """Pillars Map chip — last-run snapshot. PUBLIC (no auth) so the chip
    works on the homepage too. Returns the most recent self-audit row."""
    db = _get_db()
    latest = await get_latest_self_audit(db) if db is not None else None
    target = (os.environ.get("SELF_AUDIT_TARGET_URL") or DEFAULT_TARGET)
    threshold = int(os.environ.get("SELF_AUDIT_ALERT_THRESHOLD")
                     or DEFAULT_THRESHOLD)
    healthy = bool(latest and (latest.get("overall_score") or 0) >= threshold)
    return {
        "ok": True,
        "service": "self_audit",
        "target": target,
        "threshold": threshold,
        "healthy": healthy,
        "latest": latest,
        "ts": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/api/self-audit/run")
async def self_audit_run_now(authorization: Optional[str] = Header(None)) -> dict:
    """Manual trigger — admin only."""
    _verify_admin(authorization)
    db = _get_db()
    row = await run_self_audit(db)
    if isinstance(row.get("started_at"), datetime):
        row["started_at"] = row["started_at"].isoformat()
    if isinstance(row.get("completed_at"), datetime):
        row["completed_at"] = row["completed_at"].isoformat()
    return {"ok": True, "row": row}


@router.get("/api/self-audit/history")
async def self_audit_history(
    authorization: Optional[str] = Header(None),
    limit: int = 50,
) -> dict:
    """Last N rows for trending. Admin only."""
    _verify_admin(authorization)
    db = _get_db()
    if db is None:
        return {"items": [], "total": 0}
    cap = max(1, min(int(limit or 50), 500))
    cur = db.self_audit_log.find(
        {}, projection={"_id": 0},
    ).sort("started_at", -1).limit(cap)
    items = []
    async for d in cur:
        if isinstance(d.get("started_at"), datetime):
            d["started_at"] = d["started_at"].isoformat()
        if isinstance(d.get("completed_at"), datetime):
            d["completed_at"] = d["completed_at"].isoformat()
        items.append(d)
    return {"items": items, "total": len(items)}
