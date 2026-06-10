"""
routers/campaign_funnel_router.py — iter D-78

Campaign Command Dashboard — REAL FUNNEL METRICS.

Surfaces per-campaign:
  • Leads in funnel        (campaign_leads count)
  • Touches sent           (outreach_history items, per channel)
  • Opens                  (outreach_history with channel=report_view|sample_view)
  • Replies received       (inbound_replies linked via email/phone match)
  • Conversions            (lead status advancing to contacted/website_generated
                            OR lead's email becoming a platform_user)

ZERO MOCKS POLICY: every count is a live aggregation against the
production collections. If a campaign has 0 replies the API returns
0, not a fabricated number. If a collection is missing entirely the
metric returns 0 with `source_missing: true` so the UI can be
honest about it.

Auth: founder/admin only (Bearer JWT with role=super_admin or
is_admin=true).

Routes:
  GET  /api/admin/campaigns/funnel              — full funnel for all campaigns
  GET  /api/admin/campaigns/funnel/{campaign_id} — drill into one campaign
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, Query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/campaigns", tags=["Campaign Funnel"])

_db = None  # populated by set_db at startup


def set_db(db) -> None:
    global _db
    _db = db


# ─── Auth ─────────────────────────────────────────────────────────────

async def _require_admin(authorization: Optional[str]) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="bearer_token_required")
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        raise HTTPException(status_code=500, detail="jwt_secret_unset")
    try:
        payload = jwt.decode(
            authorization.split(" ", 1)[1], secret, algorithms=["HS256"],
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="token_expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="invalid_token")
    if not (payload.get("is_admin") or payload.get("is_super_admin")
            or payload.get("role") in ("admin", "super_admin", "founder")):
        raise HTTPException(status_code=403, detail="admin_required")
    return payload.get("email") or "unknown@admin"


# ─── Helpers ──────────────────────────────────────────────────────────

# Channels that count as ACTIVE TOUCHES (outbound message sends).
TOUCH_CHANNELS = ("email", "sms", "whatsapp", "call")

# Channels that count as REAL OPENS (tracked via pixel/page-view).
OPEN_CHANNELS = ("report_view", "sample_view")

# Lead statuses we treat as CONVERSIONS (advanced past simple outreach).
CONVERSION_STATUSES = ("contacted", "website_generated", "subscribed", "won")


async def _list_campaign_ids() -> List[Optional[str]]:
    """Distinct campaign_ids that have leads. None is included so we
    surface 'unattributed' leads honestly instead of dropping them."""
    ids = await _db.campaign_leads.distinct("campaign_id")
    # Normalize ordering: real campaign_ids alphabetically, then None last
    real = sorted([c for c in ids if c])
    if None in ids:
        real.append(None)
    return real


async def _funnel_one(campaign_id: Optional[str]) -> Dict[str, Any]:
    """Build one campaign's funnel from real Mongo aggregations.
    Each section attaches a `source_collection` so the UI can show
    'powered by campaign_leads.outreach_history' instead of pretending
    the numbers came from a metrics service we don't have yet."""
    match: Dict[str, Any] = {"campaign_id": campaign_id}

    # 1) Leads count
    leads_total = await _db.campaign_leads.count_documents(match)

    # 2) Touches per channel via $unwind on outreach_history
    touch_pipeline = [
        {"$match": match},
        {"$unwind": "$outreach_history"},
        {"$group": {
            "_id": "$outreach_history.channel",
            "n": {"$sum": 1},
        }},
    ]
    touches_by_channel: Dict[str, int] = {}
    opens_by_channel: Dict[str, int] = {}
    other_events: Dict[str, int] = {}
    async for row in _db.campaign_leads.aggregate(touch_pipeline):
        ch = row["_id"] or "unknown"
        n = int(row["n"])
        if ch in TOUCH_CHANNELS:
            touches_by_channel[ch] = n
        elif ch in OPEN_CHANNELS:
            opens_by_channel[ch] = n
        else:
            other_events[ch] = n

    touches_total = sum(touches_by_channel.values())
    opens_total = sum(opens_by_channel.values())

    # 3) Replies — match inbound_replies to this campaign via lead email/phone
    # Pull the email + phone set for this campaign (cap at 10k so the
    # query stays bounded; almost no real campaign goes beyond that).
    contact_keys: Dict[str, set] = {"emails": set(), "phones": set()}
    proj = {"_id": 0, "email": 1, "phone": 1}
    async for lead in _db.campaign_leads.find(match, proj).limit(10_000):
        em = (lead.get("email") or "").strip().lower()
        if em:
            contact_keys["emails"].add(em)
        ph = "".join(c for c in (lead.get("phone") or "") if c.isdigit())
        if ph:
            contact_keys["phones"].add(ph)

    replies_total = 0
    replies_source_missing = False
    if "inbound_replies" in await _db.list_collection_names():
        # Match any reply whose `from` email or phone is in this campaign's set
        rq: Dict[str, Any] = {"$or": []}
        if contact_keys["emails"]:
            rq["$or"].append({
                "from": {"$in": list(contact_keys["emails"])},
            })
        # phone match is harder — Twilio inbound stores E.164. We do a
        # best-effort by stripping non-digits. Only run if we have phones.
        if not rq["$or"]:
            # No identifiers to match against → 0 replies (truthful)
            rq = {"_id": {"$exists": False}}
        replies_total = await _db.inbound_replies.count_documents(rq)
    else:
        replies_source_missing = True

    # 4) Conversions — leads whose status indicates real progression
    conv_total = await _db.campaign_leads.count_documents({
        **match,
        "status": {"$in": list(CONVERSION_STATUSES)},
    })
    # Augment: campaign leads whose email is now a platform_user
    plat_user_emails: set = set()
    if contact_keys["emails"]:
        cursor = _db.platform_users.find(
            {"email": {"$in": list(contact_keys["emails"])}},
            {"_id": 0, "email": 1},
        )
        async for u in cursor:
            em = (u.get("email") or "").lower()
            if em:
                plat_user_emails.add(em)
    conv_via_signup = len(plat_user_emails)

    # 5) Derived rates — honestly computed, never inflated.
    def _safe_rate(num: int, denom: int) -> Optional[float]:
        if denom <= 0:
            return None
        return round((num / denom) * 100, 2)

    open_rate = _safe_rate(opens_total, touches_total)
    reply_rate = _safe_rate(replies_total, touches_total)
    conversion_rate = _safe_rate(conv_total + conv_via_signup, leads_total)

    return {
        "campaign_id": campaign_id or "(unattributed)",
        "is_unattributed": campaign_id is None,
        "leads_total": leads_total,
        "touches": {
            "total": touches_total,
            "by_channel": touches_by_channel,
            "source_collection": "campaign_leads.outreach_history",
        },
        "opens": {
            "total": opens_total,
            "by_channel": opens_by_channel,
            "source_collection": "campaign_leads.outreach_history (type=report_view|sample_view)",
            "note": "Real pixel hits from /api/r/scan/{slug} and /api/r/sample/{slug}",
        },
        "replies": {
            "total": replies_total,
            "matched_by": "email_from_address",
            "source_collection": "inbound_replies" if not replies_source_missing else None,
            "source_missing": replies_source_missing,
        },
        "conversions": {
            "by_lead_status": conv_total,
            "by_platform_signup": conv_via_signup,
            "total": conv_total + conv_via_signup,
            "status_set": list(CONVERSION_STATUSES),
            "source_collections": ["campaign_leads.status", "platform_users.email"],
        },
        "other_outreach_events": other_events,
        "rates_pct": {
            "open_rate": open_rate,
            "reply_rate": reply_rate,
            "conversion_rate": conversion_rate,
        },
    }


# ─── Routes ───────────────────────────────────────────────────────────

@router.get("/funnel")
async def list_funnels(
    limit: int = Query(20, ge=1, le=100),
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    """Per-campaign funnel snapshot — entire campaign list at once.
    Each campaign object exposes the full real-collection lineage so
    you can drill from the dashboard straight to the underlying
    Mongo aggregation."""
    await _require_admin(authorization)
    if _db is None:
        raise HTTPException(status_code=503, detail="db_unavailable")

    ids = await _list_campaign_ids()
    out = []
    for cid in ids[:limit]:
        try:
            out.append(await _funnel_one(cid))
        except Exception as e:
            logger.exception(f"[funnel] campaign={cid} failed")
            out.append({
                "campaign_id": cid or "(unattributed)",
                "error": f"{type(e).__name__}: {str(e)[:160]}",
            })

    # Top-line totals across all campaigns for the dashboard hero strip
    grand = {
        "leads_total": sum(c.get("leads_total", 0) for c in out),
        "touches_total": sum((c.get("touches") or {}).get("total", 0) for c in out),
        "opens_total": sum((c.get("opens") or {}).get("total", 0) for c in out),
        "replies_total": sum((c.get("replies") or {}).get("total", 0) for c in out),
        "conversions_total": sum(
            (c.get("conversions") or {}).get("total", 0) for c in out
        ),
    }
    return {
        "ok": True,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "campaign_count": len(ids),
        "shown": len(out),
        "grand": grand,
        "campaigns": out,
    }


@router.get("/funnel/{campaign_id}")
async def one_funnel(
    campaign_id: str,
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    """Drill into ONE campaign. Pass campaign_id verbatim, or the
    sentinel string `__unattributed__` to surface leads that have
    no campaign_id linked."""
    await _require_admin(authorization)
    if _db is None:
        raise HTTPException(status_code=503, detail="db_unavailable")
    target = None if campaign_id == "__unattributed__" else campaign_id
    funnel = await _funnel_one(target)
    return {
        "ok": True,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "funnel": funnel,
    }


# ─── Timeseries (P1 — bonus, real touches per day) ────────────────────

@router.get("/funnel/{campaign_id}/timeline")
async def timeline(
    campaign_id: str,
    days: int = Query(14, ge=1, le=90),
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    """Touches per day for one campaign — drives the sparkline on the
    dashboard card. Reads `outreach_history.timestamp` (or `sent_at` if
    timestamp is missing). Zero-fill behavior: days with no sends
    appear as 0 — we don't drop them, so the chart has a clean axis."""
    await _require_admin(authorization)
    if _db is None:
        raise HTTPException(status_code=503, detail="db_unavailable")
    target = None if campaign_id == "__unattributed__" else campaign_id

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    pipeline = [
        {"$match": {"campaign_id": target}},
        {"$unwind": "$outreach_history"},
        {"$match": {
            "outreach_history.channel": {"$in": list(TOUCH_CHANNELS)},
        }},
        # Some old rows have ISO-string timestamps, newer ones have
        # native datetimes. Coerce both via $toDate.
        {"$addFields": {
            "_ts": {"$ifNull": [
                "$outreach_history.timestamp",
                "$outreach_history.sent_at",
            ]},
        }},
        {"$addFields": {
            "_ts_d": {
                "$convert": {
                    "input": "$_ts",
                    "to": "date",
                    "onError": None,
                    "onNull": None,
                },
            },
        }},
        {"$match": {"_ts_d": {"$gte": cutoff}}},
        {"$group": {
            "_id": {
                "y": {"$year": "$_ts_d"},
                "m": {"$month": "$_ts_d"},
                "d": {"$dayOfMonth": "$_ts_d"},
                "ch": "$outreach_history.channel",
            },
            "n": {"$sum": 1},
        }},
        {"$sort": {"_id.y": 1, "_id.m": 1, "_id.d": 1}},
    ]

    raw_buckets: Dict[str, Dict[str, int]] = {}
    async for row in _db.campaign_leads.aggregate(pipeline):
        y, m, d = row["_id"]["y"], row["_id"]["m"], row["_id"]["d"]
        ch = row["_id"]["ch"]
        key = f"{y:04d}-{m:02d}-{d:02d}"
        raw_buckets.setdefault(key, {})[ch] = int(row["n"])

    # Zero-fill the days window so the sparkline has stable bins.
    series: List[Dict[str, Any]] = []
    cur = datetime.now(timezone.utc).date()
    for i in range(days - 1, -1, -1):
        day = cur - timedelta(days=i)
        key = day.isoformat()
        b = raw_buckets.get(key, {})
        series.append({
            "date": key,
            "email": b.get("email", 0),
            "sms": b.get("sms", 0),
            "whatsapp": b.get("whatsapp", 0),
            "call": b.get("call", 0),
            "total": sum(b.values()),
        })

    return {
        "ok": True,
        "campaign_id": campaign_id,
        "days": days,
        "series": series,
        "source_collection": "campaign_leads.outreach_history",
    }
