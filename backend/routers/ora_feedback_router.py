"""
routers/ora_feedback_router.py — iter 329d

Per-reply thumbs-up/down feedback for the ORA chat UI.

  POST /api/ora/feedback
      body: { session_id, message_id, rating, reason? }
      rating ∈ {"up", "down"}
      reason ∈ {"wrong_number","wrong_action","didnt_understand",
                "technical_jargon","other"}  — required when rating=down
      → 200 {ok: true, stored: true}

  GET  /api/admin/ora/feedback/summary?days=7  (admin-only)
      → { window_days, up, down, by_reason: {...} }
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(tags=["ora-feedback"])

_db = None


def set_db(database):
    global _db
    _db = database


def _admin_dep():
    from routers.ora_agent_router import get_admin_user
    return get_admin_user


_VALID_RATINGS = {"up", "down"}
_VALID_REASONS = {
    "wrong_number", "wrong_action", "didnt_understand",
    "technical_jargon", "other",
}


class FeedbackBody(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)
    message_id: str = Field(min_length=1, max_length=128)
    rating:     str = Field(min_length=1, max_length=16)
    reason:     str = Field(default="", max_length=64)
    comment:    str = Field(default="", max_length=500)


@router.post("/api/ora/feedback")
async def submit_feedback(body: FeedbackBody):
    if _db is None:
        raise HTTPException(503, "db not ready")
    if body.rating not in _VALID_RATINGS:
        raise HTTPException(400, f"rating must be one of {_VALID_RATINGS}")
    reason = body.reason or ""
    if body.rating == "down":
        if reason and reason not in _VALID_REASONS:
            raise HTTPException(400, f"reason must be one of {_VALID_REASONS}")
    # Idempotent on (session_id, message_id) — last write wins so the
    # founder can change their mind.
    doc = {
        "session_id": body.session_id,
        "message_id": body.message_id,
        "rating":     body.rating,
        "reason":     reason or None,
        "comment":    (body.comment or "")[:500],
        "ts":         datetime.now(timezone.utc),
    }
    await _db.ora_feedback.update_one(
        {"session_id": body.session_id, "message_id": body.message_id},
        {"$set": doc},
        upsert=True,
    )
    return {"ok": True, "stored": True, "rating": body.rating}


@router.get("/api/admin/ora/feedback/summary")
async def feedback_summary(days: int = 7,
                              user: dict = Depends(_admin_dep())):
    if _db is None:
        raise HTTPException(503, "db not ready")
    days = max(1, min(int(days or 7), 90))
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    up = await _db.ora_feedback.count_documents({
        "ts": {"$gte": cutoff}, "rating": "up",
    })
    down = await _db.ora_feedback.count_documents({
        "ts": {"$gte": cutoff}, "rating": "down",
    })
    by_reason: dict[str, int] = {}
    cur = _db.ora_feedback.find(
        {"ts": {"$gte": cutoff}, "rating": "down", "reason": {"$ne": None}},
        {"_id": 0, "reason": 1},
    ).limit(1000)
    async for r in cur:
        k = r.get("reason") or "other"
        by_reason[k] = by_reason.get(k, 0) + 1
    return {
        "ok":            True,
        "window_days":   days,
        "up":            up,
        "down":          down,
        "by_reason":     by_reason,
        "total":         up + down,
    }


async def weekly_feedback_summary(db) -> dict:
    """Used by morning brief (iter 329d). Returns the line text + raw counts."""
    if db is None:
        return {"line": "", "up": 0, "down": 0}
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    up = await db.ora_feedback.count_documents({
        "ts": {"$gte": cutoff}, "rating": "up",
    })
    down = await db.ora_feedback.count_documents({
        "ts": {"$gte": cutoff}, "rating": "down",
    })
    by_reason: dict[str, int] = {}
    cur = db.ora_feedback.find(
        {"ts": {"$gte": cutoff}, "rating": "down", "reason": {"$ne": None}},
        {"_id": 0, "reason": 1},
    ).limit(1000)
    async for r in cur:
        k = r.get("reason") or "other"
        by_reason[k] = by_reason.get(k, 0) + 1
    top_issue = ""
    if by_reason:
        name, count = max(by_reason.items(), key=lambda kv: kv[1])
        top_issue = f" Top issue: {name.replace('_', ' ')} ({count} time{'s' if count != 1 else ''})."
    line = (
        f"ORA FEEDBACK (7d): {up} 👍, {down} 👎.{top_issue}"
        if (up + down) else
        "ORA FEEDBACK (7d): no ratings yet."
    )
    return {"line": line, "up": up, "down": down, "by_reason": by_reason}
