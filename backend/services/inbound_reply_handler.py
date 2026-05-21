"""
Inbound Reply Handler — iter 282al-9 (auto-warm-reply).

When a customer replies to an outreach email, this service:
  1. Matches the inbound email to a lead (by from-address)
  2. Classifies intent: positive / question / opt_out / negative / unknown
  3. Logs the reply to db.inbound_replies (TTL 365d)
  4. For POSITIVE intent → composes a warm value-first reply via
     outreach_composer and sends it through Resend
  5. For OPT_OUT → adds to DNC, no reply
  6. For NEGATIVE → flag for human review, no auto-reply
  7. Updates lead.lifecycle_stage to "engaged" + boosts flame_score
  8. Emits to A2A bus so morning brief picks it up

Pipe:
  Resend Inbound webhook OR IMAP poller → POST /api/email/inbound → here.

Public surface:
  • handle_inbound_reply(db, payload) → dict
  • classify_intent(text) → str
  • compose_warm_reply(lead, inbound_text) → dict (subject, body)
  • ensure_inbound_indexes(db)
"""
from __future__ import annotations

import logging
import os
import re
import uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Intent keywords (fast pre-classification before LLM)
# ─────────────────────────────────────────────────────────────────────
POSITIVE_KEYWORDS = (
    "yes", "interested", "tell me more", "how do i proceed",
    "how do we proceed", "what's the next step", "whats the next step",
    "send me more", "love it", "looks great", "that's great",
    "looks good", "i'm in", "lets do it", "let's do it",
    "omg", "amazing", "wow", "perfect", "sounds good",
    "happy to chat", "happy to talk", "sign me up", "go ahead",
)

QUESTION_KEYWORDS = (
    "how much", "what does it cost", "pricing", "price",
    "what do you do", "what is this", "who are you", "is this real",
    "do you actually", "what's included", "whats included",
)

OPT_OUT_KEYWORDS = (
    "stop", "unsubscribe", "remove me", "do not contact",
    "don't contact", "dont email", "leave me alone",
    "spam", "not interested", "no thanks", "no thank you",
)

NEGATIVE_KEYWORDS = (
    "scam", "fraud", "fake", "bullshit", "bs", "lawyer",
    "report you", "lawsuit", "sue you", "casl violation",
)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def classify_intent(text: str) -> str:
    """Lightweight rule-based classifier. Returns one of:
    positive | question | opt_out | negative | unknown."""
    t = _norm(text)
    if not t:
        return "unknown"
    # Opt-out is highest priority — never auto-reply
    for kw in OPT_OUT_KEYWORDS:
        if kw in t:
            return "opt_out"
    for kw in NEGATIVE_KEYWORDS:
        if kw in t:
            return "negative"
    for kw in POSITIVE_KEYWORDS:
        if kw in t:
            return "positive"
    for kw in QUESTION_KEYWORDS:
        if kw in t:
            return "question"
    # Single-word "yes"
    if t in ("y", "ok", "okay", "sure", "absolutely"):
        return "positive"
    return "unknown"


# ─────────────────────────────────────────────────────────────────────
# Lead lookup
# ─────────────────────────────────────────────────────────────────────
async def _find_lead_by_email(db, email: str) -> dict | None:
    if not email or db is None:
        return None
    e = email.strip().lower()
    try:
        return await db.campaign_leads.find_one(
            {"email": {"$regex": f"^{re.escape(e)}$", "$options": "i"}},
            projection={"_id": 0},
        )
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────
# Warm reply composer
# ─────────────────────────────────────────────────────────────────────
async def compose_warm_reply(lead: dict, inbound_text: str,
                              site_url: str | None = None) -> dict:
    """Compose a value-first warm reply. Wraps outreach_composer with the
    inbound message as context. Falls back to a hand-tuned template when
    the LLM gateway is unreachable."""
    biz = lead.get("business_name") or "your business"
    city = lead.get("city") or ""
    cat = lead.get("category") or "business"

    # Hand-tuned fallback (used when LLM unreachable). Crafted to be
    # value-first, Canadian-spelled, CASL-defensible.
    fallback_subject = f"Re: {biz} — let's get you live"
    fallback_body = (
        f"Hi! Thanks for getting back so quickly — happy to hear from you.\n\n"
        f"Here's how we proceed:\n"
        f"  1. Tell me what services you'd like featured (just the top 3-5 "
        f"are fine — I can fill the rest from your existing info).\n"
        f"  2. Any photos? Send 2-3 if you have them. If not, no worries — "
        f"the preview already uses your branding.\n"
        f"  3. I'll publish the final version to a permanent address "
        + (f"and confirm with you in {city or 'your area'} within 24 hours."
            if city else "and confirm with you within 24 hours.")
        + "\n\n"
    )
    if site_url:
        fallback_body += (
            f"Your live preview right now: {site_url}\n\n"
        )
    fallback_body += (
        f"Reply with whatever info you have — even a quick voice memo "
        f"works. I'll handle the rest.\n\n"
        f"— TJ at AUREM\n"
        f"🍁 Canadian-owned, Mississauga ON · CASL Compliant\n"
        f"7221 Sigsbee Dr, Mississauga ON L4T 3L6 · Reply STOP to opt out."
    )

    api_key = os.environ.get("EMERGENT_LLM_KEY", "").strip()
    if not api_key:
        return {"subject": fallback_subject, "body": fallback_body,
                "fallback_used": True}

    try:
        from services.llm_gateway import call_llm_with_meta
        system = (
            "You are TJ at AUREM, a Canadian-owned outreach platform "
            "based in Mississauga, ON. A prospect just replied to your "
            "free-website-preview email with positive intent.\n\n"
            "Write a warm, helpful, VALUE-FIRST reply that:\n"
            "  • Acknowledges their reply (1 short sentence)\n"
            "  • Lays out the next 3 concrete steps to get them live\n"
            "  • Asks for the minimum info you need (services, photos, "
            "hours) — but explicitly say none of it is required\n"
            "  • Confirms the working preview URL if provided\n"
            "  • Signs off as TJ at AUREM\n"
            "  • Includes the Canadian footer with full address + STOP\n\n"
            "Tone: friendly, not pushy. Canadian spelling. Max 160 words. "
            "Return JSON only: {\"subject\": \"...\", \"body\": \"...\"}"
        )
        prompt = (
            f"Business: {biz} | City: {city} | Category: {cat}\n"
            f"Their reply: \"{(inbound_text or '')[:600]}\"\n"
            + (f"Working preview URL: {site_url}\n" if site_url else "")
            + "\nWrite the warm reply now. JSON only."
        )
        gw = await call_llm_with_meta(system, prompt, max_tokens=500)
        if not gw.get("ok"):
            return {"subject": fallback_subject, "body": fallback_body,
                    "fallback_used": True}
        import json as _json
        raw = (gw.get("content") or "").strip()
        # Strip code fences if present
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw,
                      flags=re.IGNORECASE | re.MULTILINE)
        try:
            parsed = _json.loads(raw)
        except Exception:
            m = re.search(r"\{.*\}", raw, re.S)
            parsed = _json.loads(m.group(0)) if m else {}
        subject = parsed.get("subject") or fallback_subject
        body = parsed.get("body") or fallback_body
        # Always guarantee CASL footer presence
        if "stop" not in body.lower():
            body = body.rstrip() + "\n\nReply STOP to opt out. AUREM, Mississauga ON."
        return {"subject": subject, "body": body, "fallback_used": False,
                "provider": gw.get("provider")}
    except Exception as e:
        logger.warning(f"[inbound] compose LLM failed: {e}")
        return {"subject": fallback_subject, "body": fallback_body,
                "fallback_used": True}


# ─────────────────────────────────────────────────────────────────────
# Site URL resolver — picks the WORKING URL for the lead
# ─────────────────────────────────────────────────────────────────────
async def _resolve_site_url(db, lead: dict) -> str | None:
    """Find the lead's auto-built site and return a *reachable* URL.
    Prefers the published live_url (when DNS is wired), falls back to
    the always-live path-based URL `/api/sites/{slug}`."""
    if db is None or not lead:
        return None
    try:
        site = await db.auto_built_sites.find_one(
            {"lead_id": lead.get("lead_id")},
            projection={"_id": 0, "slug": 1, "live_url": 1,
                         "publish_status": 1},
            sort=[("ts", -1)],
        )
    except Exception:
        site = None
    if not site:
        return None
    slug = site.get("slug")
    if site.get("publish_status") == "live" and site.get("live_url"):
        return site["live_url"]
    if slug:
        return f"https://aurem.live/api/sites/{slug}"
    return None


# ─────────────────────────────────────────────────────────────────────
# Sender
# ─────────────────────────────────────────────────────────────────────
async def _send_reply_email(to_addr: str, subject: str, body: str,
                              in_reply_to: str | None = None) -> dict:
    """Send via Resend. Returns {ok, id?, error?}."""
    api_key = os.environ.get("RESEND_API_KEY", "").strip()
    if not api_key:
        return {"ok": False, "error": "RESEND_API_KEY not set"}
    from_addr = os.environ.get("RESEND_FROM_EMAIL",
                                "ORA <ora@aurem.live>")
    try:
        import httpx
        headers = {"Authorization": f"Bearer {api_key}",
                   "Content-Type": "application/json"}
        # Convert plain-text body to simple HTML (preserve newlines).
        html = (
            "<div style='font-family:Arial,sans-serif;font-size:14px;"
            "line-height:1.6;color:#222'>"
            + body.replace("\n", "<br/>")
            + "</div>"
        )
        payload = {
            "from": from_addr, "to": [to_addr],
            "subject": subject, "html": html, "text": body,
        }
        if in_reply_to:
            payload["headers"] = {"In-Reply-To": in_reply_to,
                                   "References": in_reply_to}
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post("https://api.resend.com/emails",
                              json=payload, headers=headers)
            if r.status_code in (200, 201):
                d = r.json()
                return {"ok": True, "id": d.get("id")}
            return {"ok": False, "error": f"{r.status_code}: {r.text[:200]}"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


# ─────────────────────────────────────────────────────────────────────
# Public — handle_inbound_reply
# ─────────────────────────────────────────────────────────────────────
async def handle_inbound_reply(db, payload: dict) -> dict:
    """Main entry. payload = normalized inbound email:
        {from, to, subject, text, html?, in_reply_to?, references?}

    Returns {received, intent, matched_lead, auto_replied, reply_id?}.
    """
    from_addr = (payload.get("from") or "").strip().lower()
    text = payload.get("text") or payload.get("html") or ""
    subject = payload.get("subject") or ""
    in_reply_to = payload.get("in_reply_to") or ""
    received_at = datetime.now(timezone.utc)
    msg_id = str(uuid.uuid4())

    intent = classify_intent(f"{subject}\n{text}")
    lead = await _find_lead_by_email(db, from_addr)

    record = {
        "message_id": msg_id,
        "from": from_addr,
        "to": payload.get("to"),
        "subject": subject[:300],
        "text": (text or "")[:5000],
        "in_reply_to": in_reply_to,
        "intent": intent,
        "lead_id": (lead or {}).get("lead_id"),
        "matched_lead": bool(lead),
        "received_at": received_at,
        "auto_replied": False,
        "reply_id": None,
    }
    if db is not None:
        try:
            await db.inbound_replies.insert_one(dict(record))
        except Exception as e:
            logger.debug(f"[inbound] insert failed: {e}")
        # iter 322aj — Mirror to db.unified_inbox so customer-facing
        # OmnichannelHub auto-displays inbound emails alongside SMS/WA.
        try:
            from services.inbox_writer import write_inbox
            await write_inbox(
                db,
                channel="email",
                direction="inbound",
                sender=from_addr,
                message=text or subject or "",
                thread_id=(lead or {}).get("lead_id") or "",
                business_id=(lead or {}).get("tenant_id")
                            or (lead or {}).get("business_id"),
            )
        except Exception as e:
            logger.debug(f"[inbound] unified_inbox mirror failed: {e}")

    # Always update lead → engaged + flame boost on any reply
    if lead and db is not None:
        try:
            from services.lead_lifecycle import transition
            await transition(db, lead["lead_id"], "engaged",
                             reason="email_reply", by="inbound_handler",
                             force=True)
        except Exception as e:
            logger.debug(f"[inbound] transition failed: {e}")
        try:
            inc = 30 if intent == "positive" else 10
            await db.campaign_leads.update_one(
                {"lead_id": lead["lead_id"]},
                {"$inc": {"flame_score_boost": inc}},
            )
        except Exception:
            pass

    # Opt-out → DNC + no reply
    if intent == "opt_out":
        try:
            from services.lead_dedup import process_stop_reply
            await process_stop_reply(db, email=from_addr)
        except Exception as e:
            logger.debug(f"[inbound] DNC add failed: {e}")
        return {"received": True, "intent": intent,
                "matched_lead": bool(lead), "auto_replied": False,
                "action": "added_to_dnc"}

    # Negative → flag for human, no auto-reply
    if intent == "negative":
        if db is not None:
            try:
                await db.sentinel_alerts.insert_one({
                    "kind": "negative_inbound_reply",
                    "from": from_addr,
                    "lead_id": (lead or {}).get("lead_id"),
                    "subject": subject[:200],
                    "text": (text or "")[:500],
                    "ts": received_at,
                })
            except Exception:
                pass
        return {"received": True, "intent": intent,
                "matched_lead": bool(lead), "auto_replied": False,
                "action": "flagged_for_human"}

    # Positive or question → auto-warm-reply (gated on env flag)
    auto_enabled = os.environ.get("INBOUND_AUTO_REPLY", "true").lower() \
        not in ("0", "false", "no")
    if not auto_enabled or not lead:
        return {"received": True, "intent": intent,
                "matched_lead": bool(lead), "auto_replied": False,
                "action": "logged"}

    if intent not in ("positive", "question"):
        return {"received": True, "intent": intent,
                "matched_lead": True, "auto_replied": False,
                "action": "logged_unknown"}

    site_url = await _resolve_site_url(db, lead)
    composed = await compose_warm_reply(lead, text, site_url)
    reply_subject = composed.get("subject")
    if not (reply_subject or "").lower().startswith("re:"):
        reply_subject = f"Re: {subject}" if subject else reply_subject

    send = await _send_reply_email(
        to_addr=from_addr,
        subject=reply_subject,
        body=composed.get("body") or "",
        in_reply_to=in_reply_to or None,
    )

    if db is not None:
        try:
            await db.inbound_replies.update_one(
                {"message_id": msg_id},
                {"$set": {
                    "auto_replied": bool(send.get("ok")),
                    "reply_id":     send.get("id"),
                    "reply_subject": reply_subject,
                    "reply_provider": composed.get("provider"),
                    "reply_fallback": bool(composed.get("fallback_used")),
                    "reply_error": send.get("error") if not send.get("ok") else None,
                }},
            )
        except Exception:
            pass

    # iter 282al-10 — Telegram hot-lead ping (positive intent only).
    # Fires regardless of auto-reply send outcome so the founder sees the
    # signal even if Resend hiccups.
    # iter 325d — ALSO set hot_lead_flag on the lead row + fire the
    # shared founder alert (WhatsApp + Telegram via services/hot_lead_alerts).
    # The shared service replaces the old standalone autopilot telegram ping
    # AND wires up the WhatsApp channel that previously only fired from
    # sample-page visits.
    if intent == "positive":
        # Mark the lead as hot so followup_ora.py auto-skips it (sequence
        # pause) and the CRM badges the row.
        if lead and db is not None:
            try:
                await db.campaign_leads.update_one(
                    {"lead_id": lead["lead_id"]},
                    {"$set": {
                        "hot_lead_flag": True,
                        "hot_lead_source": "email_reply",
                        "hot_lead_at": received_at,
                        "status": "interested",
                    }},
                )
            except Exception as e:
                logger.debug(f"[inbound] hot_lead_flag set failed: {e}")
        # Founder alert across WhatsApp + Telegram (shared service).
        try:
            from services.hot_lead_alerts import fire_hot_lead_admin_alert
            preview = (text or "").strip().replace("\n", " ")
            if len(preview) > 140:
                preview = preview[:140].rstrip() + "…"
            biz = (lead.get("business_name") if lead else None) or from_addr
            alert_result = await fire_hot_lead_admin_alert(
                db,
                business_name=biz,
                lead_id=(lead or {}).get("lead_id"),
                source="email_reply",
                detail=preview,
            )
            if db is not None:
                try:
                    await db.inbound_replies.update_one(
                        {"message_id": msg_id},
                        {"$set": {
                            "founder_alert_fired": True,
                            "founder_alert_telegram_ok": alert_result.get("telegram", {}).get("ok"),
                            "founder_alert_whatsapp_ok": alert_result.get("whatsapp", {}).get("ok"),
                        }},
                    )
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"[inbound] hot_lead alert failed: {e}")

    return {
        "received": True, "intent": intent, "matched_lead": True,
        "auto_replied": bool(send.get("ok")),
        "reply_id": send.get("id"),
        "site_url": site_url,
        "fallback_used": bool(composed.get("fallback_used")),
        "action": "auto_replied" if send.get("ok") else "send_failed",
    }


# ─────────────────────────────────────────────────────────────────────
# Indexes
# ─────────────────────────────────────────────────────────────────────
async def ensure_inbound_indexes(db) -> None:
    if db is None:
        return
    try:
        await db.inbound_replies.create_index(
            [("received_at", 1)],
            expireAfterSeconds=365 * 24 * 3600,
            name="received_at_ttl",
        )
        await db.inbound_replies.create_index(
            [("from", 1), ("received_at", -1)], name="from_received",
        )
        await db.inbound_replies.create_index(
            [("intent", 1), ("received_at", -1)], name="intent_received",
        )
    except Exception as e:
        logger.debug(f"[inbound] index skip: {e}")


__all__ = [
    "classify_intent",
    "compose_warm_reply",
    "handle_inbound_reply",
    "ensure_inbound_indexes",
    "POSITIVE_KEYWORDS",
    "OPT_OUT_KEYWORDS",
]
