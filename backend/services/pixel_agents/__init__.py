"""
pixel_agents — pixel-event fan-out agents (visitor_intel, form_capture,
error_healer). Subscribed to pixel A2A topics, write per-BIN insights and
emit telemetry to admin ORA brain.
═══════════════════════════════════════════════════════════════════════════
Lightweight by design — they DO NOT enrich via Emergent API on every event
(too expensive at scale). Enrichment happens in batches via the existing
pixel_event_buffer + a separate `pixel_enrichment_scheduler` (future).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def visitor_intel_agent(db, event_doc: Dict[str, Any]) -> None:
    """Tags page_view / scroll_depth events with a lead_score signal,
    upserts into a `visitor_intel` collection per-BIN."""
    if db is None or not event_doc:
        return
    bin_id = event_doc.get("business_id") or event_doc.get("tenant_id") or ""
    session = event_doc.get("session_id") or ""
    if not bin_id or not session:
        return
    if event_doc.get("event") not in ("page_view", "scroll_depth", "click"):
        return
    score_increment = {
        "page_view": 1,
        "scroll_depth": 2,
        "click": 3,
    }.get(event_doc.get("event"), 1)
    try:
        await db.visitor_intel.update_one(
            {"business_id": bin_id, "session_id": session},
            {"$inc": {"lead_score": score_increment, "events_count": 1},
             "$set": {"last_seen_at": _now_iso(),
                      "last_url": event_doc.get("url", "")},
             "$setOnInsert": {"first_seen_at": _now_iso()}},
            upsert=True,
        )
    except Exception as e:
        logger.debug(f"[visitor_intel] upsert failed: {e}")


async def form_capture_agent(db, event_doc: Dict[str, Any]) -> None:
    """Form submissions → campaign_leads with full intent payload."""
    if db is None or not event_doc:
        return
    if event_doc.get("event") != "form_submit":
        return
    bin_id = event_doc.get("business_id") or event_doc.get("tenant_id") or ""
    if not bin_id:
        return
    data = event_doc.get("data") or {}
    email = (data.get("email") or "").strip().lower()
    if not email:
        return
    try:
        await db.campaign_leads.update_one(
            {"business_id": bin_id, "email": email},
            {"$set": {
                "business_id": bin_id, "email": email,
                "source": "pixel_form_submit",
                "last_form_url": event_doc.get("url", ""),
                "last_session_id": event_doc.get("session_id", ""),
                "data": data,
                "updated_at": _now_iso(),
            }, "$setOnInsert": {"created_at": _now_iso(), "status": "new"},
             "$inc": {"form_submit_count": 1}},
            upsert=True,
        )
    except Exception as e:
        logger.debug(f"[form_capture] upsert failed: {e}")


async def error_healer_agent(db, event_doc: Dict[str, Any]) -> None:
    """Pixel error events → forwards into the existing client_errors
    pipeline so sentinel_repair_loop picks them up automatically."""
    if db is None or not event_doc:
        return
    if event_doc.get("event") != "error":
        return
    bin_id = event_doc.get("business_id") or event_doc.get("tenant_id") or ""
    data = event_doc.get("data") or {}
    try:
        await db.client_errors.insert_one({
            "business_id": bin_id,
            "ts": _now_iso(),
            "type": "pixel_error",
            "classification": "pixel_event",
            "ai_eligible": True,
            "status": "new",
            "message": (data.get("message") or "")[:500],
            "url": event_doc.get("url", ""),
            "stack": (data.get("stack") or "")[:1500],
            "session_id": event_doc.get("session_id", ""),
        })
    except Exception as e:
        logger.debug(f"[error_healer] insert failed: {e}")


async def fan_out(db, event_doc: Dict[str, Any]) -> None:
    """Single entrypoint — call from the pixel ingest after writing the
    main pixel_events row. Each agent is fire-and-forget; failures are
    logged but never bubble."""
    try:
        await visitor_intel_agent(db, event_doc)
    except Exception:
        pass
    try:
        await form_capture_agent(db, event_doc)
    except Exception:
        pass
    try:
        await error_healer_agent(db, event_doc)
    except Exception:
        pass
