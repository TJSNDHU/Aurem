"""
SMS Engine — Unified SMS Sending Layer (Twilio)
================================================
Primary: Tenant's own Twilio creds (from DB)
Fallback: Global TWILIO_* env vars
From: TWILIO_PHONE_NUMBER

Usage:
    from services.sms_engine import SMSEngine
    engine = SMSEngine(db)
    result = await engine.send_message(tenant_id, "+16134000000", "Hello!")
"""

import os
import logging
from datetime import datetime, timezone
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class SMSEngine:
    def __init__(self, db):
        self.db = db

    async def _get_creds(self, tenant_id: str) -> Dict:
        """Get Twilio creds — tenant-specific first, then global fallback."""
        try:
            doc = await self.db.user_integrations.find_one(
                {"tenant_id": tenant_id},
                {"_id": 0, "sms_config": 1}
            )
            if doc:
                sc = doc.get("sms_config", {})
                if sc.get("twilio_sid") and sc.get("twilio_token") and sc.get("twilio_phone"):
                    return {
                        "sid": sc["twilio_sid"],
                        "token": sc["twilio_token"],
                        "phone": sc["twilio_phone"],
                        "source": "tenant",
                    }
        except Exception:
            pass

        sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
        token = os.environ.get("TWILIO_AUTH_TOKEN", "")
        phone = os.environ.get("TWILIO_PHONE_NUMBER", "")
        if sid and token and phone:
            return {"sid": sid, "token": token, "phone": phone, "source": "global"}

        return {}

    def _format_phone(self, phone: str) -> str:
        """Ensure E.164 format."""
        cleaned = "".join(c for c in phone if c.isdigit() or c == "+")
        if not cleaned.startswith("+"):
            if len(cleaned) == 10:
                cleaned = "+1" + cleaned
            elif len(cleaned) == 11 and cleaned.startswith("1"):
                cleaned = "+" + cleaned
            else:
                cleaned = "+" + cleaned
        return cleaned

    async def send_message(self, tenant_id: str, to: str, message: str) -> Dict:
        """Send an SMS via Twilio. Uses tenant creds → global fallback.

        KILL SWITCH (A2P 10DLC pending): when SMS_DISABLED=true (default), the
        send is short-circuited, logged to `sms_skipped_logs`, and re-routed
        through WhatsApp so the customer still gets the message.
        """
        from services.sms_killswitch import is_sms_disabled, log_skipped_sms

        to_formatted = self._format_phone(to)

        if is_sms_disabled():
            logger.info(
                f"[sms_killswitch] SMS suppressed (engine) → routing to WhatsApp "
                f"(tenant={tenant_id}, to={to_formatted})"
            )
            try:
                from shared.providers.twilio import send_whatsapp_message
                wa_result = await send_whatsapp_message(to_formatted, message)
            except Exception as e:
                wa_result = {"success": False, "error": f"whatsapp_fallback_failed: {e}"}

            await log_skipped_sms(
                to=to_formatted,
                message=message,
                tenant_id=tenant_id,
                caller="services.sms_engine.SMSEngine.send_message",
                redirected_to="whatsapp" if wa_result.get("success") else None,
            )
            await self._log_sms(
                tenant_id, to_formatted, message,
                wa_result.get("message_sid", ""),
                bool(wa_result.get("success")),
                error=wa_result.get("error", "") or "sms_skipped_a2p_pending",
            )
            wa_result.setdefault("engine", "whatsapp_fallback")
            wa_result["sms_skipped"] = True
            wa_result["skip_reason"] = "A2P_10DLC_pending"
            return wa_result

        creds = await self._get_creds(tenant_id)
        if not creds:
            return {"success": False, "error": "Twilio not configured", "engine": "sms"}

        try:
            from twilio.rest import Client
            client = Client(creds["sid"], creds["token"])

            msg = client.messages.create(
                body=message,
                from_=creds["phone"],
                to=to_formatted,
            )

            await self._log_sms(tenant_id, to_formatted, message, msg.sid, True)

            logger.info(f"[SMS] Sent to {to_formatted} via Twilio ({creds['source']}), SID: {msg.sid}")
            return {
                "success": True,
                "message_sid": msg.sid,
                "status": msg.status,
                "engine": "twilio",
                "source": creds["source"],
            }

        except Exception as e:
            logger.error(f"[SMS] Send failed: {e}")
            await self._log_sms(tenant_id, to_formatted, message, "", False, str(e))
            return {"success": False, "error": str(e), "engine": "twilio"}

    async def _log_sms(self, tenant_id: str, to: str, message: str, sid: str, success: bool, error: str = ""):
        """Log SMS send and update usage counter."""
        try:
            await self.db.sms_logs.insert_one({
                "tenant_id": tenant_id,
                "to": to,
                "message": message[:500],
                "message_sid": sid,
                "success": success,
                "error": error,
                "engine": "twilio",
                "sent_at": datetime.now(timezone.utc).isoformat(),
            })
            if success:
                await self.db.user_integrations.update_one(
                    {"tenant_id": tenant_id},
                    {
                        "$inc": {"sms_sent": 1},
                        "$set": {"last_sms_at": datetime.now(timezone.utc).isoformat()},
                    }
                )
        except Exception as e:
            logger.warning(f"[SMS] Log failed: {e}")
