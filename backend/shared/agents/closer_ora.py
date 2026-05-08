"""
Closer ORA 💰 — Converts non-responsive leads.
Receives leads from Follow-up after 7+ days of silence and runs a more
direct, urgency-heavy sequence: competitor angle → case study email → voice call → final offer.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from services.agents import AuremAgent

logger = logging.getLogger(__name__)


CLOSER_SEQUENCE = [
    {"step": 1, "channel": "whatsapp", "template": "closer_competitor_angle"},
    {"step": 2, "channel": "email",    "template": "closer_case_study"},
    {"step": 3, "channel": "call",     "template": "closer_voice_pitch"},
    {"step": 4, "channel": "sms",      "template": "closer_50_off_final"},
]


class CloserORA(AuremAgent):
    AGENT_ID = "closer_ora"
    AGENT_NAME = "Closer ORA"
    AGENT_EMOJI = "💰"
    AGENT_JOB = "Convert non-responsive leads"

    async def run_cycle(self) -> Dict[str, Any]:
        if self._paused or self.db is None:
            return {"skipped": True}

        converted = 0
        attempted = 0
        cold_skipped = 0
        now = datetime.now(timezone.utc)

        cursor = self.db.campaign_leads.find(
            {"stage": "handed_to_closer", "status": {"$nin": ["do_not_contact", "closed_won"]}},
            {"_id": 0},
        ).limit(50)
        leads = await cursor.to_list(length=50)
        self.mark_task(f"Closing pass on {len(leads)} stuck leads")

        for lead in leads:
            steps_done = lead.get("closer_steps_done", [])
            # Pick next step
            next_step = None
            for step in CLOSER_SEQUENCE:
                if step["template"] not in steps_done:
                    next_step = step
                    break

            if not next_step:
                # All closer steps exhausted — mark cold, notify Hunter
                await self.db.campaign_leads.update_one(
                    {"lead_id": lead["lead_id"]},
                    {"$set": {"stage": "cold", "cold_at": now.isoformat()}},
                )
                await self.notify(
                    "hunter_ora",
                    "skip_area",
                    {"city": lead.get("city"), "industry": lead.get("category"),
                     "reason": "closer_exhausted"},
                )
                cold_skipped += 1
                continue

            gating = lead.get("channel_gating") or {}
            if not gating.get(next_step["channel"], True):
                steps_done.append(next_step["template"])  # skip gated
                await self.db.campaign_leads.update_one(
                    {"lead_id": lead["lead_id"]},
                    {"$set": {"closer_steps_done": steps_done}},
                )
                continue

            try:
                await self._send_closer_step(lead, next_step)
                steps_done.append(next_step["template"])
                await self.db.campaign_leads.update_one(
                    {"lead_id": lead["lead_id"]},
                    {"$set": {"closer_steps_done": steps_done, "last_closer_at": now.isoformat()}},
                )
                attempted += 1
            except Exception as e:
                logger.warning(f"[CloserORA] step failed for {lead.get('lead_id')}: {e}")

            # Check if this lead converted since last cycle
            if lead.get("stage") == "closed_won":
                converted += 1

        stats = {"closer_attempts": attempted, "converted": converted, "cold_skipped": cold_skipped}
        self._today_stats = stats
        await self.broadcast("daily_complete", {"agent": self.AGENT_ID, "stats": stats})
        return stats

    async def _send_closer_step(self, lead: Dict[str, Any], step: Dict[str, Any]):
        """Closer messaging — more direct tone than Follow-up."""
        ch = step["channel"]
        biz = lead.get("business_name", "your business")
        city = lead.get("city", "your area")
        industry = lead.get("category", "your industry")

        messages = {
            "closer_competitor_angle":
                f"Hi {biz} — your competitor in {city} just joined AUREM. "
                f"Don't want you to fall behind. 30 seconds to show you?",
            "closer_case_study":
                f"<p>Auto shop in Brampton got <strong>47 new customers in 30 days</strong> with AUREM. "
                f"Same could happen for {biz}. <a href='https://aurem.live/case-studies'>Read how →</a></p>",
            "closer_voice_pitch":
                f"AUREM voice call scheduled",
            "closer_50_off_final":
                f"Last call for {biz}: 50% off, today only. https://aurem.live/offer-50",
        }
        body = messages.get(step["template"], "")

        if ch == "whatsapp":
            try:
                from services.twilio_service import send_whatsapp_message
                from services.casl_compliance import wrap_whatsapp
                phone = lead.get("phone")
                if phone:
                    await send_whatsapp_message(phone, wrap_whatsapp(body))
            except Exception:
                pass
        elif ch == "email":
            import resend, os
            email = lead.get("email")
            if email:
                from services.casl_compliance import wrap_email_html
                resend.api_key = os.environ.get("RESEND_API_KEY", "")
                try:
                    resend.Emails.send({
                        "from": "ORA <ora@aurem.live>",
                        "to": [email],
                        "subject": f"{biz} — {industry} case study",
                        "html": wrap_email_html(body, lead_id=lead["lead_id"]),
                    })
                except Exception:
                    pass
        elif ch == "sms":
            import os, httpx
            from services.casl_compliance import wrap_sms
            phone = lead.get("phone")
            sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
            tok = os.environ.get("TWILIO_AUTH_TOKEN", "")
            fn  = os.environ.get("TWILIO_PHONE_NUMBER", "")
            if phone and sid and tok and fn:
                async with httpx.AsyncClient(timeout=15) as c:
                    await c.post(
                        f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
                        auth=(sid, tok),
                        data={"From": fn, "To": phone, "Body": wrap_sms(body)},
                    )
        elif ch == "call":
            try:
                from services.flame_auto_dialer import trigger_call_for_lead
                await trigger_call_for_lead(self.db, lead["lead_id"], reason="closer_pitch")
            except Exception:
                pass
