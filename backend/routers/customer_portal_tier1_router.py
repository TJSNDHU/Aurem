"""
Customer Portal Tier-1 router (iter D-84)
═════════════════════════════════════════════════════════════════════════════
Customer-facing, BIN-scoped, zero-mock endpoints for the /my portal:

  §1  GET  /api/customer/activity         — "Aaj ORA ne kya kiya" feed (union)
  §2  GET  /api/customer/leads/funnel     — pipeline funnel counts
      GET  /api/customer/leads            — paginated leads list
  §3  GET  /api/customer/appointments     — upcoming + past bookings

All reads derive the tenant BIN server-side (never trust a client-sent bin)
via the same rule v2_customer_actions_router uses: business_id → bin → email-prefix.
Every collection / field name below was verified against live Mongo.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/customer", tags=["customer · portal tier-1"])

_db = None


def set_db(database) -> None:
    global _db
    _db = database


def _customer_bin(request: Request) -> str:
    """Server-side BIN derivation — identical to missing_endpoints_router so
    every customer surface resolves the same tenant. Never trusts a client bin."""
    from routers.missing_endpoints_router import _customer_bin as _shared
    return _shared(request)


def _db_or_503():
    if _db is None:
        raise HTTPException(503, "Database unavailable")
    return _db


# ═══════════════════════════════════════════════════════════════════════════
# §1 — Activity feed (real bin-scoped union)
# ═══════════════════════════════════════════════════════════════════════════
def _iso(v: Any) -> str:
    if isinstance(v, datetime):
        return v.astimezone(timezone.utc).isoformat()
    return str(v) if v else ""


@router.get("/activity")
async def activity(request: Request, limit: int = 30, before: Optional[str] = None) -> Dict[str, Any]:
    bin_id = _customer_bin(request)
    db = _db_or_503()
    limit = max(1, min(limit, 50))
    per = limit + 10  # over-fetch per source, then merge

    def _ts_filter(field: str) -> Dict[str, Any]:
        return {field: {"$lt": before}} if before else {}

    items: List[Dict[str, Any]] = []

    # — scans —
    async for d in db.customer_scans.find(
        {"tenant_bin": bin_id, **_ts_filter("created_at")},
        {"_id": 0, "created_at": 1, "overall_score": 1, "score": 1, "website": 1},
    ).sort("created_at", -1).limit(per):
        score = d.get("overall_score") or d.get("score")
        items.append({
            "ts": _iso(d.get("created_at")), "type": "scan", "icon_hint": "scan",
            "title": "Website scan completed",
            "detail": (f"Health score: {score}/100" if score is not None else d.get("website", "")),
            "link": "/my/website",
        })

    # — repairs / site fixes —
    async for d in db.repair_jobs.find(
        {"tenant_bin": bin_id, **_ts_filter("created_at")},
        {"_id": 0, "created_at": 1, "status": 1, "repair_plan": 1, "current_phase_label": 1},
    ).sort("created_at", -1).limit(per):
        n = len(d.get("repair_plan") or [])
        st = d.get("status", "")
        title = "Repair plan ready" if st == "plan_ready_for_customer" else f"Repair job — {st or 'running'}"
        items.append({
            "ts": _iso(d.get("created_at")), "type": "fix", "icon_hint": "fix",
            "title": title,
            "detail": (f"{n} fix items generated" if n else d.get("current_phase_label", "")),
            "link": "/my/website",
        })

    # — ORA outreach / sourced leads —
    async for d in db.campaign_leads.find(
        {"business_id": bin_id, **_ts_filter("created_at")},
        {"_id": 0, "created_at": 1, "last_blast_at": 1, "business_name": 1, "status": 1},
    ).sort("created_at", -1).limit(per):
        name = d.get("business_name") or "a prospect"
        if d.get("last_blast_at"):
            items.append({
                "ts": _iso(d.get("last_blast_at")), "type": "outreach", "icon_hint": "outreach",
                "title": "ORA sent outreach", "detail": f"To {name}", "link": "/my/leads",
            })
        items.append({
            "ts": _iso(d.get("created_at")), "type": "lead", "icon_hint": "lead",
            "title": "ORA sourced a lead", "detail": name,
            "link": "/my/leads",
        })

    # — appointments —
    async for d in db.appointments.find(
        {"business_id": bin_id, **_ts_filter("created_at")},
        {"_id": 0, "created_at": 1, "appointment_datetime": 1, "name": 1, "channel": 1},
    ).sort("created_at", -1).limit(per):
        items.append({
            "ts": _iso(d.get("created_at")), "type": "appointment", "icon_hint": "appointment",
            "title": "Appointment booked",
            "detail": (d.get("name") or "") + (f" · {d.get('channel')}" if d.get("channel") else ""),
            "link": "/my/appointments",
        })

    items = [i for i in items if i["ts"]]
    items.sort(key=lambda x: x["ts"], reverse=True)
    page = items[:limit]
    next_before = page[-1]["ts"] if len(page) == limit and len(items) > limit else None
    return {"bin_id": bin_id, "items": page, "count": len(page), "next_before": next_before}


# ═══════════════════════════════════════════════════════════════════════════
# §2 — Leads & pipeline (campaign_leads, bin = business_id, stage = `status`)
# ═══════════════════════════════════════════════════════════════════════════
# Map raw lead status values → the 4 funnel stages the UI shows.
_STAGE_MAP = {
    "new": "found", "sourced": "found", "queued": "found", "pending": "found",
    "scanned": "found", "enriched": "found",
    "contacted": "contacted", "emailed": "contacted", "blasted": "contacted",
    "called": "contacted", "whatsapp_sent": "contacted", "sms_sent": "contacted",
    "replied": "replied", "responded": "replied", "engaged": "replied", "interested": "replied",
    "booked": "booked", "meeting": "booked", "converted": "booked", "won": "booked",
}
_FUNNEL_ORDER = ["found", "contacted", "replied", "booked"]


def _stage_of(status: Optional[str]) -> str:
    return _STAGE_MAP.get((status or "").strip().lower(), "found")


@router.get("/leads/funnel")
async def leads_funnel(request: Request) -> Dict[str, Any]:
    bin_id = _customer_bin(request)
    db = _db_or_503()
    counts = {s: 0 for s in _FUNNEL_ORDER}
    total = 0
    async for d in db.campaign_leads.find({"business_id": bin_id}, {"_id": 0, "status": 1}):
        counts[_stage_of(d.get("status"))] += 1
        total += 1
    return {"bin_id": bin_id, "total": total,
            "funnel": [{"stage": s, "count": counts[s]} for s in _FUNNEL_ORDER]}


@router.get("/leads")
async def leads_list(request: Request, stage: Optional[str] = None, page: int = 1) -> Dict[str, Any]:
    bin_id = _customer_bin(request)
    db = _db_or_503()
    page = max(1, page)
    per = 25
    q: Dict[str, Any] = {"business_id": bin_id}
    cursor = db.campaign_leads.find(
        q, {"_id": 0, "business_name": 1, "contact_name": 1, "source": 1,
            "status": 1, "updated_at": 1, "created_at": 1, "last_reply_snippet": 1},
    ).sort("updated_at", -1)
    rows: List[Dict[str, Any]] = []
    async for d in cursor:
        st = _stage_of(d.get("status"))
        if stage and st != stage:
            continue
        rows.append({
            "business_name": d.get("business_name") or "—",
            "contact_name": d.get("contact_name") or "",
            "source": d.get("source") or "ORA hunt",
            "stage": st, "raw_status": d.get("status"),
            "last_touch": _iso(d.get("updated_at") or d.get("created_at")),
            "reply_snippet": (d.get("last_reply_snippet") or "")[:160],
        })
    start = (page - 1) * per
    return {"bin_id": bin_id, "total": len(rows), "page": page, "per_page": per,
            "leads": rows[start:start + per], "has_more": len(rows) > start + per}


# ═══════════════════════════════════════════════════════════════════════════
# §3 — Appointments (db.appointments, bin = business_id)
# ═══════════════════════════════════════════════════════════════════════════
@router.get("/appointments")
async def appointments(request: Request) -> Dict[str, Any]:
    bin_id = _customer_bin(request)
    db = _db_or_503()
    now = datetime.now(timezone.utc).isoformat()
    upcoming: List[Dict[str, Any]] = []
    past: List[Dict[str, Any]] = []
    async for d in db.appointments.find(
        {"business_id": bin_id},
        {"_id": 0, "appointment_datetime": 1, "name": 1, "email": 1,
         "channel": 1, "status": 1, "notes": 1, "appointment_type": 1},
    ).sort("appointment_datetime", 1):
        when = _iso(d.get("appointment_datetime"))
        row = {
            "when": when, "with_whom": d.get("name") or d.get("email") or "—",
            "channel": d.get("channel") or d.get("appointment_type") or "",
            "status": d.get("status") or "scheduled", "notes": (d.get("notes") or "")[:200],
        }
        (upcoming if when and when >= now else past).append(row)
    past.reverse()
    return {"bin_id": bin_id, "upcoming": upcoming, "past": past,
            "count": len(upcoming) + len(past)}


print("[STARTUP] Customer Portal Tier-1 router loaded (activity/leads/appointments)", flush=True)
