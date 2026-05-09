"""
JWT Blocklist — MongoDB-only token revocation (iter 322y).

iter 322y: External-cache dependency removed from the auth path. The
blocklist now lives entirely in MongoDB so cache outages cannot break
login or token-verification any longer. Schema:

  collection: token_blocklist
  {
    jti:        str   (JWT ID, unique index)
    blocked_at: datetime (insertion time)
    reason:     str   (e.g. "logout", "password_reset", "admin_revoke")
    expires_at: datetime (TTL index — auto-purges)
  }

Why MongoDB-only:
  - External-cache outage no longer breaks login.
  - Mongo is already the single point of failure for the rest of the
    platform — adding another moving part to auth doubled the failure
    surface for no net safety gain.
  - Mongo TTL index provides the same auto-cleanup semantics as the
    previous SETEX expiry.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

_INDEX_BUILT = False
_DEFAULT_TTL_SECONDS = 8 * 3600  # 8h — matches JWT default expiry


def _resolve_db():
    """Resolve the Motor handle the same way every other auth-path
    module does — server.db is set during FastAPI startup."""
    try:
        from server import db as _server_db
        return _server_db
    except Exception:
        return None


async def _ensure_indexes(db) -> None:
    """Idempotent. Build the unique jti index + TTL index once per
    process. Safe under concurrent calls because Mongo's createIndex
    is a no-op when the same index already exists."""
    global _INDEX_BUILT
    if _INDEX_BUILT or db is None:
        return
    try:
        await db.token_blocklist.create_index("jti", unique=True)
        await db.token_blocklist.create_index(
            "expires_at", expireAfterSeconds=0
        )
        _INDEX_BUILT = True
    except Exception as e:
        logger.debug(f"[jwt-blocklist] index ensure skipped: {e}")


async def block_token(
    token: str, jti: str, ttl_seconds: int = _DEFAULT_TTL_SECONDS,
    reason: str = "logout",
) -> bool:
    """Add a token's JTI to the blocklist. Idempotent — re-blocking the
    same JTI is a no-op (Mongo upsert collapses duplicates)."""
    if not jti:
        return False
    db = _resolve_db()
    if db is None:
        logger.warning("[jwt-blocklist] db unavailable — block_token skipped")
        return False
    await _ensure_indexes(db)
    now = datetime.now(timezone.utc)
    try:
        await db.token_blocklist.update_one(
            {"jti": jti},
            {
                "$set": {
                    "jti": jti,
                    "expires_at": now + timedelta(seconds=ttl_seconds),
                    "reason": reason,
                },
                "$setOnInsert": {"blocked_at": now},
            },
            upsert=True,
        )
        return True
    except Exception as e:
        logger.debug(f"[jwt-blocklist] block failed: {e}")
        return False


async def is_blocked(jti: str) -> bool:
    """Return True if the token JTI is currently revoked.

    Mongo's TTL purges lazily (every 60s background sweep), so we also
    check `expires_at > now` to handle the small window between expiry
    and physical row removal."""
    if not jti:
        return False
    db = _resolve_db()
    if db is None:
        # Failsafe: Mongo unreachable means we cannot verify revocation.
        # We choose AVAILABILITY over strict revocation here — a logged-out
        # user retains access for at most 8h until JWT exp anyway.
        return False
    await _ensure_indexes(db)
    try:
        doc = await db.token_blocklist.find_one(
            {"jti": jti}, {"_id": 0, "expires_at": 1}
        )
        if not doc:
            return False
        exp = doc.get("expires_at")
        if isinstance(exp, datetime):
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            return exp > datetime.now(timezone.utc)
        # No expires_at (legacy row) → treat as still blocked.
        return True
    except Exception as e:
        logger.debug(f"[jwt-blocklist] check failed: {e}")
        return False


async def unblock_token(jti: str) -> bool:
    """Manual un-revoke (e.g. admin reverses a logout). Returns True
    if a row was removed."""
    if not jti:
        return False
    db = _resolve_db()
    if db is None:
        return False
    try:
        res = await db.token_blocklist.delete_one({"jti": jti})
        return res.deleted_count > 0
    except Exception as e:
        logger.debug(f"[jwt-blocklist] unblock failed: {e}")
        return False


async def blocklist_size() -> Optional[int]:
    """Diagnostic — current revoked-token count. Returns None if DB is down."""
    db = _resolve_db()
    if db is None:
        return None
    try:
        return await db.token_blocklist.count_documents({})
    except Exception:
        return None
