"""
services/shannon_autofix.py — autonomous Shannon Security follow-up.
Iter 325f Phase 4.

Shannon's HIGH/CRITICAL findings already land in `db.pending_approvals`
the moment `shannon_security.ingest_report()` runs (iter 325f Phase 1.3).
This module covers the rest:

  - LOW / MEDIUM findings — quietly enqueued as tier-1 pending_approvals
    so the ORA CTO repair agent can propose a fix. Founder doesn't get
    paged.
  - HIGH / CRITICAL findings — Telegram alert is fired here so the
    founder knows the queue is hot (the approval row itself was already
    written upstream; this is the human-facing ping).

Tick is scheduled every 30 minutes from registry.py.

Collections touched:
  - db.shannon_reports        (read)
  - db.pending_approvals      (write, via services.pending_approvals)
  - db.shannon_autofix_ticks  (write, debug log)
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict

logger = logging.getLogger(__name__)

LOW_MED = {"low", "medium"}
HIGH_CRIT = {"high", "critical"}


def _get_db():
    try:
        import server
        return getattr(server, "db", None)
    except Exception:
        return None


async def shannon_autofix_tick(db=None) -> Dict[str, Any]:
    """Inspect the most recent Shannon report and:
       1. Enqueue tier-1 pending_approvals for every LOW/MED finding not
          already enqueued.
       2. Fire a Telegram alert summarising HIGH/CRITICAL counts.
    Returns a stats dict for cron logging."""
    db = db or _get_db()
    if db is None:
        return {"ok": False, "error": "db_unavailable"}

    latest = await db.shannon_reports.find_one({}, sort=[("created_at", -1)])
    if not latest:
        return {"ok": True, "reason": "no_reports"}

    vulns = latest.get("vulnerabilities") or []
    target = latest.get("target", "unknown")

    sev_counts = {"low": 0, "medium": 0, "high": 0, "critical": 0}
    queued_low_med = 0
    deduped = 0

    try:
        from services.pending_approvals import create_pending_approval
    except ImportError:
        create_pending_approval = None  # graceful

    for v in vulns:
        sev = (v.get("severity") or "").lower()
        if sev in sev_counts:
            sev_counts[sev] += 1
        if sev in LOW_MED and create_pending_approval is not None:
            title = (v.get("title") or v.get("name") or
                     v.get("id") or "Security finding")
            try:
                row = await create_pending_approval(
                    type="security_fix",
                    title=f"[{sev.upper()}] {title}",
                    detail=(v.get("fix_suggestion") or v.get("remediation")
                            or "(no auto-fix suggestion)"),
                    severity=sev,
                    source="shannon_autofix",
                    fingerprint=f"shannon:{target}:{v.get('id') or title[:60]}",
                    tier=1,
                    metadata={"target": target, "auto_proposed": True,
                              "vuln_id": v.get("id")},
                    db=db,
                )
                if row.get("deduped"):
                    deduped += 1
                else:
                    queued_low_med += 1
            except Exception as e:
                logger.debug(f"[shannon_autofix] enqueue failed: {e}")

    # Telegram digest for HIGH/CRITICAL.
    high = sev_counts["high"] + sev_counts["critical"]
    if high > 0:
        try:
            from services.telegram_bot_service import send_telegram_alert
            await send_telegram_alert(
                message=(
                    f"Shannon scan of {target}\n\n"
                    f"  CRITICAL : {sev_counts['critical']}\n"
                    f"  HIGH     : {sev_counts['high']}\n"
                    f"  MEDIUM   : {sev_counts['medium']}\n"
                    f"  LOW      : {sev_counts['low']}\n\n"
                    f"All HIGH/CRITICAL findings are awaiting your approval:\n"
                    f"https://aurem.live/admin/approvals"
                ),
                alert_type="shannon_high",
                fingerprint=f"shannon:{target}:{latest.get('timestamp')}",
            )
        except Exception as e:
            logger.debug(f"[shannon_autofix] telegram skipped: {e}")

    stats = {
        "ok": True,
        "target": target,
        "sev_counts": sev_counts,
        "queued_low_med": queued_low_med,
        "deduped": deduped,
        "high_critical": high,
    }
    try:
        await db.shannon_autofix_ticks.insert_one({
            **stats,
            "ts": datetime.now(timezone.utc).isoformat(),
        })
    except Exception:
        pass
    return stats
