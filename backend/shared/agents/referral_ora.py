"""
Referral ORA 🤝 — Handles customer referrals.
Triggered when an existing client submits a referral via dashboard,
replies with referral info, or the CRM `referrals` collection gets a new doc.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List

from services.agents import AuremAgent

logger = logging.getLogger(__name__)


REFERRAL_SEQUENCE = [
    {"days_after": 0, "channel": "whatsapp", "template": "referral_warm_intro"},
    {"days_after": 3, "channel": "email",    "template": "referral_success_story"},
    {"days_after": 7, "channel": "whatsapp", "template": "referral_discount_offer"},
]


class ReferralORA(AuremAgent):
    AGENT_ID = "referral_ora"
    AGENT_NAME = "Referral ORA"
    AGENT_EMOJI = "🤝"
    AGENT_JOB = "Handle customer references"

    async def run_cycle(self) -> Dict[str, Any]:
        if self._paused or self.db is None:
            return {"skipped": True}

        now = datetime.now(timezone.utc)
        contacted = 0

        # Pull all referral docs where processing not complete
        cursor = self.db.referrals.find(
            {"status": {"$nin": ["converted", "do_not_contact", "complete"]}},
            {"_id": 0},
        ).limit(100)
        referrals = await cursor.to_list(length=100)
        self.mark_task(f"Referral pass ({len(referrals)} pending)")

        for ref in referrals:
            created_at_str = ref.get("created_at")
            if not created_at_str:
                continue
            try:
                created = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
            except Exception:
                continue

            days_old = (now - created).days
            steps_done = ref.get("steps_done", [])

            for step in REFERRAL_SEQUENCE:
                if days_old >= step["days_after"] and step["template"] not in steps_done:
                    try:
                        await self._send_referral_step(ref, step)
                        steps_done.append(step["template"])
                        await self.db.referrals.update_one(
                            {"referral_id": ref["referral_id"]},
                            {"$set": {"steps_done": steps_done, "last_touch_at": now.isoformat()}},
                        )
                        contacted += 1
                    except Exception as e:
                        logger.warning(f"[ReferralORA] step failed: {e}")
                    break  # one step per pass

        # Notify referrers when their referral was contacted
        await self._notify_referrers_of_contacts()

        stats = {"referrals_contacted": contacted, "pending": len(referrals)}
        self._today_stats = stats
        await self.broadcast("daily_complete", {"agent": self.AGENT_ID, "stats": stats})
        return stats

    async def _send_referral_step(self, ref: Dict[str, Any], step: Dict[str, Any]):
        name = ref.get("referral_name") or "there"
        referrer = ref.get("referred_by") or "a client"
        city = ref.get("city") or "your area"

        messages = {
            "referral_warm_intro":
                f"Hi {name}! Your friend {referrer} from {city} suggested I reach out. "
                f"They love AUREM and thought you would too. 30 seconds to show you?",
            "referral_success_story":
                f"<p>{referrer} has been with AUREM and seen real results. "
                f"We'd love to do the same for you — <a href='https://aurem.live/referral'>here's how →</a></p>",
            "referral_discount_offer":
                f"Special referral offer for friends of {referrer}: 25% off first month. "
                f"Valid this week only → https://aurem.live/referral-offer",
        }
        body = messages.get(step["template"], "")
        ch = step["channel"]

        if ch == "whatsapp":
            try:
                from services.twilio_service import send_whatsapp_message
                from services.casl_compliance import wrap_whatsapp
                phone = ref.get("phone")
                if phone:
                    await send_whatsapp_message(phone, wrap_whatsapp(body))
            except Exception:
                pass
        elif ch == "email":
            from services.email_engine import resend  # iter 326x defensive
            import os
            email = ref.get("email")
            if email:
                from services.casl_compliance import wrap_email_html
                resend.api_key = os.environ.get("RESEND_API_KEY", "")
                try:
                    resend.Emails.send({
                        "from": f"ORA <{os.environ.get('AUREM_CONTACT_EMAIL','ora@aurem.live')}>",
                        "to": [email],
                        "subject": f"{referrer} sent me your way",
                        "html": wrap_email_html(body, lead_id=ref.get("referral_id", "")),
                    })
                except Exception:
                    pass

    async def _notify_referrers_of_contacts(self):
        """Ping the referrer whenever their referral was just contacted."""
        if self.db is None:
            return
        cursor = self.db.referrals.find(
            {"referrer_notified": {"$ne": True}, "steps_done": {"$ne": []}},
            {"_id": 0},
        ).limit(50)
        pending = await cursor.to_list(length=50)
        for ref in pending:
            referrer_email = ref.get("referrer_email")
            if not referrer_email:
                continue
            try:
                from services.email_engine import resend  # iter 326x defensive
                import os
                from services.casl_compliance import wrap_email_html
                resend.api_key = os.environ.get("RESEND_API_KEY", "")
                resend.Emails.send({
                    "from": "ORA <ora@aurem.live>",
                    "to": [referrer_email],
                    "subject": f"Your referral {ref.get('referral_name','')} was just contacted!",
                    "html": wrap_email_html(
                        f"<p>Quick update — we reached out to {ref.get('referral_name','your referral')}. "
                        f"Thanks for trusting AUREM 🙏</p>",
                        lead_id=ref.get("referral_id", ""),
                    ),
                })
                await self.db.referrals.update_one(
                    {"referral_id": ref["referral_id"]},
                    {"$set": {"referrer_notified": True,
                              "referrer_notified_at": datetime.now(timezone.utc).isoformat()}},
                )
            except Exception:
                continue
