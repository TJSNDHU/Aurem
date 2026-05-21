"""
ensure_audit_log_ttl.py — iter 326h
═══════════════════════════════════════════════════════════════════════════
Idempotent TTL setup for high-volume audit log collections.

PROBLEM SOLVED
──────────────
DB scan (iter 326h) found `api_audit_log` had grown to **1,394,963 rows**
spanning 42 days (oldest: 2026-04-09). An existing TTL index `ts_ttl_35d`
was indexing the WRONG field (`ts` — the actual timestamp field is
`timestamp`), so Mongo's TTL monitor silently never expired anything.

FIX
───
1. Drop the broken `ts_ttl_35d` index (wrong field, never fired).
2. Create `ttl_timestamp_7d` TTL index on the `timestamp` field with
   `expireAfterSeconds = 604800` (7 days). Mongo's background TTL
   monitor will start expiring old rows within 60 seconds.

Run on every backend startup. `create_index` is idempotent — Mongo no-ops
if the index already exists with identical specs. We catch the
`OperationFailure` raised when an index with the same name but different
options exists (operator may want to tune retention) and just log it.
"""
from __future__ import annotations

import logging
from typing import Any

from pymongo import ASCENDING
from pymongo.errors import OperationFailure

logger = logging.getLogger(__name__)

# 7 days. Founder explicitly requested this retention window.
_TTL_SECONDS_7D = 7 * 24 * 60 * 60  # 604800

# (collection, field, expireAfterSeconds, index_name)
_TTL_SPECS: list[tuple[str, str, int, str]] = [
    ("api_audit_log", "timestamp", _TTL_SECONDS_7D, "ttl_timestamp_7d"),
]


async def ensure_audit_log_ttl(db) -> dict[str, Any]:
    """Idempotently install retention TTLs.

    Returns a per-collection summary:
      {
        "ok": True,
        "results": {
          "api_audit_log": {
            "dropped_broken_indexes": ["ts_ttl_35d"],
            "created":  "ttl_timestamp_7d",
            "field":    "timestamp",
            "ttl_seconds": 604800,
          }
        }
      }
    """
    if db is None:
        return {"ok": False, "reason": "db_unavailable"}

    results: dict[str, Any] = {}
    for coll_name, field, ttl_seconds, index_name in _TTL_SPECS:
        coll = db[coll_name]
        entry: dict[str, Any] = {
            "field":        field,
            "ttl_seconds":  ttl_seconds,
            "dropped_broken_indexes": [],
            "created":      None,
            "already_exists": False,
            "error":        None,
        }
        # ── Step 1: drop any *broken* TTL index on this collection.
        # A TTL index whose key field is NOT the one we expect is dead
        # weight — it never matches and never fires. Drop it so the
        # collection has exactly one functional TTL.
        try:
            info = await coll.index_information()
            for name, meta in info.items():
                if "expireAfterSeconds" not in meta:
                    continue
                # Single-field index spec is [(field, 1)]
                keyspec = meta.get("key") or []
                if not keyspec:
                    continue
                indexed_field = keyspec[0][0]
                if indexed_field != field and name != "_id_":
                    try:
                        await coll.drop_index(name)
                        entry["dropped_broken_indexes"].append(name)
                        logger.info(
                            f"[audit-ttl] dropped broken TTL index "
                            f"{coll_name}.{name} (was on {indexed_field!r}, "
                            f"expected {field!r})"
                        )
                    except OperationFailure as e:
                        logger.warning(
                            f"[audit-ttl] could not drop {coll_name}.{name}: {e}"
                        )
        except Exception as e:
            entry["error"] = f"index_info_failed:{type(e).__name__}:{str(e)[:120]}"
            results[coll_name] = entry
            continue

        # ── Step 2: create the correct TTL index (idempotent).
        try:
            await coll.create_index(
                [(field, ASCENDING)],
                expireAfterSeconds=ttl_seconds,
                name=index_name,
                background=True,
            )
            entry["created"] = index_name
            logger.info(
                f"[audit-ttl] ensured {coll_name}.{index_name} "
                f"on {field!r} TTL={ttl_seconds}s ({ttl_seconds//86400}d)"
            )
        except OperationFailure as e:
            # Index already exists with conflicting options — preserve
            # operator's choice and just log.
            msg = str(e)
            if "already exists" in msg.lower() or "IndexOptionsConflict" in msg:
                entry["already_exists"] = True
                logger.info(
                    f"[audit-ttl] {coll_name}.{index_name} already exists "
                    "with different options — preserving operator override"
                )
            else:
                entry["error"] = f"create_index_failed:{str(e)[:160]}"

        results[coll_name] = entry

    return {"ok": True, "results": results}
