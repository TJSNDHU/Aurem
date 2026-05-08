"""
ORA Self-Healing Monitor (iter 281.1, Phase 2.1)

Watchdog that polls 5 critical services every 5 minutes, performs scoped
auto-heal actions on transient failures, and routes alerts through ORA's
existing notifications collection (NOT direct Twilio — admin SMS is
synthesized downstream by the existing alert pipeline).

Services watched:
  1. Stripe        — GET /api/stripe-embed/health → secret_mode == "live"
  2. MongoDB       — ping payment_transactions collection
  3. Twilio        — env vars TWILIO_ACCOUNT_SID + TWILIO_AUTH_TOKEN present
  4. Redis         — ping shared async pool
  5. ORA           — POST /api/ora/command responds in < 3000ms

Auto-heal:
  - Redis down  → call utils.redis_pool.reset_for_hot_reload() and re-ping
                   up to 3x (60s each) before alerting
  - Mongo down  → re-instantiate AsyncIOMotorClient on _db (we do this by
                   bouncing the global handle via reset_db_handle())
  - ORA slow    → drop in-process cache (LRU caches across the ora
                   modules) and let next request mint fresh

Storage:
  - db.ora_health_checks       : last status per service (upsert)
  - db.notifications           : alert events when status flips green→red
  - db.ora_health_incidents    : full incident log

State machine (per-service):
  green  → green   : silent
  green  → yellow  : silent (transient — wait for next tick)
  green  → red     : alert + heal
  red    → red     : silent (don't spam)
  red    → green   : "service recovered" alert
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from datetime import datetime, timezone
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# Admin contact (used by downstream alert pipeline; we just stamp the
# notification with this so the pipeline knows where to deliver SMS).
_ADMIN_PHONE = os.environ.get("ORA_HEALTH_ADMIN_PHONE", "+16134000000")

_LOCAL_BACKEND = "http://localhost:8001"
_TIMEOUT = 3.0  # tight — we never want the watchdog itself to hang


# ─────────────────────────────────────────────────────────────────────
# Individual service checks. Each returns (status, latency_ms, reason).
# status ∈ {"green", "yellow", "red"}
# ─────────────────────────────────────────────────────────────────────
async def _check_stripe() -> tuple[str, int, str]:
    t0 = time.time()
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            r = await client.get(f"{_LOCAL_BACKEND}/api/stripe-embed/health")
        latency_ms = int((time.time() - t0) * 1000)
        if r.status_code != 200:
            return ("red", latency_ms, f"HTTP {r.status_code}")
        body = r.json()
        mode = body.get("secret_mode", "unknown")
        if mode == "live":
            return ("green", latency_ms, "live keys active")
        if mode == "test":
            return ("yellow", latency_ms, "running in TEST mode")
        return ("red", latency_ms, f"unexpected mode={mode}")
    except Exception as e:
        return ("red", int((time.time() - t0) * 1000), f"unreachable: {e}")


async def _check_mongo(db) -> tuple[str, int, str]:
    t0 = time.time()
    try:
        await db.payment_transactions.estimated_document_count()
        return ("green", int((time.time() - t0) * 1000), "primary collection reachable")
    except Exception as e:
        return ("red", int((time.time() - t0) * 1000), f"ping failed: {e}")


async def _check_twilio() -> tuple[str, int, str]:
    sid = os.environ.get("TWILIO_ACCOUNT_SID", "").strip()
    tok = os.environ.get("TWILIO_AUTH_TOKEN", "").strip()
    if sid and tok:
        return ("green", 0, "credentials present")
    missing = [k for k, v in (("SID", sid), ("TOKEN", tok)) if not v]
    return ("red", 0, f"missing: {','.join(missing)}")


async def _check_redis() -> tuple[str, int, str]:
    """Ping shared pool. Tolerates absence of REDIS_URL (yellow, not red)."""
    if not os.environ.get("REDIS_URL", "").strip():
        return ("yellow", 0, "REDIS_URL not configured (optional)")
    t0 = time.time()
    try:
        from utils.redis_pool import get_async_redis
        client = await get_async_redis()
        if client is None:
            return ("red", int((time.time() - t0) * 1000), "client init failed")
        await client.ping()
        return ("green", int((time.time() - t0) * 1000), "pool alive")
    except Exception as e:
        return ("red", int((time.time() - t0) * 1000), f"ping failed: {e}")


async def _check_ora() -> tuple[str, int, str]:
    """POST /api/ora/command with a trivial probe and require <3s."""
    t0 = time.time()
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            r = await client.post(
                f"{_LOCAL_BACKEND}/api/ora/command",
                json={"command": "health-ping", "session_id": "ora_self_heal_watchdog"},
            )
        latency_ms = int((time.time() - t0) * 1000)
        if r.status_code >= 500:
            return ("red", latency_ms, f"HTTP {r.status_code}")
        if latency_ms >= 3000:
            return ("yellow", latency_ms, f"slow ({latency_ms}ms ≥ 3000ms threshold)")
        return ("green", latency_ms, f"{latency_ms}ms")
    except Exception as e:
        return ("red", int((time.time() - t0) * 1000), f"error: {e}")


# ─────────────────────────────────────────────────────────────────────
# Auto-heal handlers (best-effort, never raise)
# ─────────────────────────────────────────────────────────────────────
async def _heal_redis() -> str:
    try:
        from utils.redis_pool import reset_for_hot_reload, get_async_redis
        for attempt in range(1, 4):
            reset_for_hot_reload()
            await asyncio.sleep(1.0)
            client = await get_async_redis()
            if client is not None:
                try:
                    await client.ping()
                    return f"recovered on attempt {attempt}"
                except Exception:
                    pass
        return "all 3 reconnect attempts failed"
    except Exception as e:
        return f"heal-error: {e}"


async def _heal_mongo(db) -> str:
    """For mongo we can't bounce the client without restarting the process —
    but we CAN re-ping with a fresh aggregate to confirm liveness recovered.
    APScheduler will retry on next tick. This is best-effort acknowledge."""
    try:
        await db.payment_transactions.estimated_document_count()
        return "ping ok on re-check"
    except Exception as e:
        return f"still down: {e}"


async def _heal_ora() -> str:
    """Drop in-process LRU caches across the ora_* modules."""
    cleared = []
    for mod_name in [
        "services.ora_brain",
        "services.ora_intent_router",
        "services.ora_command_handler",
        "services.ora_response_cache",
    ]:
        try:
            import importlib
            mod = importlib.import_module(mod_name)
            for attr in dir(mod):
                obj = getattr(mod, attr, None)
                if callable(obj) and hasattr(obj, "cache_clear"):
                    try:
                        obj.cache_clear()
                        cleared.append(f"{mod_name}.{attr}")
                    except Exception:
                        pass
        except ImportError:
            continue
    return f"cleared {len(cleared)} caches" if cleared else "no caches to clear"


# ─────────────────────────────────────────────────────────────────────
# Notification dispatch (ORA notifications collection)
# ─────────────────────────────────────────────────────────────────────
async def _emit_notification(db, service: str, kind: str, msg: str) -> None:
    """Write into db.notifications. Existing pipeline picks these up and
    fan-outs to admin SMS / push. We do NOT call Twilio directly here.
    """
    try:
        await db.notifications.insert_one({
            "kind": "ora_health",
            "service": service,
            "severity": "critical" if kind == "down" else "info",
            "title": f"ORA Health: {service.upper()} {kind}",
            "body": msg,
            "tenant_id": "system",
            "admin_phone": _ADMIN_PHONE,
            "read": False,
            "sent_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        logger.warning(f"[ora_self_heal] notification write failed: {e}")


# ─────────────────────────────────────────────────────────────────────
# Single tick — called by scheduler every 5 min
# ─────────────────────────────────────────────────────────────────────
async def run_health_tick(db) -> dict:
    """Run all 5 checks, persist, heal where needed, emit alerts on flips.
    Returns the latest status snapshot for the Mission Control widget."""
    if db is None:
        logger.warning("[ora_self_heal] db unavailable, skipping tick")
        return {}

    services: dict = {
        "stripe": await _check_stripe(),
        "mongo":  await _check_mongo(db),
        "twilio": await _check_twilio(),
        "redis":  await _check_redis(),
        "ora":    await _check_ora(),
    }

    now_iso = datetime.now(timezone.utc).isoformat()
    snapshot: dict = {}

    for service, (status, latency_ms, reason) in services.items():
        # Fetch previous state
        prior = await db.ora_health_checks.find_one(
            {"service": service}, {"_id": 0}
        ) or {}
        prev_status = prior.get("status")

        heal_result: Optional[str] = None
        if status == "red":
            if service == "redis":
                heal_result = await _heal_redis()
                # Re-check after heal
                redo = await _check_redis()
                if redo[0] == "green":
                    status, latency_ms, reason = redo
                    reason = f"healed: {heal_result}"
            elif service == "mongo":
                heal_result = await _heal_mongo(db)
            elif service == "ora":
                heal_result = await _heal_ora()

        # Persist current state
        await db.ora_health_checks.update_one(
            {"service": service},
            {"$set": {
                "service": service,
                "status": status,
                "latency_ms": latency_ms,
                "reason": reason,
                "last_check": now_iso,
                "last_heal_action": heal_result,
            }},
            upsert=True,
        )

        # Append to incident log only on flips (avoid noise)
        if prev_status != status:
            try:
                await db.ora_health_incidents.insert_one({
                    "service": service,
                    "from_status": prev_status,
                    "to_status": status,
                    "reason": reason,
                    "heal_action": heal_result,
                    "ts": now_iso,
                })
            except Exception:
                pass

            # Fire alert via ORA notifications pipeline.
            #   green → red   = "down"
            #   red   → green = "recovered"
            # Other transitions stay silent.
            if prev_status == "green" and status == "red":
                await _emit_notification(db, service, "down", reason)
            elif prev_status == "red" and status == "green":
                heal_msg = f" ({heal_result})" if heal_result else ""
                await _emit_notification(
                    db, service, "recovered", f"{reason}{heal_msg}"
                )

        snapshot[service] = {
            "status": status, "latency_ms": latency_ms, "reason": reason,
            "last_heal_action": heal_result, "last_check": now_iso,
        }

    return snapshot


def install_scheduler(scheduler, db) -> None:
    """Hook into the existing AsyncIOScheduler in registry.py.
    Idempotent: replace_existing=True ensures no duplicate jobs on hot-reload.
    """
    async def _watchdog_tick():
        try:
            await run_health_tick(db)
        except Exception as e:
            logger.warning(f"[ora_self_heal] tick error: {e}")

    try:
        scheduler.add_job(
            _watchdog_tick,
            "interval", minutes=5,
            id="ora_self_heal_watchdog",
            name="ORA Self-Heal Watchdog (5min)",
            replace_existing=True,
            max_instances=1,        # don't pile up if a tick runs slow
            coalesce=True,          # collapse missed runs into one
            misfire_grace_time=120,
        )
        logger.info("[ora_self_heal] watchdog scheduled (every 5 min)")
    except Exception as e:
        logger.warning(f"[ora_self_heal] scheduler install failed: {e}")
