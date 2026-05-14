"""
Pillars Health — fast 4-pillar status endpoint for AdminShell PillarGate.

Reads:  /api/pillars/health  → { P1, P2, P3, P4 }
Writes: POST /api/pillars/override  → set/clear manual override (testing + repair)

Sources of truth:
- Existing pillars_map data (collections + worker heartbeats)
- pillar_overrides collection (manual founder/auto-repair overrides)
- Cached for 5s to avoid hammering DB every poll

Mapping (per founder brief):
  P1 INFRASTRUCTURE  ← p1_sales (legacy) + Mongo + Redis ping
  P2 INTELLIGENCE    ← LLM keys + ORA brain (heuristic: emergent llm key + recent agent activity)
  P3 OUTREACH        ← p3_monitor + Twilio/Resend keys + voice_call_logs writers
  P4 REVENUE         ← p2_billing (Stripe + subscriptions)

Status verdicts: green | yellow | red | loading
"""
from __future__ import annotations

import os
import time
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/pillars", tags=["Pillars Health"])

_db = None
_cache = {"ts": 0.0, "data": None}
_CACHE_TTL_SEC = 5


def set_db(db):
    global _db
    _db = db


def _get_db():
    global _db
    if _db is None:
        try:
            import server
            _db = getattr(server, "db", None)
        except Exception:
            pass
    return _db


def _verify_admin(authorization: Optional[str]) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Admin authentication required")
    import jwt
    try:
        secret = (os.environ.get("JWT_SECRET") or (_ for _ in ()).throw(__import__("fastapi").HTTPException(status_code=500, detail="JWT not configured")))
        payload = jwt.decode(authorization.split(" ", 1)[1], secret, algorithms=["HS256"])
        if payload.get("is_admin") or payload.get("role") == "admin" or payload.get("email"):
            return payload
        raise HTTPException(status_code=403, detail="Admin only")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


# ─── Pillar checks ──────────────────────────────────────────────────────────
# iter 282w — P1 is the foundation pillar (Mongo liveness). Previously a
# single 2s ping decided the verdict, so any transient Atlas latency spike
# or brief connection hiccup flipped P1 to red and the admin console
# reported "Infrastructure degraded". There was ALSO no real auto-repair —
# just a sentinel_alert insert. Fix: retry the ping 3× with exponential
# backoff + treat intermittent failures as yellow (not red), and attempt
# a motor-level reconnect before declaring hard red. Green response is
# cached 30s on success so a single slow ping can't flap the dot.
#
# iter 322 — P1 anti-flap hardening (user feedback: "system shows offline
# every few mins"). Atlas M0 free-tier shared-CPU bursts spike pings to
# 3-4s during cold cache, causing P1 to flap red↔green every 5-10 min.
#   • Background pre-warm pinger every 10s keeps the motor pool hot →
#     hot pings consistently <100ms even on M0
#   • Sticky-green window extended 30s → 90s (covers the typical M0
#     burst-credit refill cycle of ~60s)
#   • RED only after 3 CONSECUTIVE bad cycles (true outage gate); single
#     or double bad cycles surface as YELLOW so the system stays "live"
#     with a degraded label rather than going fully offline.

_P1_LAST_GREEN_TS = 0.0
_P1_GREEN_STICKY_SEC = 90.0  # iter 322: was 30s — too tight for M0 bursts
_P1_CONSECUTIVE_FAILS = 0
_P1_FAIL_THRESHOLD_FOR_RED = 3  # iter 322: only RED after 3 bad cycles
_P1_PREWARMER_STARTED = False


async def _p1_prewarm_loop(db) -> None:
    """Background tick — pings Mongo every 10s to keep the motor pool hot.
    Never raises. Updates _P1_LAST_GREEN_TS on success so the public health
    endpoint can short-circuit to green when warm pings are healthy."""
    global _P1_LAST_GREEN_TS, _P1_CONSECUTIVE_FAILS
    while True:
        try:
            ok = await _p1_single_ping(db, timeout=2.0)
            if ok:
                _P1_LAST_GREEN_TS = time.time()
                _P1_CONSECUTIVE_FAILS = 0
        except Exception:
            pass
        await asyncio.sleep(10)


def start_p1_prewarmer(db) -> bool:
    """Idempotent — start the background ping warmer once at app startup."""
    global _P1_PREWARMER_STARTED
    if _P1_PREWARMER_STARTED:
        return False
    try:
        asyncio.create_task(_p1_prewarm_loop(db))
        _P1_PREWARMER_STARTED = True
        logger.info("[pillar-p1] pre-warm loop started (10s tick)")
        return True
    except RuntimeError:
        # No running loop yet — safe to skip; will start on first health hit.
        return False


async def _p1_single_ping(db, timeout: float) -> bool:
    try:
        await asyncio.wait_for(db.command("ping"), timeout=timeout)
        return True
    except Exception as e:
        logger.debug(f"[pillar-p1] ping failed (timeout={timeout}s): {e}")
        return False


async def _check_p1_infrastructure(db) -> str:
    """Mongo reachable with graceful retry + sticky-green + yellow-on-transient.

    Green  : warm-pinger green within sticky window OR any of 3 retries succeeds.
    Yellow : warm-pinger had recent green within sticky window (transient blip).
    Red    : 3 consecutive bad cycles AND no green seen within sticky window.
    """
    global _P1_LAST_GREEN_TS, _P1_CONSECUTIVE_FAILS
    now_ts = time.time()

    # iter 322 — sticky-green short-circuit. If the background warmer
    # observed a healthy ping within the sticky window, trust it. Avoids
    # racing N concurrent pollers all hitting Atlas at once.
    if (now_ts - _P1_LAST_GREEN_TS) < _P1_GREEN_STICKY_SEC:
        _P1_CONSECUTIVE_FAILS = 0
        return "green"

    # First attempt — generous 4s timeout (Atlas cold-cache spikes can hit 3s).
    if await _p1_single_ping(db, timeout=4.0):
        _P1_LAST_GREEN_TS = now_ts
        _P1_CONSECUTIVE_FAILS = 0
        return "green"

    # Second attempt — tighter 3s.
    await asyncio.sleep(0.2)
    if await _p1_single_ping(db, timeout=3.0):
        _P1_LAST_GREEN_TS = now_ts
        _P1_CONSECUTIVE_FAILS = 0
        return "green"

    # Third attempt — final 2.5s; if this fails, try motor-level reconnect.
    await asyncio.sleep(0.3)
    if await _p1_single_ping(db, timeout=2.5):
        _P1_LAST_GREEN_TS = now_ts
        _P1_CONSECUTIVE_FAILS = 0
        return "green"

    # Auto-repair attempt: poke the motor client to force a topology refresh.
    # Best-effort — motor uses a pooled async client; calling .list_database_names()
    # with a fresh timeout will trigger server_selection + reconnection.
    try:
        client = getattr(db, "client", None)
        if client is not None:
            await asyncio.wait_for(
                client.list_database_names(), timeout=4.0
            )
            _P1_LAST_GREEN_TS = now_ts
            _P1_CONSECUTIVE_FAILS = 0
            logger.info("[pillar-p1] auto-repair via topology refresh succeeded")
            return "green"
    except Exception as e:
        logger.warning(f"[pillar-p1] auto-repair reconnect failed: {e}")

    # Failure path — increment consecutive-fail counter. Only declare RED
    # after N consecutive cycles fail. Single/double blips → YELLOW so the
    # system stays "live" with a degraded label rather than offline.
    _P1_CONSECUTIVE_FAILS += 1

    # iter 322 — autonomous A2A → Council → ORA escalation per fail cycle:
    #   1st fail (yellow)  → DIAGNOSE   (Claude root-cause + suggested fix)
    #   2nd fail (yellow)  → AUTO-FIX   (motor refresh + breaker reset + cache)
    #   3rd fail (red)     → DR SYNC    (DR mirror snapshot + outage broadcast)
    # Fire-and-forget; never blocks the health endpoint. Per-tier 60s rate
    # limit prevents cascading task creation on a 10s polling cycle.
    try:
        from services.pillar_escalation import schedule_escalation
        schedule_escalation(db, "P1", _P1_CONSECUTIVE_FAILS)
    except Exception as e:
        logger.debug(f"[pillar-p1] escalation dispatch skipped: {e}")

    if _P1_CONSECUTIVE_FAILS >= _P1_FAIL_THRESHOLD_FOR_RED:
        return "red"
    return "yellow"


# iter 322 — generic per-pillar consecutive-fail tracker for P2/P3/P4. Same
# anti-flap ladder as P1: yellow→yellow→red, sticky-green window, escalation
# dispatch on every increment. Liveness signal for P2/P3/P4 is "env present
# AND no relevant breaker is OPEN" — purely env-var checks would never flap,
# but breaker state DOES flap during real upstream throttling, which is the
# scenario user wants the autonomous loop to handle.
_PN_LAST_GREEN_TS: dict = {"P2": 0.0, "P3": 0.0, "P4": 0.0}
_PN_CONSECUTIVE_FAILS: dict = {"P2": 0, "P3": 0, "P4": 0}
_PN_GREEN_STICKY_SEC = 90.0
_PN_FAIL_THRESHOLD_FOR_RED = 3


def _pillar_breakers_open(pillar: str) -> list[str]:
    """Return list of OPEN breaker names relevant to a pillar. Empty = healthy."""
    try:
        from services.breakers import breaker_status
        statuses = breaker_status()
    except Exception:
        return []
    rel = {
        "P2": ("openrouter", "groq", "anthropic", "openai"),
        "P3": ("twilio", "resend"),
        "P4": ("stripe",),
    }.get(pillar, ())
    open_names: list[str] = []
    for b_name, b_state in statuses.items():
        if isinstance(b_state, dict) and b_state.get("state") == "open":
            if any(r in b_name.lower() for r in rel):
                open_names.append(b_name)
    return open_names


def _ladder_resolve(pillar: str, healthy: bool, db) -> str:
    """Apply the yellow→yellow→red ladder + dispatch escalation."""
    now_ts = time.time()
    if healthy:
        _PN_LAST_GREEN_TS[pillar] = now_ts
        _PN_CONSECUTIVE_FAILS[pillar] = 0
        return "green"
    # Sticky-green: brief blip while we were recently healthy → degraded but live
    if (now_ts - _PN_LAST_GREEN_TS.get(pillar, 0.0)) < _PN_GREEN_STICKY_SEC:
        # Still record the fail cycle so we can escalate even from sticky window
        _PN_CONSECUTIVE_FAILS[pillar] += 1
    else:
        _PN_CONSECUTIVE_FAILS[pillar] += 1

    consec = _PN_CONSECUTIVE_FAILS[pillar]
    try:
        from services.pillar_escalation import schedule_escalation
        schedule_escalation(db, pillar, consec)
    except Exception as e:
        logger.debug(f"[pillar-{pillar}] escalation dispatch skipped: {e}")

    if consec >= _PN_FAIL_THRESHOLD_FOR_RED:
        return "red"
    return "yellow"


async def _check_p2_intelligence(db) -> str:
    """Healthy when an LLM key is configured AND no provider breaker is OPEN."""
    has_key = bool(
        os.environ.get("EMERGENT_LLM_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or os.environ.get("ANTHROPIC_API_KEY")
        or os.environ.get("GROQ_API_KEY")
    )
    open_breakers = _pillar_breakers_open("P2")
    healthy = has_key and not open_breakers
    return _ladder_resolve("P2", healthy, db)


async def _check_p3_outreach(db) -> str:
    """Healthy when at least one outreach channel is configured AND its breaker
    is not OPEN. Both channels throttled → degraded → escalates."""
    has_resend = bool(os.environ.get("RESEND_API_KEY"))
    has_twilio = bool(
        os.environ.get("TWILIO_ACCOUNT_SID") and os.environ.get("TWILIO_AUTH_TOKEN")
    )
    if not (has_resend or has_twilio):
        return _ladder_resolve("P3", False, db)
    open_breakers = _pillar_breakers_open("P3")
    # If BOTH channels are throttled (or the only available one is) → unhealthy
    available_channels = sum([has_resend, has_twilio])
    throttled_channels = sum(
        1 for b in open_breakers
        if any(c in b.lower() for c in ("twilio", "resend"))
    )
    healthy = throttled_channels < available_channels  # at least one path live
    return _ladder_resolve("P3", healthy, db)


async def _check_p4_revenue(db) -> str:
    """Healthy when Stripe key is configured AND its breaker is not OPEN."""
    has_stripe = bool(
        os.environ.get("STRIPE_API_KEY") or os.environ.get("STRIPE_SECRET_KEY")
    )
    open_breakers = _pillar_breakers_open("P4")
    healthy = has_stripe and not open_breakers
    return _ladder_resolve("P4", healthy, db)


async def _gather_status(db) -> dict:
    """Return raw pillar statuses (pre-override)."""
    p1 = await _check_p1_infrastructure(db)
    p2 = await _check_p2_intelligence(db)
    p3 = await _check_p3_outreach(db)
    p4 = await _check_p4_revenue(db)
    return {"P1": p1, "P2": p2, "P3": p3, "P4": p4}


async def _apply_overrides(db, statuses: dict) -> dict:
    """Apply pillar_overrides — manual founder/auto-repair overrides."""
    try:
        async for ov in db.pillar_overrides.find({"active": True}, {"_id": 0}):
            pkey = ov.get("pillar")
            status = ov.get("status")
            if pkey in statuses and status in ("green", "yellow", "red"):
                statuses[pkey] = status
    except Exception:
        pass
    return statuses


# ─── Endpoints ──────────────────────────────────────────────────────────────

@router.get("/health")
async def pillars_health(authorization: Optional[str] = Header(None)):
    """
    Fast 4-pillar verdict. Cached 5s. Used by AdminShell every 10s.
    Returns: { P1, P2, P3, P4, worst, ts, source }
    """
    _verify_admin(authorization)
    db = _get_db()
    if db is None:
        return {
            "P1": "red", "P2": "red", "P3": "red", "P4": "red",
            "worst": "red", "ts": datetime.now(timezone.utc).isoformat(),
            "source": "no-db",
        }

    now = time.time()
    if _cache["data"] and (now - _cache["ts"]) < _CACHE_TTL_SEC:
        return _cache["data"]

    statuses = await _gather_status(db)
    statuses = await _apply_overrides(db, statuses)

    order = {"green": 0, "yellow": 1, "red": 2}
    worst = max(statuses.values(), key=lambda s: order.get(s, 0))

    out = {
        **statuses,
        "worst": worst,
        "ts": datetime.now(timezone.utc).isoformat(),
        "source": "live",
    }
    _cache["ts"] = now
    _cache["data"] = out

    # If any pillar red → fire auto-repair (iter 282w — now actually repairs P1).
    if "red" in statuses.values():
        red_pillars = [k for k, v in statuses.items() if v == "red"]
        try:
            await db.sentinel_alerts.insert_one({
                "kind": "pillar_red",
                "pillars": red_pillars,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
        except Exception:
            pass
        # Auto-repair P1: force a topology refresh + log the attempt.
        if "P1" in red_pillars:
            try:
                client = getattr(db, "client", None)
                if client is not None:
                    asyncio.create_task(
                        _p1_background_repair(db, red_pillars)
                    )
            except Exception:
                pass

    return out


async def _p1_background_repair(db, red_pillars: list) -> None:
    """Fire-and-forget P1 infra repair. Retries ping after a short delay and
    records the outcome in `repair_requests` so the admin console auto-repair
    widget can surface the activity."""
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        await db.repair_requests.insert_one({
            "pillar": "P1",
            "kind": "mongo_topology_refresh",
            "ts": now_iso,
            "source": "pillar_auto_repair",
            "status": "running",
            "red_pillars": red_pillars,
        })
    except Exception:
        pass

    repaired = False
    try:
        client = getattr(db, "client", None)
        if client is not None:
            # Forces server_selection + reopens dead sockets in the motor pool.
            await asyncio.wait_for(client.list_database_names(), timeout=6.0)
            await asyncio.wait_for(db.command("ping"), timeout=3.0)
            repaired = True
    except Exception as e:
        logger.warning(f"[pillar-p1] background repair failed: {e}")

    # Invalidate cache so the next /api/pillars/health call re-checks live.
    _cache["ts"] = 0.0
    try:
        await db.repair_requests.insert_one({
            "pillar": "P1",
            "kind": "mongo_topology_refresh_result",
            "ts": datetime.now(timezone.utc).isoformat(),
            "source": "pillar_auto_repair",
            "status": "repaired" if repaired else "failed",
        })
    except Exception:
        pass
    if repaired:
        global _P1_LAST_GREEN_TS
        _P1_LAST_GREEN_TS = time.time()
        logger.info("[pillar-p1] background auto-repair succeeded — cache invalidated")


class PillarOverride(BaseModel):
    pillar: str   # P1/P2/P3/P4
    status: str   # green/yellow/red
    reason: Optional[str] = None
    duration_minutes: Optional[int] = None  # auto-expire (None = until cleared)


@router.post("/override")
async def set_override(body: PillarOverride, authorization: Optional[str] = Header(None)):
    """Set a manual override for a pillar (testing + auto-repair)."""
    user = _verify_admin(authorization)
    db = _get_db()
    if db is None:
        raise HTTPException(503, "DB not available")
    if body.pillar not in ("P1", "P2", "P3", "P4"):
        raise HTTPException(400, "pillar must be P1|P2|P3|P4")
    if body.status not in ("green", "yellow", "red"):
        raise HTTPException(400, "status must be green|yellow|red")

    from datetime import timedelta
    now = datetime.now(timezone.utc)
    expires = (now + timedelta(minutes=body.duration_minutes)).isoformat() if body.duration_minutes else None
    doc = {
        "pillar": body.pillar,
        "status": body.status,
        "reason": body.reason or "manual",
        "active": True,
        "set_by": user.get("email", "unknown"),
        "set_at": now.isoformat(),
        "expires_at": expires,
    }
    # Deactivate prior, insert new
    await db.pillar_overrides.update_many({"pillar": body.pillar, "active": True}, {"$set": {"active": False}})
    await db.pillar_overrides.insert_one(doc)
    _cache["ts"] = 0.0  # invalidate cache
    return {"ok": True, "override": {**doc, "_id": None}}


@router.delete("/override/{pillar}")
async def clear_override(pillar: str, authorization: Optional[str] = Header(None)):
    _verify_admin(authorization)
    db = _get_db()
    if db is None:
        raise HTTPException(503, "DB not available")
    res = await db.pillar_overrides.update_many(
        {"pillar": pillar, "active": True}, {"$set": {"active": False}}
    )
    _cache["ts"] = 0.0
    return {"ok": True, "cleared": int(res.modified_count)}


@router.post("/repair/trigger")
async def trigger_repair(body: dict, authorization: Optional[str] = Header(None)):
    """Stub: log a repair request. Real auto-repair runs via existing self_repair_loop."""
    _verify_admin(authorization)
    db = _get_db()
    if db is not None:
        await db.repair_requests.insert_one({
            "pillar": body.get("pillar"),
            "ts": datetime.now(timezone.utc).isoformat(),
            "source": "pillar_gate",
        })
    return {"ok": True, "queued": True}
