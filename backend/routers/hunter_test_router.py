"""
Hunter LIVE Test Route — Safe E2E Diagnostic (Email + SMS + WhatsApp)
═══════════════════════════════════════════════════════════════════════════════
Verifies the full Find → Compose → Send chain end-to-end WITHOUT touching a
single real business. Messages are addressed only to the admin's own inbox /
phone. The mock lead is the content, not the target.
"""
import os
import logging
from datetime import datetime, timezone
from typing import Optional

import jwt
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, EmailStr

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Hunter Live Test"])

_db = None


def set_db(database):
    global _db
    _db = database


def _decode(request: Request) -> dict:
    auth = request.headers.get("authorization") or request.headers.get("Authorization") or ""
    token = auth.split(" ", 1)[1] if auth.startswith("Bearer ") else None
    if not token:
        raise HTTPException(401, "Auth required")
    try:
        return jwt.decode(token, (os.environ.get("JWT_SECRET") or (_ for _ in ()).throw(__import__("fastapi").HTTPException(status_code=500, detail="JWT not configured"))), algorithms=["HS256"])
    except Exception:
        raise HTTPException(401, "Invalid token")


async def _require_admin(request: Request) -> dict:
    p = _decode(request)
    role = (p.get("role") or "").lower()
    if role not in ("admin", "super_admin") and not (p.get("is_admin") or p.get("is_super_admin")):
        raise HTTPException(403, "Admin required")
    return p


class HunterTestBody(BaseModel):
    test_email: Optional[EmailStr] = Field(None, description="Your own inbox for the test email")
    test_phone: Optional[str] = Field(None, max_length=25, description="Your own phone (E.164, e.g. +14155552671)")
    industry: str = Field("salons", max_length=40)
    province: str = Field("Ontario", max_length=40)
    count: int = Field(1, ge=1, le=3, description="Max leads to mock-find (capped at 3)")
    send_email: bool = Field(True, description="Send the preview email to test_email")
    send_sms: bool = Field(False, description="Send a plain SMS to test_phone")
    send_whatsapp: bool = Field(False, description="Send a WhatsApp message to test_phone")


@router.post("/api/agents/hunter/run-test")
async def hunter_run_test(body: HunterTestBody, request: Request):
    """SAFE end-to-end Hunter diagnostic — fires Email + SMS + WhatsApp only
    to the admin's own inbox/phone. Zero real businesses are contacted.
    """
    admin = await _require_admin(request)

    channels_requested = [c for c, on in [
        ("email", body.send_email and bool(body.test_email)),
        ("sms", body.send_sms and bool(body.test_phone)),
        ("whatsapp", body.send_whatsapp and bool(body.test_phone)),
    ] if on]
    if not channels_requested:
        raise HTTPException(400, "Select at least one channel: email (needs test_email) or sms/whatsapp (needs test_phone)")

    trace = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "admin": admin.get("email"),
        "test_email": body.test_email,
        "test_phone": body.test_phone,
        "channels": channels_requested,
        "steps": [],
    }

    # ── STEP 1: Mock-find leads ──────────────────────────────────────
    try:
        from services.hunt_live import start_hunt
        hunt_id = await start_hunt(
            _db,
            city=body.province,
            industry=body.industry,
            count=body.count,
            mock=True,
        )
        trace["steps"].append({"step": "mock_hunt", "ok": True, "hunt_id": hunt_id, "count": body.count})
    except Exception as e:
        logger.exception(f"[hunter-test] mock hunt failed: {e}")
        trace["steps"].append({"step": "mock_hunt", "ok": False, "error": str(e)})
        raise HTTPException(500, f"mock hunt failed: {e}")

    # ── STEP 2: Sample lead (from DB or synthetic fallback) ──────────
    sample_lead = None
    if _db is not None:
        for coll in ("hunt_leads", "leads", "campaign_leads"):
            try:
                doc = await _db[coll].find_one({"hunt_id": hunt_id}, {"_id": 0})
                if doc:
                    sample_lead = doc
                    trace["steps"].append({"step": "fetch_sample", "ok": True, "from_collection": coll})
                    break
            except Exception:
                continue

    if not sample_lead:
        sample_lead = {
            "business_name": f"Demo {body.industry.title()} Co.",
            "city": body.province,
            "industry": body.industry,
            "phone": "+1-555-TEST-001",
            "website": "https://example.com",
            "score": 82,
        }
        trace["steps"].append({"step": "fetch_sample", "ok": True, "fallback": True})

    # ── STEP 3a: Compose the email body ──────────────────────────────
    subject = f"[TEST RUN] Hunter found: {sample_lead.get('business_name','Demo')}"
    html = f"""
    <div style='font-family:Georgia,serif;max-width:560px;'>
      <h2 style='color:#C9A227;letter-spacing:1px;'>◆ AUREM Hunter — Live Test Run</h2>
      <p>Safe diagnostic verifying the Find → Compose → Send chain.
         <em>No real business was contacted.</em></p>
      <h3 style='color:#0a0a12;margin-top:24px;'>Sample lead captured</h3>
      <table style='border-collapse:collapse;font-size:14px;width:100%;'>
        <tr><td style='color:#888;padding:4px 0;'>Business</td><td><strong>{sample_lead.get('business_name','—')}</strong></td></tr>
        <tr><td style='color:#888;padding:4px 0;'>Industry</td><td>{sample_lead.get('industry', body.industry)}</td></tr>
        <tr><td style='color:#888;padding:4px 0;'>Location</td><td>{sample_lead.get('city', body.province)}</td></tr>
        <tr><td style='color:#888;padding:4px 0;'>Score</td><td>{sample_lead.get('score','—')}/100</td></tr>
        <tr><td style='color:#888;padding:4px 0;'>Phone</td><td>{sample_lead.get('phone','—')}</td></tr>
        <tr><td style='color:#888;padding:4px 0;'>Website</td><td>{sample_lead.get('website','—')}</td></tr>
      </table>
      <p style='margin-top:24px;color:#555;'>If you received this email, the
         full outreach pipeline is working: lead discovery ✓ · email composition
         ✓ · Resend delivery ✓. Flip <code>dry_run</code> to false on Hunter
         when ready to go LIVE.</p>
      <p style='color:#999;font-size:11px;margin-top:30px;'>Test ID · <code>{hunt_id}</code></p>
    </div>
    """

    # ── STEP 4a: Send Email via Resend ───────────────────────────────
    if body.send_email and body.test_email:
        try:
            from services.email_engine import resend  # iter 326x defensive
            resend.api_key = os.environ.get("RESEND_API_KEY") or ""
            if not resend.api_key:
                trace["steps"].append({"step": "send_email", "ok": False, "error": "RESEND_API_KEY missing"})
            else:
                from_email = os.environ.get("RESEND_FROM_EMAIL") or "ORA <ora@aurem.live>"
                sent = resend.Emails.send({
                    "from": from_email, "to": [body.test_email],
                    "subject": subject, "html": html,
                })
                trace["steps"].append({
                    "step": "send_email", "ok": True,
                    "resend_id": (sent or {}).get("id"),
                    "to": body.test_email, "from": from_email,
                })
        except Exception as e:
            logger.exception(f"[hunter-test] email send failed: {e}")
            trace["steps"].append({"step": "send_email", "ok": False, "error": str(e)})
    else:
        trace["steps"].append({"step": "send_email", "ok": True, "skipped": True})

    # ── STEP 4b: Send SMS via Twilio ─────────────────────────────────
    if body.send_sms and body.test_phone:
        try:
            from services.twilio_service import send_sms
            sms_msg = (
                f"AUREM Hunter — TEST RUN\n"
                f"Mock lead: {sample_lead.get('business_name','—')}\n"
                f"Score: {sample_lead.get('score','—')}/100\n"
                f"Test ID: {hunt_id}\n\n"
                f"Pipeline verified: FIND -> SMS OK"
            )
            res = await send_sms(body.test_phone, sms_msg)
            trace["steps"].append({
                "step": "send_sms", "ok": bool(res.get("success")),
                "sid": res.get("sid"), "to": body.test_phone,
                "error": res.get("error"),
            })
        except Exception as e:
            logger.exception(f"[hunter-test] sms send failed: {e}")
            trace["steps"].append({"step": "send_sms", "ok": False, "error": str(e)})

    # ── STEP 4c: Send WhatsApp via WHAPI.cloud ──────────────────────
    if body.send_whatsapp and body.test_phone:
        try:
            from services.whapi_service import send_whatsapp_message as whapi_send
            wa_msg = (
                f"🎯 *AUREM Hunter — TEST RUN*\n\n"
                f"_Diagnostic ping. No real business was contacted._\n\n"
                f"*Mock lead found:*\n"
                f"• Business: {sample_lead.get('business_name','—')}\n"
                f"• Industry: {sample_lead.get('industry', body.industry)}\n"
                f"• Location: {sample_lead.get('city', body.province)}\n"
                f"• Score: {sample_lead.get('score','—')}/100\n\n"
                f"✓ Pipeline verified: FIND → COMPOSE → WhatsApp (via WHAPI)\n"
                f"Test ID: `{hunt_id}`"
            )
            res = await whapi_send(body.test_phone, wa_msg)
            trace["steps"].append({
                "step": "send_whatsapp", "ok": bool(res.get("success")),
                "message_id": res.get("message_id"), "to": body.test_phone,
                "provider": "whapi", "error": res.get("error"),
            })
        except Exception as e:
            logger.exception(f"[hunter-test] whatsapp send failed: {e}")
            trace["steps"].append({"step": "send_whatsapp", "ok": False, "error": str(e), "provider": "whapi"})

    # ── STEP 5: Audit record ─────────────────────────────────────────
    if _db is not None:
        try:
            await _db.hunter_live_tests.insert_one({
                "test_id": hunt_id,
                "admin_email": admin.get("email"),
                "to_email": body.test_email,
                "to_phone": body.test_phone,
                "channels": channels_requested,
                "industry": body.industry,
                "province": body.province,
                "ran_at": trace["started_at"],
                "ok": all(s.get("ok") for s in trace["steps"]),
                "sample_lead_name": sample_lead.get("business_name"),
            })
        except Exception:
            pass

    trace["ok"] = all(s.get("ok") for s in trace["steps"])
    trace["completed_at"] = datetime.now(timezone.utc).isoformat()
    return {"ok": trace["ok"], "hunt_id": hunt_id, "sample": sample_lead, "trace": trace}


@router.get("/api/agents/hunter/run-test/history")
async def hunter_test_history(request: Request, limit: int = 20):
    await _require_admin(request)
    if _db is None:
        raise HTTPException(503, "db not ready")
    out = []
    async for d in _db.hunter_live_tests.find({}, {"_id": 0}).sort("ran_at", -1).limit(limit):
        out.append(d)
    return {"ok": True, "count": len(out), "tests": out}
