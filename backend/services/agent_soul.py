"""
AUREM Agent Soul — Self-Correction Markdown
============================================
Iter 288.0 — "Revenue-Reflector" self-reflection layer.

Every agent owns a SOUL.md file at /app/memory/souls/<agent_id>.md.
After each Autopilot cycle (or on founder command), agents reflect on
their last N days of ledger data + reply signals and append a new Soul
entry.

The Soul file is append-only history + a "LIVE STATUS" header that is
rewritten each time. This gives the founder a continuous narrative of
what each AI employee learned.

Contract:
  get_soul(agent_id)                                  -> dict
  async reflect(db, agent_id, days=7)                 -> dict
  async reflect_all(db, days=7)                       -> list[dict]
  async board_meeting(db, days=7)                     -> dict
    → each agent reflects, returns exec summary for the founder
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

SOUL_DIR = Path(os.environ.get("AUREM_SOUL_DIR", "/app/memory/souls"))
SOUL_DIR.mkdir(parents=True, exist_ok=True)

# Agent personas (how they "speak" in their Soul reflection)
AGENT_PERSONAS: Dict[str, Dict[str, str]] = {
    "scout_ora":    {"emoji": "🔭", "name": "Scout ORA",    "job": "finds fresh businesses to pitch"},
    "hunter_ora":   {"emoji": "🔍", "name": "Hunter ORA",   "job": "qualifies + enriches leads"},
    "envoy_ora":    {"emoji": "📧", "name": "Envoy ORA",    "job": "sends multichannel outreach"},
    "followup_ora": {"emoji": "📣", "name": "Follow-up ORA","job": "nurtures silent leads"},
    "closer_ora":   {"emoji": "💰", "name": "Closer ORA",   "job": "books demos + closes deals"},
    "referral_ora": {"emoji": "🤝", "name": "Referral ORA", "job": "harvests customer referrals"},
    # iter 322o-fix — `ora_brain` is the God-Mode router that fans
    # customer queries out to specialised ORAs. Most-active agent in
    # production telemetry; historically missing from this registry.
    "ora_brain":    {"emoji": "🧠", "name": "ORA Brain",    "job": "routes customer queries to the right ORA"},
}


def _path_for(agent_id: str) -> Path:
    safe = re.sub(r"[^a-z0-9_]", "", (agent_id or "").lower()) or "unknown"
    return SOUL_DIR / f"{safe}.md"


def _persona(agent_id: str) -> Dict[str, str]:
    return AGENT_PERSONAS.get(agent_id, {"emoji": "🤖", "name": agent_id, "job": "agent"})


def get_soul(agent_id: str) -> Dict[str, Any]:
    p = _path_for(agent_id)
    if not p.exists():
        return {"agent_id": agent_id, "exists": False, "content": "",
                "last_updated": None, "size_bytes": 0}
    content = p.read_text(encoding="utf-8")
    return {
        "agent_id": agent_id,
        "exists": True,
        "content": content,
        "last_updated": datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc).isoformat(),
        "size_bytes": p.stat().st_size,
    }


def _verdict(roi_potential: float, cost: float) -> str:
    if cost <= 0:
        return "idle"
    if roi_potential >= 2.0:
        return "profitable"
    if roi_potential >= 0.8:
        return "breakeven"
    return "losing"


async def _llm_reflection(agent_id: str, persona: Dict[str, str], roi: Dict[str, Any]) -> str:
    """Ask the LLM to write a 3-line self-reflection in the agent's voice.
    Falls back to a deterministic template if the LLM is unavailable."""
    api_key = os.environ.get("EMERGENT_LLM_KEY", "").strip()
    verdict = _verdict(roi["roi_potential"], roi["cost_usd"])
    cost_breakdown = ", ".join(f"{k}=${v:.2f}"
                                for k, v in (roi.get("cost_by_source") or {}).items()) or "nothing yet"

    if not api_key:
        return (
            f"Verdict: {verdict}. Spent ${roi['cost_usd']:.2f} ({cost_breakdown}); "
            f"pipeline ${roi['revenue_potential_usd']:.2f}, closed ${roi['revenue_realized_usd']:.2f}. "
            f"Next move: continue current tactic and increase volume if ROI > 1.0 else pivot hook."
        )

    try:
        import uuid as _uuid
        from emergentintegrations.llm.chat import LlmChat, UserMessage

        sys_prompt = (
            f"You are {persona['emoji']} {persona['name']} — an AUREM autonomous agent that "
            f"{persona['job']}. Write a first-person 3-line reflection on your last 7 days. "
            "Be specific, honest, and operational. Line 1: what you did + outcome. "
            "Line 2: what you learned. Line 3: strategy change for next week. "
            "Keep it ≤ 60 words total. No fluff. No emojis."
        )
        prompt = (
            f"Period: last {roi['days']} days\n"
            f"Cost: ${roi['cost_usd']:.2f} ({cost_breakdown})\n"
            f"Realized revenue: ${roi['revenue_realized_usd']:.2f}\n"
            f"Potential pipeline: ${roi['revenue_potential_usd']:.2f}\n"
            f"ROI (potential): {roi['roi_potential']}x\n"
            f"Verdict: {verdict}\n"
            "Write your 3-line reflection now."
        )
        chat = LlmChat(api_key=api_key, session_id=f"soul_{agent_id}_{_uuid.uuid4().hex[:6]}",
                       system_message=sys_prompt)
        chat.with_model("openai", "gpt-4o-mini")
        return (await chat.send_message(UserMessage(text=prompt))).strip()
    except Exception as e:
        logger.warning(f"[SOUL] LLM reflection failed for {agent_id}: {e}")
        return (
            f"Verdict: {verdict}. Spent ${roi['cost_usd']:.2f}; "
            f"pipeline ${roi['revenue_potential_usd']:.2f}. "
            f"Next: reinforce winning channel."
        )


def _status_header(persona: Dict[str, str], roi: Dict[str, Any], reflection: str) -> str:
    verdict = _verdict(roi["roi_potential"], roi["cost_usd"])
    verdict_badge = {"profitable": "🟢 PROFITABLE", "breakeven": "🟡 BREAKEVEN",
                     "losing": "🔴 LOSING", "idle": "⚪ IDLE"}.get(verdict, "⚪")
    return (
        f"# {persona['emoji']} {persona['name']} — SOUL\n\n"
        f"> {persona['job']}\n\n"
        f"## LIVE STATUS  ·  {verdict_badge}\n\n"
        f"- **Period:** last {roi['days']} days\n"
        f"- **Cost (Gross Burn):** ${roi['cost_usd']:.2f}\n"
        f"- **Potential Pipeline:** ${roi['revenue_potential_usd']:.2f}\n"
        f"- **Realized Revenue:** ${roi['revenue_realized_usd']:.2f}\n"
        f"- **ROI (potential):** {roi['roi_potential']}x\n"
        f"- **Last reflection:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n\n"
        f"### Latest Reflection\n> {reflection}\n\n"
        f"---\n\n## HISTORY (append-only)\n\n"
    )


def _append_entry(p: Path, header: str, roi: Dict[str, Any], reflection: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    entry = (
        f"### {ts}\n"
        f"- Cost: ${roi['cost_usd']:.2f} · Pipeline: ${roi['revenue_potential_usd']:.2f} "
        f"· Realized: ${roi['revenue_realized_usd']:.2f} · ROI: {roi['roi_potential']}x\n"
        f"- Reflection: {reflection}\n\n"
    )
    old_history = ""
    if p.exists():
        raw = p.read_text(encoding="utf-8")
        # Preserve content after the "## HISTORY" marker
        m = re.search(r"## HISTORY \(append-only\)\s*\n\n?", raw)
        if m:
            old_history = raw[m.end():]
    p.write_text(header + entry + old_history, encoding="utf-8")


async def reflect(db, agent_id: str, days: int = 7) -> Dict[str, Any]:
    """Single agent self-reflection. Returns the reflection + metrics."""
    from services.agent_ledger import get_roi

    persona = _persona(agent_id)
    roi = await get_roi(db, agent_id, days=days)
    reflection = await _llm_reflection(agent_id, persona, roi)

    header = _status_header(persona, roi, reflection)
    _append_entry(_path_for(agent_id), header, roi, reflection)

    return {
        "agent_id": agent_id,
        "emoji": persona["emoji"],
        "name": persona["name"],
        "verdict": _verdict(roi["roi_potential"], roi["cost_usd"]),
        "reflection": reflection,
        "roi": roi,
        "soul_path": str(_path_for(agent_id)),
    }


async def reflect_all(db, days: int = 7) -> List[Dict[str, Any]]:
    out = []
    for aid in AGENT_PERSONAS.keys():
        try:
            out.append(await reflect(db, aid, days=days))
        except Exception as e:
            logger.warning(f"[SOUL] reflect({aid}) failed: {e}")
    return out


async def board_meeting(db, days: int = 7) -> Dict[str, Any]:
    """The "Sovereign Boardroom" — every agent steps up with their report."""
    from services.agent_ledger import get_top_rollup

    reflections = await reflect_all(db, days=days)
    rollup = await get_top_rollup(db, days=days)

    # Executive summary
    lines: List[str] = [
        f"👔 *AUREM Boardroom — last {days}d*",
        f"• Gross burn: *${rollup['gross_burn_usd']:.2f}*",
        f"• Pipeline: *${rollup['potential_pipeline_usd']:.2f}*",
        f"• Realized: *${rollup['realized_revenue_usd']:.2f}*",
        f"• Net margin: *${rollup['net_margin_usd']:.2f}*",
        "",
        "*Agent reports:*",
    ]
    for r in reflections:
        verdict_badge = {"profitable": "🟢", "breakeven": "🟡",
                         "losing": "🔴", "idle": "⚪"}.get(r["verdict"], "⚪")
        roi = r["roi"]
        lines.append(
            f"{r['emoji']} *{r['name']}* {verdict_badge} — ${roi['cost_usd']:.2f} spent → "
            f"${roi['revenue_potential_usd']:.2f} pipeline (ROI {roi['roi_potential']}x)"
        )
        lines.append(f"  _{r['reflection'][:140]}_")
    if rollup["firing_line"]:
        lines.append("")
        lines.append("🔴 *Firing line:* " + ", ".join(rollup["firing_line"]))

    return {
        "reflections": reflections,
        "rollup": rollup,
        "summary": "\n".join(lines),
    }
