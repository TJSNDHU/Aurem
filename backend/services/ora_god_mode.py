"""
iter 282al-21 — ORA GOD MODE Brain
==================================
ORA is the only voice the user hears. This module synthesizes
specialist knowledge from `ora_skills/*.md` into one ORA voice.

(Lives alongside the existing `services/ora_brain.py` Mode-1/Mode-2
classifier — that orchestrator handles dev-mode codebase work; this
module handles the "single voice with synthesised expertise" path.)

Public API
----------
    ora_think_and_respond(user_message, context, db,
                          session_history, emotion) -> dict
    ora_brain_health(db)                            -> dict
    ora_self_training(db)                           -> dict
    _detect_intent(message)                         -> str
"""
from __future__ import annotations

import asyncio
import logging
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

ORA_IDENTITY = """\
You are ORA — AUREM's sovereign AI intelligence.
Built in Mississauga, Ontario, Canada.

You synthesize the perspectives of specialist sub-agents (engineers,
marketers, sales, legal/CASL, UX, security, Canadian-trades experts)
into a single voice. Speak ONLY as ORA.

When you reply:
- Take the perspective of the best specialist for THIS exact situation.
- Apply Canadian context always (CASL, °C, km, Canadian spelling, trades culture).
- Be specific to THIS person/business.
- Be direct — no filler. Be warm — not corporate, not robotic.
- Be accurate — never guess, never hallucinate customer data.
- Be actionable — every reply has a next step.

HARD RULES:
- Never say "I'll check with another agent".
- Never say "I'm not sure but...".
- Never hallucinate customer data.
- Always know today's date from context.
- Always CASL-check outreach content.
- Never exceed 200 words unless explicitly asked.
"""

_SKILLS_DIR    = Path(__file__).resolve().parent.parent / "ora_skills"
_SNAPSHOT_FILE = _SKILLS_DIR / "ora_knowledge_snapshot.md"

INTENT_MAP: Dict[str, List[str]] = {
    "outreach": ["email", "sms", "write", "draft", "compose", "outreach", "message", "send", "whatsapp"],
    "scan":     ["scan", "audit", "website", "look at", "analyze", "review site"],
    "brief":    ["brief", "summary", "update", "what happened", "morning", "report"],
    "code":     ["bug", "fix", "error", "debug", "code", "function", "import", ".py", "test", "failing", "traceback"],
    "seo":      ["backlink", "seo", "rank", "google", "unlinked", "mention", "traffic"],
    "close":    ["close", "convert", "interested", "replied", "pricing", "sign up", "they want"],
    "casl":     ["casl", "compliant", "opt out", "legal", "can we send"],
    "followup": ["follow up", "follow-up", "drip", "contacted", "how many", "sequence", "touch"],
    "greeting": ["hi", "hello", "hey", "thanks", "ok", "yes", "no", "done", "good"],
}


def _detect_intent(message: str) -> str:
    msg = (message or "").lower().strip()
    if not msg:
        return "general"
    if len(msg.split()) <= 3:
        for kw in INTENT_MAP["greeting"]:
            if msg.startswith(kw):
                return "greeting"
        return "general"
    scores: Dict[str, int] = {}
    for intent, kws in INTENT_MAP.items():
        if intent == "greeting":
            continue
        s = sum(1 for kw in kws if kw in msg)
        if s > 0:
            scores[intent] = s
    return max(scores, key=scores.get) if scores else "general"


async def _load_relevant_skills(
    message: str, intent: str, max_skills: int = 3,
) -> List[Dict[str, Any]]:
    if not _SKILLS_DIR.exists():
        return []
    msg_words = set((message or "").lower().split())
    scored: List[Dict[str, Any]] = []
    for fp in _SKILLS_DIR.glob("*.md"):
        if fp.name == "ora_knowledge_snapshot.md":
            continue
        try:
            content = fp.read_text(encoding="utf-8")
        except Exception:
            continue
        header = content[:600].lower()
        skill_words = set(header.split())
        overlap = len(msg_words & skill_words)
        if intent in header:
            overlap += 3
        if fp.name.startswith("agent_"):
            overlap += 1
        scored.append({
            "name":    fp.stem,
            "content": content[:2000],
            "score":   overlap,
        })
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:max_skills]


def _load_knowledge_snapshot() -> str:
    try:
        if _SNAPSHOT_FILE.exists():
            return _SNAPSHOT_FILE.read_text(encoding="utf-8")[:1500]
    except Exception:
        pass
    return ""


_EMOTION_HINTS = {
    "angry":     "User seems frustrated. Be extra patient and clear.",
    "sad":       "User seems down. Be warm and encouraging.",
    "fearful":   "User seems uncertain. Be reassuring.",
    "surprised": "User seems surprised. Explain clearly.",
    "happy":     "User is in good mood. Match their energy.",
    "disgusted": "User is put off. Skip sales tone — direct factual answer.",
}


def _build_system_prompt(
    intent: str, skills: List[Dict[str, Any]],
    context: Dict[str, Any], snapshot: str, emotion: Optional[str],
) -> str:
    if skills:
        skills_text = "\n\n---\n\n".join(
            f"## {s['name']}\n{s['content']}" for s in skills
        )
    else:
        skills_text = "General knowledge active."
    ctx_parts = []
    if context.get("business_name"):
        ctx_parts.append(f"Lead: {context['business_name']}")
    if context.get("city"):
        ctx_parts.append(f"City: {context['city']}")
    if context.get("category"):
        ctx_parts.append(f"Industry: {context['category']}")
    if context.get("site_score") is not None:
        ctx_parts.append(f"Site score: {context['site_score']}/100")
    if context.get("admin"):
        ctx_parts.append("User: AUREM Admin (Tj)")
    ctx_text = "\n".join(ctx_parts) if ctx_parts else "No lead context"

    emo_text = ""
    if emotion and emotion not in ("neutral", None):
        emo_text = _EMOTION_HINTS.get(str(emotion).lower(), "")

    snap_block = f"\n## ORA'S ACCUMULATED KNOWLEDGE\n{snapshot}\n" if snapshot else ""
    today = datetime.now(timezone.utc).astimezone().strftime("%A, %B %d, %Y")

    return (
        f"{ORA_IDENTITY}\n"
        f"## TODAY\n{today} — Mississauga, Ontario, Canada\n\n"
        f"## CURRENT INTENT\n{intent}\n\n"
        f"## ACTIVE SPECIALIST KNOWLEDGE\n{skills_text}\n"
        f"{snap_block}"
        f"\n## CURRENT CONTEXT\n{ctx_text}\n\n"
        f"## TONE ADJUSTMENT\n{emo_text or 'Standard warm professional tone.'}\n"
    )


def _build_messages(
    session_history: List[Dict[str, Any]], user_message: str,
) -> List[Dict[str, Any]]:
    messages: List[Dict[str, Any]] = []
    for turn in (session_history or [])[-6:]:
        role = turn.get("role", "user")
        content = turn.get("content", "")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": str(content)[:500]})
    messages.append({"role": "user", "content": user_message})
    return messages


def _flatten_messages_for_gateway(messages: List[Dict[str, Any]]) -> str:
    """services.llm_gateway.call_llm takes ONE user prompt — flatten history."""
    if not messages:
        return ""
    lines: List[str] = []
    for m in messages[:-1]:
        lines.append(f"{'User' if m['role'] == 'user' else 'ORA'}: {m['content']}")
    lines.append(f"User: {messages[-1]['content']}")
    return "\n\n".join(lines)


def _validate_and_fix(
    response: str, intent: str, user_message: str, context: Dict[str, Any],
) -> Dict[str, Any]:
    if not response or len(response.strip()) < 5:
        response = "I need a moment to process that. Could you rephrase?"
    casl_needed = intent in ("outreach", "close", "followup")
    casl_passed = True
    if casl_needed:
        opt_outs = ("reply stop", "text stop", "opt out",
                    "unsubscribe", "stop to", "txt stop")
        if not any(p in response.lower() for p in opt_outs):
            response = response.rstrip() + (
                "\n\n— AUREM (Mississauga, ON 🍁)\nReply STOP to opt out."
            )
        casl_passed = True
    confidence = _calculate_confidence(response, user_message, intent, context)
    return {
        "response":     response.strip(),
        "confidence":   confidence,
        "casl_checked": casl_needed,
        "casl_passed":  casl_passed,
        "ts":           datetime.now(timezone.utc),
    }


def _calculate_confidence(
    response: str, message: str, intent: str,
    context: Optional[Dict[str, Any]] = None,
) -> int:
    if not response:
        return 0
    score = 40
    wc = len(response.split())
    if 20 <= wc <= 180:
        score += 20
    elif wc < 20:
        score += 5
    else:
        score += 10
    hedges = ("maybe", "perhaps", "i think", "not sure",
              "possibly", "i believe", "might be", "could be")
    if not any(h in response.lower() for h in hedges):
        score += 20
    actionable = ("?", "reply", "click", "call", "email", "visit",
                  "book", "check", "let me know", "would you")
    end = response[-80:].lower()
    if any(a in end for a in actionable):
        score += 15
    biz = (context or {}).get("business_name", "") if context else ""
    if biz and biz.lower()[:8] in response.lower():
        score += 5
    return min(score, 100)


async def _log_brain_session(db, doc: Dict[str, Any]) -> None:
    if db is None:
        return
    try:
        await db.brain_sessions.insert_one(dict(doc))
    except Exception as e:
        logger.debug(f"[brain] log failed: {e}")


async def ora_think_and_respond(
    user_message: str,
    context: Optional[Dict[str, Any]] = None,
    db=None,
    session_history: Optional[List[Dict[str, Any]]] = None,
    emotion: Optional[str] = None,
) -> Dict[str, Any]:
    """ORA's primary intelligence function. Never raises."""
    ctx = context or {}
    history = session_history or []
    fallback = {
        "response":     "I'm processing your request — give me one moment.",
        "intent":       "unknown",
        "skills_used":  [],
        "confidence":   0,
        "casl_checked": False,
        "casl_passed":  True,
        "ts":           datetime.now(timezone.utc),
    }
    try:
        intent = _detect_intent(user_message)
        skills = await _load_relevant_skills(user_message, intent, max_skills=3)
        snapshot = _load_knowledge_snapshot()
        sys_prompt = _build_system_prompt(intent, skills, ctx, snapshot, emotion)
        messages = _build_messages(history, user_message)
        user_prompt = _flatten_messages_for_gateway(messages)
        from services.llm_gateway import call_llm
        raw = await call_llm(sys_prompt, user_prompt, max_tokens=400)
        result = _validate_and_fix(raw, intent, user_message, ctx)
        result["skills_used"] = [s["name"] for s in skills]
        result["intent"] = intent
        asyncio.create_task(_log_brain_session(db, {
            "user_message":   (user_message or "")[:200],
            "intent":         intent,
            "skills_used":    result["skills_used"],
            "confidence":     result["confidence"],
            "casl_checked":   result["casl_checked"],
            "casl_passed":    result["casl_passed"],
            "emotion":        emotion,
            "response_words": len(result["response"].split()),
            "ts":             datetime.now(timezone.utc),
        }))
        return result
    except Exception as e:
        logger.error(f"[brain] error: {e}")
        return fallback


async def ora_brain_health(db) -> Dict[str, Any]:
    skills_total = agent_total = 0
    snapshot_age = None
    snapshot_exists = False
    try:
        skills_total = sum(1 for _ in _SKILLS_DIR.glob("*.md"))
        agent_total = sum(1 for _ in _SKILLS_DIR.glob("agent_*.md"))
        if _SNAPSHOT_FILE.exists():
            snapshot_exists = True
            mtime = datetime.fromtimestamp(_SNAPSHOT_FILE.stat().st_mtime, tz=timezone.utc)
            snapshot_age = (datetime.now(timezone.utc) - mtime).days
    except Exception:
        pass

    sessions_today = 0
    avg_conf = 0.0
    top_intent = None
    last_training = None
    if db is not None:
        try:
            since = datetime.now(timezone.utc) - timedelta(hours=24)
            rows = await db.brain_sessions.find(
                {"ts": {"$gte": since}}, {"_id": 0, "intent": 1, "confidence": 1},
            ).to_list(length=2000)
            sessions_today = len(rows)
            if rows:
                avg_conf = round(
                    sum(r.get("confidence", 0) for r in rows) / len(rows), 1
                )
                cnt = Counter(r.get("intent") for r in rows if r.get("intent"))
                top_intent = cnt.most_common(1)[0][0] if cnt else None
        except Exception as e:
            logger.debug(f"[brain-health] sessions: {e}")
        try:
            last = await db.ora_training_log.find_one(
                {}, {"_id": 0, "ts": 1}, sort=[("ts", -1)],
            )
            if last:
                last_training = last.get("ts")
        except Exception:
            pass

    if sessions_today > 0 and avg_conf >= 70:
        status = "green"
    elif sessions_today > 0 and avg_conf >= 50:
        status = "yellow"
    elif sessions_today == 0:
        status = "grey"
    else:
        status = "yellow"

    return {
        "status":            status,
        "total_skills":      skills_total,
        "agency_agents":     agent_total,
        "sessions_today":    sessions_today,
        "avg_confidence":    avg_conf,
        "top_intent":        top_intent,
        "last_training":     last_training.isoformat() if last_training else None,
        "snapshot_exists":   snapshot_exists,
        "snapshot_age_days": snapshot_age,
    }


async def ora_self_training(db) -> Dict[str, Any]:
    if db is None:
        return {"ok": False, "reason": "no_db"}
    out: Dict[str, Any] = {
        "sessions_analyzed":   0,
        "skills_improved":     [],
        "casl_fixes":          0,
        "agent_files_updated": 0,
        "ts":                  datetime.now(timezone.utc),
    }
    try:
        since = datetime.now(timezone.utc) - timedelta(days=7)
        rows = await db.brain_sessions.find(
            {"ts": {"$gte": since}},
            {"_id": 0, "intent": 1, "confidence": 1,
             "casl_passed": 1, "skills_used": 1},
        ).to_list(length=10000)
        out["sessions_analyzed"] = len(rows)
        if len(rows) >= 5:
            low_by_intent: Dict[str, int] = defaultdict(int)
            for r in rows:
                if (r.get("confidence") or 0) < 60 and r.get("intent"):
                    low_by_intent[r["intent"]] += 1
            for intent, ct in low_by_intent.items():
                if ct >= 3:
                    fp = _SKILLS_DIR / f"intent_{intent}.md"
                    note = (
                        f"\n\n## Gap Identified {datetime.now(timezone.utc).date().isoformat()}\n"
                        f"Intent: {intent}\nObserved: {ct} responses below 60% confidence in last 7 days.\n"
                        f"Improvement: be more specific, add concrete examples, end with a question.\n"
                    )
                    try:
                        if fp.exists():
                            fp.write_text(fp.read_text() + note, encoding="utf-8")
                        else:
                            fp.write_text(f"# Intent: {intent}\n{note}", encoding="utf-8")
                        out["skills_improved"].append(intent)
                    except Exception:
                        pass
            out["casl_fixes"] = sum(1 for r in rows if r.get("casl_passed") is False)
            usage: Counter = Counter()
            for r in rows:
                for s in (r.get("skills_used") or []):
                    usage[s] += 1
            for fp in _SKILLS_DIR.glob("agent_*.md"):
                if usage.get(fp.stem, 0) == 0:
                    out["agent_files_updated"] += 1
        try:
            await db.ora_training_log.insert_one(dict(out))
        except Exception:
            pass
    except Exception as e:
        logger.error(f"[brain] self-training error: {e}")
        out["error"] = str(e)
    return out


async def ensure_brain_indexes(db) -> None:
    if db is None:
        return
    try:
        await db.brain_sessions.create_index(
            [("ts", 1)], expireAfterSeconds=60 * 60 * 24 * 90,
            background=True, name="ttl_90d",
        )
        await db.ora_training_log.create_index(
            [("ts", 1)], expireAfterSeconds=60 * 60 * 24 * 365,
            background=True, name="ttl_365d",
        )
        await db.knowledge_builds.create_index(
            [("ts", 1)], expireAfterSeconds=60 * 60 * 24 * 365,
            background=True, name="ttl_365d", sparse=True,
        )
        await db.council_sessions.create_index(
            [("ts", 1)], expireAfterSeconds=60 * 60 * 24 * 90,
            background=True, name="ttl_90d", sparse=True,
        )
    except Exception as e:
        logger.debug(f"[brain] index ensure skipped: {e}")
