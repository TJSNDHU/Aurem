"""
AUREM Circuit Breakers (pybreaker + Redis state storage)
========================================================
Redis-backed circuit breakers so state survives pod restarts.

Design:
- 6 named breakers (mongodb / redis / openrouter / twilio / resend / groq)
- State stored in Redis; survives uvicorn reload + K8s pod restart.
- Business exceptions (KeyError, ValueError, TypeError) excluded from
  trip logic so bad input never opens an infrastructure breaker.
- State transitions written to MongoDB `breaker_events` via listener.

IMPORTANT: The redis client for pybreaker must use decode_responses=False
(raw bytes); a dedicated client is created here to avoid conflicting with
the app's shared redis client which may use decode_responses=True.
"""
from __future__ import annotations

import os
import logging
from datetime import datetime, timezone

import pybreaker
import redis as redis_sync

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════
# Redis client — dedicated for breaker state (raw bytes)
# ═══════════════════════════════════════════════════════════════════════
_redis_for_breakers = None


def _get_breaker_redis():
    """Lazy-init a dedicated Redis client for pybreaker state storage."""
    global _redis_for_breakers
    if _redis_for_breakers is not None:
        return _redis_for_breakers

    redis_url = os.environ.get("REDIS_URL", "").strip()
    if not redis_url:
        logger.warning("[breakers] REDIS_URL unset — breakers will use in-memory state")
        return None

    try:
        _redis_for_breakers = redis_sync.StrictRedis.from_url(
            redis_url,
            decode_responses=False,  # REQUIRED by pybreaker
            socket_timeout=2,
            socket_connect_timeout=2,
        )
        _redis_for_breakers.ping()
        logger.info("[breakers] Redis-backed state storage ready")
        return _redis_for_breakers
    except Exception as e:
        logger.warning(f"[breakers] Redis unavailable ({e}) — breakers will use in-memory state")
        _redis_for_breakers = None
        return None


def _make_storage(namespace: str):
    """Return a CircuitRedisStorage or None (→ in-memory fallback)."""
    r = _get_breaker_redis()
    if r is None:
        return None
    try:
        return pybreaker.CircuitRedisStorage(
            pybreaker.STATE_CLOSED,
            r,
            namespace=namespace,
        )
    except Exception as e:
        logger.warning(f"[breakers] CircuitRedisStorage('{namespace}') failed: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════
# Breaker definitions — module-level globals
# ═══════════════════════════════════════════════════════════════════════
# Business exceptions that should NEVER trip the breaker:
_BUSINESS_EXCLUSIONS = [KeyError, ValueError, TypeError]


def _mk(name: str, fail_max: int, reset_timeout: int, exclude: list):
    """Create a named breaker with Redis storage (if available)."""
    kwargs = dict(
        fail_max=fail_max,
        reset_timeout=reset_timeout,
        name=name,
        exclude=exclude,
    )
    storage = _make_storage(f"cb_{name}")
    if storage is not None:
        kwargs["state_storage"] = storage
    return pybreaker.CircuitBreaker(**kwargs)


mongodb_breaker    = _mk("mongodb",    fail_max=3, reset_timeout=30, exclude=_BUSINESS_EXCLUSIONS)
redis_breaker      = _mk("redis",      fail_max=3, reset_timeout=20, exclude=_BUSINESS_EXCLUSIONS)
openrouter_breaker = _mk("openrouter", fail_max=2, reset_timeout=45, exclude=[])
twilio_breaker     = _mk("twilio",     fail_max=3, reset_timeout=60, exclude=[])
resend_breaker     = _mk("resend",     fail_max=3, reset_timeout=60, exclude=[])
groq_breaker       = _mk("groq",       fail_max=2, reset_timeout=30, exclude=[])

ALL_BREAKERS = [
    mongodb_breaker, redis_breaker, openrouter_breaker,
    twilio_breaker, resend_breaker, groq_breaker,
]


# ═══════════════════════════════════════════════════════════════════════
# MongoDB listener — records every state change to `breaker_events`
# ═══════════════════════════════════════════════════════════════════════
class AUREMBreakerListener(pybreaker.CircuitBreakerListener):
    def __init__(self, db):
        self.db = db

    def state_change(self, cb, old_state, new_state):
        import asyncio
        try:
            asyncio.create_task(self.db.breaker_events.insert_one({
                "breaker": cb.name,
                "old_state": str(old_state.name if hasattr(old_state, "name") else old_state),
                "new_state": str(new_state.name if hasattr(new_state, "name") else new_state),
                "timestamp": datetime.now(timezone.utc),
            }))
            logger.info(f"[breaker:{cb.name}] {old_state} → {new_state}")
        except RuntimeError:
            # No running loop (e.g. sync context) — ignore; the transition still happens.
            pass
        except Exception as e:
            logger.warning(f"[breakers] listener write failed: {e}")


_listener_attached = False


def attach_db_listeners(db):
    """Attach a MongoDB listener to every breaker (idempotent)."""
    global _listener_attached
    if _listener_attached or db is None:
        return
    listener = AUREMBreakerListener(db)
    for b in ALL_BREAKERS:
        b.add_listener(listener)
    _listener_attached = True
    logger.info(f"[breakers] DB listener attached to {len(ALL_BREAKERS)} breakers")


def breaker_status() -> dict:
    """Snapshot of all breaker states — for admin dashboards."""
    out = {}
    for b in ALL_BREAKERS:
        try:
            out[b.name] = {
                "state": b.current_state,
                "fail_counter": b.fail_counter,
                "fail_max": b.fail_max,
                "reset_timeout": b.reset_timeout,
            }
        except Exception as e:
            out[b.name] = {"error": str(e)}
    return out


__all__ = [
    "mongodb_breaker", "redis_breaker", "openrouter_breaker",
    "twilio_breaker", "resend_breaker", "groq_breaker",
    "ALL_BREAKERS", "attach_db_listeners", "breaker_status",
    "AUREMBreakerListener",
]
