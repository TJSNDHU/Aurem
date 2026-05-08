"""
Forecast → Campaign Auto-Trigger (iter 314)
=============================================
Closes the Sunday-strategy → Monday-action loop.

When `send_forecast_now` finishes, this module:
  1. Parses the forecast markdown for the NEXT BIG BET section
  2. Asks ORA to extract {topic, target_profile filters,
     5-message Envoy sequence with Day 1/3/7/14/21 cadence}
  3. Matches top-50 leads from db.campaign_leads against the profile
  4. Persists `db.forecast_campaigns` with status="armed"
  5. WhatsApp pings +16134000000 so TJ can preview/cancel before
     Monday 9 AM Toronto firing window
  6. Scheduler `forecast_campaign_dispatcher` (hourly, runs from
     server.py) fires the sequence Monday 9 AM TO unless
     status="cancelled".

Public:
  await arm_campaign_from_forecast(db, forecast_id, raw_markdown) -> dict
  await dispatch_due_forecast_campaigns(db) -> dict
  await cancel_forecast_campaign(db, campaign_id) -> dict
"""
from __future__ import annotations

import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

FOUNDER_WHATSAPP = os.environ.get("FOUNDER_WHATSAPP", "+16134000000")
TZ_OFFSET_HOURS = -4  # Toronto

CADENCE_DAYS = [1, 3, 7, 14, 21]
CADENCE_LABELS = ["Intro + bet-specific offer",
                    "Value proof (audit/site preview)",
                    "Follow-up + urgency",
                    "Last chance",
                    "Break-up message"]


def _toronto_now() -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=TZ_OFFSET_HOURS)


def _next_monday_9am_utc() -> datetime:
    """Next upcoming Monday 9 AM Toronto, expressed in UTC."""
    n = _toronto_now()
    days_ahead = (7 - n.weekday()) % 7
    if days_ahead == 0 and n.hour >= 9:
        days_ahead = 7
    target_to = (n.replace(hour=9, minute=0, second=0, microsecond=0)
                  + timedelta(days=days_ahead))
    return target_to - timedelta(hours=TZ_OFFSET_HOURS)


def _extract_bet_text(md: str) -> str:
    if not md:
        return ""
    m = re.search(r"\*?\*?NEXT BIG BET\*?\*?\s*[:\-]?\s*(.+?)(?=\n\*\*|\Z)",
                  md, flags=re.DOTALL | re.IGNORECASE)
    return (m.group(1) if m else "").strip()[:500]


async def _ora_extract_plan(bet_text: str,
                              forecast_md: str) -> Optional[Dict[str, Any]]:
    """Use ORA to convert the bet narrative into a structured campaign plan."""
    api_key = os.environ.get("EMERGENT_LLM_KEY", "")
    if not api_key:
        return None
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage  # type: ignore
        import asyncio
        prompt = (
            "From this Sunday Forecast NEXT BIG BET, extract the campaign "
            "plan as STRICT JSON only (no preamble, no code fences). Schema:\n"
            "{\n"
            '  "topic": "<≤80 char headline>",\n'
            '  "value_prop": "<one-sentence pitch>",\n'
            '  "target_profile": {\n'
            '     "categories": ["<industry tag>", ...],          // up to 4\n'
            '     "needs_website": true|false,\n'
            '     "website_quality": ["poor","broken","none"]|null,\n'
            '     "min_score": 0-100|null,\n'
            '     "max_score": 0-100|null\n'
            "  },\n"
            '  "messages": [\n'
            '     {"day":1,"channel":"sms|email","subject":"<email subj or null>","body":"<≤320 chars, {{first_name}} placeholder OK>"},\n'
            '     {"day":3,...}, {"day":7,...}, {"day":14,...}, {"day":21,...}\n'
            "  ]\n"
            "}\n\nForecast:\n```\n" + forecast_md[:1800] + "\n```\n\n"
            "NEXT BIG BET (focus):\n" + bet_text[:600]
        )
        chat = LlmChat(
            api_key=api_key,
            session_id=f"fcast-camp-{uuid.uuid4().hex[:10]}",
            system_message=("You are ORA, AUREM's outbound strategist. "
                             "Output ONLY valid JSON. Bodies under 320 chars, "
                             "Canadian voice, specific dollar/time anchors, "
                             "no emoji walls, no fluff."),
        ).with_model("anthropic", "claude-sonnet-4-5-20250929") \
         .with_params(max_tokens=1400)
        out = await asyncio.wait_for(
            chat.send_message(UserMessage(text=prompt)), timeout=45.0,
        )
        return _strip_json(out)
    except Exception as e:
        logger.warning(f"[fcast-camp] ORA extract failed: {e}")
        return None


def _strip_json(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    t = text.strip()
    # Strip code fences if present
    t = re.sub(r"^```(?:json)?\s*", "", t)
    t = re.sub(r"\s*```\s*$", "", t)
    # Find first { and matching last }
    s = t.find("{")
    e = t.rfind("}")
    if s == -1 or e == -1 or e <= s:
        return None
    try:
        return json.loads(t[s:e + 1])
    except Exception:
        return None


async def _match_leads(db, profile: Dict[str, Any],
                         limit: int = 50) -> List[Dict[str, Any]]:
    """Match top leads. If the strict profile yields too few, progressively
    relax filters so the campaign still has a target list."""
    proj = {"_id": 0, "lead_id": 1, "business_name": 1, "phone": 1,
            "email": 1, "category": 1, "website_url": 1,
            "conviction_score": 1, "score": 1}

    async def _query(filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        return await db.campaign_leads.find(
            filters, proj,
        ).sort([("conviction_score", -1), ("score", -1)]) \
            .limit(limit).to_list(limit)

    base = {"status": {"$ne": "do_not_contact"}}
    cats_in = [c.lower() for c in (profile.get("categories") or []) if c]
    wq = profile.get("website_quality") or []

    # Tier 1: strict — categories + needs_website + quality
    if cats_in:
        cat_alts = list({*cats_in,
                          *[c.title() for c in cats_in],
                          *[c.upper() for c in cats_in]})
        q1 = {**base, "category": {"$in": cat_alts}}
        if profile.get("needs_website") is True:
            q1["$or"] = [{"website_url": {"$in": [None, ""]}},
                          {"verification.has_website": False}]
        if wq:
            q1["website_quality"] = {"$in": wq}
        rows = await _query(q1)
        if len(rows) >= max(5, limit // 4):
            return rows

    # Tier 2: drop website_quality (often empty in legacy rows)
    if cats_in:
        cat_alts = list({*cats_in, *[c.title() for c in cats_in]})
        # Substring match on category to catch "auto shops, salons" etc
        regex_alts = [{"category": {"$regex": c, "$options": "i"}}
                       for c in cats_in]
        q2 = {**base, "$or": regex_alts}
        rows = await _query(q2)
        if rows:
            return rows

    # Tier 3: any lead with phone OR email (general SMB outreach)
    q3 = {**base,
          "$or": [{"phone": {"$nin": [None, ""]}},
                   {"email": {"$nin": [None, ""]}}]}
    return await _query(q3)


async def arm_campaign_from_forecast(
    db, forecast_id: str, raw_markdown: str,
) -> Dict[str, Any]:
    """Main entry — called after a Sunday Forecast is generated."""
    bet = _extract_bet_text(raw_markdown)
    if len(bet) < 30:
        return {"ok": False, "skipped": "no_next_big_bet_in_forecast"}

    plan = await _ora_extract_plan(bet, raw_markdown)
    if not plan:
        return {"ok": False, "skipped": "ora_extraction_failed",
                 "bet_text": bet[:200]}
    msgs = plan.get("messages") or []
    if len(msgs) < 5:
        return {"ok": False, "skipped": "insufficient_messages",
                 "got": len(msgs), "bet_text": bet[:200]}

    profile = plan.get("target_profile") or {}
    leads = await _match_leads(db, profile, limit=50)

    fire_at_utc = _next_monday_9am_utc()
    record = {
        "campaign_id": uuid.uuid4().hex[:14],
        "forecast_id": forecast_id,
        "bet_topic": (plan.get("topic") or bet)[:120],
        "value_prop": (plan.get("value_prop") or "")[:240],
        "target_profile": profile,
        "messages": [
            {"day": int(m.get("day") or CADENCE_DAYS[i % 5]),
              "channel": (m.get("channel") or "sms").lower(),
              "subject": m.get("subject"),
              "body": str(m.get("body") or "")[:320],
              "label": CADENCE_LABELS[i] if i < 5 else "follow-up"}
            for i, m in enumerate(msgs[:5])
        ],
        "lead_count": len(leads),
        "lead_ids": [L["lead_id"] for L in leads],
        "lead_preview": [
            {"lead_id": L.get("lead_id"),
              "business_name": L.get("business_name"),
              "category": L.get("category")} for L in leads[:5]
        ],
        "status": "armed",
        "armed_at": datetime.now(timezone.utc).isoformat(),
        "scheduled_send_at": fire_at_utc.isoformat(),
        "fired_at": None,
    }
    try:
        await db.forecast_campaigns.insert_one(dict(record))
    except Exception as e:
        logger.warning(f"[fcast-camp] persist failed: {e}")

    # WhatsApp alert
    fire_to = (fire_at_utc + timedelta(hours=TZ_OFFSET_HOURS)) \
        .strftime("%a %b %d · %I:%M %p TO")
    try:
        from routers.whatsapp_alerts import send_whatsapp
        text = (
            f"🎯 Forecast campaign armed\n"
            f"Bet: {record['bet_topic']}\n"
            f"Leads matched: {len(leads)}\n"
            f"Envoy fires {fire_to}\n"
            f"Cancel: /admin/console (campaign {record['campaign_id']})"
        )
        await send_whatsapp(FOUNDER_WHATSAPP, text)
    except Exception as e:
        logger.debug(f"[fcast-camp] wa alert failed: {e}")

    record.pop("_id", None)
    return {"ok": True, **record}


# ─── Dispatcher ──────────────────────────────────────────────────────────
async def dispatch_due_forecast_campaigns(db) -> Dict[str, Any]:
    """Hourly tick — fire armed campaigns whose scheduled_send_at has passed."""
    now_iso = datetime.now(timezone.utc).isoformat()
    cursor = db.forecast_campaigns.find(
        {"status": "armed", "scheduled_send_at": {"$lte": now_iso}},
        {"_id": 0},
    )
    fired = []
    async for camp in cursor:
        out = await _fire_campaign(db, camp)
        fired.append({"campaign_id": camp["campaign_id"],
                       "ok": out.get("ok"),
                       "sent": out.get("sent_count")})
    return {"ok": True, "fired": fired, "count": len(fired)}


async def _fire_campaign(db, camp: Dict[str, Any]) -> Dict[str, Any]:
    """Send Day-1 message immediately, schedule Days 3/7/14/21 via existing
    drip queue (db.outbound_messages with send_at)."""
    try:
        from routers.whatsapp_alerts import send_whatsapp
    except Exception:
        send_whatsapp = None  # type: ignore

    sent = 0
    queued = 0
    failures: List[str] = []
    fire_at = datetime.now(timezone.utc)
    msgs = camp.get("messages") or []

    # Build message map by day for easy lookup
    by_day: Dict[int, Dict[str, Any]] = {}
    for m in msgs:
        by_day[int(m.get("day") or 1)] = m

    for lead_id in camp.get("lead_ids") or []:
        lead = await db.campaign_leads.find_one(
            {"lead_id": lead_id},
            {"_id": 0, "lead_id": 1, "phone": 1, "email": 1,
              "business_name": 1},
        )
        if not lead:
            continue
        first_name = (lead.get("business_name") or "there").split()[0]

        for day, m in by_day.items():
            body = str(m.get("body") or "").replace("{{first_name}}", first_name)
            if not body:
                continue
            send_at = (fire_at + timedelta(days=max(0, day - 1))).isoformat()
            doc = {
                "id": uuid.uuid4().hex[:14],
                "lead_id": lead_id,
                "campaign_id": camp["campaign_id"],
                "channel": m.get("channel", "sms"),
                "subject": m.get("subject"),
                "body": body,
                "send_at": send_at,
                "status": "queued",
                "created_at": fire_at.isoformat(),
                "source": "forecast_campaign",
            }
            try:
                await db.outbound_messages.insert_one(dict(doc))
                queued += 1
            except Exception as e:
                failures.append(str(e)[:80])

            # Day-1 SMS — fire immediately
            if day == 1 and m.get("channel", "sms") == "sms" \
                    and send_whatsapp and lead.get("phone"):
                try:
                    out = await send_whatsapp(lead["phone"], body)
                    if out and out.get("ok"):
                        sent += 1
                        await db.outbound_messages.update_one(
                            {"id": doc["id"]},
                            {"$set": {
                                "status": "sent",
                                "sent_at": datetime.now(timezone.utc).isoformat(),
                            }},
                        )
                except Exception as e:
                    failures.append(f"send:{type(e).__name__}")

    await db.forecast_campaigns.update_one(
        {"campaign_id": camp["campaign_id"]},
        {"$set": {
            "status": "fired",
            "fired_at": datetime.now(timezone.utc).isoformat(),
            "sent_count": sent, "queued_count": queued,
            "failure_count": len(failures),
            "failures_sample": failures[:5],
        }},
    )
    return {"ok": True, "sent_count": sent, "queued_count": queued,
            "failures": len(failures)}


async def cancel_forecast_campaign(db,
                                     campaign_id: str) -> Dict[str, Any]:
    res = await db.forecast_campaigns.update_one(
        {"campaign_id": campaign_id, "status": "armed"},
        {"$set": {"status": "cancelled",
                   "cancelled_at": datetime.now(timezone.utc).isoformat()}},
    )
    if res.modified_count == 0:
        return {"ok": False, "error": "not_found_or_not_armed"}
    return {"ok": True, "campaign_id": campaign_id, "status": "cancelled"}


async def list_forecast_campaigns(db,
                                     limit: int = 20) -> List[Dict[str, Any]]:
    return await db.forecast_campaigns.find({}, {"_id": 0}) \
        .sort("armed_at", -1).limit(limit).to_list(limit)
