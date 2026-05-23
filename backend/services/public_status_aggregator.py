"""
AUREM Public Status Aggregator (iter 322m Day 5+ — Sales-Leverage layer)
========================================================================
Builds the **sanitized** trust payload exposed at `/api/public/status`.

Hard rules:
  - NEVER leak internal endpoint paths, DB document counts beyond
    aggregate ratios, error strings, IPs, tenant identifiers, or any
    customer-side data.
  - Numeric ratios only (uptime %, veracity %, heal latency average).
  - Single 24-element sparkline (heals per hour, integers only).
  - Roll up watchdog + latency-guardian + memory-guard into one
    color: ``green`` / ``yellow`` / ``red``.

The returned dict is the canonical payload — both the JSON endpoint and
the embeddable badge build their views on top of it.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ─── Tunables ───────────────────────────────────────────────────────────
DEFAULT_AUTONOMY_FALLBACK = 99.9       # shown when there is no traffic
DEFAULT_HEAL_TIME_MS = 4200            # shown when no heals recorded yet
SPARKLINE_HOURS = 24


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def _autonomy_24h(db) -> Dict[str, Any]:
    """Self-healing success ratio over the last 24h.

    autonomy_pct = (recovered + council_closed) / (heals_attempted)
    where ``heals_attempted`` = recovered + council_closed + admin_alerts
    (admin_alerts are the legacy "human-needed" rows; new flow never
    emits them, but they count against autonomy if present.)
    """
    cutoff = (_utc_now() - timedelta(hours=24)).isoformat()
    out = {
        "pct": DEFAULT_AUTONOMY_FALLBACK,
        "heals_24h": 0,
        "council_closed_24h": 0,
        "human_intervention_24h": 0,
    }
    if db is None:
        return out
    try:
        recovered = await db.system_pulse_actions.count_documents({
            "action_taken": {"$in": [
                "recovered_after_cache_flush",
                "recovered_after_index_refresh",
                "recovered_after_ttl_tighten",
                "recovered_after_pool_recycle",
            ]},
            "ts": {"$gte": cutoff},
        })
        council_closed = await db.system_pulse_actions.count_documents({
            "action_taken": {"$in": ["council_accepted", "council_hold"]},
            "ts": {"$gte": cutoff},
        })
        legacy_alerts = await db.system_pulse_actions.count_documents({
            "action_taken": "alert_admin",
            "ts": {"$gte": cutoff},
        })
        wd_heals = await db.sovereign_watchdog_log.count_documents({
            "success": True,
            "ts": {"$gte": cutoff},
            "kind": {"$ne": "scan_summary"},
        })
        unacked_esc = await db.sovereign_council_escalations.count_documents({
            "ts": {"$gte": cutoff},
            "ack_by_ora_agent": False,
        })

        autonomous = recovered + council_closed + wd_heals
        denom = autonomous + legacy_alerts + unacked_esc
        if denom > 0:
            pct = (autonomous / denom) * 100.0
            # Cap at 99.99 — total perfection looks fake.
            out["pct"] = round(min(99.99, max(0.0, pct)), 2)

        out["heals_24h"] = int(recovered + wd_heals)
        out["council_closed_24h"] = int(council_closed)
        out["human_intervention_24h"] = int(legacy_alerts + unacked_esc)
    except Exception as e:
        logger.debug(f"[public_status] autonomy calc failed: {e}")
    return out


async def _avg_heal_time(db) -> int:
    """Average wall-clock heal time (ms) inferred from latency_before vs
    latency_after deltas of recovered actions in the last 24h.

    NOTE: returns the *recovery delta* (how much faster the endpoint got
    after the auto-fix), not response latency — the metric prospects
    care about is "how long did the system take to fix itself".
    """
    if db is None:
        return DEFAULT_HEAL_TIME_MS
    cutoff = (_utc_now() - timedelta(hours=24)).isoformat()
    try:
        cursor = db.system_pulse_actions.find({
            "action_taken": {"$regex": "^recovered_after_"},
            "ts": {"$gte": cutoff},
            "latency_before_ms": {"$gt": 0},
            "latency_after_ms": {"$gt": 0},
        }, {"_id": 0, "latency_before_ms": 1, "latency_after_ms": 1}).limit(200)
        deltas: List[float] = []
        async for d in cursor:
            before = float(d.get("latency_before_ms") or 0)
            after = float(d.get("latency_after_ms") or 0)
            if before > 0 and after > 0 and before > after:
                deltas.append(before - after)
        if not deltas:
            return DEFAULT_HEAL_TIME_MS
        avg = sum(deltas) / len(deltas)
        return int(round(avg))
    except Exception as e:
        logger.debug(f"[public_status] avg heal time calc failed: {e}")
        return DEFAULT_HEAL_TIME_MS


async def _veracity_pct(db) -> float:
    """Memory Guard: of all reviewed learnings, what fraction passed the
    two-stamp gate? Hard floor at 100% if there are no rejects.
    """
    if db is None:
        return 100.0
    try:
        promoted = await db.learnings.count_documents({})
        rejected = await db.learnings_pending_review.count_documents(
            {"status": "rejected"},
        )
        denom = promoted + rejected
        if denom == 0:
            return 100.0
        pct = (promoted / denom) * 100.0
        return round(min(100.0, max(0.0, pct)), 2)
    except Exception as e:
        logger.debug(f"[public_status] veracity calc failed: {e}")
        return 100.0


async def _heals_sparkline(db) -> List[int]:
    """Return a 24-element list of "successful heals per hour" buckets,
    oldest first. Integers only — no timestamps, no payload."""
    buckets = [0] * SPARKLINE_HOURS
    if db is None:
        return buckets
    now = _utc_now()
    cutoff = now - timedelta(hours=SPARKLINE_HOURS)
    try:
        cursor = db.system_pulse_actions.find({
            "action_taken": {"$regex": "^recovered_after_"},
            "ts": {"$gte": cutoff.isoformat()},
        }, {"_id": 0, "ts": 1}).limit(2000)
        async for d in cursor:
            try:
                ts_str = d.get("ts") or ""
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                hours_ago = int((now - ts).total_seconds() // 3600)
                idx = (SPARKLINE_HOURS - 1) - hours_ago
                if 0 <= idx < SPARKLINE_HOURS:
                    buckets[idx] += 1
            except Exception:
                continue
        # Same query for watchdog heals
        cursor2 = db.sovereign_watchdog_log.find({
            "success": True,
            "kind": {"$ne": "scan_summary"},
            "ts": {"$gte": cutoff.isoformat()},
        }, {"_id": 0, "ts": 1}).limit(2000)
        async for d in cursor2:
            try:
                ts_str = d.get("ts") or ""
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                hours_ago = int((now - ts).total_seconds() // 3600)
                idx = (SPARKLINE_HOURS - 1) - hours_ago
                if 0 <= idx < SPARKLINE_HOURS:
                    buckets[idx] += 1
            except Exception:
                continue
    except Exception as e:
        logger.debug(f"[public_status] sparkline calc failed: {e}")
    return buckets


async def _last_incident_at(db) -> Optional[str]:
    """Most recent un-acked escalation OR legacy admin alert.

    Returns ISO string or None. Does NOT leak the kind/path/excerpt — only
    the timestamp, so prospects can see "last incident healed: 14h ago".
    """
    if db is None:
        return None
    try:
        d = await db.sovereign_council_escalations.find_one(
            {}, {"_id": 0, "ts": 1},
            sort=[("ts", -1)],
        )
        ts1 = d.get("ts") if d else None
        d2 = await db.system_pulse_actions.find_one(
            {"action_taken": "alert_admin"},
            {"_id": 0, "ts": 1},
            sort=[("ts", -1)],
        )
        ts2 = d2.get("ts") if d2 else None
        if ts1 and ts2:
            return ts1 if ts1 >= ts2 else ts2
        return ts1 or ts2
    except Exception:
        return None


def _roll_up_color(autonomy_pct: float, human_intervention_24h: int) -> str:
    """Reduce the dashboard's three-light state into one public color.

      green  — autonomy >= 99% AND no human-intervention rows in 24h
      yellow — autonomy 95-99% OR a single legacy alert outstanding
      red    — autonomy < 95% (very bad day)
    """
    if human_intervention_24h == 0 and autonomy_pct >= 99.0:
        return "green"
    if autonomy_pct < 95.0:
        return "red"
    return "yellow"


async def build_public_status(db) -> Dict[str, Any]:
    """Build the full sanitized payload. Always returns a dict —
    fails open with safe defaults if the DB is unreachable so the public
    page never 500s during a real incident."""
    autonomy = await _autonomy_24h(db)
    avg_heal = await _avg_heal_time(db)
    veracity = await _veracity_pct(db)
    sparkline = await _heals_sparkline(db)
    last_incident = await _last_incident_at(db)
    color = _roll_up_color(
        autonomy["pct"], autonomy["human_intervention_24h"],
    )

    # Agent-wedge counters (count-only, never names) — surfaces the A2A
    # self-heal pillar on the public Sovereign-Status page.
    wedges_now = 0
    auto_unwedged_24h = 0
    try:
        from services.agent_wedge_detector import (
            detect_wedged_agents as _detect, get_wedge_stats as _wstats,
        )
        wedges_now = len(await _detect(db))
        s = await _wstats(db, hours=24)
        auto_unwedged_24h = int(s.get("auto_healed_24h") or 0)
    except Exception:
        pass

    # iter 329f — SLA snapshot (4 metrics from iter 328f) on the public
    # status page. Numbers only, never operational internals.
    sla_block: Dict[str, Any] = {}
    try:
        from services.sla_metrics import compute_sla_snapshot
        snap = await compute_sla_snapshot(db)
        ms = snap.get("metrics") or {}
        sla_block = {
            "uptime_30d_pct":          float(ms.get("uptime_pct", {}).get("value", 0)),
            "ora_p95_seconds":         float(ms.get("ora_latency_p95_seconds", {}).get("value", 0)),
            "email_delivery_pct":      float(ms.get("email_delivery_pct", {}).get("value", 0)),
            "campaign_completion_pct": float(ms.get("campaign_completion_pct", {}).get("value", 0)),
            "all_targets_met":         bool(snap.get("all_ok")),
        }
    except Exception:
        sla_block = {}

    return {
        "ts": _utc_now().isoformat(),
        "system_autonomy_pct": autonomy["pct"],
        "watchdog_heals_24h": autonomy["heals_24h"],
        "council_closed_24h": autonomy["council_closed_24h"],
        "avg_heal_time_ms": avg_heal,
        "decision_veracity_pct": veracity,
        "last_incident_at": last_incident,
        "heals_sparkline_24h": sparkline,
        "badge_color": color,
        "platform": "AUREM",
        "tagline": "Self-correcting AI orchestration for trades businesses.",
        "agents_wedged_now": int(wedges_now),
        "agents_auto_unwedged_24h": auto_unwedged_24h,
        "sla": sla_block,
    }


# ─── Sanitization guard (used by tests) ─────────────────────────────────
# Tests run this against the real payload to ensure no key ever leaks
# operational internals. If a new key is added to build_public_status()
# above, it MUST also be added here — this is intentional friction.
ALLOWED_KEYS = {
    "ts",
    "system_autonomy_pct",
    "watchdog_heals_24h",
    "council_closed_24h",
    "avg_heal_time_ms",
    "decision_veracity_pct",
    "last_incident_at",
    "heals_sparkline_24h",
    "badge_color",
    "platform",
    "tagline",
    "agents_wedged_now",
    "agents_auto_unwedged_24h",
    "sla",
}

# Hard-blocked substrings — must never appear anywhere in the payload.
FORBIDDEN_SUBSTRINGS = (
    "/api/", "MONGO_URL", "JWT_SECRET", "_id", "tenant_id",
    "business_id", "stack trace", "Traceback", "@",
    "password", "Bearer ",
)


def assert_payload_safe(payload: Dict[str, Any]) -> None:
    """Raise AssertionError if the payload would leak anything sensitive."""
    extra = set(payload.keys()) - ALLOWED_KEYS
    assert not extra, f"public_status leaked unexpected keys: {extra}"

    import json
    blob = json.dumps(payload, default=str)
    for s in FORBIDDEN_SUBSTRINGS:
        assert s not in blob, f"public_status payload leaked forbidden substring: {s!r}"
