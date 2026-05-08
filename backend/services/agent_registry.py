"""
AUREM Agent Registry — Phase 0
==============================
Single source of truth for all 20 platform agents.

- Batched heartbeats (in-memory dict, flushed to MongoDB every 30s).
- Batched action logs (insert_many at 20-event threshold OR on flush).
- Mirror writes to `ora_brain_thoughts` so ORA Brain sees every action.

Public:
  await heartbeat(agent)
  await log_action(agent, action, result, lead_id=None,
                   metadata=None, success=True)
  await flush_heartbeats()  # called by 30s scheduler
  await flush_actions()     # also called periodically + on threshold
  AGENT_REGISTRY            # dict
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pymongo import UpdateOne

logger = logging.getLogger(__name__)

# ─── Canonical agent registry (T1/T2/T3/T4) ──────────────────────────
AGENT_REGISTRY: Dict[str, str] = {
    # T1 Pipeline
    "scout":        "services/total_scout.py",
    "hunter":       "services/agents/hunter_ora.py",
    "envoy":        "services/auto_blast_engine.py",
    "followup":     "services/agents/followup_ora.py",
    "closer":       "services/agents/closer_ora.py",
    "referral":     "services/agents/referral_ora.py",
    # T2 Council
    "casl":         "services/casl_compliance.py",
    "qa":           "services/qa_agent_deep.py",
    "security":     "services/aurem_skills/security_review.py",
    "pricing":      "services/agents/pricing_agent.py",
    "council":      "services/council_rotation.py",
    # T3 Sovereign
    "wedge":        "services/agent_wedge_detector.py",
    "watchdog":     "services/sovereign_watchdog.py",
    "memory_guard": "services/sovereign_memory.py",
    "learning_bus": "services/sovereign_memory.py",
    # T4 ORA
    "ora_brain":    "services/ora_brain.py",
    "ora_console":  "services/ora_command_center.py",
    "ora_brief":    "services/morning_brief.py",
    "ora_voice":    "routers/voice_agent_router.py",
    "ora_widget":   "routers/ora_support_router.py",
}

# In-memory batching buffers
_hb_buffer: Dict[str, datetime] = {}
_action_buffer: List[Dict[str, Any]] = []
_action_lock = asyncio.Lock()

ACTION_FLUSH_THRESHOLD = 20


def _get_db():
    try:
        import server
        return getattr(server, "db", None)
    except Exception:
        return None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ─── Heartbeats ──────────────────────────────────────────────────────

async def heartbeat(agent: str) -> None:
    """Mark agent as alive — buffered, flushed by scheduler."""
    if agent not in AGENT_REGISTRY:
        logger.debug(f"[registry] unknown agent: {agent}")
    _hb_buffer[agent] = _utc_now()


async def flush_heartbeats() -> int:
    """Bulk-write buffered heartbeats to MongoDB."""
    if not _hb_buffer:
        return 0
    db = _get_db()
    if db is None:
        return 0
    snapshot = dict(_hb_buffer)
    _hb_buffer.clear()
    ops = [
        UpdateOne(
            {"agent": name},
            {
                "$set": {"last_seen": ts, "status": "active"},
                "$setOnInsert": {"file": AGENT_REGISTRY.get(name, "?")},
            },
            upsert=True,
        )
        for name, ts in snapshot.items()
    ]
    try:
        await db.agent_heartbeats.bulk_write(ops, ordered=False)
        return len(ops)
    except Exception as e:
        # Restore buffer so next flush retries
        for k, v in snapshot.items():
            _hb_buffer.setdefault(k, v)
        logger.warning(f"[registry] heartbeat flush failed: {e}")
        return 0


# ─── Action logs ─────────────────────────────────────────────────────

async def log_action(
    agent: str,
    action: str,
    result: str,
    *,
    lead_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    success: bool = True,
) -> None:
    """Buffered action log. Auto-flushes at threshold."""
    doc = {
        "agent": agent,
        "action": action,
        "result": str(result)[:1000],
        "lead_id": lead_id,
        "metadata": metadata or {},
        "success": bool(success),
        "ts": _utc_now(),
    }
    async with _action_lock:
        _action_buffer.append(doc)
        should_flush = len(_action_buffer) >= ACTION_FLUSH_THRESHOLD
    if should_flush:
        await flush_actions()


async def flush_actions() -> int:
    """Bulk-insert buffered actions + mirror to ora_brain_thoughts."""
    db = _get_db()
    if db is None:
        return 0
    async with _action_lock:
        if not _action_buffer:
            return 0
        snapshot = list(_action_buffer)
        _action_buffer.clear()

    try:
        await asyncio.gather(
            db.agent_actions.insert_many(snapshot),
            db.ora_brain_thoughts.insert_many([
                {
                    "source": a["agent"],
                    "event": a["action"],
                    "summary": a["result"],
                    "lead_id": a.get("lead_id"),
                    "success": a.get("success", True),
                    "ts": a["ts"],
                }
                for a in snapshot
            ]),
        )
        return len(snapshot)
    except Exception as e:
        logger.warning(f"[registry] action flush failed: {e}")
        # Restore buffer
        async with _action_lock:
            _action_buffer.extend(snapshot)
        return 0


# ─── Periodic flush scheduler ────────────────────────────────────────

async def registry_flush_scheduler():
    """Forever loop — flush heartbeats + actions every 30s."""
    print("[registry] flush scheduler alive — 30s interval", flush=True)
    while True:
        try:
            await asyncio.sleep(30)
            await asyncio.gather(
                flush_heartbeats(),
                flush_actions(),
                return_exceptions=True,
            )
        except asyncio.CancelledError:
            # Final drain on shutdown
            await asyncio.gather(
                flush_heartbeats(),
                flush_actions(),
                return_exceptions=True,
            )
            raise
        except Exception as e:
            logger.error(f"[registry] flush scheduler error: {e}",
                         exc_info=True)
            await asyncio.sleep(15)
