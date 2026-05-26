"""
aurem_cto.routers.unlock — P6 unlock-request flow placeholder.

Customer requests temporary GitHub collaborator access. Admin approves
with a time window; cron auto-revokes when the window expires. Full
audit trail.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, Field

from ..services.auth import current_dev
from ..services.db import require_db

router = APIRouter(prefix="/unlock", tags=["AUREM CTO Unlock"])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class UnlockRequestBody(BaseModel):
    reason: str = Field(..., min_length=10, max_length=2000)


@router.post("/request")
async def request_unlock(body: UnlockRequestBody,
                          authorization: str = Header(None)) -> dict[str, Any]:
    me = await current_dev(authorization)
    db = require_db()
    import uuid as _u
    req_id = _u.uuid4().hex[:16]
    await db.aurem_cto_unlock_requests.insert_one({
        "request_id":  req_id,
        "user_id":     me["user_id"],
        "email":       me.get("email", ""),
        "reason":      body.reason,
        "status":      "pending",
        "requested_at": _now_iso(),
        "approved_at": None,
        "approved_by": None,
        "expires_at":  None,
        "revoked_at":  None,
    })
    return {"request_id": req_id, "status": "pending"}


@router.get("/mine")
async def my_requests(authorization: str = Header(None)) -> dict[str, Any]:
    me = await current_dev(authorization)
    db = require_db()
    cur = db.aurem_cto_unlock_requests.find(
        {"user_id": me["user_id"]}, {"_id": 0},
    ).sort("requested_at", -1).limit(20)
    rows = [d async for d in cur]
    return {"requests": rows}
