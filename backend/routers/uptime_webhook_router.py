"""
routers/uptime_webhook_router.py — iter 328c

Single public endpoint that accepts external uptime monitor webhooks.

POST /api/uptime/report
  body: JSON with monitor / url / status / ping_ms / ts / secret
  → 200 with {"ok": true, "stored": true, "secret_ok": bool}
  → 401 if shared secret mismatches and EXTERNAL_UPTIME_SECRET is set.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/api/uptime", tags=["uptime"])

_db = None


def set_db(database):
    global _db
    _db = database


@router.post("/report")
async def uptime_report(request: Request):
    if _db is None:
        raise HTTPException(503, "db not ready")
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "invalid JSON body")
    if not isinstance(body, dict):
        raise HTTPException(400, "JSON object required")

    from services.external_uptime_monitor import (
        record_external_ping, verify_payload_secret,
    )
    # If the founder has configured a secret, enforce it. If not, we
    # still accept the ping so the founder can wire things up and see
    # data flowing — but mark `secret_ok=False` for the audit row.
    import os
    secret_supplied = body.get("secret") or ""
    if os.environ.get("EXTERNAL_UPTIME_SECRET") and not verify_payload_secret(secret_supplied):
        raise HTTPException(401, "invalid shared secret")

    out = await record_external_ping(_db, body)
    return out
