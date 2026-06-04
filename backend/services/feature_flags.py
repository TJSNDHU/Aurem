"""
feature_flags.py — iter D-63
============================
Mongo-backed feature flags for blast-radius control.

Schema (collection: `feature_flags`):
    {
        "flag":        "new_pricing_engine",       # unique
        "enabled":     true,                       # global on/off
        "rollout_pct": 25,                         # 0-100, default 100
        "tenants":     ["tenant-uuid-1"],          # explicit allow-list
        "description": "Switch to new metered billing",
        "created_at":  ISO,
        "updated_at":  ISO,
    }

Decision order:
    1. Flag not found              → DEFAULT (False, but configurable)
    2. enabled=False               → False
    3. tenant in tenants list      → True
    4. rollout_pct=100             → True
    5. rollout_pct=0               → False
    6. Otherwise: hash(tenant+flag) % 100 < rollout_pct  (deterministic)

The deterministic hash means once a tenant is bucketed in, they stay in
across pod restarts — critical for consistent user experience during
percentage-based rollouts.
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_db = None
# In-memory cache: 30s TTL. Mongo lookup on every is_enabled() call would
# pummel the DB during high-traffic paths (Pillar Map heartbeat, etc.).
_CACHE: Dict[str, tuple] = {}  # flag → (doc, expires_at)
_CACHE_TTL_SEC = 30.0


def set_db(db) -> None:
    """Wire the Mongo db handle (called from server startup)."""
    global _db
    _db = db


def _get_db():
    return _db


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _fetch_flag(flag: str) -> Optional[Dict[str, Any]]:
    import time as _t
    now = _t.monotonic()
    cached = _CACHE.get(flag)
    if cached and cached[1] > now:
        return cached[0]

    db = _get_db()
    if db is None:
        return None
    doc = await db.feature_flags.find_one({"flag": flag}, {"_id": 0})
    _CACHE[flag] = (doc, now + _CACHE_TTL_SEC)
    return doc


def _bucket_hash(tenant: str, flag: str) -> int:
    """Deterministic 0-99 bucket — same tenant always lands in same bucket."""
    h = hashlib.sha256(f"{tenant}::{flag}".encode("utf-8")).hexdigest()
    return int(h[:8], 16) % 100


async def is_enabled(
    flag: str,
    tenant: str = "",
    *,
    default: bool = False,
) -> bool:
    """Resolve whether a feature flag is on for the given tenant."""
    if not flag:
        return default
    doc = await _fetch_flag(flag)
    if not doc:
        return default
    if not doc.get("enabled", True):
        return False
    # Explicit tenant allow-list always wins.
    if tenant and tenant in (doc.get("tenants") or []):
        return True
    pct = int(doc.get("rollout_pct", 100))
    if pct >= 100:
        return True
    if pct <= 0:
        return False
    # Percentage rollout — deterministic per tenant.
    if not tenant:
        # No tenant key → use the random global bucket; keeps "% on" stable
        # for stateless calls across pod boots.
        return _bucket_hash("__global__", flag) < pct
    return _bucket_hash(tenant, flag) < pct


async def set_flag(
    flag: str,
    *,
    enabled: bool = True,
    rollout_pct: int = 100,
    tenants: Optional[List[str]] = None,
    description: str = "",
) -> Dict[str, Any]:
    """Upsert a feature flag. Returns the persisted doc."""
    if not flag or not flag.replace("_", "").replace("-", "").isalnum():
        raise ValueError("flag must be alphanumeric / underscore / dash")
    if not (0 <= int(rollout_pct) <= 100):
        raise ValueError("rollout_pct must be 0-100")
    db = _get_db()
    if db is None:
        raise RuntimeError("feature_flags db not wired")
    update = {
        "flag": flag,
        "enabled": bool(enabled),
        "rollout_pct": int(rollout_pct),
        "tenants": list(tenants or []),
        "description": description or "",
        "updated_at": _now_iso(),
    }
    await db.feature_flags.update_one(
        {"flag": flag},
        {"$set": update, "$setOnInsert": {"created_at": _now_iso()}},
        upsert=True,
    )
    # Bust cache for this flag.
    _CACHE.pop(flag, None)
    return await db.feature_flags.find_one({"flag": flag}, {"_id": 0})


async def list_flags() -> List[Dict[str, Any]]:
    db = _get_db()
    if db is None:
        return []
    out = []
    async for d in db.feature_flags.find({}, {"_id": 0}).sort("flag", 1):
        out.append(d)
    return out


async def delete_flag(flag: str) -> bool:
    db = _get_db()
    if db is None:
        return False
    res = await db.feature_flags.delete_one({"flag": flag})
    _CACHE.pop(flag, None)
    return res.deleted_count > 0
