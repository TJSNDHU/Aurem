"""
AUREM — Inbound Email Router (iter 305h)
========================================
Receives email forwarded from Cloudflare Email Routing → Worker →
POST /api/email/inbound, generates an ORA auto-reply via
`call_ora_brain`, and sends it back via Resend with proper threading
headers (`In-Reply-To`, `References`).

Flow:
  Mike replies to ora@aurem.live
    → Cloudflare Email Routing Worker forwards as JSON/webhook to
      https://aurem.live/api/email/inbound
    → This endpoint:
        1. Logs inbound to db.email_inbox
        2. Loads conversation thread (prior outbound + inbound mails
           matching sender-email or message-id root)
        3. Builds ORA system prompt (Canadian-Moat-aware, CASL safe,
           never overpromises)
        4. call_ora_brain(system, user, history)
        5. Sends reply via Resend with threading headers
        6. Logs outbound to db.email_outbox
        7. Returns 200 JSON

Supported shapes for inbound payload (all optional fields tolerated):
  - Cloudflare native workflow:
        {from, to, subject, text, html, headers, messageId}
  - Generic SMTP forward:
        {sender, recipient, subject, body, body_html, message_id, in_reply_to}
  - Resend future inbound webhook compat.

Env:
  RESEND_API_KEY, RESEND_FROM_EMAIL, EMAIL_INBOUND_TOKEN (optional).

Safety:
  - Inbound token check (if EMAIL_INBOUND_TOKEN set) via
    `Authorization: Bearer <token>` or `?token=` query param.
  - Dedup guard on `message_id` (never reply twice to the same email).
  - Founder email (teji.ss1986@gmail.com / FOUNDER_EMAIL) — log but DO
    NOT auto-reply (don't loop on yourself).
  - Max-reply rate: 3 replies per sender per 24h (spam / loop guard).
"""
from __future__ import annotations

import logging
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/email", tags=["Inbound Email"])

RESEND_KEY = os.environ.get("RESEND_API_KEY", "").strip()
RESEND_FROM = os.environ.get("RESEND_FROM_EMAIL", "AUREM <ora@aurem.live>")
FOUNDER_EMAIL = os.environ.get("FOUNDER_EMAIL", "").strip().lower()
INBOUND_TOKEN = os.environ.get("EMAIL_INBOUND_TOKEN", "").strip()

MAX_REPLIES_PER_SENDER_24H = 3

_db = None


def set_db(database):
    global _db
    _db = database


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ─── Payload normalization ──────────────────────────────────────────────────

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def _extract_email(value: str) -> Optional[str]:
    if not value:
        return None
    m = _EMAIL_RE.search(str(value))
    return m.group(0).lower() if m else None


def _coalesce(*vals):
    for v in vals:
        if v:
            return v
    return None


class _Normalised(BaseModel):
    sender: str
    recipient: str
    subject: str = ""
    body: str = ""
    body_html: str = ""
    message_id: str = Field(default_factory=lambda: f"<inbound-{uuid.uuid4().hex}@aurem.live>")
    in_reply_to: Optional[str] = None
    headers: dict = Field(default_factory=dict)


def _normalize_payload(raw: dict) -> Optional[_Normalised]:
    """Accept the union of CF / Resend / generic SMTP shapes."""
    if not isinstance(raw, dict):
        return None
    sender = _extract_email(_coalesce(
        raw.get("from"), raw.get("sender"), raw.get("From"),
        (raw.get("envelope") or {}).get("from"),
    ))
    recipient = _extract_email(_coalesce(
        raw.get("to"), raw.get("recipient"), raw.get("To"),
        (raw.get("envelope") or {}).get("to"),
    ))
    subject = _coalesce(raw.get("subject"), raw.get("Subject")) or ""
    body = _coalesce(raw.get("text"), raw.get("body"), raw.get("body_text"), raw.get("plain")) or ""
    body_html = _coalesce(raw.get("html"), raw.get("body_html"), raw.get("html_body")) or ""
    message_id = _coalesce(
        raw.get("messageId"), raw.get("message_id"),
        (raw.get("headers") or {}).get("message-id"),
        (raw.get("headers") or {}).get("Message-ID"),
    )
    in_reply_to = _coalesce(
        raw.get("inReplyTo"), raw.get("in_reply_to"),
        (raw.get("headers") or {}).get("in-reply-to"),
        (raw.get("headers") or {}).get("In-Reply-To"),
    )
    headers = raw.get("headers") or {}
    if not sender or not recipient:
        return None
    data = {
        "sender": sender, "recipient": recipient,
        "subject": subject, "body": body, "body_html": body_html,
        "headers": headers,
    }
    if message_id:
        data["message_id"] = message_id
    if in_reply_to:
        data["in_reply_to"] = in_reply_to
    return _Normalised(**data)


# ─── ORA Reply Generation ────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are ORA — the AI concierge for AUREM, an AI sales
platform for Canadian trades businesses. You are responding to an
inbound email reply on behalf of TJ (founder).

Style rules (strict):
- Warm, human, concise. First-name basis. 3–5 short paragraphs max.
- Canadian English spelling, polite, NEVER pushy or salesy.
- If the sender is clearly a lead: acknowledge their reply, answer any
  specific question they asked, and gently point them to the next
  action (pricing, signup, or book a call).
- If the sender asks a technical question (e.g., "how does this
  work"): explain in plain English in 2–3 bullet points.
- If the sender says "stop", "unsubscribe", "not interested": respond
  with a one-line polite acknowledgement ("You're unsubscribed — no
  more emails from us. Thanks for letting us know.") and do NOT sell.
- NEVER invent pricing, SLAs, features, or capabilities. Only reference
  the 3 AUREM plans: Starter $97/mo, Growth $449/mo, Enterprise
  $997/mo — in CAD.
- Always end with "Warm regards, TJ · AUREM" (founder signature). Never
  sign off as "ORA" or "AI".
- Include real links only from this allowlist:
    https://aurem.live/#pricing
    https://aurem.live/platform/login
    https://aurem.live/book
    https://aurem.live

Return ONLY the plain-text email body. No subject line. No greeting
boilerplate before your first paragraph."""


async def _load_thread(db, sender: str, limit: int = 8) -> list[dict]:
    """Pull last N mails with this sender, oldest first, for LLM context."""
    if db is None:
        return []
    out: list[dict] = []
    async for row in db.email_inbox.find(
        {"sender": sender}, {"_id": 0, "subject": 1, "body": 1, "ts": 1}
    ).sort("ts", -1).limit(limit):
        row["direction"] = "inbound"
        out.append(row)
    async for row in db.email_outbox.find(
        {"to": sender}, {"_id": 0, "subject": 1, "body": 1, "ts": 1}
    ).sort("ts", -1).limit(limit):
        row["direction"] = "outbound"
        out.append(row)
    # Sort oldest first so LLM sees temporal flow
    out.sort(key=lambda r: r.get("ts") or datetime.min.replace(tzinfo=timezone.utc))
    return out[-limit:]


def _format_history_for_llm(history: list[dict]) -> list[dict]:
    msgs: list[dict] = []
    for row in history:
        role = "user" if row.get("direction") == "inbound" else "assistant"
        body = (row.get("body") or "")[:1500]
        if not body:
            continue
        msgs.append({"role": role, "content": body})
    return msgs


async def _generate_reply(inbound: _Normalised, history: list[dict]) -> str:
    from services.openrouter_client import call_ora_brain
    user_block = (
        f"Subject: {inbound.subject or '(no subject)'}\n"
        f"From: {inbound.sender}\n\n"
        f"{(inbound.body or '(empty body)')[:4000]}\n\n"
        "Compose the plain-text reply body now."
    )
    try:
        res = await call_ora_brain(
            system_prompt=_SYSTEM_PROMPT,
            user_message=user_block,
            conversation_history=_format_history_for_llm(history),
            temperature=0.5,
            max_tokens=600,
        )
    except Exception as e:
        logger.exception(f"[email_inbound] ORA brain failed: {e}")
        return (
            "Hey — thanks for writing back! I'll get you a proper answer within a few hours.\n\n"
            "In the meantime, everything is live at https://aurem.live — pricing on the homepage.\n\n"
            "Warm regards,\nTJ · AUREM"
        )
    body = (res.get("content") or res.get("text") or "").strip()
    if not body:
        body = "Thanks for the reply! TJ here — I'll personally follow up shortly.\n\nWarm regards,\nTJ · AUREM"
    return body


# ─── Outbound ───────────────────────────────────────────────────────────────

def _send_via_resend(to: str, subject: str, body: str, in_reply_to: Optional[str]) -> dict:
    if not RESEND_KEY:
        return {"ok": False, "error": "RESEND_API_KEY not set"}
    try:
        import resend  # type: ignore
        resend.api_key = RESEND_KEY
        params: dict[str, Any] = {
            "from": RESEND_FROM,
            "to": [to],
            "subject": subject,
            "text": body,
            "html": body.replace("\n", "<br>"),
        }
        if in_reply_to:
            # Resend passes headers through as email headers
            params["headers"] = {
                "In-Reply-To": in_reply_to,
                "References": in_reply_to,
            }
        r = resend.Emails.send(params)
        return {"ok": True, "resend_id": (r or {}).get("id")}
    except Exception as e:
        logger.exception(f"[email_inbound] resend send failed: {e}")
        return {"ok": False, "error": str(e)[:160]}


# ─── Guards ─────────────────────────────────────────────────────────────────

async def _already_processed(db, message_id: str) -> bool:
    if not message_id or db is None:
        return False
    doc = await db.email_inbox.find_one(
        {"message_id": message_id, "replied": True}, {"_id": 1},
    )
    return bool(doc)


async def _reply_rate_exceeded(db, sender: str) -> bool:
    if db is None:
        return False
    cutoff = _now() - timedelta(hours=24)
    n = await db.email_outbox.count_documents(
        {"to": sender, "ts": {"$gte": cutoff}, "source": "email_inbound_autoreply"},
    )
    return n >= MAX_REPLIES_PER_SENDER_24H


def _auth_ok(request: Request) -> bool:
    """Bug-fix #96 — previously returned True when INBOUND_TOKEN was
    unset, making the inbound email endpoint fully public. Anyone could
    POST a fake email and trigger ORA to compose+send an auto-reply
    (prompt injection vector). Now we fail closed when the token is
    not configured, unless explicitly opted out for local dev."""
    if not INBOUND_TOKEN:
        # Explicit dev opt-in only
        if os.environ.get("EMAIL_INBOUND_ALLOW_PUBLIC", "").strip() == "1":
            return True
        logger.error(
            "[email_inbound] rejected — EMAIL_INBOUND_TOKEN not set. "
            "Set it in .env or set EMAIL_INBOUND_ALLOW_PUBLIC=1 to opt-in for dev."
        )
        return False
    ah = request.headers.get("Authorization", "")
    if ah.startswith("Bearer ") and ah[7:].strip() == INBOUND_TOKEN:
        return True
    if request.query_params.get("token") == INBOUND_TOKEN:
        return True
    return False


# ─── Routes ─────────────────────────────────────────────────────────────────

@router.get("/inbound/health")
async def inbound_health():
    return {
        "ok": True,
        "resend_configured": bool(RESEND_KEY),
        "token_required": bool(INBOUND_TOKEN),
        "founder_email_set": bool(FOUNDER_EMAIL),
        "max_replies_per_sender_24h": MAX_REPLIES_PER_SENDER_24H,
    }


@router.post("/inbound")
async def email_inbound(request: Request):
    """Primary inbound webhook — Cloudflare Email Worker → here."""
    if not _auth_ok(request):
        raise HTTPException(status_code=401, detail="Invalid or missing inbound token")
    if _db is None:
        raise HTTPException(status_code=503, detail="DB unavailable")

    try:
        raw = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    inbound = _normalize_payload(raw)
    if not inbound:
        # Log raw payload for forensic debug so no mail is silently dropped
        await _db.email_inbox.insert_one({
            "ts": _now(), "parsed": False, "raw": raw,
            "error": "unparseable_payload",
        })
        raise HTTPException(status_code=400, detail="Missing sender / recipient")

    # Dedup on message-id
    if await _already_processed(_db, inbound.message_id):
        return {"ok": True, "skipped": "already_processed", "message_id": inbound.message_id}

    # Log inbound first (always, even if we later decline to reply)
    inbox_doc = {
        "ts": _now(),
        "parsed": True,
        "sender": inbound.sender,
        "recipient": inbound.recipient,
        "subject": inbound.subject,
        "body": inbound.body,
        "body_html": inbound.body_html,
        "message_id": inbound.message_id,
        "in_reply_to": inbound.in_reply_to,
        "headers": inbound.headers,
        "replied": False,
    }
    await _db.email_inbox.insert_one(inbox_doc)

    # Don't auto-reply to ourselves / founder
    if inbound.sender == FOUNDER_EMAIL or inbound.sender == inbound.recipient:
        return {"ok": True, "skipped": "founder_or_self"}

    # Rate limit guard (spam / loop protection)
    if await _reply_rate_exceeded(_db, inbound.sender):
        logger.warning(f"[email_inbound] rate limit exceeded for {inbound.sender}")
        return {"ok": True, "skipped": "rate_limit_exceeded"}

    # Generate and send reply
    history = await _load_thread(_db, inbound.sender, limit=6)
    reply_body = await _generate_reply(inbound, history)

    reply_subject = inbound.subject or "Re: your message"
    if reply_subject and not reply_subject.lower().startswith("re:"):
        reply_subject = f"Re: {reply_subject}"

    send_res = _send_via_resend(
        to=inbound.sender,
        subject=reply_subject,
        body=reply_body,
        in_reply_to=inbound.message_id,
    )

    # Log outbound
    await _db.email_outbox.insert_one({
        "ts": _now(),
        "to": inbound.sender,
        "from": RESEND_FROM,
        "subject": reply_subject,
        "body": reply_body,
        "in_reply_to": inbound.message_id,
        "resend_id": send_res.get("resend_id"),
        "ok": send_res.get("ok"),
        "error": send_res.get("error"),
        "source": "email_inbound_autoreply",
    })

    if send_res.get("ok"):
        await _db.email_inbox.update_one(
            {"message_id": inbound.message_id},
            {"$set": {"replied": True, "replied_at": _now()}},
        )
    return {
        "ok": bool(send_res.get("ok")),
        "sender": inbound.sender,
        "reply_sent": bool(send_res.get("ok")),
        "resend_id": send_res.get("resend_id"),
        "error": send_res.get("error"),
    }


# Idempotent index ensure
async def ensure_email_indexes(db) -> None:
    try:
        await db.email_inbox.create_index(
            "message_id", name="email_inbox_msgid",
            partialFilterExpression={"message_id": {"$exists": True}},
        )
        await db.email_inbox.create_index([("sender", 1), ("ts", -1)],
                                          name="email_inbox_sender_ts")
        await db.email_outbox.create_index([("to", 1), ("ts", -1)],
                                           name="email_outbox_to_ts")
    except Exception as e:
        logger.debug(f"[email_inbound] index ensure skipped: {e}")
