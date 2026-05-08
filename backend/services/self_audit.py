"""
Self-Audit Service — iter 282al-10.

Hourly cron that audits aurem.live (or any configured target) using the
existing seo_audit_router._local_score_from_v2 deterministic fallback.
Stores every run in `db.self_audit_log` (TTL 90 days) and pings Telegram if
the score drops below the configured threshold (default 95).

Public surface:
  • run_self_audit(db) — runs one cycle, returns the row
  • get_latest_self_audit(db) — for the Pillars Map chip
  • ensure_self_audit_indexes(db)

Telegram threshold = SELF_AUDIT_ALERT_THRESHOLD env (default 95).
Target URL    = SELF_AUDIT_TARGET_URL env (default https://aurem.live).
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

DEFAULT_TARGET = "https://aurem.live"
DEFAULT_THRESHOLD = 95


async def _score_target(url: str) -> dict:
    """Run the local-only audit (no PSI / Firecrawl dependency)."""
    from services.seo_audit_v2 import (
        fetch_html, parse_head_tags, run_seo_audit_v2,
    )
    # Run head + v2 + html fetch concurrently
    v2_task = asyncio.wait_for(run_seo_audit_v2(url), timeout=20.0)
    html_task = asyncio.wait_for(fetch_html(url), timeout=12.0)
    v2, html = await asyncio.gather(v2_task, html_task)
    head = parse_head_tags(html) if html else {}

    # Derive 4-axis score using the same heuristic as seo_audit_router
    from routers.seo_audit_router import _local_score_from_v2
    return _local_score_from_v2(v2, head, html)


async def run_self_audit(db, *, target_url: str | None = None,
                          threshold: int | None = None) -> dict:
    """Run one self-audit pass + alert + log. Returns the row."""
    target = (target_url or os.environ.get("SELF_AUDIT_TARGET_URL")
              or DEFAULT_TARGET)
    th = int(threshold if threshold is not None
             else os.environ.get("SELF_AUDIT_ALERT_THRESHOLD")
             or DEFAULT_THRESHOLD)

    started = datetime.now(timezone.utc)
    try:
        scored = await _score_target(target)
        ok = True
        err = None
    except Exception as e:
        logger.warning(f"[self_audit] {target} failed: {e}")
        scored = {
            "performance": 0, "seo": 0, "accessibility": 0,
            "best_practices": 0, "overall_score": 0,
        }
        ok = False
        err = str(e)[:300]

    overall = int(scored.get("overall_score") or 0)
    row = {
        "target": target,
        "ok": ok, "error": err,
        "overall_score": overall,
        "performance": int(scored.get("performance") or 0),
        "seo": int(scored.get("seo") or 0),
        "accessibility": int(scored.get("accessibility") or 0),
        "best_practices": int(scored.get("best_practices") or 0),
        "has_h1": bool(scored.get("has_h1")),
        "has_structured_data": bool(scored.get("has_structured_data")),
        "title": (scored.get("title") or "")[:160],
        "started_at": started,
        "completed_at": datetime.now(timezone.utc),
        "alerted": False,
    }

    # Telegram alert if below threshold
    if ok and overall < th:
        try:
            from services.autopilot_brief_notifier import _send_telegram
            text = (
                f"⚠️ AUREM self-audit dropped to {overall}/100\n\n"
                f"  • Site: {target}\n"
                f"  • Performance: {row['performance']}\n"
                f"  • SEO: {row['seo']}\n"
                f"  • Accessibility: {row['accessibility']}\n"
                f"  • Best practices: {row['best_practices']}\n\n"
                f"Threshold: {th}. Run a fresh audit at "
                f"{target}/audit and ship a fix."
            )
            r = await _send_telegram(text)
            row["alerted"] = bool(r.get("ok"))
            row["alert_channel"] = "telegram"
        except Exception as e:
            logger.debug(f"[self_audit] alert failed: {e}")

    if db is not None:
        try:
            await db.self_audit_log.insert_one(dict(row))
        except Exception as e:
            logger.debug(f"[self_audit] log insert failed: {e}")

    return row


async def get_latest_self_audit(db) -> dict | None:
    """Return the most recent row (used by Pillars Map chip)."""
    if db is None:
        return None
    try:
        row = await db.self_audit_log.find_one(
            {}, projection={"_id": 0},
            sort=[("started_at", -1)],
        )
        if row and isinstance(row.get("started_at"), datetime):
            row["started_at"] = row["started_at"].isoformat()
        if row and isinstance(row.get("completed_at"), datetime):
            row["completed_at"] = row["completed_at"].isoformat()
        return row
    except Exception as e:
        logger.debug(f"[self_audit] latest fetch failed: {e}")
        return None


async def ensure_self_audit_indexes(db) -> None:
    if db is None:
        return
    try:
        await db.self_audit_log.create_index(
            [("started_at", 1)],
            expireAfterSeconds=90 * 24 * 3600,
            name="started_at_ttl_90d",
        )
        await db.self_audit_log.create_index(
            [("target", 1), ("started_at", -1)],
            name="target_started",
        )
    except Exception as e:
        logger.debug(f"[self_audit] index skip: {e}")


__all__ = [
    "run_self_audit",
    "get_latest_self_audit",
    "ensure_self_audit_indexes",
    "DEFAULT_THRESHOLD",
    "DEFAULT_TARGET",
]
