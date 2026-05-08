"""
SMS Kill Switch — A2P 10DLC pending (iter 282al-33: CA allowlist)
==================================================================
Twilio is returning Error 30034 (unregistered number) on SMS attempts
to US numbers until our A2P 10DLC campaign is approved. This module is
the single source of truth that lets the platform short-circuit SMS
sends and re-route them to WhatsApp without scattering toggles across
the codebase.

iter 282al-33 — **Canadian allowlist**: US A2P 10DLC applies only to US
destinations. SMS sent from our Canadian long code (+14314500004) to a
Canadian number is fully legal under CRTC CASL and will not be blocked
by Twilio. We now permit CA→CA traffic by default while keeping US
destinations blocked until our A2P campaign lands.

Behavior:
  - is_sms_disabled() reads env SMS_DISABLED ("true" by default until A2P is live)
  - is_blocked_destination(to) returns True iff the recipient falls under
    the current block policy (US numbers while A2P pending, + anything if
    SMS_DISABLED=true and allow_ca=false)
  - log_skipped_sms() inserts a record into the `sms_skipped_logs` collection
    so the founder daily brief can surface the volume of suppressed sends.
  - install_global_patch() monkey-patches twilio.rest.Client.messages.create so
    that ANY direct call site (drip_sequencer, trial_sms, email_templates,
    automations, etc.) is intercepted. WhatsApp + CA destinations pass through.

Re-enable plan (after A2P approval):
  Set SMS_DISABLED=false in /app/backend/.env and restart backend.
  Until then, CA destinations are allowed via SMS_ALLOW_CA=true (default).
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# Default to TRUE — outbound SMS stays off until the founder explicitly re-enables.
_DEFAULT_DISABLED = "true"
_DEFAULT_ALLOW_CA = "true"  # iter 282al-33 — Canadian destinations allowed by default
_SKIP_REASON = "A2P_10DLC_pending"
_PATCH_INSTALLED = False


def is_sms_disabled() -> bool:
    val = (os.environ.get("SMS_DISABLED") or _DEFAULT_DISABLED).strip().lower()
    return val in ("1", "true", "yes", "on")


def is_ca_allowed() -> bool:
    """True iff CA destinations may be sent while A2P is pending."""
    val = (os.environ.get("SMS_ALLOW_CA") or _DEFAULT_ALLOW_CA).strip().lower()
    return val in ("1", "true", "yes", "on")


def is_blocked_destination(to: str) -> bool:
    """Return True iff THIS destination should be blocked by the kill-switch.

    Policy:
      - WhatsApp → never blocked
      - If SMS_DISABLED is false → never blocked
      - If SMS_DISABLED is true AND destination is Canadian AND CA allowed → allowed
      - Otherwise → blocked
    """
    to_str = str(to or "")
    if to_str.startswith("whatsapp:"):
        return False
    if not is_sms_disabled():
        return False
    if is_ca_allowed():
        try:
            from services.ca_numbers import is_canadian_number
            if is_canadian_number(to_str):
                return False
        except Exception:  # noqa: BLE001
            pass
    return True


def skip_reason() -> str:
    return _SKIP_REASON


async def log_skipped_sms(
    to: str,
    message: str,
    tenant_id: Optional[str] = None,
    caller: str = "unknown",
    redirected_to: Optional[str] = None,
) -> None:
    """Persist a skipped-SMS record to MongoDB. Best-effort — never raises."""
    try:
        from shared.memory_tiers import _get_db
        db = _get_db()
        if db is None:
            return
        await db.sms_skipped_logs.insert_one({
            "type": "sms_skipped",
            "reason": _SKIP_REASON,
            "tenant_id": tenant_id,
            "caller": caller,
            "to": to,
            "message": (message or "")[:500],
            "redirected_to": redirected_to,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[sms_killswitch] Failed to log skipped SMS: {e}")


def _log_skipped_sms_sync(to: str, message: str, caller: str) -> None:
    """Sync best-effort log used from inside the monkey-patched Twilio client."""
    try:
        from shared.memory_tiers import _get_db
        db = _get_db()
        if db is None:
            return
        # Motor exposes async-only methods; use pymongo client for the sync path.
        from motor.motor_asyncio import AsyncIOMotorDatabase
        if isinstance(db, AsyncIOMotorDatabase):
            client = db.client
            sync_db = client.delegate[db.name]
            sync_db.sms_skipped_logs.insert_one({
                "type": "sms_skipped",
                "reason": _SKIP_REASON,
                "caller": caller,
                "to": to,
                "message": (message or "")[:500],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
    except Exception as e:  # noqa: BLE001
        logger.debug(f"[sms_killswitch] sync log skipped: {e}")


class _StubMessage:
    """Mimics twilio.rest.api.v2010.account.message.MessageInstance for skipped sends."""

    def __init__(self, to: str):
        self.sid = "SKIPPED_A2P_PENDING"
        self.status = "sms_skipped_a2p_pending"
        self.to = to
        self.error_code = None
        self.error_message = None


def install_global_patch() -> None:
    """Monkey-patch twilio.rest.Client so direct SMS sends are blocked globally.

    WhatsApp messages (To/from starts with 'whatsapp:') pass through unmodified.
    Idempotent — safe to call multiple times.
    """
    global _PATCH_INSTALLED
    if _PATCH_INSTALLED:
        return
    try:
        from twilio.rest.api.v2010.account.message import MessageList
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[sms_killswitch] Twilio SDK not available, skipping patch: {e}")
        return

    original_create = MessageList.create

    def _patched_create(self, *args, **kwargs):
        # Fast path: SMS fully enabled → bypass gate.
        if not is_sms_disabled():
            return original_create(self, *args, **kwargs)
        to = kwargs.get("to") or (args[0] if args else "") or ""
        from_ = kwargs.get("from_") or ""
        # iter 282al-33 — Canadian destinations + WhatsApp pass through.
        if not is_blocked_destination(to) and not str(from_).startswith("whatsapp:"):
            return original_create(self, *args, **kwargs)
        # WhatsApp from-side guard (belt-and-braces)
        if str(to).startswith("whatsapp:") or str(from_).startswith("whatsapp:"):
            return original_create(self, *args, **kwargs)
        body = kwargs.get("body", "")
        logger.info(
            f"[sms_killswitch] BLOCKED direct SMS to={to} (A2P_10DLC_pending) — "
            f"caller bypassed wrapper. Logging to sms_skipped_logs."
        )
        _log_skipped_sms_sync(to=str(to), message=str(body), caller="twilio_client_direct")
        return _StubMessage(to=str(to))

    MessageList.create = _patched_create  # type: ignore[assignment]
    _PATCH_INSTALLED = True
    logger.info("[sms_killswitch] Global Twilio SMS kill switch installed")
    print("[sms_killswitch] Global Twilio SMS kill switch installed", flush=True)


# ─── Auto-install on import (idempotent) ─────────────────────────────────
# Even if server.py's startup_event misses the hook (hot reload, etc.), the
# patch is applied as soon as anything imports sms_killswitch.
if is_sms_disabled():
    try:
        install_global_patch()
    except Exception as _e:  # noqa: BLE001
        logger.warning(f"[sms_killswitch] auto-install failed: {_e}")

