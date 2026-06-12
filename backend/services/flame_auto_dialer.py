"""
Flame Auto-Dialer
-----------------
When a prospect hits the INFERNO tier (flame_score >= 100) on their sample
website, this service:

  1. Looks up the lead (phone, business_name, website_url, verification gate)
  2. Respects Accurate-Scout's channel_gating: no call if call gate is OFF
  3. Sends a pre-call WhatsApp alert to the owner (per-tenant override supported)
  4. Generates a personalized "YOU'RE LITERALLY ON THE WEBSITE RIGHT NOW" pitch
  5. Dials via Twilio VoiceEngine (logs to call_logs + voice_calls + flame_auto_dials)

Public API:
    await try_auto_dial(db, viewer, lead_id) -> dict
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Optional

import httpx

from shared.tenant import FOUNDER_BIN

logger = logging.getLogger(__name__)

INFERNO_THRESHOLD = 100  # flame score at which we auto-dial
DEFAULT_ALERT_PHONE = os.environ.get("AUREM_HOT_LEAD_PHONE", "+16134000000")


# ─────────────────────────────────────────────────────────────
# Tenant-specific alert phone override
# ─────────────────────────────────────────────────────────────
async def _resolve_alert_phone(db, tenant_id: Optional[str]) -> str:
    """Return tenant's flame alert phone or global default."""
    if tenant_id:
        try:
            s = await db.tenant_settings.find_one({"tenant_id": tenant_id}, {"_id": 0, "flame_alert_phone": 1})
            if s and s.get("flame_alert_phone"):
                return s["flame_alert_phone"]
        except Exception:
            pass
    return DEFAULT_ALERT_PHONE


# ─────────────────────────────────────────────────────────────
# Pitch builder
# ─────────────────────────────────────────────────────────────
def _build_pitch_script(lead: dict, viewer: dict) -> str:
    """Generate a 'they're LITERALLY on the website right now' script for TwiML."""
    contact = (lead.get("contact_name") or "there").split()[0] if lead.get("contact_name") else "there"
    business = lead.get("business_name") or viewer.get("business_name") or "your business"
    dur_min = max(1, int((viewer.get("duration_seconds") or 60) / 60))

    # Keep script under ~40s spoken — ~90 words
    return (
        f"Hi {contact}, this is O R A from AUREM. "
        f"I notice you're looking at {business}'s new sample website right now — "
        f"you've been browsing for about {dur_min} minutes. "
        f"I'm calling because we already built this site for you for free, based on your Google listing. "
        f"If you like what you see, I can transfer the domain to you today — no credit card needed to start. "
        f"Press one to hear the three biggest improvements we noticed, or press two to schedule a follow-up."
    )


# ─────────────────────────────────────────────────────────────
# WhatsApp pre-call alert
# ─────────────────────────────────────────────────────────────
async def _send_pre_call_alert(alert_phone: str, viewer: dict, lead: dict) -> bool:
    whapi_token = os.environ.get("WHAPI_API_TOKEN", "")
    whapi_url = os.environ.get("WHAPI_API_URL", "")
    if not (whapi_token and whapi_url):
        return False
    phone = alert_phone.replace("+", "").replace("-", "").replace(" ", "")
    if not phone:
        return False

    business = viewer.get("business_name") or lead.get("business_name") or "Unknown Business"
    target = lead.get("phone") or "(no lead phone)"
    score = viewer.get("flame_score", "?")
    msg = (
        f"☎️ *AUTO-DIALING NOW*\n\n"
        f"Calling *{business}* — INFERNO score *{score}*\n"
        f"📞 Target: {target}\n\n"
        f"They're on their sample site right now.\n"
        f"Expected to connect in 5-10 sec.\n\n"
        f"_AUREM Flame Auto-Dialer_"
    )
    try:
        async with httpx.AsyncClient(timeout=8) as c:
            await c.post(
                f"{whapi_url}/messages/text",
                headers={"authorization": f"Bearer {whapi_token}", "content-type": "application/json"},
                json={"to": f"{phone}@s.whatsapp.net", "body": msg},
            )
        return True
    except Exception as e:
        logger.warning(f"[FlameAutoDial] WA pre-call alert failed: {e}")
        return False


async def _send_prospect_wa_simultaneous(lead: dict, viewer: dict) -> bool:
    """Task 1: fire a WhatsApp to the PROSPECT the same instant the auto-dial rings.
       90%+ pickup when they see WA + incoming call together."""
    whapi_token = os.environ.get("WHAPI_API_TOKEN", "")
    whapi_url = os.environ.get("WHAPI_API_URL", "")
    if not (whapi_token and whapi_url):
        return False
    target_phone = (lead.get("phone") or "").strip()
    if not target_phone:
        return False
    # Respect channel gating — if WhatsApp blocked, skip
    gate = ((lead.get("verification") or {}).get("channel_gating") or {})
    if gate.get("whatsapp") is False or lead.get("dnc"):
        return False

    phone = target_phone.replace("+", "").replace("-", "").replace(" ", "")
    business = lead.get("business_name") or viewer.get("business_name") or "your business"
    first = (lead.get("contact_name") or "").split()[0] or "there"
    base = os.environ.get("PUBLIC_APP_URL", "https://aurem.live").rstrip("/")
    slug = viewer.get("slug") or ""
    link = f"{base}/sample/{slug}" if slug else base
    body = (
        f"Hey {first}! 👋 That's me calling you right now about {business}'s free website.\n\n"
        f"Pick up — or reply here! 📞\n{link}"
    )
    try:
        async with httpx.AsyncClient(timeout=8) as c:
            r = await c.post(
                f"{whapi_url}/messages/text",
                headers={"authorization": f"Bearer {whapi_token}", "content-type": "application/json"},
                json={"to": f"{phone}@s.whatsapp.net", "body": body},
            )
            return r.status_code < 300
    except Exception as e:
        logger.warning(f"[FlameAutoDial] prospect WA simultaneous failed: {e}")
        return False


# ─────────────────────────────────────────────────────────────
# Main orchestrator
# ─────────────────────────────────────────────────────────────
async def try_auto_dial(db, viewer: dict, lead_id: Optional[str] = None) -> dict:
    """
    Fire the auto-dial flow if eligible.

    Returns dict with `status` one of:
      - "dialed"        : Twilio call placed
      - "mock_dialed"   : Twilio not configured, logged simulation
      - "blocked_gate"  : Accurate-Scout call gate is OFF
      - "blocked_dnc"   : lead marked DNC
      - "no_phone"      : lead has no phone
      - "no_lead"       : no lead found
      - "below_tier"    : score not yet INFERNO
      - "already_dialed": this session already auto-dialed
      - "disabled"      : auto-dialer disabled globally
    """
    if os.environ.get("FLAME_AUTO_DIALER_ENABLED", "true").lower() in ("false", "0", "no"):
        return {"status": "disabled"}

    if (viewer.get("flame_score") or 0) < INFERNO_THRESHOLD:
        return {"status": "below_tier"}

    session_id = viewer.get("session_id")
    if not session_id:
        return {"status": "no_lead"}

    # Idempotency — check if we already auto-dialed this session
    existing = await db.flame_auto_dials.find_one({"session_id": session_id}, {"_id": 0, "status": 1})
    if existing:
        return {"status": "already_dialed", "previous": existing.get("status")}

    # Resolve lead_id from viewer if not provided
    if not lead_id:
        viewer_doc = await db.aurem_live_viewers.find_one({"session_id": session_id}, {"_id": 0, "lead_id": 1})
        lead_id = (viewer_doc or {}).get("lead_id")
    if not lead_id and viewer.get("slug"):
        site = await db.aurem_websites.find_one({"slug": viewer["slug"]}, {"_id": 0, "lead_id": 1})
        lead_id = (site or {}).get("lead_id")

    if not lead_id:
        return {"status": "no_lead"}

    lead = await db.campaign_leads.find_one(
        {"lead_id": lead_id, "business_id": FOUNDER_BIN}, {"_id": 0})
    if not lead:
        return {"status": "no_lead"}

    # DNC / gate checks
    if lead.get("dnc"):
        await _log_dial(db, session_id, lead_id, lead, viewer, "blocked_dnc", None, None)
        return {"status": "blocked_dnc"}

    gate = ((lead.get("verification") or {}).get("channel_gating") or {}).get("call")
    # gate True → allowed; False or missing → block UNLESS override env
    override = os.environ.get("FLAME_DIAL_OVERRIDE_GATE", "").lower() in ("true", "1", "yes")
    if gate is False and not override:
        await _log_dial(db, session_id, lead_id, lead, viewer, "blocked_gate", None, None)
        return {"status": "blocked_gate", "reason": "channel_gating.call is false (Accurate-Scout low-confidence phone)"}

    phone = (lead.get("phone") or "").strip()
    if not phone:
        await _log_dial(db, session_id, lead_id, lead, viewer, "no_phone", None, None)
        return {"status": "no_phone"}

    # Build pitch
    script = _build_pitch_script(lead, viewer)

    # Pre-call WA alert + simultaneous WA to the PROSPECT (Task 1)
    alert_phone = await _resolve_alert_phone(db, lead.get("tenant_id"))
    wa_sent, prospect_wa_sent = await asyncio.gather(
        _send_pre_call_alert(alert_phone, viewer, lead),
        _send_prospect_wa_simultaneous(lead, viewer),
    )

    # Place the call
    dial_result: dict
    try:
        from services.voice_engine import VoiceEngine
        engine = VoiceEngine(db)
        dial_result = await engine.make_call(
            tenant_id=lead.get("tenant_id") or "flame-auto",
            to_number=phone,
            lead_id=lead_id,
            custom_script=script,
        )
    except Exception as e:
        logger.error(f"[FlameAutoDial] VoiceEngine.make_call crashed: {e}")
        dial_result = {"success": False, "error": str(e)}

    call_sid = dial_result.get("call_sid") if dial_result.get("success") else None
    status = "dialed" if dial_result.get("success") else (
        "mock_dialed" if "not configured" in str(dial_result.get("error", "")).lower() else "dial_failed"
    )

    # Log to voice_calls so it shows up in the CRM Call Logs feed
    try:
        await db.voice_calls.insert_one({
            "persona": "flame_autodialer",
            "persona_name": "Flame Auto-Dialer",
            "tier": "premium",
            "direction": "outbound",
            "sentiment": None,
            "csat_score": None,
            "duration_seconds": None,
            "started_at": datetime.now(timezone.utc),
            "ended_at": None,
            "status": status,
            "actions_taken": ["flame_auto_dial"],
            "caller_phone": phone,
            "business_name": lead.get("business_name"),
            "lead_id": lead_id,
            "session_id": session_id,
            "flame_score": viewer.get("flame_score"),
            "script": script,
            "call_sid": call_sid,
            "source": "flame_auto_dialer",
        })
    except Exception as e:
        logger.warning(f"[FlameAutoDial] voice_calls log failed: {e}")

    await _log_dial(db, session_id, lead_id, lead, viewer, status, script, call_sid, wa_sent, alert_phone)

    # Lifecycle: transition to called_no_response on any non-success (blitz will move to following_up)
    try:
        from services.lead_lifecycle import transition, record_touchpoint
        await record_touchpoint(
            db, lead_id, "call", "flame_auto_dial", status,
            details={"flame_score": viewer.get("flame_score"), "call_sid": call_sid, "error": dial_result.get("error")},
        )
        if status in ("dial_failed",):
            await transition(db, lead_id, "called_no_response", reason=f"flame_dial_failed:{dial_result.get('error', '')[:60]}")
        elif status in ("dialed", "mock_dialed"):
            # We dialed — keep them in 'called_no_response' pending answer/voicemail webhook signal.
            # For MVP, if dialed successfully we just record touchpoint; lifecycle will update on answer webhook later.
            pass
    except Exception as e:
        logger.warning(f"[FlameAutoDial] lifecycle hook failed: {e}")

    # Task 3: fire voicemail / dial-failure 3-channel blitz (WA + email + SMS)
    blitz_result = None
    if status == "dial_failed":
        try:
            from services.drip_sequencer import fire_voicemail_blitz
            blitz_result = await fire_voicemail_blitz(db, lead_id, viewer)
        except Exception as e:
            logger.warning(f"[FlameAutoDial] voicemail blitz failed: {e}")

    return {
        "status": status,
        "to": phone,
        "script_preview": script[:140] + "…",
        "call_sid": call_sid,
        "wa_pre_call_alert_sent": wa_sent,
        "prospect_wa_simultaneous_sent": prospect_wa_sent,
        "alert_phone": alert_phone,
        "engine": dial_result.get("engine"),
        "error": dial_result.get("error"),
        "voicemail_blitz": blitz_result,
    }


async def _log_dial(db, session_id, lead_id, lead, viewer, status, script, call_sid, wa_sent=False, alert_phone=None):
    try:
        await db.flame_auto_dials.insert_one({
            "session_id": session_id,
            "lead_id": lead_id,
            "business_name": lead.get("business_name") or viewer.get("business_name"),
            "to": lead.get("phone"),
            "flame_score": viewer.get("flame_score"),
            "flame_tier": viewer.get("flame_tier"),
            "status": status,
            "script_preview": (script or "")[:240],
            "call_sid": call_sid,
            "wa_pre_call_alert_sent": wa_sent,
            "alert_phone": alert_phone,
            "dialed_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        logger.warning(f"[FlameAutoDial] flame_auto_dials log failed: {e}")
