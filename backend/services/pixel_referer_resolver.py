"""
services/pixel_referer_resolver.py — iter 330c

When a pixel webhook arrives without a `tenant_id` AND without a
valid API key, we used to dump it into `unmatched_pixel_events`. The
founder now has a UI to map each unknown referer → tenant once; from
that moment forward, every future pixel from that referer auto-
resolves to the chosen tenant.

Storage
───────
Collection `pixel_referer_map`:
  {
    "_id": <referer_host>,        # e.g. "shop.example.ca"
    "tenant_id": "<tenant_id>",
    "linked_by": "<email>",
    "linked_at": <utc datetime>,
  }

Resolution
──────────
`resolve_tenant_from_referer(db, referer_header)` returns the tenant_id
or None. We key on the *host* of the referer to be tolerant of path
differences (`/` vs `/checkout` are the same tenant). Falls back to the
full referer string when host extraction fails.
"""
from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlparse


def _host_of(referer: str | None) -> str | None:
    if not referer:
        return None
    try:
        host = urlparse(referer).hostname
        return host.lower() if host else referer.lower()[:120]
    except Exception:
        return referer.lower()[:120]


async def resolve_tenant_from_referer(db, referer: str | None) -> str | None:
    """Return the mapped tenant_id, or None when no mapping exists."""
    if db is None:
        return None
    host = _host_of(referer)
    if not host:
        return None
    try:
        row = await db.pixel_referer_map.find_one({"_id": host})
    except Exception:
        return None
    return (row or {}).get("tenant_id")


async def link_referer_to_tenant(
    db, *, referer: str, tenant_id: str, linked_by: str = "founder",
) -> dict:
    if db is None:
        return {"ok": False, "error": "db not ready"}
    host = _host_of(referer)
    if not host:
        return {"ok": False, "error": "no referer host parseable"}
    if not tenant_id:
        return {"ok": False, "error": "tenant_id required"}
    # Confirm tenant exists (cheap sanity check).
    try:
        exists = await db.tenants.find_one({"bin_id": tenant_id}, {"_id": 0, "bin_id": 1})
        if not exists:
            return {"ok": False, "error": f"tenant {tenant_id} not found in `tenants`"}
    except Exception:
        pass
    await db.pixel_referer_map.update_one(
        {"_id": host},
        {"$set": {
            "tenant_id":  tenant_id,
            "linked_by":  linked_by,
            "linked_at":  datetime.now(timezone.utc),
            "referer":    referer[:300],
        }},
        upsert=True,
    )
    # Best-effort: also re-claim any past unmatched rows from the same
    # host so the audit log reflects the new mapping.
    try:
        await db.unmatched_pixel_events.update_many(
            {"referer": {"$regex": host.replace(".", r"\.")}},
            {"$set": {"resolved_tenant_id": tenant_id, "resolved_at": datetime.now(timezone.utc)}},
        )
    except Exception:
        pass
    return {"ok": True, "host": host, "tenant_id": tenant_id}
