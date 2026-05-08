"""
Voice Engine — Outbound AI Voice Calls (Twilio)
=================================================
Makes outbound calls with dynamic TwiML scripts.
ORA speaks to leads, handles keypress responses.

Usage:
    from services.voice_engine import VoiceEngine
    engine = VoiceEngine(db)
    result = await engine.make_call(tenant_id, "+16134000000", "lead-001")
"""

import os
import logging
from datetime import datetime, timezone
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class VoiceEngine:
    def __init__(self, db):
        self.db = db

    def _get_creds(self) -> Dict:
        """Get Twilio creds from env."""
        sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
        token = os.environ.get("TWILIO_AUTH_TOKEN", "")
        phone = os.environ.get("TWILIO_PHONE_NUMBER", "")
        if sid and token and phone:
            return {"sid": sid, "token": token, "phone": phone}
        return {}

    def _format_phone(self, phone: str) -> str:
        cleaned = "".join(c for c in phone if c.isdigit() or c == "+")
        if not cleaned.startswith("+"):
            if len(cleaned) == 10:
                cleaned = "+1" + cleaned
            elif len(cleaned) == 11 and cleaned.startswith("1"):
                cleaned = "+" + cleaned
            else:
                cleaned = "+" + cleaned
        return cleaned

    def _build_twiml(self, lead: Dict, callback_url: str = "") -> str:
        """Build dynamic TwiML script from lead data."""
        name = lead.get("contact_name") or lead.get("first_name") or "there"
        website = lead.get("website_url", "your website")
        issues = lead.get("issues_count", 0)
        score = lead.get("score", 50)
        lead_id = lead.get("lead_id", "")

        script = (
            f"Hi {name}, this is O R A from AUREM. "
            f"I scanned {website} and found {issues} issues "
            f"affecting your Google ranking. Your site scored {score} out of 100. "
            f"I've already prepared the fixes. "
            f"Press 1 to hear more about the report, or press 2 to opt out."
        )

        # TwiML with Gather for keypress
        if callback_url:
            twiml = (
                f'<Response>'
                f'<Gather numDigits="1" action="{callback_url}/api/voice/keypress/{lead_id}" method="POST" timeout="10">'
                f'<Say voice="Polly.Joanna">{script}</Say>'
                f'</Gather>'
                f'<Say voice="Polly.Joanna">We didn\'t receive a response. Have a great day!</Say>'
                f'</Response>'
            )
        else:
            twiml = f'<Response><Say voice="Polly.Joanna">{script}</Say></Response>'

        return twiml

    async def make_call(self, tenant_id: str, to_number: str, lead_id: str = "", custom_script: str = "") -> Dict:
        """
        Make an outbound voice call via Twilio.
        If lead_id is provided, fetches lead data for personalized script.
        """
        creds = self._get_creds()
        if not creds:
            return {"success": False, "error": "Twilio not configured", "engine": "voice"}

        to_formatted = self._format_phone(to_number)

        # Fetch lead data if lead_id provided
        lead = {}
        if lead_id:
            lead = await self.db.campaign_leads.find_one({"lead_id": lead_id}, {"_id": 0}) or {}
            if not lead:
                lead = await self.db.envoy_outreach.find_one({"lead_id": lead_id}, {"_id": 0}) or {}

        # Build TwiML
        callback_url = os.environ.get("REACT_APP_BACKEND_URL", "")
        if custom_script:
            twiml = f'<Response><Say voice="Polly.Joanna">{custom_script}</Say></Response>'
        else:
            twiml = self._build_twiml(lead, callback_url)

        try:
            from twilio.rest import Client
            client = Client(creds["sid"], creds["token"])

            call = client.calls.create(
                twiml=twiml,
                to=to_formatted,
                from_=creds["phone"],
            )

            await self._log_call(tenant_id, to_formatted, lead_id, call.sid, "initiated")

            logger.info(f"[VOICE] Call initiated to {to_formatted}, SID: {call.sid}")
            return {
                "success": True,
                "call_sid": call.sid,
                "status": call.status,
                "engine": "twilio_voice",
                "to": to_formatted,
            }

        except Exception as e:
            logger.error(f"[VOICE] Call failed: {e}")
            await self._log_call(tenant_id, to_formatted, lead_id, "", "failed", str(e))
            return {"success": False, "error": str(e), "engine": "twilio_voice"}

    async def _log_call(self, tenant_id: str, to: str, lead_id: str, sid: str, status: str, error: str = ""):
        """Log call and update usage."""
        try:
            await self.db.call_logs.insert_one({
                "tenant_id": tenant_id,
                "to": to,
                "lead_id": lead_id,
                "call_sid": sid,
                "status": status,
                "error": error,
                "engine": "twilio_voice",
                "called_at": datetime.now(timezone.utc).isoformat(),
            })
            if status == "initiated":
                await self.db.user_integrations.update_one(
                    {"tenant_id": tenant_id},
                    {
                        "$inc": {"voice_calls": 1},
                        "$set": {"last_voice_call_at": datetime.now(timezone.utc).isoformat()},
                    }
                )
        except Exception as e:
            logger.warning(f"[VOICE] Log failed: {e}")
