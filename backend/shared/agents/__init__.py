"""
AUREM Agent Base + Registry
============================
Abstract base class for the 4 autonomous agents.
Each agent reuses existing AUREM services as its engine (Hunter reuses
`hunt_live`, Follow-up reuses `drip_sequencer`, Closer reuses `flame_auto_dialer`,
Referral is new).

Agents communicate via `services.a2a_bus.bus`.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from services.a2a_bus import bus

logger = logging.getLogger(__name__)


class AuremAgent(ABC):
    """Base class for all 4 AUREM agents."""
    # Each concrete agent sets these
    AGENT_ID: str = ""
    AGENT_NAME: str = ""
    AGENT_EMOJI: str = "🤖"
    AGENT_JOB: str = ""

    def __init__(self, db):
        self.db = db
        self._paused: bool = False
        # LIVE MODE — dry-run system removed (iter 263). Agents now always
        # run real outbound actions, guarded only by `daily_cap`.
        self.daily_cap: int = int(__import__("os").environ.get("AUREM_AGENT_DAILY_CAP", "20"))
        self._today_stats: Dict[str, int] = {}
        self._last_run_at: Optional[str] = None
        self._current_task: str = "idle"

    # ─── Lifecycle ─────────────────────────────────────────────
    async def pause(self):
        self._paused = True
        await bus.emit(self.AGENT_ID, "paused", {"agent": self.AGENT_ID})

    async def resume(self):
        self._paused = False
        await bus.emit(self.AGENT_ID, "resumed", {"agent": self.AGENT_ID})

    @property
    def paused(self) -> bool:
        return self._paused

    # ─── Core execution (subclass must implement) ──────────────
    @abstractmethod
    async def run_cycle(self) -> Dict[str, Any]:
        """Run one tick of the agent's work. Return stats dict."""
        ...

    # ─── Admin snapshot ────────────────────────────────────────
    def snapshot(self) -> Dict[str, Any]:
        """What the Admin Command Center displays for this agent."""
        sent_today = sum(self._today_stats.values()) if self._today_stats else 0
        return {
            "agent_id": self.AGENT_ID,
            "name": self.AGENT_NAME,
            "emoji": self.AGENT_EMOJI,
            "job": self.AGENT_JOB,
            "status": "paused" if self._paused else "active",
            "daily_cap": self.daily_cap,
            "sent_today": sent_today,
            "cap_reached": sent_today >= self.daily_cap,
            "current_task": self._current_task,
            "today_stats": self._today_stats.copy(),
            "last_run_at": self._last_run_at,
        }

    def can_send(self) -> bool:
        """Check daily cap before real outbound action."""
        sent_today = sum(self._today_stats.values()) if self._today_stats else 0
        return sent_today < self.daily_cap

    # ─── A2A helpers ───────────────────────────────────────────
    async def notify(self, to_agent: str, event: str, payload: Dict[str, Any]):
        return await bus.emit(self.AGENT_ID, event, payload, to_agent=to_agent)

    async def broadcast(self, event: str, payload: Dict[str, Any]):
        return await bus.emit(self.AGENT_ID, event, payload, to_agent=None)

    def mark_task(self, label: str):
        self._current_task = label
        self._last_run_at = datetime.now(timezone.utc).isoformat()


# ═══════════════════════════════════════════
# Agent Registry — all agents live here
# ═══════════════════════════════════════════
_agents: Dict[str, AuremAgent] = {}


def register_agents(db):
    """Instantiate all 4 agents and register them. Called at startup.

    iter 322au — made resilient to missing agent classes so a single
    missing module doesn't break the whole startup path. Each agent is
    imported individually; failures are logged and skipped.
    """
    # iter 322ev — agent classes live in `shared.agents.*`. The
    # `services.agents.*` paths are shim modules and do NOT re-export the
    # class symbols, so `getattr(mod, cls_name)` returned None for every
    # agent, spamming a warning per agent on every startup. Import from
    # the canonical location.
    agent_specs = [
        ("shared.agents.hunter_ora",   "HunterORA"),
        ("shared.agents.followup_ora", "FollowupORA"),
        ("shared.agents.closer_ora",   "CloserORA"),
        ("shared.agents.referral_ora", "ReferralORA"),
    ]
    for mod_path, cls_name in agent_specs:
        try:
            mod = __import__(mod_path, fromlist=[cls_name])
            cls = getattr(mod, cls_name, None)
            if cls is None:
                logger.warning(f"[Agents] {cls_name} not found in {mod_path} — skipped")
                continue
            agent = cls(db)
            _agents[agent.AGENT_ID] = agent
            logger.info(f"[Agents] Registered: {agent.AGENT_EMOJI} {agent.AGENT_NAME}")
        except Exception as e:
            logger.warning(f"[Agents] {cls_name} init failed — skipped ({e})")

    try:
        bus.set_db(db)
    except Exception as e:
        logger.warning(f"[Agents] bus.set_db failed: {e}")
    return _agents


# Bi-directional aliases so both short (`hunter`) and full (`hunter_ora`) IDs
# are accepted from ANY consumer (frontend, webhooks, tests, SSE clients).
# Prevents future ID-drift regressions at the source of truth.
_AGENT_ALIAS = {
    "hunter":   "hunter_ora",
    "followup": "followup_ora",
    "closer":   "closer_ora",
    "referral": "referral_ora",
    # self-map (already canonical)
    "hunter_ora":   "hunter_ora",
    "followup_ora": "followup_ora",
    "closer_ora":   "closer_ora",
    "referral_ora": "referral_ora",
}


def get_agent(agent_id: str) -> Optional[AuremAgent]:
    canonical = _AGENT_ALIAS.get((agent_id or "").strip().lower(), agent_id)
    return _agents.get(canonical)


def all_agents() -> List[AuremAgent]:
    return list(_agents.values())
