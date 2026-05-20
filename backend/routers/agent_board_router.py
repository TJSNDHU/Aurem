"""
AUREM Agent Board Router — "Sovereign Boardroom"
=================================================
Iter 288.0 — Exposes the Revenue-Reflector to the Admin PWA.

Endpoints (all FOUNDER-only — require is_admin JWT):
  GET  /api/agents/board/rollup?days=1|7|30      — Live Ledger Hub numbers
  GET  /api/agents/board/ledger?days=7           — full per-agent P&L table
  GET  /api/agents/board/roi/{agent_id}?days=7   — single-agent deep dive
  POST /api/agents/board/meeting                 — ORA "Board Meeting" trigger
  GET  /api/agents/board/soul/{agent_id}         — fetch the agent's SOUL.md
  GET  /api/agents/board/rates                   — fetch editable rate card
  PUT  /api/agents/board/rates/{key}             — update one rate
  POST /api/agents/board/record-cost             — manual cost pin (debug/demo)
  POST /api/agents/board/record-revenue          — mark realized/potential $
  GET  /api/agents/board/kill-switch?days=7      — who should be fired
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import jwt as pyjwt
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/agents/board", tags=["Agent Boardroom"])

_db = None


def set_db(db):
    global _db
    _db = db


def _get_db():
    return _db


def _require_founder(request: Request) -> Dict[str, Any]:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Missing Bearer token")
    try:
        from middleware.tenant_guard import JWT_SECRET, JWT_ALGORITHM
        payload = pyjwt.decode(
            auth.split(" ", 1)[1], JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
        )
    except Exception as e:
        raise HTTPException(401, f"Invalid token: {e}")
    if not (payload.get("is_admin") or payload.get("is_super_admin")):
        raise HTTPException(403, "Founder only")
    return payload


# ─────────────────────────────────────────────────────────────
# MODELS
# ─────────────────────────────────────────────────────────────
class RateUpdate(BaseModel):
    rate: float = Field(..., ge=0)
    label: Optional[str] = None
    unit: Optional[str] = None


class CostRecord(BaseModel):
    agent_id: str
    source: str
    units: float
    meta: Optional[Dict[str, Any]] = None


class RevenueRecord(BaseModel):
    agent_id: str
    amount_usd: float
    stage: str  # potential | interested | closed_won | closed_lost
    lead_id: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None


# ─────────────────────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────────────────────
@router.get("/rollup")
async def rollup(request: Request, days: int = 1,
                   exclude_synthetic: bool = False):
    _require_founder(request)
    from services.agent_ledger import get_top_rollup
    return await get_top_rollup(_get_db(), days=max(1, min(days, 90)),
                                    exclude_synthetic=exclude_synthetic)


@router.get("/ledger")
async def ledger(request: Request, days: int = 7,
                   exclude_synthetic: bool = False):
    _require_founder(request)
    from services.agent_ledger import get_board
    return {"days": days, "exclude_synthetic": exclude_synthetic,
            "rows": await get_board(_get_db(), days=max(1, min(days, 90)),
                                        exclude_synthetic=exclude_synthetic)}


@router.get("/roi/{agent_id}")
async def agent_roi(request: Request, agent_id: str, days: int = 7,
                       exclude_synthetic: bool = False):
    _require_founder(request)
    from services.agent_ledger import get_roi
    return await get_roi(_get_db(), agent_id,
                            days=max(1, min(days, 90)),
                            exclude_synthetic=exclude_synthetic)


@router.post("/meeting")
async def meeting(request: Request, days: int = 7):
    _require_founder(request)
    from services.agent_soul import board_meeting
    return await board_meeting(_get_db(), days=max(1, min(days, 90)))


@router.get("/soul/{agent_id}")
async def soul(request: Request, agent_id: str):
    _require_founder(request)
    from services.agent_soul import get_soul
    return get_soul(agent_id)


@router.get("/rates")
async def rates(request: Request):
    _require_founder(request)
    from services.agent_ledger import get_rates
    return await get_rates(_get_db())


@router.put("/rates/{key}")
async def update_rate(request: Request, key: str, body: RateUpdate):
    _require_founder(request)
    from services.agent_ledger import set_rate
    return await set_rate(_get_db(), key, body.rate, label=body.label, unit=body.unit)


@router.post("/record-cost")
async def record_cost_ep(request: Request, body: CostRecord):
    _require_founder(request)
    from services.agent_ledger import record_cost
    return await record_cost(_get_db(), body.agent_id, body.source, body.units, meta=body.meta)


@router.post("/record-revenue")
async def record_revenue_ep(request: Request, body: RevenueRecord):
    _require_founder(request)
    from services.agent_ledger import record_revenue
    return await record_revenue(_get_db(), body.agent_id, body.amount_usd, body.stage,
                                 lead_id=body.lead_id, meta=body.meta)


@router.get("/kill-switch")
async def kill_switch(request: Request, days: int = 7, min_roi: float = 0.5, min_cost: float = 1.0):
    _require_founder(request)
    from services.agent_ledger import kill_switch_check
    losers = await kill_switch_check(_get_db(), days=days, min_roi=min_roi, min_cost=min_cost)
    return {"days": days, "min_roi": min_roi, "min_cost": min_cost,
            "losers": losers, "count": len(losers)}


# ─────────────────────────────────────────────────────────────
# PHASE 3 · A2A LIVE RAIL
# Combines per-agent recent-activity pulse + a unified founder timeline
# (ledger costs + sentinel heals + deploys + ora commands).
# ─────────────────────────────────────────────────────────────
@router.post("/voice-log")
async def voice_log(request: Request):
    """Retell-AI webhook → voice_call_logs + DNC opt-out auto-push.

    PUBLIC: Retell hits this directly. No auth — protect via signature header
    if RETELL_WEBHOOK_SECRET is set; otherwise accept all (preview mode).

    Payload schema (Retell post-call event):
      {call_id, agent_id, from_number, to_number, direction,
       duration_seconds, transcript, call_status, disconnection_reason,
       start_timestamp, end_timestamp}
    """
    db = _get_db()
    if db is None:
        return {"status": "ok", "skipped": "db_not_ready"}

    # ── Optional HMAC signature verification ──
    secret = os.environ.get("RETELL_WEBHOOK_SECRET", "").strip()
    raw = await request.body()
    if secret:
        sig = request.headers.get("x-retell-signature", "") or request.headers.get("x-aurem-sig", "")
        import hmac
        import hashlib
        expected = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
        if not sig or not hmac.compare_digest(sig.lower().replace("sha256=", ""), expected):
            logger.warning("[voice-log] bad signature — rejecting")
            raise HTTPException(401, "invalid signature")

    import json as _json
    try:
        body = _json.loads(raw.decode("utf-8") or "{}")
    except Exception:
        raise HTTPException(400, "invalid JSON")

    transcript = (body.get("transcript") or "").lower()

    # ── Intent extraction ──
    BOOK_KEYWORDS = ("book", "schedule", "appointment", "confirm")
    OPT_OUT_KEYWORDS = ("remove", "opt out", "opt-out", "not interested", "stop calling", "do not call")
    booked = any(k in transcript for k in BOOK_KEYWORDS)
    opted_out = any(k in transcript for k in OPT_OUT_KEYWORDS)

    duration_seconds = float(body.get("duration_seconds") or 0)
    from_number = (body.get("from_number") or "").strip()
    to_number = (body.get("to_number") or "").strip()
    direction = body.get("direction") or "outbound"

    # The "lead phone" is the non-AUREM end of the call
    lead_number = to_number if direction == "outbound" else from_number

    doc = {
        "call_id": body.get("call_id"),
        "agent_id": body.get("agent_id"),
        "from_number": from_number,
        "to_number": to_number,
        "lead_number": lead_number,
        "direction": direction,
        "duration_seconds": duration_seconds,
        "duration_minutes": round(duration_seconds / 60.0, 3),
        "transcript": body.get("transcript") or "",
        "call_status": body.get("call_status"),
        "disconnection_reason": body.get("disconnection_reason"),
        "start_timestamp": body.get("start_timestamp"),
        "end_timestamp": body.get("end_timestamp"),
        "booked": booked,
        "opted_out": opted_out,
        "received_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        await db.voice_call_logs.insert_one(dict(doc))
    except Exception as e:
        logger.warning(f"[voice-log] insert failed: {e}")
        raise HTTPException(500, "log insert failed")

    # ── DNC list push on opt-out ──
    if opted_out and lead_number:
        try:
            await db.dnc_list.update_one(
                {"phone": lead_number},
                {"$set": {
                    "phone": lead_number,
                    "source": "voice_call_optout",
                    "agent_id": body.get("agent_id"),
                    "call_id": body.get("call_id"),
                    "added_at": datetime.now(timezone.utc).isoformat(),
                }},
                upsert=True,
            )
            logger.info(f"[voice-log] DNC added: {lead_number}")
        except Exception as e:
            logger.warning(f"[voice-log] DNC upsert failed: {e}")

    # ── Boardroom Ledger: voice cost + booking revenue attribution ──
    try:
        from services.agent_ledger import record_cost, record_revenue
        if duration_seconds > 0:
            minutes = max(1, round(duration_seconds / 60.0))
            await record_cost(db, "envoy_ora", "voice_retell", minutes,
                              meta={"call_id": body.get("call_id"), "lead": lead_number})
        if booked:
            await record_revenue(db, "closer_ora", amount_usd=0,
                                 stage="voice_booking_potential",
                                 meta={"call_id": body.get("call_id"), "lead": lead_number})
    except Exception:
        pass

    # ── Trial-link auto-SMS (iter 289.7) ──
    # Send to anyone who didn't explicitly opt out; the SMS itself includes
    # STOP-reply support so recipients can still bail.
    sms_result = {"sent": False, "reason": "not attempted"}
    if not opted_out and lead_number:
        try:
            from services.trial_sms import send_trial_sms
            sms_result = await send_trial_sms(
                db,
                lead_number=lead_number,
                call_id=body.get("call_id") or "",
                booked=booked,
            )
        except Exception as e:
            logger.warning(f"[voice-log] trial-sms hook failed: {e}")

    return {
        "status": "ok",
        "booked": booked,
        "opted_out": opted_out,
        "dnc_added": opted_out and bool(lead_number),
        "trial_sms": sms_result,
    }


@router.get("/voice-log/stats")
async def voice_log_stats(request: Request, days: int = 7):
    """Founder-only: roll-up of voice_call_logs over N days."""
    _require_founder(request)
    db = _get_db()
    if db is None:
        return {"calls": 0, "minutes": 0, "booked": 0, "opted_out": 0}
    from datetime import timedelta
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    pipeline = [
        {"$match": {"received_at": {"$gte": since}}},
        {"$group": {
            "_id": None,
            "calls": {"$sum": 1},
            "minutes": {"$sum": "$duration_minutes"},
            "booked": {"$sum": {"$cond": ["$booked", 1, 0]}},
            "opted_out": {"$sum": {"$cond": ["$opted_out", 1, 0]}},
        }},
    ]
    rows = await db.voice_call_logs.aggregate(pipeline).to_list(length=1)
    if not rows:
        return {"days": days, "calls": 0, "minutes": 0, "booked": 0, "opted_out": 0}
    r = rows[0]
    return {
        "days": days,
        "calls": r["calls"],
        "minutes": round(r.get("minutes", 0) or 0, 2),
        "booked": r["booked"],
        "opted_out": r["opted_out"],
        "booking_rate_pct": round(r["booked"] / r["calls"] * 100, 1) if r["calls"] else 0,
    }


@router.post("/deploys/log")
async def log_deploy(request: Request, body: Optional[Dict[str, Any]] = None):
    """Founder-only: explicitly log a deploy event (CI / Vercel webhook target).

    Body (all optional):
      - trigger:       'manual' | 'ci' | 'webhook' | 'rollback'   (default: 'manual')
      - commit_sha:    overrides git rev-parse HEAD if provided
      - branch:        overrides current branch
      - commit_message
      - source:        free-form note (e.g. 'github-actions')
    """
    _require_founder(request)
    from services.deploy_logger import log_deploy_event
    extra = {}
    body = body or {}
    for k in ("commit_sha", "branch", "commit_message", "commit_author", "source"):
        v = body.get(k)
        if v is not None:
            extra[k] = v
    trigger = body.get("trigger", "manual")
    doc = await log_deploy_event(_get_db(), trigger=trigger, extra=extra)
    return {"success": doc is not None, "event": doc}


@router.get("/pulse")
async def pulse(request: Request, agents_window_min: int = 15, timeline_limit: int = 10):
    """Live rail data for the AdminShell sidebar.

    Returns:
      agents:   per-agent activity over last N minutes (status: live | idle | dormant)
      timeline: last N events across all founder-relevant streams
    """
    _require_founder(request)
    db = _get_db()
    if db is None:
        return {"agents": [], "timeline": [], "now": None}

    from datetime import datetime, timezone, timedelta
    from services.agent_ledger import AGENT_IDS

    now = datetime.now(timezone.utc)
    win = (now - timedelta(minutes=max(1, min(agents_window_min, 1440)))).isoformat()

    # ── per-agent pulse ──
    pipeline = [
        {"$match": {"kind": "cost", "timestamp": {"$gte": win}}},
        {"$group": {
            "_id": "$agent_id",
            "count": {"$sum": 1},
            "cost": {"$sum": "$cost_usd"},
            "last_ts": {"$max": "$timestamp"},
        }},
    ]
    seen = {}
    async for row in db.agent_ledger_entries.aggregate(pipeline):
        seen[row["_id"]] = {
            "count": row["count"],
            "cost_usd": round(row.get("cost", 0.0) or 0.0, 4),
            "last_ts": row.get("last_ts"),
        }

    agents_out = []
    known_ids = set(AGENT_IDS) | set(seen.keys())
    for aid in sorted(known_ids):
        s = seen.get(aid)
        if s and s["count"] > 0:
            status = "live"
        else:
            # check 24h activity for "idle" vs "dormant"
            since_24h = (now - timedelta(hours=24)).isoformat()
            recent = await db.agent_ledger_entries.find_one(
                {"kind": "cost", "agent_id": aid, "timestamp": {"$gte": since_24h}},
                {"_id": 0, "timestamp": 1},
            )
            status = "idle" if recent else "dormant"
        agents_out.append({
            "agent_id": aid,
            "status": status,
            "count": (s or {}).get("count", 0),
            "cost_usd": (s or {}).get("cost_usd", 0.0),
            "last_ts": (s or {}).get("last_ts"),
        })

    # ── founder timeline (mixed sources, latest N) ──
    timeline = []

    # 1) Recent ledger entries
    cursor = db.agent_ledger_entries.find(
        {}, {"_id": 0, "kind": 1, "agent_id": 1, "source": 1, "cost_usd": 1,
             "amount_usd": 1, "stage": 1, "timestamp": 1}
    ).sort("timestamp", -1).limit(timeline_limit)
    async for d in cursor:
        if d.get("kind") == "cost":
            msg = f"{d.get('agent_id')} · {d.get('source')} · ${d.get('cost_usd', 0):.4f}"
        else:
            msg = f"{d.get('agent_id')} · {d.get('stage', 'revenue')} · ${d.get('amount_usd', 0):.2f}"
        timeline.append({"type": "ledger", "kind": d.get("kind"), "agent_id": d.get("agent_id"),
                         "msg": msg, "ts": d.get("timestamp")})

    # 2) Sentinel auto-heals (best-effort — collection may not exist)
    try:
        async for d in db.autopilot_sentinel_log.find(
            {}, {"_id": 0, "action": 1, "phase": 1, "tenant_id": 1, "timestamp": 1}
        ).sort("timestamp", -1).limit(5):
            timeline.append({
                "type": "sentinel",
                "msg": f"sentinel · {d.get('action', 'heal')} · {d.get('phase', '')}",
                "ts": d.get("timestamp"),
            })
    except Exception:
        pass

    # 3) ORA commands (last few)
    try:
        async for d in db.ora_command_log.find(
            {}, {"_id": 0, "intent": 1, "user": 1, "raw": 1, "timestamp": 1}
        ).sort("timestamp", -1).limit(5):
            raw = (d.get("raw") or "")[:60]
            timeline.append({
                "type": "ora",
                "msg": f"ora · {d.get('intent', 'CHAT')} · {raw}",
                "ts": d.get("timestamp"),
            })
    except Exception:
        pass

    # 4) Deploy events (best-effort)
    try:
        async for d in db.deploy_events.find(
            {}, {"_id": 0, "trigger": 1, "branch": 1, "commit": 1, "repo": 1, "timestamp": 1}
        ).sort("timestamp", -1).limit(3):
            commit = d.get("commit") or ""
            timeline.append({
                "type": "deploy",
                "msg": f"deploy · {d.get('trigger', 'manual')} · {commit[:7]}",
                "ts": d.get("timestamp"),
                "meta": {
                    "commit_sha": commit,
                    "repo": d.get("repo") or os.environ.get("AUREM_GITHUB_REPO", "AUREMBeauty/AUREM-"),
                    "branch": d.get("branch", ""),
                },
            })
    except Exception:
        pass

    timeline.sort(key=lambda x: x.get("ts") or "", reverse=True)
    timeline = timeline[:timeline_limit]

    return {
        "now": now.isoformat(),
        "window_minutes": agents_window_min,
        "agents": agents_out,
        "timeline": timeline,
    }
