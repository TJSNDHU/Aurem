"""
Armed Outreach Campaigns (iter 315i)
=====================================
Sovereign founder command: "start blast", "go", "leads blast karo" →
ORA arms a campaign — top N unblasted leads, scheduled for next
Monday 9 AM America/Toronto, $149 repair pitch by default.

Design:
- ARM now, FIRE later. Actual blast is blocked by Twilio 10DLC approval.
- Once Twilio approves, the 5-min scheduler will pick it up automatically
  on the scheduled_at boundary. Zero manual step.

Public:
  await arm_outreach(db, founder, *, count=50, pitch="repair_149",
                       city=None, schedule="monday_9am") -> dict
  await cancel_latest_armed(db, founder) -> dict
  await fire_due_campaigns(db) -> dict
  await armed_outreach_scheduler(db) -> never returns
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import pytz
    _TZ = pytz.timezone("America/Toronto")
except Exception:
    _TZ = timezone.utc

DEFAULT_COUNT = 50
ALERT_PHONE = os.environ.get("FOUNDER_PHONE", "+16134000000")


def _next_monday_9am() -> datetime:
    """Next Monday 9 AM America/Toronto, in UTC."""
    try:
        now = datetime.now(_TZ)
    except Exception:
        now = datetime.now(timezone.utc)
    days_ahead = (0 - now.weekday()) % 7  # 0 = Monday
    if days_ahead == 0 and now.hour >= 9:
        days_ahead = 7
    target = (now + timedelta(days=days_ahead)).replace(
        hour=9, minute=0, second=0, microsecond=0)
    if target.tzinfo is None:
        return target.replace(tzinfo=timezone.utc)
    return target.astimezone(timezone.utc)


async def _pick_leads(db, count: int, city: Optional[str]) -> List[Dict[str, Any]]:
    """Top N unblasted leads, DND-safe, sorted by newest."""
    q: Dict[str, Any] = {
        "status": {"$nin": ["do_not_contact", "blasted", "bounced",
                                "unsubscribed"]},
        "armed_for_campaign": {"$in": [None, "", False]},
    }
    if city:
        q["city"] = {"$regex": f"^{re.escape(city)}$", "$options": "i"}
    cur = db.campaign_leads.find(
        q, {"_id": 0, "lead_id": 1, "business_name": 1, "email": 1,
              "phone": 1, "city": 1, "industry": 1}
    ).sort("created_at", -1).limit(count)
    return await cur.to_list(count)


PITCH_LIBRARY = {
    "repair_149": {
        "label": "$149 Quick Repair",
        "cta_url_tmpl": "https://aurem.live/api/repair-report/{public_slug}",
        # iter 315j — carrier-compliance: removed "FREE"/"trial"/promo
        # exclamations. Concrete, consultant tone. STOP opt-out included.
        "first_msg": (
            "Hi {business_name}, I'm ORA from AUREM. "
            "I audited your website and found {issues_critical}+ issues "
            "costing you customers monthly. "
            "Your full report: {cta_url}. "
            "Reply YES to see the fix plan. Reply STOP to opt out."),
        "second_msg": (
            "Quick follow-up, {business_name} — the top 3 issues "
            "typically recover 15-30% of lost leads when fixed. "
            "Your report: {cta_url}. Reply STOP to opt out."),
    },
    "saas_97": {
        "label": "$97/mo AUREM Platform",
        "cta_url_tmpl": "https://aurem.live/report/{lead_id}",
        "first_msg": (
            "Hi {business_name}, I'm ORA from AUREM. "
            "I analyzed your Google presence and put together a short "
            "report on gaps that are costing you customers monthly. "
            "Your report: {cta_url}. "
            "Reply YES to see the full analysis. Reply STOP to opt out."),
        "second_msg": (
            "{business_name}, checking in — did the report land? "
            "{cta_url}. Reply STOP to opt out."),
    },
}


async def arm_outreach(db, founder: str = "tj", *,
                          count: int = DEFAULT_COUNT,
                          pitch: str = "repair_149",
                          city: Optional[str] = None,
                          schedule: str = "monday_9am") -> Dict[str, Any]:
    """Arm a campaign. Idempotent per (founder, pitch) within 24h."""
    if db is None:
        return {"ok": False, "error": "db_unavailable"}
    pitch_cfg = PITCH_LIBRARY.get(pitch)
    if not pitch_cfg:
        return {"ok": False, "error": f"unknown pitch: {pitch}"}

    # Idempotency: if an armed campaign with the same pitch exists, return it
    existing = await db.armed_campaigns.find_one(
        {"pitch": pitch, "status": "armed"},
        {"_id": 0}, sort=[("armed_at", -1)])
    if existing:
        try:
            sched_left = (datetime.fromisoformat(existing["scheduled_at"])
                            - datetime.now(timezone.utc))
            if sched_left.total_seconds() > 0:
                return {"ok": True, "skipped": "already_armed",
                         "campaign_id": existing["campaign_id"],
                         "scheduled_at": existing["scheduled_at"],
                         "lead_count": existing.get("lead_count"),
                         "pitch_label": pitch_cfg["label"]}
        except Exception:
            pass

    leads = await _pick_leads(db, count, city)
    if not leads:
        return {"ok": False, "error": "no_eligible_leads"}

    if schedule == "monday_9am":
        scheduled_at = _next_monday_9am()
    elif schedule == "now":
        scheduled_at = datetime.now(timezone.utc) + timedelta(minutes=2)
    else:
        scheduled_at = _next_monday_9am()

    lead_ids = [lead["lead_id"] for lead in leads]
    campaign_id = f"arm_{uuid.uuid4().hex[:10]}"
    now_iso = datetime.now(timezone.utc).isoformat()
    cancel_token = uuid.uuid4().hex[:8]

    record = {
        "campaign_id": campaign_id,
        "status": "armed",
        "founder": founder,
        "pitch": pitch,
        "pitch_label": pitch_cfg["label"],
        "city": city,
        "lead_ids": lead_ids,
        "lead_count": len(lead_ids),
        "scheduled_at": scheduled_at.isoformat(),
        "armed_at": now_iso,
        "cancel_token": cancel_token,
        "fired_count": 0,
        "delivered_count": 0,
        "failed_count": 0,
        "firing_started_at": None,
        "completed_at": None,
    }
    await db.armed_campaigns.insert_one(dict(record))

    # Mark those leads so we don't double-arm them in parallel campaigns.
    await db.campaign_leads.update_many(
        {"lead_id": {"$in": lead_ids}},
        {"$set": {"armed_for_campaign": campaign_id,
                   "armed_at": now_iso}},
    )
    logger.info(
        f"[armed-outreach] campaign {campaign_id} armed — "
        f"{len(lead_ids)} leads, fires {scheduled_at.isoformat()}")

    return {
        "ok": True, "campaign_id": campaign_id,
        "lead_count": len(lead_ids),
        "scheduled_at": scheduled_at.isoformat(),
        "scheduled_local": scheduled_at.astimezone(_TZ).strftime(
            "%A %I:%M %p %Z") if hasattr(_TZ, "localize") else
            scheduled_at.isoformat(),
        "pitch_label": pitch_cfg["label"],
        "cancel_token": cancel_token,
    }


async def cancel_latest_armed(db, founder: str = "tj") -> Dict[str, Any]:
    """Cancel the most-recent armed (not-yet-firing) campaign."""
    if db is None:
        return {"ok": False, "error": "db_unavailable"}
    target = await db.armed_campaigns.find_one(
        {"founder": founder, "status": "armed"},
        {"_id": 0}, sort=[("armed_at", -1)])
    if not target:
        return {"ok": False, "error": "no_armed_campaign"}
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.armed_campaigns.update_one(
        {"campaign_id": target["campaign_id"]},
        {"$set": {"status": "cancelled", "cancelled_at": now_iso}},
    )
    # Release the arm locks on leads
    await db.campaign_leads.update_many(
        {"armed_for_campaign": target["campaign_id"]},
        {"$set": {"armed_for_campaign": None},
          "$unset": {"armed_at": ""}},
    )
    logger.info(f"[armed-outreach] cancelled {target['campaign_id']}")
    return {"ok": True, "cancelled": target["campaign_id"],
            "released_leads": target.get("lead_count", 0)}


async def _fire_one_lead(db, campaign: Dict[str, Any],
                              lead_id: str) -> Dict[str, Any]:
    """Delegate to the existing blast_one executor so we reuse message-send
    + dedupe + rate-limit plumbing.

    iter 327m — CASL gate added. Audit (2026-02-23) found the blast
    pipeline checked do_not_contact but the agent-direct path did NOT.
    Now both paths go through `services.casl_gate.is_blocked_by_casl`
    so the rule is enforced everywhere (fail-closed on errors)."""
    lead = await db.campaign_leads.find_one(
        {"lead_id": lead_id}, {"_id": 0})
    if not lead:
        return {"ok": False, "error": "lead_gone"}
    # ── CASL gate ──
    try:
        from services.casl_gate import is_blocked_by_casl
        casl = await is_blocked_by_casl(
            db, email=lead.get("email"), phone=lead.get("phone"),
        )
        if casl.get("blocked"):
            # Mark the lead so we don't keep retrying.
            await db.campaign_leads.update_one(
                {"lead_id": lead_id},
                {"$set": {
                    "status":             "do_not_contact",
                    "casl_blocked_at":    datetime.now(timezone.utc).isoformat(),
                    "casl_block_reason":  casl.get("reason"),
                }},
            )
            return {
                "ok":     False,
                "lead_id": lead_id,
                "error":   "casl_blocked",
                "reason":  casl.get("reason"),
            }
    except Exception as e:
        # Fail-closed: a broken gate must NOT silently permit sends.
        return {"ok": False, "lead_id": lead_id,
                "error": "casl_gate_error",
                "detail": f"{type(e).__name__}: {str(e)[:120]}"}

    try:
        from services.ora_command_center import _exec_blast_one
        res = await _exec_blast_one(
            db, {"business_name": lead.get("business_name")})
        return {"ok": bool(res.get("ok")), "lead_id": lead_id,
                "reply": (res.get("reply") or "")[:140]}
    except Exception as e:
        return {"ok": False, "lead_id": lead_id, "err": str(e)[:140]}


async def fire_due_campaigns(db) -> Dict[str, Any]:
    """Scheduler tick. Fires all armed campaigns whose scheduled_at has passed."""
    if db is None:
        return {"ok": False, "error": "db_unavailable"}
    now_iso = datetime.now(timezone.utc).isoformat()
    summary = {"fired_campaigns": 0, "fired_messages": 0, "skipped": 0}
    cur = db.armed_campaigns.find(
        {"status": "armed", "scheduled_at": {"$lte": now_iso}},
        {"_id": 0}).limit(5)
    async for camp in cur:
        try:
            await db.armed_campaigns.update_one(
                {"campaign_id": camp["campaign_id"]},
                {"$set": {"status": "firing",
                           "firing_started_at": now_iso}},
            )
            delivered = 0
            failed = 0
            for lid in camp.get("lead_ids", []):
                res = await _fire_one_lead(db, camp, lid)
                if res.get("ok"):
                    delivered += 1
                else:
                    failed += 1
            done_iso = datetime.now(timezone.utc).isoformat()
            await db.armed_campaigns.update_one(
                {"campaign_id": camp["campaign_id"]},
                {"$set": {"status": "completed",
                           "completed_at": done_iso,
                           "delivered_count": delivered,
                           "failed_count": failed,
                           "fired_count": delivered + failed}},
            )
            summary["fired_campaigns"] += 1
            summary["fired_messages"] += delivered + failed
            logger.info(
                f"[armed-outreach] FIRED {camp['campaign_id']} "
                f"— delivered={delivered} failed={failed}")
            # Founder alert
            try:
                from routers.whatsapp_alerts import send_whatsapp
                await send_whatsapp(
                    ALERT_PHONE,
                    f"🔥 Campaign {camp['campaign_id']} FIRED\n"
                    f"{camp['pitch_label']}\n"
                    f"Delivered: {delivered}/{camp.get('lead_count')}\n"
                    f"Failed: {failed}",
                )
            except Exception:
                pass
        except Exception as e:
            logger.warning(
                f"[armed-outreach] fire failed {camp.get('campaign_id')}: {e}")
            summary["skipped"] += 1
    return {"ok": True, **summary}


async def armed_outreach_scheduler(db) -> None:
    """Runs forever. Every 5 min, fires any due armed campaigns."""
    await asyncio.sleep(60)
    while True:
        try:
            await fire_due_campaigns(db)
        except Exception as e:
            logger.warning(f"[armed-outreach] scheduler tick failed: {e}")
        await asyncio.sleep(300)
