"""
Follow-up ORA 📣 — Works on contacted leads.
Runs the drip schedule against leads marked "new" by the Hunter.
Day 3: WhatsApp · Day 7: Email · Day 14: WhatsApp · Day 21: SMS · Day 30: Voice · Day 60: Final offer.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict

from services.agents import AuremAgent

logger = logging.getLogger(__name__)


DRIP_SCHEDULE = [
    {"days_after_new": 3,  "channel": "whatsapp", "template": "followup_day3_nudge"},
    {"days_after_new": 7,  "channel": "email",    "template": "followup_day7_trial_offer"},
    {"days_after_new": 14, "channel": "whatsapp", "template": "followup_day14_objection"},
    {"days_after_new": 21, "channel": "sms",      "template": "followup_day21_urgency"},
    {"days_after_new": 30, "channel": "call",     "template": "followup_day30_voice"},
    {"days_after_new": 60, "channel": "email",    "template": "followup_day60_50_off"},
]


class FollowupORA(AuremAgent):
    AGENT_ID = "followup_ora"
    AGENT_NAME = "Follow-up ORA"
    AGENT_EMOJI = "📣"
    AGENT_JOB = "Work on contacted leads"

    async def run_cycle(self) -> Dict[str, Any]:
        if self._paused or self.db is None:
            return {"skipped": True}

        sent = 0
        handed_to_closer = 0
        now = datetime.now(timezone.utc)

        # Eligible: leads in "new", "contacted", or "following_up" stage, not DNC
        cursor = self.db.campaign_leads.find(
            {
                "status": {"$nin": ["do_not_contact", "subscribed", "closed_won"]},
                "stage": {"$in": ["new", "contacted", "following_up"]},
            },
            {"_id": 0},
        ).limit(200)

        leads = await cursor.to_list(length=200)
        self.mark_task(f"Drip pass on {len(leads)} leads")

        for lead in leads:
            created_at_str = lead.get("created_at") or lead.get("last_scouted_at")
            if not created_at_str:
                continue
            try:
                created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
            except Exception:
                continue

            days_old = (now - created_at).days

            # iter 282af — Site diff before any drip step. If the lead's
            # website has changed since the last scan, stash a note on the
            # lead dict so `_send_drip_step` can prepend it to the body.
            lead_site = (lead.get("website_url") or lead.get("website") or "").strip()
            if lead_site.startswith(("http://", "https://")):
                try:
                    from services.website_diff import diff_lead_site
                    diff = await diff_lead_site(self.db, lead["lead_id"], lead_site)
                    if diff.get("changed"):
                        preview = (diff.get("new_content_preview") or "").strip()
                        lead["_site_diff_note"] = (
                            "Note: this lead's website has changed since last "
                            f"scan. New content preview: {preview[:200]}. "
                            "Reference this change in the outreach if relevant."
                        )
                except Exception as e:
                    logger.debug(f"[FollowupORA] diff skipped for {lead.get('lead_id')}: {e}")

            # iter 282ah — compute outreach tone once per lead (rating ×
            # review_count). Stash on the lead dict so `_send_drip_step`
            # uses the right register per channel.
            try:
                from services.tone_tuner import get_outreach_tone
                lead["_tone_hint"] = get_outreach_tone(lead)
            except Exception:
                pass

            # Find the next drip step that's due
            drip_sent = lead.get("drip_steps_sent", [])
            for step in DRIP_SCHEDULE:
                if days_old >= step["days_after_new"] and step["template"] not in drip_sent:
                    # Respect channel gating
                    gating = lead.get("channel_gating") or {}
                    if not gating.get(step["channel"], True):
                        continue
                    try:
                        await self._send_drip_step(lead, step)
                        drip_sent.append(step["template"])
                        await self.db.campaign_leads.update_one(
                            {"lead_id": lead["lead_id"]},
                            {"$set": {"drip_steps_sent": drip_sent, "last_drip_at": now.isoformat()}},
                        )
                        sent += 1
                    except Exception as e:
                        logger.warning(f"[FollowupORA] drip failed for {lead.get('lead_id')}: {e}")
                    break

            # Hand off to Closer if stuck 7+ days with no reply
            last_reply = lead.get("last_reply_at")
            if (days_old >= 7 and not last_reply
                    and lead.get("stage") != "handed_to_closer"):
                await self.notify("closer_ora", "no_response",
                                  {"lead_id": lead["lead_id"], "business": lead.get("business_name"),
                                   "days_waiting": days_old})
                await self.db.campaign_leads.update_one(
                    {"lead_id": lead["lead_id"]},
                    {"$set": {"stage": "handed_to_closer", "handed_to_closer_at": now.isoformat()}},
                )
                handed_to_closer += 1

        stats = {"drip_sent": sent, "handed_to_closer": handed_to_closer}
        self._today_stats = stats
        await self.broadcast("daily_complete", {"agent": self.AGENT_ID, "stats": stats})
        return stats

    async def _send_drip_step(self, lead: Dict[str, Any], step: Dict[str, Any]):
        """Dispatch a single drip message. Thin wrapper over existing channels.

        iter 282ai — bodies + subjects are now LLM-composed via
        `services.outreach_composer.compose_outreach`. Hardcoded strings
        are only the composer's fallback path (triggered on LLM timeout /
        unparseable response). If `lead['_site_diff_note']` is set (by
        `run_cycle` when the website changed), it's passed to the composer
        as `site_change_context`. Send logic (Resend/Twilio) unchanged.
        """
        ch = step["channel"]
        diff_note = (lead.get("_site_diff_note") or "").strip() or None
        step_num = int(step.get("step_num") or step.get("step") or 1)
        scan_content = lead.get("scan_content")

        # iter 282al-6 — Outreach cooldown / DNC / dup-business gate.
        # Check BEFORE composing so we don't burn LLM tokens on blocked
        # leads. Logged to outreach_blocked for the daily review.
        try:
            from services.lead_dedup import (
                can_contact_lead, log_outreach_blocked,
            )
            allowed, reason = await can_contact_lead(self.db, lead)
            if not allowed:
                await log_outreach_blocked(self.db, lead, reason)
                logger.info(
                    f"[FollowupORA] blocked drip lead_id="
                    f"{lead.get('lead_id')} reason={reason}",
                )
                return
        except Exception as _de:
            logger.debug(f"[FollowupORA] dedup gate skipped: {_de}")

        # ── Compose one message for this channel/step ──
        from services.outreach_composer import compose_outreach
        composed = await compose_outreach(
            lead=lead, channel=ch, step=step_num, db=self.db,
            site_change_context=diff_note, scan_content=scan_content,
        )
        body = composed.get("body") or ""
        subject = composed.get("subject") or "Quick follow-up"

        if composed.get("fallback_used"):
            try:
                await self.db.composer_fallbacks.insert_one({
                    "lead_id":  lead.get("lead_id"),
                    "channel":  ch,
                    "step":     step_num,
                    "ts":       datetime.now(timezone.utc),
                    "reason":   "llm_failed",
                })
            except Exception:
                pass

        if ch == "whatsapp":
            from services.casl_compliance import wrap_whatsapp
            from services.twilio_service import send_whatsapp_message
            phone = lead.get("phone")
            if phone:
                await send_whatsapp_message(phone, wrap_whatsapp(body))
        elif ch == "email":
            import os

            import resend
            email = lead.get("email")
            if email:
                from services.casl_compliance import wrap_email_html
                resend.api_key = os.environ.get("RESEND_API_KEY", "")
                # Wrap composed body as HTML paragraph; wrap_email_html
                # appends footer + trackers per CASL.
                html = wrap_email_html(
                    f"<p>{body}</p>", lead_id=lead["lead_id"],
                )
                try:
                    resend.Emails.send({
                        "from": "ORA <ora@aurem.live>",
                        "to": [email],
                        "subject": subject,
                        "html": html,
                    })
                except Exception:
                    pass
        elif ch == "sms":
            import os
            import re as _re

            import httpx
            phone = lead.get("phone")
            sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
            tok = os.environ.get("TWILIO_AUTH_TOKEN", "")
            fn  = os.environ.get("TWILIO_PHONE_NUMBER", "")
            if phone and sid and tok and fn:
                from services.casl_compliance import wrap_sms
                # iter 282al — carrier filtering of long /report/<uuid>
                # URLs blows SMS deliverability (Twilio error 30007). Mint
                # a real shortlink for this lead and rewrite any reference
                # to /report/<lead_id>, /r/<lead_id>, or bare lead_id URL
                # with the short form before carriers see it.
                try:
                    from services.shortlink_service import get_or_create_shortlink
                    lead_id = lead.get("lead_id") or ""
                    if lead_id:
                        report_target = f"https://aurem.live/report/{lead_id}"
                        short_url = await get_or_create_shortlink(
                            self.db, lead_id, report_target,
                        )
                        if short_url and short_url != report_target:
                            # Replace full-URL variants (http/https, /r/, /report/)
                            body = _re.sub(
                                r"https?://(?:www\.)?aurem\.live/(?:report|r)/[A-Za-z0-9\-_]+",
                                short_url,
                                body,
                            )
                            # Replace bare host-relative variants too
                            body = _re.sub(
                                r"\baurem\.live/(?:report|r)/[A-Za-z0-9\-_]+",
                                short_url.replace("https://", ""),
                                body,
                            )
                except Exception as _se:
                    logger.debug(f"[FollowupORA] shortlink rewrite skipped: {_se}")
                async with httpx.AsyncClient(timeout=15) as c:
                    await c.post(
                        f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
                        auth=(sid, tok),
                        data={"From": fn, "To": phone, "Body": wrap_sms(body)},
                    )
        elif ch == "call":
            try:
                from services.flame_auto_dialer import trigger_call_for_lead
                await trigger_call_for_lead(self.db, lead["lead_id"], reason="followup_day30")
            except Exception:
                pass
