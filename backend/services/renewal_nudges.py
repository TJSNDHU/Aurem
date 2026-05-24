"""
services/renewal_nudges.py — iter 332b D-1
=============================================

Daily cron that scans `db.organizations` for any org whose
`contract_renewal_date` falls in {90, 60, 30, 14} days from today.
For each match, fires a Telegram nudge to the founder so they can
upsell / fix retention risk BEFORE auto-renewal locks in another
12 months of the current tier.

Why this exists:
  Contracts auto-renew silently. Without a nudge, the founder learns
  about renewals after the credit-card charge — too late to upsell or
  rescue an unhappy account.

Idempotency:
  We write a row to `renewal_nudges_sent` keyed on (org_id, window_days,
  due_date_iso). The job skips orgs whose key is already present.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

_db = None

NUDGE_WINDOWS = (90, 60, 30, 14)


def set_db(database) -> None:
    global _db
    _db = database


def _today_utc() -> date:
    return datetime.now(timezone.utc).date()


def _parse_renewal_date(value) -> Optional[date]:
    """Accepts date, datetime, or ISO string. Returns date or None."""
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
        except Exception:
            try:
                return date.fromisoformat(value[:10])
            except Exception:
                return None
    return None


async def find_due_renewals(today: Optional[date] = None) -> list[dict]:
    """Returns the list of (org, window_days) tuples whose renewal lands
    exactly in {90, 60, 30, 14} days from `today` (UTC). Skips orgs that
    already received the nudge for this (org, window, due_date)."""
    if _db is None:
        return []
    today = today or _today_utc()
    # Compute the 4 target dates the cron cares about
    targets = {(today + timedelta(days=w)).isoformat(): w
                for w in NUDGE_WINDOWS}

    # Pull every org that has a renewal_date set
    cursor = _db.organizations.find(
        {"contract_renewal_date": {"$exists": True, "$ne": None}},
        {"_id": 0, "org_id": 1, "name": 1, "plan": 1, "mrr_usd": 1,
          "contract_renewal_date": 1, "data_residency": 1},
    )
    candidates = await cursor.to_list(length=2000)

    due: list[dict] = []
    for org in candidates:
        rd = _parse_renewal_date(org.get("contract_renewal_date"))
        if not rd:
            continue
        iso = rd.isoformat()
        if iso not in targets:
            continue
        window = targets[iso]
        # Idempotency check
        already = await _db.renewal_nudges_sent.find_one({
            "org_id":      org["org_id"],
            "window_days": window,
            "due_date":    iso,
        }, {"_id": 0})
        if already:
            continue
        due.append({"org": org, "window_days": window, "due_date": iso})
    return due


async def send_renewal_nudge(item: dict) -> dict:
    """Fire one Telegram nudge + write idempotency row + audit."""
    if _db is None:
        return {"ok": False, "error": "db_not_ready"}
    org = item["org"]
    window = item["window_days"]
    due_iso = item["due_date"]

    mrr_line = (f"MRR:     ${org.get('mrr_usd'):,}/mo"
                 if org.get("mrr_usd") else "MRR:     (not set)")
    arr_line = (f"ARR est: ${org.get('mrr_usd', 0) * 12:,}/yr"
                 if org.get("mrr_usd") else "")

    body = (
        f"🟠 Renewal nudge — {window} days out\n"
        f"\n"
        f"Org:     {org.get('name', '?')}\n"
        f"Plan:    {org.get('plan', '?').upper()}\n"
        f"{mrr_line}\n"
    )
    if arr_line:
        body += arr_line + "\n"
    body += (
        f"Renews:  {due_iso}\n"
        f"\n"
        f"What to do:\n"
        f"  • Pulse the account for upsell signals (token spend, seat growth, support tickets).\n"
        f"  • If usage is heavy, propose Pro/Enterprise tier before auto-renew.\n"
        f"  • If usage is thin, schedule a save-the-account call.\n"
    )

    sent = False
    try:
        from services.telegram_bot_service import send_telegram_alert
        await send_telegram_alert(body)
        sent = True
    except Exception as e:
        logger.warning(f"[renewal_nudge] telegram failed: {e}")

    # Idempotency row — written regardless of telegram success so we
    # don't spam on next tick. If telegram failed, the audit row notes it.
    await _db.renewal_nudges_sent.insert_one({
        "org_id":      org["org_id"],
        "window_days": window,
        "due_date":    due_iso,
        "sent_at":     datetime.now(timezone.utc).isoformat(),
        "telegram_ok": sent,
    })

    # Audit
    try:
        from services.unified_audit import write_event
        await write_event(
            action="renewal_nudge_sent",
            resource=f"org:{org['org_id']}",
            result="ok" if sent else "telegram_failed",
            user_id=None, org_id=org["org_id"],
            source_collection="renewal_nudges_sent",
            extra={"window_days": window, "due_date": due_iso,
                    "telegram_ok": sent},
        )
    except Exception:
        pass

    return {"ok": True, "sent": sent, "window_days": window,
             "due_date": due_iso, "org_id": org["org_id"]}


async def run_renewal_tick(today: Optional[date] = None) -> dict:
    """Cron entry-point. Returns a summary of what fired."""
    due = await find_due_renewals(today)
    results = []
    for item in due:
        r = await send_renewal_nudge(item)
        results.append(r)
    return {"ok": True, "checked_today": (today or _today_utc()).isoformat(),
             "nudges_fired": len(results), "details": results}


def install_scheduler(scheduler, db) -> None:
    """Daily at 9:00 AM UTC (≈ 5 AM EST). Idempotent on hot-reload."""
    set_db(db)
    async def _tick():
        try:
            r = await run_renewal_tick()
            if r["nudges_fired"]:
                logger.info(f"[renewal_nudge] fired={r['nudges_fired']} "
                            f"today={r['checked_today']}")
        except Exception as e:
            logger.warning(f"[renewal_nudge] tick error: {e}")
    try:
        scheduler.add_job(
            _tick,
            "cron", hour=9, minute=0,
            id="renewal_nudge_daily",
            name="Renewal Nudge (daily 9:00 UTC)",
            replace_existing=True,
            max_instances=1, coalesce=True, misfire_grace_time=3600,
        )
        logger.info("[renewal_nudge] daily cron installed at 09:00 UTC")
    except Exception as e:
        logger.warning(f"[renewal_nudge] scheduler install failed: {e}")
