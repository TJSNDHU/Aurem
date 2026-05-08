"""
AUREM A2A Agent Cards — Decoupled Swarm Registry
=================================================
Central registry defining capabilities for all agents.
Follows the Google A2A 'Decoupled' pattern: agents advertise their
AgentCards, and the Architect delegates tasks based on capability match.

BitNet/Tiny-Model workers register their own cards on startup,
allowing the Architect to auto-delegate stable tasks to lightweight models.
"""
import os
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any
from enum import Enum

logger = logging.getLogger(__name__)

# ═══ AGENT CARD SCHEMA ═══

class AgentCard:
    """Defines an agent's identity, capabilities, and routing rules."""

    def __init__(
        self,
        agent_id: str,
        name: str,
        role: str,
        description: str,
        capabilities: List[str],
        intent_triggers: List[str],
        model: str = "llama3.1",
        engine: str = "sovereign",
        is_worker: bool = False,
        max_tokens: int = 500,
        priority: int = 5,
        status: str = "active",
    ):
        self.agent_id = agent_id
        self.name = name
        self.role = role
        self.description = description
        self.capabilities = capabilities
        self.intent_triggers = intent_triggers
        self.model = model
        self.engine = engine
        self.is_worker = is_worker
        self.max_tokens = max_tokens
        self.priority = priority
        self.status = status
        self.registered_at = datetime.now(timezone.utc).isoformat()
        self.last_execution = None
        self.execution_count = 0
        self.success_count = 0

    def to_dict(self) -> Dict:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "role": self.role,
            "description": self.description,
            "capabilities": self.capabilities,
            "intent_triggers": self.intent_triggers,
            "model": self.model,
            "engine": self.engine,
            "is_worker": self.is_worker,
            "max_tokens": self.max_tokens,
            "priority": self.priority,
            "status": self.status,
            "registered_at": self.registered_at,
            "last_execution": self.last_execution,
            "execution_count": self.execution_count,
            "success_count": self.success_count,
            "success_rate": round(self.success_count / max(self.execution_count, 1) * 100, 1),
        }


# ═══ GLOBAL REGISTRY ═══

_registry: Dict[str, AgentCard] = {}

# Swarm execution log (ring buffer for Overwatch)
_swarm_log: List[Dict] = []
_MAX_LOG = 100


def _init_default_cards():
    """Initialize the 5 core business agent cards + ORACLE."""
    defaults = [
        AgentCard(
            agent_id="scout",
            name="SCOUT",
            role="scout",
            description="Lead discovery and qualification agent. Scans websites, identifies prospects, scores leads.",
            capabilities=["lead_discovery", "website_scan", "lead_scoring", "prospect_research", "market_analysis"],
            intent_triggers=["find leads", "scan website", "who are our prospects", "lead", "prospect", "discovery"],
            model="llama3.1",
            engine="sovereign",
            priority=3,
        ),
        AgentCard(
            agent_id="envoy",
            name="ENVOY",
            role="envoy",
            description="Outreach and communication agent. Sends emails, WhatsApp, SMS. Manages campaign sequences.",
            capabilities=["email_send", "whatsapp_send", "sms_send", "campaign_management", "follow_up", "template_generation"],
            intent_triggers=["send email", "outreach", "campaign", "follow up", "whatsapp", "contact", "message"],
            model="llama3.1",
            engine="sovereign",
            priority=4,
        ),
        AgentCard(
            agent_id="closer",
            name="CLOSER",
            role="closer",
            description="Deal closure and deployment agent. Deploys fixes, processes payments, onboards clients.",
            capabilities=["deploy_fix", "process_payment", "client_onboard", "contract_generation", "deal_close"],
            intent_triggers=["close deal", "deploy", "fix", "payment", "onboard", "invoice", "contract"],
            model="llama3.1",
            engine="sovereign",
            priority=5,
        ),
        AgentCard(
            agent_id="oracle",
            name="ORACLE",
            role="oracle",
            description="Forecasting and analytics agent. Predicts churn, forecasts revenue, generates morning briefs.",
            capabilities=["revenue_forecast", "churn_prediction", "analytics", "morning_brief", "trend_analysis", "kpi_report"],
            intent_triggers=["forecast", "predict", "analytics", "revenue", "churn", "report", "brief", "dashboard", "metrics", "how many"],
            model="llama3.1",
            engine="sovereign",
            priority=2,
        ),
        AgentCard(
            agent_id="architect",
            name="ARCHITECT",
            role="architect",
            description="System orchestration agent. Routes tasks, manages infrastructure, delegates to workers.",
            capabilities=["task_routing", "agent_delegation", "system_health", "worker_management", "infrastructure", "scaling"],
            intent_triggers=["system", "architecture", "infrastructure", "scale", "optimize", "delegate", "worker"],
            model="llama3.1",
            engine="sovereign",
            priority=1,
        ),
        AgentCard(
            agent_id="voice",
            name="VOICE",
            role="voice",
            description="Sovereign Voice identity agent. Narrates responses using XTTS v2 on the Legion GPU. Sub-200ms first-byte streaming.",
            capabilities=["voice_synthesis", "voice_identity", "skill_narration", "audio_streaming", "voice_clone"],
            intent_triggers=["speak", "say", "voice", "read aloud", "narrate", "audio", "listen"],
            model="xtts_v2",
            engine="sovereign_voice",
            priority=8,
        ),
        AgentCard(
            agent_id="shannon",
            name="SHANNON",
            role="security_auditor",
            description="Autonomous Red Team pentester. Scans source code, identifies attack vectors, and executes exploits to verify vulnerabilities. Runs on Legion hardware via Shannon/KeygraphHQ.",
            capabilities=["pentest", "vulnerability_scan", "exploit_verification", "code_audit", "attack_surface_mapping", "security_report"],
            intent_triggers=["security", "pentest", "vulnerability", "exploit", "audit security", "red team", "attack surface", "breach"],
            model="shannon_local",
            engine="sovereign",
            priority=9,
            status="awaiting_audit",
        ),
    ]

    for card in defaults:
        _registry[card.agent_id] = card

    logger.info(f"[A2A] Initialized {len(defaults)} core agent cards")


# Initialize on import
_init_default_cards()


# ═══ REGISTRY OPERATIONS ═══

def register_agent(card: AgentCard) -> Dict:
    """Register or update an agent card in the registry."""
    _registry[card.agent_id] = card
    logger.info(f"[A2A] Registered agent: {card.name} ({card.engine}/{card.model})")
    _log_swarm_event("register", card.agent_id, f"{card.name} registered ({card.engine}/{card.model})")
    return card.to_dict()


def register_worker(
    skill_name: str,
    capabilities: List[str],
    model: str = "qwen2:0.5b",
) -> Dict:
    """Register a BitNet worker as an agent in the swarm."""
    agent_id = f"worker_{skill_name}"
    card = AgentCard(
        agent_id=agent_id,
        name=f"WORKER:{skill_name}",
        role="worker",
        description=f"BitNet micro-worker for offloaded skill: {skill_name}",
        capabilities=capabilities,
        intent_triggers=[skill_name.replace("-", " "), skill_name.replace("_", " ")],
        model=model,
        engine="bitnet",
        is_worker=True,
        max_tokens=200,
        priority=10,
    )
    _registry[agent_id] = card
    logger.info(f"[A2A] BitNet worker registered: {skill_name} → {model}")
    _log_swarm_event("worker_register", agent_id, f"BitNet worker for '{skill_name}' registered on {model}")
    return card.to_dict()


def unregister_agent(agent_id: str) -> bool:
    """Remove an agent from the registry."""
    if agent_id in _registry:
        del _registry[agent_id]
        _log_swarm_event("unregister", agent_id, f"Agent {agent_id} removed from swarm")
        return True
    return False


def get_agent_card(agent_id: str) -> Optional[Dict]:
    """Get a specific agent's card."""
    card = _registry.get(agent_id)
    return card.to_dict() if card else None


def get_all_cards() -> List[Dict]:
    """Get all agent cards in the registry."""
    return [card.to_dict() for card in _registry.values()]


def find_agent_for_task(query: str, prefer_worker: bool = True) -> Optional[Dict]:
    """
    Match a task query to the best agent based on intent triggers and capabilities.
    If prefer_worker=True and a BitNet worker matches, prefer it (cheaper).
    """
    query_lower = query.lower()
    query_words = set(query_lower.split())

    scored = []
    for card in _registry.values():
        if card.status != "active":
            continue

        score = 0
        # Intent trigger matching
        for trigger in card.intent_triggers:
            trigger_words = set(trigger.lower().split())
            overlap = len(query_words & trigger_words)
            if overlap > 0:
                score += overlap * 3

        # Capability matching
        for cap in card.capabilities:
            cap_words = set(cap.lower().replace("_", " ").split())
            if len(query_words & cap_words) > 0:
                score += 2

        # Worker bonus (cheaper execution)
        if prefer_worker and card.is_worker and score > 0:
            score += 5

        if score > 0:
            scored.append((score, card))

    if not scored:
        return None

    scored.sort(key=lambda x: (-x[0], x[1].priority))
    best = scored[0][1]
    return best.to_dict()


def record_execution(agent_id: str, success: bool, task: str = "", latency_ms: int = 0):
    """Record an agent execution for stats tracking."""
    card = _registry.get(agent_id)
    if card:
        card.execution_count += 1
        if success:
            card.success_count += 1
        card.last_execution = datetime.now(timezone.utc).isoformat()

    status = "success" if success else "failed"
    _log_swarm_event("execute", agent_id, f"{task[:80]} → {status} ({latency_ms}ms)")


# ═══ SWARM EXECUTION LOG ═══

def _log_swarm_event(event_type: str, agent_id: str, detail: str):
    """Log a swarm event for Overwatch visibility."""
    _swarm_log.append({
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event_type,
        "agent": agent_id,
        "detail": detail,
    })
    if len(_swarm_log) > _MAX_LOG:
        _swarm_log.pop(0)


def get_swarm_log(limit: int = 20) -> List[Dict]:
    """Get recent swarm execution log entries."""
    return _swarm_log[-limit:]


def get_swarm_stats() -> Dict:
    """Get swarm-level statistics for Overwatch."""
    total_agents = len(_registry)
    core_agents = sum(1 for c in _registry.values() if not c.is_worker)
    workers = sum(1 for c in _registry.values() if c.is_worker)
    active = sum(1 for c in _registry.values() if c.status == "active")
    total_execs = sum(c.execution_count for c in _registry.values())
    total_success = sum(c.success_count for c in _registry.values())

    return {
        "total_agents": total_agents,
        "core_agents": core_agents,
        "workers": workers,
        "active": active,
        "total_executions": total_execs,
        "success_rate": round(total_success / max(total_execs, 1) * 100, 1),
        "swarm_log": _swarm_log[-10:],
        "agents": {c.agent_id: {"name": c.name, "engine": c.engine, "model": c.model, "execs": c.execution_count, "is_worker": c.is_worker} for c in _registry.values()},
    }
