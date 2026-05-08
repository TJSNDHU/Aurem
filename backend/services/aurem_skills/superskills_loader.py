"""
SuperSkills Loader
==================
Loads Keshav Sharma's superskills JSON manifests into AUREM's SkillsManager.

Each skill is a prompt-engineered persona with triggers, tools, and a system
prompt. When an agent asks a question that matches a skill's trigger words,
the router can apply that skill's system prompt to shape the model's response.

Credit: github.com/Keshavsharma-code/superskills

Loading order:
    1. Scan /app/backend/services/aurem_skills/superskills/*/*.json
    2. Parse each manifest (id, name, triggers, compatibility, prompts.system)
    3. Register in SkillsManager.superskills registry (in-memory)

Triggered selection:
    match_skills(query_text, agent="claude") → list of matching superskills
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

SUPERSKILLS_ROOT = Path(__file__).parent / "superskills"
_REGISTRY: Dict[str, Dict[str, Any]] = {}
_LOADED = False


def _load_all() -> Dict[str, Dict[str, Any]]:
    """One-time scan of the superskills directory into the registry."""
    global _LOADED
    if _LOADED:
        return _REGISTRY
    if not SUPERSKILLS_ROOT.exists():
        logger.warning(f"[SuperSkills] {SUPERSKILLS_ROOT} not found, registry empty")
        _LOADED = True
        return _REGISTRY

    count = 0
    for agent_dir in sorted(SUPERSKILLS_ROOT.iterdir()):
        if not agent_dir.is_dir() or agent_dir.name.startswith("_"):
            continue
        for manifest_path in agent_dir.glob("*.json"):
            try:
                data = json.loads(manifest_path.read_text(encoding="utf-8"))
                sid = data.get("id") or f"{agent_dir.name}-{manifest_path.stem}"
                data["_agent"] = agent_dir.name
                data["_path"] = str(manifest_path)
                _REGISTRY[sid] = data
                count += 1
            except Exception as exc:
                logger.warning(f"[SuperSkills] skipped {manifest_path}: {exc}")

    _LOADED = True
    logger.info(f"[SuperSkills] Loaded {count} skills across {len(_REGISTRY)} IDs")
    return _REGISTRY


def list_skills(
    agent: Optional[str] = None, category: Optional[str] = None
) -> List[Dict[str, Any]]:
    """List all loaded superskills, optionally filtered by agent or category."""
    reg = _load_all()
    out = []
    for sid, skill in reg.items():
        if agent and agent not in (skill.get("compatibility", []) + [skill.get("_agent")]):
            continue
        if category and skill.get("category") != category:
            continue
        out.append(
            {
                "id": sid,
                "name": skill.get("name"),
                "description": skill.get("description"),
                "category": skill.get("category"),
                "agent": skill.get("_agent"),
                "compatibility": skill.get("compatibility", []),
                "triggers": skill.get("triggers", []),
                "tools_required": skill.get("tools_required", []),
            }
        )
    return out


def get_skill(skill_id: str) -> Optional[Dict[str, Any]]:
    """Fetch a single superskill manifest by id."""
    reg = _load_all()
    return reg.get(skill_id)


def match_skills(
    query: str, agent: str = "claude", limit: int = 3
) -> List[Dict[str, Any]]:
    """
    Return the top-N superskills whose triggers appear in the query text.
    Used by Shannon/ORA routers to augment system prompts dynamically.
    """
    reg = _load_all()
    q = (query or "").lower()
    scored = []
    for sid, skill in reg.items():
        compat = skill.get("compatibility", []) + [skill.get("_agent", "")]
        if agent and "all" not in compat and agent not in compat:
            continue
        triggers = [str(t).lower() for t in skill.get("triggers", [])]
        score = sum(1 for t in triggers if t and t in q)
        if score:
            scored.append((score, sid, skill))
    scored.sort(key=lambda x: -x[0])
    return [
        {
            "id": sid,
            "name": skill.get("name"),
            "score": score,
            "system_prompt": skill.get("prompts", {}).get("system", ""),
            "tools_required": skill.get("tools_required", []),
        }
        for score, sid, skill in scored[:limit]
    ]


def build_augmented_prompt(
    base_system_prompt: str, query: str, agent: str = "claude", limit: int = 2
) -> str:
    """
    Inject matched superskill system prompts into the base system prompt.
    Returns the enriched prompt string for the LLM call.
    """
    matches = match_skills(query, agent=agent, limit=limit)
    if not matches:
        return base_system_prompt
    skill_blocks = "\n\n".join(
        f"## Skill: {m['name']}\n{m['system_prompt']}"
        for m in matches
        if m.get("system_prompt")
    )
    if not skill_blocks:
        return base_system_prompt
    return f"{base_system_prompt}\n\n--- SuperSkills Augmentation ---\n{skill_blocks}"


def registry_stats() -> Dict[str, Any]:
    """Admin stats for the superskills registry."""
    reg = _load_all()
    agents: Dict[str, int] = {}
    categories: Dict[str, int] = {}
    for skill in reg.values():
        a = skill.get("_agent", "unknown")
        c = skill.get("category", "uncategorized")
        agents[a] = agents.get(a, 0) + 1
        categories[c] = categories.get(c, 0) + 1
    return {
        "total": len(reg),
        "by_agent": agents,
        "by_category": categories,
        "source": str(SUPERSKILLS_ROOT),
    }
