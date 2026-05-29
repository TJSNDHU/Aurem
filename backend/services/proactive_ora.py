"""
services/proactive_ora.py — iter D-58

Auto-triggered ORA actions, no human in the loop. Four rules:

  R1) No reply in 3 days   → auto follow-up #2 email
  R2) Email opened, no reply (same day)  → WhatsApp ping
  R3) Lead visited website  → "saw you visited" message
  R4) Hot lead flag set     → immediately draft + send reply

Hard rules:
  • Configurable ON / OFF per tenant via `proactive_ora_config`
  • Rate-limited: max 3 touches / lead / week
  • CASL compliant: skip dnc / casl_blocked / unsubscribed
  • Every action logged to `outreach_history` with type
    `"proactive_ora_<rule>"`
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any

logger = logging.getLogger(__name__)

_db = None
_MAX_TOUCHES_PER_WEEK = 3


def set_db(database) -> None:
    global _db
    _db = database


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def get_config(tenant_id: str = "global") -> dict[str, Any]:
    if _db is None:
        return {"tenant_id": tenant_id, "enabled_rules": {}}
    doc = await _db.proactive_ora_config.find_one(
        {"tenant_id": tenant_id}, {"_id": 0},
    )
    if not doc:
        # Default: all rules OFF until founder opts in.
        doc = {
            "tenant_id":     tenant_id,
            "enabled_rules": {"R1": False, "R2": False, "R3": False, "R4": False},
            "created_at":    _now(),
        }
    return doc


async def set_rule(tenant_id: str, rule: str, enabled: bool) -> dict[str, Any]:
    if _db is None:
        raise RuntimeError("db_not_ready")
    if rule not in ("R1", "R2", "R3", "R4"):
        raise ValueError(f"bad_rule {rule!r}")
    cfg = await get_config(tenant_id)
    cfg.setdefault("enabled_rules", {})[rule] = bool(enabled)
    cfg["updated_at"] = _now()
    await _db.proactive_ora_config.update_one(
        {"tenant_id": tenant_id}, {"$set": cfg}, upsert=True,
    )
    return cfg


async def _touches_this_week(lead_id: str) -> int:
    if _db is None:
        return 0
    since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    return await _db.outreach_history.count_documents({
        "lead_id": lead_id,
        "ts":      {"$gte": since},
        "type":    {"$regex": "^proactive_ora_"},
    })


async def _is_compliant(lead: dict[str, Any]) -> bool:
    if not lead:
        return False
    if lead.get("dnc") is True:
        return False
    if lead.get("casl_blocked") is True:
        return False
    if lead.get("status") == "unsubscribed":
        return False
    return True


async def _log_action(rule: str, lead: dict[str, Any],
                       channel: str, ok: bool, detail: str) -> None:
    if _db is None:
        return
    await _db.outreach_history.insert_one({
        "ts":      _now(),
        "lead_id": lead.get("lead_id", ""),
        "type":    f"proactive_ora_{rule}",
        "result":  {
            "sent": [{
                "channel":  channel,
                "to":       lead.get("email") if channel == "email"
                            else lead.get("phone"),
                "ok":       ok,
                "rule":     rule,
                "detail":   detail,
            }],
        },
        "tenant_id": lead.get("tenant_id", "global"),
    })


async def _send_followup_email(lead: dict[str, Any]) -> bool:
    """R1 — generic follow-up #2 template. Real send via Resend."""
    if not lead.get("email"):
        return False
    try:
        from services.email_service import send_email
        body = (
            f"Hi {lead.get('business_name','there')},\n\n"
            "Just circling back on my previous note — happy to hop on a "
            "quick 15-minute call this week if useful.\n\n"
            "— AUREM Team"
        )
        res = await send_email(lead["email"], "Following up", body)
        return bool(res and (res.get("ok") or res.get("id")))
    except Exception as e:
        logger.warning(f"[proactive-ora] R1 send fail: {e}")
        return False


async def _send_wa_ping(lead: dict[str, Any], copy: str) -> bool:
    if not lead.get("phone"):
        return False
    try:
        from shared.providers.twilio import send_whatsapp_message
        res = await send_whatsapp_message(lead["phone"], copy)
        return bool(res and (res.get("ok") or res.get("success")))
    except Exception as e:
        logger.warning(f"[proactive-ora] WA send fail: {e}")
        return False


# ── Rule runners ────────────────────────────────────────────────────

async def _eligible(lead: dict[str, Any], rule: str) -> bool:
    if not await _is_compliant(lead):
        return False
    if await _touches_this_week(lead.get("lead_id", "")) >= _MAX_TOUCHES_PER_WEEK:
        return False
    return True


async def run_r1_no_reply_3d() -> dict[str, Any]:
    """R1 — last_blast_at older than 3d, no reply, no recent follow-up."""
    if _db is None:
        return {"actions": 0}
    cutoff = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    cursor = _db.campaign_leads.find({
        "status":         {"$in": ["emailed"]},
        "last_blast_at":  {"$lte": cutoff},
        "email":          {"$nin": ["", None]},
    }, {"_id": 0}).limit(50)

    actions = 0
    async for lead in cursor:
        if not await _eligible(lead, "R1"):
            continue
        ok = await _send_followup_email(lead)
        await _log_action("R1", lead, "email", ok, "no_reply_3d")
        if ok:
            actions += 1
    return {"actions": actions, "rule": "R1"}


async def run_r2_opened_no_reply() -> dict[str, Any]:
    """R2 — hot_lead_flag set (email opened) within last 24h + no reply."""
    if _db is None:
        return {"actions": 0}
    since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    cursor = _db.campaign_leads.find({
        "hot_lead_flag":      True,
        "hot_lead_reason":    "email_opened",
        "hot_lead_signal_at": {"$gte": since},
        "phone":              {"$nin": ["", None]},
    }, {"_id": 0}).limit(50)

    actions = 0
    async for lead in cursor:
        if not await _eligible(lead, "R2"):
            continue
        copy = (f"Hi {lead.get('business_name','there')}, saw you opened "
                "our note today — happy to answer anything quickly here. "
                "— AUREM")
        ok = await _send_wa_ping(lead, copy)
        await _log_action("R2", lead, "whatsapp", ok, "opened_no_reply")
        if ok:
            actions += 1
    return {"actions": actions, "rule": "R2"}


async def run_r3_website_visited() -> dict[str, Any]:
    """R3 — recent cta_clicks row matched to lead."""
    if _db is None:
        return {"actions": 0}
    since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    visited_slugs = []
    async for d in _db.cta_clicks.find({"ts": {"$gte": since}},
                                          {"_id": 0, "slug": 1}):
        if d.get("slug"):
            visited_slugs.append(d["slug"])
    if not visited_slugs:
        return {"actions": 0, "rule": "R3"}

    actions = 0
    async for site in _db.auto_websites.find(
        {"slug": {"$in": visited_slugs}}, {"_id": 0, "lead_id": 1},
    ):
        lead = await _db.campaign_leads.find_one(
            {"lead_id": site["lead_id"]}, {"_id": 0},
        )
        if not lead or not await _eligible(lead, "R3"):
            continue
        copy = ("Hi! Saw you visited the preview I built for you — "
                "want me to walk you through it? — AUREM")
        ch = "whatsapp" if lead.get("phone") else "email"
        ok = (await _send_wa_ping(lead, copy) if ch == "whatsapp"
              else await _send_followup_email(lead))
        await _log_action("R3", lead, ch, ok, "website_visited")
        if ok:
            actions += 1
    return {"actions": actions, "rule": "R3"}


async def run_r4_hot_lead() -> dict[str, Any]:
    """R4 — hot_lead_flag clicked within last 60 min → immediate reply."""
    if _db is None:
        return {"actions": 0}
    since = (datetime.now(timezone.utc) - timedelta(minutes=60)).isoformat()
    cursor = _db.campaign_leads.find({
        "hot_lead_flag":      True,
        "hot_lead_reason":    "email_clicked",
        "hot_lead_signal_at": {"$gte": since},
    }, {"_id": 0}).limit(30)

    actions = 0
    async for lead in cursor:
        if not await _eligible(lead, "R4"):
            continue
        copy = (
            f"Hi {lead.get('business_name','there')} — saw you clicked "
            "through our note. Quick question: what part stood out? "
            "Happy to send a tailored quote within the hour. — AUREM"
        )
        ch = "email" if lead.get("email") else "whatsapp"
        ok = (await _send_followup_email(lead) if ch == "email"
              else await _send_wa_ping(lead, copy))
        await _log_action("R4", lead, ch, ok, "hot_click_60min")
        if ok:
            actions += 1
    return {"actions": actions, "rule": "R4"}


async def run_all(tenant_id: str = "global") -> dict[str, Any]:
    cfg = await get_config(tenant_id)
    enabled = cfg.get("enabled_rules") or {}
    out: dict[str, Any] = {"tenant_id": tenant_id, "ran": []}
    runners = (("R1", run_r1_no_reply_3d),
                ("R2", run_r2_opened_no_reply),
                ("R3", run_r3_website_visited),
                ("R4", run_r4_hot_lead))
    for rid, runner in runners:
        if not enabled.get(rid):
            out["ran"].append({"rule": rid, "skipped": "disabled"})
            continue
        res = await runner()
        out["ran"].append(res)
    out["completed_at"] = _now()
    return out
