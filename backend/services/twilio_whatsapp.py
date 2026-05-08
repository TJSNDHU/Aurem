"""
Twilio WhatsApp Business API (WABA) — iter 287.4

Official, Meta-approved WhatsApp outbound messaging. Replaces the
unofficial WHAPI QR-scan gateway (which got the founder's personal
WhatsApp account restricted for bulk outreach).

CONFIGURATION (.env):
  TWILIO_ACCOUNT_SID        # already present
  TWILIO_AUTH_TOKEN         # already present
  TWILIO_WA_FROM_NUMBER     # e.g. whatsapp:+14155238886 (sandbox) or
                            # whatsapp:+14314500004 (your registered sender)
  TWILIO_WA_TEMPLATE_SID    # Content SID of your approved template (optional;
                            # only needed for cold outreach beyond 24h session)
  TWILIO_WA_STATUS_WEBHOOK  # optional: public URL for delivery callbacks

TWO MODES:

1) SESSION message (freeform, cheap, < 24h after user's last reply)
     await send_whatsapp_session(
         to_phone="+16475551234",
         body="Thanks for replying! Here's the brochure...",
     )

2) TEMPLATE message (cold outreach, Meta-approved templates only)
     await send_whatsapp_template(
         to_phone="+16475551234",
         content_sid="HXxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
         variables={"1": "Master Maid", "2": "Toronto"},
     )

PRICING (Twilio, as of 2026-04):
  - Marketing template (cold):  $0.0358 / msg  (CA)
  - Utility template:           $0.0115 / msg
  - Authentication template:    $0.0083 / msg
  - Session message:            $0.0000 / msg  (included in conversation fee)
  - Conversation fee (24h):     $0.0055 (marketing) / $0.0055 (utility)

GETTING STARTED — SANDBOX (5 min, no Meta review):
  1. Twilio console → Messaging → Try it out → Send a WhatsApp message
  2. You'll see a sandbox number + join code (e.g. "join xxx-xxx")
  3. From your phone, WhatsApp that code to +1 415 523 8886
  4. Set TWILIO_WA_FROM_NUMBER=whatsapp:+14155238886
  5. Test messages will now work (but only to numbers that have joined)

GETTING STARTED — PRODUCTION (1-3 days, Meta reviews):
  1. Twilio console → Messaging → Senders → WhatsApp Senders → Create
  2. Submit your Twilio number +14314500004 for WhatsApp
  3. Meta verifies your business (requires Facebook Business Manager account)
  4. Once approved, submit templates under Messaging → Content Builder
  5. Templates approve in 24-48h; use content_sid in send_whatsapp_template()
"""
from __future__ import annotations

import logging
import os
from typing import Any, Optional

import httpx

logger = logging.getLogger("twilio_whatsapp")

TWILIO_API_BASE = "https://api.twilio.com/2010-04-01"


def _normalize_phone(phone: str) -> str:
    """Convert '(416) 555-1234' or '14165551234' → '+14165551234'.
    Returns '' on junk input."""
    if not phone:
        return ""
    digits = "".join(c for c in phone if c.isdigit())
    if not digits:
        return ""
    if len(digits) == 10:
        digits = "1" + digits
    if len(digits) < 10:
        return ""
    return "+" + digits


def _wa_addr(phone: str) -> str:
    """Wrap phone for WhatsApp format: '+16475551234' → 'whatsapp:+16475551234'"""
    normalized = _normalize_phone(phone)
    if not normalized:
        return ""
    if normalized.startswith("whatsapp:"):
        return normalized
    return f"whatsapp:{normalized}"


def _creds() -> tuple[Optional[str], Optional[str], Optional[str]]:
    sid = (os.environ.get("TWILIO_ACCOUNT_SID") or "").strip()
    tok = (os.environ.get("TWILIO_AUTH_TOKEN") or "").strip()
    frm = (os.environ.get("TWILIO_WA_FROM_NUMBER") or "").strip()
    if frm and not frm.startswith("whatsapp:"):
        frm = f"whatsapp:{frm}"
    return (sid or None, tok or None, frm or None)


async def send_whatsapp_session(
    to_phone: str,
    body: str,
) -> dict:
    """Freeform session message. ONLY works within 24h of recipient's
    last inbound message. Meta will REJECT cold freeform messages.

    Returns:
      {"success": bool, "message_sid": str|None, "error": str|None,
       "to": str, "mode": "session"}
    """
    sid, tok, frm = _creds()
    missing = []
    if not sid:
        missing.append("TWILIO_ACCOUNT_SID")
    if not tok:
        missing.append("TWILIO_AUTH_TOKEN")
    if not frm:
        missing.append("TWILIO_WA_FROM_NUMBER")
    if missing:
        return {"success": False, "error": f"creds_missing: {','.join(missing)}",
                "to": to_phone, "mode": "session"}

    to_wa = _wa_addr(to_phone)
    if not to_wa:
        return {"success": False, "error": "invalid_phone", "to": to_phone,
                "mode": "session"}

    data = {"From": frm, "To": to_wa, "Body": body}
    webhook = (os.environ.get("TWILIO_WA_STATUS_WEBHOOK") or "").strip()
    if webhook:
        data["StatusCallback"] = webhook

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(
                f"{TWILIO_API_BASE}/Accounts/{sid}/Messages.json",
                auth=(sid, tok),
                data=data,
            )
        body_json = r.json()
    except Exception as e:
        return {"success": False, "error": f"http_error:{str(e)[:120]}",
                "to": to_wa, "mode": "session"}

    if r.status_code in (200, 201):
        return {
            "success": True,
            "message_sid": body_json.get("sid"),
            "status": body_json.get("status"),
            "to": to_wa,
            "mode": "session",
        }
    # Twilio error envelope
    return {
        "success": False,
        "error": body_json.get("message") or f"http_{r.status_code}",
        "error_code": body_json.get("code"),
        "to": to_wa,
        "mode": "session",
    }


async def send_whatsapp_template(
    to_phone: str,
    content_sid: Optional[str] = None,
    variables: Optional[dict[str, str]] = None,
) -> dict:
    """Template (cold-outreach safe) message. Uses Meta-approved template
    content referenced by Twilio Content SID.

    If content_sid is not passed, uses TWILIO_WA_TEMPLATE_SID from env.

    Returns same shape as send_whatsapp_session with mode="template".
    """
    import json as _json

    sid, tok, frm = _creds()
    tmpl = (content_sid or os.environ.get("TWILIO_WA_TEMPLATE_SID", "")).strip()
    missing = []
    if not sid:
        missing.append("TWILIO_ACCOUNT_SID")
    if not tok:
        missing.append("TWILIO_AUTH_TOKEN")
    if not frm:
        missing.append("TWILIO_WA_FROM_NUMBER")
    if not tmpl:
        missing.append("TWILIO_WA_TEMPLATE_SID")
    if missing:
        return {"success": False, "error": f"creds_missing: {','.join(missing)}",
                "to": to_phone, "mode": "template"}

    to_wa = _wa_addr(to_phone)
    if not to_wa:
        return {"success": False, "error": "invalid_phone", "to": to_phone,
                "mode": "template"}

    data: dict[str, Any] = {
        "From": frm,
        "To": to_wa,
        "ContentSid": tmpl,
    }
    if variables:
        data["ContentVariables"] = _json.dumps(variables)
    webhook = (os.environ.get("TWILIO_WA_STATUS_WEBHOOK") or "").strip()
    if webhook:
        data["StatusCallback"] = webhook

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(
                f"{TWILIO_API_BASE}/Accounts/{sid}/Messages.json",
                auth=(sid, tok),
                data=data,
            )
        body_json = r.json()
    except Exception as e:
        return {"success": False, "error": f"http_error:{str(e)[:120]}",
                "to": to_wa, "mode": "template"}

    if r.status_code in (200, 201):
        return {
            "success": True,
            "message_sid": body_json.get("sid"),
            "status": body_json.get("status"),
            "template_sid": tmpl,
            "to": to_wa,
            "mode": "template",
        }
    return {
        "success": False,
        "error": body_json.get("message") or f"http_{r.status_code}",
        "error_code": body_json.get("code"),
        "template_sid": tmpl,
        "to": to_wa,
        "mode": "template",
    }


async def send_whatsapp(to_phone: str, body: str,
                        content_sid: Optional[str] = None,
                        variables: Optional[dict[str, str]] = None,
                        mode: str = "auto") -> dict:
    """Smart sender: picks template vs session automatically.

    mode = "auto" (default):
      - If TWILIO_WA_TEMPLATE_SID configured OR content_sid passed → template
      - Else → session (freeform, will fail if recipient hasn't messaged first)

    Honest behavior — no fake success when Meta would reject.
    """
    if mode == "session":
        return await send_whatsapp_session(to_phone, body)
    if mode == "template":
        return await send_whatsapp_template(to_phone, content_sid, variables)
    # auto
    has_template = bool(
        content_sid or (os.environ.get("TWILIO_WA_TEMPLATE_SID") or "").strip()
    )
    if has_template:
        return await send_whatsapp_template(to_phone, content_sid, variables)
    return await send_whatsapp_session(to_phone, body)
