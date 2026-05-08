"""Sentinel Watchdog Router (iter 288.5)
- POST /api/sentinel/fire        — manually trigger one tick (founder)
- GET  /api/sentinel/status      — last sentinel_run + watch-window state
- POST /api/sentinel/all-eyes-on — arm all 6 agents for tomorrow morning
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Any, Dict

import jwt as pyjwt
from fastapi import APIRouter, HTTPException, Request

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/sentinel", tags=["Autopilot Sentinel"])

_db = None


def set_db(db):
    global _db
    _db = db


def _require_founder(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Missing token")
    try:
        from middleware.tenant_guard import JWT_SECRET, JWT_ALGORITHM
        p = pyjwt.decode(auth.split(" ", 1)[1], JWT_SECRET,
                         algorithms=[JWT_ALGORITHM], options={"verify_exp": False})
    except Exception as e:
        raise HTTPException(401, f"Invalid token: {e}")
    if not (p.get("is_admin") or p.get("is_super_admin")):
        raise HTTPException(403, "Founder only")
    return p


@router.post("/fire")
async def fire(request: Request, force: bool = True):
    _require_founder(request)
    from services.autopilot_sentinel import sentinel_tick
    return await sentinel_tick(force=force)


@router.get("/status")
async def status(request: Request):
    _require_founder(request)
    from services.autopilot_sentinel import _in_watch_window, WATCH_START_HHMM, WATCH_END_HHMM
    if _db is None:
        return {"ok": False, "reason": "db unavailable"}
    last = await _db.sentinel_runs.find_one({}, {"_id": 0}, sort=[("ts", -1)])
    return {
        "ok": True,
        "in_watch_window": _in_watch_window(),
        "watch_start": f"{WATCH_START_HHMM[0]:02d}:{WATCH_START_HHMM[1]:02d}",
        "watch_end": f"{WATCH_END_HHMM[0]:02d}:{WATCH_END_HHMM[1]:02d}",
        "last_run": last,
    }


@router.post("/all-eyes-on")
async def all_eyes_on(request: Request):
    """Arm all 6 agents — sets a 'guard mandate' on their SOUL.md and
    flips agent_state.guard_mode=True so their next-cycle reflection
    explicitly checks pipeline health."""
    founder = _require_founder(request)
    if _db is None:
        raise HTTPException(503, "db unavailable")
    now = datetime.now(timezone.utc).isoformat()
    agents = ["scout_ora", "hunter_ora", "envoy_ora",
              "followup_ora", "closer_ora", "referral_ora"]
    res: Dict[str, Any] = {}
    for aid in agents:
        await _db.agent_state.update_one(
            {"agent_id": aid},
            {"$set": {"guard_mode": True, "guard_armed_at": now,
                      "guard_armed_by": founder.get("email", "founder"),
                      "paused": False}},
            upsert=True,
        )
        # Append guard mandate line to the agent's soul
        try:
            from services.agent_soul import _path_for, _persona
            p = _path_for(aid)
            persona = _persona(aid)
            mandate = (f"\n### {now[:19].replace('T', ' ')} UTC · 🛡️ GUARD MANDATE\n"
                       f"- Founder activated 100% Eyes-On mode for tomorrow's autopilot.\n"
                       f"- I, {persona['name']}, will self-check my pipeline every 60s during 07:55–10:00 Toronto.\n"
                       f"- Any failure → I auto-retry 3× → escalate to Sentinel watchdog.\n\n")
            existing = p.read_text(encoding="utf-8") if p.exists() else ""
            p.write_text(existing + mandate, encoding="utf-8")
            res[aid] = "armed"
        except Exception as e:
            res[aid] = f"armed (soul write failed: {e})"
    return {"ok": True, "agents": res, "armed_at": now,
            "guarantee": "Sentinel watchdog will run every 60s during 07:55–10:00 Toronto. Any phase failure auto-retries 3× then escalates to Telegram."}
