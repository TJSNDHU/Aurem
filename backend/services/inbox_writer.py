"""
Unified Inbox Writer — single helper used by every inbound channel handler.

Per AUREM customer-facing spec, every inbound event (email, SMS, WhatsApp)
mirrors into `db.unified_inbox` in this exact shape:

  {
    business_id: "AUR-FNDR-001",
    channel: "email" | "sms" | "whatsapp",
    direction: "inbound" | "outbound",
    from: "<sender>",
    message: "<body>",
    timestamp: <utc>,
    thread_id: <lead_id>,
    read: false,
    sent_via: "resend"|"twilio_sms"|"twilio_whatsapp"|"whapi"  (optional, outbound only)
  }

The OmnichannelHub UI reads `db.unified_inbox` directly, so this collection
is the SOURCE OF TRUTH for the customer-facing inbox.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

_VALID_CHANNELS = {"email", "sms", "whatsapp"}
_VALID_DIRECTIONS = {"inbound", "outbound"}


async def write_inbox(
    db,
    *,
    channel: str,
    direction: str,
    sender: str,
    message: str,
    thread_id: Optional[str] = None,
    business_id: Optional[str] = None,
    sent_via: Optional[str] = None,
) -> Optional[str]:
    """Insert a single row into `db.unified_inbox`. Returns inserted _id (str)
    on success, None on failure. Never raises.
    """
    if db is None:
        return None
    ch = (channel or "").lower().strip()
    di = (direction or "inbound").lower().strip()
    if ch not in _VALID_CHANNELS:
        logger.debug(f"[InboxWriter] invalid channel: {channel!r}")
        return None
    if di not in _VALID_DIRECTIONS:
        di = "inbound"

    # Customer-facing inbox MUST always carry a business_id so the
    # OmnichannelHub query (`{business_id: bin}`) returns the right rows.
    bin_id = (business_id or "").strip() or os.environ.get(
        "DEFAULT_TENANT_BIN", "AUR-FNDR-001"
    )

    doc = {
        "business_id": bin_id,
        "channel": ch,
        "direction": di,
        "from": (sender or "")[:300],
        "message": (message or "")[:5000],
        "timestamp": datetime.now(timezone.utc),
        "thread_id": thread_id or "",
        "read": False,
    }
    if sent_via:
        doc["sent_via"] = sent_via

    try:
        res = await db.unified_inbox.insert_one(doc)
        return str(res.inserted_id)
    except Exception as e:
        logger.debug(f"[InboxWriter] insert failed: {e}")
        return None


async def ensure_indexes(db) -> None:
    """Create indexes for fast read queries by the customer dashboard.

    Called once at app startup. Idempotent.
    """
    if db is None:
        return
    try:
        await db.unified_inbox.create_index(
            [("business_id", 1), ("timestamp", -1)], background=True
        )
        await db.unified_inbox.create_index(
            [("thread_id", 1), ("timestamp", -1)], background=True
        )
        await db.unified_inbox.create_index(
            [("business_id", 1), ("read", 1)], background=True
        )
        logger.info("[InboxWriter] unified_inbox indexes ensured")
    except Exception as e:
        logger.warning(f"[InboxWriter] index create failed: {e}")
