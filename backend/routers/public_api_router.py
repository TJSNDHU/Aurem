"""
routers/public_api_router.py — iter D-59 Part B

Public-facing AUREM API. Third-party projects (or the founder's other
apps) authenticate with `Authorization: Bearer aurem_sk_live_...` and
get access to:

  POST /api/v1/public/ora/chat       (scope: ora_chat)
  POST /api/v1/public/cto/chat       (scope: cto_chat)
  GET  /api/v1/public/leads/lookup   (scope: leads_read)
  GET  /api/v1/public/health         (no scope — sanity ping)

All requests are rate-limited per-key per-day, logged to
`aurem_api_usage`, and rejected with proper HTTP codes:

  401 invalid_key
  403 scope_forbidden
  429 daily_quota_exceeded
"""
from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/public", tags=["aurem-public-api"])


def set_db(database) -> None:
    from services import aurem_public_api as _svc
    _svc.set_db(database)


async def _gate(authorization: str | None, scope: str) -> dict[str, Any]:
    """Standard auth + rate-limit + audit prelude for every public
    endpoint. Returns the key row on success or raises HTTPException."""
    from services.aurem_public_api import (
        validate_key, check_rate_limit, KEY_PREFIX,
    )
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "missing_bearer_token")
    secret = authorization.split(" ", 1)[1]
    if not secret.startswith(KEY_PREFIX):
        raise HTTPException(401, "invalid_key_format")
    row = await validate_key(secret, scope=scope)
    if not row:
        raise HTTPException(403, "invalid_key_or_scope_forbidden")
    allowed, reason = await check_rate_limit(row["key_id"])
    if not allowed:
        raise HTTPException(429, reason)
    return row


async def _record(row: dict[str, Any], endpoint: str,
                   status_code: int, started_at: float) -> None:
    from services.aurem_public_api import record_usage
    latency_ms = int((time.time() - started_at) * 1000)
    await record_usage(row["key_id"], endpoint, status_code, latency_ms)


# ── /health (anonymous) ──────────────────────────────────────────────

@router.get("/health")
async def health() -> dict[str, Any]:
    return {"ok": True, "platform": "aurem-public-api", "version": "v1"}


# ── /ora/chat ────────────────────────────────────────────────────────

class ChatBody(BaseModel):
    message:     str = Field(..., min_length=1, max_length=4000)
    session_id:  str = Field("", max_length=80)
    system_hint: str = Field("", max_length=400)


@router.post("/ora/chat")
async def ora_chat(body: ChatBody,
                    authorization: str = Header(None)) -> dict[str, Any]:
    started = time.time()
    row = await _gate(authorization, "ora_chat")
    try:
        from services.dev_cto_chat import _free_tier_key, _call_openrouter
        api_key = _free_tier_key() or ""
        sys_msg = (
            "You are ORA, the AUREM customer-facing assistant. Be warm, "
            "concise, on-brand. " + (body.system_hint or "")
        )
        messages = [
            {"role": "system", "content": sys_msg},
            {"role": "user",   "content": body.message},
        ]
        reply = await _call_openrouter(
            api_key, "deepseek/deepseek-chat-v3-0324:free",
            messages, temperature=0.2,
        )
        out = {"ok": True, "reply": reply,
                "session_id": body.session_id,
                "tier": "free", "model": "deepseek-v3"}
        await _record(row, "/ora/chat", 200, started)
        return out
    except Exception as e:
        await _record(row, "/ora/chat", 500, started)
        raise HTTPException(500, f"ora_chat_error: {e}")


# ── /cto/chat ────────────────────────────────────────────────────────

@router.post("/cto/chat")
async def cto_chat(body: ChatBody,
                    authorization: str = Header(None)) -> dict[str, Any]:
    started = time.time()
    row = await _gate(authorization, "cto_chat")
    try:
        from services.dev_cto_chat import _free_tier_key, _call_openrouter
        api_key = _free_tier_key() or ""
        sys_msg = (
            "You are AUREM CTO, a deterministic engineering assistant. "
            "Be precise, plain-English, 1-3 sentences. Never invent "
            "SHAs/dates/iter tags. " + (body.system_hint or "")
        )
        messages = [
            {"role": "system", "content": sys_msg},
            {"role": "user",   "content": body.message},
        ]
        reply = await _call_openrouter(
            api_key, "deepseek/deepseek-chat-v3-0324:free",
            messages, temperature=0.0,
        )
        out = {"ok": True, "reply": reply,
                "session_id": body.session_id,
                "tier": "free", "model": "deepseek-v3"}
        await _record(row, "/cto/chat", 200, started)
        return out
    except Exception as e:
        await _record(row, "/cto/chat", 500, started)
        raise HTTPException(500, f"cto_chat_error: {e}")


# ── /leads/lookup ────────────────────────────────────────────────────

@router.get("/leads/lookup")
async def leads_lookup(
    email: str = Query("", max_length=200),
    phone: str = Query("", max_length=40),
    limit: int = Query(5, ge=1, le=20),
    authorization: str = Header(None),
) -> dict[str, Any]:
    started = time.time()
    row = await _gate(authorization, "leads_read")
    if not email and not phone:
        await _record(row, "/leads/lookup", 400, started)
        raise HTTPException(400, "email_or_phone_required")
    from services.aurem_public_api import _db
    if _db is None:
        raise HTTPException(503, "db_unavailable")
    q: dict[str, Any] = {}
    if email: q["email"] = email.strip().lower()
    if phone: q["phone"] = phone.strip()
    items: list[dict[str, Any]] = []
    async for d in _db.campaign_leads.find(
        q, {"_id": 0, "lead_id": 1, "business_name": 1, "email": 1,
             "phone": 1, "city": 1, "country": 1, "status": 1,
             "hot_lead_flag": 1},
    ).limit(limit):
        items.append(d)
    out = {"ok": True, "items": items, "count": len(items)}
    await _record(row, "/leads/lookup", 200, started)
    return out
