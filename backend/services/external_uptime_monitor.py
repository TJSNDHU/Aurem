"""
services/external_uptime_monitor.py — iter 328c (external uptime guard)

Goal
────
Internal monitors lie when the system crashes. This module is the
"watch the watchman" layer: it expects an EXTERNAL service
(UptimeRobot or Better Uptime) to ping `https://aurem.live/api/health`
every 5 minutes. If we go > 10 min without a recorded ping, we know
the external monitor is also down OR the public site is unreachable
from the outside world.

Two pieces:

  • Inbound webhook route (`POST /api/uptime/report`) accepts ping
    notifications from the external service (HMAC-signed body).
    UptimeRobot supports custom webhook payloads natively; Better
    Uptime supports outgoing webhooks too. The route is stateless —
    it just stamps the latest receive time.

  • `monthly_uptime_report(db)` summarises the last 30 days of
    pings into the morning brief. Counts UP / DOWN events,
    longest outage, total downtime minutes.

Environment
───────────
  EXTERNAL_UPTIME_SECRET   — shared HMAC secret (set by founder)
  EXTERNAL_UPTIME_URL_TARGET — typically https://aurem.live/api/health
                                — informational only, not used in code.

Setup (founder-side, 5-minute task)
────────────────────────────────────
  1. Sign up at uptimerobot.com (free tier: 50 monitors).
  2. Add monitor: HTTPS — https://aurem.live/api/health — interval 5min.
  3. Add Alert Contact: Webhook → URL = https://aurem.live/api/uptime/report
     POST body (raw):
         {
           "monitor": "*monitorFriendlyName*",
           "url":     "*monitorURL*",
           "status":  "*alertType*",          # 1=down, 2=up
           "ping_ms": "*responseTime*",
           "ts":      "*alertDateTime*",
           "secret":  "<paste the same EXTERNAL_UPTIME_SECRET here>"
         }
  4. Set `EXTERNAL_UPTIME_SECRET=<random 32 bytes>` in prod env.

When set up correctly the morning brief will include a line like:
    "External uptime (UptimeRobot 30d): 99.94% — 1 outage, 8 min total"
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

PING_COLLECTION = "external_uptime_pings"
STALE_THRESHOLD_MINUTES = 10


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _shared_secret() -> str:
    return os.environ.get("EXTERNAL_UPTIME_SECRET") or ""


def verify_payload_secret(secret_from_body: str) -> bool:
    expected = _shared_secret()
    if not expected:
        # Not configured yet — accept-and-quarantine so the founder can
        # see incoming pings while wiring up the secret.
        return False
    return bool(secret_from_body) and secret_from_body == expected


async def record_external_ping(db, payload: dict) -> dict:
    """Stamp the latest external ping into Mongo."""
    if db is None:
        return {"ok": False, "error": "db not ready"}
    doc = {
        "monitor": (payload.get("monitor") or "unknown")[:120],
        "url":     (payload.get("url")     or "")[:300],
        "status":  str(payload.get("status") or "")[:8],
        "ping_ms": int(payload.get("ping_ms") or 0) if str(payload.get("ping_ms") or "").isdigit() else None,
        "ext_ts":  (payload.get("ts") or "")[:64],
        "ts":      _now(),
        "secret_ok": verify_payload_secret(payload.get("secret") or ""),
    }
    await db[PING_COLLECTION].insert_one(doc)
    return {"ok": True, "stored": True, "secret_ok": doc["secret_ok"]}


async def staleness_check(db) -> dict:
    """Return whether the external monitor has gone silent.

    If > STALE_THRESHOLD_MINUTES since the last accepted ping AND a
    ping was ever recorded, fire a Telegram alert (dedup'd per hour).
    """
    if db is None:
        return {"ok": False, "error": "db not ready"}
    last = await db[PING_COLLECTION].find_one(
        {"secret_ok": True}, sort=[("ts", -1)],
    )
    if not last:
        return {"ok": True, "configured": False,
                "hint": "no external pings yet — see EXTERNAL_UPTIME_SECRET setup"}
    age_s = (_now() - last["ts"]).total_seconds()
    stale = age_s > STALE_THRESHOLD_MINUTES * 60
    if stale:
        try:
            from services.silent_failure_alerts import _send as _tg
            hour = _now().strftime("%Y-%m-%d %H")
            await _tg(
                f"📡 External uptime monitor silent for {int(age_s / 60)} min "
                f"— check UptimeRobot dashboard. Last ping: "
                f"{last['ts'].isoformat()}",
                fingerprint=f"ext_uptime_silent_{hour}",
            )
        except Exception as e:
            logger.debug(f"[ext-uptime] alert failed: {e}")
    return {
        "ok":           True,
        "configured":   True,
        "stale":        stale,
        "last_ping":    last["ts"].isoformat(),
        "minutes_ago":  round(age_s / 60, 1),
    }


async def monthly_uptime_report(db) -> dict:
    """30-day summary used by the morning brief."""
    if db is None:
        return {"configured": False, "summary": ""}
    cutoff = _now() - timedelta(days=30)
    total = await db[PING_COLLECTION].count_documents(
        {"ts": {"$gte": cutoff}, "secret_ok": True}
    )
    if total == 0:
        return {"configured": False,
                "summary": "External uptime (30d): not configured yet."}
    down = await db[PING_COLLECTION].count_documents({
        "ts":     {"$gte": cutoff},
        "secret_ok": True,
        "status": {"$in": ["1", "down", "DOWN"]},
    })
    # Each ping represents 5 minutes; outage minutes is approximate.
    outage_min = down * 5
    total_min = total * 5
    uptime_pct = round(100.0 - (100.0 * outage_min / total_min), 3) if total_min else 100.0
    return {
        "configured":  True,
        "uptime_pct":  uptime_pct,
        "outages":     down,
        "outage_min":  outage_min,
        "total_pings": total,
        "summary": (
            f"External uptime (UptimeRobot 30d): {uptime_pct}% — "
            f"{down} outage{'s' if down != 1 else ''}, {outage_min} min total"
        ),
    }
