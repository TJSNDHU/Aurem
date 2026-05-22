"""
services/ora_morning_brief.py — iter 326gg (Phase 3 P3.2).

Mobile-first morning brief. The founder opens their phone at 7am and
sees yesterday's revenue / campaigns / alerts / today's focus leads
on one short screen. No 8 emails, no Telegram noise — one structured
JSON the mobile UI renders into big-text cards.

Reuses existing data — never invents numbers.

Public API
──────────
    set_db(database)
    await build_brief(tenant_id: str | None = None, *, founder_email: str | None = None)
        → {
            ok, date, campaigns, revenue, alerts, focus_leads,
            decisions, generated_at
          }
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

_db = None


def set_db(database) -> None:
    global _db
    _db = database


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _day_window(days_back: int = 1) -> tuple[datetime, datetime, str]:
    """Return (start, end, label) for the 24h window starting `days_back`
    days ago at UTC midnight."""
    now = _now()
    end = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start = end - timedelta(days=days_back)
    label = start.strftime("%Y-%m-%d")
    return start, end, label


async def _campaigns_yesterday() -> dict:
    """Outreach numbers from yesterday's UTC day."""
    if _db is None:
        return {"sent": 0, "replies": 0, "leads_blasted": 0}
    start, end, _ = _day_window(1)
    start_iso, end_iso = start.isoformat(), end.isoformat()
    sent = await _db.campaign_leads.count_documents({
        "outreach_history.timestamp": {"$gte": start_iso, "$lt": end_iso},
    })
    # Replies (any 'reply' or 'interested' status surfacing in outreach_history)
    replies = await _db.campaign_leads.count_documents({
        "outreach_history": {
            "$elemMatch": {
                "type":   {"$in": ["voice_response", "reply"]},
                "status": {"$nin": ["failed"]},
                "timestamp": {"$gte": start_iso, "$lt": end_iso},
            },
        },
    })
    leads_blasted = await _db.campaign_leads.count_documents({
        "last_blast_at": {"$gte": start_iso, "$lt": end_iso},
    })
    return {"sent": sent, "replies": replies, "leads_blasted": leads_blasted}


async def _revenue_today_vs_yesterday() -> dict:
    """Best-effort revenue delta. Reads `customer_subscriptions` /
    `payments` collections without inventing numbers — if neither has
    rows, returns None for the delta so the UI can render '—'."""
    if _db is None:
        return {"mrr_now": None, "mrr_yesterday": None, "delta": None}
    mrr_now = None
    try:
        active = await _db.customer_subscriptions.count_documents(
            {"status": {"$in": ["active", "trialing"]}}
        )
        if active is not None:
            mrr_now = active
    except Exception:
        pass
    return {"active_subscriptions": mrr_now, "delta": None}


async def _alerts_open() -> list[dict]:
    """Anything the founder must look at today: failed payments, churn
    risk, daemon trips, etc. Read-only — pulls from `incident_bus` if
    present, otherwise returns empty."""
    if _db is None:
        return []
    out: list[dict] = []
    try:
        cutoff = (_now() - timedelta(hours=24)).isoformat()
        async for d in _db.incident_bus.find(
            {"ts": {"$gte": cutoff}, "resolved": {"$ne": True}},
            {"_id": 0, "ts": 1, "severity": 1, "title": 1, "source": 1},
        ).sort("ts", -1).limit(10):
            out.append({
                "ts":       d.get("ts"),
                "severity": d.get("severity") or "info",
                "title":    d.get("title") or "(no title)",
                "source":   d.get("source") or "system",
            })
    except Exception as e:
        logger.debug(f"[morning-brief] incidents skipped: {e}")
    return out


async def _focus_leads(limit: int = 10) -> list[dict]:
    """Top warm leads — replied or scored high, not yet won/lost."""
    if _db is None:
        return []
    out: list[dict] = []
    try:
        cur = (
            _db.campaign_leads
            .find(
                {"status": {"$in": ["replied", "warm", "qualified"]}},
                {"_id": 0, "lead_id": 1, "business_name": 1, "city": 1,
                 "industry": 1, "score": 1, "status": 1, "updated_at": 1},
            )
            .sort([("score", -1), ("updated_at", -1)])
            .limit(int(limit))
        )
        async for d in cur:
            out.append(d)
    except Exception as e:
        logger.debug(f"[morning-brief] focus leads skipped: {e}")
    return out


async def _recent_decisions(limit: int = 5) -> list[dict]:
    """Last few ORA decisions so the founder can see what auto-executed
    overnight without opening the full Recent Decisions panel."""
    if _db is None:
        return []
    out: list[dict] = []
    try:
        cutoff = _now() - timedelta(hours=24)
        cur = (
            _db.ora_decisions
            .find({"ts": {"$gte": cutoff}},
                  {"_id": 0, "ts": 1, "tool": 1, "outcome": 1, "summary": 1})
            .sort("ts", -1)
            .limit(int(limit))
        )
        async for d in cur:
            ts = d.get("ts")
            out.append({
                "ts":      ts.isoformat() if isinstance(ts, datetime) else ts,
                "tool":    d.get("tool"),
                "outcome": d.get("outcome"),
                "summary": (d.get("summary") or "")[:200],
            })
    except Exception as e:
        logger.debug(f"[morning-brief] decisions skipped: {e}")
    return out


async def build_brief(
    tenant_id: Optional[str] = None,
    *,
    founder_email: Optional[str] = None,
) -> dict:
    """Aggregate all four sections into the mobile-ready payload."""
    _, _, label = _day_window(1)
    campaigns = await _campaigns_yesterday()
    revenue   = await _revenue_today_vs_yesterday()
    alerts    = await _alerts_open()
    focus     = await _focus_leads()
    decisions = await _recent_decisions()

    return {
        "ok":           True,
        "date":         label,
        "tenant_id":    tenant_id or "global",
        "founder":      founder_email,
        "campaigns":    campaigns,
        "revenue":      revenue,
        "alerts":       alerts,
        "alerts_count": len(alerts),
        "focus_leads":  focus,
        "focus_count":  len(focus),
        "decisions":    decisions,
        "generated_at": _now().isoformat(),
    }
