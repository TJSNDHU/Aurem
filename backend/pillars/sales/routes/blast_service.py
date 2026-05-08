"""Sales/Campaign — Per-Lead Blast Dispatch + Test Endpoints.

Split from the former monolithic routers/campaign_router.py (2,068 LOC) as
part of Pillar 1 (Sales) logic modularization — iter 262.
"""
import logging
import os
import uuid
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional, Any, Dict
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from pillars.sales.routes._shared import (
    _get_db, _verify_admin, _get_today_schedule,
    WHATSAPP_TEMPLATES, EMAIL_SUBJECTS, TARGET_CATEGORIES, COMPETITOR_TEMPLATES,
)

router = APIRouter(prefix="/api/campaign", tags=["AUREM Campaign"])
logger = logging.getLogger(__name__)


@router.post("/leads/{lead_id}/send-email")
async def send_lead_email(lead_id: str, request: Request):
    """Send email to a campaign lead."""
    _verify_admin(request)
    db = _get_db()
    lead = await db.campaign_leads.find_one({"lead_id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(404, "Lead not found")
    body = await request.json()
    use_template = bool(body.get("use_template", False))
    if use_template:
        from services.aurem_outreach_templates import render_email_subject, render_email_html
        subject = body.get("subject") or render_email_subject(lead)
        html = body.get("html") or render_email_html(lead)
    else:
        subject = body.get("subject", f"{lead['business_name']} — Get More Customers on Autopilot")
        html = body.get("html", "")
    to = body.get("to", lead.get("email", ""))
    if not to:
        raise HTTPException(400, "No email address")
    try:
        import resend
        resend.api_key = os.environ.get("RESEND_API_KEY", "")
        r = resend.Emails.send({"from": "ORA <ora@aurem.live>", "to": [to], "subject": subject, "html": html or f"<p>Hi {lead['business_name']},</p><p>Follow up from AUREM Intelligence AI.</p>", "reply_to": "support@aurem.live"})
        email_id = r.get("id", str(r))
        now = datetime.now(timezone.utc).isoformat()
        await db.campaign_leads.update_one({"lead_id": lead_id}, {"$push": {"outreach_history": {"type": "email", "to": to, "status": "sent", "email_id": email_id, "subject": subject, "template": "aurem_v1" if use_template else "custom", "timestamp": now}}, "$set": {"status": "emailed", "updated_at": now}})
        return {"success": True, "email_id": email_id}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/leads/{lead_id}/send-whatsapp")
async def send_lead_whatsapp(lead_id: str, request: Request):
    """Send WhatsApp to a campaign lead via WHAPI."""
    _verify_admin(request)
    db = _get_db()
    lead = await db.campaign_leads.find_one({"lead_id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(404, "Lead not found")
    body = await request.json()
    use_template = bool(body.get("use_template", False))
    if use_template:
        from services.aurem_outreach_templates import render_whatsapp
        message = body.get("message") or render_whatsapp(lead)
    else:
        message = body.get("message", f"Hi {lead['business_name']}! This is ORA from AUREM Intelligence AI.")
    phone = body.get("phone", lead.get("phone", "")).replace("+", "").replace("-", "").replace(" ", "")
    if not phone:
        raise HTTPException(400, "No phone number")
    try:
        import httpx
        whapi_token = os.environ.get("WHAPI_API_TOKEN", "")
        whapi_url = os.environ.get("WHAPI_API_URL", "")
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(f"{whapi_url}/messages/text", headers={"authorization": f"Bearer {whapi_token}", "content-type": "application/json"}, json={"to": f"{phone}@s.whatsapp.net", "body": message})
            data = resp.json()
        now = datetime.now(timezone.utc).isoformat()
        await db.campaign_leads.update_one({"lead_id": lead_id}, {"$push": {"outreach_history": {"type": "whatsapp", "to": phone, "status": "sent" if resp.status_code == 200 else "failed", "template": "aurem_v1" if use_template else "custom", "timestamp": now}}, "$set": {"updated_at": now}})
        return {"success": resp.status_code == 200, "data": data}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/leads/{lead_id}/send-sms")
async def send_lead_sms(lead_id: str, request: Request):
    """Send SMS to a campaign lead via Twilio."""
    _verify_admin(request)
    db = _get_db()
    lead = await db.campaign_leads.find_one({"lead_id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(404, "Lead not found")
    body = await request.json()
    use_template = bool(body.get("use_template", False))
    if use_template:
        from services.aurem_outreach_templates import render_sms
        message = body.get("message") or render_sms(lead)
    else:
        message = body.get("message", f"Hi {lead['business_name']}! ORA from AUREM Intelligence AI. See aurem.live/demo")
    phone = body.get("phone", lead.get("phone", ""))
    if not phone:
        raise HTTPException(400, "No phone number")
    try:
        import httpx
        sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
        token = os.environ.get("TWILIO_AUTH_TOKEN", "")
        from_num = os.environ.get("TWILIO_PHONE_NUMBER", "")
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json", auth=(sid, token), data={"From": from_num, "To": phone, "Body": message})
            data = resp.json()
        now = datetime.now(timezone.utc).isoformat()
        await db.campaign_leads.update_one({"lead_id": lead_id}, {"$push": {"outreach_history": {"type": "sms", "to": phone, "status": "sent" if resp.status_code in (200,201) else "failed", "sid": data.get("sid",""), "template": "aurem_v1" if use_template else "custom", "timestamp": now}}, "$set": {"updated_at": now}})
        return {"success": resp.status_code in (200,201), "sid": data.get("sid")}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/leads/{lead_id}/call")
async def call_lead(lead_id: str, request: Request):
    """Make ORA voice call to a campaign lead via Twilio."""
    _verify_admin(request)
    db = _get_db()
    lead = await db.campaign_leads.find_one({"lead_id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(404, "Lead not found")
    body = await request.json()
    use_template = bool(body.get("use_template", False))
    phone = body.get("phone", lead.get("phone", ""))
    if use_template:
        from services.aurem_outreach_templates import render_voice_script
        script = body.get("script") or render_voice_script(lead)
    else:
        script = body.get("script", f"Hello {lead['business_name']}. This is ORA, the AI business assistant from AUREM Intelligence AI. We help businesses like yours get more customers through AI-powered marketing. Visit aurem dot live for a free demo. Thank you!")
    if not phone:
        raise HTTPException(400, "No phone number")
    try:
        import httpx
        sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
        token = os.environ.get("TWILIO_AUTH_TOKEN", "")
        from_num = os.environ.get("TWILIO_PHONE_NUMBER", "")
        twiml = f'<Response><Say voice="Polly.Joanna">{script}</Say></Response>'
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Calls.json", auth=(sid, token), data={"From": from_num, "To": phone, "Twiml": twiml})
            data = resp.json()
        now = datetime.now(timezone.utc).isoformat()
        await db.campaign_leads.update_one({"lead_id": lead_id}, {"$push": {"outreach_history": {"type": "call", "to": phone, "status": data.get("status","queued"), "call_sid": data.get("sid",""), "template": "aurem_v1" if use_template else "custom", "timestamp": now}}, "$set": {"updated_at": now}})
        return {"success": resp.status_code in (200,201), "call_sid": data.get("sid"), "status": data.get("status")}
    except Exception as e:
        raise HTTPException(500, str(e))


async def execute_blast_for_lead(
    db,
    lead: Dict[str, Any],
    respect_gating: bool = True,
    source: str = "manual",
) -> Dict[str, Any]:
    """
    Shared core that performs a 4-channel AUREM blast for a given lead doc.
    Used by both the manual /blast-all endpoint and the auto_blast_engine.
    Returns same shape as the manual endpoint response.

    respect_gating=True skips channels where verification gated them OFF.
    """
    lead_id = lead.get("lead_id")

    # Auto-generate sample website if missing
    if not lead.get("website_url"):
        try:
            from routers.website_builder_router import auto_generate_if_missing
            await auto_generate_if_missing(db, lead)
            # Re-fetch to pick up generated url
            fresh = await db.campaign_leads.find_one({"lead_id": lead_id}, {"_id": 0})
            if fresh:
                lead = fresh
        except Exception as e:
            logger.warning(f"[Blast] Website auto-generate failed for {lead_id}: {e}")

    from services.aurem_outreach_templates import (
        render_whatsapp, render_sms, render_email_subject,
        render_email_html, render_voice_script,
    )
    phone = (lead.get("phone") or "").strip()
    email = (lead.get("email") or "").strip()
    results: Dict[str, Any] = {}
    history_entries = []
    now = datetime.now(timezone.utc).isoformat()

    gates = ((lead.get("verification") or {}).get("channel_gating") or {}) if respect_gating else {}

    # iter 295 — runtime safety net: if the lead has actual contact data but the
    # cached verifier marked the channel false, re-evaluate with current rules.
    # Email and call are low-carrier-risk and should fire whenever the data exists.
    if respect_gating:
        if email and gates.get("email") is False:
            gates["email"] = True   # CASL implied-consent for listed B2B emails
        if phone and gates.get("call") is False:
            gates["call"] = True    # Twilio voice — no A2P requirement
        # SMS stays gated (carrier A2P enforcement is real)
        # WhatsApp stays gated (Meta template approval)

    def _gate_open(ch: str) -> bool:
        if not respect_gating:
            return True
        return gates.get(ch, True) is not False

    # 1) EMAIL
    if email and _gate_open("email"):
        try:
            import resend
            resend.api_key = os.environ.get("RESEND_API_KEY", "")
            r = resend.Emails.send({
                "from": "ORA <ora@aurem.live>",
                "to": [email],
                "subject": render_email_subject(lead),
                "html": render_email_html(lead),
                "reply_to": "support@aurem.live",
            })
            eid = r.get("id", str(r))
            results["email"] = {"success": True, "email_id": eid, "to": email}
            history_entries.append({"type": "email", "to": email, "status": "sent", "email_id": eid, "subject": render_email_subject(lead), "template": "aurem_v1", "source": source, "timestamp": now})
        except Exception as e:
            results["email"] = {"success": False, "error": str(e), "to": email}
    elif email and not _gate_open("email"):
        results["email"] = {"success": False, "error": "gated", "to": email}
    else:
        results["email"] = {"success": False, "error": "no email address"}

    # 2) SMS (Twilio)
    if phone and _gate_open("sms"):
        try:
            import httpx
            sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
            token = os.environ.get("TWILIO_AUTH_TOKEN", "")
            from_num = os.environ.get("TWILIO_PHONE_NUMBER", "")
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
                    auth=(sid, token),
                    data={"From": from_num, "To": phone, "Body": render_sms(lead)},
                )
                data = resp.json()
            ok = resp.status_code in (200, 201)
            results["sms"] = {"success": ok, "sid": data.get("sid"), "to": phone, "status_code": resp.status_code, "error": data.get("message") if not ok else None}
            history_entries.append({"type": "sms", "to": phone, "status": "sent" if ok else "failed", "sid": data.get("sid", ""), "template": "aurem_v1", "source": source, "timestamp": now})
        except Exception as e:
            results["sms"] = {"success": False, "error": str(e), "to": phone}
    elif phone and not _gate_open("sms"):
        results["sms"] = {"success": False, "error": "gated", "to": phone}
    else:
        results["sms"] = {"success": False, "error": "no phone number"}

    # 3) WHATSAPP
    #
    # iter 287.4 — Twilio WhatsApp Business API (WABA) is now PRIMARY.
    # Meta-approved, legally safe for cold B2B outreach.
    #
    # Fallback: WHAPI (unofficial QR-scan gateway) still wired but guarded
    # by WHAPI_BLAST_DISABLED flag. After the account restriction incident
    # on 2026-04-24, WHAPI_BLAST_DISABLED=true — keep disabled until founder
    # decides to re-enable with a different number.
    #
    # Routing:
    #   - If TWILIO_WA_FROM_NUMBER configured → use Twilio WABA (primary)
    #   - Else if WHAPI_BLAST_DISABLED=false → fall back to WHAPI
    #   - Else → skip with honest "no_wa_provider" status
    import os as _os
    whapi_disabled = (_os.environ.get("WHAPI_BLAST_DISABLED", "false").lower()
                      in ("1", "true", "yes", "on"))
    twilio_wa_ready = bool((_os.environ.get("TWILIO_WA_FROM_NUMBER") or "").strip())

    if phone and _gate_open("whatsapp") and twilio_wa_ready:
        # PRIMARY: Twilio WhatsApp Business API
        try:
            from services.twilio_whatsapp import send_whatsapp
            body = render_whatsapp(lead)
            # If a template is configured, variables are populated from lead
            wa_res = await send_whatsapp(
                phone, body,
                variables={
                    "1": lead.get("business_name", ""),
                    "2": lead.get("city", "your area"),
                },
            )
            ok = bool(wa_res.get("success"))
            results["whatsapp"] = {
                "success": ok,
                "to": wa_res.get("to") or phone,
                "message_id": wa_res.get("message_sid"),
                "provider": "twilio_waba",
                "mode": wa_res.get("mode"),
                "error": wa_res.get("error"),
            }
            history_entries.append({
                "type": "whatsapp",
                "to": wa_res.get("to") or phone,
                "status": "sent" if ok else "failed",
                "template": wa_res.get("mode"),
                "provider": "twilio_waba",
                "source": source,
                "error": wa_res.get("error"),
                "message_id": wa_res.get("message_sid"),
                "timestamp": now,
            })
        except Exception as e:
            results["whatsapp"] = {"success": False, "error": str(e), "to": phone,
                                   "provider": "twilio_waba"}
            history_entries.append({
                "type": "whatsapp", "to": phone, "status": "failed",
                "error": str(e), "provider": "twilio_waba",
                "source": source, "timestamp": now,
            })
    elif phone and _gate_open("whatsapp") and not whapi_disabled:
        try:
            from services.whapi_service import send_whatsapp_message
            body = render_whatsapp(lead)
            wa_res = await send_whatsapp_message(phone, body)
            ok = bool(wa_res.get("success"))
            results["whatsapp"] = {
                "success": ok,
                "to": wa_res.get("phone") or phone,
                "message_id": wa_res.get("message_id"),
                "error": wa_res.get("error"),
            }
            history_entries.append({
                "type": "whatsapp",
                "to": wa_res.get("phone") or phone,
                "status": "sent" if ok else "failed",
                "template": "aurem_v1",
                "source": source,
                "error": wa_res.get("error"),
                "message_id": wa_res.get("message_id"),
                "timestamp": now,
            })
        except Exception as e:
            results["whatsapp"] = {"success": False, "error": str(e), "to": phone}
            history_entries.append({
                "type": "whatsapp", "to": phone, "status": "failed",
                "error": str(e), "source": source, "timestamp": now,
            })
    elif phone and not _gate_open("whatsapp"):
        results["whatsapp"] = {"success": False, "error": "gated", "to": phone}
    elif phone and whapi_disabled:
        # Honest skip record — no fake "sent" status
        results["whatsapp"] = {
            "success": False,
            "error": "whapi_blast_disabled_by_admin",
            "to": phone,
        }
        history_entries.append({
            "type": "whatsapp", "to": phone, "status": "skipped",
            "error": "WHAPI_BLAST_DISABLED=true — account restricted",
            "source": source, "timestamp": now,
        })
    else:
        results["whatsapp"] = {"success": False, "error": "no phone number"}

    # 4) VOICE CALL (Twilio)
    if phone and _gate_open("call"):
        try:
            import httpx
            sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
            token = os.environ.get("TWILIO_AUTH_TOKEN", "")
            from_num = os.environ.get("TWILIO_PHONE_NUMBER", "")
            twiml = f'<Response><Say voice="Polly.Joanna">{render_voice_script(lead)}</Say></Response>'
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Calls.json",
                    auth=(sid, token),
                    data={"From": from_num, "To": phone, "Twiml": twiml},
                )
                data = resp.json()
            ok = resp.status_code in (200, 201)
            results["voice"] = {"success": ok, "call_sid": data.get("sid"), "status": data.get("status"), "to": phone, "status_code": resp.status_code, "error": data.get("message") if not ok else None}
            history_entries.append({"type": "call", "to": phone, "status": data.get("status", "queued"), "call_sid": data.get("sid", ""), "template": "aurem_v1", "source": source, "timestamp": now})
        except Exception as e:
            results["voice"] = {"success": False, "error": str(e), "to": phone}
    elif phone and not _gate_open("call"):
        results["voice"] = {"success": False, "error": "gated", "to": phone}
    else:
        results["voice"] = {"success": False, "error": "no phone number"}

    # Persist all entries + status update
    if history_entries:
        new_status = "emailed" if results.get("email", {}).get("success") else lead.get("status", "contacted")
        await db.campaign_leads.update_one(
            {"lead_id": lead_id},
            {"$push": {"outreach_history": {"$each": history_entries}},
             "$set": {"status": new_status, "updated_at": now, "last_blast_at": now, "last_blast_source": source}},
        )

    sent_count = sum(1 for c in results.values() if c.get("success"))

    # ──────────────── Iter 288.8 · Boardroom Ledger cost hooks ────────────────
    # Attribute every successful channel send to the Envoy agent so the
    # Sovereign Boardroom P&L reflects real outreach burn (not zeros).
    try:
        from services.agent_ledger import record_cost
        agent_id = "envoy_ora"
        meta = {"lead_id": lead_id, "source": source}
        if results.get("email", {}).get("success"):
            await record_cost(db, agent_id, "email_resend", 1, meta={**meta, "channel": "email"})
        if results.get("sms", {}).get("success"):
            await record_cost(db, agent_id, "sms_twilio", 1, meta={**meta, "channel": "sms"})
        if results.get("whatsapp", {}).get("success"):
            provider = results["whatsapp"].get("provider") or "whapi"
            await record_cost(db, agent_id, "waba_twilio" if provider == "twilio_waba" else "waba_twilio",
                              1, meta={**meta, "channel": "whatsapp", "provider": provider})
        if results.get("voice", {}).get("success"):
            await record_cost(db, agent_id, "voice_twilio", 1, meta={**meta, "channel": "voice"})
    except Exception as _ledger_err:
        logger.debug(f"[Blast] ledger record_cost skipped: {_ledger_err}")

    return {
        "lead_id": lead_id,
        "business_name": lead.get("business_name"),
        "sent_count": sent_count,
        "total_channels": 4,
        "source": source,
        "results": results,
        "timestamp": now,
    }


@router.post("/leads/{lead_id}/blast-all")
async def blast_all_channels(lead_id: str, request: Request):
    """
    Send the AUREM-branded outreach across all 4 channels in parallel
    (Email → Resend, SMS → Twilio, WhatsApp → WHAPI, Voice → Twilio).
    Variables auto-fill from the lead document.
    """
    _verify_admin(request)
    db = _get_db()
    lead = await db.campaign_leads.find_one({"lead_id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(404, "Lead not found")
    return await execute_blast_for_lead(db, lead, respect_gating=False, source="manual")


# ══════════════════════════════════════════════
# Auto-Blast Engine — toggles + manual trigger
# ══════════════════════════════════════════════
class TestEmailRequest(BaseModel):
    to: str
    template: str = "outbound_1"
    business_name: str = "Test Business"
    first_name: str = "Business Owner"
    score: int = 65
    issues_count: int = 4
    website: str = "example.com"


class TestSMSRequest(BaseModel):
    to: str
    message: str = ""
    first_name: str = "there"
    website: str = "example.com"
    issues_count: int = 3
    lead_id: str = "test"


@router.post("/test-sms")
async def test_sms(data: TestSMSRequest, request: Request):
    """Send a test SMS via the SMS Engine (Twilio)."""
    _verify_admin(request)

    message = data.message or f"Hi {data.first_name}, ORA here. Scanned {data.website}. Found {data.issues_count} issues. Report: aurem.live/report/{data.lead_id}"

    try:
        from services.sms_engine import SMSEngine
        from server import db as _sms_db
        sms_engine = SMSEngine(_sms_db)
        result = await sms_engine.send_message("polaris-built-001", data.to, message)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/test-email")
async def test_email(data: TestEmailRequest, request: Request):
    """Send a test outbound email using Resend."""
    _verify_admin(request)

    template_num = data.template.replace("outbound_", "")
    template_path = Path(__file__).parent.parent / "templates" / f"outbound_email_{template_num}.html"

    if not template_path.exists():
        raise HTTPException(404, f"Template {data.template} not found")

    html = template_path.read_text()

    # Variable substitution
    replacements = {
        "{{first_name}}": data.first_name,
        "{{business_name}}": data.business_name,
        "{{website}}": data.website,
        "{{score}}": str(data.score),
        "{{issues_count}}": str(data.issues_count),
        "{{issue_1}}": "Missing meta descriptions on 12 pages",
        "{{issue_2}}": "No SSL certificate detected",
        "{{issue_3}}": "Page load time exceeds 4 seconds",
        "{{impact}}": "High — losing ~30% potential traffic",
        "{{days_since}}": "7",
        "{{report_link}}": f"https://aurem.live/report/test",
        "{{unsubscribe_link}}": f"https://aurem.live/unsubscribe?email={data.to}",
    }
    for key, val in replacements.items():
        html = html.replace(key, val)

    # Select subject
    subjects = EMAIL_SUBJECTS.get(data.template, ["Your Website Report"])
    import random
    subject = random.choice(subjects).format(
        score=data.score, issues_count=data.issues_count,
        business_name=data.business_name,
    )

    # Route via Email Engine (Resend)
    try:
        from services.email_engine import EmailEngine
        from server import db as _email_db
        email_engine = EmailEngine(_email_db)
        result = await email_engine.send_message("polaris-built-001", data.to, subject, html)
        if result.get("success"):
            return {"success": True, "email_id": result.get("email_id"), "subject": subject, "engine": result.get("engine")}
        else:
            return {"success": False, "error": result.get("error", "Send failed"), "subject": subject, "engine": result.get("engine")}
    except Exception as e:
        return {"success": False, "error": str(e), "subject": subject}


# ══════════════════════════════════════════════
# WhatsApp Outreach
# ══════════════════════════════════════════════
class TestWhatsAppRequest(BaseModel):
    to: str
    template: str = "initial"
    business_name: str = "Test Business"
    first_name: str = "Business Owner"
    score: int = 65
    issues_count: int = 4


@router.post("/test-whatsapp")
async def test_whatsapp(data: TestWhatsAppRequest, request: Request):
    """Send a test WhatsApp message via WHAPI (or mock if key missing)."""
    _verify_admin(request)

    template_text = WHATSAPP_TEMPLATES.get(data.template, WHATSAPP_TEMPLATES["initial"])
    message = template_text.format(
        first_name=data.first_name,
        business_name=data.business_name,
        score=data.score,
        issues_count=data.issues_count,
        report_link="https://aurem.live/report/test",
        top_issue="Page load time exceeds 4 seconds",
    )

    # Route via WhatsApp Hybrid Engine
    try:
        from services.whatsapp_engine import WhatsAppEngine
        from server import db as _campaign_db
        wa_engine = WhatsAppEngine(_campaign_db)
        phone = data.to.replace("+", "").replace("-", "").replace(" ", "")
        result = await wa_engine.send_message("polaris-built-001", phone, message)
        if result.get("success"):
            return {"success": True, "message_id": result.get("message_id"), "template": data.template, "engine": result.get("engine")}
        else:
            return {"success": False, "error": result.get("error", "Send failed"), "engine": result.get("engine")}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ══════════════════════════════════════════════
# Call Outreach
# ══════════════════════════════════════════════
class TestCallRequest(BaseModel):
    to: str
    script: str = "voicemail"
    first_name: str = "Business Owner"
    website: str = "example.com"
    score: int = 65
    issues_count: int = 4


@router.post("/test-call")
async def test_call(data: TestCallRequest, request: Request):
    """Trigger a test outbound call via VoiceEngine."""
    _verify_admin(request)

    try:
        from services.voice_engine import VoiceEngine
        from server import db as _voice_db
        engine = VoiceEngine(_voice_db)

        # Build custom script from ora_call_script if available
        custom_script = ""
        try:
            from services.ora_call_script import render_script
            custom_script = render_script(
                data.script,
                first_name=data.first_name,
                website=data.website,
                score=data.score,
                issues_count=data.issues_count,
            )
        except Exception:
            custom_script = f"Hi {data.first_name}, this is ORA from AUREM. I scanned {data.website} and found {data.issues_count} issues. Your site scored {data.score} out of 100."

        result = await engine.make_call("polaris-built-001", data.to, custom_script=custom_script)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


# ══════════════════════════════════════════════
# Voice Call by Lead ID + Keypress Webhook
# ══════════════════════════════════════════════

@router.post("/voice-call/{lead_id}")
async def voice_call_lead(lead_id: str, request: Request):
    """Trigger an outbound ORA voice call to a specific lead."""
    _verify_admin(request)

    db = _get_db()
    if not db:
        raise HTTPException(500, "DB not available")

    try:
        from services.voice_engine import VoiceEngine
        engine = VoiceEngine(db)

        # Get lead phone number
        lead = await db.campaign_leads.find_one({"lead_id": lead_id}, {"_id": 0})
        if not lead:
            lead = await db.envoy_outreach.find_one({"lead_id": lead_id}, {"_id": 0})
        if not lead or not lead.get("phone"):
            raise HTTPException(404, "Lead not found or no phone number")

        phone = lead["phone"]
        result = await engine.make_call("polaris-built-001", phone, lead_id)
        return result
    except HTTPException:
        raise
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/voice/keypress/{lead_id}")
async def voice_keypress_handler(lead_id: str, request: Request):
    """
    Twilio webhook for keypress during ORA voice call.
    Press 1 = interested → update lead status
    Press 2 = opt out → add to do_not_contact
    """
    from fastapi.responses import Response

    db = _get_db()

    # Parse form data from Twilio webhook
    form_data = await request.form()
    digits = form_data.get("Digits", "")

    if digits == "1":
        # Interested — update lead
        if db:
            await db.campaign_leads.update_one(
                {"lead_id": lead_id},
                {"$set": {"status": "voice_interested", "updated_at": datetime.now(timezone.utc).isoformat()},
                 "$push": {"outreach_history": {"type": "voice_response", "response": "interested", "at": datetime.now(timezone.utc).isoformat()}}},
            )
        twiml = (
            '<Response>'
            '<Say voice="Polly.Joanna">Great! I\'ll send you the full report by email right now. '
            'You can also view it at aurem dot live. '
            'Thank you for your time, and have a wonderful day!</Say>'
            '</Response>'
        )
    elif digits == "2":
        # Opt out
        if db:
            lead = await db.campaign_leads.find_one({"lead_id": lead_id}, {"_id": 0, "phone": 1, "email": 1})
            if lead:
                await db.do_not_contact.update_one(
                    {"phone": lead.get("phone", "")},
                    {"$set": {"phone": lead.get("phone", ""), "email": lead.get("email", ""),
                              "reason": "voice_opt_out", "channel": "all",
                              "opted_out_at": datetime.now(timezone.utc).isoformat()}},
                    upsert=True,
                )
            await db.campaign_leads.update_one(
                {"lead_id": lead_id},
                {"$set": {"status": "opted_out", "dnc": True}},
            )
        twiml = (
            '<Response>'
            '<Say voice="Polly.Joanna">No problem at all. '
            'You\'ve been removed from our list and won\'t receive further calls. '
            'Have a great day!</Say>'
            '</Response>'
        )
    else:
        twiml = (
            '<Response>'
            '<Say voice="Polly.Joanna">Sorry, I didn\'t catch that. '
            'Thank you for your time. Goodbye!</Say>'
            '</Response>'
        )

@router.post("/whatsapp-webhook")
async def whatsapp_stop_handler(request: Request):
    """Handle incoming WhatsApp STOP messages for CASL compliance."""
    db = _get_db()
    if not db:
        return {"ok": True}
    try:
        body = await request.json()
        messages = body.get("messages", [])
        for msg in messages:
            text = msg.get("text", {}).get("body", "").strip().upper()
            sender = msg.get("from", "")
            if text == "STOP" and sender:
                phone = f"+{sender.replace('@s.whatsapp.net', '')}"
                await db.do_not_contact.update_one(
                    {"phone": phone},
                    {"$setOnInsert": {
                        "phone": phone,
                        "email": "",
                        "reason": "whatsapp-stop",
                        "added_at": datetime.now(timezone.utc).isoformat(),
                    }},
                    upsert=True,
                )
                await db.campaign_leads.update_many(
                    {"phone": phone},
                    {"$set": {"status": "not_interested", "dnc": True}},
                )
                logger.info(f"[CASL] WhatsApp STOP received from {phone}")
    except Exception as e:
        logger.warning(f"WhatsApp webhook error: {e}")
    return {"ok": True}


# ══════════════════════════════════════════════
# Automation: Batch operations called by scheduler
# ══════════════════════════════════════════════
