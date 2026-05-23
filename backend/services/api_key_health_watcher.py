"""
services/api_key_health_watcher.py — iter 330d

When any 3rd-party HTTP integration returns a "your key is broken"
signal (401 / 403 / 429 hard-cap / suspended), this module emits
exactly ONE Telegram alert per (provider, day, status) so the founder
finds out within minutes — not next week when a campaign is empty.

Public API
──────────
    record_api_failure(provider, status_code, body_excerpt="", key_hint="")

    health_summary(db, days=7)   →  used by morning brief / cockpit

The watcher is integration-agnostic: pass any provider name and any
status code; it does the throttling and alert formatting.

Dedup
─────
Fingerprint = "apikey_<provider>_<status_bucket>_<YYYY-MM-DD>"
status_bucket ∈ {"unauthorized" 401, "forbidden" 403, "rate_limit" 429, "other"}
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger("api_key_health")

_BUCKET = {401: "unauthorized", 403: "forbidden", 429: "rate_limit"}
_BAD_BODY_TOKENS = (
    "suspended", "api_inaccessible", "permission_denied",
    "invalid api key", "invalid_api_key", "key has been disabled",
    "key not valid", "consumer.+suspended",
)


def _bucket(status_code: int) -> str:
    if status_code in _BUCKET:
        return _BUCKET[status_code]
    return "other"


def _is_credential_error(status_code: int, body: str) -> bool:
    """Returns True when the failure is plausibly a key/credential problem.

    Hard-bucket 401 / 403 always count. For 429 we also count. For other
    status codes we look at the body for known credential-fault tokens.
    """
    if status_code in (401, 403, 429):
        return True
    b = (body or "").lower()
    return any(tok in b for tok in _BAD_BODY_TOKENS)


_db_ref = None


def set_db(database):
    global _db_ref
    _db_ref = database


async def record_api_failure(
    *,
    provider:    str,
    status_code: int,
    body:        str = "",
    key_hint:    str = "",
) -> dict:
    """Persist + (maybe) Telegram-alert one failure.

    Returns: {"ok": True, "alerted": bool}
    Never raises — failure to record never breaks the caller.
    """
    if not _is_credential_error(status_code, body):
        return {"ok": True, "alerted": False, "reason": "not_credential_error"}

    bucket = _bucket(status_code)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    fingerprint = f"apikey_{provider}_{bucket}_{today}"

    # Persist regardless of alert dedup so we keep a full audit trail.
    if _db_ref is not None:
        try:
            await _db_ref.api_key_health_log.insert_one({
                "ts":          datetime.now(timezone.utc),
                "provider":    provider,
                "status_code": status_code,
                "bucket":      bucket,
                "key_hint":    key_hint[:24],
                "body":        (body or "")[:400],
                "fingerprint": fingerprint,
            })
        except Exception as e:
            logger.debug(f"[api-key-health] persist failed: {e}")

    # Telegram alert — fingerprinted so we send at most one per (provider,
    # bucket, day).
    alerted = False
    try:
        from services.silent_failure_alerts import _send as _tg
        bucket_emoji = {
            "unauthorized": "🚫", "forbidden": "⛔", "rate_limit": "🐌",
        }.get(bucket, "⚠️")
        head = body.strip().splitlines()[0] if body else ""
        await _tg(
            f"{bucket_emoji} API KEY ISSUE — `{provider}` returned HTTP "
            f"{status_code} ({bucket}). {('Body: ' + head[:140]) if head else ''} "
            f"Founder: check the dashboard for `{provider}` and rotate the key.",
            fingerprint=fingerprint,
        )
        alerted = True
    except Exception as e:
        logger.debug(f"[api-key-health] alert failed: {e}")

    return {"ok": True, "alerted": alerted, "fingerprint": fingerprint}


async def health_summary(db, days: int = 7) -> dict:
    """Last-N-day rollup. Used by morning brief / outreach health card."""
    if db is None:
        return {"ok": False, "error": "db unavailable"}
    cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, days))
    by_provider: dict[str, dict[str, int]] = {}
    try:
        cur = db.api_key_health_log.find(
            {"ts": {"$gte": cutoff}},
            {"_id": 0, "provider": 1, "bucket": 1},
        ).limit(2000)
        async for r in cur:
            p = r.get("provider") or "unknown"
            b = r.get("bucket") or "other"
            by_provider.setdefault(p, {}).setdefault(b, 0)
            by_provider[p][b] += 1
    except Exception:
        pass
    return {"ok": True, "window_days": days, "by_provider": by_provider}
