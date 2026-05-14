"""
ora_autonomous_ops.py — Self-healing background scheduler (iter 322g)
═══════════════════════════════════════════════════════════════════════
User mandate: "Autonomous loop main daal — daily 2-4 times — ORA khud kare,
manual nahi karna. Watchdog auto-fix bhi karo."

Two loops in this file:

1. **ollama_warmer_autonomous_loop()** — runs every 6 hours (4x/day).
   Sends 1 small prompt via daemon to keep qwen2.5:7b-instruct hot.
   Skips silently if daemon offline.

2. **watchdog_autofix_loop()** — runs every 90s. Polls
   `ora_campaign_health._id='global'`. If `zero_sent_streak >= 3`,
   runs the channel-gating re-seed (same logic as our manual fix:
   detect quality leads + seed gating + purge junk). Logs every action
   to `ora_autonomous_log` so the founder can audit.

Both are best-effort. They never raise to the caller — they wait on
exponential backoff if MongoDB drops. Designed to run unattended for
days.
"""
from __future__ import annotations

import asyncio
import json as _json
import logging
import os
import shlex
import time
from datetime import datetime, timezone, timedelta

logger = logging.getLogger("ora_autonomous_ops")

_db = None

# ── Warmer config ────────────────────────────────────────────────────
WARM_INTERVAL_S    = 6 * 3600         # every 6h  → 4 warmups per day
WARM_FIRST_DELAY_S = 90               # initial delay so backend stabilises

# ── Watchdog auto-fix config ─────────────────────────────────────────
AUTOFIX_INTERVAL_S          = 90      # check campaign health every 90s
AUTOFIX_MIN_STREAK_TO_FIRE  = 3       # don't fire on transient blips
AUTOFIX_COOLDOWN_S          = 600     # don't refire same playbook for 10min

JUNK_DOMAINS = (
    "wikipedia.org", "reddit.com", "yelp.com", "autozone.com",
    "findbusinesses4sale.com", "bizbuysell.com", "walmart.com",
    "amazon.com", "homedepot.com", "lowes.com", "costco.com",
    "zenrows.com",
)
JUNK_NAME_PATTERNS = (
    "wikipedia", "reddit", "findbusinesses", "bizbuysell",
    "businesses for sale", "yelp.com/search",
)


def set_db(database) -> None:
    global _db
    _db = database


async def _log_action(playbook: str, summary: str, **extras) -> None:
    """Append to ora_autonomous_log for founder audit."""
    if _db is None:
        return
    try:
        await _db.ora_autonomous_log.insert_one({
            "playbook": playbook,
            "summary": summary,
            "ts": datetime.now(timezone.utc).isoformat(),
            **extras,
        })
    except Exception as e:
        logger.warning(f"[autonomous] log insert failed: {e}")


# ── 1. Ollama warmer (autonomous) ────────────────────────────────────
async def _warm_ollama_once() -> dict:
    """Fire a tiny chat at qwen2.5:7b-instruct via Legion daemon. Returns
    {ok, elapsed_ms, error?}.
    """
    try:
        from services.legion_tool import legion_exec
    except Exception as e:
        return {"ok": False, "error": f"import: {e}"}

    # Skip if daemon is dead.
    if _db is not None:
        # Bug-fix: bound the DB poll. find_one without an explicit timeout
        # can hang indefinitely if the Mongo driver loses its primary
        # mid-tick, which would jam this loop for the full 6h interval.
        try:
            s = await asyncio.wait_for(
                _db.legion_daemon_status.find_one(
                    {"_id": "global"}, {"_id": 0, "last_poll_ts": 1}
                ),
                timeout=5.0,
            )
        except asyncio.TimeoutError:
            return {"ok": False, "error": "db query timeout"}
        except Exception as e:
            return {"ok": False, "error": f"db query: {e}"}
        last = float((s or {}).get("last_poll_ts") or 0)
        if not last or (time.time() - last) > 120:
            return {"ok": False, "error": "daemon offline"}

    model = os.environ.get("LEGION_OLLAMA_MODEL", "qwen2.5:7b-instruct")
    url = os.environ.get("LEGION_OLLAMA_URL", "http://localhost:11434")
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "hi"}],
        "stream": False,
        "keep_alive": "60m",
        "options": {"num_predict": 3, "temperature": 0.0},
    }
    body = _json.dumps(payload)
    cmd = (
        f"curl -sS --max-time 90 "
        f"-H 'Content-Type: application/json' "
        f"-d {shlex.quote(body)} "
        f"{url.rstrip('/')}/api/chat | head -c 400"
    )
    started = time.time()
    result = await legion_exec(cmd=cmd, cwd="/tmp", timeout_s=100, risk_hint="low", wait_max_s=110)
    elapsed_ms = int((time.time() - started) * 1000)
    return {
        "ok": bool(result.get("ok")) and result.get("exit_code") == 0,
        "elapsed_ms": elapsed_ms,
        "error": result.get("error"),
        "stderr": (result.get("stderr") or "")[:120],
    }


async def ollama_warmer_autonomous_loop() -> None:
    # iter 322g+ prod-guard: skip in production (no laptop reach via daemon).
    try:
        from services.prod_guard import is_production_pod
        if is_production_pod():
            print("[autonomous-warmer] skipped — production pod (no daemon)", flush=True)
            return
    except Exception:
        pass

    print(f"[autonomous-warmer] alive — first warm in {WARM_FIRST_DELAY_S}s, "
          f"then every {WARM_INTERVAL_S/3600:.1f}h", flush=True)
    await asyncio.sleep(WARM_FIRST_DELAY_S)
    while True:
        try:
            res = await _warm_ollama_once()
            if res["ok"]:
                await _log_action(
                    "ollama_warm", f"OK in {res['elapsed_ms']}ms",
                    elapsed_ms=res["elapsed_ms"],
                )
                logger.info(f"[autonomous-warmer] OK in {res['elapsed_ms']}ms")
            else:
                logger.info(f"[autonomous-warmer] skipped: {res.get('error')}")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"[autonomous-warmer] loop err: {e}", exc_info=True)
        await asyncio.sleep(WARM_INTERVAL_S)


# ── 2. Watchdog auto-fix executor ────────────────────────────────────
_last_fire = {}   # playbook → epoch seconds, prevents flap


def _can_fire(playbook: str) -> bool:
    last = _last_fire.get(playbook, 0)
    if time.time() - last < AUTOFIX_COOLDOWN_S:
        return False
    _last_fire[playbook] = time.time()
    return True


async def _autofix_channel_gating() -> dict:
    """Re-seed channel_gating from raw lead email/phone for unsent leads
    AND purge junk domains. Same logic as our manual one-off but runs
    continuously now.
    """
    if _db is None:
        return {"ok": False, "error": "no db"}
    purged = 0
    fixed = 0
    skipped = 0
    cursor = _db.campaign_leads.find(
        {"last_blast_at": {"$exists": False},
         "status": {"$nin": ["signed_up", "not_interested", "unsubscribed"]}},
        {"_id": 0, "lead_id": 1, "business_name": 1, "email": 1, "phone": 1, "verification": 1},
    )
    async for lead in cursor:
        name = (lead.get("business_name") or "").lower()
        email = (lead.get("email") or "").lower()
        phone = (lead.get("phone") or "").strip()
        # Junk?
        if (any(d in email for d in JUNK_DOMAINS)
                or any(p in name for p in JUNK_NAME_PATTERNS)):
            await _db.campaign_leads.update_one(
                {"lead_id": lead["lead_id"]},
                {"$set": {
                    "status": "not_interested",
                    "noise_filtered_at": datetime.now(timezone.utc).isoformat(),
                    "noise_reason": "autonomous-autofix-junk-purge",
                }},
            )
            purged += 1
            continue
        # Need contact + missing gating?
        v = lead.get("verification") or {}
        cg = v.get("channel_gating") or {}
        if any(cg.values()):
            skipped += 1
            continue
        if not (email or phone):
            skipped += 1
            continue
        v["channel_gating"] = {
            "email":    bool(email and "@" in email),
            "call":     bool(phone),
            "sms":      bool(phone),
            "whatsapp": bool(phone),
        }
        v["source"] = "autonomous-autofix-322g"
        await _db.campaign_leads.update_one(
            {"lead_id": lead["lead_id"]},
            {"$set": {"verification": v}},
        )
        fixed += 1
    return {"ok": True, "purged": purged, "fixed": fixed, "skipped": skipped}


async def _autofix_restart_blast() -> dict:
    """Force-trigger one auto-blast cycle so the engine re-runs immediately
    instead of waiting for its 2-min sleep."""
    try:
        from services import auto_blast_engine
        auto_blast_engine.set_db(_db)
        result = await asyncio.wait_for(
            auto_blast_engine.run_auto_blast_cycle(force=True), timeout=90
        )
        return {"ok": True, "processed": result.get("total_processed"),
                "sent": result.get("total_sent")}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


async def watchdog_autofix_loop() -> None:
    # iter 322g+ — watchdog autofix is 100% DB-only (re-seed channel_gating,
    # restart blast cycle). NO Legion calls. So it MUST run in production too
    # — that's exactly where campaigns serve real revenue 24/7. Earlier we
    # mistakenly gated it behind prod_guard; that left prod self-healing dead.
    print(f"[autonomous-autofix] alive — polling every {AUTOFIX_INTERVAL_S}s "
          f"(pure DB, runs in both preview + prod)", flush=True)
    await asyncio.sleep(40)
    _err_backoff = AUTOFIX_INTERVAL_S
    while True:
        try:
            # Bug-fix: guard against `_db` not being wired yet during a
            # cold pod start. Previously this raised AttributeError on
            # the very first tick and killed the whole loop until
            # pillar_orchestrator restarted it.
            if _db is None:
                await asyncio.sleep(AUTOFIX_INTERVAL_S)
                continue

            h = await _db.ora_campaign_health.find_one({"_id": "global"}, {"_id": 0}) or {}
            tripped = h.get("tripped") or []
            streak = int(h.get("zero_sent_streak") or 0)
            veto_rate = float(h.get("veto_rate_1h") or 0)

            # ── Playbook A: zero_sent_streak → re-seed gating + restart blast ──
            if "zero_sent_streak" in tripped and streak >= AUTOFIX_MIN_STREAK_TO_FIRE:
                if _can_fire("zero_sent"):
                    logger.warning(
                        f"[autonomous-autofix] firing zero_sent playbook "
                        f"(streak={streak})"
                    )
                    a = await _autofix_channel_gating()
                    b = await _autofix_restart_blast()
                    # Bug-fix: surface autofix-restart failures explicitly
                    # — previously they were silently buried inside the
                    # _log_action audit doc with no operator alert.
                    if not b.get("ok"):
                        logger.error(
                            f"[autonomous-autofix] restart_blast FAILED — "
                            f"{b.get('error')}"
                        )
                    await _log_action(
                        "zero_sent_autofix",
                        f"streak={streak} → seeded={a.get('fixed')} purged={a.get('purged')} "
                        f"restart_ok={b.get('ok')} restart_sent={b.get('sent')}",
                        streak=streak, autofix_seed=a, autofix_restart=b,
                    )

            # ── Playbook B: high_veto_rate → re-seed gating only ──
            if "high_veto_rate" in tripped and veto_rate >= 0.9:
                if _can_fire("high_veto"):
                    logger.warning(
                        f"[autonomous-autofix] firing high_veto playbook "
                        f"(rate={veto_rate:.2f})"
                    )
                    a = await _autofix_channel_gating()
                    await _log_action(
                        "high_veto_autofix",
                        f"rate={veto_rate:.2f} → seeded={a.get('fixed')} purged={a.get('purged')}",
                        veto_rate=veto_rate, autofix_seed=a,
                    )

            # Healthy tick — reset error backoff window.
            _err_backoff = AUTOFIX_INTERVAL_S
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"[autonomous-autofix] loop err: {e}", exc_info=True)
            # Bug-fix: exponential backoff (capped at 30 min) so a sustained
            # downstream outage doesn't hammer Mongo every 90 s.
            _err_backoff = min(_err_backoff * 2, 1800)
            await asyncio.sleep(_err_backoff)
            continue
        await asyncio.sleep(AUTOFIX_INTERVAL_S)
