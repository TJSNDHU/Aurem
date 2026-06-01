"""
services/aurem_public_api.py — iter D-59 Part B

AUREM Public API — commercialization surface. Issues, validates, and
rate-limits API keys that external projects use to call ORA + CTO
agents over HTTPS.

Key format:
  aurem_sk_live_<32-char-secret>   (32 random urlsafe bytes)

Storage shape (`aurem_api_keys`):
  {
    key_id:        uuid (public, safe to log),
    key_hash:      sha256 of the secret (we NEVER store the secret),
    key_prefix:    first 16 chars (for UI listing — "aurem_sk_live_abc")
    name:          founder-friendly label,
    owner_email:   founder or third-party email,
    scopes:        ["ora_chat","cto_chat","leads_read"],
    rate_limit_per_min:  default 30,
    rate_limit_per_day:  default 5000,
    created_at, last_used_at,
    revoked, revoked_at,
    usage:         {today, total},
  }

Usage log (`aurem_api_usage`) is append-only:
  {key_id, endpoint, status_code, latency_ms, ts}
"""
from __future__ import annotations

import hashlib
import logging
import secrets
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any

logger = logging.getLogger(__name__)

_db = None

DEFAULT_SCOPES = ["ora_chat", "cto_chat", "leads_read"]
KEY_PREFIX = "aurem_sk_live_"


def set_db(database) -> None:
    global _db
    _db = database


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_key(secret: str) -> str:
    """sha256 hex — used as the at-rest representation of the secret."""
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def _new_secret() -> str:
    """Generate a fresh secret. 32 bytes of urlsafe random."""
    return KEY_PREFIX + secrets.token_urlsafe(32)


async def issue_key(*, name: str, owner_email: str,
                     scopes: list[str] | None = None,
                     rate_per_min: int = 30,
                     rate_per_day: int = 5000) -> dict[str, Any]:
    """Mint a new API key. Returns the cleartext secret ONCE — caller
    must show it to the founder and never persist it server-side."""
    if _db is None:
        raise RuntimeError("db_not_ready")
    scopes = list(scopes or DEFAULT_SCOPES)
    secret = _new_secret()
    key_id = str(uuid.uuid4())
    row = {
        "key_id":             key_id,
        "key_hash":           _hash_key(secret),
        "key_prefix":         secret[:20],     # first 20 chars only
        "name":               name.strip()[:80],
        "owner_email":        owner_email.strip().lower()[:120],
        "scopes":             scopes,
        "rate_limit_per_min": int(rate_per_min),
        "rate_limit_per_day": int(rate_per_day),
        "created_at":         _now(),
        "last_used_at":       "",
        "revoked":            False,
        "revoked_at":         "",
        "usage_today":        0,
        "usage_total":        0,
        "usage_day":          "",
    }
    await _db.aurem_api_keys.insert_one(row)
    logger.info(f"[public-api] issued key id={key_id} owner={owner_email}")
    public_row = {k: v for k, v in row.items() if k != "key_hash"}
    return {"ok": True, "secret": secret, "key": public_row}


async def list_keys() -> list[dict[str, Any]]:
    if _db is None:
        return []
    out = []
    async for r in _db.aurem_api_keys.find(
        {}, {"_id": 0, "key_hash": 0},
    ).sort("created_at", -1):
        out.append(r)
    return out


async def revoke(key_id: str) -> dict[str, Any]:
    if _db is None:
        raise RuntimeError("db_not_ready")
    res = await _db.aurem_api_keys.update_one(
        {"key_id": key_id},
        {"$set": {"revoked": True, "revoked_at": _now()}},
    )
    return {"ok": res.modified_count == 1, "key_id": key_id}


async def validate_key(secret: str, scope: str | None = None
                        ) -> dict[str, Any] | None:
    """Returns the key row if valid + active + scope allowed, else None."""
    if not secret or not secret.startswith(KEY_PREFIX):
        return None
    if _db is None:
        return None
    row = await _db.aurem_api_keys.find_one(
        {"key_hash": _hash_key(secret)}, {"_id": 0},
    )
    if not row:
        return None
    if row.get("revoked"):
        return None
    if scope and scope not in (row.get("scopes") or []):
        return None
    return row


async def check_rate_limit(key_id: str) -> tuple[bool, str]:
    """Per-day cap only (simple + cheap). Returns (allowed, reason)."""
    if _db is None:
        return True, ""
    row = await _db.aurem_api_keys.find_one(
        {"key_id": key_id}, {"_id": 0},
    )
    if not row:
        return False, "key_not_found"
    today = datetime.now(timezone.utc).date().isoformat()
    if row.get("usage_day") != today:
        # New day → reset
        await _db.aurem_api_keys.update_one(
            {"key_id": key_id},
            {"$set": {"usage_day": today, "usage_today": 0}},
        )
        return True, ""
    if row.get("usage_today", 0) >= row.get("rate_limit_per_day", 5000):
        return False, "daily_quota_exceeded"
    return True, ""


async def record_usage(key_id: str, endpoint: str,
                        status_code: int, latency_ms: int) -> None:
    if _db is None:
        return
    try:
        await _db.aurem_api_keys.update_one(
            {"key_id": key_id},
            {"$inc": {"usage_today": 1, "usage_total": 1},
              "$set": {"last_used_at": _now()}},
        )
        await _db.aurem_api_usage.insert_one({
            "key_id":     key_id,
            "endpoint":   endpoint,
            "status_code": status_code,
            "latency_ms": latency_ms,
            "ts":         _now(),
        })
    except Exception as e:
        logger.warning(f"[public-api] usage write failed: {e}")


async def usage_for(key_id: str, days: int = 7) -> dict[str, Any]:
    if _db is None:
        return {}
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    pipe = [
        {"$match": {"key_id": key_id, "ts": {"$gte": since}}},
        {"$group": {"_id": "$endpoint", "n": {"$sum": 1}}},
    ]
    by_endpoint: dict[str, int] = {}
    async for d in _db.aurem_api_usage.aggregate(pipe):
        by_endpoint[d["_id"]] = d["n"]
    total = await _db.aurem_api_usage.count_documents({
        "key_id": key_id, "ts": {"$gte": since},
    })
    return {"total": total, "by_endpoint": by_endpoint, "days": days}
