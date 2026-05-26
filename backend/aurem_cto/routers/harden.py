"""
aurem_cto.routers.harden — P1 server auto-hardening (placeholder).

When a customer connects a server for the first time, this router
SSHes in and runs apt update/upgrade, installs Docker + Compose +
Caddy, sets up the deploy user, locks down root SSH, and returns the
hardening report.

Real implementation lands in the P1 slice. Right now only a status
endpoint is exposed so the frontend can detect module presence.
"""
from __future__ import annotations

from fastapi import APIRouter, Header

from ..services.auth import current_dev
from ..services.db import require_db

router = APIRouter(prefix="/harden", tags=["AUREM CTO Hardening"])


@router.get("/last")
async def last_report(authorization: str = Header(None)) -> dict:
    """Returns the most recent hardening report for this user, or null."""
    me = await current_dev(authorization)
    db = require_db()
    row = await db.aurem_cto_server_hardenings.find_one(
        {"user_id": me["user_id"]},
        {"_id": 0},
        sort=[("ts", -1)],
    )
    return {"report": row}
