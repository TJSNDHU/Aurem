"""
Agent Skill Broadcast — shared helper read by all 28 internal agents.

When an admin broadcasts a set of antigravity skills via
`/api/admin/antigravity-skills/broadcast`, the singleton doc
`ora_skills_broadcast/_id=active` is updated with a `system_addendum`.

Every agent imports this module and calls `get_addendum(db, agent_name)`
right before constructing its LLM call. The returned string is appended
to the agent's existing system prompt, so the agent instantly inherits
the broadcasted skills (no redeploy, no restart needed).

A small per-agent TTL cache (15s) avoids hitting Mongo on every turn.
"""
from __future__ import annotations

import time
from typing import Optional

# {agent_name: (expires_at_epoch, addendum_str, skill_ids_tuple)}
_CACHE: dict[str, tuple[float, str, tuple[str, ...]]] = {}
_TTL_S = 15.0


async def get_active_broadcast(db) -> Optional[dict]:
    """Return the active broadcast doc, or None.

    Direct accessor for code that needs full metadata.
    """
    if db is None:
        return None
    return await db.ora_skills_broadcast.find_one({"_id": "active"}, {"_id": 0})


async def get_addendum(db, agent_name: str = "ALL") -> str:
    """Return the system-prompt addendum the agent should append.

    Returns "" when no broadcast is active or this agent is not targeted.
    Cached for 15 seconds per agent_name.
    """
    now = time.time()
    entry = _CACHE.get(agent_name)
    if entry and entry[0] > now:
        return entry[1]

    doc = await get_active_broadcast(db)
    if not doc:
        _CACHE[agent_name] = (now + _TTL_S, "", ())
        return ""

    targets = doc.get("target_agents", "ALL")
    if targets != "ALL" and agent_name not in targets:
        _CACHE[agent_name] = (now + _TTL_S, "", ())
        return ""

    addendum = doc.get("system_addendum") or ""
    if not addendum:
        _CACHE[agent_name] = (now + _TTL_S, "", ())
        return ""

    full = (
        "\n\n=== ANTIGRAVITY SKILLS — LIVE BROADCAST ===\n"
        "(Use these playbooks when relevant to the task.)\n"
        f"{addendum}\n"
        "=== END BROADCAST ===\n"
    )
    _CACHE[agent_name] = (
        now + _TTL_S,
        full,
        tuple(doc.get("skill_ids") or []),
    )
    return full


def invalidate_cache() -> None:
    """Called when an admin updates the broadcast — agents pick up the
    change on their next call."""
    _CACHE.clear()
