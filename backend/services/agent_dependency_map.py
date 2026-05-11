"""
AUREM Agent Dependency Map — iter 322ar
=========================================
Hard-coded map of the 25 ORA-agent collective + their feeds/depends-on
relationships. Used by the Collective Scanner to find root causes and
order council fixes by cascade impact.

Contract:
    feeds       : agents this agent supplies data/leads/decisions to
    depends_on  : agents this agent needs upstream to function
    scan_kind   : how the scanner derives this agent's health
                  (collection_recent | scheduler_job | counter |
                  custom_callable)

Usage:
    from services.agent_dependency_map import DEPENDENCY_MAP, downstream_of
    downstream_of("scout_ora")   # → {hunter_ora, followup_ora, closer_ora, …}
"""

from typing import Dict, List, Set


# All 25 agents in the AUREM collective.
# `scan` field tells the collective scanner where to look:
#   ("recent", "<mongo_col>", <fresh_minutes>)
#   ("count",  "<mongo_col>", <min_docs>)
#   ("scheduler", "<job_id>",  <max_late_seconds>)
DEPENDENCY_MAP: Dict[str, Dict] = {
    # ── Outbound funnel ──────────────────────────────────────────────
    "scout_ora": {
        "feeds": ["hunter_ora", "intel_merge_agent", "morning_brief_agent"],
        "depends_on": ["birdeye_agent", "apollo_agent", "duckduckgo_search"],
        "scan": ("recent", "scout_runs", 720),  # 12 h
    },
    "hunter_ora": {
        "feeds": ["followup_ora", "campaign_agent"],
        "depends_on": ["scout_ora"],
        "scan": ("recent", "leads", 360),  # 6 h
    },
    "followup_ora": {
        "feeds": ["closer_ora", "inbox_agent"],
        "depends_on": ["hunter_ora", "campaign_agent"],
        "scan": ("recent", "ora_dev_actions", 360),
    },
    "closer_ora": {
        "feeds": ["pipeline_promoter"],
        "depends_on": ["followup_ora", "voice_agent"],
        "scan": ("count", "comm_leads", 1),
    },
    "pipeline_promoter": {
        "feeds": ["morning_brief_agent"],
        "depends_on": ["closer_ora"],
        "scan": ("recent", "campaign_leads", 1440),  # 24 h
    },

    # ── Intel + scraping ─────────────────────────────────────────────
    "intel_merge_agent": {
        "feeds": ["morning_brief_agent", "inbox_agent"],
        "depends_on": ["scout_ora"],
        "scan": ("count", "bin_intelligence", 1),
    },
    "birdeye_agent": {
        "feeds": ["scout_ora"],
        "depends_on": [],
        "scan": ("count", "birdeye_reviews_cache", 0),
    },
    "apollo_agent": {
        "feeds": ["scout_ora"],
        "depends_on": [],
        "scan": ("count", "apollo_lookups", 0),
    },
    "duckduckgo_search": {
        "feeds": ["scout_ora", "webclaw_agent"],
        "depends_on": [],
        "scan": ("count", "search_queries", 0),
    },
    "webclaw_agent": {
        "feeds": ["intel_merge_agent"],
        "depends_on": ["duckduckgo_search"],
        "scan": ("recent", "webclaw_runs", 1440),
    },

    # ── Comms + execution ────────────────────────────────────────────
    "inbox_agent": {
        "feeds": ["followup_ora", "morning_brief_agent"],
        "depends_on": ["campaign_agent"],
        "scan": ("count", "unified_inbox", 0),
    },
    "campaign_agent": {
        "feeds": ["followup_ora", "inbox_agent"],
        "depends_on": ["hunter_ora"],
        "scan": ("recent", "campaign_messages_log", 720),
    },
    "voice_agent": {
        "feeds": ["closer_ora", "inbox_agent"],
        "depends_on": ["sovereign_warmer"],
        "scan": ("count", "voice_call_logs", 0),
    },

    # ── ORA brain ────────────────────────────────────────────────────
    "ora_brain": {
        "feeds": ["dev_loop", "morning_brief_agent", "council_agent"],
        "depends_on": ["sovereign_warmer", "groq_gateway"],
        "scan": ("recent", "ora_brain_thoughts", 60),
    },
    "council_agent": {
        "feeds": ["dev_loop", "truth_ledger_agent"],
        "depends_on": ["sentinel_agent", "ora_brain"],
        "scan": ("recent", "council_decisions", 1440),
    },
    "evolver_agent": {
        "feeds": ["ora_brain"],
        "depends_on": ["a2a_bus"],
        "scan": ("count", "evolver_events", 0),
    },

    # ── Self-healing ─────────────────────────────────────────────────
    "sentinel_agent": {
        "feeds": ["council_agent", "dev_loop"],
        "depends_on": ["error_ledger", "anomaly_detector"],
        "scan": ("recent", "sentinel_runs", 60),
    },
    "dev_loop": {
        "feeds": ["truth_ledger_agent"],
        "depends_on": ["council_agent", "sentinel_agent"],
        "scan": ("recent", "ora_dev_actions", 1440),
    },
    "truth_ledger_agent": {
        "feeds": [],
        "depends_on": ["council_agent", "dev_loop"],
        "scan": ("count", "truth_ledger", 0),
    },
    "anomaly_detector": {
        "feeds": ["sentinel_agent"],
        "depends_on": ["a2a_bus"],
        "scan": ("recent", "anomaly_events", 1440),
    },
    "error_ledger": {
        "feeds": ["sentinel_agent"],
        "depends_on": [],
        "scan": ("count", "error_ledger", 0),
    },

    # ── Infra ────────────────────────────────────────────────────────
    "groq_gateway": {
        "feeds": ["ora_brain", "evolver_agent"],
        "depends_on": [],
        "scan": ("count", "llm_gateway_log", 0),
    },
    "sovereign_warmer": {
        "feeds": ["ora_brain", "voice_agent"],
        "depends_on": [],
        "scan": ("recent", "sovereign_warmer_log", 30),
    },
    "a2a_bus": {
        "feeds": ["evolver_agent", "anomaly_detector"],
        "depends_on": [],
        "scan": ("recent", "a2a_messages", 720),
    },
    "morning_brief_agent": {
        "feeds": [],
        "depends_on": [
            "scout_ora", "intel_merge_agent", "inbox_agent",
            "pipeline_promoter", "ora_brain",
        ],
        "scan": ("recent", "morning_briefs", 1440),
    },
}


ALL_AGENTS: List[str] = list(DEPENDENCY_MAP.keys())


def downstream_of(agent: str) -> Set[str]:
    """Recursively collect every agent that depends on `agent` (directly or
    indirectly). Used to compute cascade impact when an agent is broken."""
    if agent not in DEPENDENCY_MAP:
        return set()
    out: Set[str] = set()
    stack = list(DEPENDENCY_MAP[agent].get("feeds", []))
    while stack:
        a = stack.pop()
        if a in out or a not in DEPENDENCY_MAP:
            continue
        out.add(a)
        stack.extend(DEPENDENCY_MAP[a].get("feeds", []))
    return out


def upstream_of(agent: str) -> Set[str]:
    """Reverse — every agent that must be healthy for `agent` to work."""
    if agent not in DEPENDENCY_MAP:
        return set()
    out: Set[str] = set()
    stack = list(DEPENDENCY_MAP[agent].get("depends_on", []))
    while stack:
        a = stack.pop()
        if a in out or a not in DEPENDENCY_MAP:
            continue
        out.add(a)
        stack.extend(DEPENDENCY_MAP[a].get("depends_on", []))
    return out
