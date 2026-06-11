"""
services/email_events.py — iter D-80.

Real per-email time-series of Resend webhook events.

Before D-80 the codebase had three partial sources of email
engagement signal:
  • lead_lifecycle_router.resend_webhook → pushes touchpoints onto
    `campaign_leads.touchpoints` array (good for the lead view, bad
    for funnel aggregation — 200-item cap, no time-series query)
  • services.template_performance → keyed by template_id only, can't
    join back to campaign
  • campaign_leads.outreach_history with type=report_view → pixel hit
    from D-75 Part 1 deliverable links, NOT real Resend opens

D-80 adds a single canonical collection `email_events` that holds
EVERY Resend webhook event with enough context to power the
Campaign Command Funnel's open/click metrics directly:

  {
    event_type:    "email.sent" | "delivered" | "opened" | "clicked" | "bounced" | "complained",
    email_id:      str (Resend's message id, primary join key),
    email_to:      str (lowercased recipient),
    lead_id:       str | None (resolved via _find_lead_by_email),
    campaign_id:   str | None (copied from lead doc),
    template_id:   str | None (from resend tags),
    click_url:     str | None,
    timestamp:     datetime (UTC, when Resend fired the event),
    received_at:   datetime (UTC, when we got it),
    raw:           dict (full event for forensics)
  }

ZERO MOCKS: this writes only what Resend gave us. If
template_id is absent we store None; we do not invent one.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

EVENT_TYPES = {
    "email.sent", "email.delivered", "email.opened",
    "email.clicked", "email.bounced", "email.complained",
}

_db = None


def set_db(database) -> None:
    global _db
    _db = database


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_ts(s: Any) -> datetime:
    """Resend sends `created_at` as ISO string. Coerce → datetime.
    Falls back to `now()` if the field is missing/malformed."""
    if isinstance(s, datetime):
        return s if s.tzinfo else s.replace(tzinfo=timezone.utc)
    if isinstance(s, str):
        try:
            # Resend uses "2026-06-10T12:34:56.789Z"
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception:
            return _now()
    return _now()


async def record_event(
    *,
    event_type: str,
    email_id: str,
    email_to: str,
    raw: dict,
    lead_id: Optional[str] = None,
    campaign_id: Optional[str] = None,
    template_id: Optional[str] = None,
    click_url: Optional[str] = None,
    created_at: Any = None,
) -> Optional[str]:
    """Persist one event. Returns the inserted _id (as str) on success
    or None when the event was deduped / dropped. Idempotent on
    (email_id, event_type, timestamp) via the unique index."""
    if _db is None:
        return None
    if event_type not in EVENT_TYPES:
        logger.debug(f"[email_events] dropping unknown type: {event_type}")
        return None
    if not email_id:
        # Resend always sends an id — if it's missing, that's a bad
        # payload, not a bug worth crashing on. Drop honestly.
        logger.warning("[email_events] event missing email_id, dropping")
        return None

    ts = _parse_ts(created_at)
    doc = {
        "event_type": event_type,
        "email_id":   email_id,
        "email_to":   (email_to or "").strip().lower(),
        "lead_id":    lead_id,
        "campaign_id": campaign_id,
        "template_id": template_id,
        "click_url":  click_url,
        "timestamp":  ts.isoformat(),
        "received_at": _now().isoformat(),
        "raw":         raw or {},
    }
    try:
        # Insert via upsert on the dedup key so a Resend retry of the
        # exact same event won't double-count. The unique index is
        # created lazily by ensure_indexes() below.
        await _db.email_events.update_one(
            {
                "event_type": event_type,
                "email_id":   email_id,
                "timestamp":  doc["timestamp"],
            },
            {"$setOnInsert": doc},
            upsert=True,
        )
        return email_id
    except Exception as e:
        logger.warning(f"[email_events] insert failed: {e}")
        return None


async def ensure_indexes() -> None:
    """Idempotent — create the indexes the funnel relies on. Called
    once at startup (and again is a no-op)."""
    if _db is None:
        return
    try:
        await _db.email_events.create_index(
            [("event_type", 1), ("email_id", 1), ("timestamp", 1)],
            name="ee_dedup_unique",
            unique=True,
        )
        await _db.email_events.create_index(
            [("campaign_id", 1), ("event_type", 1), ("timestamp", -1)],
            name="ee_funnel",
        )
        await _db.email_events.create_index(
            [("lead_id", 1), ("timestamp", -1)],
            name="ee_by_lead",
        )
    except Exception as e:
        logger.warning(f"[email_events] index setup failed: {e}")


async def count_for_campaign(
    campaign_id: Optional[str], event_type: str,
) -> int:
    """Used by campaign_funnel to read real Resend opens/clicks for
    one campaign. Returns 0 honestly when no events match — we
    don't fabricate a baseline."""
    if _db is None:
        return 0
    q: dict[str, Any] = {"event_type": event_type, "campaign_id": campaign_id}
    return await _db.email_events.count_documents(q)
