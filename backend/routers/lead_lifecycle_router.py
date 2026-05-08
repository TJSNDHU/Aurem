"""
Lead Lifecycle Router
---------------------
Powers the Kanban Pipeline UI in Campaign HQ.
"""
from __future__ import annotations

import hmac
import hashlib
import logging
import os
from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Header, Query, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/lifecycle", tags=["Lead Lifecycle"])

logger = logging.getLogger(__name__)
_db = None


def set_db(db):
    global _db
    _db = db


def _get_db():
    global _db
    if _db is not None:
        return _db
    try:
        from motor.motor_asyncio import AsyncIOMotorClient
        mongo_url = os.environ.get("MONGO_URL", "").strip().strip('"').strip("'")
        if not mongo_url:
            return None
        client = AsyncIOMotorClient(mongo_url)
        _db = client[os.environ.get("DB_NAME", "aurem_db")]
        return _db
    except Exception:
        return None


def _auth(authorization: Optional[str]):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "auth required")


# ─────────────────────────────────────────────────────────────
# Kanban board + metrics
# ─────────────────────────────────────────────────────────────
@router.get("/pipeline")
async def pipeline(
    authorization: Optional[str] = Header(None),
    limit_per_stage: int = Query(50, ge=1, le=200),
):
    _auth(authorization)
    db = _get_db()
    if db is None:
        raise HTTPException(503, "db_unavailable")
    from services.lead_lifecycle import get_pipeline_board
    return await get_pipeline_board(db, limit_per_stage)


@router.get("/metrics")
async def metrics(authorization: Optional[str] = Header(None)):
    _auth(authorization)
    db = _get_db()
    if db is None:
        raise HTTPException(503, "db_unavailable")
    from services.lead_lifecycle import get_metrics
    return await get_metrics(db)


@router.get("/lead/{lead_id}")
async def lead_detail(lead_id: str, authorization: Optional[str] = Header(None)):
    _auth(authorization)
    db = _get_db()
    if db is None:
        raise HTTPException(503, "db_unavailable")
    lead = await db.campaign_leads.find_one({"lead_id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(404, "lead_not_found")
    return lead


# ─────────────────────────────────────────────────────────────
# Transitions & manual actions
# ─────────────────────────────────────────────────────────────
class MoveStageIn(BaseModel):
    lead_id: str
    to_stage: str
    reason: Optional[str] = ""
    force: Optional[bool] = False


@router.post("/move-stage")
async def move_stage(body: MoveStageIn, authorization: Optional[str] = Header(None)):
    _auth(authorization)
    db = _get_db()
    if db is None:
        raise HTTPException(503, "db_unavailable")
    from services.lead_lifecycle import transition
    return await transition(db, body.lead_id, body.to_stage, reason=body.reason or "manual", by="admin", force=bool(body.force))


class AddNoteIn(BaseModel):
    lead_id: str
    note: str


@router.post("/add-note")
async def add_note_ep(body: AddNoteIn, authorization: Optional[str] = Header(None)):
    _auth(authorization)
    db = _get_db()
    if db is None:
        raise HTTPException(503, "db_unavailable")
    from services.lead_lifecycle import add_note
    return await add_note(db, body.lead_id, body.note)


class NextActionIn(BaseModel):
    lead_id: str
    when_iso: str
    action_type: Optional[str] = "manual"


@router.post("/set-next-action")
async def set_next(body: NextActionIn, authorization: Optional[str] = Header(None)):
    _auth(authorization)
    db = _get_db()
    if db is None:
        raise HTTPException(503, "db_unavailable")
    from services.lead_lifecycle import set_next_action
    return await set_next_action(db, body.lead_id, body.when_iso, body.action_type or "manual")


# ─────────────────────────────────────────────────────────────
# Manual blast + manual drip trigger
# ─────────────────────────────────────────────────────────────
class ManualBlastIn(BaseModel):
    lead_id: str
    channel: str  # whatsapp | email | sms
    body: Optional[str] = None
    subject: Optional[str] = None


@router.post("/manual-blast")
async def manual_blast(body: ManualBlastIn, authorization: Optional[str] = Header(None)):
    _auth(authorization)
    db = _get_db()
    if db is None:
        raise HTTPException(503, "db_unavailable")
    lead = await db.campaign_leads.find_one({"lead_id": body.lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(404, "lead_not_found")

    from services.drip_sequencer import _send_wa, _send_email, _send_sms, _channel_allowed
    from services.lead_lifecycle import record_touchpoint

    if not _channel_allowed(lead, body.channel):
        return {"ok": False, "error": "channel_gated_or_missing_contact"}

    ok = False
    if body.channel == "whatsapp":
        ok = await _send_wa(lead.get("phone") or "", body.body or "Hi from AUREM!")
    elif body.channel == "email":
        ok = await _send_email(lead.get("email") or "", body.subject or "From AUREM", body.body or "")
    elif body.channel == "sms":
        ok = await _send_sms(lead.get("phone") or "", body.body or "Hi from AUREM")
    else:
        raise HTTPException(400, "unknown channel")

    await record_touchpoint(db, body.lead_id, body.channel, "manual_blast", "sent" if ok else "failed",
                            details={"subject": body.subject, "body_preview": (body.body or "")[:180]})
    return {"ok": ok, "channel": body.channel}


@router.post("/run-drips-now")
async def run_drips_now(authorization: Optional[str] = Header(None)):
    """Manually kick the drip scheduler (for testing)."""
    _auth(authorization)
    db = _get_db()
    if db is None:
        raise HTTPException(503, "db_unavailable")
    from services.drip_sequencer import run_due_drips
    return await run_due_drips(db)


class BlitzIn(BaseModel):
    lead_id: str


@router.post("/voicemail-blitz")
async def voicemail_blitz_ep(body: BlitzIn, authorization: Optional[str] = Header(None)):
    _auth(authorization)
    db = _get_db()
    if db is None:
        raise HTTPException(503, "db_unavailable")
    from services.drip_sequencer import fire_voicemail_blitz
    return await fire_voicemail_blitz(db, body.lead_id)


# ─────────────────────────────────────────────────────────────
# Backfill — mark existing leads as 'new' if missing
# ─────────────────────────────────────────────────────────────
@router.post("/backfill-stages")
async def backfill_stages(authorization: Optional[str] = Header(None)):
    _auth(authorization)
    db = _get_db()
    if db is None:
        raise HTTPException(503, "db_unavailable")
    now_iso = datetime.now(timezone.utc).isoformat()
    r = await db.campaign_leads.update_many(
        {"lifecycle_stage": {"$exists": False}},
        {"$set": {
            "lifecycle_stage": "new",
            "lifecycle_stage_changed_at": now_iso,
            "lifecycle_history": [{"from": None, "to": "new", "at": now_iso, "reason": "backfill", "by": "system"}],
        }},
    )
    return {"updated": r.modified_count}


# ═══════════════════════════════════════════════════════════════
# ENGAGEMENT WEBHOOKS — auto-advance pipeline on opens/clicks/reads
# ═══════════════════════════════════════════════════════════════
async def _find_lead_by_email(db, email: str) -> Optional[dict]:
    if not email:
        return None
    return await db.campaign_leads.find_one(
        {"email": {"$regex": f"^{email}$", "$options": "i"}},
        {"_id": 0, "lead_id": 1, "lifecycle_stage": 1, "business_name": 1, "flame_score": 1},
    )


async def _find_lead_by_phone(db, phone: str) -> Optional[dict]:
    if not phone:
        return None
    # Normalize — strip non-digits for matching
    digits = "".join(c for c in phone if c.isdigit())
    if not digits:
        return None
    # Try exact match first, then partial (last 10 digits)
    last10 = digits[-10:] if len(digits) >= 10 else digits
    return await db.campaign_leads.find_one(
        {"$or": [
            {"phone": {"$regex": digits, "$options": "i"}},
            {"phone": {"$regex": last10, "$options": "i"}},
        ]},
        {"_id": 0, "lead_id": 1, "lifecycle_stage": 1, "business_name": 1, "contact_name": 1, "flame_score": 1},
    )


def _verify_resend_sig(body: bytes, sig: str) -> bool:
    """Resend uses Svix-compatible signatures. Verify against RESEND_WEBHOOK_SECRET."""
    secret = os.environ.get("RESEND_WEBHOOK_SECRET", "")
    if not secret:
        return True  # allow when secret not set (dev / initial wiring)
    try:
        # Svix format: "v1,<signature>" — we validate a HMAC-SHA256 over body
        expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, sig or "")
    except Exception:
        return False


@router.post("/webhook/resend")
async def resend_webhook(request: Request):
    """
    Resend webhook. Events we care about:
      - email.delivered   → touchpoint 'delivered'
      - email.opened      → lead → engaged
      - email.clicked     → lead → engaged + flame score boost
      - email.bounced     → touchpoint 'failed'
      - email.complained  → touchpoint 'complained' + DNC
    """
    body = await request.body()
    sig = request.headers.get("svix-signature") or request.headers.get("resend-signature") or ""
    if not _verify_resend_sig(body, sig):
        raise HTTPException(401, "invalid signature")

    try:
        import json
        event = json.loads(body)
    except Exception:
        raise HTTPException(400, "invalid json")

    db = _get_db()
    if db is None:
        return {"received": True, "db": "unavailable"}

    event_type = event.get("type", "")
    data = event.get("data", {}) or {}
    to_list = data.get("to") or []
    email_to = to_list[0] if to_list else data.get("email_to") or ""

    lead = await _find_lead_by_email(db, email_to)
    if not lead:
        return {"received": True, "matched_lead": False, "type": event_type}

    from services.lead_lifecycle import transition, record_touchpoint

    lead_id = lead["lead_id"]
    current_stage = lead.get("lifecycle_stage") or "new"

    if event_type == "email.delivered":
        await record_touchpoint(db, lead_id, "email", "resend_delivered", "sent",
                                details={"email_id": data.get("email_id")})
        if current_stage == "new":
            await transition(db, lead_id, "contacted", reason="email_delivered", by="resend_webhook")

    elif event_type == "email.opened":
        await record_touchpoint(db, lead_id, "email", "resend_opened", "opened",
                                details={"email_id": data.get("email_id")})
        # Move contacted → engaged
        if current_stage in ("new", "contacted"):
            await transition(db, lead_id, "engaged", reason="email_opened", by="resend_webhook", force=True)

    elif event_type == "email.clicked":
        click = data.get("click", {}) or {}
        await record_touchpoint(db, lead_id, "email", "resend_clicked", "clicked",
                                details={"email_id": data.get("email_id"), "url": click.get("link")})
        # HIGH intent — engage + boost flame score by +20
        if current_stage in ("new", "contacted", "called_no_response", "following_up", "cold"):
            await transition(db, lead_id, "engaged", reason="email_clicked_link", by="resend_webhook", force=True)
        try:
            await db.campaign_leads.update_one(
                {"lead_id": lead_id},
                {"$inc": {"flame_score_boost": 20}},
            )
        except Exception:
            pass

    elif event_type in ("email.bounced", "email.complained"):
        kind = "resend_bounced" if event_type == "email.bounced" else "resend_complained"
        await record_touchpoint(db, lead_id, "email", kind, "failed",
                                details={"email_id": data.get("email_id")})
        if event_type == "email.complained":
            # Opt-out on spam complaint
            await db.campaign_leads.update_one({"lead_id": lead_id}, {"$set": {"dnc": True, "dnc_reason": "email_complaint"}})

    return {"received": True, "type": event_type, "lead_id": lead_id, "from_stage": current_stage}


@router.post("/webhook/whapi")
async def whapi_webhook(request: Request):
    """
    WHAPI webhook — inbound messages + read receipts.
      - statuses with status='read'   → engaged
      - messages (inbound text)       → following_up + admin WA alert
    """
    body = await request.body()

    # WHAPI verification: we can require a bearer token via ENV, or the WHAPI X-Webhook-Secret
    expected_secret = os.environ.get("WHAPI_WEBHOOK_SECRET", "")
    if expected_secret:
        got = request.headers.get("x-webhook-secret") or request.headers.get("authorization", "").replace("Bearer ", "")
        if got != expected_secret:
            raise HTTPException(401, "invalid secret")

    try:
        import json
        payload = json.loads(body)
    except Exception:
        raise HTTPException(400, "invalid json")

    db = _get_db()
    if db is None:
        return {"received": True, "db": "unavailable"}

    from services.lead_lifecycle import transition, record_touchpoint

    actions = []

    # READ RECEIPTS — statuses array
    for status in (payload.get("statuses") or []):
        if status.get("status") != "read":
            continue
        recipient = (status.get("recipient_id") or "").replace("@s.whatsapp.net", "")
        if not recipient:
            continue
        lead = await _find_lead_by_phone(db, recipient)
        if not lead:
            actions.append({"type": "read", "matched": False, "phone": recipient})
            continue
        await record_touchpoint(db, lead["lead_id"], "whatsapp", "whapi_read", "read",
                                details={"message_id": status.get("id")})
        cur = lead.get("lifecycle_stage") or "new"
        if cur in ("new", "contacted"):
            await transition(db, lead["lead_id"], "engaged", reason="wa_read", by="whapi_webhook", force=True)
        actions.append({"type": "read", "lead_id": lead["lead_id"]})

    # INBOUND MESSAGES — messages array
    for msg in (payload.get("messages") or []):
        if msg.get("from_me"):
            continue
        from_phone = (msg.get("from") or msg.get("chat_id") or "").replace("@s.whatsapp.net", "")
        body_text = (msg.get("text") or {}).get("body") if isinstance(msg.get("text"), dict) else (msg.get("text") or msg.get("body") or "")
        lead = await _find_lead_by_phone(db, from_phone)
        if not lead:
            actions.append({"type": "inbound", "matched": False, "from": from_phone})
            continue
        await record_touchpoint(db, lead["lead_id"], "whatsapp", "whapi_inbound", "replied",
                                details={"from": from_phone, "body_preview": (body_text or "")[:180]})
        await transition(db, lead["lead_id"], "following_up", reason="wa_replied", by="whapi_webhook", force=True)

        # Admin WA alert
        alert_phone = os.environ.get("AUREM_HOT_LEAD_PHONE", "+16134000000")
        await _send_admin_reply_alert(alert_phone, lead, body_text or "")
        actions.append({"type": "inbound", "lead_id": lead["lead_id"], "admin_alerted": True})

    return {"received": True, "actions": actions}


async def _send_admin_reply_alert(alert_phone: str, lead: dict, body_text: str) -> bool:
    whapi_token = os.environ.get("WHAPI_API_TOKEN", "")
    whapi_url = os.environ.get("WHAPI_API_URL", "")
    if not (whapi_token and whapi_url):
        return False
    phone = alert_phone.replace("+", "").replace("-", "").replace(" ", "")
    if not phone:
        return False
    business = lead.get("business_name") or "Unknown Business"
    contact = lead.get("contact_name") or ""
    msg = (
        f"💬 *LEAD REPLIED*\n\n"
        f"*{business}* — {contact}\n\n"
        f"Reply:\n_{(body_text or '')[:240]}_\n\n"
        f"Stage → following_up\n"
        f"_AUREM Auto-Pipeline_"
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
        logger.warning(f"[Lifecycle] admin reply alert failed: {e}")
        return False


# ═══════════════════════════════════════════════════════════════
# TEST ENDPOINTS — simulate webhook events for verification
# ═══════════════════════════════════════════════════════════════
class SimulateEmailEventIn(BaseModel):
    lead_id: str
    event: str  # delivered | opened | clicked | bounced


@router.post("/webhook/resend/simulate")
async def simulate_resend(body: SimulateEmailEventIn, authorization: Optional[str] = Header(None)):
    _auth(authorization)
    db = _get_db()
    if db is None:
        raise HTTPException(503, "db_unavailable")
    lead = await db.campaign_leads.find_one({"lead_id": body.lead_id}, {"_id": 0, "email": 1})
    if not lead or not lead.get("email"):
        raise HTTPException(404, "lead_not_found_or_no_email")
    # Fake a Resend payload
    payload = {
        "type": f"email.{body.event}",
        "data": {
            "email_id": f"sim-{int(datetime.now(timezone.utc).timestamp())}",
            "to": [lead["email"]],
            "click": {"link": "https://aurem.live/sample/test"} if body.event == "clicked" else {},
        },
    }
    # Call the webhook internally (bypass signature in dev)
    import json
    req_body = json.dumps(payload).encode()

    class _FakeReq:
        headers = {}
        async def body(self):
            return req_body
    return await resend_webhook(_FakeReq())


class SimulateWhapiEventIn(BaseModel):
    lead_id: str
    event: str  # read | inbound
    body_text: Optional[str] = "Yes I'm interested, tell me more"


@router.post("/webhook/whapi/simulate")
async def simulate_whapi(body: SimulateWhapiEventIn, authorization: Optional[str] = Header(None)):
    _auth(authorization)
    db = _get_db()
    if db is None:
        raise HTTPException(503, "db_unavailable")
    lead = await db.campaign_leads.find_one({"lead_id": body.lead_id}, {"_id": 0, "phone": 1})
    if not lead or not lead.get("phone"):
        raise HTTPException(404, "lead_not_found_or_no_phone")
    phone_digits = "".join(c for c in lead["phone"] if c.isdigit())
    if body.event == "read":
        payload = {"statuses": [{"status": "read", "id": f"sim-{phone_digits}", "recipient_id": f"{phone_digits}@s.whatsapp.net"}]}
    else:
        payload = {"messages": [{"from": f"{phone_digits}@s.whatsapp.net", "from_me": False,
                                  "text": {"body": body.body_text or "Yes"}}]}
    import json
    req_body = json.dumps(payload).encode()

    class _FakeReq:
        headers = {}
        async def body(self):
            return req_body
    return await whapi_webhook(_FakeReq())




# ═══════════════════════════════════════════════════════════════
# MORNING DIGEST — on-demand preview + manual send
# ═══════════════════════════════════════════════════════════════
@router.get("/morning-digest/preview")
async def morning_digest_preview(authorization: Optional[str] = Header(None)):
    """Build the digest without sending — returns the message body for preview."""
    _auth(authorization)
    db = _get_db()
    if db is None:
        raise HTTPException(503, "db_unavailable")
    from services.morning_digest import build_digest
    return await build_digest(db)


class DigestSendIn(BaseModel):
    to_phone: Optional[str] = None


@router.post("/morning-digest/send")
async def morning_digest_send(
    body: Optional[DigestSendIn] = None,
    authorization: Optional[str] = Header(None),
):
    """Fire the digest WhatsApp NOW (for testing / manual re-send)."""
    _auth(authorization)
    db = _get_db()
    if db is None:
        raise HTTPException(503, "db_unavailable")
    from services.morning_digest import send_morning_digest
    to = body.to_phone if body else None
    return await send_morning_digest(db, to_phone=to)


@router.get("/morning-digest/history")
async def morning_digest_history(
    authorization: Optional[str] = Header(None),
    limit: int = Query(30, ge=1, le=100),
):
    _auth(authorization)
    db = _get_db()
    if db is None:
        raise HTTPException(503, "db_unavailable")
    cursor = db.morning_digest_log.find({}, {"_id": 0}).sort("sent_at", -1).limit(limit)
    docs = await cursor.to_list(length=limit)
    return {"count": len(docs), "digests": docs}
