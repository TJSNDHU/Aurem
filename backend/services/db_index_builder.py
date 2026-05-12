"""
DB Index Builder — Iteration 205 (Safe-Mode DB Optimization)
=============================================================
ADD-ONLY: creates MongoDB indexes if missing. Never drops or modifies
existing indexes. Runs at server startup (non-blocking, background=True).

Indexes are idempotent — create_index() is a no-op if identical index exists.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Tuple, Dict, Any

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════
# Plain indexes — pure speed-ups, zero risk
# ══════════════════════════════════════════════
# (collection, field_or_key, options)
PLAIN_INDEXES: List[Tuple[str, str, dict]] = [
    ("campaign_leads",       "slug",        {}),
    ("campaign_leads",       "tenant_id",   {}),
    ("campaign_leads",       "created_at",  {}),
    ("pixel_events",         "api_key",     {}),
    ("touchpoints",          "lead_id",     {}),
    ("touchpoints",          "tenant_id",   {}),
    # iter 322ee — lifecycle_history was auto-resurrecting empty;
    # services/lead_lifecycle.transition() writes to lead_lifecycle_events
    # (the live collection) not lifecycle_history. Re-add if/when a writer
    # for lifecycle_history exists.
    ("system_auto_repairs",  "tenant_id",   {}),
    ("scan_history",         "tenant_id",   {}),
    ("aurem_live_viewers",   "slug",        {}),
    ("aurem_workspaces",     "tenant_id",   {}),
    ("platform_users",       "bin",         {}),
    ("platform_users",       "email",       {}),
]


# ══════════════════════════════════════════════
# TTL indexes — auto-cleanup of old records
# ══════════════════════════════════════════════
# CRITICAL: TTL requires a BSON Date field, not an ISO string. AUREM legacy
# code writes `created_at` as ISO strings, so those TTL indexes silently no-op.
# To make TTL actually work, we index a dedicated `ttl_at` (datetime) field.
# Every ingest path that wants auto-expiry must set `ttl_at = datetime.now(tz.utc)`.
TTL_INDEXES: List[Tuple[str, str, int]] = [
    ("pixel_events",        "ttl_at", 7776000),   # 90 days
    ("flame_alerts_log",    "ttl_at", 2592000),   # 30 days
    ("fallback_usage_log",  "ttl_at", 2592000),   # 30 days
    ("patch_reports",       "ttl_at", 2592000),   # 30 days
    ("ora_command_log",     "ttl_at", 5184000),   # 60 days
]


async def build_all_indexes(db) -> Dict[str, Any]:
    """Idempotently add every index. Safe to call on every startup."""
    started = datetime.now(timezone.utc)
    results = {"plain": [], "ttl": [], "errors": []}

    # Plain indexes
    for coll, field, opts in PLAIN_INDEXES:
        try:
            name = await db[coll].create_index(field, background=True, **opts)
            results["plain"].append({"collection": coll, "field": field, "name": name})
        except Exception as e:
            logger.warning(f"[IndexBuilder] plain {coll}.{field} failed: {e}")
            results["errors"].append({"collection": coll, "field": field, "error": str(e)[:200]})

    # TTL indexes
    for coll, field, secs in TTL_INDEXES:
        try:
            name = await db[coll].create_index(
                field, background=True, expireAfterSeconds=secs,
                name=f"{field}_ttl_{secs}",
            )
            results["ttl"].append({"collection": coll, "field": field, "expireAfterSeconds": secs, "name": name})
        except Exception as e:
            # If an index on this field already exists without TTL, Mongo refuses to
            # convert it. That's fine — we don't modify existing indexes (safe-mode).
            logger.info(f"[IndexBuilder] ttl {coll}.{field} skipped (likely existing plain index): {e}")
            results["errors"].append({"collection": coll, "field": field, "ttl": True, "error": str(e)[:200]})

    elapsed_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
    logger.info(
        f"[IndexBuilder] completed in {elapsed_ms}ms — "
        f"{len(results['plain'])} plain + {len(results['ttl'])} ttl + {len(results['errors'])} errors/skipped"
    )
    return {
        "ran_at": started.isoformat(),
        "elapsed_ms": elapsed_ms,
        "plain_count": len(results["plain"]),
        "ttl_count": len(results["ttl"]),
        "skipped_count": len(results["errors"]),
        **results,
    }
