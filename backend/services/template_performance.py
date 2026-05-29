"""
services/template_performance.py — iter D-58

Track per-template blast performance (sent / opened / clicked / replied)
+ weekly auto-iteration: promote the best template to default and
retire any with < 10 % open rate.

Storage:
  blast_performance — append-only per-event rows
    {template_id, event ("sent"|"opened"|"clicked"|"replied"),
     lead_id, email, ts, message_id}

Aggregations + the current default + retired list live in:
  blast_template_state — singleton row
    {default_template, retired:[…], last_rotated_at}

Hard rules:
  • A template needs ≥ 20 sent rows before it can be auto-rotated
    in or retired (avoid noise).
  • Retirement is reversible — we only mark `retired:true` in the
    state row; the template file itself is untouched.
  • The hand-picked founder default cannot be auto-retired (flagged
    via metadata field `founder_locked`).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any

logger = logging.getLogger(__name__)

_db = None
_MIN_SAMPLE = 20


def set_db(database) -> None:
    global _db
    _db = database


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def record_event(template_id: str, event: str,
                        lead_id: str = "", email: str = "",
                        message_id: str = "") -> None:
    """Append-only event log. Called by the blast engine + Resend
    webhook (`email.opened` / `email.clicked`) + reply webhook."""
    if _db is None or not template_id:
        return
    valid_events = ("sent", "opened", "clicked", "replied")
    if event not in valid_events:
        logger.warning(f"[tpl-perf] dropping bad event {event!r}")
        return
    await _db.blast_performance.insert_one({
        "template_id": template_id,
        "event":       event,
        "lead_id":     lead_id,
        "email":       email,
        "message_id":  message_id,
        "ts":          _now(),
    })


async def stats_for(template_id: str | None = None,
                     window_days: int = 30
                     ) -> list[dict[str, Any]]:
    """Aggregate per-template metrics over the last `window_days`."""
    if _db is None:
        return []
    since = (datetime.now(timezone.utc)
              - timedelta(days=window_days)).isoformat()
    match: dict[str, Any] = {"ts": {"$gte": since}}
    if template_id:
        match["template_id"] = template_id
    pipe = [
        {"$match":  match},
        {"$group":  {
            "_id":      {"template_id": "$template_id", "event": "$event"},
            "n":        {"$sum": 1},
        }},
    ]
    counts: dict[str, dict[str, int]] = {}
    async for d in _db.blast_performance.aggregate(pipe):
        tid = d["_id"]["template_id"]
        ev  = d["_id"]["event"]
        counts.setdefault(tid, {})[ev] = d["n"]
    out: list[dict[str, Any]] = []
    for tid, ev in counts.items():
        sent    = ev.get("sent",    0)
        opened  = ev.get("opened",  0)
        clicked = ev.get("clicked", 0)
        replied = ev.get("replied", 0)
        out.append({
            "template_id":   tid,
            "sent":          sent,
            "opened":        opened,
            "clicked":       clicked,
            "replied":       replied,
            "open_rate":     (opened / sent) if sent else 0.0,
            "click_rate":    (clicked / sent) if sent else 0.0,
            "reply_rate":    (replied / sent) if sent else 0.0,
            "sample_ready":  sent >= _MIN_SAMPLE,
            "window_days":   window_days,
        })
    out.sort(key=lambda r: (r["sample_ready"], r["open_rate"], r["sent"]),
              reverse=True)
    return out


async def current_state() -> dict[str, Any]:
    if _db is None:
        return {}
    return await _db.blast_template_state.find_one(
        {"_id": "global"}, {"_id": 0},
    ) or {}


async def weekly_rotate() -> dict[str, Any]:
    """Called every Sunday 03:00 UTC. Picks the highest open_rate
    template with at least `_MIN_SAMPLE` sends + retires anything
    below 10 % open rate."""
    rows = await stats_for(window_days=14)
    ready = [r for r in rows if r["sample_ready"]]
    promoted = ""
    retired:  list[str] = []
    if ready:
        promoted = ready[0]["template_id"]
    for r in rows:
        if r["sample_ready"] and r["open_rate"] < 0.10:
            retired.append(r["template_id"])

    state = await current_state()
    founder_locked = (state.get("founder_locked") or [])
    # Never auto-retire founder-locked.
    retired = [t for t in retired if t not in founder_locked]

    new_state = {
        "default_template": promoted or state.get("default_template", ""),
        "retired":          sorted(set(state.get("retired", []) + retired)),
        "last_rotated_at":  _now(),
        "founder_locked":   founder_locked,
        "considered":       [r["template_id"] for r in rows],
        "winner_metrics":   ready[0] if ready else {},
    }
    if _db is not None:
        await _db.blast_template_state.update_one(
            {"_id": "global"}, {"$set": new_state}, upsert=True,
        )
    logger.info(
        f"[tpl-perf] rotated default→{promoted!r}, "
        f"retired={len(retired)} (founder_locked kept {founder_locked!r})"
    )
    return new_state
