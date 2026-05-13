"""
incident_bus.py — Single ingestion bus for AUREM incidents (iter 322ff).

Every error, anomaly, or anomaly-suspect event from frontend / backend /
middleware / ORA tools flows through THIS module. Nothing else writes to
`incident_ledger` directly.

Responsibilities:
  • Hash-based deduplication (5-minute window) so a 502 storm = 1 incident
  • Severity & category normalization (P0..P3)
  • Mongo persistence to `incident_ledger`
  • Fingerprint library `incident_fingerprints` (learning loop)
  • Telegram alerts for P0 (best-effort)

Honest design notes (no theater):
  - This file is the BUS. The TRIAGE BRAIN and FIX PLAYBOOKS live in
    `triage_brain.py` and `incident_playbooks.py`. This module never
    LLM-calls; it ingests, dedups, persists, and returns the row.
  - Fingerprint = sha1(category + signature). `signature` is the
    caller's stable identifier (e.g. "frontend_crash:OraChat.jsx:safeJson").
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)

_db = None
LEDGER = "incident_ledger"
FINGERPRINTS = "incident_fingerprints"

DEDUP_WINDOW_S = 300  # 5 minutes

# Canonical category set (also accepted by API)
CATEGORIES = {
    "transient_502",
    "timeout",
    "backend_5xx",
    "frontend_crash",
    "frontend_unhandled_rejection",
    "tool_exception",
    "route_missing",
    "db_conn",
    "dependency_missing",
    "permission_denied",
    "legion_disconnect",
    "ghost_blocked",
    "council_stuck",
    "rate_limit_hit",
    "build_error",
    "unknown",
}

# Severity scale
SEVERITIES = {"P0", "P1", "P2", "P3"}


def set_db(database) -> None:
    global _db
    _db = database


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _hash_fingerprint(category: str, signature: str) -> str:
    payload = f"{category}|{signature or ''}".encode("utf-8", "ignore")
    return hashlib.sha1(payload).hexdigest()[:16]


def _normalise(category: str, severity: str | None) -> tuple[str, str]:
    cat = (category or "unknown").strip().lower()
    if cat not in CATEGORIES:
        cat = "unknown"
    sev = (severity or "P2").upper()
    if sev not in SEVERITIES:
        sev = "P2"
    return cat, sev


async def report(
    *,
    category: str,
    signature: str,
    severity: str | None = None,
    source: str = "unknown",
    title: str = "",
    detail: str = "",
    metadata: dict | None = None,
    customer_id: str | None = None,
    actor: str = "system",
) -> dict[str, Any]:
    """Ingest an incident. Returns the row.

    Dedup behavior: if an incident with the same fingerprint exists in
    `incident_ledger` with `status in {open, triaged, fixing}` and was
    created within DEDUP_WINDOW_S, increment `occurrences` and update
    `last_seen` instead of creating a new row.
    """
    if _db is None:
        return {"ok": False, "error": "incident_bus DB not set"}

    cat, sev = _normalise(category, severity)
    sig = (signature or "")[:240]
    fp = _hash_fingerprint(cat, sig)
    now = _now()
    cutoff = now - timedelta(seconds=DEDUP_WINDOW_S)

    # Dedup query
    existing = await _db[LEDGER].find_one(
        {
            "fingerprint": fp,
            "status": {"$in": ["open", "triaged", "fixing"]},
            "last_seen": {"$gte": cutoff},
        },
        sort=[("last_seen", -1)],
    )

    if existing:
        await _db[LEDGER].update_one(
            {"incident_id": existing["incident_id"]},
            {
                "$inc": {"occurrences": 1},
                "$set": {
                    "last_seen": now,
                    "last_detail": (detail or "")[:2000],
                },
            },
        )
        existing.pop("_id", None)
        existing["occurrences"] = int(existing.get("occurrences", 1)) + 1
        existing["last_seen"] = now.isoformat()
        existing["deduped"] = True
        return {"ok": True, **existing}

    incident_id = f"INC-{now.strftime('%Y%m%d')}-{uuid4().hex[:6].upper()}"
    row: dict[str, Any] = {
        "incident_id":  incident_id,
        "fingerprint":  fp,
        "category":     cat,
        "severity":     sev,
        "source":       source[:80],
        "signature":    sig,
        "title":        (title or sig or cat)[:240],
        "detail":       (detail or "")[:4000],
        "last_detail":  (detail or "")[:2000],
        "metadata":     metadata or {},
        "customer_id":  customer_id,
        "actor":        actor[:80],
        "occurrences":  1,
        "status":       "open",        # open → triaged → fixing → resolved | escalated
        "auto_fixable": None,           # filled by triage
        "playbook":     None,           # filled by triage
        "fix_steps":    [],             # appended by playbook execution
        "created_at":   now,
        "last_seen":    now,
        "resolved_at":  None,
        "mttr_ms":      None,
    }
    await _db[LEDGER].insert_one(row)
    row.pop("_id", None)

    # Update fingerprint library counters (learning loop)
    await _db[FINGERPRINTS].update_one(
        {"_id": fp},
        {
            "$set":  {"category": cat, "signature": sig, "last_seen": now},
            "$inc":  {"total_count": 1},
            "$setOnInsert": {"first_seen": now, "known_playbook": None},
        },
        upsert=True,
    )

    # P0 fire-and-forget Telegram alert (best-effort, never blocks ingest)
    if sev == "P0":
        asyncio.create_task(_send_p0_alert(row))

    row["created_at"] = now.isoformat()
    row["last_seen"]  = now.isoformat()
    return {"ok": True, **row}


async def get(incident_id: str) -> dict[str, Any]:
    if _db is None:
        return {"ok": False, "error": "DB not set"}
    doc = await _db[LEDGER].find_one({"incident_id": incident_id}, {"_id": 0})
    if not doc:
        return {"ok": False, "error": "not found"}
    for k in ("created_at", "last_seen", "resolved_at"):
        if isinstance(doc.get(k), datetime):
            doc[k] = doc[k].isoformat()
    return {"ok": True, **doc}


async def list_recent(
    *,
    limit: int = 50,
    status: str | None = None,
    severity: str | None = None,
    category: str | None = None,
    since_hours: int | None = None,
) -> dict[str, Any]:
    if _db is None:
        return {"ok": False, "error": "DB not set", "rows": []}
    q: dict[str, Any] = {}
    if status:
        q["status"] = status
    if severity:
        q["severity"] = severity
    if category:
        q["category"] = category
    if since_hours:
        q["last_seen"] = {"$gte": _now() - timedelta(hours=since_hours)}
    cursor = _db[LEDGER].find(q, {"_id": 0}).sort([("last_seen", -1)]).limit(max(1, min(limit, 200)))
    rows: list[dict[str, Any]] = []
    async for d in cursor:
        for k in ("created_at", "last_seen", "resolved_at"):
            if isinstance(d.get(k), datetime):
                d[k] = d[k].isoformat()
        rows.append(d)
    return {"ok": True, "rows": rows, "count": len(rows)}


async def update_status(
    incident_id: str,
    *,
    status: str,
    playbook: str | None = None,
    fix_step: dict | None = None,
    auto_fixable: bool | None = None,
    triage_summary: dict | None = None,
) -> dict[str, Any]:
    if _db is None:
        return {"ok": False, "error": "DB not set"}
    if status not in ("open", "triaged", "fixing", "resolved", "escalated"):
        return {"ok": False, "error": f"bad status: {status}"}
    set_fields: dict[str, Any] = {"status": status}
    if playbook is not None:
        set_fields["playbook"] = playbook
    if auto_fixable is not None:
        set_fields["auto_fixable"] = bool(auto_fixable)
    if triage_summary is not None:
        set_fields["triage_summary"] = triage_summary
    if status == "resolved":
        doc = await _db[LEDGER].find_one({"incident_id": incident_id}, {"created_at": 1, "_id": 0})
        now = _now()
        set_fields["resolved_at"] = now
        if doc and doc.get("created_at"):
            try:
                ca = doc["created_at"]
                if isinstance(ca, str):
                    ca = datetime.fromisoformat(ca.replace("Z", "+00:00"))
                # Motor returns naive datetimes from Mongo — normalise to UTC
                if isinstance(ca, datetime) and ca.tzinfo is None:
                    ca = ca.replace(tzinfo=timezone.utc)
                set_fields["mttr_ms"] = int((now - ca).total_seconds() * 1000)
            except Exception as _mttr_err:
                logger.debug(f"[incident_bus] mttr calc failed: {_mttr_err}")

    update: dict[str, Any] = {"$set": set_fields}
    if fix_step is not None:
        update["$push"] = {"fix_steps": {**fix_step, "ts": _now()}}

    res = await _db[LEDGER].update_one({"incident_id": incident_id}, update)
    if res.matched_count == 0:
        return {"ok": False, "error": "not found"}
    return await get(incident_id)


async def fingerprint_stats() -> dict[str, Any]:
    """Top recurring fingerprints — the learning library."""
    if _db is None:
        return {"ok": False, "error": "DB not set", "rows": []}
    cursor = _db[FINGERPRINTS].find({}, {"_id": 1, "category": 1, "signature": 1,
                                          "total_count": 1, "known_playbook": 1,
                                          "first_seen": 1, "last_seen": 1}
                                     ).sort([("total_count", -1)]).limit(50)
    rows: list[dict[str, Any]] = []
    async for d in cursor:
        d["fingerprint"] = d.pop("_id")
        for k in ("first_seen", "last_seen"):
            if isinstance(d.get(k), datetime):
                d[k] = d[k].isoformat()
        rows.append(d)
    return {"ok": True, "rows": rows, "count": len(rows)}


async def _send_p0_alert(row: dict[str, Any]) -> None:
    """Best-effort Telegram P0 alert — never raises."""
    bot = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not bot or not chat:
        return
    try:
        import httpx
        msg = (
            f"🚨 *AUREM P0 incident*\n"
            f"`{row['incident_id']}`\n"
            f"*{row['category']}* · {row['source']}\n"
            f"{(row.get('title') or '')[:200]}\n"
            f"_{(row.get('detail') or '')[:240]}_"
        )
        url = f"https://api.telegram.org/bot{bot}/sendMessage"
        async with httpx.AsyncClient(timeout=8.0) as c:
            await c.post(url, json={
                "chat_id": chat, "text": msg, "parse_mode": "Markdown",
                "disable_web_page_preview": True,
            })
    except Exception as e:
        logger.debug(f"[incident_bus] P0 alert failed: {e}")
