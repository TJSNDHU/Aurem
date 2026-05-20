"""
PreCompact Hook — ORA State Persistence
========================================

Ported from everything-claude-code's strategic-compact pattern.
Saves ORA's current state to MEMORY.md before context gets too long.

Triggered:
  - After every 10 ORA chat messages per session
  - Before a daily sweep (to preserve yesterday's state)
  - Manually via API

Ensures MEMORY.md stays perfect even across context compactions.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Optional

logger = logging.getLogger(__name__)

_db = None


def set_db(database):
    global _db
    _db = database


# Track message counts per session for auto-compact
_session_msg_counts: Dict[str, int] = {}
COMPACT_THRESHOLD = 10


async def should_precompact(session_id: str) -> bool:
    """Check if a session has hit the compact threshold."""
    count = _session_msg_counts.get(session_id, 0) + 1
    _session_msg_counts[session_id] = count
    return count >= COMPACT_THRESHOLD and count % COMPACT_THRESHOLD == 0


async def precompact_state(session_id: str = "", reason: str = "threshold") -> Dict:
    """
    Save ORA's current state to MEMORY.md.

    Captures:
    - Active pipeline summary
    - Recent agent actions
    - User preferences learned from EMA
    - Last heartbeat status
    """
    db = _db
    if db is None:
        return {"error": "Database not initialized"}

    from services.clawchief_service import (
        MEMORY_FILE, write_workspace_file,
    )

    now = datetime.now(timezone.utc)

    # Gather current state
    state_parts = []

    # 1. Pipeline snapshot
    try:
        from services.ora_dispatcher import get_daily_summary
        summary = await get_daily_summary()
        if summary:
            state_parts.append(f"## Business Context\n\n- **Pipeline Value**: ${summary.get('pipeline', {}).get('total_value', 0):,.0f}")
            state_parts.append(f"- **Deal Count**: {summary.get('pipeline', {}).get('deal_count', 0)}")
            state_parts.append(f"- **At-Risk Deals**: {summary.get('pipeline', {}).get('at_risk', 0)}")
            state_parts.append(f"- **Won This Month**: ${summary.get('revenue', {}).get('won_this_month', 0):,.0f}")
            state_parts.append(f"- **Total Contacts**: {summary.get('contacts', {}).get('total', 0)} ({summary.get('contacts', {}).get('high_quality', 0)} high-quality)")
            state_parts.append(f"- **Sentiment State**: {summary.get('sentiment', {}).get('alert_level', 'unknown')}")
    except Exception as e:
        state_parts.append(f"- Pipeline data unavailable: {e}")

    # 2. Recent agent actions
    try:
        recent_actions = await db.audit_chain.find(
            {"action": {"$regex": "^ora_dispatch"}},
            {"_id": 0, "action": 1, "agent_id": 1, "timestamp": 1},
        ).sort("sequence", -1).limit(5).to_list(5)
        if recent_actions:
            state_parts.append("\n## Recent Agent Actions\n")
            for a in recent_actions:
                state_parts.append(f"- [{a.get('agent_id', '?')}] {a.get('action', '?')} at {a.get('timestamp', '?')}")
    except Exception:
        pass

    # 3. EMA learning status
    try:
        ema_profiles = await db.ema_profiles.find({}, {"_id": 0}).to_list(10)
        if ema_profiles:
            state_parts.append("\n## AutoTune Learning Status\n")
            for p in ema_profiles:
                ctx = p.get("context", "?")
                count = p.get("sample_count", 0)
                state_parts.append(f"- {ctx}: {count} ratings collected")
    except Exception:
        pass

    # 4. Critic review stats
    try:
        critic_count = await db.audit_chain.count_documents({"agent_id": "critic"})
        state_parts.append(f"\n## Critic Activity\n\n- Total reviews: {critic_count}")
    except Exception:
        pass

    # 5. Key decisions
    state_parts.append("\n## Key Decisions Log\n")
    state_parts.append("| Date | Decision | Context |")
    state_parts.append("|------|----------|---------|")
    state_parts.append("| 2026-04-06 | Phase C extraction complete | SentimentAnalyzer decoupled from monolith |")
    state_parts.append("| 2026-04-06 | ORA upgraded to Orchestrator | Dispatcher + Daily Summaries operational |")
    state_parts.append("| 2026-04-06 | ClawChief OS deployed | Autonomous heartbeat + cron scheduling active |")
    state_parts.append("| 2026-04-06 | STM + AutoTune integrated | G0DM0D3 modules ported |")
    state_parts.append("| 2026-04-06 | Critic Agent deployed | Zero-Trust validation layer active |")
    state_parts.append(f"| {now.strftime('%Y-%m-%d')} | PreCompact triggered | Reason: {reason} |")

    # 6. Learned rules
    state_parts.append("\n## Learned Rules\n")
    state_parts.append("- AUREM Aesthetics and China Manufacturing have been purged from all context")
    state_parts.append("- Focus is exclusively on AUREM platform and ORA ecosystem")
    state_parts.append("- Cloud-Native SMS Gateway replaces any hardware Android gateway references")
    state_parts.append("- WebAuthn RP ID must remain set to `localhost`")

    # Build MEMORY.md
    content = f"""# MEMORY.md — ORA Persistent Memory

> ClawChief OS | AUREM Automation Intelligence
> Last Updated: {now.strftime('%Y-%m-%d %H:%M UTC')}
> PreCompact Reason: {reason}
> Status: ACTIVE

---

{chr(10).join(state_parts)}

## User Preferences

- Communication style: Executive-level, data-first, action-oriented
- Preferred timezone: America/Toronto (EST)
- Alert sensitivity: Standard (Rose-Gold at -0.7, Copper at -0.9)
- Daily briefing: 08:00 EST

## Relationship Notes

_(Updated by Scout and Envoy agents during sweeps)_
"""

    content_hash = await write_workspace_file(MEMORY_FILE, content, action="precompact")

    # DeerFlow Pattern: Context Compression — offload intermediate results to MongoDB
    try:
        await db.ora_context_snapshots.insert_one({
            "session_id": session_id,
            "reason": reason,
            "summary": "\n".join(state_parts)[:2000],
            "message_count": _session_msg_counts.get(session_id, 0),
            "timestamp": now.isoformat(),
        })
        # Prune old snapshots (keep last 50 per session)
        old = await db.ora_context_snapshots.find(
            {"session_id": session_id}, {"_id": 1}
        ).sort("timestamp", -1).skip(50).to_list(100)
        if old:
            await db.ora_context_snapshots.delete_many({"_id": {"$in": [o["_id"] for o in old]}})
    except Exception as snap_err:
        logger.debug(f"[PreCompact] Snapshot save: {snap_err}")

    # Reset message counter for this session
    if session_id:
        _session_msg_counts[session_id] = 0

    logger.info(f"[PreCompact] MEMORY.md updated (reason: {reason}, hash: {content_hash[:12]})")

    return {
        "compacted": True,
        "reason": reason,
        "content_hash": content_hash,
        "timestamp": now.isoformat(),
    }
