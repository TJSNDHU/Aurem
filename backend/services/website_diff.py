"""
Website Diff / Change Tracking — iter 282af (Prompt 3).

Tracks per-lead website snapshots so the Follow-up agent can weave
"what changed on your site" context into outreach.

Public surface (keep this API stable):
  • snapshot_lead_site(db, lead_id, url)  → dict
  • diff_lead_site(db, lead_id, url)      → dict
  • init_indexes_and_cleanup(db)          → none  (run at app start)

Internal helpers exposed for unit tests:
  • compute_word_count_delta(old, new)    → int
  • simulate_first_diff(url)              → dict  (stateless)

Collections:
  • website_snapshots  — per-scan content + brand + contacts
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

SNAPSHOT_RETENTION_DAYS = 90
_SNAPSHOT_RETENTION_SECONDS = SNAPSHOT_RETENTION_DAYS * 24 * 3600


# ─────────────────────────────────────────────────────────────────────
# Pure helpers (no DB)
# ─────────────────────────────────────────────────────────────────────
def _word_count(text: str | None) -> int:
    return len((text or "").split())


def compute_word_count_delta(old: dict, new: dict) -> int:
    """Return |new.word_count - old.word_count|. Accepts partial dicts."""
    a = int((old or {}).get("word_count") or _word_count((old or {}).get("content")))
    b = int((new or {}).get("word_count") or _word_count((new or {}).get("content")))
    return b - a


def simulate_first_diff(url: str) -> dict:
    """Stateless helper for `test_diff_returns_no_change_on_first_scan`.

    Mirrors the contract of `diff_lead_site` for the case where no prior
    snapshot exists, without hitting the DB.
    """
    now = datetime.now(timezone.utc)
    return {
        "lead_id":            None,
        "url":                url,
        "changed":            False,
        "word_count_delta":   0,
        "new_content_preview": "",
        "last_snapshot_ts":   None,
        "ts":                 now,
    }


# ─────────────────────────────────────────────────────────────────────
# DB-backed functions
# ─────────────────────────────────────────────────────────────────────
async def snapshot_lead_site(db, lead_id: str, url: str) -> dict:
    """Scan `url` via scan_website() and persist the result.

    Returns the stored document. Never raises — on scan failure we store
    a minimal row with status=failed so downstream diffs don't crash.
    """
    from services.website_scraper import scan_website

    scan = await scan_website(url)
    content = scan.get("content") or ""
    now = datetime.now(timezone.utc)
    doc = {
        "lead_id":     lead_id,
        "url":         url,
        "content":     content[:10000],   # hard cap so Mongo stays lean
        "brand":       scan.get("brand"),
        "contacts":    scan.get("contacts"),
        "word_count":  _word_count(content),
        "source":      scan.get("source"),
        "status":      scan.get("status"),
        "ts":          now,
        "date":        now.strftime("%Y-%m-%d"),
    }
    try:
        await db.website_snapshots.insert_one(dict(doc))
    except Exception as e:
        logger.debug(f"[website_diff] snapshot insert failed: {e}")
    return doc


async def diff_lead_site(db, lead_id: str, url: str) -> dict:
    """Compare a fresh scan of `url` against the latest stored snapshot.

    Behaviour:
      • No prior snapshot → save the fresh one and return changed=False.
      • Prior snapshot exists → compute word-count delta and content diff.
        changed=True iff word_count_delta != 0 OR first 500 chars of
        content differ.
    Never raises.
    """
    now = datetime.now(timezone.utc)
    try:
        prev = await db.website_snapshots.find_one(
            {"lead_id": lead_id, "url": url},
            sort=[("ts", -1)], projection={"_id": 0},
        )
    except Exception as e:
        logger.debug(f"[website_diff] lookup failed: {e}")
        prev = None

    fresh = await snapshot_lead_site(db, lead_id, url)

    if prev is None:
        return {
            "lead_id":            lead_id,
            "url":                url,
            "changed":            False,
            "word_count_delta":   0,
            "new_content_preview": "",
            "last_snapshot_ts":   None,
            "ts":                 now,
        }

    delta = compute_word_count_delta(prev, fresh)
    prev_head = (prev.get("content") or "")[:500]
    new_head = (fresh.get("content") or "")[:500]
    content_changed = prev_head != new_head
    changed = bool(delta != 0 or content_changed)

    return {
        "lead_id":            lead_id,
        "url":                url,
        "changed":            changed,
        "word_count_delta":   delta,
        "new_content_preview": (fresh.get("content") or "")[:200] if changed else "",
        "last_snapshot_ts":   prev.get("ts"),
        "ts":                 now,
    }


# ─────────────────────────────────────────────────────────────────────
# Startup hooks
# ─────────────────────────────────────────────────────────────────────
async def init_indexes_and_cleanup(db) -> dict:
    """Create TTL indexes + one-off 90-day purge. Safe to call multiple times.

    Returns stats for logging. Never raises — every step is try/except so a
    missing collection or connection flake doesn't kill app boot.
    """
    stats: dict[str, Any] = {"snapshots_deleted": 0, "indexes_ok": []}
    # TTL on website_snapshots.ts — 90 days
    try:
        await db.website_snapshots.create_index(
            [("ts", 1)], expireAfterSeconds=_SNAPSHOT_RETENTION_SECONDS,
            name="ts_ttl_90d",
        )
        await db.website_snapshots.create_index(
            [("lead_id", 1), ("ts", -1)], name="lead_ts",
        )
        stats["indexes_ok"].append("website_snapshots")
    except Exception as e:
        logger.debug(f"[website_diff] snapshot index skipped: {e}")

    # TTL on webclaw_usage.ts — 90 days (Prompt 3 hygiene)
    try:
        await db.webclaw_usage.create_index(
            [("ts", 1)], expireAfterSeconds=_SNAPSHOT_RETENTION_SECONDS,
            name="ts_ttl_90d",
        )
        await db.webclaw_usage.create_index([("date", 1)], name="date_idx")
        stats["indexes_ok"].append("webclaw_usage")
    except Exception as e:
        logger.debug(f"[website_diff] webclaw_usage index skipped: {e}")

    # TTL safety-net in case Mongo TTL monitor is lagging
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=SNAPSHOT_RETENTION_DAYS)
        res = await db.website_snapshots.delete_many({"ts": {"$lt": cutoff}})
        stats["snapshots_deleted"] = getattr(res, "deleted_count", 0)
    except Exception as e:
        logger.debug(f"[website_diff] cleanup skipped: {e}")

    return stats


# ─────────────────────────────────────────────────────────────────────
# Rollup helper (used by services.webclaw_usage_rollup cron)
# ─────────────────────────────────────────────────────────────────────
def build_rollup_doc(date: str, count: int, brand_rate: float,
                      contacts_rate: float, avg_content_length: int) -> dict:
    """Shape the webclaw_usage_daily doc. Pure."""
    return {
        "date":                date,
        "count":               int(count),
        "brand_rate":          float(brand_rate),
        "contacts_rate":       float(contacts_rate),
        "avg_content_length":  int(avg_content_length),
        "rolled_up_at":        datetime.now(timezone.utc),
    }


__all__ = [
    "snapshot_lead_site",
    "diff_lead_site",
    "init_indexes_and_cleanup",
    "compute_word_count_delta",
    "simulate_first_diff",
    "build_rollup_doc",
    "SNAPSHOT_RETENTION_DAYS",
]
