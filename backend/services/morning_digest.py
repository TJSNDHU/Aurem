"""
AUREM Morning Digest
--------------------
Daily 7 AM EST WhatsApp digest to the owner with:
  - Email opens + clicks in last 24h (business names)
  - Hottest live lead (top flame score)
  - Replies requiring follow-up TODAY
  - Calls made in last 24h
  - Pipeline counts by stage
  - Wins this week
  - Avg days-to-close trend (this week vs last week)

Sent to `AUREM_HOT_LEAD_PHONE` via WHAPI.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


async def _wa_send(phone: str, body: str) -> bool:
    token = os.environ.get("WHAPI_API_TOKEN", "")
    url = os.environ.get("WHAPI_API_URL", "")
    if not (token and url and phone):
        return False
    cleaned = phone.replace("+", "").replace("-", "").replace(" ", "")
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(
                f"{url}/messages/text",
                headers={"authorization": f"Bearer {token}", "content-type": "application/json"},
                json={"to": f"{cleaned}@s.whatsapp.net", "body": body},
            )
            return r.status_code < 300
    except Exception as e:
        logger.warning(f"[Digest] WA send failed: {e}")
        return False


async def _collect_data(db) -> dict:
    """Gather all metrics needed for the digest."""
    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(hours=24)
    day_ago_iso = day_ago.isoformat()
    week_ago_iso = (now - timedelta(days=7)).isoformat()
    two_weeks_ago_iso = (now - timedelta(days=14)).isoformat()

    # Email opens + clicks in last 24h — via touchpoints
    try:
        pipeline = [
            {"$unwind": "$touchpoints"},
            {"$match": {
                "touchpoints.channel": "email",
                "touchpoints.status": {"$in": ["opened", "clicked"]},
                "touchpoints.at": {"$gte": day_ago_iso},
            }},
            {"$group": {"_id": {"lead_id": "$lead_id", "status": "$touchpoints.status"},
                        "business_name": {"$first": "$business_name"},
                        "at": {"$max": "$touchpoints.at"}}},
            {"$sort": {"at": -1}},
            {"$limit": 20},
        ]
        email_events = await db.campaign_leads.aggregate(pipeline).to_list(length=20)
    except Exception as e:
        logger.warning(f"[Digest] email agg failed: {e}")
        email_events = []

    opens = [e for e in email_events if e["_id"]["status"] == "opened"]
    clicks = [e for e in email_events if e["_id"]["status"] == "clicked"]

    # Hottest lead — highest flame_score in live_viewers in last 24h
    try:
        live_doc = await db.aurem_live_viewers.find_one(
            {"last_heartbeat_at": {"$gte": day_ago_iso}},
            {"_id": 0, "business_name": 1, "ping_count": 1, "slug": 1, "lead_id": 1},
            sort=[("ping_count", -1)],
        )
    except Exception:
        live_doc = None

    # Replies in last 24h requiring follow-up
    try:
        reply_pipe = [
            {"$unwind": "$touchpoints"},
            {"$match": {
                "touchpoints.kind": {"$in": ["whapi_inbound", "resend_replied"]},
                "touchpoints.at": {"$gte": day_ago_iso},
            }},
            {"$group": {"_id": "$lead_id",
                        "business_name": {"$first": "$business_name"},
                        "contact_name": {"$first": "$contact_name"},
                        "at": {"$max": "$touchpoints.at"},
                        "body": {"$last": "$touchpoints.details.body_preview"}}},
            {"$sort": {"at": -1}},
            {"$limit": 10},
        ]
        replies = await db.campaign_leads.aggregate(reply_pipe).to_list(length=10)
    except Exception:
        replies = []

    # Calls made last 24h
    try:
        calls_count = await db.voice_calls.count_documents({
            "$or": [
                {"started_at": {"$gte": day_ago}},
                {"started_at": {"$gte": day_ago_iso}},  # when stored as string
            ]
        })
    except Exception:
        calls_count = 0

    # Pipeline stage counts
    try:
        stages = ["new", "contacted", "engaged", "called_no_response", "following_up", "won", "cold"]
        stage_counts = {}
        for s in stages:
            stage_counts[s] = await db.campaign_leads.count_documents({"lifecycle_stage": s})
        # Include legacy unstaged in 'new'
        unstaged = await db.campaign_leads.count_documents({"lifecycle_stage": {"$exists": False}})
        stage_counts["new"] += unstaged
    except Exception:
        stage_counts = {}

    # Wins this week
    try:
        won_this_week = await db.campaign_leads.count_documents({
            "lifecycle_stage": "won",
            "lifecycle_stage_changed_at": {"$gte": week_ago_iso},
        })
    except Exception:
        won_this_week = 0

    # Avg days-to-close: this week vs last week
    async def _avg_days(start_iso, end_iso):
        cursor = db.campaign_leads.find(
            {"lifecycle_stage": "won",
             "lifecycle_stage_changed_at": {"$gte": start_iso, "$lt": end_iso}},
            {"_id": 0, "lifecycle_history": 1},
        ).limit(200)
        days = []
        async for d in cursor:
            hist = d.get("lifecycle_history") or []
            if not hist:
                continue
            try:
                first = datetime.fromisoformat(hist[0]["at"].replace("Z", "+00:00"))
                won = next((h for h in hist if h.get("to") == "won"), None)
                if won:
                    last = datetime.fromisoformat(won["at"].replace("Z", "+00:00"))
                    days.append((last - first).total_seconds() / 86400.0)
            except Exception:
                continue
        return round(sum(days) / len(days), 1) if days else 0.0

    this_week_avg = await _avg_days(week_ago_iso, now.isoformat())
    last_week_avg = await _avg_days(two_weeks_ago_iso, week_ago_iso)

    if last_week_avg > 0:
        pct_change = round(((this_week_avg - last_week_avg) / last_week_avg) * 100, 0)
    else:
        pct_change = 0

    # Ramp-mode status line (Safe vs Aggressive)
    ramp_status = ""
    try:
        settings = await db.auto_hunt_settings.find_one({"_id": "singleton"}, {"_id": 0}) or {}
        if settings.get("enabled"):
            from services.agents.hunter_ora import HunterORA
            today_limit = await HunterORA(db).get_daily_limit()
            mode = settings.get("ramp_mode", "safe")
            emoji = "🚀" if mode == "aggressive" else "🐢"
            ramp_status = f"Mode: {emoji} {mode.title()} — Today limit: *{today_limit}*"
    except Exception:
        pass

    # ── TEST MODE REPORT ─────────────────────────────
    # If auto_hunt_settings.test_mode_started_at is set within last 48h, add a
    # dedicated report block: What ran · What failed · What auto-repaired · Attention.
    test_mode_report: Optional[dict] = None
    try:
        ahs = await db.auto_hunt_settings.find_one({"_id": "singleton"}) or {}
        tm_ts = ahs.get("test_mode_started_at")
        if tm_ts:
            # Parse ISO; keep block active for 48h
            try:
                tm_dt = datetime.fromisoformat(tm_ts.replace("Z", "+00:00"))
            except Exception:
                tm_dt = None
            active = bool(tm_dt and (datetime.now(timezone.utc) - tm_dt) < timedelta(hours=48))
            if active:
                # What ran — agent cycles in last 24h
                cycles_24h = await db.a2a_events.count_documents({
                    "event": "daily_complete", "timestamp": {"$gte": day_ago_iso},
                })
                new_leads_ev = await db.a2a_events.count_documents({
                    "event": "new_leads_batch", "timestamp": {"$gte": day_ago_iso},
                })
                listener_acks = await db.a2a_events.count_documents({
                    "event": "listener_ack", "timestamp": {"$gte": day_ago_iso},
                })
                # What failed — build_log + recent errors
                failed_builds = await db.build_log.count_documents({
                    "status": "failed", "started_at": {"$gte": day_ago_iso},
                })
                # What auto-repaired — auto_repair_log entries in last 24h
                auto_repairs = 0
                try:
                    auto_repairs = await db.auto_repair_log.count_documents({
                        "timestamp": {"$gte": day_ago_iso},
                    })
                except Exception:
                    pass
                # Needs attention — pending genes + active anomalies
                pending_genes = 0
                active_anomalies = 0
                try:
                    pending_genes = await db.evolver_genes.count_documents({"status": "pending_review"})
                except Exception:
                    pass
                try:
                    active_anomalies = await db.anomalies.count_documents({
                        "resolved": False, "detected_at": {"$gte": day_ago_iso},
                    })
                except Exception:
                    pass

                test_mode_report = {
                    "started_at": tm_ts,
                    "agent_cycles": cycles_24h,
                    "new_leads_events": new_leads_ev,
                    "listener_acks": listener_acks,
                    "failed_builds": failed_builds,
                    "auto_repairs": auto_repairs,
                    "pending_genes": pending_genes,
                    "active_anomalies": active_anomalies,
                }
    except Exception as e:
        logger.warning(f"[Digest] test_mode section failed: {e}")

    return {
        "opens": opens,
        "clicks": clicks,
        "hottest": live_doc,
        "replies": replies,
        "calls_24h": calls_count,
        "stages": stage_counts,
        "won_this_week": won_this_week,
        "this_week_avg_days": this_week_avg,
        "last_week_avg_days": last_week_avg,
        "pct_change_days": pct_change,
        "ramp_status": ramp_status,
        "test_mode": test_mode_report,
    }


def _format_digest(data: dict) -> str:
    """Render the WhatsApp message body."""
    today = datetime.now(timezone.utc).astimezone().strftime("%a, %b %d")
    opens = data["opens"]
    clicks = data["clicks"]
    hottest = data["hottest"]
    replies = data["replies"]
    stages = data["stages"]

    lines = [f"🌅 *AUREM Morning Digest — {today}*", ""]

    # Emails opened
    lines.append(f"📧 Emails opened last night: *{len(opens)}*")
    if opens:
        names = [o.get("business_name") or "?" for o in opens[:4]]
        lines.append("  " + ", ".join(names) + (" …" if len(opens) > 4 else ""))
    lines.append("")

    # Clicks
    if clicks:
        lines.append(f"🖱 Clicks: *{len(clicks)}*")
        for c in clicks[:3]:
            lines.append(f"  · {c.get('business_name') or '?'}")
        lines.append("")

    # Hottest lead
    if hottest:
        lines.append(f"🔥 Hottest lead: *{hottest.get('business_name') or '?'}* — pings {hottest.get('ping_count', 0)}")
        lines.append("")

    # Replies — follow up today
    if replies:
        lines.append("💬 Replied (follow up TODAY):")
        for r in replies[:5]:
            n = r.get("business_name") or r.get("contact_name") or "?"
            body = r.get("body") or ""
            preview = f" — _{body[:60]}_" if body else ""
            lines.append(f"  · {n}{preview}")
        lines.append("")

    # Calls
    lines.append(f"📞 Calls made: *{data['calls_24h']}*")
    lines.append("")

    # Pipeline snapshot
    lines.append("*📊 Pipeline:*")
    lines.append(
        f"New: {stages.get('new', 0)} · "
        f"Engaged: {stages.get('engaged', 0)} · "
        f"Following Up: {stages.get('following_up', 0)}"
    )
    if data["won_this_week"] > 0:
        lines.append(f"✅ Won this week: *{data['won_this_week']}* 🎉")
    lines.append("")

    # Avg-days trend
    twa = data["this_week_avg_days"]
    lwa = data["last_week_avg_days"]
    pct = data["pct_change_days"]
    if twa > 0 or lwa > 0:
        arrow = "↓" if pct < 0 else ("↑" if pct > 0 else "→")
        lines.append(f"⏱ Avg days to close: *{twa}* ({arrow}{abs(pct)}% vs last week)")
        lines.append("")

    # Footer
    # Auto-Hunt ramp status line (Safe vs Aggressive) — computed in _collect_data
    ramp = data.get("ramp_status")
    if ramp:
        lines.append(ramp)
        lines.append("")

    # ── TEST MODE BLOCK ──
    tm = data.get("test_mode")
    if tm:
        lines.append("🧪 *TEST MODE — last 24h*")
        lines.append(f"  ✓ Ran: {tm['agent_cycles']} agent cycles · {tm['new_leads_events']} new-leads events · {tm['listener_acks']} listener acks")
        lines.append(f"  ✗ Failed: {tm['failed_builds']} build(s)")
        lines.append(f"  🔧 Auto-repaired: {tm['auto_repairs']} runtime issue(s)")
        attention_bits = []
        if tm["pending_genes"]:
            attention_bits.append(f"{tm['pending_genes']} gene(s) pending review")
        if tm["active_anomalies"]:
            attention_bits.append(f"{tm['active_anomalies']} open anomaly/anomalies")
        if attention_bits:
            lines.append(f"  ⚠️ Attention: {' · '.join(attention_bits)}")
        else:
            lines.append("  ⚠️ Attention: none — clean run ✅")
        lines.append("")

    base = os.environ.get("PUBLIC_APP_URL", "https://aurem.live").rstrip("/")
    lines.append(f"{base}/dashboard → full pipeline")

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────
async def build_digest(db) -> dict:
    data = await _collect_data(db)
    body = _format_digest(data)
    return {"body": body, "data": data}


async def _send_whatsapp_digest(body: str, phone: Optional[str] = None) -> bool:
    """iter 326e — thin shim used by `nightly_cycle.send_evening_brief`.

    The evening brief job in `services/nightly_cycle.py` calls this name
    via a runtime import. It was renamed when this module was refactored
    around iter 320, leaving the nightly job logging:
       [EveningBrief] send failed: cannot import name '_send_whatsapp_digest'
       from 'services.morning_digest'
    every single night. This shim restores the contract: deliver the
    pre-formatted body to the founder's WHAPI phone using the same
    `_wa_send` helper the morning digest uses. Returns True on success.
    """
    target = phone or os.environ.get("AUREM_HOT_LEAD_PHONE", "+16134000000")
    return await _wa_send(target, body)


async def send_morning_digest(db, to_phone: Optional[str] = None) -> dict:
    """Build + send the digest. Returns {sent, to, body_preview}."""
    data = await _collect_data(db)
    body = _format_digest(data)
    phone = to_phone or os.environ.get("AUREM_HOT_LEAD_PHONE", "+16134000000")

    sent = await _wa_send(phone, body)
    # Log to dedicated collection
    try:
        await db.morning_digest_log.insert_one({
            "to": phone,
            "sent": sent,
            "sent_at": datetime.now(timezone.utc).isoformat(),
            "body": body,
            "summary": {k: v for k, v in data.items() if k in ("calls_24h", "stages", "won_this_week", "this_week_avg_days", "pct_change_days")},
            "opens_count": len(data.get("opens") or []),
            "clicks_count": len(data.get("clicks") or []),
            "replies_count": len(data.get("replies") or []),
        })
    except Exception as e:
        logger.warning(f"[Digest] log failed: {e}")

    return {"sent": sent, "to": phone, "body_preview": body[:400], "opens": len(data["opens"]), "replies": len(data["replies"])}
