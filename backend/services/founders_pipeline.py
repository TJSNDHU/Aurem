"""
Founders Pipeline (iter 305) — 6-stage build engine
====================================================
Stage 1: preprocess_input(text) → structured task object
Stage 2: multi_model_race(task) → asyncio.gather(Claude, Gemini, ORA)
Stage 3: enhance_council(decision, task, race) → adds risk_score(1-10),
         auto_build_eligible, optimized_prompt
Stage 6: record_learning() / recent_learnings(n=20)
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

LEARNINGS_COLLECTION = "ora_learnings"
LEARNINGS_LOOKBACK = 20

# Whitelist & blacklist for Stage 5 — used by self-edit + auto_build_eligible
WHITELIST_PREFIXES = (
    "frontend/src/components/",
    "frontend/src/pages/",
    "backend/routers/",
    "backend/services/",
)
BLACKLIST_EXACT = {
    "backend/.env",
    "frontend/.env",
    "backend/server.py",
    "backend/routers/auth_router.py",
    "backend/services/council.py",
    "backend/services/zero_downtime_repair.py",
    "backend/services/lock_in_validator.py",
    "backend/services/founders_pipeline.py",
    "backend/services/self_edit_engine.py",
    "backend/routers/founders_console_router.py",
}
BLACKLIST_NAME_PATTERNS = ("lock", "locked")


def _is_path_safe(path: str) -> bool:
    p = path.lstrip("/").replace("\\", "/")
    if p in BLACKLIST_EXACT:
        return False
    base = os.path.basename(p).lower()
    if any(pat in base for pat in BLACKLIST_NAME_PATTERNS):
        return False
    if not any(p.startswith(pre) for pre in WHITELIST_PREFIXES):
        return False
    return True


# ─── Stage 1: pre-processor ─────────────────────────────────────────────────
INTENT_KEYWORDS = {
    "BUILD":     ["add", "build", "create", "ship", "make", "implement", "banao",
                  "banade", "naya", "nayi", "widget", "add karo", "add kar do"],
    "FIX":       ["fix", "repair", "bug", "broken", "issue", "thik karo",
                  "theek karo", "thoda fix", "kaam nahi"],
    "STATUS":    ["status", "kitne", "how many", "count", "kitni", "dashboard",
                  "summary", "snapshot", "abhi", "current state"],
    "LEADS":     ["leads", "pipeline", "stages", "discovered", "contacted",
                  "responded", "qualified", "leads kitne"],
    "SCOUT":     ["scout", "find", "search", "discover", "dhoondh", "khoj",
                  "khojo", "look for", "businesses in", "shops in"],
    "PAUSE":     ["pause", "stop", "halt", "ruko", "band karo", "rok do",
                  "freeze"],
    "QUESTION":  ["what", "how", "why", "kya", "kaise", "kyun", "?", "show me",
                  "tell me", "kahan"],
    "STRATEGY":  ["should we", "plan", "roadmap", "next step", "kya karna",
                  "strategy", "decide"],
    "BLAST":     ["blast", "outreach", "send to", "campaign", "fire blast"],
}

PRIORITY_KEYWORDS = {
    "P0": ["urgent", "now", "asap", "down", "broken", "abhi", "turant"],
    "P1": ["soon", "today", "important", "aaj"],
    "P2": ["this week", "iteration"],
    "P3": ["later", "someday", "backlog"],
}

SCOPE_KEYWORDS = {
    "frontend": ["ui", "page", "screen", "button", "widget", "frontend",
                 "design", "color", "card", "banner", "modal"],
    "backend":  ["api", "endpoint", "router", "service", "scheduler", "cron",
                 "backend"],
    "db":       ["mongo", "collection", "schema", "field", "index", "db", "database"],
    "config":   ["env", "config", "secret", "key", "setting"],
}


async def _english_normalize(raw: str) -> str:
    """Use Claude with EMERGENT key to translate Hindi/Punjabi/Hinglish to clean
    English in ≤80 tokens. Fail-soft to raw input."""
    api_key = os.environ.get("EMERGENT_LLM_KEY", "")
    if not api_key or len(raw) > 800:
        return raw.strip()
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage  # type: ignore
        chat = LlmChat(
            api_key=api_key,
            session_id=f"fc-norm-{uuid.uuid4().hex[:8]}",
            system_message=("You normalize Hindi/Punjabi/Hinglish founder commands "
                            "to clean concise English. Output ONLY the English "
                            "version, no quotes, no preamble."),
        ).with_model("anthropic", "claude-3-5-haiku-20241022").with_params(max_tokens=120)
        out = await asyncio.wait_for(chat.send_message(UserMessage(text=raw)), timeout=8)
        return (out or "").strip() or raw
    except Exception:
        return raw.strip()


async def preprocess_input(raw: str) -> Dict[str, Any]:
    """Return structured task object."""
    raw = (raw or "").strip()
    english = await _english_normalize(raw)
    low = english.lower()

    intent = "QUESTION"
    for kind, words in INTENT_KEYWORDS.items():
        if any(w in low for w in words):
            intent = kind
            break

    priority = "P2"
    for p, words in PRIORITY_KEYWORDS.items():
        if any(w in low for w in words):
            priority = p
            break

    scope: List[str] = []
    for s, words in SCOPE_KEYWORDS.items():
        if any(w in low for w in words):
            scope.append(s)
    if not scope:
        # Default: if it mentions visual/page → frontend; else backend
        scope = ["frontend"] if any(k in low for k in ("page", "widget", "ui")) else ["backend"]

    title = english[:80].rstrip(".")
    if intent == "BUILD" and not title.lower().startswith(("add ", "build ", "create ")):
        title = "Build: " + title

    affected = re.findall(r"[a-zA-Z0-9_/]+\.(?:py|jsx?|tsx?|css|json|md)", english)

    return {
        "intent": intent, "title": title,
        "description": english, "scope": scope,
        "priority": priority, "affected_files": affected[:10],
        "raw_input": raw, "normalized_input": english,
        "preprocessed_at": datetime.now(timezone.utc).isoformat(),
    }


# ─── Stage 2: multi-model race ──────────────────────────────────────────────
async def _llm_call(model_provider: str, model_name: str, system: str,
                    prompt: str, max_tokens: int = 220, timeout: float = 12.0) -> str:
    api_key = os.environ.get("EMERGENT_LLM_KEY", "")
    if not api_key:
        return ""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage  # type: ignore
        chat = LlmChat(
            api_key=api_key, session_id=f"fc-{uuid.uuid4().hex[:10]}",
            system_message=system,
        ).with_model(model_provider, model_name).with_params(max_tokens=max_tokens)
        out = await asyncio.wait_for(chat.send_message(UserMessage(text=prompt)), timeout=timeout)
        return (out or "").strip()
    except Exception as e:
        logger.warning(f"[fc-llm] {model_provider}/{model_name} failed: {e}")
        return ""


def _strip_to_json(s: str) -> Dict[str, Any]:
    if not s:
        return {}
    s = s.strip()
    s = re.sub(r"^```(?:json)?\s*", "", s)
    s = re.sub(r"\s*```$", "", s)
    m = re.search(r"\{.*\}", s, flags=re.S)
    raw = m.group(0) if m else s
    try:
        return json.loads(raw)
    except Exception:
        return {"raw": s[:400]}


async def _claude_risk(task: Dict[str, Any]) -> Dict[str, Any]:
    sys = ("You are AUREM's risk analyst. Output STRICT JSON: "
           '{"feasibility":"high|medium|low","risks":[<=4 short strings],'
           '"blockers":[<=3 short strings]}. No prose, no markdown.')
    prompt = f"Task: {task['title']}\nDetails: {task['description'][:400]}"
    return _strip_to_json(await _llm_call("anthropic", "claude-sonnet-4-5-20250929",
                                          sys, prompt, max_tokens=500))


async def _gemini_plan(task: Dict[str, Any]) -> Dict[str, Any]:
    sys = ("You are AUREM's implementation architect. Output STRICT JSON: "
           '{"approach":"<short paragraph>","files":[<=5 path strings],'
           '"db_changes":[<=3 short strings],"new_dependencies":[<=3 names]}. '
           "No prose, no markdown.")
    prompt = (f"Task: {task['title']}\nScope: {task['scope']}\n"
              f"Details: {task['description'][:400]}")
    return _strip_to_json(await _llm_call("gemini", "gemini-2.5-flash",
                                          sys, prompt, max_tokens=600))


async def _ora_context(task: Dict[str, Any], db) -> Dict[str, Any]:
    """ORA brain: pull last 20 learnings, summarize relevance."""
    past = await recent_learnings(db, LEARNINGS_LOOKBACK)
    similar = []
    title_low = task["title"].lower()
    for r in past:
        prev_title = (r.get("task_title") or "").lower()
        if any(w in prev_title for w in title_low.split() if len(w) > 3):
            similar.append({
                "title": r.get("task_title"),
                "outcome": r.get("outcome"),
                "risk": r.get("risk_score"),
            })
    sys = ("You are ORA, AUREM's platform memory. Given a new task and a list "
           "of similar past tasks, output STRICT JSON: "
           '{"platform_context":"<short>","similar_past":[<=3 short strings],'
           '"warnings":[<=3 short strings]}. No prose, no markdown.')
    prompt = (f"New task: {task['title']}\nDetails: {task['description'][:300]}\n"
              f"Similar past: {json.dumps(similar[:5])[:600]}")
    out = _strip_to_json(await _llm_call("anthropic", "claude-3-5-haiku-20241022",
                                          sys, prompt, max_tokens=500))
    out.setdefault("similar_past_count", len(similar))
    return out


async def _nvidia_validate(task: Dict[str, Any]) -> Dict[str, Any]:
    """NVIDIA NIM technical validator — 4th model in the race.

    Free tier: 40 req/min. Falls back gracefully if key missing or rate-limited.
    """
    api_key = os.environ.get("NVIDIA_NIM_API_KEY", "")
    if not api_key:
        return {"skipped": "no_nvidia_key"}
    model = os.environ.get("NVIDIA_NIM_MODEL", "openai/gpt-oss-120b")
    sys = ("You are a technical validator. Output STRICT JSON: "
           '{"feasibility":"high|medium|low","tech_risks":[<=3 short strings],'
           '"architecture":"<one short sentence>",'
           '"code_approach":"<one short sentence>"}. No prose, no markdown.')
    prompt = (f"Task: {task['title']}\nScope: {task.get('scope','')}\n"
              f"Details: {task['description'][:400]}")

    import httpx
    last_err = ""
    for attempt in range(3):  # 40 rpm — 2s backoff between retries
        try:
            async with httpx.AsyncClient(timeout=25) as c:
                r = await c.post(
                    "https://integrate.api.nvidia.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}",
                              "Accept": "application/json"},
                    json={
                        "model": model,
                        "max_tokens": 320, "temperature": 0.2,
                        "messages": [
                            {"role": "system", "content": sys},
                            {"role": "user", "content": prompt},
                        ],
                    },
                )
            if r.status_code == 429:
                await asyncio.sleep(2)
                last_err = "rate_limited"
                continue
            if r.status_code >= 400:
                return {"skipped": f"http_{r.status_code}",
                         "body": r.text[:200]}
            data = r.json()
            text = (data.get("choices", [{}])[0].get("message", {})
                     .get("content", "") or "").strip()
            return _strip_to_json(text)
        except Exception as e:
            last_err = f"{type(e).__name__}:{str(e)[:80]}"
            await asyncio.sleep(1.5)
    return {"skipped": last_err or "unknown"}


async def multi_model_race(task: Dict[str, Any], db) -> Dict[str, Any]:
    """Run 4 LLMs in parallel and merge to a single Council Brief.

    Iter 315: enrich brief with `proven_bets_summary` so the Council /
    optimized prompt biases BUILD toward patterns that actually convert."""
    started = datetime.now(timezone.utc)
    results = await asyncio.gather(
        _claude_risk(task), _gemini_plan(task), _ora_context(task, db),
        _nvidia_validate(task),
        return_exceptions=True,
    )
    claude_a, gemini_p, ora_c, nvidia_v = (
        r if isinstance(r, dict) else {} for r in results)

    proven_summary = ""
    try:
        from services.attribution import proven_bets_summary
        proven_summary = await proven_bets_summary(db, days=30)
    except Exception as e:
        logger.debug(f"[pipeline] proven bets summary failed: {e}")

    return {
        "claude_analysis": claude_a, "gemini_plan": gemini_p,
        "ora_context": ora_c, "nvidia_analysis": nvidia_v,
        "proven_bets_summary": proven_summary,
        "merged_at": datetime.now(timezone.utc).isoformat(),
        "race_duration_s": round((datetime.now(timezone.utc) - started).total_seconds(), 2),
    }


# ─── Stage 3: enhance council output ────────────────────────────────────────
def _build_optimized_prompt(task: Dict[str, Any], race: Dict[str, Any]) -> str:
    g = race.get("gemini_plan") or {}
    files = ", ".join((g.get("files") or [])[:5]) or "<inferred>"
    approach = (g.get("approach") or task["description"])[:280]
    db_changes = ", ".join((g.get("db_changes") or [])[:3]) or "none"
    risks = ", ".join((race.get("claude_analysis") or {}).get("risks", [])[:3]) or "none"
    proven = (race.get("proven_bets_summary") or "").strip()
    proven_line = (
        f"PROVEN CONVERTERS (last 30d): {proven[:400]} — bias toward these patterns when extending features."
        if proven else ""
    )
    return (
        f"TASK: {task['title']}\n"
        f"INTENT: {task['intent']} · PRIORITY: {task['priority']}\n"
        f"APPROACH: {approach}\n"
        f"FILES TO TOUCH: {files}\n"
        f"DB CHANGES: {db_changes}\n"
        f"RISKS TO AVOID: {risks}\n"
        + (f"{proven_line}\n" if proven_line else "")
        + "CONSTRAINTS: production-ready · no env edits · "
        + "no auth-router edits · no locked-build edits"
    )


def _risk_score_1_10(decision: Dict[str, Any], race: Dict[str, Any]) -> int:
    """Normalize council 0-1 confidence + claude feasibility into 1-10 risk."""
    avg = float(decision.get("avg_confidence") or 0.6)
    base = max(1, min(10, round(10 * (1 - avg))))   # low conf → high risk
    feas = (race.get("claude_analysis") or {}).get("feasibility", "")
    if feas == "low":
        base = min(10, base + 3)
    elif feas == "medium":
        base = min(10, base + 1)
    risks = (race.get("claude_analysis") or {}).get("risks") or []
    blockers = (race.get("claude_analysis") or {}).get("blockers") or []
    base = min(10, base + min(2, len(blockers)))
    if len(risks) >= 4:
        base = min(10, base + 1)
    return max(1, base)


def _auto_build_eligible(task: Dict[str, Any], race: Dict[str, Any],
                          risk_score: int) -> Dict[str, Any]:
    g = race.get("gemini_plan") or {}
    files = list(g.get("files") or [])
    new_deps = list(g.get("new_dependencies") or [])
    db_changes = list(g.get("db_changes") or [])
    blockers: List[str] = []
    if len(files) > 3:
        blockers.append(f"too_many_files ({len(files)})")
    if any(d for d in new_deps if d and d.lower() not in ("none", "n/a", "")):
        blockers.append(f"new_dependencies ({new_deps})")
    if any(d for d in db_changes if d and d.lower() not in ("none", "n/a", "")):
        blockers.append(f"db_schema_changes ({db_changes})")
    if risk_score > 4:
        blockers.append(f"risk_too_high (risk={risk_score}/10)")
    if "config" in task.get("scope", []):
        blockers.append("env_or_config_change")
    bad_files = [f for f in files if f and not _is_path_safe(f)]
    if bad_files:
        blockers.append(f"path_outside_whitelist ({bad_files})")
    return {"eligible": len(blockers) == 0, "blockers": blockers}


def enhance_council(council_record: Dict[str, Any],
                    task: Dict[str, Any],
                    race: Dict[str, Any]) -> Dict[str, Any]:
    """Pure function — does NOT mutate council.py. Returns enriched dict."""
    risk_score = _risk_score_1_10(council_record, race)
    abe = _auto_build_eligible(task, race, risk_score)
    optimized_prompt = _build_optimized_prompt(task, race)

    decision_label = council_record.get("decision", "veto")
    if decision_label == "approve":
        verdict = "APPROVED"
    elif decision_label == "escalate":
        verdict = "NEEDS_CLARIFICATION"
    else:
        verdict = "REJECTED"

    return {
        **council_record,
        "verdict": verdict,
        "risk_score": risk_score,
        "auto_build_eligible": abe["eligible"],
        "auto_build_blockers": abe["blockers"],
        "optimized_prompt": optimized_prompt,
        "estimated_tokens": len(optimized_prompt.split()) * 2,
    }


# ─── Stage 6: ORA learnings ─────────────────────────────────────────────────
async def record_learning(db, payload: Dict[str, Any]) -> str:
    if db is None:
        return ""
    learning_id = uuid.uuid4().hex[:14]
    doc = {
        "learning_id": learning_id,
        "task_title": payload.get("task_title"),
        "raw_input": payload.get("raw_input"),
        "optimized_prompt": payload.get("optimized_prompt"),
        "council_verdict": payload.get("council_verdict"),
        "risk_score": payload.get("risk_score"),
        "outcome": payload.get("outcome"),
        "files_changed": payload.get("files_changed") or [],
        "duration_seconds": payload.get("duration_seconds"),
        "build_path": payload.get("build_path"),
        "build_summary": payload.get("build_summary"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    try:
        await db[LEARNINGS_COLLECTION].insert_one(doc)
    except Exception as e:
        logger.warning(f"[fc-learning] insert failed: {e}")
    return learning_id


async def recent_learnings(db, n: int = LEARNINGS_LOOKBACK) -> List[Dict[str, Any]]:
    if db is None:
        return []
    try:
        cur = db[LEARNINGS_COLLECTION].find({}, {"_id": 0}).sort("timestamp", -1).limit(int(n))
        return await cur.to_list(length=int(n))
    except Exception:
        return []
