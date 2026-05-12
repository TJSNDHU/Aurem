"""
ora_tools_router.py — Admin-only REST surface for ORA's read-only tools (iter 322ej).

Endpoints:
  GET  /api/ora-tools/list                 — registry of available tools
  POST /api/ora-tools/execute              — invoke one tool by name + args
  GET  /api/ora-tools/invocations          — recent audit log

Pattern matches customer_audit_router + db_audit_router (admin JWT gate).
"""
from __future__ import annotations

import logging
import os
from typing import Optional

import jwt
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ora-tools", tags=["ORA · Tools"])

_db = None
_jwt_secret = os.environ.get("JWT_SECRET") or os.environ.get("JWT_SECRET_KEY") or ""
_jwt_algo = os.environ.get("JWT_ALGO", "HS256")


def set_db(database) -> None:
    global _db
    _db = database
    # Propagate to the service so the audit log + db_count tools work.
    from services.ora_tools import set_db as _set_tools_db
    _set_tools_db(database)


async def _require_admin(authorization: Optional[str]) -> dict:
    if _db is None:
        raise HTTPException(503, "DB not initialised")
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Missing bearer token")
    try:
        payload = jwt.decode(
            authorization.split(" ", 1)[1].strip(),
            _jwt_secret, algorithms=[_jwt_algo],
        )
    except Exception:
        raise HTTPException(401, "Invalid token")
    email = (payload.get("email") or payload.get("sub") or "").lower()
    user = await _db.users.find_one(
        {"email": email},
        {"_id": 0, "is_admin": 1, "is_super_admin": 1, "role": 1},
    )
    if not user or not (
        user.get("is_admin") or user.get("is_super_admin")
        or user.get("role") in ("admin", "super_admin")
    ):
        raise HTTPException(403, "Admin access required")
    return {"email": email}


class ExecuteReq(BaseModel):
    tool: str
    args: dict = {}


@router.get("/list")
async def list_tools_endpoint(authorization: Optional[str] = Header(None)):
    """Return the registry of available read-only tools."""
    await _require_admin(authorization)
    from services.ora_tools import list_tools
    return {"ok": True, "tools": list_tools()}


@router.post("/execute")
async def execute_tool_endpoint(
    body: ExecuteReq,
    authorization: Optional[str] = Header(None),
):
    """Invoke a tool. Read-only in P1 (no writes, no service control)."""
    user = await _require_admin(authorization)
    from services.ora_tools import invoke_tool
    return await invoke_tool(body.tool, body.args, actor=user["email"])


@router.get("/invocations")
async def recent_invocations(
    limit: int = 30,
    tool: Optional[str] = None,
    authorization: Optional[str] = Header(None),
):
    """Audit trail — last N tool invocations."""
    await _require_admin(authorization)
    if limit < 1 or limit > 200:
        limit = 30
    q = {"tool": tool} if tool else {}
    cur = _db.ora_tool_invocations.find(
        q, {"_id": 0},
    ).sort("ts", -1).limit(limit)
    items = await cur.to_list(limit)
    return {"ok": True, "count": len(items), "invocations": items}
