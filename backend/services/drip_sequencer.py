"""
Drip Sequencer + Multi-Channel Blitz
------------------------------------
Executes scheduled drip steps for leads in `called_no_response` or `following_up`
stages, and fires 3-channel blitz when a flame auto-dial goes to voicemail.

Drip timeline (triggered when lifecycle moves to `called_no_response`):
    Day 1:  WhatsApp — friendly nudge
    Day 3:  Email    — 14-day trial offer
    Day 7:  WhatsApp — ask for objection
    Day 14: SMS      — urgency push
    Day 30: Call     — ORA re-dial
    Day 60: Email    — final 50% off offer  →  stage becomes 'cold'

Respects Accurate-Scout `channel_gating` — blocked channels are skipped (the
step is marked `skipped_gated` so metrics know why) and the NEXT available
channel in the timeline still fires.

Public API:
  await run_due_drips(db) -> dict          # cron hook
  await fire_voicemail_blitz(db, lead_id, viewer=None) -> dict
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Optional

import httpx

from services.lead_lifecycle import record_touchpoint, transition

from shared.tenant import FOUNDER_BIN

logger = logging.getLogger(__name__)

# Schedule: (day, channel, step_name)
DRIP_SCHEDULE: list[tuple[int, str, str]] = [
    (1,  "whatsapp", "drip_day1_wa_nudge"),
    (3,  "email",    "drip_day3_email_trial"),
    (7,  "whatsapp", "drip_day7_wa_objection"),
    (14, "sms",      "drip_day14_sms_urgency"),
    (30, "call",     "drip_day30_ora_redial"),
    (60, "email",    "drip_day60_email_final_offer"),
]
FINAL_STEP_DAY = 60


# ─────────────────────────────────────────────────────────────
# Templates (inline AUREM tone — concise, friendly, urgency)
# ─────────────────────────────────────────────────────────────
def _first_name(lead: dict) -> str:
    name = lead.get("contact_name") or ""
    return (name.split()[0] if name else "there")


def _business(lead: dict) -> str:
    return lead.get("business_name") or "your business"


def _slug_url(lead: dict) -> str:
    slug = lead.get("slug") or lead.get("website_slug") or ""
    base = os.environ.get("PUBLIC_APP_URL", "https://aurem.live").rstrip("/")
    return f"{base}/sample/{slug}" if slug else (lead.get("website_url") or f"{base}")


def tmpl_wa_day1(lead: dict) -> str:
    return (
        f"Hi {_first_name(lead)}! 👋\n\n"
        f"Just tried calling you about {_business(lead)}'s free sample website — "
        f"it's still live and waiting for you:\n"
        f"{_slug_url(lead)}\n\n"
        f"Take a look — and reply here if you'd like to go live with it. No card needed. "
        f"— AUREM"
    )


def tmpl_email_day3(lead: dict) -> dict:
    return {
        "subject": f"{_business(lead)} — extended 14-day free trial",
        "html": (
            f"<div style='font-family:Arial,sans-serif;max-width:560px;margin:auto;color:#111'>"
            f"<p>Hi {_first_name(lead)},</p>"
            f"<p>I wanted to follow up on the sample website we built for <b>{_business(lead)}</b>. "
            f"We've extended the free trial to <b>14 days</b> — no credit card needed to go live.</p>"
            f"<p><a href='{_slug_url(lead)}' style='background:#ff6b00;color:#fff;padding:10px 18px;"
            f"text-decoration:none;border-radius:6px;display:inline-block'>View your site →</a></p>"
            f"<p>Reply to this email with any questions. ORA (our AI) will handle it within 60 seconds.</p>"
            f"<p style='color:#888;font-size:13px'>— AUREM</p>"
            f"</div>"
        ),
    }


def tmpl_wa_day7(lead: dict) -> str:
    return (
        f"Hey {_first_name(lead)} — quick question.\n\n"
        f"What's holding you back from going live with your {_business(lead)} website? "
        f"Pricing, design, timing? Reply with any concern and our AI will personally address it.\n\n"
        f"Site still live here: {_slug_url(lead)}"
    )


def tmpl_sms_day14(lead: dict) -> str:
    return (
        f"{_first_name(lead)} — your competitors are already using AUREM to out-rank you on Google. "
        f"Last reminder about {_business(lead)}'s free website: {_slug_url(lead)} Reply STOP to opt out."
    )


def tmpl_call_day30_script(lead: dict) -> str:
    return (
        f"Hi {_first_name(lead)}, this is O R A from AUREM again. "
        f"Quick update — we've noticed two of {_business(lead)}'s competitors started running "
        f"AUREM-built websites this month, and they're already picking up new customers from Google. "
        f"Your site is still waiting at {_slug_url(lead)}. "
        f"Press one to activate it right now with a fifty percent first-month discount, or press two to opt out."
    )


def tmpl_email_day60(lead: dict) -> dict:
    return {
        "subject": f"{_business(lead)} — final 50% off offer (today only)",
        "html": (
            f"<div style='font-family:Arial,sans-serif;max-width:560px;margin:auto;color:#111'>"
            f"<p>Hi {_first_name(lead)},</p>"
            f"<p>This is our last note about <b>{_business(lead)}</b>'s website. We're taking it offline in 48 hours "
            f"unless you want to keep it. If you do — <b>50% off your first month, today only.</b></p>"
            f"<p><a href='{_slug_url(lead)}?promo=LAST50' style='background:#ff1744;color:#fff;padding:12px 22px;"
            f"text-decoration:none;border-radius:6px;display:inline-block;font-weight:bold'>Claim 50% off →</a></p>"
            f"<p style='color:#888;font-size:13px'>After this email, we'll archive the draft. No further reminders.<br>— AUREM</p>"
            f"</div>"
        ),
    }


# ─────────────────────────────────────────────────────────────
# Channel senders (reuse existing integrations)
# ─────────────────────────────────────────────────────────────
async def _send_wa(phone: str, body: str) -> bool:
    token = os.environ.get("WHAPI_API_TOKEN", "")
    url = os.environ.get("WHAPI_API_URL", "")
    if not (token and url and phone):
        return False
    cleaned = phone.replace("+", "").replace("-", "").replace(" ", "")
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(
                f"{url}/messages/text",
                headers={"authorization": f"Bearer {token}", "content-type": "application/json"},
                json={"to": f"{cleaned}@s.whatsapp.net", "body": body},
            )
            return r.status_code < 300
    except Exception as e:
        logger.warning(f"[Drip] WA send failed: {e}")
        return False


async def _send_email(to: str, subject: str, html: str) -> bool:
    """Use Resend directly (email_engine is tenant-scoped, we send transactional here)."""
    try:
        api_key = os.environ.get("RESEND_API_KEY", "")
        from_addr = os.environ.get("RESEND_FROM_EMAIL", "ORA <ora@aurem.live>")
        if not (api_key and to):
            return False
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post(
                "https://api.resend.com/emails",
                headers={"authorization": f"Bearer {api_key}", "content-type": "application/json"},
                json={"from": from_addr, "to": [to], "subject": subject, "html": html},
            )
            return r.status_code < 300
    except Exception as e:
        logger.warning(f"[Drip] Email send failed: {e}")
        return False


async def _send_sms(phone: str, body: str) -> bool:
    try:
        from twilio.rest import Client  # type: ignore
        sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
        tok = os.environ.get("TWILIO_AUTH_TOKEN", "")
        frm = os.environ.get("TWILIO_PHONE_NUMBER", "")
        if not (sid and tok and frm and phone):
            return False
        client = Client(sid, tok)
        msg = await asyncio.to_thread(
            client.messages.create, body=body, from_=frm, to=phone
        )
        return bool(msg.sid)
    except Exception as e:
        logger.warning(f"[Drip] SMS send failed: {e}")
        return False


async def _place_call(db, lead: dict, script: str) -> dict:
    try:
        from services.voice_engine import VoiceEngine
        engine = VoiceEngine(db)
        return await engine.make_call(
            tenant_id=lead.get("tenant_id") or "drip",
            to_number=lead.get("phone") or "",
            lead_id=lead.get("lead_id") or "",
            custom_script=script,
        )
    except Exception as e:
        logger.warning(f"[Drip] Call failed: {e}")
        return {"success": False, "error": str(e)}


# ─────────────────────────────────────────────────────────────
# Gate resolver
# ─────────────────────────────────────────────────────────────
def _channel_allowed(lead: dict, channel: str) -> bool:
    """Respect Accurate-Scout channel_gating + DNC."""
    if lead.get("dnc"):
        return False
    gate = ((lead.get("verification") or {}).get("channel_gating") or {})
    # If gate explicitly False → blocked. Missing key → allowed (benefit of doubt for legacy leads).
    val = gate.get(channel)
    if val is False:
        return False
    # For SMS/WA/Call, require a phone
    if channel in ("whatsapp", "sms", "call") and not (lead.get("phone") or "").strip():
        return False
    if channel == "email" and not (lead.get("email") or "").strip():
        return False
    return True


# ─────────────────────────────────────────────────────────────
# Single-step executor
# ─────────────────────────────────────────────────────────────
async def _execute_step(db, lead: dict, day: int, channel: str, step_name: str) -> dict:
    lead_id = lead["lead_id"]

    if not _channel_allowed(lead, channel):
        await record_touchpoint(db, lead_id, channel, step_name, "skipped_gated",
                                details={"reason": "channel_gating or dnc or missing_contact"})
        return {"step": step_name, "status": "skipped_gated"}

    ok = False
    meta: dict = {}
    if channel == "whatsapp":
        body = tmpl_wa_day1(lead) if day == 1 else tmpl_wa_day7(lead)
        ok = await _send_wa(lead.get("phone") or "", body)
        meta["body_preview"] = body[:180]
    elif channel == "email":
        data = tmpl_email_day3(lead) if day == 3 else tmpl_email_day60(lead)
        ok = await _send_email(lead.get("email") or "", data["subject"], data["html"])
        meta["subject"] = data["subject"]
    elif channel == "sms":
        body = tmpl_sms_day14(lead)
        ok = await _send_sms(lead.get("phone") or "", body)
        meta["body_preview"] = body[:180]
    elif channel == "call":
        script = tmpl_call_day30_script(lead)
        res = await _place_call(db, lead, script)
        ok = bool(res.get("success"))
        meta = {"call_sid": res.get("call_sid"), "error": res.get("error"), "script_preview": script[:180]}

    status = "sent" if ok else "failed"
    await record_touchpoint(db, lead_id, channel, step_name, status, details=meta)
    return {"step": step_name, "status": status, "meta": meta}


# ─────────────────────────────────────────────────────────────
# Cron — run due drips
# ─────────────────────────────────────────────────────────────
async def run_due_drips(db) -> dict:
    """Scan for leads whose next drip step is due; execute each."""
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()

    cursor = db.campaign_leads.find(
        {
            "business_id": FOUNDER_BIN,
            "lifecycle_stage": {"$in": ["called_no_response", "following_up", "cold"]},
            "drip.next_action_at": {"$lte": now_iso},
            "$or": [{"drip.completed": {"$ne": True}}, {"lifecycle_stage": "cold"}],
        },
        {"_id": 0},
    ).limit(100)

    executed = 0
    results = []
    async for lead in cursor:
        drip = lead.get("drip") or {}
        day = int(drip.get("next_step_day") or 1)

        # Find the schedule entry for this day
        step = next(((d, ch, nm) for (d, ch, nm) in DRIP_SCHEDULE if d == day), None)

        if lead.get("lifecycle_stage") == "cold":
            # Cold lead re-approach — send a single WhatsApp nudge
            res = await _execute_step(db, lead, 1, "whatsapp", "cold_reapproach_wa")
            results.append({"lead_id": lead["lead_id"], "cold_reapproach": res})
            await db.campaign_leads.update_one(
                {"lead_id": lead["lead_id"], "business_id": FOUNDER_BIN},
                {"$set": {"drip.next_action_at": (now + timedelta(days=90)).isoformat()}},
            )
            executed += 1
            continue

        if not step:
            # No matching step — advance past this day
            await db.campaign_leads.update_one(
                {"lead_id": lead["lead_id"], "business_id": FOUNDER_BIN},
                {"$set": {"drip.next_action_at": (now + timedelta(days=7)).isoformat()}},
            )
            continue

        d, channel, step_name = step
        # Move to following_up after Day 1
        if d >= 3 and lead.get("lifecycle_stage") == "called_no_response":
            await transition(db, lead["lead_id"], "following_up", reason="drip_progressed")

        res = await _execute_step(db, lead, d, channel, step_name)
        executed += 1

        # Advance to next step, or mark complete → cold
        next_step = next(((dd, cc, nn) for (dd, cc, nn) in DRIP_SCHEDULE if dd > d), None)
        if next_step is None:
            # Day 60 was the last — move to cold, schedule re-approach in 90d
            await transition(db, lead["lead_id"], "cold", reason="drip_exhausted")
            update = {
                "drip.completed": True,
                "drip.next_step_day": None,
                "drip.next_action_at": (now + timedelta(days=90)).isoformat(),
                "drip.last_completed_at": now_iso,
            }
        else:
            nd, _nc, _nn = next_step
            started_raw = (lead.get("drip") or {}).get("started_at") or now_iso
            try:
                started = datetime.fromisoformat(str(started_raw).replace("Z", "+00:00"))
            except Exception:
                started = now
            update = {
                "drip.next_step_day": nd,
                "drip.next_action_at": (started + timedelta(days=nd)).isoformat(),
                "drip.last_step_at": now_iso,
            }

        steps_done = list(((lead.get("drip") or {}).get("steps_completed") or []))
        if d not in steps_done:
            steps_done.append(d)

        update["drip.steps_completed"] = steps_done
        await db.campaign_leads.update_one(
            {"lead_id": lead["lead_id"], "business_id": FOUNDER_BIN},
            {"$set": update})
        results.append({"lead_id": lead["lead_id"], "step": step_name, "status": res["status"]})

    return {"executed": executed, "results": results, "ran_at": now_iso}


# ─────────────────────────────────────────────────────────────
# Voicemail / dial-fail → 3-channel blitz (Task 3)
# ─────────────────────────────────────────────────────────────
async def fire_voicemail_blitz(db, lead_id: str, viewer: Optional[dict] = None) -> dict:
    """Send WhatsApp voice-note-style text + Gmail thread + SMS within ~60s."""
    lead = await db.campaign_leads.find_one(
        {"lead_id": lead_id, "business_id": FOUNDER_BIN}, {"_id": 0})
    if not lead:
        return {"ok": False, "error": "lead_not_found"}

    business = lead.get("business_name") or (viewer or {}).get("business_name") or "your business"
    first = _first_name(lead)
    slug_url = _slug_url({**(viewer or {}), **lead})

    # 1. WA voice-note-style message
    wa_body = (
        f"Hey {first} — that was me just now 🎙️\n\n"
        f"Couldn't reach you live about {business}'s website. "
        f"Here it is live: {slug_url}\n\n"
        f"Reply here and I'll answer in under 60 seconds. — AUREM"
    )
    wa_ok = await _send_wa(lead.get("phone") or "", wa_body)
    await record_touchpoint(db, lead_id, "whatsapp", "voicemail_blitz_wa", "sent" if wa_ok else "failed",
                            details={"body_preview": wa_body[:180]})

    # 2. Gmail thread / Email
    email_data = {
        "subject": f"Tried reaching you about {business}'s website",
        "html": (
            f"<div style='font-family:Arial,sans-serif;max-width:540px;margin:auto;color:#111'>"
            f"<p>Hi {first},</p>"
            f"<p>Just tried calling you about <b>{business}</b>'s free sample website. "
            f"Couldn't catch you — so I'm sending the link here so you can take a look whenever.</p>"
            f"<p><a href='{slug_url}' style='background:#ff6b00;color:#fff;padding:10px 18px;"
            f"text-decoration:none;border-radius:6px;display:inline-block'>View your site →</a></p>"
            f"<p>Reply to this email — our AI responds within a minute, 24/7.</p>"
            f"<p style='color:#888;font-size:13px'>— AUREM</p></div>"
        ),
    }
    email_ok = await _send_email(lead.get("email") or "", email_data["subject"], email_data["html"])
    await record_touchpoint(db, lead_id, "email", "voicemail_blitz_email", "sent" if email_ok else "failed",
                            details={"subject": email_data["subject"]})

    # 3. SMS fallback
    sms_body = (
        f"{first}, AUREM here — just called you re: {business}'s free site. "
        f"Link: {slug_url} — reply to chat, or STOP to opt out."
    )
    sms_ok = await _send_sms(lead.get("phone") or "", sms_body)
    await record_touchpoint(db, lead_id, "sms", "voicemail_blitz_sms", "sent" if sms_ok else "failed",
                            details={"body_preview": sms_body[:180]})

    # Mark blitz fired
    await db.campaign_leads.update_one(
        {"lead_id": lead_id, "business_id": FOUNDER_BIN},
        {"$set": {"voicemail_blitz_fired_at": datetime.now(timezone.utc).isoformat()}},
    )

    # Transition into following_up if not already there
    await transition(db, lead_id, "following_up", reason="voicemail_blitz")

    return {
        "ok": True,
        "wa_sent": wa_ok,
        "email_sent": email_ok,
        "sms_sent": sms_ok,
        "channels_fired": sum([wa_ok, email_ok, sms_ok]),
    }
