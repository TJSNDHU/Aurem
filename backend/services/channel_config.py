"""
channel_config.py — Single source of truth for outbound channel availability.

Problem this solves:
  Different routers/services read Twilio/WhatsApp env vars under inconsistent
  names (TWILIO_WHATSAPP_FROM vs TWILIO_WHATSAPP_NUMBER vs TWILIO_FROM_NUMBER).
  Result: ops-status flags channels "not_connected" even after the user has
  added valid credentials.

Rules:
  - Twilio SMS:      needs ACCOUNT_SID + AUTH_TOKEN + a plain "from" number
                     (TWILIO_PHONE_NUMBER, fallback TWILIO_FROM_NUMBER).
  - Twilio Voice:    same credentials as SMS — if SMS is configured, Voice is too.
  - Twilio WhatsApp: ACCOUNT_SID + AUTH_TOKEN + a WhatsApp-prefixed number.
                     Reads any of:
                       TWILIO_WHATSAPP_NUMBER  (canonical)
                       TWILIO_WHATSAPP_FROM
                       WHATSAPP_FROM
                     If none explicit, we assume the user's TWILIO_PHONE_NUMBER
                     is WhatsApp-approved and auto-prefix with "whatsapp:".
                     (Operator can disable this by setting
                     TWILIO_WHATSAPP_AUTODERIVE=0.)
  - Meta WhatsApp:   WHATSAPP_ACCESS_TOKEN + WHATSAPP_PHONE_NUMBER_ID
                     (separate Meta Cloud path, not Twilio).

Public API:
  twilio_status()     → {"configured": bool, "sms_from": str|None,
                          "whatsapp_from": str|None, "reason": str}
  stripe_status()     → {"configured": bool, "mode": "live"|"test"|None, "key_preview": str}
  meta_whatsapp_status() → {"configured": bool, "phone_id": str|None}
"""
from __future__ import annotations
import os
from typing import Optional, Dict, Any


def _env(name: str) -> str:
    return (os.environ.get(name) or "").strip()


# ─── Twilio ──────────────────────────────────────────────────────────

def get_twilio_credentials() -> Dict[str, str]:
    return {
        "sid": _env("TWILIO_ACCOUNT_SID"),
        "token": _env("TWILIO_AUTH_TOKEN"),
    }


def get_twilio_sms_from() -> Optional[str]:
    """Plain E.164 number for SMS/Voice."""
    num = _env("TWILIO_PHONE_NUMBER") or _env("TWILIO_FROM_NUMBER")
    return num or None


def get_twilio_whatsapp_from() -> Optional[str]:
    """WhatsApp-prefixed Twilio sender ('whatsapp:+14155238886')."""
    explicit = (
        _env("TWILIO_WHATSAPP_NUMBER")
        or _env("TWILIO_WHATSAPP_FROM")
        or _env("WHATSAPP_FROM")
    )
    if explicit:
        return explicit if explicit.startswith("whatsapp:") else f"whatsapp:{explicit}"

    # Auto-derive from the SMS number if the operator hasn't opted out.
    if _env("TWILIO_WHATSAPP_AUTODERIVE").lower() in ("0", "false", "no"):
        return None
    sms_from = get_twilio_sms_from()
    if sms_from:
        return sms_from if sms_from.startswith("whatsapp:") else f"whatsapp:{sms_from}"
    return None


def twilio_status() -> Dict[str, Any]:
    creds = get_twilio_credentials()
    sms_from = get_twilio_sms_from()
    wa_from = get_twilio_whatsapp_from()
    missing = []
    if not creds["sid"]:
        missing.append("TWILIO_ACCOUNT_SID")
    if not creds["token"]:
        missing.append("TWILIO_AUTH_TOKEN")
    if not sms_from:
        missing.append("TWILIO_PHONE_NUMBER")
    configured = not missing
    return {
        "configured": configured,
        "sms_configured": configured,
        "voice_configured": configured,
        "whatsapp_configured": configured and bool(wa_from),
        "sms_from": sms_from,
        "whatsapp_from": wa_from,
        "missing": missing,
        "reason": "ok" if configured else f"Missing env: {', '.join(missing)}",
    }


# ─── Stripe ──────────────────────────────────────────────────────────

def get_stripe_api_key() -> Optional[str]:
    """Resolve the Stripe API key with a safe test/live mode toggle.

    iter 279: adds a STRIPE_MODE env var that can be set to 'test' or 'live'
    to pick between STRIPE_SECRET_KEY_TEST and STRIPE_SECRET_KEY (live).
    This lets demos use test-mode keys safely without real charges while
    production keeps the canonical live key. If STRIPE_MODE is unset, we
    fall back to the existing single-key behaviour.
    """
    mode = (_env("STRIPE_MODE") or "").lower().strip()

    if mode == "test":
        test_key = _env("STRIPE_SECRET_KEY_TEST") or _env("STRIPE_TEST_SECRET_KEY")
        if test_key:
            return test_key
        # fall through so callers still get *some* key rather than None

    if mode == "live":
        live_key = _env("STRIPE_SECRET_KEY") or _env("STRIPE_SECRET_KEY")
        if live_key:
            return live_key

    # Default / legacy single-key path
    return _env("STRIPE_SECRET_KEY") or _env("STRIPE_SECRET_KEY") or None


def stripe_status() -> Dict[str, Any]:
    key = get_stripe_api_key()
    requested_mode = (_env("STRIPE_MODE") or "").lower().strip() or None
    if not key:
        return {
            "configured": False,
            "mode": None,
            "requested_mode": requested_mode,
            "key_preview": "",
            "reason": "No Stripe key set (STRIPE_SECRET_KEY or STRIPE_API_KEY)",
        }
    actual_mode = (
        "live" if key.startswith("sk_live_")
        else ("test" if key.startswith("sk_test_") else "unknown")
    )
    return {
        "configured": True,
        "mode": actual_mode,
        "requested_mode": requested_mode,
        "key_preview": f"{key[:10]}…{key[-4:]}" if len(key) > 14 else "set",
        "reason": f"Stripe {actual_mode} key loaded"
                  + (f" (requested {requested_mode})" if requested_mode else ""),
    }


# ─── Meta WhatsApp Cloud (alternative to Twilio WhatsApp) ────────────

def meta_whatsapp_status() -> Dict[str, Any]:
    token = _env("WHATSAPP_ACCESS_TOKEN") or _env("META_WHATSAPP_TOKEN") or _env("WHATSAPP_TOKEN")
    phone_id = _env("WHATSAPP_PHONE_NUMBER_ID") or _env("META_WHATSAPP_PHONE_ID")
    configured = bool(token and phone_id)
    return {
        "configured": configured,
        "token_present": bool(token),
        "phone_id": phone_id or None,
        "reason": "ok" if configured else "Missing WHATSAPP_ACCESS_TOKEN and/or WHATSAPP_PHONE_NUMBER_ID",
    }


# ─── Unified snapshot ────────────────────────────────────────────────

def all_channels_status() -> Dict[str, Any]:
    t = twilio_status()
    m = meta_whatsapp_status()
    s = stripe_status()
    whatsapp_ready = t["whatsapp_configured"] or m["configured"]
    whatsapp_mode = (
        "twilio" if t["whatsapp_configured"] else ("meta_cloud" if m["configured"] else None)
    )
    return {
        "twilio": t,
        "meta_whatsapp": m,
        "stripe": s,
        "whatsapp": {
            "configured": whatsapp_ready,
            "mode": whatsapp_mode,
            "twilio_from": t["whatsapp_from"],
            "meta_phone_id": m["phone_id"],
        },
    }
