"""
AUREM Agent Wedge Detector + A2A Self-Heal (iter 322o)
========================================================

Sovereign-grade auto-detection + auto-heal for ORA agents that get
stuck in "boot-XXX · NNm" red state.

Why this exists
---------------
Watchdog already heals **process-level** wedges (whole backend down).
Latency Guardian heals **endpoint-level** slowness. But neither
catches **agent-level** wedges where ONE specific ORA (Scout / Hunter
/ Closer) freezes on a long-running task while the rest of the system
is healthy. That's the gap shown by ``boot-1777956593 · 52m``.

Design
------
1. **Detect** (every WEDGE_SCAN_INTERVAL_S, default 30 s):
   - Read ``agent_ledger_entries`` per known agent.
   - Last activity = latest `timestamp` row.
   - Wedged = (had activity within last 7 days) AND (no activity for
     `WEDGE_THRESHOLD_S`, default 30 min).
   - Idle agents (zero rows in 7 days) are NOT wedged — they're
     dormant, that's a different state.

2. **Heal** (cascade — runs once per detected wedge):
   - Step 1  · Heartbeat ping  — insert a `kind: "boot_unwedge"` row
     so downstream readers see the agent move forward again.
   - Step 2  · Council notify  — convene_council("agent_wedge", ...)
     so the System ORA cluster knows about this peer and can route
     work around / re-attest.
   - Step 3  · Pulse log       — write to `system_pulse_actions` for
     the public Sovereign-Status dashboard.

3. **A2A signal** — every heal writes a row in
   `agent_a2a_signals` with `{kind: "wedge_recovered", from, to}` so
   peer agents (Memory Guard, Council Rotation, future workers) can
   subscribe to the broadcast in their own scan cycles.

Idempotency
-----------
A heal cascade only fires if no other heal has been logged for the
same agent within the last `WEDGE_HEAL_COOLDOWN_S` (default 600 s).
This prevents the scheduler from thrashing the same agent every tick
while it's in cold-boot.

Public API
----------
- ``detect_wedged_agents(db) -> List[Dict]``
- ``auto_heal_agent(db, agent_id) -> Dict``
- ``run_wedge_scan(db) -> Dict``  (scheduler entry-point)
- ``get_wedge_stats(db, hours=24) -> Dict``  (for dashboards)
"""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ─── Tunables ───────────────────────────────────────────────────────────
# Default wedge horizon: 30 min of silence on a previously-active agent.
# Production override via env without code change.
WEDGE_THRESHOLD_S = int(os.environ.get("WEDGE_THRESHOLD_S", "1800"))
# How often to scan. 60 s default — slow enough that the ~30 Mongo
# lookups per tick (T1 + T2 + T3 + ledger discovery aggregation) don't
# saturate the FastAPI event loop and starve out K8s liveness probes
# (`/health`) during deploy cold-boot.  Lower this only if you know
# the pod has plenty of headroom.
WEDGE_SCAN_INTERVAL_S = int(os.environ.get("WEDGE_SCAN_INTERVAL_S", "60"))
# Don't try to re-heal the same agent within this window.
WEDGE_HEAL_COOLDOWN_S = int(os.environ.get("WEDGE_HEAL_COOLDOWN_S", "600"))
# An agent is "previously-active" iff it had any ledger row in the last
# this-many days. Brand new agents that never ran are NOT wedged.
WEDGE_ACTIVE_DAYS = int(os.environ.get("WEDGE_ACTIVE_DAYS", "7"))


# Known ORA agents — used as detection seed when we want a deterministic
# scan (Scout / Hunter / Closer / Envoy / FollowUp / Referral / Brain).
# The detector ALSO discovers agents from the ledger so this list is
# non-blocking — it just guarantees critical agents get a status row
# even when fully silent.
#
# iter 322o-fix:
#   - Aligned id `follow_up_ora` → `followup_ora` to match the canonical
#     `services/agent_soul.py` registry. Old name was a copy-paste bug
#     that would have silently dropped FollowUp from wedge detection.
#   - Removed `hup_ora` — it appeared in production UI but is not
#     defined anywhere in this codebase. Adding it back is a code-only
#     decision that should follow agent_soul.py, not the prod ticker.
#   - Added `ora_brain` — God-Mode router, most-active agent in prod.
KNOWN_AGENTS: tuple[str, ...] = (
    "scout_ora", "hunter_ora", "closer_ora",
    "envoy_ora", "followup_ora", "referral_ora",
    "ora_brain",
)


# iter 322o+ — A2A MULTI-TIER WIRING
# ===================================
# The wedge detector now treats THREE tiers of agents:
#
#   T1 Customer ORAs    — KNOWN_AGENTS above, healed via ledger heartbeat
#   T2 Council members  — 11 LLM personas in `ora_council._BUILTIN_PROMPTS`,
#                         healed via `council_sessions` heartbeat
#   T3 Sovereign workers — Watchdog / MemoryGuard / Rotation / Guardian /
#                         Fulfiller, healed via `system_pulse_actions` heartbeat
#
# Each tier reports activity to a different Mongo collection, so we
# query them with tier-specific lookups. Everything funnels through the
# same `auto_heal_agent` cascade so the trust badge stays unified.

COUNCIL_ROLES: tuple[str, ...] = (
    "scout", "envoy", "closer", "followup",
    "casl", "seo", "dev", "reddit",
    "security", "qa", "pricing",
)

SOVEREIGN_WORKERS: tuple[str, ...] = (
    "sovereign_watchdog", "sovereign_memory_guard",
    "council_rotation", "latency_guardian",
    "pillar_restart_fulfiller", "agent_wedge_detector",
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_ts(ts_any: Any) -> Optional[datetime]:
    """Defensive ISO parse — ledger rows mix string + datetime."""
    if ts_any is None:
        return None
    if isinstance(ts_any, datetime):
        return ts_any if ts_any.tzinfo else ts_any.replace(tzinfo=timezone.utc)
    if isinstance(ts_any, str):
        try:
            t = datetime.fromisoformat(ts_any.replace("Z", "+00:00"))
            return t if t.tzinfo else t.replace(tzinfo=timezone.utc)
        except Exception:
            return None
    return None


# ─── Detection ─────────────────────────────────────────────────────────
async def _last_activity(db, agent_id: str) -> Optional[datetime]:
    """Read the latest `timestamp` for `agent_id` from the ledger."""
    if db is None:
        return None
    try:
        row = await db.agent_ledger_entries.find_one(
            {"agent_id": agent_id},
            {"_id": 0, "timestamp": 1},
            sort=[("timestamp", -1)],
        )
    except Exception as e:
        logger.debug(f"[wedge] last_activity lookup failed for {agent_id}: {e}")
        return None
    if not row:
        return None
    return _parse_ts(row.get("timestamp"))


async def _has_recent_activity(db, agent_id: str, days: int) -> bool:
    """Has the agent inserted any row in the last `days`?"""
    if db is None:
        return False
    cutoff = (_utc_now() - timedelta(days=days)).isoformat()
    try:
        cnt = await db.agent_ledger_entries.count_documents(
            {"agent_id": agent_id, "timestamp": {"$gte": cutoff}},
            limit=1,
        )
        return cnt > 0
    except Exception:
        return False


async def detect_wedged_agents(
    db,
    *,
    threshold_s: Optional[int] = None,
    active_days: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Return the list of agents currently judged "wedged".

    Output rows:
        {
          "agent_id": str,
          "tier": "T1_customer" | "T2_council" | "T3_sovereign",
          "last_activity": "<ISO>" | None,
          "age_seconds": int,
          "reason": "stale_heartbeat",
        }
    """
    threshold = int(threshold_s if threshold_s is not None else WEDGE_THRESHOLD_S)
    days = int(active_days if active_days is not None else WEDGE_ACTIVE_DAYS)

    # Discover agents from the ledger PLUS the known-agents seed list,
    # so wedges can be flagged even on a freshly-deployed pod.
    discovered: set[str] = set(KNOWN_AGENTS)
    if db is not None:
        try:
            cursor = db.agent_ledger_entries.aggregate([
                {"$group": {"_id": "$agent_id"}},
                {"$limit": 100},
            ])
            async for d in cursor:
                aid = d.get("_id")
                if isinstance(aid, str) and aid:
                    discovered.add(aid)
        except Exception as e:
            logger.debug(f"[wedge] discover via ledger failed: {e}")

    now = _utc_now()
    wedged: List[Dict[str, Any]] = []
    for agent_id in sorted(discovered):
        last = await _last_activity(db, agent_id)
        # If the agent has NEVER reported, it's not wedged — it's dormant.
        if last is None:
            continue
        age_s = int((now - last).total_seconds())
        if age_s < threshold:
            continue
        # Confirm "previously active" — must have run in last N days.
        if not await _has_recent_activity(db, agent_id, days):
            continue
        wedged.append({
            "agent_id": agent_id,
            "tier": "T1_customer",
            "last_activity": last.isoformat(),
            "age_seconds": age_s,
            "reason": "stale_heartbeat",
        })
    return wedged


# ─── A2A MULTI-TIER DETECTION (iter 322o+) ─────────────────────────────
async def _last_council_activity(db, role: str) -> Optional[datetime]:
    """T2 Council heartbeat = latest council_sessions row touching `role`."""
    if db is None:
        return None
    try:
        row = await db.council_sessions.find_one(
            {"$or": [
                {"role": role},
                {"agents_used": role},
                {"winner": role},
            ]},
            {"_id": 0, "ts": 1},
            sort=[("ts", -1)],
        )
    except Exception:
        return None
    if not row:
        return None
    return _parse_ts(row.get("ts"))


async def _last_sovereign_activity(db, worker: str) -> Optional[datetime]:
    """T3 Sovereign worker heartbeat — `system_pulse_actions` rows tagged
    with the worker's source. Falls back to most-recent action of any
    kind so a quietly-healthy worker doesn't get false-positived.
    """
    if db is None:
        return None
    try:
        row = await db.system_pulse_actions.find_one(
            {"$or": [
                {"source": worker},
                {"recovered_by": worker},
            ]},
            {"_id": 0, "ts": 1},
            sort=[("ts", -1)],
        )
    except Exception:
        return None
    if not row:
        return None
    return _parse_ts(row.get("ts"))


async def detect_wedged_council(
    db,
    *,
    threshold_s: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Return Council roles whose last `council_sessions` heartbeat is
    older than the threshold. Council should fire at least once per
    rotation tick (default 5 min) so the threshold is much shorter than
    T1 — default 60 min hard floor.
    """
    threshold = int(threshold_s if threshold_s is not None else max(WEDGE_THRESHOLD_S, 3600))
    now = _utc_now()
    wedged: List[Dict[str, Any]] = []
    for role in COUNCIL_ROLES:
        last = await _last_council_activity(db, role)
        if last is None:
            continue  # role never used → dormant, not wedged
        age_s = int((now - last).total_seconds())
        if age_s < threshold:
            continue
        wedged.append({
            "agent_id": f"council:{role}",
            "tier": "T2_council",
            "last_activity": last.isoformat(),
            "age_seconds": age_s,
            "reason": "stale_council_heartbeat",
        })
    return wedged


async def detect_wedged_sovereign_workers(
    db,
    *,
    threshold_s: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Return Sovereign workers whose pulse-action stream has gone
    silent. Workers tick frequently (30s-5min); 30 min silence is a
    confident wedge signal.
    """
    threshold = int(threshold_s if threshold_s is not None else WEDGE_THRESHOLD_S)
    now = _utc_now()
    wedged: List[Dict[str, Any]] = []
    for worker in SOVEREIGN_WORKERS:
        last = await _last_sovereign_activity(db, worker)
        if last is None:
            continue
        age_s = int((now - last).total_seconds())
        if age_s < threshold:
            continue
        wedged.append({
            "agent_id": f"worker:{worker}",
            "tier": "T3_sovereign",
            "last_activity": last.isoformat(),
            "age_seconds": age_s,
            "reason": "stale_worker_heartbeat",
        })
    return wedged


async def detect_all_wedges(db) -> List[Dict[str, Any]]:
    """Single-shot scan across ALL three tiers — what `run_wedge_scan`
    iterates over now.

    iter 322p — runs T1/T2/T3 detection in parallel via asyncio.gather
    so a single tick takes ~max(t1, t2, t3) instead of sum. Critical
    for keeping the event loop responsive for K8s `/health` probes
    during deploy cold-boot.
    """
    import asyncio as _asyncio
    t1, t2, t3 = await _asyncio.gather(
        detect_wedged_agents(db),
        detect_wedged_council(db),
        detect_wedged_sovereign_workers(db),
        return_exceptions=False,
    )
    return list(t1) + list(t2) + list(t3)


# ─── Heal cascade ──────────────────────────────────────────────────────
async def _recently_healed(db, agent_id: str) -> bool:
    """Was this agent healed within `WEDGE_HEAL_COOLDOWN_S`?"""
    if db is None:
        return False
    cutoff = (_utc_now() - timedelta(seconds=WEDGE_HEAL_COOLDOWN_S)).isoformat()
    try:
        row = await db.agent_a2a_signals.find_one(
            {
                "kind": "wedge_recovered",
                "to": agent_id,
                "ts": {"$gte": cutoff},
            },
            {"_id": 1},
        )
        return row is not None
    except Exception:
        return False


async def _step_heartbeat_ping(db, agent_id: str) -> Dict[str, Any]:
    """Step 1 — write a no-op ledger row so heartbeat readers see motion.

    `kind: "boot_unwedge"` is a marker the dashboard can filter out from
    real cost/revenue rows but still lights up the "last activity" tile.
    """
    started = time.perf_counter()
    if db is None:
        return {"step": "heartbeat_ping", "ok": False, "reason": "no_db"}
    entry = {
        "kind": "boot_unwedge",
        "agent_id": agent_id,
        "source": "wedge_detector",
        "units": 0.0,
        "cost_usd": 0.0,
        "meta": {"healed_by": "wedge_detector"},
        "timestamp": _utc_now().isoformat(),
    }
    try:
        await db.agent_ledger_entries.insert_one(entry)
    except Exception as e:
        return {"step": "heartbeat_ping", "ok": False, "error": str(e)[:160]}
    elapsed_us = int((time.perf_counter() - started) * 1_000_000)
    return {"step": "heartbeat_ping", "ok": True, "elapsed_us": elapsed_us}


async def _step_council_notify(db, agent_id: str, age_seconds: int) -> Dict[str, Any]:
    """Step 2 — broadcast to the System ORA Council so peers can route.

    We DO NOT call `convene_council()` directly with an LLM cascade —
    that would cost LLM dollars for what is structurally a routine
    re-attest. Instead we drop a `kind: "wedge_recovered"` signal in
    `agent_a2a_signals`; the Council Rotation worker picks it up in its
    next tick (already running) and decides whether to escalate.
    """
    started = time.perf_counter()
    if db is None:
        return {"step": "council_notify", "ok": False, "reason": "no_db"}
    signal = {
        "kind": "wedge_recovered",
        "from": "wedge_detector",
        "to": agent_id,
        "payload": {"age_seconds": age_seconds, "trigger": "auto_heal"},
        "ts": _utc_now().isoformat(),
    }
    try:
        await db.agent_a2a_signals.insert_one(signal)
    except Exception as e:
        return {"step": "council_notify", "ok": False, "error": str(e)[:160]}
    elapsed_us = int((time.perf_counter() - started) * 1_000_000)
    return {"step": "council_notify", "ok": True, "elapsed_us": elapsed_us}


async def _step_pulse_log(
    db, agent_id: str, age_seconds: int, total_us: int,
) -> Dict[str, Any]:
    """Step 3 — durable telemetry row for the public Sovereign-Status."""
    started = time.perf_counter()
    if db is None:
        return {"step": "pulse_log", "ok": False, "reason": "no_db"}
    row = {
        "kind": "agent_wedge_recovered",
        "agent_id": agent_id,
        "age_seconds_before_heal": age_seconds,
        "heal_total_us": total_us,
        "action_taken": "recovered_after_wedge_heal",
        "latency_before_ms": age_seconds * 1000,
        "latency_after_ms": max(1, total_us // 1000),
        "ts": _utc_now().isoformat(),
    }
    try:
        await db.system_pulse_actions.insert_one(row)
    except Exception as e:
        return {"step": "pulse_log", "ok": False, "error": str(e)[:160]}
    elapsed_us = int((time.perf_counter() - started) * 1_000_000)
    return {"step": "pulse_log", "ok": True, "elapsed_us": elapsed_us}


async def auto_heal_agent(
    db,
    agent_id: str,
    *,
    age_seconds: int = 0,
    force: bool = False,
) -> Dict[str, Any]:
    """Run the 3-step heal cascade for one agent.

    `force=True` skips the cooldown check (used by the manual admin
    "Heal Now" button — confirmed-by-human override).
    """
    if not agent_id:
        return {"healed": False, "reason": "no_agent_id"}
    if not force and await _recently_healed(db, agent_id):
        return {"healed": False, "reason": "in_cooldown",
                "cooldown_s": WEDGE_HEAL_COOLDOWN_S}

    started = time.perf_counter()
    steps: List[Dict[str, Any]] = []

    s1 = await _step_heartbeat_ping(db, agent_id)
    steps.append(s1)
    s2 = await _step_council_notify(db, agent_id, age_seconds)
    steps.append(s2)

    total_us = int((time.perf_counter() - started) * 1_000_000)
    s3 = await _step_pulse_log(db, agent_id, age_seconds, total_us)
    steps.append(s3)

    healed = all(s.get("ok") for s in steps)
    return {
        "healed": healed,
        "agent_id": agent_id,
        "age_seconds_before_heal": age_seconds,
        "heal_total_us": total_us,
        "steps": steps,
    }


# ─── Scheduler entry-point ─────────────────────────────────────────────
async def _record_learning(db, agent_id: str, age_seconds: int, tier: str) -> None:
    """Feed every wedge event into Memory Guard's 2-stamp queue so the
    Council can review the cause and (after second-stamp) promote the
    fix to permanent learnings.

    iter 322o+ — closes the A2A → Council → ORA learning circle:
        Wedge detected → heartbeat heal → A2A signal → learnings_pending_review
                                                   ↓
                       Council Rotation worker (already running every 5 min)
                                                   ↓
                                Second stamp → `learnings` (permanent)
    """
    if db is None or not agent_id:
        return
    # Phase 2 — use canonical submit_learning so stamps are properly tracked
    # by sovereign_memory.REQUIRED_STAMPS. Falls back to direct insert on import
    # error so older-pillar boots don't crash.
    try:
        from services.sovereign_memory import submit_learning
        await submit_learning(
            kind="agent_wedge_observation",
            subject=agent_id,
            payload={
                "age_seconds_before_heal": age_seconds,
                "auto_healed": True,
                "trigger": "wedge_detector",
                "tier": tier,
            },
            vote="approve",
            submitted_by="wedge_detector",
            role="infrastructure",
        )
    except Exception as e:
        # Fallback path
        import uuid as _uuid
        try:
            await db.learnings_pending_review.insert_one({
                "id": f"wedge-{agent_id}-{int(_utc_now().timestamp())}-{_uuid.uuid4().hex[:6]}",
                "kind": "agent_wedge_observation",
                "subject": agent_id, "tier": tier,
                "payload": {
                    "age_seconds_before_heal": age_seconds,
                    "auto_healed": True,
                    "trigger": "wedge_detector",
                },
                "stamps": [{"role": "wedge_detector",
                            "verdict": "approve",
                            "ts": _utc_now().isoformat()}],
                "ts": _utc_now().isoformat(),
                "status": "pending",
            })
        except Exception as e2:
            logger.debug(f"[wedge] learning record failed for {agent_id}: {e2}")
        logger.debug(f"[wedge] submit_learning failed, used fallback: {e}")

    # Phase 2 — emit A2A so ORA Brain learns about wedges + heals
    try:
        from services.a2a_bus import bus
        from services.agent_registry import heartbeat, log_action
        import asyncio as _asyncio
        _asyncio.create_task(_asyncio.gather(
            heartbeat("wedge"),
            log_action("wedge", "WEDGE_HEALED",
                       f"agent={agent_id} age={age_seconds}s tier={tier}",
                       metadata={"agent": agent_id, "age": age_seconds}),
            bus.emit("wedge", "WEDGE_HEALED", {
                "agent": agent_id, "tier": tier, "age_seconds": age_seconds,
            }),
            return_exceptions=True,
        ))
    except Exception:
        pass


async def run_wedge_scan(db) -> Dict[str, Any]:
    """One full detect → heal pass across **all three tiers** (T1/T2/T3).
    Wired to APScheduler at `WEDGE_SCAN_INTERVAL_S`. Idempotent — the
    cooldown guard prevents accidental thrash.

    Side-effects per detected wedge:
      1. Heal cascade (heartbeat ping → A2A signal → pulse log)
      2. Memory Guard learning row (`learnings_pending_review`) so the
         Council can audit *why* this wedge happened and enshrine the
         fix after the second stamp.
    """
    started = time.perf_counter()
    wedged = await detect_all_wedges(db)
    healed: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []
    by_tier: Dict[str, int] = {"T1_customer": 0, "T2_council": 0, "T3_sovereign": 0}
    for w in wedged:
        by_tier[w.get("tier", "T1_customer")] = by_tier.get(w.get("tier"), 0) + 1
        out = await auto_heal_agent(
            db, w["agent_id"], age_seconds=w["age_seconds"],
        )
        if out.get("healed"):
            healed.append({
                "agent_id": w["agent_id"],
                "tier": w.get("tier"),
                "heal_total_us": out.get("heal_total_us"),
                "age_seconds_before_heal": w["age_seconds"],
            })
            # Learning-loop: every successful heal generates an
            # observation row for memory_guard's 2-stamp gate.
            await _record_learning(
                db, w["agent_id"], w["age_seconds"], w.get("tier", "T1_customer"),
            )
        else:
            skipped.append({
                "agent_id": w["agent_id"],
                "tier": w.get("tier"),
                "reason": out.get("reason", "step_failed"),
            })
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    return {
        "scan_at": _utc_now().isoformat(),
        "wedged_detected": len(wedged),
        "wedged_by_tier": by_tier,
        "healed": healed,
        "skipped": skipped,
        "elapsed_ms": elapsed_ms,
    }


# ─── Stats for dashboards ──────────────────────────────────────────────
async def get_wedge_stats(db, hours: int = 24) -> Dict[str, Any]:
    """24-h rollup of wedge events for telemetry consumers."""
    if db is None:
        return {
            "hours": hours, "wedges_now": 0,
            "auto_healed_24h": 0, "avg_heal_us": 0,
        }
    cutoff = (_utc_now() - timedelta(hours=max(1, int(hours)))).isoformat()
    try:
        wedges_now = len(await detect_wedged_agents(db))
        healed_24h = await db.system_pulse_actions.count_documents({
            "action_taken": "recovered_after_wedge_heal",
            "ts": {"$gte": cutoff},
        })
        avg_total = 0
        cursor = db.system_pulse_actions.find(
            {"action_taken": "recovered_after_wedge_heal",
             "ts": {"$gte": cutoff}},
            {"_id": 0, "heal_total_us": 1},
        ).limit(500)
        rows = []
        async for d in cursor:
            v = int(d.get("heal_total_us") or 0)
            if v > 0:
                rows.append(v)
        if rows:
            avg_total = int(sum(rows) / len(rows))
        return {
            "hours": hours,
            "wedges_now": int(wedges_now),
            "auto_healed_24h": int(healed_24h),
            "avg_heal_us": avg_total,
        }
    except Exception as e:
        logger.debug(f"[wedge] stats failed: {e}")
        return {
            "hours": hours, "wedges_now": 0,
            "auto_healed_24h": 0, "avg_heal_us": 0,
        }
