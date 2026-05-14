"""
AUREM Blast-Chain router (Section 7)
====================================

Endpoints
---------
- POST  /api/admin/blast-chain/start            (admin) start a chain for a lead
- POST  /api/admin/blast-chain/run-now          (admin) advance all due chains
- GET   /api/admin/blast-chain/status?lead_id=  (admin) inspect chain state
- POST  /api/blast/reply                        (public webhook) inbound replies
                                                from Resend (email) / Twilio (SMS)

Reply webhook — minimum schema:
  { "lead_id": "...", "channel": "email|sms|whatsapp",
    "text": "raw body", "from": "from address (optional)" }

Resend can be wired via inbound parsing → POST to this endpoint.
Twilio can be wired with a thin shim that resolves From → lead_id, then POSTs.
"""
from __future__ import annotations

import os
import logging
from typing import Any, Dict

import jwt
from fastapi import APIRouter, HTTPException, Request

logger = logging.getLogger(__name__)

router = APIRouter(tags=["blast-chain"])
admin_router = APIRouter(prefix="/api/admin/blast-chain", tags=["admin-blast-chain"])

_db = None


def set_db(database) -> None:
    global _db
    _db = database


def _require_admin(request: Request) -> Dict[str, Any]:
    auth = request.headers.get("Authorization", "")
    token = auth[7:] if auth.startswith("Bearer ") else ""
    if not token:
        raise HTTPException(401, "Auth required")
    try:
        payload = jwt.decode(
            token,
            (os.environ.get("JWT_SECRET") or (_ for _ in ()).throw(__import__("fastapi").HTTPException(status_code=500, detail="JWT not configured"))),
            algorithms=["HS256"],
        )
    except Exception:
        raise HTTPException(401, "Invalid token")
    if not (payload.get("is_admin") or payload.get("is_super_admin") or
            payload.get("role") in ("admin", "super_admin", "founder")):
        raise HTTPException(403, "Admin required")
    return payload


# ─────────────────────────────────────────────────────────────────────
# Admin endpoints
# ─────────────────────────────────────────────────────────────────────

@admin_router.post("/start")
async def chain_start(request: Request) -> Dict[str, Any]:
    """Manually start a 4-touch chain for a single lead."""
    _require_admin(request)
    if _db is None:
        raise HTTPException(503, "database unavailable")
    body = await request.json()
    lead_id = (body.get("lead_id") or "").strip()
    if not lead_id:
        raise HTTPException(400, "lead_id required")
    lead = await _db.campaign_leads.find_one({"lead_id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(404, "lead not found")
    from services.blast_chain import start_chain
    return await start_chain(_db, lead, source="admin")


@admin_router.post("/run-now")
async def chain_run_now(request: Request) -> Dict[str, Any]:
    """Force-advance any chains whose next touch is due."""
    _require_admin(request)
    from services.blast_chain import run_chain_advance_cycle
    return await run_chain_advance_cycle(limit=200)


@admin_router.get("/status")
async def chain_status(request: Request, lead_id: str) -> Dict[str, Any]:
    """Inspect the chain state of a single lead."""
    _require_admin(request)
    if _db is None:
        raise HTTPException(503, "database unavailable")
    lead = await _db.campaign_leads.find_one(
        {"lead_id": lead_id},
        {"_id": 0, "lead_id": 1, "blast_chain": 1, "hot_lead_flag": 1,
         "dnc": 1, "status": 1, "last_blast_at": 1},
    )
    if not lead:
        raise HTTPException(404, "lead not found")
    return lead


# ─────────────────────────────────────────────────────────────────────
# Public reply webhook
# ─────────────────────────────────────────────────────────────────────

@router.post("/api/blast/reply")
async def blast_reply(request: Request) -> Dict[str, Any]:
    """Inbound reply webhook (email / sms / whatsapp).

    Body: { "lead_id": str, "channel": "email|sms|whatsapp",
            "text": str, "from": str }

    Classifies the reply (hot / dnc / cold), updates the lead, halts the
    chain when appropriate, and pings Telegram on hot replies.
    """
    if _db is None:
        raise HTTPException(503, "database unavailable")
    try:
        body = await request.json()
    except Exception:
        body = {}
    lead_id = (body.get("lead_id") or "").strip()
    channel = (body.get("channel") or "").strip().lower() or "email"
    text = (body.get("text") or "").strip()
    from_addr = (body.get("from") or body.get("from_addr") or "").strip()
    if not lead_id or not text:
        raise HTTPException(400, "lead_id and text required")

    from services.blast_chain import handle_reply
    return await handle_reply(
        _db, lead_id, channel=channel, text=text, from_addr=from_addr,
    )
