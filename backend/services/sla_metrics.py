"""
services/sla_metrics.py — iter 328f (SLA + Error Budget)

Defines AUREM's SLA targets and computes today's vs. monthly progress:

  • Uptime ≥ 99.5% / month   (sliding 30-day window from
    `aurem_health_log` row count vs total minute-buckets).
  • ORA chat reply latency p95 < 3 s   (from `ora_decisions` /
    `ora_session_costs` last 24h).
  • Email delivery rate ≥ 95%   (resend/gmail success / total in
    last 24h).
  • Campaign completion rate ≥ 98%   (`ora_campaign_health.
    last_run_processed > 0` cycles / total cycles in last 24h).

Telegram alert fires once per metric per day when below target.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)


SLA_TARGETS = {
    "uptime_pct":              99.5,
    "ora_latency_p95_seconds": 3.0,
    "email_delivery_pct":      95.0,
    "campaign_completion_pct": 98.0,
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def compute_sla_snapshot(db) -> dict:
    """One-shot snapshot of all 4 SLA metrics. Returns:

        {
          "ts": iso,
          "metrics": {
              uptime_pct:              {value, target, ok, breach_minutes},
              ora_latency_p95_seconds: {value, target, ok, sample_size},
              email_delivery_pct:      {value, target, ok, sent, delivered},
              campaign_completion_pct: {value, target, ok, cycles, productive},
          },
          "all_ok": bool,
        }
    """
    if db is None:
        return {"ok": False, "error": "db not ready"}

    metrics: dict[str, dict] = {}

    # ── uptime: % of last-30d minutes where at least one nightly probe
    #    or warm-probe succeeded ─────────────────────────────────────
    try:
        cutoff = _now() - timedelta(days=30)
        total_minutes = 30 * 24 * 60
        # `aurem_health_log` is populated by warm_prober every minute.
        ok_count = await db.aurem_health_log.count_documents({
            "ts": {"$gte": cutoff},
            "ok": True,
        })
        # Clamp at total — can't exceed window length.
        uptime_pct = min(100.0, round(100.0 * ok_count / total_minutes, 3))
        target = SLA_TARGETS["uptime_pct"]
        metrics["uptime_pct"] = {
            "value":          uptime_pct,
            "target":         target,
            "ok":             uptime_pct >= target,
            "breach_minutes": max(0, total_minutes - ok_count),
            "sample_size":    total_minutes,
        }
    except Exception as e:
        metrics["uptime_pct"] = {"error": str(e)[:200], "ok": False,
                                  "value": 0.0, "target": SLA_TARGETS["uptime_pct"]}

    # ── ORA p95 latency, last 24h, from `ora_session_costs` ─────────
    try:
        cutoff = _now() - timedelta(hours=24)
        cur = db.ora_session_costs.find(
            {"ts": {"$gte": cutoff}, "latency_seconds": {"$exists": True}},
            {"_id": 0, "latency_seconds": 1},
        ).limit(2000)
        samples: list[float] = []
        async for r in cur:
            try:
                samples.append(float(r["latency_seconds"]))
            except Exception:
                continue
        if samples:
            samples.sort()
            idx = max(0, int(round(0.95 * (len(samples) - 1))))
            p95 = samples[idx]
        else:
            p95 = 0.0
        target = SLA_TARGETS["ora_latency_p95_seconds"]
        metrics["ora_latency_p95_seconds"] = {
            "value":       round(p95, 3),
            "target":      target,
            "ok":          bool(samples) and p95 <= target,
            "sample_size": len(samples),
        }
    except Exception as e:
        metrics["ora_latency_p95_seconds"] = {"error": str(e)[:200], "ok": False,
                                                 "value": 0.0,
                                                 "target": SLA_TARGETS["ora_latency_p95_seconds"]}

    # ── email delivery rate, last 24h, from `email_sent_log` ────────
    try:
        cutoff = _now() - timedelta(hours=24)
        sent = await db.email_sent_log.count_documents({"ts": {"$gte": cutoff}})
        delivered = await db.email_sent_log.count_documents({
            "ts": {"$gte": cutoff}, "status": {"$in": ["sent", "delivered", "ok"]},
        })
        pct = round(100.0 * delivered / sent, 2) if sent else 100.0
        target = SLA_TARGETS["email_delivery_pct"]
        metrics["email_delivery_pct"] = {
            "value":     pct,
            "target":    target,
            "ok":        pct >= target if sent else True,   # no traffic = ok
            "sent":      sent,
            "delivered": delivered,
        }
    except Exception as e:
        metrics["email_delivery_pct"] = {"error": str(e)[:200], "ok": False,
                                          "value": 0.0,
                                          "target": SLA_TARGETS["email_delivery_pct"]}

    # ── campaign completion rate, last 24h, from `ora_campaign_health` ──
    try:
        cutoff = _now() - timedelta(hours=24)
        cur = db.ora_campaign_health.find(
            {"ts": {"$gte": cutoff}},
            {"_id": 0, "last_run_processed": 1, "last_run_sent": 1},
        ).limit(2000)
        cycles = 0
        productive = 0
        async for r in cur:
            cycles += 1
            if (r.get("last_run_processed") or 0) > 0 or (r.get("last_run_sent") or 0) > 0:
                productive += 1
        pct = round(100.0 * productive / cycles, 2) if cycles else 100.0
        target = SLA_TARGETS["campaign_completion_pct"]
        metrics["campaign_completion_pct"] = {
            "value":      pct,
            "target":     target,
            "ok":         pct >= target if cycles else True,
            "cycles":     cycles,
            "productive": productive,
        }
    except Exception as e:
        metrics["campaign_completion_pct"] = {"error": str(e)[:200], "ok": False,
                                                "value": 0.0,
                                                "target": SLA_TARGETS["campaign_completion_pct"]}

    all_ok = all(m.get("ok") for m in metrics.values())
    snapshot = {
        "ts":      _now().isoformat(),
        "metrics": metrics,
        "all_ok":  all_ok,
    }
    # Persist (best-effort) so the morning brief / history view can read it.
    try:
        await db.sla_snapshots.insert_one(dict(snapshot))
    except Exception as e:
        logger.warning(f"[sla] snapshot persist failed: {e}")
    return snapshot


async def maybe_alert_sla_breach(db, snapshot: dict) -> dict:
    """Fire one Telegram per breaching metric per day."""
    if not snapshot or not snapshot.get("metrics"):
        return {"ok": False, "error": "no snapshot"}
    day = _now().strftime("%Y-%m-%d")
    fired: list[str] = []
    for name, m in snapshot["metrics"].items():
        if m.get("ok") is True:
            continue
        try:
            from services.silent_failure_alerts import _send as _tg
            await _tg(
                f"⚠️ SLA breach — {name}={m.get('value')} (target {m.get('target')}). "
                f"See ora_cockpit → SLA card for detail.",
                fingerprint=f"sla_breach_{name}_{day}",
            )
            fired.append(name)
        except Exception as e:
            logger.debug(f"[sla] alert failed for {name}: {e}")
    return {"ok": True, "fired": fired}
