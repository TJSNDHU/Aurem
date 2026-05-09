"""
llm_response_cache.py — Signature-keyed LLM response cache.

Goal: drop Claude token spend on repeated error signatures. The Sentinel
loop already dedups by `signature` at the suggestion layer, but a cache
hit at the *LLM layer* means we skip even the triage + Claude calls
entirely when an identical error class re-appears within TTL.

Schema (collection: `llm_response_cache`):
  {
    cache_key:   sha1(scope + signature + prompt_hash)  (unique index)
    scope:       "sentinel_diagnose" | "admin_ora" | ...
    signature:   error signature (or question hash for ORA)
    payload:     JSON dict — the cached LLM output (parsed)
    hits:        int — usage counter
    created_at:  datetime
    expires_at:  datetime  (TTL index — auto-purges)
  }
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# 24h default TTL — error patterns recur, but fix recommendations should
# refresh daily so we re-learn after deploys / dependency bumps.
DEFAULT_TTL_HOURS = 24
_INDEX_BUILT = False


def _hash_key(scope: str, signature: str, prompt_seed: str = "") -> str:
    """Stable cache key. `prompt_seed` lets callers vary the prompt
    while keeping the same signature (e.g. system-prompt revisions)."""
    raw = f"{scope}::{signature}::{prompt_seed}".encode("utf-8")
    return hashlib.sha1(raw).hexdigest()


async def _ensure_indexes(db) -> None:
    """Idempotent: unique cache_key + TTL on expires_at."""
    global _INDEX_BUILT
    if _INDEX_BUILT or db is None:
        return
    try:
        await db.llm_response_cache.create_index("cache_key", unique=True)
        await db.llm_response_cache.create_index(
            "expires_at", expireAfterSeconds=0
        )
        _INDEX_BUILT = True
    except Exception as e:
        logger.debug(f"[llm-cache] index ensure skipped: {e}")


async def cache_get(
    db, *, scope: str, signature: str, prompt_seed: str = ""
) -> Optional[Dict[str, Any]]:
    """Return cached payload or None. Increments hit counter on hit."""
    if db is None or not signature:
        return None
    await _ensure_indexes(db)
    key = _hash_key(scope, signature, prompt_seed)
    doc = await db.llm_response_cache.find_one({"cache_key": key}, {"_id": 0})
    if not doc:
        return None
    # Mongo TTL purges lazily — guard against a still-present-but-expired row.
    exp = doc.get("expires_at")
    if isinstance(exp, datetime):
        # Mongo returns naive datetimes — coerce to UTC for the comparison.
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp < datetime.now(timezone.utc):
            return None
    try:
        await db.llm_response_cache.update_one(
            {"cache_key": key}, {"$inc": {"hits": 1}}
        )
    except Exception:
        pass
    return doc.get("payload")


async def cache_put(
    db,
    *,
    scope: str,
    signature: str,
    payload: Dict[str, Any],
    prompt_seed: str = "",
    ttl_hours: int = DEFAULT_TTL_HOURS,
) -> None:
    """Upsert payload. Caller is responsible for not caching errors."""
    if db is None or not signature or not payload:
        return
    await _ensure_indexes(db)
    key = _hash_key(scope, signature, prompt_seed)
    now = datetime.now(timezone.utc)
    try:
        await db.llm_response_cache.update_one(
            {"cache_key": key},
            {
                "$set": {
                    "cache_key": key,
                    "scope": scope,
                    "signature": signature,
                    "payload": payload,
                    "expires_at": now + timedelta(hours=ttl_hours),
                },
                "$setOnInsert": {"created_at": now, "hits": 0},
            },
            upsert=True,
        )
    except Exception as e:
        logger.debug(f"[llm-cache] put failed: {e}")
