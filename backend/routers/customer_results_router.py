"""
Customer-facing inbox & results — `/api/customer/inbox` + `/api/customer/results`.

GOLD-MINE LOCKED:
  • Numbers and aggregate counts only.
  • NO lead names, NO contact details, NO export, NO raw data joins.
  • Customers see OUTCOMES, never records.

Endpoints:
  GET  /api/customer/inbox/threads        — unified_inbox grouped by thread_id
  POST /api/customer/inbox/reply          — send reply on correct channel
  GET  /api/customer/results-summary      — TILE A (4 KPIs)
  GET  /api/customer/results-activity     — TILE B (anonymous activity feed)
  GET  /api/customer/results-pipeline     — TILE C (lead-count by stage)

Backed by:
  • db.unified_inbox     (written by services/inbox_writer.py)
  • db.agent_actions     (written by every Scout/Hunter/Closer ORA)
  • db.touchpoints       (per-channel inbound/outbound events)
  • db.campaign_leads    (lifecycle_stage per lead)
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import jwt
from fastapi import APIRouter, Body, HTTPException, Request

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/customer", tags=["Customer Results"])

_db = None


def set_db(database) -> None:
    global _db
    _db = database


def _decode(token: str) -> dict:
    secret = os.environ.get("JWT_SECRET") or os.environ.get("JWT_SECRET_KEY") or ""
    if not secret:
        raise HTTPException(500, "JWT secret not configured")
    try:
        return jwt.decode(token, secret, algorithms=["HS256"])
    except Exception:
        raise HTTPException(401, "Invalid token")


async def _ctx(request: Request) -> dict:
    """Resolve {business_id, email} from the request JWT.

    Falls back to looking up business_id from `platform_users` when the
    token is older and pre-dates the embedded business_id claim.
    """
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Authentication required")
    claims = _decode(auth[7:])
    bin_id = claims.get("business_id") or ""
    email = (claims.get("email") or "").lower()
    if not bin_id and email and _db is not None:
        u = await _db.platform_users.find_one(
            {"email": email}, {"_id": 0, "business_id": 1}
        )
        bin_id = (u or {}).get("business_id") or ""
    if not bin_id:
        raise HTTPException(403, "Token missing business context")
    return {"business_id": bin_id, "email": email}


# ═══════════════════════════════════════════════════════════════════════
# INBOX — threads + reply
# ═══════════════════════════════════════════════════════════════════════
@router.get("/inbox/threads")
async def inbox_threads(request: Request, limit: int = 25):
    """One row per thread_id: latest message + channel + unread count.

    Privacy: returns `from_handle` (masked) and `last_message_preview`
    only — full sender details are never exposed in list view.
    """
    ctx = await _ctx(request)
    bin_id = ctx["business_id"]
    pipeline = [
        {"$match": {"business_id": bin_id}},
        {"$sort": {"timestamp": -1}},
        {"$group": {
            "_id": "$thread_id",
            "channel": {"$first": "$channel"},
            "last_direction": {"$first": "$direction"},
            "last_message": {"$first": "$message"},
            "last_from": {"$first": "$from"},
            "last_ts": {"$first": "$timestamp"},
            "unread": {
                "$sum": {"$cond": [
                    {"$and": [
                        {"$eq": ["$direction", "inbound"]},
                        {"$eq": ["$read", False]},
                    ]}, 1, 0,
                ]},
            },
            "count": {"$sum": 1},
        }},
        {"$sort": {"last_ts": -1}},
        {"$limit": max(1, min(limit, 100))},
    ]
    rows: List[Dict[str, Any]] = []
    async for r in _db.unified_inbox.aggregate(pipeline):
        from_raw = (r.get("last_from") or "")
        # Mask the sender — never expose raw phone/email in the list.
        handle = _mask_handle(from_raw, r.get("channel"))
        rows.append({
            "thread_id": r.get("_id") or "",
            "channel": r.get("channel"),
            "last_direction": r.get("last_direction"),
            "last_message_preview": (r.get("last_message") or "")[:140],
            "last_at": r["last_ts"].isoformat() if r.get("last_ts") else None,
            "unread": int(r.get("unread", 0)),
            "message_count": int(r.get("count", 0)),
            "from_handle": handle,
        })
    return {"ok": True, "business_id": bin_id, "total": len(rows), "threads": rows}


@router.get("/inbox/thread/{thread_id}")
async def inbox_thread_messages(thread_id: str, request: Request, limit: int = 50):
    """Full message list for one thread. Customer sees their own
    business_id only — cross-tenant access is blocked at the match stage.
    """
    ctx = await _ctx(request)
    cursor = _db.unified_inbox.find(
        {"thread_id": thread_id, "business_id": ctx["business_id"]},
        {"_id": 0},
    ).sort("timestamp", 1).limit(max(1, min(limit, 200)))
    msgs: List[Dict[str, Any]] = []
    async for m in cursor:
        ts = m.get("timestamp")
        if isinstance(ts, datetime):
            m["timestamp"] = ts.isoformat()
        # Mask sender in payload too — UI never sees raw contact.
        m["from_handle"] = _mask_handle(m.get("from"), m.get("channel"))
        m.pop("from", None)
        msgs.append(m)

    # Mark inbound as read once viewed.
    try:
        await _db.unified_inbox.update_many(
            {"thread_id": thread_id, "business_id": ctx["business_id"],
             "direction": "inbound", "read": False},
            {"$set": {"read": True}},
        )
    except Exception:
        pass

    return {"ok": True, "thread_id": thread_id, "count": len(msgs), "messages": msgs}


@router.post("/inbox/reply")
async def inbox_reply(request: Request, body: Dict[str, Any] = Body(...)):
    """Send a reply on the appropriate channel and log it.

    Body: {thread_id, message, channel?, to?}
      - channel: optional override; otherwise auto-detected from latest
        inbound message on the thread.
      - to: optional override; otherwise the last inbound `from`.
    """
    ctx = await _ctx(request)
    thread_id = (body.get("thread_id") or "").strip()
    message = (body.get("message") or "").strip()
    channel_override = (body.get("channel") or "").lower().strip() or None
    to_override = (body.get("to") or "").strip() or None
    if not thread_id or not message:
        raise HTTPException(400, "thread_id and message are required")

    # Auto-detect channel + recipient from the latest INBOUND row.
    last_in = await _db.unified_inbox.find_one(
        {"thread_id": thread_id, "business_id": ctx["business_id"],
         "direction": "inbound"},
        {"_id": 0, "channel": 1, "from": 1},
        sort=[("timestamp", -1)],
    )
    channel = channel_override or (last_in or {}).get("channel")
    to_addr = to_override or (last_in or {}).get("from") or ""
    if not channel:
        raise HTTPException(400, "could not determine channel for thread")
    if not to_addr:
        raise HTTPException(400, "could not determine recipient for thread")

    sent_via = None
    sent_ok = False
    send_err: Optional[str] = None
    try:
        if channel == "email":
            sent_via = "resend"
            from services.inbound_reply_handler import _send_reply_email
            res = await _send_reply_email(
                to_addr=to_addr,
                subject=(body.get("subject") or "Re: your message"),
                body=message,
            )
            sent_ok = bool(res.get("ok"))
            send_err = res.get("error") if not sent_ok else None
        elif channel == "sms":
            sent_via = "twilio_sms"
            sent_ok, send_err = await _send_sms(to_addr, message)
        elif channel == "whatsapp":
            sent_via = "twilio_whatsapp"  # WHAPI fallback handled internally
            sent_ok, send_err = await _send_whatsapp(to_addr, message)
        else:
            raise HTTPException(400, f"unsupported channel: {channel}")
    except HTTPException:
        raise
    except Exception as e:
        send_err = str(e)[:200]

    # Always log to unified_inbox (even on send fail — audit trail).
    from services.inbox_writer import write_inbox
    await write_inbox(
        _db,
        channel=channel,
        direction="outbound",
        sender="customer",  # masked — never the customer's real email
        message=message,
        thread_id=thread_id,
        business_id=ctx["business_id"],
        sent_via=sent_via,
    )
    # Touchpoint event (engagement timeline).
    try:
        await _db.touchpoints.insert_one({
            "lead_id": thread_id,
            "tenant_id": ctx["business_id"],
            "channel": channel,
            "direction": "outbound",
            "status": "sent" if sent_ok else "send_failed",
            "via": sent_via,
            "ts": datetime.now(timezone.utc),
        })
    except Exception:
        pass

    return {
        "ok": sent_ok,
        "channel": channel,
        "sent_via": sent_via,
        "error": send_err,
        "thread_id": thread_id,
    }


async def _send_sms(to_addr: str, body: str) -> tuple[bool, Optional[str]]:
    sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
    tok = os.environ.get("TWILIO_AUTH_TOKEN", "")
    src = os.environ.get("TWILIO_PHONE_NUMBER", "") or os.environ.get("TWILIO_SMS_FROM", "")
    if not (sid and tok and src):
        return False, "TWILIO_* env vars missing"
    try:
        import httpx
        async with httpx.AsyncClient(timeout=12) as c:
            r = await c.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
                data={"To": to_addr, "From": src, "Body": body},
                auth=(sid, tok),
            )
        if r.status_code in (200, 201):
            return True, None
        return False, f"{r.status_code}: {r.text[:200]}"
    except Exception as e:
        return False, str(e)[:200]


async def _send_whatsapp(to_addr: str, body: str) -> tuple[bool, Optional[str]]:
    # Prefer Twilio WABA, fall back to WHAPI.
    sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
    tok = os.environ.get("TWILIO_AUTH_TOKEN", "")
    waba_from = os.environ.get("TWILIO_WHATSAPP_FROM", "")
    if sid and tok and waba_from:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=12) as c:
                r = await c.post(
                    f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
                    data={
                        "To": f"whatsapp:{to_addr}" if not to_addr.startswith("whatsapp:") else to_addr,
                        "From": waba_from if waba_from.startswith("whatsapp:") else f"whatsapp:{waba_from}",
                        "Body": body,
                    },
                    auth=(sid, tok),
                )
            if r.status_code in (200, 201):
                return True, None
            return False, f"twilio_waba {r.status_code}: {r.text[:200]}"
        except Exception as e:
            return False, str(e)[:200]
    # WHAPI fallback
    whapi = os.environ.get("WHAPI_API_TOKEN", "")
    if not whapi:
        return False, "no whatsapp provider configured"
    try:
        import httpx
        async with httpx.AsyncClient(timeout=12) as c:
            r = await c.post(
                "https://gate.whapi.cloud/messages/text",
                headers={"Authorization": f"Bearer {whapi}", "Content-Type": "application/json"},
                json={"to": to_addr, "body": body},
            )
        if r.status_code in (200, 201):
            return True, None
        return False, f"whapi {r.status_code}: {r.text[:200]}"
    except Exception as e:
        return False, str(e)[:200]


def _mask_handle(raw: str, channel: Optional[str]) -> str:
    """Convert sender into a privacy-safe handle for the customer view.

    Email:    "user@example.com"  → "u***@example.com"
    Phone:    "+14165551234"      → "+1·••••1234"
    Other:    "Anonymous"
    """
    raw = (raw or "").strip()
    if not raw:
        return "—"
    if channel == "email" or "@" in raw:
        try:
            local, dom = raw.split("@", 1)
            local = local[:1] + "***" if len(local) >= 1 else "***"
            return f"{local}@{dom}"
        except Exception:
            return "anon@masked"
    # Treat as phone-like
    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) >= 4:
        return f"+{digits[0]}·••••{digits[-4:]}"
    return "anon"


# ═══════════════════════════════════════════════════════════════════════
# TILE A — "AUREM Working For You"
# ═══════════════════════════════════════════════════════════════════════
@router.get("/results-summary")
async def results_summary(request: Request):
    """4 KPIs over the last 30 days, no PII."""
    ctx = await _ctx(request)
    bin_id = ctx["business_id"]
    since = datetime.now(timezone.utc) - timedelta(days=30)

    # Leads found — Scout writes here. We also count campaign_leads as a fallback.
    leads_found = 0
    try:
        leads_found = await _db.campaign_leads.count_documents({
            "tenant_id": bin_id, "created_at": {"$gte": since},
        })
    except Exception:
        pass
    if leads_found == 0:
        try:
            leads_found = await _db.agent_actions.count_documents({
                "tenant_id": bin_id, "action_type": {"$in": ["scout_found", "lead_discovered"]},
                "ts": {"$gte": since},
            })
        except Exception:
            pass

    # Outreach sent — touchpoints with direction=outbound + status in {sent, delivered}
    outreach_sent = 0
    try:
        outreach_sent = await _db.touchpoints.count_documents({
            "tenant_id": bin_id,
            "direction": "outbound",
            "ts": {"$gte": since},
        })
    except Exception:
        pass

    # Responses — inbound touchpoints OR unified_inbox inbound.
    responses = 0
    try:
        responses = await _db.unified_inbox.count_documents({
            "business_id": bin_id,
            "direction": "inbound",
            "timestamp": {"$gte": since},
        })
    except Exception:
        pass
    if responses == 0:
        try:
            responses = await _db.touchpoints.count_documents({
                "tenant_id": bin_id, "direction": "inbound", "ts": {"$gte": since},
            })
        except Exception:
            pass

    # Meetings booked — bookings collection.
    meetings = 0
    try:
        meetings = await _db.bookings.count_documents({
            "business_id": bin_id,
            "created_at": {"$gte": since},
        })
    except Exception:
        pass

    return {
        "ok": True,
        "window_days": 30,
        "leads_found": leads_found,
        "outreach_sent": outreach_sent,
        "responses": responses,
        "meetings_booked": meetings,
    }


# ═══════════════════════════════════════════════════════════════════════
# TILE B — "Recent Activity" (anonymous outcomes feed)
# ═══════════════════════════════════════════════════════════════════════
@router.get("/results-activity")
async def results_activity(request: Request, limit: int = 12):
    """Anonymous outcome lines from agent_actions over the last 14 days.

    Returns lines like "Found 3 leads in Mississauga" — never lead names
    or contact details. Aggregates by (action_type, city, day).
    """
    ctx = await _ctx(request)
    bin_id = ctx["business_id"]
    since = datetime.now(timezone.utc) - timedelta(days=14)

    # Aggregate agent_actions by (action_type, city, day)
    pipeline = [
        {"$match": {
            "tenant_id": bin_id, "ts": {"$gte": since},
        }},
        {"$addFields": {
            "_day": {"$dateToString": {"format": "%Y-%m-%d", "date": "$ts"}},
        }},
        {"$group": {
            "_id": {
                "day": "$_day",
                "action_type": "$action_type",
                "city": {"$ifNull": ["$city", ""]},
            },
            "count": {"$sum": 1},
            "last_ts": {"$max": "$ts"},
        }},
        {"$sort": {"last_ts": -1}},
        {"$limit": max(1, min(limit, 50))},
    ]
    items: List[Dict[str, Any]] = []
    try:
        async for r in _db.agent_actions.aggregate(pipeline):
            k = r["_id"]
            line = _render_activity_line(
                action_type=k.get("action_type") or "",
                count=int(r["count"]),
                city=k.get("city") or "",
            )
            items.append({
                "line": line,
                "count": int(r["count"]),
                "action_type": k.get("action_type"),
                "at": r["last_ts"].isoformat() if r.get("last_ts") else None,
            })
    except Exception as e:
        logger.warning(f"[results-activity] aggregate failed: {e}")

    return {"ok": True, "window_days": 14, "items": items}


def _render_activity_line(action_type: str, count: int, city: str) -> str:
    """Render an anonymous activity line. NO names, NO contacts."""
    n = count
    plural = "s" if n != 1 else ""
    loc = f" in {city}" if city else ""
    pretty = {
        "scout_found": f"Found {n} lead{plural}{loc}",
        "lead_discovered": f"Discovered {n} lead{plural}{loc}",
        "email_sent": f"Sent {n} email{plural}",
        "sms_sent": f"Sent {n} SMS{plural}",
        "whatsapp_sent": f"Sent {n} WhatsApp message{plural}",
        "followup_sent": f"Sent {n} follow-up{plural}",
        "voice_call_made": f"Made {n} voice call{plural}",
        "lead_qualified": f"Qualified {n} lead{plural}",
        "lead_moved_closer": f"{n} lead{plural} moved to closer",
        "meeting_booked": f"Booked {n} meeting{plural}",
        "site_built": f"Built {n} website{plural}",
        "review_request_sent": f"Sent {n} review request{plural}",
    }
    return pretty.get(action_type, f"{action_type.replace('_', ' ').title()} ×{n}")


# ═══════════════════════════════════════════════════════════════════════
# TILE C — "Pipeline This Month" (lead counts by stage)
# ═══════════════════════════════════════════════════════════════════════
PIPELINE_STAGES = [
    ("Discovered",  ["discovered", "new", "scouted"]),
    ("Contacted",   ["contacted", "outreach_sent", "warming"]),
    ("Responded",   ["responded", "engaged", "replied"]),
    ("Interested",  ["interested", "qualified", "hot"]),
    ("Closed",      ["closed", "won", "converted", "customer"]),
]


@router.get("/results-pipeline")
async def results_pipeline(request: Request):
    """Lead count by pipeline stage this month. Counts only — no names.

    Uses `campaign_leads.lifecycle_stage` as the source of truth.
    """
    ctx = await _ctx(request)
    bin_id = ctx["business_id"]
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    out: List[Dict[str, Any]] = []
    total = 0
    for label, aliases in PIPELINE_STAGES:
        cnt = 0
        try:
            cnt = await _db.campaign_leads.count_documents({
                "tenant_id": bin_id,
                "lifecycle_stage": {"$in": aliases},
                "created_at": {"$gte": month_start},
            })
        except Exception:
            pass
        total += cnt
        out.append({"stage": label, "count": cnt})

    return {
        "ok": True,
        "month_start": month_start.isoformat(),
        "total": total,
        "stages": out,
    }
