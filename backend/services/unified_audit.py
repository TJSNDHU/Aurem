"""
services/unified_audit.py — iter 332b Batch A (Fix 2)

Single source of truth for ALL audit events across AUREM. Wraps the
five legacy collections (audit_log, customer_audit_log, self_audit_log,
catalog_audit_log, ora_tool_audit) behind one consistent API.

Schema (`db.unified_audit_log`):
  {
    event_id:           UUID4 hex
    timestamp:          ISO-8601 UTC
    user_id:            str | None
    org_id:             str | None       (kept None until org entity ships)
    action:             "tool_invoke" | "deploy" | "login" | "config_change" | ...
    resource:           short string identifying what was touched
    result:             "ok" | "fail" | "blocked"
    ip_address:         str | None
    user_agent:         str | None
    source_collection:  which legacy collection this row was minted from
    extra:              dict — anything else the caller wants to record
  }

Two public surfaces:
  • async write_event(...) — append a row, fire-and-forget safe
  • async query_events(filters, limit, offset) — paginated read
  • async export_events_csv(filters) — CSV string for auditors
"""
from __future__ import annotations

import csv
import io
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

_db = None


def set_db(database) -> None:
    global _db
    _db = database


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def write_event(
    *,
    action: str,
    resource: str = "",
    result: str = "ok",
    user_id: Optional[str] = None,
    org_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    source_collection: str = "unified_audit_log",
    extra: Optional[dict] = None,
) -> dict[str, Any]:
    """Append one row. Returns {ok, event_id}. Never raises — callers
    should be able to call this without try/except blocks of their own."""
    if _db is None:
        return {"ok": False, "error": "db not ready"}
    if result not in ("ok", "fail", "blocked"):
        result = "fail"
    row = {
        "event_id":          uuid.uuid4().hex,
        "timestamp":         _now_iso(),
        "user_id":           user_id,
        "org_id":            org_id,
        "action":            (action or "unknown")[:80],
        "resource":          (resource or "")[:200],
        "result":            result,
        "ip_address":        ip_address,
        "user_agent":        (user_agent or "")[:200] if user_agent else None,
        "source_collection": source_collection,
        "extra":             {},   # populated below if caller passed one
    }
    # Defensive trim of extra dict (max 50 keys)
    if isinstance(extra, dict):
        row["extra"] = {k: v for k, v in list(extra.items())[:50]}
    try:
        await _db.unified_audit_log.insert_one(row)
        return {"ok": True, "event_id": row["event_id"]}
    except Exception as e:
        logger.warning(f"[unified-audit] write failed: {e}")
        return {"ok": False, "error": str(e)[:120]}


async def query_events(
    *,
    user_id: Optional[str] = None,
    action: Optional[str] = None,
    resource: Optional[str] = None,
    result: Optional[str] = None,
    source_collection: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    """Paginated query against unified_audit_log. All filters optional."""
    if _db is None:
        return {"ok": False, "rows": [], "total": 0}
    q: dict[str, Any] = {}
    if user_id:
        q["user_id"] = user_id
    if action:
        q["action"] = action
    if resource:
        q["resource"] = resource
    if result:
        q["result"] = result
    if source_collection:
        q["source_collection"] = source_collection
    if date_from or date_to:
        rng: dict[str, Any] = {}
        if date_from:
            rng["$gte"] = date_from
        if date_to:
            rng["$lte"] = date_to
        q["timestamp"] = rng
    limit  = max(1, min(int(limit or 100), 1000))
    offset = max(0, int(offset or 0))
    cursor = _db.unified_audit_log.find(q, {"_id": 0}) \
                  .sort("timestamp", -1).skip(offset).limit(limit)
    rows = await cursor.to_list(length=limit)
    total = await _db.unified_audit_log.count_documents(q)
    return {"ok": True, "rows": rows, "total": total,
             "limit": limit, "offset": offset}


async def export_events_csv(**filters: Any) -> str:
    """Returns a CSV string for auditors. Honors the same filters as
    query_events but lifts the row cap to 10k."""
    filters["limit"]  = min(int(filters.get("limit") or 10000), 10000)
    filters["offset"] = 0
    r = await query_events(**filters)
    rows = r.get("rows", [])
    buf = io.StringIO()
    fields = ["event_id", "timestamp", "user_id", "org_id",
              "action", "resource", "result",
              "ip_address", "user_agent", "source_collection"]
    w = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    w.writeheader()
    for row in rows:
        # Flatten any nested 'extra' so it doesn't break CSV
        row = {**row}
        row.pop("extra", None)
        w.writerow(row)
    return buf.getvalue()


__all__ = [
    "set_db",
    "write_event", "query_events", "export_events_csv",
]
