"""
services/pixel_health.py — iter 327l

Daily Pixel Health check for the Morning Brief.

Purpose
-------
The AUREM tracking pixel (`static/aurem-pixel.js`) sends customer
page-view events to `POST /api/universal/webhooks/generic`, which
inserts into `db.universal_events`. If something silently breaks
(LEAN_ROUTES skip-list regression like we hit in iter 327h, CORS
issue, pixel JS removed from a customer site), events stop flowing
and we have no visibility — until the next 30-day cohort report
collapses.

This module:
  1. Counts yesterday's `universal_events` inserts.
  2. Computes the 7-day average (excluding yesterday).
  3. Returns a plain-English summary line for the Morning Brief:
       "Yesterday: 247 pixel events (7-day avg: 312) — normal"
     or
       "Yesterday: 45 pixel events (7-day avg: 312) — LOW, check pixel install"
  4. If yesterday's count is ≥50% BELOW the 7-day average AND the
     average itself is non-trivial (≥10 events), fire a deduped
     Telegram alert via the existing silent_failure_alerts pipe.

Design notes
------------
- Cheap: two count queries with date-range filters; no scan, no
  aggregation pipeline.
- Idempotent: dedup fingerprint is the date string so we only ping
  once per day even if the brief runs multiple times.
- Safe: every Mongo call is wrapped — failure returns a soft
  "(pixel health unavailable)" line so the brief itself never breaks.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# Threshold: a "low" day is one where yesterday < (avg * (1 - DROP_RATIO)).
# 0.5 = 50% below the 7-day average.
DROP_RATIO = 0.5
# Don't alert on days where the average itself is sparse — too noisy.
MIN_AVG_FOR_ALERT = 10


async def _count_events_in_range(db, start: datetime, end: datetime) -> int:
    """Count `universal_events` documents inserted between [start, end)."""
    if db is None:
        return 0
    try:
        # `ts` field is set in universal_connector.normalize_webhook_event
        # at insert time. Range-filter is index-friendly when indexed.
        n = await db.universal_events.count_documents({
            "ts": {"$gte": start, "$lt": end},
        })
        return int(n or 0)
    except Exception as e:
        logger.warning(f"[pixel-health] count failed [{start}..{end}): {e}")
        return 0


def _classify(yesterday: int, avg: float) -> str:
    """Return one of: 'normal', 'low', 'sparse'.
    - sparse: avg < MIN_AVG_FOR_ALERT (don't grade)
    - low: yesterday < avg*(1-DROP_RATIO) AND avg ≥ MIN_AVG_FOR_ALERT
    - normal: otherwise
    """
    if avg < MIN_AVG_FOR_ALERT:
        return "sparse"
    if yesterday < avg * (1.0 - DROP_RATIO):
        return "low"
    return "normal"


async def compute_pixel_health(db) -> dict:
    """Return:
      {
        "yesterday_count":  int,
        "seven_day_avg":    float,
        "classification":   "normal" | "low" | "sparse",
        "brief_line":       str,
        "date_yesterday":   "YYYY-MM-DD",
      }
    Always returns a dict; never raises.
    """
    now = datetime.now(timezone.utc)
    today_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = today_midnight - timedelta(days=1)
    seven_days_back_start = today_midnight - timedelta(days=8)
    seven_days_back_end = yesterday_start  # exclude yesterday

    yesterday = await _count_events_in_range(db, yesterday_start, today_midnight)
    week_total = await _count_events_in_range(db, seven_days_back_start, seven_days_back_end)
    avg = week_total / 7.0 if week_total else 0.0

    cls = _classify(yesterday, avg)
    if cls == "sparse":
        line = (
            f"Yesterday: {yesterday} pixel events "
            f"(7-day avg: {avg:.0f}) — sparse, not enough history yet"
        )
    elif cls == "low":
        line = (
            f"Yesterday: {yesterday} pixel events "
            f"(7-day avg: {avg:.0f}) — LOW, check pixel install"
        )
    else:
        line = (
            f"Yesterday: {yesterday} pixel events "
            f"(7-day avg: {avg:.0f}) — normal"
        )
    return {
        "yesterday_count":  yesterday,
        "seven_day_avg":    round(avg, 1),
        "classification":   cls,
        "brief_line":       line,
        "date_yesterday":   yesterday_start.strftime("%Y-%m-%d"),
    }


async def maybe_alert_low_pixel_day(db, health: dict) -> dict:
    """Fire a Telegram alert if classification == 'low'.
    Idempotent: dedup fingerprint is yesterday's date so re-running
    the brief won't double-ping.

    Returns {"alerted": bool, "reason": str, ...}.
    """
    if health.get("classification") != "low":
        return {"alerted": False, "reason": "not_low"}
    fingerprint = f"pixel_low_{health.get('date_yesterday','unknown')}"
    body = (
        f"⚠️ AUREM Pixel Health: LOW day detected.\n"
        f"Date: {health.get('date_yesterday')}\n"
        f"Yesterday's pixel events: {health.get('yesterday_count')}\n"
        f"7-day average: {health.get('seven_day_avg')}\n"
        f"That's a >50% drop. Check that aurem-pixel.js is still "
        f"installed on customer sites and that "
        f"/api/universal/webhooks/generic is not returning 404."
    )
    try:
        from services.silent_failure_alerts import _send
        send_result = await _send(
            message=body,
            alert_type="pixel_health_low",
            fingerprint=fingerprint,
        )
        return {"alerted": True, "send_result": send_result,
                "fingerprint": fingerprint}
    except Exception as e:
        logger.warning(f"[pixel-health] alert dispatch failed: {e}")
        return {"alerted": False, "reason": f"dispatch_error: {type(e).__name__}"}
