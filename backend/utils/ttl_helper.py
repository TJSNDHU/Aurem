"""
TTL helper — Iteration 206
Ensures any document targeted for TTL auto-cleanup has a `ttl_at` BSON Date
field. Safe to sprinkle on inserts: additive, never removes anything.

Usage:
    from utils.ttl_helper import with_ttl
    doc = with_ttl(doc)  # adds ttl_at = datetime.now(tz.utc) if missing
    await db.pixel_events.insert_one(doc)
"""
from datetime import datetime, timezone
from typing import Dict, Any


def with_ttl(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Return the same dict with `ttl_at` set to now() if not already present."""
    if "ttl_at" not in doc:
        doc["ttl_at"] = datetime.now(timezone.utc)
    return doc
