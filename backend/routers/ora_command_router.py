"""
ORA Command Router
==================
Exposes the ORA Command Center across 3 channels:

  POST /api/ora/command            — ORA chat (aurem.live) & generic JSON
  POST /api/ora/telegram/webhook   — Telegram bot webhook
  POST /api/ora/whapi/webhook      — WhatsApp (WHAPI) inbound command webhook
  GET  /api/ora/command/help       — Returns the help text (public)

All channels share the same parser/executor (services.ora_command_center).
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ora", tags=["ORA Command Center"])

_db = None


def set_db(db):
    global _db
    _db = db


def _get_db():
    return _db


# ─────────────────────────────────────────────────────────────
# MODELS
# ─────────────────────────────────────────────────────────────
class CommandRequest(BaseModel):
    text: str
    channel: Optional[str] = "chat"
    user: Optional[str] = "admin"
    session_id: Optional[str] = None


# ─────────────────────────────────────────────────────────────
# PUBLIC HELP
# ─────────────────────────────────────────────────────────────
@router.get("/command/help")
async def command_help():
    from services.ora_command_center import HELP_TEXT
    return {"help": HELP_TEXT}


# ─────────────────────────────────────────────────────────────
# GENERIC ENDPOINT — used by aurem.live ORA chat UI
# ─────────────────────────────────────────────────────────────
@router.post("/command")
async def run_command(body: CommandRequest):
    """
    Parse and execute a natural-language AUREM command.

    Dispatch order (iter 281.2 — Sovereign Brain):
      1. ora_command_center.execute_command — explicit AUREM commands
         (status / leads / scout / blast / pipeline / build / fix / ...)
      2. If intent ∈ {UNKNOWN, CHAT} → fall through to ORA Sovereign
         Brain which classifies the message into Mode 1 (general
         intelligence via ULTRAPLINIAN) or Mode 2 (engineering proposal
         queued in db.ora_dev_actions for human approval).
      3. iter 281.4 / Phase 2.4 — every reply is auto-localized to the
         user's detected language (Hindi/Punjabi/French/Arabic/etc.)
         using the dual-pass language detector + Claude translator.

    Returns {"ok", "intent", "reply", "params", "data"}.
    """
    from services.ora_command_center import execute_command
    from services.language_detector import (
        detect_language, remember_language, localize_reply,
    )
    db = _get_db()
    user = body.user or "admin"
    sid = body.session_id if hasattr(body, "session_id") and body.session_id else f"ora_{user}"

    # Pass 1+2 language detection (in parallel-friendly order)
    detected = await detect_language(body.text)
    preferred = await remember_language(db, session_id=sid, user=user, detected=detected)

    result = await execute_command(
        db, body.text, channel=body.channel or "chat", user=user
    )

    # Brain fallback — only when registered command parser didn't catch it.
    if result.get("intent") in ("UNKNOWN", "CHAT"):
        try:
            from services.ora_brain import run_brain
            brain = await run_brain(
                db, body.text,
                session_id=sid,
                user=user,
            )
            if brain.get("ok") or result.get("intent") == "UNKNOWN":
                brain["intent"] = brain.get("intent") or "general"
                result = brain
        except Exception as e:
            logger.warning(f"[ORA-CC] Sovereign brain fallback failed: {e}")

    # Language-aware response — mirror the user's language.
    target = preferred or detected.get("lang", "en")
    address = detected.get("reply_address", "boss")
    is_mixed = bool(detected.get("is_mixed"))
    if target and target != "en" and result.get("reply"):
        try:
            result["reply"] = await localize_reply(
                result["reply"],
                target_lang=target,
                is_mixed=is_mixed,
                address=address,
            )
        except Exception as e:
            logger.debug(f"[ORA-CC] localize_reply failed: {e}")

    # iter 281.5 — Phase 2.5 hooks (omnichannel context + next-best-action)
    # Skip for anonymous homepage_visitor / public traffic to keep latency
    # low (NBA Claude call adds ~3-5s per turn).
    is_anon = (user or "admin") in ("homepage_visitor", "anonymous", "public", "")
    if not is_anon:
        try:
            from services.ora_phase_25 import remember_omni_context, generate_next_action
            await remember_omni_context(
                db, user=user, channel=body.channel or "chat",
                text=body.text, intent=result.get("intent"),
            )
            # Generate NBA in the background-ish (await but cheap if LLM up)
            nba = await generate_next_action(
                db, user=user, context_text=body.text,
                last_intent=result.get("intent"),
            )
            result["data"]["next_action"] = nba
        except Exception as e:
            logger.debug(f"[ORA-CC] phase-25 hooks failed: {e}")

    # Surface language metadata in `data` for clients (debug + UI)
    result.setdefault("data", {})
    result["data"]["language"] = {
        "detected": detected.get("lang"),
        "script": detected.get("script"),
        "confidence": detected.get("confidence"),
        "is_mixed": is_mixed,
        "preferred": preferred,
        "address": address,
    }
    return result


# ─────────────────────────────────────────────────────────────
# TELEGRAM WEBHOOK
# Setup: BotFather → /newbot → copy token into TELEGRAM_BOT_TOKEN
# Then: curl https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://aurem.live/api/ora/telegram/webhook
# ─────────────────────────────────────────────────────────────
async def _telegram_reply(chat_id: int | str, text: str) -> bool:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        logger.warning("[ORA-CC] TELEGRAM_BOT_TOKEN not set — cannot reply")
        return False
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown", "disable_web_page_preview": True},
            )
        return resp.status_code == 200
    except Exception as e:
        logger.warning(f"[ORA-CC] Telegram send failed: {e}")
        return False


@router.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    """
    Receives Telegram updates. Extracts the message text, executes the command,
    replies in the same chat.
    """
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON body")

    # Optional: verify Telegram secret token header
    expected_secret = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")
    if expected_secret:
        got = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if got != expected_secret:
            raise HTTPException(401, "Bad secret token")

    msg = payload.get("message") or payload.get("edited_message") or {}
    chat = msg.get("chat") or {}
    chat_id = chat.get("id")
    text = (msg.get("text") or "").strip()
    user = (msg.get("from") or {}).get("username") or str((msg.get("from") or {}).get("id", "tg_user"))

    if not chat_id or not text:
        return {"ok": True, "skipped": "no_text"}

    from services.ora_command_center import execute_command
    db = _get_db()
    result = await execute_command(db, text, channel="telegram", user=user)
    reply = result.get("reply") or "Command received."
    await _telegram_reply(chat_id, reply)
    return {"ok": True, "intent": result.get("intent")}


# ─────────────────────────────────────────────────────────────
# WHATSAPP (WHAPI) INBOUND COMMAND WEBHOOK
# Setup in WHAPI Dashboard → Webhooks → point "messages" events to:
#   https://aurem.live/api/ora/whapi/webhook
# ─────────────────────────────────────────────────────────────
ADMIN_PHONES = {p.strip() for p in os.environ.get("AUREM_ADMIN_PHONES", "").split(",") if p.strip()}


async def _whapi_reply(to_chat_id: str, text: str) -> bool:
    whapi_token = os.environ.get("WHAPI_API_TOKEN", "")
    whapi_url = os.environ.get("WHAPI_API_URL", "")
    if not (whapi_token and whapi_url):
        logger.warning("[ORA-CC] WHAPI not configured — cannot reply")
        return False
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{whapi_url}/messages/text",
                headers={"authorization": f"Bearer {whapi_token}", "content-type": "application/json"},
                json={"to": to_chat_id, "body": text},
            )
        return resp.status_code == 200
    except Exception as e:
        logger.warning(f"[ORA-CC] WHAPI send failed: {e}")
        return False


@router.post("/whapi/webhook")
async def whapi_webhook(request: Request):
    """
    Receives inbound WhatsApp messages from WHAPI.
    Only admins listed in AUREM_ADMIN_PHONES can issue commands
    (to prevent random prospects triggering scouts/blasts).
    """
    try:
        payload = await request.json()
    except Exception:
        return Response(status_code=200)

    messages = payload.get("messages", []) or []
    processed = 0
    for m in messages:
        if m.get("from_me"):
            continue
        text = ""
        if isinstance(m.get("text"), dict):
            text = m["text"].get("body", "") or ""
        elif isinstance(m.get("text"), str):
            text = m["text"]
        text = (text or "").strip()
        if not text:
            continue

        chat_id = m.get("chat_id") or m.get("from") or ""
        from_phone = (m.get("from") or "").split("@")[0].split(":")[0]

        # ACL: only whitelisted admin phones may issue commands
        if ADMIN_PHONES and from_phone not in ADMIN_PHONES:
            logger.info(f"[ORA-CC] WhatsApp command ignored (non-admin): {from_phone}")
            continue

        from services.ora_command_center import execute_command
        db = _get_db()
        result = await execute_command(db, text, channel="whatsapp", user=from_phone)
        reply = result.get("reply") or "Command received."
        await _whapi_reply(chat_id, reply)
        processed += 1

    return {"ok": True, "processed": processed}


# ─────────────────────────────────────────────────────────────
# ADMIN UTILITY — set Telegram webhook URL with one call
# ─────────────────────────────────────────────────────────────
@router.post("/telegram/setup-webhook")
async def telegram_setup_webhook(request: Request):
    """
    Registers this server's /api/ora/telegram/webhook URL with Telegram.
    Body: {"base_url": "https://aurem.live"}  (or omit to use request.base_url)
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        raise HTTPException(400, "TELEGRAM_BOT_TOKEN not set")
    body: Dict[str, Any] = {}
    try:
        body = await request.json()
    except Exception:
        body = {}
    base = body.get("base_url") or str(request.base_url).rstrip("/")
    webhook_url = f"{base}/api/ora/telegram/webhook"
    params: Dict[str, Any] = {"url": webhook_url, "drop_pending_updates": True}
    secret = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")
    if secret:
        params["secret_token"] = secret
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(f"https://api.telegram.org/bot{token}/setWebhook", json=params)
        return {"ok": resp.status_code == 200, "telegram_response": resp.json(), "webhook_url": webhook_url}
    except Exception as e:
        raise HTTPException(500, f"Telegram setup failed: {e}")
