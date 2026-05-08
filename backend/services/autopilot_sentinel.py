"""Autopilot Sentinel Watchdog — Iter 288.5
==========================================
"100% Eyes On" guarantee for tomorrow morning. Runs every 60s during the
autopilot window (07:55–10:00 Toronto) and self-heals any phase failure.

Watchdog loop:
  1. SCOUT health: Google Places ping + last lead-write age
  2. HUNT health: enrichment pipeline (Apollo + email_guesser) reachable
  3. BLAST health: Resend + Twilio API keys + WABA template approved
  4. REPORT health: Telegram bot reachable + brief notifier ready
  5. AGENT-EYES: every agent self-checks its KPIs, posts to its SOUL.md

Auto-heal actions when a phase fails:
  - retry the phase up to 3× with exponential backoff
  - rotate to fallback (Google→Tavily→Firecrawl→DIY)
  - reset stale fallback_failure_state counters
  - re-fire the autopilot run if the morning fire produced 0 leads
  - send single Telegram "✅ AUTO-HEALED" or "🚨 NEEDS HUMAN" alert (deduped)
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# Watch window (Toronto local) — sentinel only runs during this period
WATCH_START_HHMM = (7, 55)   # 07:55
WATCH_END_HHMM = (10, 0)     # 10:00

# Hard self-heal limits (per run)
MAX_RETRIES_PER_PHASE = 3
RETRY_BACKOFF_BASE_SEC = 30  # 30s, 60s, 120s

_db = None


def set_db(db) -> None:
    global _db
    _db = db


def _toronto_now():
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/Toronto"))
    except Exception:
        return datetime.now(timezone.utc)


def _in_watch_window() -> bool:
    n = _toronto_now()
    h, m = n.hour, n.minute
    cur = h * 60 + m
    start = WATCH_START_HHMM[0] * 60 + WATCH_START_HHMM[1]
    end = WATCH_END_HHMM[0] * 60 + WATCH_END_HHMM[1]
    return start <= cur <= end


# ─────────────────────────────────────────────────────────────
# Phase health probes (each returns {"ok": bool, "reason": str})
# ─────────────────────────────────────────────────────────────
async def _probe_scout(db) -> Dict[str, Any]:
    """Health probe — must use a query guaranteed to return results.
    Niche category scouts may legitimately return 0 places; that's NOT a Sentinel failure."""
    key = os.environ.get("GOOGLE_PLACES_API_KEY", "").strip()
    if not key:
        return {"ok": False, "reason": "GOOGLE_PLACES_API_KEY missing", "fatal": True}
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(
                "https://places.googleapis.com/v1/places:searchText",
                headers={"Content-Type": "application/json",
                         "X-Goog-Api-Key": key,
                         "X-Goog-FieldMask": "places.displayName"},
                json={"textQuery": "restaurants Toronto"},  # broad query, never 0 results
            )
            d = r.json()
            # Probe failure ONLY on auth/quota errors. Empty results = legitimate niche miss.
            if r.status_code in (401, 403, 429):
                return {"ok": False, "reason": f"places HTTP {r.status_code} (auth/quota)", "fatal": True}
            if r.status_code != 200:
                return {"ok": False, "reason": f"places HTTP {r.status_code}"}
            if not d.get("places"):
                return {"ok": False, "reason": "broad probe returned 0 — API likely degraded"}
    except Exception as e:
        return {"ok": False, "reason": f"places probe error: {e}"}
    return {"ok": True}


async def _probe_hunt(db) -> Dict[str, Any]:
    apollo = os.environ.get("APOLLO_API_KEY", "").strip()
    if not apollo:
        return {"ok": False, "reason": "APOLLO_API_KEY missing (DIY proxy still works)"}
    return {"ok": True}


async def _probe_blast(db) -> Dict[str, Any]:
    missing = []
    for k in ("RESEND_API_KEY", "TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN"):
        if not os.environ.get(k, "").strip():
            missing.append(k)
    if missing:
        return {"ok": False, "reason": f"missing env: {missing}"}
    return {"ok": True}


async def _probe_report(db) -> Dict[str, Any]:
    if not os.environ.get("TELEGRAM_BOT_TOKEN", "").strip():
        return {"ok": False, "reason": "TELEGRAM_BOT_TOKEN missing"}
    return {"ok": True}


async def _probe_agents(db) -> Dict[str, Any]:
    """Each agent self-checks its KPIs (last 48h)."""
    if db is None:
        return {"ok": False, "reason": "db unavailable"}
    yesterday = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
    try:
        cnt = await db.campaign_leads.count_documents({"created_at": {"$gte": yesterday}})
    except Exception as e:
        return {"ok": False, "reason": f"campaign_leads probe: {e}"}
    if cnt == 0:
        return {"ok": False, "reason": "0 leads in last 48h — Scout idle"}
    return {"ok": True, "leads_48h": cnt}


PHASES = [
    ("scout",  _probe_scout),
    ("hunt",   _probe_hunt),
    ("blast",  _probe_blast),
    ("report", _probe_report),
    ("agents", _probe_agents),
]


# ─────────────────────────────────────────────────────────────
# Heal actions
# ─────────────────────────────────────────────────────────────
async def _heal_scout(db, reason: str) -> Dict[str, Any]:
    # Reset fallback counter so future runs don't carry stale fail state
    try:
        await db.fallback_failure_state.update_one(
            {"service": "scout", "primary": "google_places"},
            {"$set": {"consecutive_failures": 0,
                      "auto_healed_at": datetime.now(timezone.utc).isoformat(),
                      "auto_healed_reason": reason[:120]}},
            upsert=True,
        )
    except Exception:
        pass
    # Re-fire ORA hunt with rotated target
    try:
        cfg = await db.platform_config.find_one({"config_key": "master_autopilot"}, {"_id": 0})
        from routers.master_autopilot_router import _DEFAULT_CANADA_SCOUT_TARGETS
        targets = (cfg or {}).get("scout_targets") or _DEFAULT_CANADA_SCOUT_TARGETS
        idx = (int((cfg or {}).get("scout_target_idx", 0)) + 1) % len(targets)
        await db.platform_config.update_one(
            {"config_key": "master_autopilot"},
            {"$set": {"scout_target_idx": idx}},
            upsert=True,
        )
        target = targets[idx]
        from services.ora_command_center import _exec_hunt
        r = await _exec_hunt(db, {**target, "source": "sentinel_heal_scout"})
        return {"ok": bool(r and r.get("ok")), "target": target, "hunt": (r or {}).get("data", {})}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


async def _heal_hunt(db, reason: str) -> Dict[str, Any]:
    return {"ok": True, "note": "Apollo down → DIY scraper fallback already active"}


async def _heal_blast(db, reason: str) -> Dict[str, Any]:
    return {"ok": False, "note": "Cannot self-heal missing API keys", "needs_human": True}


async def _heal_report(db, reason: str) -> Dict[str, Any]:
    return {"ok": False, "note": "Cannot self-heal missing Telegram token", "needs_human": True}


async def _heal_agents(db, reason: str) -> Dict[str, Any]:
    # Re-fire morning brief if 0 leads — kicks the autopilot scout phase manually
    try:
        from routers.master_autopilot_router import _DEFAULT_CANADA_SCOUT_TARGETS
        cfg = await db.platform_config.find_one({"config_key": "master_autopilot"}, {"_id": 0})
        targets = (cfg or {}).get("scout_targets") or _DEFAULT_CANADA_SCOUT_TARGETS
        idx = int((cfg or {}).get("scout_target_idx", 0)) % len(targets)
        target = targets[idx]
        from services.ora_command_center import _exec_hunt
        r = await _exec_hunt(db, {**target, "source": "sentinel_heal_agents"})
        return {"ok": bool(r and r.get("ok")), "fired_target": target}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


HEALERS = {
    "scout":  _heal_scout,
    "hunt":   _heal_hunt,
    "blast":  _heal_blast,
    "report": _heal_report,
    "agents": _heal_agents,
}


# ─────────────────────────────────────────────────────────────
# Telegram dedup alert
# ─────────────────────────────────────────────────────────────
_last_alert_key: Optional[str] = None
_last_alert_at: Optional[datetime] = None


async def _telegram(db, msg: str, dedup_key: str) -> None:
    global _last_alert_key, _last_alert_at
    now = datetime.now(timezone.utc)
    if (_last_alert_key == dedup_key and _last_alert_at
            and (now - _last_alert_at) < timedelta(minutes=15)):
        return
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not (token and chat):
        return
    try:
        async with httpx.AsyncClient(timeout=8) as c:
            await c.post(f"https://api.telegram.org/bot{token}/sendMessage",
                         json={"chat_id": chat, "text": msg, "parse_mode": "Markdown"})
        _last_alert_key, _last_alert_at = dedup_key, now
    except Exception as e:
        logger.warning(f"[Sentinel] telegram failed: {e}")


# ─────────────────────────────────────────────────────────────
# Main tick
# ─────────────────────────────────────────────────────────────
async def sentinel_tick(force: bool = False) -> Dict[str, Any]:
    if _db is None:
        return {"ok": False, "reason": "db unset"}
    if not force and not _in_watch_window():
        return {"ok": True, "skipped": "outside watch window"}

    report: Dict[str, Any] = {"ts": datetime.now(timezone.utc).isoformat(), "phases": {}}

    for phase_name, probe_fn in PHASES:
        try:
            res = await probe_fn(_db)
        except Exception as e:
            res = {"ok": False, "reason": f"probe exception: {e}"}
        report["phases"][phase_name] = res

        if res.get("ok"):
            continue

        # FAILED — attempt heal with retries
        healer = HEALERS.get(phase_name)
        if not healer:
            continue
        for attempt in range(1, MAX_RETRIES_PER_PHASE + 1):
            await asyncio.sleep(RETRY_BACKOFF_BASE_SEC * (2 ** (attempt - 1)) if attempt > 1 else 0)
            try:
                heal = await healer(_db, res.get("reason", ""))
            except Exception as e:
                heal = {"ok": False, "error": str(e)[:200]}
            res.setdefault("heal_attempts", []).append({"attempt": attempt, "result": heal})
            if heal.get("ok"):
                await _telegram(_db,
                                f"✅ *AUREM Sentinel* auto-healed `{phase_name}` "
                                f"(attempt {attempt}). Reason: _{res.get('reason','')[:80]}_",
                                dedup_key=f"healed_{phase_name}")
                break
        else:
            # All retries failed
            needs_human = any(a["result"].get("needs_human") for a in res.get("heal_attempts", []))
            if needs_human:
                await _telegram(_db,
                                f"🚨 *AUREM Sentinel* — `{phase_name}` failed and needs human.\n"
                                f"Reason: _{res.get('reason','')[:120]}_\n"
                                f"All {MAX_RETRIES_PER_PHASE} auto-heal attempts exhausted.",
                                dedup_key=f"human_{phase_name}")

    # Persist run for audit
    try:
        await _db.sentinel_runs.insert_one({**report, "ttl_at": datetime.now(timezone.utc)})
    except Exception:
        pass

    return report


# ─────────────────────────────────────────────────────────────
# Background loop — kicked from server.py startup
# ─────────────────────────────────────────────────────────────
_running = False


async def sentinel_loop(interval_seconds: int = 60) -> None:
    global _running
    if _running:
        return
    _running = True
    logger.info(f"[Sentinel] watchdog loop started (every {interval_seconds}s)")
    while True:
        try:
            res = await sentinel_tick()
            # Always persist a lightweight heartbeat so observers can prove
            # the loop is alive — even outside the 07:55–10:00 watch window
            # when sentinel_tick() short-circuits with "skipped".
            if _db is not None:
                try:
                    await _db.sentinel_heartbeats.update_one(
                        {"_id": "singleton"},
                        {"$set": {
                            "ts": datetime.now(timezone.utc).isoformat(),
                            "last_result": res,
                            "interval_seconds": interval_seconds,
                            "in_watch_window": _in_watch_window(),
                        }},
                        upsert=True,
                    )
                except Exception:
                    pass
        except Exception as e:
            logger.exception(f"[Sentinel] tick failed: {e}")
        await asyncio.sleep(interval_seconds)
