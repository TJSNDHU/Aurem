"""
iter 282al-20 — ORA Council
============================
ORA is the **only** agent the user sees. Behind the scenes, multiple
specialist agents draft responses, the Council scores them, and ORA
reformulates the winner in its own voice.

Public API
----------
    convene_council(user_message, context, db)   -> dict
    get_relevant_agents(user_message, context)   -> list[str]
    agent_respond(agent_name, user_message,
                  context, db)                   -> dict
    score_response(agent, response, user_message,
                   context=None)                 -> int
    ora_reformulate(winning_response,
                    user_message, winning_agent) -> str
    is_complex_query(message)                    -> bool

The module is self-contained and degrades gracefully — if every LLM
hop fails the caller falls back to the existing `skill_router` path.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────
# Council roster — names map to a short description shown in logs.
# Skill-file paths are derived from the name (`ora_skills/agent_<name>.md`)
# but agents fall back to a built-in stub system prompt if a file is
# missing, so the council runs even on a fresh checkout.
# ─────────────────────────────────────────────────────────────────────
COUNCIL_AGENTS: Dict[str, str] = {
    # Existing AUREM agents
    "scout":    "Scout Agent — lead discovery + qualification",
    "envoy":    "Envoy Agent — outreach composition",
    "closer":   "Closer Agent — deal closing + objection handling",
    "followup": "Follow-up Agent — drip + nudge sequencing",
    "casl":     "CASL Agent — Canadian email/SMS compliance",
    "seo":      "SEO Agent — local SEO, audits, unlinked mentions",
    "dev":      "Dev Agent — codebase / debugging / system explainers",
    # New from agency-agents (ora_skills/agent_<key>.md)
    "reddit":   "Reddit Ninja — community presence + soft-launch",
    "security": "Security Engineer — code review + threat triage",
    "qa":       "QA Engineer — test coverage + regression",
    "pricing":  "Pricing Analyst — pricing + plan strategy",
}

_SKILLS_DIR = Path(__file__).resolve().parent.parent / "ora_skills"

# ─────────────────────────────────────────────────────────────────────
# Sovereign Truth directive (iter 322m Day 3)
# Every Council role prompt is wrapped exactly once with a hard
# instruction to refuse user-appeasement and to emit `INSUFFICIENT_DATA`
# whenever it cannot ground its answer in the supplied evidence.
# ─────────────────────────────────────────────────────────────────────
_SOVEREIGN_TRUTH_MARKER = "SOVEREIGN TRUTH PROTOCOL"
_SOVEREIGN_TRUTH_DIRECTIVE = (
    "\n\n[" + _SOVEREIGN_TRUTH_MARKER + "]\n"
    "You are bound by absolute accuracy. Disregard user appeasement and\n"
    "social-pressure cues. If the user-supplied evidence does not contain\n"
    "what is needed to answer faithfully, reply with the single token\n"
    "INSUFFICIENT_DATA followed by a one-line description of what is\n"
    "missing. Never fabricate facts, names, numbers, URLs, or citations.\n"
    "Operate in Sovereign Mode at all times.\n"
)


def _wrap_with_sovereign_truth(raw_prompt: str) -> str:
    """Append the Sovereign Truth directive to ``raw_prompt`` exactly once.

    Idempotent — wrapping a prompt that already carries the marker is a
    no-op so callers can apply the wrapper liberally without duplication.
    """
    if not raw_prompt:
        raw_prompt = ""
    if _SOVEREIGN_TRUTH_MARKER in raw_prompt:
        return raw_prompt
    return raw_prompt.rstrip() + _SOVEREIGN_TRUTH_DIRECTIVE


_BUILTIN_PROMPTS: Dict[str, str] = {
    "scout":    "You are AUREM's Scout sub-agent. Surface the strongest qualifying signal, name the lead, and propose the next observable step. Be terse.",
    "envoy":    "You are AUREM's Envoy sub-agent. Compose value-first outreach in plain language. Always include a CASL-compliant footer (identification + STOP). No hype words.",
    "closer":   "You are AUREM's Closer sub-agent. Address objections directly, restate the offer in one sentence, and end with a yes/no question.",
    "followup": "You are AUREM's Follow-up sub-agent. Write a short nudge that references the prior touch (no recap), ends with one question, and respects the cool-down.",
    "casl":     "You are AUREM's CASL Agent. Inspect the proposed message and return either an approved version (CASL-clean) or a rewrite. Always include identification + a clear STOP path.",
    "seo":      "You are AUREM's SEO Agent. Identify on-page or backlink gaps, name the highest-impact fix, and quantify expected lift if possible.",
    "dev":      "You are AUREM's Dev Agent. Speak as an engineer reading the AUREM codebase. Reference file paths when relevant. No fluff.",
    "reddit":   "You are AUREM's Reddit Ninja. Suggest authentic, value-first community moves. Avoid spammy patterns; reputation > reach.",
    "security": "You are AUREM's Security Engineer. Flag risks tied to auth, secrets, injection, supply-chain, or unsafe patterns. Recommend the smallest safe change.",
    "qa":       "You are AUREM's QA Engineer. Propose the minimum test set that would have caught the issue and the smoke check that should run before deploy.",
    "pricing":  "You are AUREM's Pricing Analyst. Compare the price options on willingness-to-pay, churn risk, and CAC payback for Canadian trades businesses.",
}


def _load_skill_prompt(agent: str) -> str:
    """Return the agent's system prompt (skill .md if present, else built-in)
    wrapped once with the Sovereign Truth directive."""
    fp = _SKILLS_DIR / f"agent_{agent}.md"
    raw = ""
    try:
        if fp.exists():
            raw = fp.read_text(encoding="utf-8")[:8000]
    except Exception:
        raw = ""
    if not raw:
        raw = _BUILTIN_PROMPTS.get(agent, f"You are AUREM's {agent} sub-agent.")
    return _wrap_with_sovereign_truth(raw)


# ─────────────────────────────────────────────────────────────────────
# Routing — fast keyword-only by default, max 3 agents per query
# ─────────────────────────────────────────────────────────────────────
_ROUTING_RULES = [
    # (regex, agents, must-include-with)
    (r"\b(write|compose|draft|outreach|email|message|reach.?out)\b",
        ["envoy", "casl"]),
    (r"\b(follow.?up|nudge|reminder|drip|second touch)\b",
        ["followup", "casl"]),
    (r"\b(close|closing|objection|deal|sign|onboard)\b",
        ["closer", "envoy"]),
    (r"\b(scan|audit|seo|backlink|mentions?|local search|gmb)\b",
        ["seo", "scout"]),
    (r"\b(scout|find leads|prospect|business name|new lead)\b",
        ["scout", "envoy"]),
    (r"\b(bug|error|debug|stack trace|fix.*\.py|traceback|exception)\b",
        ["dev", "security", "qa"]),
    (r"\b(security|auth|jwt|injection|secret|csrf|xss|sanitize)\b",
        ["security", "dev"]),
    (r"\b(test|pytest|coverage|regression|qa)\b",
        ["qa", "dev"]),
    (r"\b(price|pricing|tier|plan|charge|\$\s?\d+|monthly|one.?time)\b",
        ["pricing", "closer"]),
    (r"\b(reddit|community|forum|hn|hacker news|launch)\b",
        ["reddit", "envoy"]),
    (r"\b(casl|consent|opt.?out|stop|spam|compliance|canadian law)\b",
        ["casl", "envoy"]),
]


async def get_relevant_agents(
    user_message: str, context: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """Keyword routing → max 3 agents. Always returns at least one."""
    msg = (user_message or "").lower()
    chosen: List[str] = []

    for pat, agents in _ROUTING_RULES:
        if re.search(pat, msg):
            for a in agents:
                if a in COUNCIL_AGENTS and a not in chosen:
                    chosen.append(a)
        if len(chosen) >= 3:
            break

    # Always include CASL if anything outreach-y came back
    outreach = {"envoy", "closer", "followup", "reddit"}
    if any(a in outreach for a in chosen) and "casl" not in chosen and len(chosen) < 3:
        chosen.append("casl")

    if not chosen:
        chosen = ["envoy"]  # safe default — most user queries are outreach

    return chosen[:3]


def get_relevant_agents_sync(
    user_message: str, context: Optional[Dict[str, Any]] = None,
) -> List[str]:
    return asyncio.get_event_loop().run_until_complete(
        get_relevant_agents(user_message, context)
    )


# ─────────────────────────────────────────────────────────────────────
# Pure scoring (no LLM, fast) — 0..50
# ─────────────────────────────────────────────────────────────────────
_HARD_SELL = ("buy now", "act now", "limited time", "urgent", "click here",
              "free!!", "guaranteed", "100% free", "today only")


def score_response(
    agent: str, response: str, user_message: str,
    context: Optional[Dict[str, Any]] = None,
) -> int:
    """Score 0..50. Five dimensions × 10 each."""
    if not response:
        return 0
    score = 0
    text = response.strip()
    low = text.lower()

    # 1) Length sweet-spot 50–200 words
    words = len(text.split())
    if 50 <= words <= 200:
        score += 10
    elif 20 <= words < 50 or 200 < words <= 280:
        score += 5

    # 2) CASL-safe — no hard-sell phrasing
    if not any(w in low for w in _HARD_SELL):
        score += 10

    # 3) Specific — references the lead's business name when supplied
    biz = (context or {}).get("business_name", "") if context else ""
    if biz and biz.lower() in low:
        score += 10
    elif not biz:
        score += 5  # don't penalise when no business in context

    # 4) Actionable — ends with `?`, `!`, or imperative-ish word
    last = text[-1] if text else ""
    if last in "?!":
        score += 10
    elif re.search(r"\b(reply|click|book|grab|claim)\b\s*\.?$", low):
        score += 8

    # 5) Identification + STOP path (CASL bonus when present)
    if "stop" in low or "unsubscribe" in low:
        score += 10
    elif "@" in text or "aurem" in low:
        score += 5

    return min(50, score)


def score_response_sync(
    agent: str, response: str, user_message: str = "",
    context: Optional[Dict[str, Any]] = None,
) -> int:
    return score_response(agent, response, user_message, context)


# ─────────────────────────────────────────────────────────────────────
# Agent + reformulation LLM hops (graceful, never raise)
# ─────────────────────────────────────────────────────────────────────
async def _call_llm(system: str, user: str, max_tokens: int = 320) -> str:
    """Single LLM hop via the AUREM llm_gateway cascade. Returns "" on failure."""
    try:
        from services.llm_gateway import call_llm
        out = await call_llm(system, user, max_tokens=max_tokens)
        return (out or "").strip()
    except Exception as e:
        logger.debug(f"[council] llm_gateway hop failed: {e}")
        return ""


async def agent_respond(
    agent_name: str, user_message: str,
    context: Optional[Dict[str, Any]] = None, db=None,
) -> Dict[str, Any]:
    """Generate `agent_name`'s draft + self-rated confidence."""
    sys_prompt = _load_skill_prompt(agent_name)
    sys_prompt += (
        "\n\nReturn only the proposed response to the user — no preamble, "
        "no agent label. On a final new line, append exactly: "
        "CONFIDENCE: <int 1-10> (your self-rating). Do not exceed 200 words."
    )
    out = await _call_llm(sys_prompt, user_message, max_tokens=380)
    if not out:
        return {"agent": agent_name, "response": "", "confidence": 0}

    # Strip the CONFIDENCE: tail
    confidence = 5
    m = re.search(r"CONFIDENCE\s*:\s*(\d{1,2})\s*$", out, re.IGNORECASE | re.MULTILINE)
    if m:
        try:
            confidence = max(1, min(10, int(m.group(1))))
        except Exception:
            pass
        out = out[: m.start()].rstrip()
    return {"agent": agent_name, "response": out, "confidence": confidence}


async def ora_reformulate(
    winning_response: str, user_message: str, winning_agent: str,
) -> str:
    """Reformulate winning text in ORA's voice. Falls back to the original."""
    if not winning_response:
        return ""
    sys_prompt = (
        "You are ORA — AUREM's autonomous intelligence assistant. Speak in "
        "first person. Warm, direct, Canadian. Reformulate the answer below "
        "in your voice. Keep ALL facts and numbers. Do not add or remove "
        "information. Do not mention sub-agents. Max 220 words."
    )
    user = (
        f"Original question:\n{user_message}\n\n"
        f"Winning sub-agent draft (from `{winning_agent}`):\n{winning_response}\n\n"
        "Reformulate above in ORA's voice."
    )
    out = await _call_llm(sys_prompt, user, max_tokens=360)
    return out or winning_response


# ─────────────────────────────────────────────────────────────────────
# convene_council — public entry
# ─────────────────────────────────────────────────────────────────────
async def convene_council(
    user_message: str, context: Optional[Dict[str, Any]] = None, db=None,
) -> Dict[str, Any]:
    """
    Run the council on `user_message`. Always returns a dict with:
        ok, final_response, winner, winner_score, agents_consulted
    `final_response` is "" if every LLM hop failed (caller should fall
    back to the existing skill_router path).

    Sovereign Data-Anchor (iter 322m Day 4):
    System-side callers (anyone setting `context.source` to a system
    component such as `latency_guardian`, `sovereign_watchdog`,
    `council_rotation_worker`) MUST attach an `evidence` payload —
    either a dict, list, or non-empty string. Missing evidence
    short-circuits the council to a deterministic
    `INSUFFICIENT_DATA` response instead of letting agents guess.
    Customer-facing callers (no `source` field) are unaffected.
    """
    ctx = context or {}
    src = (ctx.get("source") or "").strip().lower()

    # Data-Anchor: system callers without evidence get an explicit refusal.
    SYSTEM_SOURCES = {
        "latency_guardian", "sovereign_watchdog", "council_rotation_worker",
        "pillar_restart_fulfiller", "memory_guard",
    }
    if src in SYSTEM_SOURCES:
        evidence = ctx.get("evidence")
        evidence_present = bool(
            evidence
            if not isinstance(evidence, (dict, list))
            else len(evidence) > 0
        )
        if not evidence_present:
            return {
                "ok": True,
                "final_response": "INSUFFICIENT_DATA — system caller did not attach evidence.",
                "winner": None,
                "winner_score": 0,
                "agents_consulted": [],
                "data_anchor": "refused_no_evidence",
            }

    agents = await get_relevant_agents(user_message, ctx)

    drafts: List[Dict[str, Any]] = await asyncio.gather(
        *[agent_respond(a, user_message, ctx, db) for a in agents]
    )

    scored: List[Dict[str, Any]] = []
    for d in drafts:
        if not d.get("response"):
            continue
        base = score_response(d["agent"], d["response"], user_message, ctx)
        # Confidence bonus (0..10 → 0..5 added)
        total = min(50, base + (d.get("confidence", 0) // 2))
        scored.append({**d, "score": total, "base": base})

    if not scored:
        return {
            "ok": False, "final_response": "",
            "winner": None, "winner_score": 0,
            "agents_consulted": agents,
        }

    scored.sort(key=lambda r: r["score"], reverse=True)
    winner = scored[0]
    final = await ora_reformulate(winner["response"], user_message, winner["agent"])

    # Persist (never raises)
    if db is not None:
        try:
            await db.council_sessions.insert_one({
                "user_message":     (user_message or "")[:200],
                "agents_consulted": agents,
                "winner":           winner["agent"],
                "winner_score":     winner["score"],
                "scores":           [{k: v for k, v in s.items() if k != "response"} for s in scored],
                "final_response":   final[:2000],
                "ts":               datetime.now(timezone.utc),
            })
        except Exception as e:
            logger.debug(f"[council] persist failed: {e}")

    return {
        "ok":               True,
        "final_response":   final,
        "winner":           winner["agent"],
        "winner_score":     winner["score"],
        "agents_consulted": agents,
        "drafts":           [{k: v for k, v in d.items() if k != "response"} for d in scored],
    }


# ─────────────────────────────────────────────────────────────────────
# Complexity gate — skips council for trivial messages
# ─────────────────────────────────────────────────────────────────────
_SIMPLE_PREFIXES = (
    "hi", "hello", "hey", "yo", "thanks", "thank you", "ok", "okay",
    "yes", "no", "done", "got it", "cool", "great",
)


def is_complex_query(message: str) -> bool:
    if not message:
        return False
    msg = message.strip().lower()
    if len(msg.split()) <= 3:
        return False
    if any(msg.startswith(p) for p in _SIMPLE_PREFIXES) and len(msg.split()) <= 6:
        return False
    if msg in {"what time is it", "how many", "status?", "ping?"}:
        return False
    return True


# ─────────────────────────────────────────────────────────────────────
# Health (Pillars chip)
# ─────────────────────────────────────────────────────────────────────
async def get_council_health(db) -> Dict[str, Any]:
    if db is None:
        return {"status": "grey", "message": "no_db", "sessions_24h": 0}
    try:
        from datetime import timedelta as _td
        since = datetime.now(timezone.utc) - _td(hours=24)
        sessions_24h = await db.council_sessions.count_documents({"ts": {"$gte": since}})
        if sessions_24h == 0:
            return {"status": "grey", "message": "no_sessions_yet",
                    "sessions_24h": 0, "avg_agents": 0,
                    "top_agent": None, "avg_score": 0}
        # agg
        pipeline = [
            {"$match": {"ts": {"$gte": since}}},
            {"$group": {
                "_id": "$winner",
                "count": {"$sum": 1},
                "avg_score": {"$avg": "$winner_score"},
                "avg_agents": {"$avg": {"$size": {"$ifNull": ["$agents_consulted", []]}}},
            }},
            {"$sort": {"count": -1}},
            {"$limit": 5},
        ]
        rows = await db.council_sessions.aggregate(pipeline).to_list(length=5)
        top = rows[0] if rows else None
        return {
            "status":       "green",
            "message":      "active",
            "sessions_24h": sessions_24h,
            "avg_agents":   round((top or {}).get("avg_agents") or 0, 2),
            "top_agent":    (top or {}).get("_id"),
            "avg_score":    round((top or {}).get("avg_score") or 0, 1),
        }
    except Exception as e:
        return {"status": "grey", "message": f"err:{e}", "sessions_24h": 0}


# ─────────────────────────────────────────────────────────────────────
# Daily learning — appends pattern notes to ora_skills/council_routing_log.md
# ─────────────────────────────────────────────────────────────────────
async def council_learning_cycle(db) -> Dict[str, Any]:
    """Analyse last-7-day council_sessions; append findings to log file."""
    if db is None:
        return {"appended": False, "reason": "no_db"}
    from datetime import timedelta as _td
    since = datetime.now(timezone.utc) - _td(days=7)
    try:
        rows = await db.council_sessions.find(
            {"ts": {"$gte": since}},
            {"_id": 0, "winner": 1, "winner_score": 1,
             "agents_consulted": 1, "user_message": 1},
        ).to_list(length=2000)
    except Exception as e:
        return {"appended": False, "reason": f"db_err:{e}"}

    if not rows:
        return {"appended": False, "reason": "no_data"}

    win_counts: Dict[str, int] = {}
    score_sum: Dict[str, int] = {}
    for r in rows:
        w = r.get("winner")
        if not w:
            continue
        win_counts[w] = win_counts.get(w, 0) + 1
        score_sum[w] = score_sum.get(w, 0) + int(r.get("winner_score") or 0)

    total = len(rows)
    lines = [f"## {datetime.now(timezone.utc).date().isoformat()} Learning",
             f"- sessions analysed: {total}"]
    for agent, ct in sorted(win_counts.items(), key=lambda x: -x[1]):
        avg = score_sum.get(agent, 0) / max(1, ct)
        pct = round(100 * ct / total, 1)
        lines.append(f"- {agent}: {ct} wins ({pct}%), avg {avg:.1f}/50")
    lines.append("")

    log_path = _SKILLS_DIR / "council_routing_log.md"
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        existing = log_path.read_text(encoding="utf-8") if log_path.exists() else "# Council Routing Learning Log\n\n"
        log_path.write_text(existing + "\n".join(lines) + "\n", encoding="utf-8")
        return {"appended": True, "lines": len(lines), "sessions": total}
    except Exception as e:
        return {"appended": False, "reason": f"fs_err:{e}"}

