"""
AWB Safety Module — iter 282b
=============================
Belt-and-suspenders protection against AWB autopilot duplication bugs.

Components:
  1. ensure_indexes(db)        — idempotent partial-unique index on
                                  auto_built_sites(lead_id, status) for
                                  status in {rendered, published, deployed}.
                                  Created at startup. Hard-stops the
                                  Iter282 runaway-loop class of bugs at the
                                  DB layer, even if code-level filters
                                  regress.
  2. duplicate_safety_check(db) — point-in-time check. Returns flagged
                                  leads (3+ active sites in last 24h) and
                                  alerts founder via WhatsApp + email.
  3. awb_safety_scheduler(db)   — async background task. Runs the check
                                  once a day at ~03:00 UTC.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = ["rendered", "published", "deployed"]
SPAM_THRESHOLD_24H = 3  # alert if any lead crosses this in 24h


async def _dedupe_active_sites(db) -> int:
    """Best-effort dedupe before unique-index creation.

    For each (lead_id, status) pair where status is active and there are
    duplicates, keep the most-recently-created row and demote the others
    to status='archived' so the partial-unique index can be built.
    Returns the number of rows demoted. Never raises.
    """
    if db is None:
        return 0
    demoted = 0
    try:
        pipeline = [
            {"$match": {"status": {"$in": ACTIVE_STATUSES}}},
            {"$group": {
                "_id": {"lead_id": "$lead_id", "status": "$status"},
                "ids": {"$push": {"site_id": "$site_id",
                                   "created_at": "$created_at"}},
                "count": {"$sum": 1},
            }},
            {"$match": {"count": {"$gt": 1}}},
        ]
        async for grp in db.auto_built_sites.aggregate(pipeline):
            entries = grp.get("ids") or []
            entries.sort(key=lambda e: str(e.get("created_at") or ""), reverse=True)
            losers = [e.get("site_id") for e in entries[1:] if e.get("site_id")]
            if not losers:
                continue
            res = await db.auto_built_sites.update_many(
                {"site_id": {"$in": losers}},
                {"$set": {
                    "status": "archived",
                    "archived_at": datetime.now(timezone.utc).isoformat(),
                    "archived_reason": "awb_safety_dedupe",
                }},
            )
            demoted += getattr(res, "modified_count", 0) or 0
        if demoted:
            logger.info(f"[awb_safety] deduped {demoted} duplicate active sites")
    except Exception as e:
        logger.warning(f"[awb_safety] dedupe pass skipped: {e}")
    return demoted


async def ensure_indexes(db) -> Dict[str, Any]:
    """Idempotent — safe to call on every startup.

    Production hardening (iter 282al-24): if the unique-index creation
    fails with E11000 (duplicate key) we run a best-effort dedupe pass
    and retry once. This unblocks fresh production deploys that inherit
    duplicate-active-site rows from earlier non-indexed runs.
    """
    if db is None:
        return {"ok": False, "error": "no db"}

    async def _create():
        return await db.auto_built_sites.create_index(
            [("lead_id", 1), ("status", 1)],
            unique=True,
            partialFilterExpression={"status": {"$in": ACTIVE_STATUSES}},
            name="unique_lead_active_site",
        )

    try:
        name = await _create()
        logger.info(f"[awb_safety] ensured index: {name}")
        return {"ok": True, "index": name}
    except Exception as e:
        msg = str(e)
        # Auto-recover from E11000 by deduping then retrying once
        if "E11000" in msg or "duplicate key" in msg.lower():
            demoted = await _dedupe_active_sites(db)
            if demoted > 0:
                try:
                    name = await _create()
                    logger.info(
                        f"[awb_safety] ensured index after dedupe ({demoted} rows): {name}"
                    )
                    return {"ok": True, "index": name, "deduped": demoted}
                except Exception as e2:
                    logger.warning(f"[awb_safety] index retry failed: {e2}")
                    return {"ok": False, "error": str(e2)[:200],
                            "deduped": demoted}
        logger.warning(f"[awb_safety] index ensure skipped: {e}")
        return {"ok": False, "error": msg[:200]}


async def duplicate_safety_check(db) -> Dict[str, Any]:
    """Look back 24h, find leads with 3+ active sites, alert founder if any.

    Returns the audit summary; also writes it to `awb_safety_audits`.
    """
    if db is None:
        return {"ok": False, "error": "no db"}
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(hours=24)).isoformat()

    pipeline = [
        {"$match": {
            "status": {"$in": ACTIVE_STATUSES},
            "created_at": {"$gte": cutoff},
        }},
        {"$group": {
            "_id": "$lead_id",
            "count": {"$sum": 1},
            "slugs": {"$push": "$slug"},
            "site_ids": {"$push": "$site_id"},
        }},
        {"$match": {"count": {"$gte": SPAM_THRESHOLD_24H}}},
        {"$sort": {"count": -1}},
    ]

    flagged: List[Dict[str, Any]] = []
    async for d in db.auto_built_sites.aggregate(pipeline):
        flagged.append({
            "lead_id": d["_id"],
            "count": d["count"],
            "slugs": d.get("slugs", [])[:5],
            "site_ids": d.get("site_ids", [])[:5],
        })

    audit = {
        "checked_at": now.isoformat(),
        "window": "24h",
        "threshold": SPAM_THRESHOLD_24H,
        "flagged_count": len(flagged),
        "flagged": flagged[:20],
    }

    # Persist audit
    try:
        await db.awb_safety_audits.insert_one(dict(audit))
    except Exception as e:
        logger.debug(f"[awb_safety] audit persist failed: {e}")

    if flagged:
        await _alert_founder(flagged, now)
    else:
        logger.info("[awb_safety] daily duplicate check: clean")

    return audit


async def _alert_founder(flagged: List[Dict[str, Any]], now: datetime) -> None:
    """Best-effort founder alert via WhatsApp + email."""
    lines = [
        f"  • {f['lead_id']}: {f['count']} active sites in 24h"
        for f in flagged[:10]
    ]
    body = (
        f"AWB Safety Alert ({now.strftime('%Y-%m-%d %H:%M UTC')})\n\n"
        f"{len(flagged)} lead(s) crossed the {SPAM_THRESHOLD_24H}+ active "
        f"sites/24h threshold.\n\n"
        + "\n".join(lines)
        + "\n\nThis usually indicates an AWB autopilot loop. "
        "Check `awb_autopilot_runs` for recent activity. "
        "DB unique index `unique_lead_active_site` is the hard backstop."
    )

    # WhatsApp (founder)
    try:
        from routers.whatsapp_alerts import send_whatsapp
        founder_phone = os.environ.get("FOUNDER_WHATSAPP") \
            or os.environ.get("ADMIN_WHATSAPP", "")
        if founder_phone:
            await send_whatsapp(founder_phone, body)
            logger.info("[awb_safety] founder WhatsApp alert sent")
    except Exception as e:
        logger.warning(f"[awb_safety] WhatsApp alert failed: {e}")

    # Email (founder + admin)
    try:
        import httpx
        api_key = os.environ.get("RESEND_API_KEY", "")
        founder_email = (
            os.environ.get("FOUNDER_EMAIL")
            or os.environ.get("AUREM_SALES_BCC_EMAIL")
            or os.environ.get("ADMIN_EMAIL", "")
        )
        if api_key and founder_email:
            from_addr = os.environ.get("RESEND_FROM_EMAIL",
                                        "ORA <ora@aurem.live>")
            html = (
                "<div style='font-family:Georgia,serif;max-width:520px'>"
                "<h2 style='color:#a02020'>⚠ AWB Safety Alert</h2>"
                f"<p>{len(flagged)} lead(s) crossed the "
                f"{SPAM_THRESHOLD_24H}+ active sites / 24h threshold.</p>"
                "<pre style='background:#f4f4f4;padding:12px;"
                "border-radius:6px;font-size:12px;'>"
                + "\n".join(lines) + "</pre>"
                "<p>DB unique index <code>unique_lead_active_site</code> "
                "is the hard backstop. This alert means the index "
                "<em>didn't</em> trip — the duplicates are likely from "
                "different statuses or the filter window. Investigate "
                "<code>awb_autopilot_runs</code>.</p>"
                "</div>"
            )
            async with httpx.AsyncClient(timeout=15) as c:
                await c.post(
                    "https://api.resend.com/emails",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={"from": from_addr, "to": founder_email,
                          "subject": "[AUREM] AWB safety alert — "
                                     f"{len(flagged)} lead(s) flagged",
                          "html": html},
                )
            logger.info(f"[awb_safety] founder email sent to {founder_email}")
    except Exception as e:
        logger.warning(f"[awb_safety] email alert failed: {e}")


async def awb_safety_scheduler(db) -> None:
    """Run duplicate_safety_check once a day at ~03:00 UTC.

    Sleeps until next 03:00 UTC, runs the check, repeats. Never raises —
    any exception is logged and the loop continues.
    """
    while True:
        try:
            now = datetime.now(timezone.utc)
            target = now.replace(hour=3, minute=0, second=0, microsecond=0)
            if now >= target:
                target += timedelta(days=1)
            wait_s = (target - now).total_seconds()
            logger.info(
                f"[awb_safety] next safety check at {target.isoformat()} "
                f"({wait_s/3600:.1f}h away)"
            )
            await asyncio.sleep(wait_s)
            await duplicate_safety_check(db)
        except Exception as e:
            logger.error(f"[awb_safety] scheduler tick failed: {e}")
            await asyncio.sleep(3600)  # back off 1h on error

