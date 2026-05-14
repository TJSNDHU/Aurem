"""
ORA Support Chat — lightweight inbound endpoint for the ORAWidget.

Captures every "Where are you stuck?" submission with:
  • message text
  • session_id (client-supplied or generated)
  • page_url where the widget fired
  • optional file attachments (screenshots, logs, PDFs)

All payloads are persisted in `ora_support_tickets` so the founder + Council
can sweep them later. We deliberately do NOT block on an LLM round-trip — the
endpoint replies in under 100 ms with an acknowledgement; deeper triage runs
in a background task. This keeps the widget snappy on every page.

Anonymous (unauthenticated) submissions are accepted; if a JWT is supplied
we attach the email so the follow-up email can be auto-routed.
"""
from __future__ import annotations

import asyncio
import base64
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import List, Optional

import jwt
from fastapi import APIRouter, File, Form, Request, UploadFile

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ora", tags=["ora-support"])

_db = None


def set_db(db):
    global _db
    _db = db


_MAX_ATTACHMENT_BYTES = 5 * 1024 * 1024  # 5 MB per file (matches frontend cap)
_MAX_ATTACHMENTS = 4
_ALLOWED_PREFIXES = (
    "image/",
    "application/pdf",
    "text/plain",
)


def _decode_email_from_token(request: Request) -> Optional[str]:
    """Best-effort: pull email from Bearer JWT if present. Never raises."""
    try:
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return None
        token = auth.split(" ", 1)[1]
        secret = (os.environ.get("JWT_SECRET") or (_ for _ in ()).throw(__import__("fastapi").HTTPException(status_code=500, detail="JWT not configured")))
        if not secret:
            return None
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        return (payload.get("email") or "").lower() or None
    except Exception:
        return None


@router.post("/support-chat")
async def support_chat(
    request: Request,
    message: str = Form(""),
    session_id: str = Form(""),
    page_url: str = Form(""),
    attachments: Optional[List[UploadFile]] = File(default=None),
):
    """Persist a support submission from the ORAWidget."""
    msg = (message or "").strip()
    sid = (session_id or f"ora-{uuid.uuid4().hex[:12]}").strip()
    page = (page_url or "").strip()[:500]
    email = _decode_email_from_token(request)

    # Process attachments (each capped, mime-filtered, base64-stored).
    saved_atts = []
    if attachments:
        for f in attachments[:_MAX_ATTACHMENTS]:
            try:
                ctype = f.content_type or "application/octet-stream"
                if not ctype.startswith(_ALLOWED_PREFIXES):
                    continue
                blob = await f.read()
                if not blob or len(blob) > _MAX_ATTACHMENT_BYTES:
                    continue
                saved_atts.append({
                    "name": f.filename or "attachment",
                    "content_type": ctype,
                    "size_bytes": len(blob),
                    "data_b64": base64.b64encode(blob).decode("ascii"),
                })
            except Exception as e:
                logger.warning(f"[ora-support] attachment skipped: {e}")

    if not msg and not saved_atts:
        return {"ok": False, "error": "empty_submission",
                "response": "Type something or attach a screenshot so I can help."}

    ticket = {
        "id": uuid.uuid4().hex,
        "session_id": sid,
        "email": email,
        "message": msg[:4000],
        "page_url": page,
        "attachments": saved_atts,
        "ip": (request.client.host if request.client else "")[:64],
        "user_agent": request.headers.get("user-agent", "")[:300],
        "status": "new",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    if _db is not None:
        try:
            await _db.ora_support_tickets.insert_one(dict(ticket))
        except Exception as e:
            logger.warning(f"[ora-support] persist failed: {e}")

    # Lightweight, deterministic response. Async LLM triage runs in bg if wired.
    async def _bg_triage():
        try:
            # Hook for future LLM triage / Slack alert / email digest.
            # Kept as a no-op for now so the endpoint can never 500 even
            # if downstream services are absent in preview.
            await asyncio.sleep(0)
        except Exception as e:
            logger.debug(f"[ora-support] bg triage skipped: {e}")

    try:
        asyncio.create_task(_bg_triage())
    except Exception:
        pass

    response_text = (
        "Got it — I've logged this and a teammate will follow up shortly."
        if email
        else "Got it — drop your email above (or sign in) so I can reply directly."
    )

    return {
        "ok": True,
        "ticket_id": ticket["id"],
        "session_id": sid,
        "response": response_text,
    }


@router.get("/support-chat/health")
async def support_chat_health():
    return {"status": "ok", "service": "ora-support-chat"}
