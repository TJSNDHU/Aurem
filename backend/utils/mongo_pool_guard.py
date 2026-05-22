"""
mongo_pool_guard.py — Process-wide socket / FD budget for MongoDB clients.
═══════════════════════════════════════════════════════════════════════════
WHY THIS EXISTS (iter 326m, stability bug):
  ~40 services and routers each call `AsyncIOMotorClient(mongo_url)` or
  `MongoClient(mongo_url)` WITHOUT specifying `maxPoolSize`. PyMongo's
  default is 100 connections per client → 40 clients × 100 = 4000 sockets
  attempted on a single mongod process. Plus pwa_router.py creates a
  fresh client PER request (never closes), causing a steady FD leak.

  Result observed in prod-shape preview:
    mongod: "Too many open files, errno: 24, error in creating eventfd"
    backend: "connection closed", health check 502, watchdog tripped
    user impact: app "blinks", campaign blast stuck at zero_sent x190
    cycles, login fails intermittently.

WHAT THIS DOES:
  Monkey-patches `motor.motor_asyncio.AsyncIOMotorClient.__init__` and
  `pymongo.MongoClient.__init__` to enforce sane defaults on EVERY caller,
  even legacy ad-hoc clients:

    maxPoolSize              = 5        (was: 100)
    minPoolSize              = 0        (was: 0 — kept)
    serverSelectionTimeoutMS = 10000    (was: 30000)
    socketTimeoutMS          = 20000    (was: 0/inf)
    connectTimeoutMS         = 10000    (was: 20000)

  Callers that explicitly pass these kwargs are RESPECTED — patch only
  fills in defaults via `setdefault`.

  Total FD budget cap with this patch:
    ~40 clients × 5 sockets = 200 sockets (well under any sane ulimit).

USAGE:
  Import this module at the TOP of `server.py`, BEFORE any service /
  router imports. The patch must apply before any client is constructed.

  ```python
  # server.py — first lines after stdlib imports
  from utils import mongo_pool_guard  # noqa: F401  (applies on import)
  ```

SAFETY:
  - Idempotent: applying twice is a no-op (guarded by module-level flag).
  - Non-destructive: explicit kwargs win, so a service that genuinely
    needs maxPoolSize=50 (e.g. heavy bulk worker) can pass it and the
    patch will not override.
  - Reversible: original __init__ is stashed at `_orig_motor_init` /
    `_orig_pymongo_init` for emergency rollback.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Sane defaults — see module docstring for rationale.
DEFAULTS: dict = {
    "maxPoolSize": 5,
    "minPoolSize": 0,
    "serverSelectionTimeoutMS": 10000,
    "socketTimeoutMS": 20000,
    "connectTimeoutMS": 10000,
}

_applied = False
_orig_motor_init = None
_orig_pymongo_init = None


def apply() -> bool:
    """Apply the patch. Returns True if newly applied, False if already on."""
    global _applied, _orig_motor_init, _orig_pymongo_init
    if _applied:
        return False

    try:
        from motor.motor_asyncio import AsyncIOMotorClient
        _orig_motor_init = AsyncIOMotorClient.__init__

        def _patched_motor_init(self, *args, **kwargs):
            for k, v in DEFAULTS.items():
                kwargs.setdefault(k, v)
            return _orig_motor_init(self, *args, **kwargs)

        AsyncIOMotorClient.__init__ = _patched_motor_init
    except Exception as e:
        logger.warning(f"[mongo-pool-guard] motor patch failed: {e}")

    try:
        from pymongo import MongoClient
        _orig_pymongo_init = MongoClient.__init__

        def _patched_pymongo_init(self, *args, **kwargs):
            for k, v in DEFAULTS.items():
                kwargs.setdefault(k, v)
            return _orig_pymongo_init(self, *args, **kwargs)

        MongoClient.__init__ = _patched_pymongo_init
    except Exception as e:
        logger.warning(f"[mongo-pool-guard] pymongo patch failed: {e}")

    _applied = True
    logger.info(
        f"[mongo-pool-guard] applied — defaults={DEFAULTS}"
    )
    print(
        "[STARTUP] mongo-pool-guard applied (maxPoolSize=5 default)",
        flush=True,
    )
    return True


# Apply on import so callers only need to `import utils.mongo_pool_guard`.
apply()
