"""
AUREM A2A Chain — Scout → Architect → Envoy → Closer
=====================================================
Autonomous outreach chain that turns a fresh `campaign_leads` row into
a real outbound touch with zero human intervention.

Stages (each runs once per 60-s cycle, bounded by _BATCH_SIZE):

  Architect
    Reads every `campaign_leads` with `status == "new"` that has no
    matching `execution_plans` row yet. Uses `llm_call_with_failover`
    to draft a personalised outreach message, chooses the best
    channel from what we can actually send, writes
    `execution_plans` with `confidence_score ∈ [0,100]`, and emits
    `bus.emit("architect", "plan_written", …)`.

  Envoy
    Picks `execution_plans` with `confidence_score > 70`, no delivery
    attempt yet, and `campaign_leads.status != "contacted"`. Sends
    via Resend (email) or Twilio (voice). On success it flips the
    lead to `"contacted"`, appends the attempt to
    `campaign_leads.outreach_history`, writes an `activity_feed` row,
    and emits `bus.emit("envoy", "delivered", …)`.

  Closer
    Scans `campaign_leads` with `status == "replied"` that have never
    been scored by Closer. Uses `llm_call_with_failover` to score
    the inbound reply. Scores > 80 go to `activity_feed` with
    `priority: "hot"` so the founder sees them surfaced in the
    Control Center, and emits `bus.emit("closer", "hot_reply", …)`.

Design guarantees:
  - NO self-HTTP calls — everything is a direct Python import.
  - Every LLM call routes through
    `services.model_failover.llm_call_with_failover` (free-first,
    graceful degrade).
  - Idempotent: rerunning a stage on the same lead is safe.
  - Failures in one stage never break the others (each stage is
    wrapped in its own try/except).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

CYCLE_SECONDS = 60
_BATCH_SIZE = 25
_ARCHITECT_CONFIDENCE_THRESHOLD = 70
_CLOSER_HOT_THRESHOLD = 80

# Resend free tier caps at 2-5 requests/sec. Space email sends out so
# we never hit their rate limiter. 250 ms ≈ 4 req/s — safely below 5.
_RESEND_PACING_SEC = 0.25
# Twilio REST API is generous but not infinite; small pacing helps if a
# cycle has many voice fallbacks queued.
_TWILIO_PACING_SEC = 0.15

# Stage names used as the "from_agent" label on the bus.
_ARCH = "architect"
_ENVOY = "envoy"
_CLOSER = "closer"


# ═══════════════════════════════════════════════════════════════════════
# Small helpers
# ═══════════════════════════════════════════════════════════════════════
def _now():
    return datetime.now(timezone.utc)


def _now_iso():
    return _now().isoformat()


def _resend_client():
    try:
        import resend as _r
    except ImportError:
        return None
    key = os.environ.get("RESEND_API_KEY", "").strip()
    if not key:
        return None
    _r.api_key = key
    return _r


def _twilio_client():
    try:
        from twilio.rest import Client
    except ImportError:
        return None
    sid = os.environ.get("TWILIO_ACCOUNT_SID", "").strip()
    tok = os.environ.get("TWILIO_AUTH_TOKEN", "").strip()
    if not sid or not tok:
        return None
    try:
        return Client(sid, tok)
    except Exception:
        return None


def _extract_json_block(raw: str) -> Optional[Dict[str, Any]]:
    """Pull the first `{…}` JSON object from an LLM response."""
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        pass
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def _pick_channel(lead: Dict[str, Any]) -> Optional[str]:
    """Choose the best channel we can ACTUALLY send on right now."""
    email = (lead.get("email") or "").strip()
    phone = (lead.get("phone") or "").strip()
    if email and _resend_client() is not None:
        return "email"
    if phone and _twilio_client() is not None:
        return "voice"
    return None


# ═══════════════════════════════════════════════════════════════════════
# Architect
# ═══════════════════════════════════════════════════════════════════════
async def _architect_stage(db) -> Dict[str, int]:
    """Draft plans for every fresh `campaign_leads` row without one."""
    from services.model_failover import llm_call_with_failover
    from services.a2a_bus import bus

    cursor = db.campaign_leads.find(
        {"status": "new"}, {"_id": 0}
    ).sort("created_at", 1).limit(_BATCH_SIZE)
    leads = await cursor.to_list(_BATCH_SIZE)

    drafted = 0
    skipped = 0
    for lead in leads:
        lead_id = lead.get("lead_id")
        if not lead_id:
            continue

        existing_plan = await db.execution_plans.find_one(
            {"lead_id": lead_id}, {"_id": 1}
        )
        if existing_plan:
            skipped += 1
            continue

        channel = _pick_channel(lead)
        if channel is None:
            # We can't reach this lead with any configured channel — record
            # a plan with confidence=0 so we never re-process it.
            await db.execution_plans.insert_one({
                "plan_id": f"plan-{uuid.uuid4().hex[:10]}",
                "lead_id": lead_id,
                "tenant_id": lead.get("tenant_id"),
                "recommended_channel": None,
                "message_draft": None,
                "subject_line": None,
                "confidence_score": 0,
                "reason": "no_reachable_channel",
                "status": "drafted",
                "created_at": _now_iso(),
            })
            continue

        business = lead.get("business_name") or "there"
        category = lead.get("category") or "local business"
        city = lead.get("location") or ""
        website = lead.get("website_url") or ""
        issues_count = lead.get("issues_count", 0)

        system = (
            "You are AUREM's outreach architect. Draft a single first-touch "
            "outbound message for a small local business. Keep it under 80 "
            "words, helpful, no marketing fluff, no 'FREE', no 'limited "
            "time', no 'trial'. Offer one concrete observation + one clear "
            "next step. Return STRICT JSON only with keys: "
            '{"subject_line": str (max 60 chars, email only else empty), '
            '"message": str, "confidence_score": int 0-100, "reason": str}. '
            "confidence_score reflects how likely this message will get a reply "
            "given the lead's data quality and personalisation fit."
        )
        prompt = (
            f"Business: {business}\n"
            f"Category: {category}\n"
            f"City: {city}\n"
            f"Website: {website or 'not provided'}\n"
            f"Known site issues detected: {issues_count}\n"
            f"Channel to draft for: {channel}\n\n"
            "Return JSON only."
        )

        try:
            resp = await llm_call_with_failover(
                prompt=prompt, system=system, max_tokens=400, timeout=8.0,
            )
        except Exception as e:
            logger.warning(f"[a2a-chain/architect] LLM failed for {lead_id}: {e}")
            continue

        if resp.get("degraded"):
            logger.info(f"[a2a-chain/architect] LLM degraded for {lead_id} — skip this cycle")
            continue

        parsed = _extract_json_block(resp.get("content", "")) or {}
        msg = (parsed.get("message") or "").strip()
        if not msg:
            logger.warning(f"[a2a-chain/architect] empty message for {lead_id}")
            continue

        conf = int(parsed.get("confidence_score") or 0)
        conf = max(0, min(100, conf))
        subject = (parsed.get("subject_line") or "").strip()[:60] or f"Quick note for {business}"

        plan_doc = {
            "plan_id": f"plan-{uuid.uuid4().hex[:10]}",
            "lead_id": lead_id,
            "tenant_id": lead.get("tenant_id"),
            "recommended_channel": channel,
            "message_draft": msg[:2000],
            "subject_line": subject if channel == "email" else None,
            "confidence_score": conf,
            "reason": (parsed.get("reason") or "")[:300],
            "model_used": resp.get("model_used"),
            "status": "drafted",
            "created_at": _now_iso(),
        }
        await db.execution_plans.insert_one(plan_doc)
        drafted += 1

        try:
            await bus.emit(_ARCH, "plan_written", {
                "plan_id": plan_doc["plan_id"],
                "lead_id": lead_id,
                "channel": channel,
                "confidence_score": conf,
            })
        except Exception as e:
            logger.debug(f"[a2a-chain/architect] bus emit failed: {e}")

    return {"stage": _ARCH, "drafted": drafted, "skipped_existing": skipped}


# ═══════════════════════════════════════════════════════════════════════
# Envoy
# ═══════════════════════════════════════════════════════════════════════
async def _envoy_send_email(lead: Dict[str, Any], plan: Dict[str, Any]) -> Dict[str, Any]:
    resend = _resend_client()
    if resend is None:
        return {"ok": False, "error": "resend_not_configured"}
    from_addr = os.environ.get("RESEND_FROM_EMAIL", "AUREM <hello@aurem.live>")
    to = (lead.get("email") or "").strip()
    subject = plan.get("subject_line") or f"Quick note for {lead.get('business_name','')}"
    body_text = plan.get("message_draft") or ""
    html = "<p>" + body_text.replace("\n", "<br/>") + "</p>"

    def _do_send():
        return resend.Emails.send({
            "from": from_addr,
            "to": [to],
            "subject": subject,
            "html": html,
            "text": body_text,
        })
    try:
        result = await asyncio.to_thread(_do_send)
        return {"ok": True, "provider_id": (result or {}).get("id")}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


async def _envoy_send_voice(lead: Dict[str, Any], plan: Dict[str, Any]) -> Dict[str, Any]:
    client = _twilio_client()
    if client is None:
        return {"ok": False, "error": "twilio_not_configured"}
    from_phone = os.environ.get("TWILIO_FROM_NUMBER", "").strip()
    if not from_phone:
        return {"ok": False, "error": "twilio_from_missing"}
    to = (lead.get("phone") or "").strip()
    if not to:
        return {"ok": False, "error": "no_phone_on_lead"}

    # Twilio <Say> TwiML — keep it short. Escape XML specials in the message.
    msg = (plan.get("message_draft") or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    twiml = f'<Response><Say voice="Polly.Joanna">{msg[:1000]}</Say></Response>'

    def _do_call():
        return client.calls.create(to=to, from_=from_phone, twiml=twiml)
    try:
        call = await asyncio.to_thread(_do_call)
        return {"ok": True, "provider_id": call.sid}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


async def _envoy_stage(db) -> Dict[str, int]:
    """Send every confidence>70 plan whose lead hasn't been contacted yet."""
    from services.a2a_bus import bus

    plans = await db.execution_plans.find(
        {
            "confidence_score": {"$gt": _ARCHITECT_CONFIDENCE_THRESHOLD},
            "status": "drafted",
        },
        {"_id": 0},
    ).sort("created_at", 1).limit(_BATCH_SIZE).to_list(_BATCH_SIZE)

    sent = 0
    skipped = 0
    failed = 0
    for plan in plans:
        lead_id = plan.get("lead_id")
        lead = await db.campaign_leads.find_one({"lead_id": lead_id}, {"_id": 0})
        if not lead:
            skipped += 1
            continue
        if lead.get("status") == "contacted":
            # Another path already contacted this lead — mark plan consumed
            await db.execution_plans.update_one(
                {"plan_id": plan["plan_id"]},
                {"$set": {"status": "skipped_already_contacted", "consumed_at": _now_iso()}},
            )
            skipped += 1
            continue

        channel = plan.get("recommended_channel")
        if channel == "email":
            result = await _envoy_send_email(lead, plan)
            await asyncio.sleep(_RESEND_PACING_SEC)
        elif channel == "voice":
            result = await _envoy_send_voice(lead, plan)
            await asyncio.sleep(_TWILIO_PACING_SEC)
        else:
            result = {"ok": False, "error": f"unknown_channel:{channel}"}

        now_iso = _now_iso()
        attempt = {
            "plan_id": plan["plan_id"],
            "channel": channel,
            "timestamp": now_iso,
            "success": bool(result.get("ok")),
            "provider_id": result.get("provider_id"),
            "error": result.get("error"),
        }

        await db.execution_plans.update_one(
            {"plan_id": plan["plan_id"]},
            {"$set": {
                "status": "delivered" if result.get("ok") else "send_failed",
                "consumed_at": now_iso,
                "delivery_result": attempt,
            }},
        )

        if result.get("ok"):
            sent += 1
            await db.campaign_leads.update_one(
                {"lead_id": lead_id},
                {
                    "$set": {
                        "status": "contacted",
                        "contacted_at": now_iso,
                        "last_channel_used": channel,
                        "updated_at": now_iso,
                    },
                    "$push": {"outreach_history": attempt},
                },
            )
            await db.activity_feed.insert_one({
                "event_id": f"act-{uuid.uuid4().hex[:10]}",
                "source": _ENVOY,
                "event": "outbound_sent",
                "lead_id": lead_id,
                "business_name": lead.get("business_name"),
                "channel": channel,
                "priority": "normal",
                "provider_id": result.get("provider_id"),
                "timestamp": now_iso,
            })
            try:
                await bus.emit(_ENVOY, "delivered", {
                    "lead_id": lead_id,
                    "plan_id": plan["plan_id"],
                    "channel": channel,
                    "provider_id": result.get("provider_id"),
                })
            except Exception:
                pass
        else:
            failed += 1
            logger.warning(f"[a2a-chain/envoy] send failed lead={lead_id} err={result.get('error')}")

    return {"stage": _ENVOY, "sent": sent, "skipped": skipped, "failed": failed}


# ═══════════════════════════════════════════════════════════════════════
# Closer
# ═══════════════════════════════════════════════════════════════════════
async def _closer_stage(db) -> Dict[str, int]:
    """Score every replied lead we haven't scored yet."""
    from services.model_failover import llm_call_with_failover
    from services.a2a_bus import bus

    cursor = db.campaign_leads.find(
        {
            "status": "replied",
            "$or": [
                {"closer_scored_at": {"$exists": False}},
                {"closer_scored_at": None},
            ],
        },
        {"_id": 0},
    ).sort("updated_at", 1).limit(_BATCH_SIZE)
    leads = await cursor.to_list(_BATCH_SIZE)

    scored = 0
    hot = 0
    for lead in leads:
        lead_id = lead.get("lead_id")
        reply_text = (
            lead.get("last_reply_text")
            or lead.get("reply_text")
            or lead.get("inbound_message")
            or ""
        )
        if not reply_text:
            # No reply content to score — mark scored with 0 so we don't loop.
            await db.campaign_leads.update_one(
                {"lead_id": lead_id},
                {"$set": {
                    "closer_scored_at": _now_iso(),
                    "closer_score": 0,
                    "closer_reason": "no_reply_text_on_lead",
                    "updated_at": _now_iso(),
                }},
            )
            continue

        system = (
            "You are AUREM's close-rate scorer. Read the prospect's reply and "
            "rate their buying intent from 0-100. Return STRICT JSON only: "
            '{"score": int 0-100, "intent_label": "cold"|"warm"|"hot", "reason": str}.'
        )
        prompt = (
            f"Business: {lead.get('business_name')}\n"
            f"Reply they sent:\n\"\"\"\n{reply_text[:1500]}\n\"\"\"\n\n"
            "Return JSON only."
        )

        try:
            resp = await llm_call_with_failover(
                prompt=prompt, system=system, max_tokens=300, timeout=8.0,
            )
        except Exception as e:
            logger.warning(f"[a2a-chain/closer] LLM failed for {lead_id}: {e}")
            continue

        if resp.get("degraded"):
            continue

        parsed = _extract_json_block(resp.get("content", "")) or {}
        score = int(parsed.get("score") or 0)
        score = max(0, min(100, score))
        intent = (parsed.get("intent_label") or "cold").lower()
        reason = (parsed.get("reason") or "")[:300]
        now_iso = _now_iso()

        await db.campaign_leads.update_one(
            {"lead_id": lead_id},
            {"$set": {
                "closer_score": score,
                "closer_intent": intent,
                "closer_reason": reason,
                "closer_scored_at": now_iso,
                "updated_at": now_iso,
            }},
        )
        scored += 1

        if score > _CLOSER_HOT_THRESHOLD:
            hot += 1
            await db.activity_feed.insert_one({
                "event_id": f"act-{uuid.uuid4().hex[:10]}",
                "source": _CLOSER,
                "event": "hot_reply",
                "lead_id": lead_id,
                "business_name": lead.get("business_name"),
                "priority": "hot",
                "score": score,
                "intent": intent,
                "reason": reason,
                "timestamp": now_iso,
            })
            try:
                await bus.emit(_CLOSER, "hot_reply", {
                    "lead_id": lead_id,
                    "score": score,
                    "intent": intent,
                })
            except Exception:
                pass

    return {"stage": _CLOSER, "scored": scored, "hot_flags": hot}


# ═══════════════════════════════════════════════════════════════════════
# Public entry points
# ═══════════════════════════════════════════════════════════════════════
async def run_full_cycle(db) -> Dict[str, Any]:
    """Run all three stages once. Exposed for manual admin triggers + tests."""
    out = {"timestamp": _now_iso()}
    for stage_fn, key in (
        (_architect_stage, _ARCH),
        (_envoy_stage, _ENVOY),
        (_closer_stage, _CLOSER),
    ):
        try:
            out[key] = await stage_fn(db)
        except Exception as e:
            logger.exception(f"[a2a-chain] {key} stage crashed: {e}")
            out[key] = {"error": str(e)[:200]}
    return out


async def a2a_chain_scheduler():
    """Long-lived loop — attached to Pillar 4."""
    logger.info("[a2a-chain] scheduler started (60-s cycle)")
    await asyncio.sleep(20)  # let startup settle
    from server import db as _db_ref

    while True:
        try:
            result = await run_full_cycle(_db_ref)
            if any(
                isinstance(v, dict) and any(
                    k for k in v if k != "stage" and v.get(k)
                )
                for v in result.values() if isinstance(v, dict)
            ):
                logger.info(f"[a2a-chain] cycle: {json.dumps(result, default=str)[:400]}")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning(f"[a2a-chain] cycle error: {e}")
        await asyncio.sleep(CYCLE_SECONDS)


__all__ = [
    "a2a_chain_scheduler",
    "run_full_cycle",
    "_architect_stage",
    "_envoy_stage",
    "_closer_stage",
    "CYCLE_SECONDS",
    "_ARCHITECT_CONFIDENCE_THRESHOLD",
    "_CLOSER_HOT_THRESHOLD",
]
