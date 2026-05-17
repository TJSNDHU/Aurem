"""
ora_chat_router.py — Conversational endpoint that uses the tool-call loop
(iter 322el). Lets ORA actually invoke tools mid-conversation instead of
text-fabricating results.

Endpoint:
  POST /api/ora-chat/ask    {prompt, system?}   → real tool-grounded answer
"""
from __future__ import annotations

import logging
import os
from typing import Optional

import jwt
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ora-chat", tags=["ORA · Chat"])

_db = None
_jwt_secret = os.environ.get("JWT_SECRET") or ""
_jwt_algo = "HS256"


def set_db(database) -> None:
    global _db
    _db = database


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


class AskReq(BaseModel):
    prompt: str
    system: Optional[str] = None
    max_tool_iters: int = 4


@router.post("/ask")
async def ask(body: AskReq, authorization: Optional[str] = Header(None)):
    """Ask ORA a question — uses the tool-call loop so all answers are
    tool-grounded (real subprocess + db + curl), never fabricated.

    iter 322ew prod-guard — wrapped in asyncio.wait_for so the request can
    NEVER hang infinitely on a stuck tool-iteration / LLM provider. Cap at
    90s. If we hit the cap the client gets a clear timeout response
    instead of a spinning loader.
    """
    import asyncio
    user = await _require_admin(authorization)
    from services.llm_gateway import call_llm_with_tools
    system = body.system or (
        "You are ORA, the AUREM autonomous agent. Apply your Core Law (Zero "
        "Hallucination Charter): every claim must come from a real tool "
        "invocation in this session. When the founder asks a question, USE "
        "the tools to fetch real data. Quote tool output verbatim. End every "
        "answer with the mandatory 3-proof footer."
    )
    try:
        res = await asyncio.wait_for(
            call_llm_with_tools(
                system_prompt=system,
                user_prompt=body.prompt,
                max_tokens=900,
                max_tool_iters=max(1, min(body.max_tool_iters, 6)),
                actor=user["email"],
            ),
            timeout=90.0,
        )
        return res
    except asyncio.TimeoutError:
        logger.warning(f"[ora-chat] /ask timed out at 90s for {user.get('email')}")
        return {
            "ok": False,
            "content": (
                "(ORA timed out — request exceeded 90s. The Sovereign tunnel "
                "may be down or all LLM providers are slow. Try again, or "
                "check /admin/ora-settings for provider health.)"
            ),
            "tool_calls_run": 0,
            "tool_invocations": [],
            "iterations": 0,
            "provider": "timeout",
            "error": "request_timeout_90s",
        }
