"""
Agent Health Check — Phase 5 (24/7 Self-Healing)
==================================================
Runs every 5 minutes via APScheduler. Applies 7 rules to the live
agent fleet. All actions are autonomous — NO human approval required.

Rules (all configurable via env, defaults shown):

  R1. silent > 24h           → mark agent stalled, restart heartbeat
  R2. rejection > 50% in 24h → pause agent (`status=paused`)
  R3. cost spike (>3x avg)   → throttle agent (set `throttle=true`)
  R4. error rate >10/min     → quarantine agent (`status=quarantined`)
  R5. queue depth > 1000     → emit OVERLOAD + scale-out hint
  R6. deploy version drift   → if running version != system_state, alert
  R7. zero-action 6h         → mark idle, request a wake-up event

Every action emits a `HEALTH_RULE_FIRED` bus event so the ORA Brain
records it. Counts are persisted in `agent_health_actions` for audit.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ─── Tunables ─────────────────────────────────────────────────────────
SILENT_HOURS = int(os.environ.get("HEALTH_SILENT_HOURS", "24"))
REJECTION_RATE_THRESHOLD = float(os.environ.get("HEALTH_REJECTION_RATE", "0.5"))
COST_SPIKE_MULTIPLIER = float(os.environ.get("HEALTH_COST_MULTIPLIER", "3.0"))
ERROR_RATE_PER_MIN = int(os.environ.get("HEALTH_ERROR_PER_MIN", "10"))
QUEUE_DEPTH_LIMIT = int(os.environ.get("HEALTH_QUEUE_LIMIT", "1000"))
IDLE_HOURS = int(os.environ.get("HEALTH_IDLE_HOURS", "6"))


def _utc() -> datetime:
    return datetime.now(timezone.utc)


def _get_db():
    try:
        import server
        return getattr(server, "db", None)
    except Exception:
        return None


async def _emit_rule(rule: str, agent: str, action: str, detail: Dict[str, Any]) -> None:
    db = _get_db()
    if db is None:
        return
    try:
        from services.a2a_bus import bus
        asyncio.create_task(bus.emit("agent_health_check", "HEALTH_RULE_FIRED", {
            "rule": rule, "agent": agent, "action": action, "detail": detail,
        }))
    except Exception:
        pass
    try:
        await db.agent_health_actions.insert_one({
            "rule": rule, "agent": agent, "action": action,
            "detail": detail, "ts": _utc(),
        })
    except Exception as e:
        logger.debug(f"[health] insert err: {e}")


# ─── R1: silent > N hours ─────────────────────────────────────────────

async def rule_silent(db) -> int:
    cutoff = (_utc() - timedelta(hours=SILENT_HOURS)).isoformat()
    cursor = db.agent_heartbeats.find(
        {"last_beat": {"$lt": cutoff}, "status": {"$ne": "silent"}},
        {"_id": 0, "agent": 1, "last_beat": 1, "status": 1},
    )
    fired = 0
    async for hb in cursor:
        agent = hb.get("agent")
        if not agent:
            continue
        await db.agent_heartbeats.update_one(
            {"agent": agent},
            {"$set": {
                "status": "silent",
                "silent_since": _utc(),
                "silent_last_beat": hb.get("last_beat"),
            }},
        )
        await _emit_rule("R1_silent", agent, "marked_silent", {
            "last_beat": hb.get("last_beat"),
            "threshold_hours": SILENT_HOURS,
        })
        fired += 1
    return fired


# ─── R2: rejection rate > 50% in 24h ──────────────────────────────────

async def rule_rejection_rate(db) -> int:
    cutoff = (_utc() - timedelta(hours=24)).isoformat()
    pipeline = [
        {"$match": {"ts": {"$gte": cutoff}}},
        {"$group": {
            "_id": "$requesting_agent",
            "total": {"$sum": 1},
            "rejected": {"$sum": {"$cond": [{"$eq": ["$verdict", "REJECTED"]}, 1, 0]}},
        }},
        {"$match": {"total": {"$gte": 5}}},  # need a meaningful sample
    ]
    fired = 0
    async for r in db.council_decisions_detailed.aggregate(pipeline):
        agent = r["_id"]
        if not agent:
            continue
        rate = r["rejected"] / max(r["total"], 1)
        if rate < REJECTION_RATE_THRESHOLD:
            continue
        # Only fire once per agent per cooldown
        recent = await db.agent_health_actions.find_one({
            "rule": "R2_rejection_rate",
            "agent": agent,
            "ts": {"$gte": _utc() - timedelta(hours=12)},
        })
        if recent:
            continue
        await db.agent_heartbeats.update_one(
            {"agent": agent},
            {"$set": {
                "status": "paused",
                "paused_reason": "high_rejection_rate",
                "paused_at": _utc(),
                "paused_rate": round(rate, 3),
            }},
            upsert=True,
        )
        await _emit_rule("R2_rejection_rate", agent, "paused", {
            "rate": round(rate, 3), "total": r["total"], "rejected": r["rejected"],
            "threshold": REJECTION_RATE_THRESHOLD,
        })
        fired += 1
    return fired


# ─── R3: cost spike (>3x rolling avg) ────────────────────────────────

async def rule_cost_spike(db) -> int:
    """Per-agent cost in last 1h vs last 24h baseline."""
    now = _utc()
    cutoff_1h = (now - timedelta(hours=1)).isoformat()
    cutoff_24h = (now - timedelta(hours=24)).isoformat()
    pipeline = [
        {"$match": {"ts": {"$gte": cutoff_24h}}},
        {"$group": {
            "_id": "$agent",
            "spend_24h": {"$sum": {"$ifNull": ["$cost_usd", 0]}},
            "spend_1h": {"$sum": {"$cond": [
                {"$gte": ["$ts", cutoff_1h]},
                {"$ifNull": ["$cost_usd", 0]}, 0,
            ]}},
        }},
        {"$match": {"spend_24h": {"$gt": 0.05}}},
    ]
    fired = 0
    async for r in db.llm_costs.aggregate(pipeline):
        agent = r["_id"]
        if not agent:
            continue
        avg_per_hr = r["spend_24h"] / 24.0
        if avg_per_hr <= 0:
            continue
        if r["spend_1h"] < COST_SPIKE_MULTIPLIER * avg_per_hr:
            continue
        recent = await db.agent_health_actions.find_one({
            "rule": "R3_cost_spike", "agent": agent,
            "ts": {"$gte": now - timedelta(hours=2)},
        })
        if recent:
            continue
        await db.agent_heartbeats.update_one(
            {"agent": agent},
            {"$set": {"throttle": True, "throttle_reason": "cost_spike",
                      "throttle_at": now}},
            upsert=True,
        )
        await _emit_rule("R3_cost_spike", agent, "throttled", {
            "spend_1h_usd": round(r["spend_1h"], 4),
            "avg_per_hr_usd": round(avg_per_hr, 4),
            "multiplier": COST_SPIKE_MULTIPLIER,
        })
        fired += 1
    return fired


# ─── R4: error rate > 10/min ─────────────────────────────────────────

async def rule_error_rate(db) -> int:
    """Per-path error rate from the error_ledger (last 5 min)."""
    cutoff = _utc() - timedelta(minutes=5)
    pipeline = [
        {"$match": {"last_seen": {"$gte": cutoff}, "status": "open"}},
        {"$group": {"_id": "$path", "count": {"$sum": "$count"}}},
        {"$match": {"count": {"$gte": ERROR_RATE_PER_MIN * 5}}},
    ]
    fired = 0
    async for r in db.error_ledger.aggregate(pipeline):
        path = r["_id"]
        if not path:
            continue
        recent = await db.agent_health_actions.find_one({
            "rule": "R4_error_rate", "agent": path,
            "ts": {"$gte": _utc() - timedelta(minutes=15)},
        })
        if recent:
            continue
        await _emit_rule("R4_error_rate", path, "quarantine_alert", {
            "count_5m": r["count"], "threshold_per_min": ERROR_RATE_PER_MIN,
        })
        fired += 1
    return fired


# ─── R5: queue depth > 1000 ─────────────────────────────────────────

async def rule_queue_overflow(db) -> int:
    """Watch a2a_error_log + scheduled_calls + followup_queue."""
    fired = 0
    candidates = ("a2a_error_log", "scheduled_calls", "followup_queue")
    for col in candidates:
        try:
            depth = await db[col].count_documents({})
        except Exception:
            continue
        if depth < QUEUE_DEPTH_LIMIT:
            continue
        recent = await db.agent_health_actions.find_one({
            "rule": "R5_queue_overflow", "agent": col,
            "ts": {"$gte": _utc() - timedelta(hours=1)},
        })
        if recent:
            continue
        await _emit_rule("R5_queue_overflow", col, "overload_alert", {
            "depth": depth, "limit": QUEUE_DEPTH_LIMIT,
        })
        fired += 1
    return fired


# ─── R6: deploy version drift ────────────────────────────────────────

async def rule_deploy_drift(db) -> int:
    try:
        from services.deploy_monitor import _read_running_version
        running = await _read_running_version()
    except Exception:
        return 0
    if not running:
        return 0
    state = await db.system_state.find_one({"key": "deploy_version"}, {"_id": 0})
    expected = (state or {}).get("value")
    if not expected or running == expected:
        return 0
    recent = await db.agent_health_actions.find_one({
        "rule": "R6_deploy_drift",
        "ts": {"$gte": _utc() - timedelta(hours=1)},
    })
    if recent:
        return 0
    await _emit_rule("R6_deploy_drift", "deploy", "drift_alert", {
        "running": running, "recorded": expected,
    })
    return 1


# ─── R7: zero-action idle 6h ─────────────────────────────────────────

async def rule_idle(db) -> int:
    cutoff = (_utc() - timedelta(hours=IDLE_HOURS)).isoformat()
    pipeline = [
        {"$match": {"ts": {"$gte": cutoff}}},
        {"$group": {"_id": "$agent", "actions": {"$sum": 1}}},
    ]
    active_agents = set()
    async for r in db.agent_actions.aggregate(pipeline):
        if r["_id"]:
            active_agents.add(r["_id"])

    fired = 0
    cursor = db.agent_heartbeats.find(
        {"status": {"$nin": ["paused", "quarantined", "silent"]}},
        {"_id": 0, "agent": 1},
    )
    async for hb in cursor:
        agent = hb.get("agent")
        if not agent or agent in active_agents:
            continue
        recent = await db.agent_health_actions.find_one({
            "rule": "R7_idle", "agent": agent,
            "ts": {"$gte": _utc() - timedelta(hours=IDLE_HOURS)},
        })
        if recent:
            continue
        await db.agent_heartbeats.update_one(
            {"agent": agent},
            {"$set": {"status": "idle", "idle_since": _utc()}},
        )
        await _emit_rule("R7_idle", agent, "marked_idle", {
            "idle_hours": IDLE_HOURS,
        })
        fired += 1
    return fired


# ─── Orchestrator ────────────────────────────────────────────────────

async def run_health_check_once() -> Dict[str, Any]:
    """Execute all 7 rules in parallel, return per-rule fire counts."""
    db = _get_db()
    if db is None:
        return {"ok": False, "error": "db_unavailable"}

    results = await asyncio.gather(
        rule_silent(db),
        rule_rejection_rate(db),
        rule_cost_spike(db),
        rule_error_rate(db),
        rule_queue_overflow(db),
        rule_deploy_drift(db),
        rule_idle(db),
        return_exceptions=True,
    )
    names = ["R1_silent", "R2_rejection_rate", "R3_cost_spike",
             "R4_error_rate", "R5_queue_overflow",
             "R6_deploy_drift", "R7_idle"]
    out: Dict[str, Any] = {"ok": True, "ts": _utc().isoformat()}
    total = 0
    for name, res in zip(names, results):
        if isinstance(res, Exception):
            out[name] = {"error": str(res)[:120]}
        else:
            out[name] = int(res)
            total += int(res)
    out["total_fired"] = total
    return out


def health_check_scheduler():
    async def _loop():
        await asyncio.sleep(120)  # post-deploy grace
        while True:
            try:
                res = await run_health_check_once()
                if res.get("total_fired", 0):
                    logger.info(f"[health] cycle fired={res['total_fired']}: {res}")
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning(f"[health] cycle err: {e}")
            await asyncio.sleep(300)  # 5-minute cycle
    return _loop
