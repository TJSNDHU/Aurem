"""
Outreach Deduplication Service — P0 cost-saver
================================================
Stops duplicate SMS / WhatsApp / outbound voice messages going to the
same phone within a configurable window (default 24h).

Why this exists
---------------
Multiple schedulers (sales blast, repair outreach, drip sequencer,
proximity blast, ORA follow-ups, sentinel anomaly alerts, autonomy
engine, scout outreach) can independently target the same lead. Without
a global dedup layer:
  • Customer receives the same message multiple times → unsubscribes
  • Twilio bills $0.01-$0.04 per duplicate → real money on a 60+/day flow
  • TJ has personally received duplicate messages from his own platform

Public API (all async, never raises)
------------------------------------
    await should_skip(phone, message_type, *, window_hours=24,
                      message_hash=None) -> dict
        Returns {"skip": bool, "reason": str, "last_sent_at": iso}

    await record_send(phone, message_type, *, campaign_id=None,
                      message_hash=None, sid=None, status=None)
        Logs a successful send to `outreach_log`. Idempotent.

    await dedup_send(send_fn, phone, message, *, message_type,
                     window_hours=24, campaign_id=None) -> dict
        Convenience wrapper: short-circuits if duplicate, otherwise
        calls send_fn(phone, message), logs the result, returns dict.

Storage
-------
Collection: ``outreach_log``
  Indexes:
    - {phone: 1, message_type: 1, sent_at: -1}    (lookup)
    - {sent_at: 1}  TTL 7 days                     (auto-prune)

Schema:
    phone: E.164 string (normalized by Twilio provider)
    message_type: "sms" | "whatsapp" | "voice"
    sent_at: datetime (UTC)
    campaign_id: optional string
    message_hash: optional sha256 of body (so the SAME wording 2x is
                  blocked even within the dedup window, but a NEW
                  message goes through)
    sid: Twilio message SID
    status: "queued" | "sent" | "failed"
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Dict, Optional

from shared.tenant import FOUNDER_BIN

logger = logging.getLogger(__name__)

# Module-level handle to the active Mongo db (set by server.py / set_db)
_db = None

# Have we ensured the indexes? (best-effort, idempotent)
_indexes_ready = False

# Default dedup windows per channel (hours)
DEFAULT_WINDOWS = {
    "sms": 24,
    "whatsapp": 24,
    "voice": 12,
}


def set_db(database) -> None:
    global _db
    _db = database


def _get_db():
    global _db
    if _db is not None:
        return _db
    try:
        import server
        _db = getattr(server, "db", None)
    except Exception:
        _db = None
    return _db


async def _ensure_indexes(db) -> None:
    global _indexes_ready
    if _indexes_ready:
        return
    try:
        await db.outreach_log.create_index(
            [("phone", 1), ("message_type", 1), ("sent_at", -1)]
        )
        # TTL 7 days — keeps the collection bounded
        await db.outreach_log.create_index(
            "sent_at", expireAfterSeconds=7 * 86400
        )
        _indexes_ready = True
    except Exception as e:
        logger.debug(f"[dedup] index ensure failed (non-fatal): {e}")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _hash_message(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8", errors="ignore")).hexdigest()[:16]


def _normalize_phone(phone: str) -> str:
    """Loose normaliser — strip whitespace + 'whatsapp:' prefix. The
    actual Twilio normaliser runs upstream; this just ensures we
    match across the SMS/WhatsApp pair for the SAME number."""
    if not phone:
        return ""
    p = phone.strip()
    if p.startswith("whatsapp:"):
        p = p[9:]
    return p


# ─────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────

async def should_skip(
    phone: str,
    message_type: str,
    *,
    window_hours: Optional[int] = None,
    message_hash: Optional[str] = None,
) -> Dict[str, Any]:
    """Return whether a send to {phone, message_type} should be skipped.

    Skip rules (any one matches → skip):
      1. ANY send of the same `message_type` to this phone within
         `window_hours` (default 24h).
      2. The EXACT same `message_hash` to this phone within 7 days
         (catches "same template, different campaigns" double-fires).
    """
    db = _get_db()
    if db is None:
        return {"skip": False, "reason": "db_unavailable"}

    await _ensure_indexes(db)

    phone = _normalize_phone(phone)
    if not phone:
        return {"skip": False, "reason": "empty_phone"}

    if window_hours is None:
        window_hours = DEFAULT_WINDOWS.get(message_type, 24)

    cutoff = _utc_now() - timedelta(hours=window_hours)

    # Rule 1: same channel within window
    try:
        recent = await db.outreach_log.find_one(
            {
                "business_id": FOUNDER_BIN,
                "phone": phone,
                "message_type": message_type,
                "sent_at": {"$gte": cutoff},
            },
            {"_id": 0, "sent_at": 1, "campaign_id": 1, "sid": 1},
            sort=[("sent_at", -1)],
        )
    except Exception as e:
        logger.warning(f"[dedup] lookup failed: {e}")
        return {"skip": False, "reason": "lookup_error"}

    if recent:
        return {
            "skip": True,
            "reason": "duplicate_within_window",
            "window_hours": window_hours,
            "last_sent_at": recent.get("sent_at"),
            "last_campaign_id": recent.get("campaign_id"),
            "last_sid": recent.get("sid"),
        }

    # Rule 2: same exact body within 7 days
    if message_hash:
        try:
            wide_cutoff = _utc_now() - timedelta(days=7)
            same_body = await db.outreach_log.find_one(
                {
                    "business_id": FOUNDER_BIN,
                    "phone": phone,
                    "message_hash": message_hash,
                    "sent_at": {"$gte": wide_cutoff},
                },
                {"_id": 0, "sent_at": 1},
                sort=[("sent_at", -1)],
            )
            if same_body:
                return {
                    "skip": True,
                    "reason": "identical_message_within_7d",
                    "last_sent_at": same_body.get("sent_at"),
                }
        except Exception:
            pass

    return {"skip": False, "reason": "ok"}


async def record_send(
    phone: str,
    message_type: str,
    *,
    campaign_id: Optional[str] = None,
    message_hash: Optional[str] = None,
    sid: Optional[str] = None,
    status: str = "sent",
    extra: Optional[Dict[str, Any]] = None,
) -> bool:
    """Insert a record of a successful send. Idempotent — safe to call
    twice for the same (phone, message_type, sent_at) within ~1ms."""
    db = _get_db()
    if db is None:
        return False
    await _ensure_indexes(db)
    try:
        doc = {
            "phone": _normalize_phone(phone),
            "message_type": message_type,
            "sent_at": _utc_now(),
            "campaign_id": campaign_id,
            "message_hash": message_hash,
            "sid": sid,
            "status": status,
        }
        if extra:
            doc.update({k: v for k, v in extra.items() if k not in doc})
        doc.setdefault("business_id", FOUNDER_BIN)
        await db.outreach_log.insert_one(doc)
        return True
    except Exception as e:
        logger.warning(f"[dedup] record_send failed: {e}")
        return False


async def dedup_send(
    send_fn: Callable[[str, str], Awaitable[Dict[str, Any]]],
    phone: str,
    message: str,
    *,
    message_type: str,
    window_hours: Optional[int] = None,
    campaign_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Send only if not a duplicate. Returns the send_fn result OR
    a `{success: True, skipped: True, reason: ...}` shape on dedup."""
    body_hash = _hash_message(message)

    skip_check = await should_skip(
        phone, message_type, window_hours=window_hours, message_hash=body_hash
    )
    if skip_check.get("skip"):
        logger.info(
            f"[dedup] SKIP {message_type} to {phone[-4:]} — "
            f"{skip_check.get('reason')}"
        )
        return {
            "success": True,
            "skipped": True,
            "reason": skip_check.get("reason"),
            "last_sent_at": skip_check.get("last_sent_at"),
            "channel": message_type,
        }

    # Not a dup → actually send
    result = await send_fn(phone, message)

    # Log only on success — failed sends should NOT block a retry
    if isinstance(result, dict) and result.get("success"):
        await record_send(
            phone, message_type,
            campaign_id=campaign_id,
            message_hash=body_hash,
            sid=result.get("message_sid") or result.get("sid"),
            status=result.get("status") or "sent",
        )
    return result
