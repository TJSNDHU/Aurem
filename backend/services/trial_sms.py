"""Trial-link SMS auto-send (iter 289.7).

Fires from `/api/agents/board/voice-log` when a Retell call ends without
opt-out. Sends the AUREM 7-day trial link + demo tutorial URL via Twilio.

Idempotency: same `call_id` is never SMS'd twice.
"""
from __future__ import annotations

import os
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("trial-sms")

TRIAL_LANDING = os.environ.get("AUREM_TRIAL_URL", "https://aurem.live")
DEMO_URL = os.environ.get("AUREM_DEMO_URL", "https://aurem.live/demo")

_BOOKED_TEMPLATE = (
    "Hi! Ora from AUREM here — thanks for chatting.\n"
    "Start your free 7-day trial (no card needed): {trial}\n"
    "Full setup tutorial + demo video: {demo}\n"
    "Your website auto-repair scan begins the moment you sign up.\n"
    "Reply STOP to opt out."
)

_GENERAL_TEMPLATE = (
    "Hi from AUREM — the world's first Automation Intelligence.\n"
    "Try us free for 7 days (no card): {trial}\n"
    "2-min demo + setup walkthrough: {demo}\n"
    "Reply STOP to opt out."
)


def _twilio_ready() -> bool:
    return all(os.environ.get(k, "").strip()
               for k in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_PHONE_NUMBER"))


async def send_trial_sms(db, *, lead_number: str, call_id: str, booked: bool) -> dict:
    """Send the trial link to a lead. Idempotent on (call_id).

    Returns: {sent: bool, sid: str|None, reason: str|None}
    """
    if not lead_number or not lead_number.strip():
        return {"sent": False, "reason": "no lead number"}
    if not _twilio_ready():
        return {"sent": False, "reason": "twilio env missing"}

    # Idempotency check
    if db is not None and call_id:
        existing = await db.voice_call_logs.find_one(
            {"call_id": call_id, "trial_link_sent": True},
            {"_id": 1},
        )
        if existing:
            return {"sent": False, "reason": "already sent for this call"}

    # DNC guard — never SMS opted-out numbers (defense-in-depth)
    if db is not None:
        dnc = await db.dnc_list.find_one({"phone": lead_number}, {"_id": 1})
        if dnc:
            return {"sent": False, "reason": "lead in DNC list"}

    template = _BOOKED_TEMPLATE if booked else _GENERAL_TEMPLATE
    body = template.format(trial=TRIAL_LANDING, demo=DEMO_URL)

    try:
        from twilio.rest import Client
        client = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])
        msg = client.messages.create(
            from_=os.environ["TWILIO_PHONE_NUMBER"],
            to=lead_number,
            body=body,
        )
        sid = getattr(msg, "sid", None)
        logger.info(f"[trial-sms] sent to {lead_number} sid={sid} booked={booked}")

        # Mark on voice_call_logs
        if db is not None and call_id:
            await db.voice_call_logs.update_one(
                {"call_id": call_id},
                {"$set": {
                    "trial_link_sent": True,
                    "trial_link_sent_at": datetime.now(timezone.utc).isoformat(),
                    "trial_link_sid": sid,
                    "trial_link_to": lead_number,
                }},
            )
            # Also mirror into a sent_trial_links collection for easy reporting
            await db.sent_trial_links.insert_one({
                "call_id": call_id,
                "lead_number": lead_number,
                "sid": sid,
                "booked": booked,
                "trial_url": TRIAL_LANDING,
                "demo_url": DEMO_URL,
                "sent_at": datetime.now(timezone.utc).isoformat(),
            })

        # Boardroom Ledger: SMS cost on closer_ora (this is the conversion handoff)
        try:
            from services.agent_ledger import record_cost
            await record_cost(db, "closer_ora", "sms_twilio", 1,
                              meta={"call_id": call_id, "kind": "trial_link", "lead": lead_number})
        except Exception:
            pass

        return {"sent": True, "sid": sid, "reason": None}
    except Exception as e:
        logger.warning(f"[trial-sms] send failed for {lead_number}: {e}")
        return {"sent": False, "reason": str(e)[:200]}
