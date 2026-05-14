"""
AUREM Council Backlog Manager — Phase 2
=========================================
Endpoints:
  POST /api/admin/council/clear-backlog
       Mass-stamp every pending learning that's been there for >1 day with
       a `council_admin` approve stamp (idempotent — won't double-stamp).
       Then promote every learning that meets REQUIRED_STAMPS.

  POST /api/admin/council/auto-promote
       Promote every pending learning where:
         pending > N days  AND
         confidence >= MIN_CONFIDENCE  AND
         times_seen >= MIN_SEEN
       (Defaults: 5 days, 0.8, 3)
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List

import jwt
from fastapi import APIRouter, HTTPException, Request

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/council", tags=["admin-council"])

_db = None


def set_db(database) -> None:
    global _db
    _db = database


def _require_admin(request: Request) -> None:
    auth = request.headers.get("Authorization", "")
    token = auth[7:] if auth.startswith("Bearer ") else ""
    if not token:
        raise HTTPException(401, "Auth required")
    try:
        payload = jwt.decode(
            token,
            (os.environ.get("JWT_SECRET") or (_ for _ in ()).throw(__import__("fastapi").HTTPException(status_code=500, detail="JWT not configured"))),
            algorithms=["HS256"],
        )
    except Exception:
        raise HTTPException(401, "Invalid token")
    if not (payload.get("is_admin") or payload.get("is_super_admin")
            or payload.get("role") in ("admin", "super_admin", "founder")):
        raise HTTPException(403, "Admin required")


@router.post("/clear-backlog")
async def clear_backlog(request: Request) -> Dict[str, Any]:
    """Stamp every pending learning older than `min_age_hours` (default 1h)
    with `council_admin` + `auto_promoter` approve, then promote whatever
    now meets the REQUIRED_STAMPS bar.

    Body (optional): `{"min_age_hours": 1, "max_rows": 2000}`

    Robust to legacy schema variants where rows lack `submitted_at`/`id`/
    `submitted_by`. Backfills missing keys before promotion."""
    _require_admin(request)
    if _db is None:
        raise HTTPException(503, "database unavailable")

    body: Dict[str, Any] = {}
    try:
        body = await request.json()
    except Exception:
        pass
    min_age_hours = float(body.get("min_age_hours", 1))
    max_rows = int(body.get("max_rows", 2000))

    cutoff = (datetime.now(timezone.utc) - timedelta(hours=min_age_hours)).isoformat()
    # Match rows whose submitted_at OR ts is older than cutoff
    rows: List[Dict[str, Any]] = await _db.learnings_pending_review.find(
        {
            "status": "pending",
            "$or": [
                {"submitted_at": {"$lte": cutoff}},
                {"ts": {"$lte": cutoff}},
            ],
        },
        {"id": 1, "stamps": 1, "_id": 1, "ts": 1, "submitted_at": 1,
         "kind": 1, "submitted_by": 1},
    ).limit(max_rows).to_list(max_rows)

    if not rows:
        return {"ok": True, "stamped": 0, "promoted": 0, "scanned": 0,
                "min_age_hours": min_age_hours}

    # Backfill missing `id`, `submitted_at`, `submitted_by` so promote_if_ready works
    import uuid as _uuid
    for r in rows:
        updates: Dict[str, Any] = {}
        if not r.get("id"):
            updates["id"] = (
                f"{r.get('kind', 'lrn')}-"
                f"{_uuid.uuid4().hex[:10]}"
            )
        if not r.get("submitted_at"):
            updates["submitted_at"] = r.get("ts") or datetime.now(timezone.utc).isoformat()
        if not r.get("submitted_by"):
            # Pull original submitter from first stamp role if present, else "system"
            stamps = r.get("stamps") or []
            updates["submitted_by"] = (
                (stamps[0].get("role") if stamps else None) or "system"
            )
        if updates:
            r.update(updates)
            await _db.learnings_pending_review.update_one(
                {"_id": r["_id"]}, {"$set": updates},
            )

    # Stamp two distinct-role approve stamps so they hit REQUIRED_STAMPS=2
    now_iso = datetime.now(timezone.utc).isoformat()
    new_stamps = [
        {"role": "council_admin", "vote": "approve",
         "ts": now_iso, "by": "clear-backlog"},
        {"role": "auto_promoter", "vote": "approve",
         "ts": now_iso, "by": "clear-backlog"},
    ]
    to_stamp_ids = []
    for r in rows:
        existing_roles = {
            s.get("role") for s in (r.get("stamps") or [])
            if s.get("vote") == "approve"
        }
        # Only stamp roles missing
        missing = [s for s in new_stamps if s["role"] not in existing_roles]
        if missing:
            await _db.learnings_pending_review.update_one(
                {"_id": r["_id"]},
                {"$push": {"stamps": {"$each": missing}}},
            )
            to_stamp_ids.append(r.get("id"))

    # Promote everything in parallel
    from services.sovereign_memory import promote_if_ready
    promote_results = await asyncio.gather(
        *[promote_if_ready(_db, r.get("id")) for r in rows if r.get("id")],
        return_exceptions=True,
    )
    promoted = sum(
        1 for r in promote_results
        if not isinstance(r, Exception) and r is not None
    )
    return {"ok": True, "scanned": len(rows),
            "stamped": len(to_stamp_ids), "promoted": promoted}


@router.post("/auto-promote")
async def auto_promote(request: Request) -> Dict[str, Any]:
    """Auto-promote rule (no manual ever): pending > N days
    AND confidence >= 0.8 AND times_seen >= 3."""
    _require_admin(request)
    if _db is None:
        raise HTTPException(503, "database unavailable")

    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    days = float(body.get("min_age_days", 5))
    min_conf = float(body.get("min_confidence", 0.8))
    min_seen = int(body.get("min_times_seen", 3))

    cutoff_iso = (
        datetime.now(timezone.utc) - timedelta(days=days)
    ).isoformat()

    rows = await _db.learnings_pending_review.find(
        {
            "status": "pending",
            "submitted_at": {"$lte": cutoff_iso},
            "confidence": {"$gte": min_conf},
        },
        {"id": 1, "stamps": 1, "_id": 0, "payload": 1},
    ).limit(500).to_list(500)

    # Filter by times_seen (lives in payload)
    candidates = [
        r for r in rows
        if int((r.get("payload") or {}).get("times_seen", 0)) >= min_seen
    ]
    if not candidates:
        return {"ok": True, "candidates": 0, "promoted": 0}

    # Stamp + promote (parallel)
    now_iso = datetime.now(timezone.utc).isoformat()
    auto_stamp = {"role": "auto_promoter", "vote": "approve",
                  "ts": now_iso, "by": "auto-promote"}
    ids = [r["id"] for r in candidates]
    await _db.learnings_pending_review.update_many(
        {"id": {"$in": ids}, "status": "pending"},
        {"$push": {"stamps": auto_stamp}},
    )

    from services.sovereign_memory import promote_if_ready
    results = await asyncio.gather(
        *[promote_if_ready(_db, lid) for lid in ids],
        return_exceptions=True,
    )
    promoted = sum(
        1 for r in results
        if not isinstance(r, Exception) and r is not None
    )
    return {"ok": True, "candidates": len(candidates), "promoted": promoted}


@router.get("/backlog-stats")
async def backlog_stats(request: Request) -> Dict[str, Any]:
    """Live counts of pending vs promoted (for ORA Morning Brief)."""
    _require_admin(request)
    if _db is None:
        raise HTTPException(503, "database unavailable")
    pending, promoted, rejected = await asyncio.gather(
        _db.learnings_pending_review.count_documents({"status": "pending"}),
        _db.learnings_pending_review.count_documents({"status": "promoted"}),
        _db.learnings_pending_review.count_documents({"status": "rejected"}),
    )
    return {
        "pending": pending, "promoted": promoted, "rejected": rejected,
    }
