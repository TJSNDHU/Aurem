"""
Ripple WhatsApp Fallback Adapter
================================
Third-tier WhatsApp fallback via Meta Cloud API (adapted from Keshav Sharma's
ripple-agent/ripple/channels/whatsapp.py).

AUREM fallback chain:
    1. Tenant Meta Cloud API (per-tenant custom creds, in WhatsAppEngine._send_meta)
    2. WHAPI.Cloud personal number (global key, in WhatsAppEngine._send_whapi_global)
    3. THIS: Ripple Meta Cloud fallback (global WHATSAPP_ACCESS_TOKEN env)

Credit: github.com/Keshavsharma-code/ripple-agent
"""
from __future__ import annotations

import json
import logging
import os
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class RippleDeliveryResult:
    attempted: bool
    ok: bool
    detail: str
    preview: Dict[str, Any] = field(default_factory=dict)
    provider: str = "ripple-meta-cloud"


def ripple_whatsapp_configured() -> bool:
    """Returns True if Ripple's Meta Cloud fallback creds are available."""
    return bool(
        os.getenv("RIPPLE_WHATSAPP_ACCESS_TOKEN") or os.getenv("WHATSAPP_ACCESS_TOKEN")
    ) and bool(
        os.getenv("RIPPLE_WHATSAPP_PHONE_NUMBER_ID") or os.getenv("WHATSAPP_PHONE_NUMBER_ID")
    )


def build_outbound(to_number: str, text: str) -> Dict[str, Any]:
    """Builds a WhatsApp Cloud API outbound payload (from ripple base)."""
    return {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": text},
    }


def send_via_ripple(to_number: str, text: str, timeout: int = 15) -> RippleDeliveryResult:
    """
    Send a WhatsApp message via the Meta Cloud API using Ripple's proven pattern.

    Used as AUREM's 3rd-tier fallback when Twilio & WHAPI both fail/unapproved.
    """
    preview = build_outbound(to_number, text)

    if not ripple_whatsapp_configured():
        return RippleDeliveryResult(
            attempted=False,
            ok=False,
            detail="Ripple Meta Cloud fallback not configured (set RIPPLE_WHATSAPP_ACCESS_TOKEN + PHONE_NUMBER_ID).",
            preview=preview,
        )

    access_token = os.getenv("RIPPLE_WHATSAPP_ACCESS_TOKEN") or os.getenv(
        "WHATSAPP_ACCESS_TOKEN"
    )
    phone_id = os.getenv("RIPPLE_WHATSAPP_PHONE_NUMBER_ID") or os.getenv(
        "WHATSAPP_PHONE_NUMBER_ID"
    )

    url = f"https://graph.facebook.com/v20.0/{phone_id}/messages"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    req = urllib.request.Request(
        url, data=json.dumps(preview).encode("utf-8"), headers=headers, method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            logger.info(
                f"[RippleWA] sent → {to_number} id={body.get('messages',[{}])[0].get('id','?')}"
            )
            return RippleDeliveryResult(
                attempted=True, ok=True, detail="Sent via Ripple Meta Cloud.", preview=body
            )
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        logger.warning(f"[RippleWA] HTTP {e.code}: {err_body[:200]}")
        return RippleDeliveryResult(
            attempted=True,
            ok=False,
            detail=f"HTTP {e.code}: {err_body[:200]}",
            preview=preview,
        )
    except Exception as e:
        logger.warning(f"[RippleWA] error: {e}")
        return RippleDeliveryResult(
            attempted=True, ok=False, detail=f"Error: {e}", preview=preview
        )


def verify_webhook(query: Dict[str, Any]) -> Optional[tuple]:
    """
    Handles Meta's GET verification challenge for the Ripple fallback webhook.
    Compatible with both single-value and list query params.
    """
    def _get(k):
        v = query.get(k, "")
        if isinstance(v, list):
            return v[0] if v else ""
        return v

    mode = _get("hub.mode")
    token = _get("hub.verify_token")
    challenge = _get("hub.challenge")

    expected = os.getenv("RIPPLE_WHATSAPP_VERIFY_TOKEN") or os.getenv(
        "WHATSAPP_VERIFY_TOKEN"
    )
    if expected and mode == "subscribe" and token == expected:
        return (200, challenge, "text/plain")
    return (403, "Forbidden", "text/plain")


def parse_inbound(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Parse an inbound Meta Cloud webhook payload into a normalized envelope."""
    try:
        entry = payload["entry"][0]
        change = entry["changes"][0]
        value = change["value"]
        message = value["messages"][0]
        return {
            "channel": "whatsapp",
            "provider": "ripple-meta-cloud",
            "user_id": message["from"],
            "thread_id": message["from"],
            "text": message.get("text", {}).get("body", ""),
            "metadata": payload,
        }
    except (KeyError, IndexError):
        return None
