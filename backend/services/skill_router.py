"""
ORA Skills Router — iter 282ak (Prompt 8, Tasks B + E).

Thin orchestration layer on top of AUREM's existing A2A agents. ORA chat
delegates to `route_to_skill()` first; if a skill matches, `execute_skill()`
calls the real agent function (no duplicate logic). On any miss/failure,
the caller falls back to its stock LLM chat.

Skills live as markdown in /app/ora_skills/*.md so humans (and ORA itself
via the Learning Engine) can edit them without code changes.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# iter 282al-29 — SKILLS_DIR now resolves relative to the backend package
# so skill .md files ship with the deployed image. Falls back to the
# legacy /app/ora_skills location if the backend-local copy is missing
# (preserves dev-environment behaviour).
_BACKEND_SKILLS = Path(__file__).resolve().parent.parent / "ora_skills"
_LEGACY_SKILLS = Path("/app/ora_skills")
# Prefer whichever directory actually has the sales skill files
SKILLS_DIR = _BACKEND_SKILLS if (_BACKEND_SKILLS / "scout_scan.md").exists() else _LEGACY_SKILLS

SKILLS = [
    "scout_scan",
    "outreach_compose",
    "followup_check",
    "closer_check",
    "morning_brief",
    "casl_check",
    "notebooklm_research",
    "seo_backlinks",
]

# iter 282al — Dev skills imported from antigravity-awesome-skills.
# ORA uses these when the user is clearly coding / debugging AUREM itself.
# All map to None (no A2A agent) — the LLM handles dev tasks with the skill
# content + dev_aurem_codebase context injected into its prompt.
DEV_SKILLS = [
    "dev_senior-fullstack",
    "dev_backend-dev-guidelines",
    "dev_security-auditor",
    "dev_test-driven-development",
    "dev_code-refactoring",
    "dev_api-design",
    "dev_multi-agent",
    "dev_debugging",
    "dev_fastapi",
    "dev_react-patterns",
    "dev_startup-founder",
    "dev_system-scan",
]

URL_RE = re.compile(r"https?://[^\s<>\"')]+", re.IGNORECASE)


# ─────────────────────────────────────────────────────────────────────
# Agent wiring — resolved lazily so a missing import never takes out ORA
# ─────────────────────────────────────────────────────────────────────
def _load_scout():
    from services import startup_init
    from shared.agents.hunter_ora import HunterORA
    return HunterORA(getattr(startup_init, "_db", None))


def _load_followup():
    from services import startup_init
    from shared.agents.followup_ora import FollowupORA
    return FollowupORA(getattr(startup_init, "_db", None))


def _load_closer():
    from services import startup_init
    from shared.agents.closer_ora import CloserORA
    return CloserORA(getattr(startup_init, "_db", None))


async def _run_composer(user_message: str, db, context: dict):
    """outreach_compose skill — returns a draft without sending."""
    from services.outreach_composer import compose_outreach
    lead = context.get("lead") or {
        "business_name": "the lead",
        "category": "general",
        "city": "",
        "lead_id": context.get("lead_id") or "draft",
    }
    channel = context.get("channel") or "email"
    step = int(context.get("step") or 1)
    r = await compose_outreach(lead, channel, step, db=db)
    subject_line = f"Subject: {r.get('subject')}\n\n" if r.get("subject") else ""
    return (
        f"Here is a draft {channel} (step {step}):\n\n"
        f"{subject_line}{r.get('body') or '(empty)'}\n\n"
        "Should I send this or adjust anything?"
    )


async def _run_morning_brief(user_message: str, db, context: dict):
    from services.morning_brief import run_morning_brief
    try:
        brief = await run_morning_brief()
        return (brief.get("brief_text") if isinstance(brief, dict) else str(brief)) \
                or "No brief available."
    except Exception as e:
        logger.debug(f"[skills] morning_brief failed: {e}")
        return "I couldn't pull the brief just now — please try again in a minute."


async def _run_scout(user_message: str, db, context: dict):
    url = context.get("url") or _extract_url(user_message)
    if url:
        try:
            from services.website_scraper import scan_website
            scan = await scan_website(url)
            return (
                "Scout scan for " + url + ":\n"
                f"- Source: {scan.get('source')}\n"
                f"- Status: {scan.get('status')}\n"
                f"- Content preview: {(scan.get('content') or '')[:200]}"
            )
        except Exception as e:
            logger.debug(f"[skills] scout scan failed: {e}")
    try:
        agent = _load_scout()
        res = await agent.run_cycle()
        return f"Scout cycle run: {json.dumps(res, default=str)[:400]}"
    except Exception as e:
        return f"Scout agent unavailable: {type(e).__name__}"


async def _run_followup(user_message: str, db, context: dict):
    try:
        agent = _load_followup()
        res = await agent.run_cycle()
        return f"Follow-up cycle: {json.dumps(res, default=str)[:400]}"
    except Exception as e:
        return f"Follow-up agent unavailable: {type(e).__name__}"


async def _run_closer(user_message: str, db, context: dict):
    try:
        agent = _load_closer()
        res = await agent.run_cycle()
        return f"Closer cycle: {json.dumps(res, default=str)[:400]}"
    except Exception as e:
        return f"Closer agent unavailable: {type(e).__name__}"


async def _run_casl(user_message: str, db, context: dict):
    """Cheap local compliance check — no LLM needed for the deterministic part."""
    opt_out = any(p in user_message.lower() for p in [
        "reply stop", "text stop", "opt out", "unsubscribe",
        "opt-out", "txt stop", "stop to opt",
    ])
    if not opt_out:
        return ("CASL FAIL: message is missing an opt-out instruction "
                "(e.g. 'Reply STOP to opt out' or 'Txt STOP').")
    if any(x in user_message.lower() for x in [
        "guaranteed", "100% success", "free money", "risk-free",
    ]):
        return "CASL FAIL: contains absolute claims that may violate truth-in-advertising."
    return "CASL PASS: opt-out present and no absolute claims detected."


async def _run_seo_backlinks(user_message: str, db, context: dict) -> str:
    """seo_backlinks skill — quick scan, brief reply. Never raises."""
    from services.unlinked_mentions_service import scan_for_unlinked_mentions
    biz  = context.get("business_name")
    site = context.get("website") or context.get("website_url")
    if not biz or not site:
        return ("I need a business name and website to run a backlink "
                "scan. Tell me both (or open a client's portal and ask "
                "again).")
    res = await scan_for_unlinked_mentions(biz, site, db, limit=5)
    n = res.get("total_unlinked", 0)
    mentions = res.get("mentions") or []
    if res.get("error") and n == 0:
        return (f"I couldn't find mentions for {biz} right now "
                f"(reason: {res['error']}). Want me to try again in a bit?")
    if n == 0:
        return (f"No unlinked mentions found for {biz} today. "
                "I'll scan again next week.")
    lines = [f"Found {n} unlinked mentions for {biz}:"]
    for m in mentions[:5]:
        ctx = (m.get("mention_context") or "")[:80]
        lines.append(f"  • {m.get('domain','?')} — \"{ctx}…\"")
    lines.append("Want me to send outreach to reclaim these?")
    return "\n".join(lines)


async def _run_notebooklm(user_message: str, db, context: dict) -> str:
    """notebooklm_research skill — direct API call, no A2A agent."""
    from services.notebooklm_service import research_lead
    lead = context.get("lead") or {
        "business_name": context.get("business_name") or "this lead",
        "website":       context.get("website") or context.get("url"),
    }
    return await research_lead(lead, user_message)


SKILL_TO_AGENT = {
    "scout_scan":          _run_scout,
    "outreach_compose":    _run_composer,
    "followup_check":      _run_followup,
    "closer_check":        _run_closer,
    "morning_brief":       _run_morning_brief,
    "casl_check":          None,   # deterministic — handled via _run_casl
    "notebooklm_research": _run_notebooklm,
    "seo_backlinks":       _run_seo_backlinks,
    # iter 282al — dev skills: LLM only, no A2A agent.
    "dev_senior-fullstack":        None,
    "dev_backend-dev-guidelines":  None,
    "dev_security-auditor":        None,
    "dev_test-driven-development": None,
    "dev_code-refactoring":        None,
    "dev_api-design":              None,
    "dev_multi-agent":             None,
    "dev_debugging":               None,
    "dev_fastapi":                 None,
    "dev_react-patterns":          None,
    "dev_startup-founder":         None,
    "dev_system-scan":             None,
}


# ─────────────────────────────────────────────────────────────────────
# Dev-intent detection — iter 282al
# Zero-cost keyword pass for coding/debugging tasks. Runs BEFORE sales
# keyword routing and LLM fallback so dev chat never spends tokens on
# routing. Order matters: more specific categories first.
# ─────────────────────────────────────────────────────────────────────
_DEV_INTENT_RULES = (
    # iter 282al-13 — system-scan must match BEFORE generic debug/security
    # rules so "scan our system / audit aurem / check status" lands here.
    ("dev_system-scan", (
        "scan our system", "scan the system", "scan aurem",
        "audit aurem", "audit our system", "system audit",
        "system status", "system health", "status of system",
        "is everything ok", "is everything healthy", "health check",
        "diagnose aurem", "what's broken", "whats broken",
        "self-audit", "self audit", "run audit on aurem",
    )),
    ("dev_test-driven-development", (
        "pytest", "unit test", "write a test", "write tests", "failing test",
        "test case", "test coverage", "assert ", "mock ", "tdd",
    )),
    ("dev_security-auditor", (
        "security review", "security issue", "security issues",
        "jwt", "auth flow", "vulnerable", "vulnerability",
        "timing attack", "sql injection", "xss", "csrf",
        "permission check", "audit this", "casl audit", "token leak",
    )),
    ("dev_debugging", (
        "fix this", "fix the bug", "there's a bug", "bug in", "debug",
        "traceback", "stack trace", "broken", "not working", "error:",
        "exception:", "why is this failing", "not returning",
    )),
    ("dev_code-refactoring", (
        "refactor", "clean up this code", "optimize this code",
        "improve this code", "simplify this", "dead code", "tech debt",
    )),
    ("dev_react-patterns", (
        "react ", "jsx ", "component ", "usestate", "useeffect",
        "frontend ", " render ", "props ", " hook ", "shadcn",
    )),
    ("dev_fastapi", (
        "fastapi", "uvicorn", "pydantic", " depends", "background task",
        "async def", "motor ", "mongodb query", "asyncio",
    )),
    ("dev_api-design", (
        "rest api", "endpoint design", "versioning", "response schema",
        "openapi", "swagger", "status code",
    )),
    ("dev_multi-agent", (
        "a2a", "agent coordination", "skill router", "multi-agent",
        "scout agent", "envoy agent", "closer agent", "follow-up agent",
    )),
    ("dev_backend-dev-guidelines", (
        "new endpoint", "new route", "new router", "add api", "build api",
        "service pattern", "error handling", "dependency injection",
    )),
    ("dev_senior-fullstack", (
        "full stack", "fullstack", "end-to-end feature", "backend and frontend",
        "react + fastapi", "wire up", "implement feature",
    )),
    ("dev_startup-founder", (
        "product decision", "pricing", "mvp scope", "what to build next",
        "roadmap", "prioritize",
    )),
)


def detect_dev_intent(message: str) -> str | None:
    """Return the best matching dev skill name or None. Zero LLM cost."""
    if not message:
        return None
    msg = message.lower()
    for skill, keywords in _DEV_INTENT_RULES:
        if any(kw in msg for kw in keywords):
            # Only return if the skill file actually exists on disk
            if (SKILLS_DIR / f"{skill}.md").exists():
                return skill
    return None


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────
def _extract_url(text: str) -> str | None:
    if not text:
        return None
    m = URL_RE.search(text)
    return m.group(0).rstrip(".,);]") if m else None


def extract_url(text: str) -> str | None:
    """Public alias (spec)."""
    return _extract_url(text)


def _load_skill_triggers() -> dict[str, str]:
    """Returns {skill_name: one-liner trigger description} from .md files."""
    out = {}
    for s in SKILLS:
        p = SKILLS_DIR / f"{s}.md"
        try:
            text = p.read_text(encoding="utf-8")
            m = re.search(r"##\s*Trigger intent\s*\n(.+?)(?=\n##|\Z)",
                            text, re.S | re.IGNORECASE)
            out[s] = (m.group(1).strip() if m else text.strip())[:400]
        except Exception:
            out[s] = ""
    return out


# ─────────────────────────────────────────────────────────────────────
# Intent-routing
# ─────────────────────────────────────────────────────────────────────
# Keyword-first routing → deterministic, zero-cost. LLM is used only as
# a secondary tiebreaker when the keyword pass is ambiguous.
_KEYWORD_MAP = [
    ("seo_backlinks", (
        "backlink", "backlinks", "unlinked", "unlinked mentions",
        " seo", "who mentions us", "who mentions aurem",
        "link reclamation", "reclaim a link", "reclaim links",
        "link building", "linking to us", "sites linking",
    )),
    ("scout_scan", (
        "scan", "check site", "check website", "research business",
        "find leads", "what does their site say", "scout",
    )),
    ("morning_brief", (
        "morning brief", "brief please", "give me a brief",
        "summary", "update", "what happened", "overnight", "morning report",
    )),
    ("closer_check", (
        "close", "convert", "objection", "they replied", "interested",
        "pricing", "sign up", "ready to buy",
    )),
    ("followup_check", (
        "follow up", "follow-up", "drip", "contacted",
        "how many touches", "sequence", "did we reach out",
    )),
    ("outreach_compose", (
        "write email", "draft sms", "compose message", "outreach for",
        "send to", "write to this lead", "draft outreach",
    )),
    ("casl_check", (
        "casl", "opt out", "opt-out", "compliant", "legal to send",
        "can we send", "is this allowed",
    )),
    ("notebooklm_research", (
        "research this", "deep dive", "deep-dive", "analyze docs",
        "create a notebook", "research notebook", "study this lead",
        "do a deep dive on", "notebooklm",
    )),
]


async def route_to_skill(user_message: str, db=None) -> str | None:
    """Map a chat message to one of SKILLS / DEV_SKILLS or None. Never raises."""
    if not user_message:
        return None

    # iter 282al — dev-intent check FIRST. Coding tasks are
    # high-confidence via keywords and we want zero LLM tokens burned
    # on routing for them.
    dev_hit = detect_dev_intent(user_message)
    if dev_hit:
        return dev_hit

    msg = user_message.lower()

    # ── Fast sales keyword pass
    for skill, keywords in _KEYWORD_MAP:
        if any(kw in msg for kw in keywords):
            return skill

    # ── Cache check (avoid hammering LLM with unmatched chatter)
    cache_key = f"route:{hash(msg) & 0xFFFFFFFF}"
    if db is not None:
        try:
            hit = await db.skill_route_cache.find_one(
                {"_id": cache_key,
                 "ts": {"$gt": datetime.now(timezone.utc) - timedelta(hours=1)}},
                projection={"_id": 0, "skill": 1},
            )
            if hit:
                return hit.get("skill")
        except Exception:
            pass

    # ── LLM fallback — only when keyword pass missed
    api_key = os.environ.get("EMERGENT_LLM_KEY", "").strip()
    if not api_key:
        return None

    try:
        triggers = _load_skill_triggers()
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        prompt = (
            "Message: " + user_message + "\n\n"
            "Skills available:\n"
            + "\n".join(f"- {s}: {triggers.get(s,'')[:120]}" for s in SKILLS)
            + "\n\nReply with ONLY the skill name (no explanation), or the "
              "word 'none' if no skill matches."
        )
        chat = (LlmChat(api_key=api_key, session_id="skill-route",
                         system_message="You route user intents to skill names. Reply with one word only.")
                .with_model("anthropic", "claude-sonnet-4-5-20250929"))
        try:
            chat = chat.with_max_tokens(20)
        except Exception:
            pass
        resp = await asyncio.wait_for(
            chat.send_message(UserMessage(text=prompt)), timeout=8.0)
        picked = (resp or "").strip().lower().split()[0].strip(".,")
        skill = picked if picked in SKILLS else None
    except Exception as e:
        logger.debug(f"[skills] LLM route failed: {e}")
        skill = None

    # Cache the result (positive or negative) for 1h
    if db is not None:
        try:
            await db.skill_route_cache.update_one(
                {"_id": cache_key},
                {"$set": {"_id": cache_key, "skill": skill,
                           "ts": datetime.now(timezone.utc)}},
                upsert=True,
            )
        except Exception:
            pass
    return skill


# ─────────────────────────────────────────────────────────────────────
# Execute a resolved skill
# ─────────────────────────────────────────────────────────────────────
async def _run_dev_skill(skill_name: str, user_message: str,
                          db, context: dict) -> str:
    """iter 282al — execute a dev_* skill via LLM with AUREM context.

    Loads `ora_skills/{skill_name}.md` as the primary skill guidance
    and ALWAYS prepends `ora_skills/dev_aurem_codebase.md` so ORA
    answers every dev task with full stack context (file paths, env,
    coding rules). Returns the LLM response or a graceful fallback.
    """
    try:
        skill_body = (SKILLS_DIR / f"{skill_name}.md").read_text(encoding="utf-8")
    except Exception as e:
        logger.debug(f"[skills] dev skill {skill_name} read failed: {e}")
        # iter 282al-13 — clearer error: list what files DO exist so
        # the founder can see if it's a deploy mismatch.
        try:
            available = ", ".join(sorted([
                p.stem for p in SKILLS_DIR.glob("dev_*.md")
            ])[:20])
        except Exception:
            available = "(unable to list skill dir)"
        return (f"Dev skill `{skill_name}` not loadable from "
                f"{SKILLS_DIR} — {type(e).__name__}: {str(e)[:80]}. "
                f"Available dev skills: {available}.")
    aurem_ctx = ""
    try:
        aurem_ctx = (SKILLS_DIR / "dev_aurem_codebase.md").read_text(encoding="utf-8")
        # iter 282al-13 — cap ctx + skill to keep ngrok-tunneled Sovereign
        # responsive (long prompts blow past tunnel timeouts).
        if len(aurem_ctx) > 4000:
            aurem_ctx = aurem_ctx[:4000] + "\n[... codebase context truncated ...]"
    except Exception:
        pass
    if len(skill_body) > 4000:
        skill_body = skill_body[:4000] + "\n[... skill body truncated ...]"

    # iter 282al-13 — `dev_system-scan`: run a REAL audit and feed it in.
    live_block = ""
    if skill_name == "dev_system-scan":
        try:
            live_block = await _gather_live_system_scan(db)
        except Exception as e:
            logger.warning(f"[skills] live system scan failed: {e}")
            live_block = (
                f"=== LIVE SYSTEM SCAN ===\n"
                f"⚠️ Scan partially failed: {type(e).__name__}: {str(e)[:140]}\n"
            )

    system_msg = (
        "You are ORA helping build the AUREM platform itself.\n\n"
        "=== AUREM CODEBASE CONTEXT ===\n"
        f"{aurem_ctx}\n\n"
        f"=== SKILL: {skill_name} ===\n"
        f"{skill_body}\n\n"
        + (live_block + "\n\n" if live_block else "")
        + "Answer the user's dev question concretely. Reference real AUREM "
        "files where relevant. Do not invent file paths. If you'd need to "
        "read a file to answer, say which file and why."
    )
    # iter 282al-13 — for system-scan we can also short-circuit: if the
    # LLM cascade is fully unreachable, return the raw scan so the
    # founder still sees the data.
    try:
        # iter 282al-5 — route dev skill through unified gateway
        # (Sovereign → OpenRouter → Emergent → fallback).
        # iter 282al-13 — wrap with 12s budget so the chat endpoint's
        # 45s outer cap never trips. Hard fallback is the live block
        # itself for system-scan (data > nothing).
        import asyncio as _aio
        from services.llm_gateway import call_llm
        # iter 282al-13 — dev mode: skip Sovereign (ngrok latency on 600
        # tokens busts the chat budget). OpenRouter → Emergent only.
        resp = await _aio.wait_for(
            call_llm(system_msg, user_message, max_tokens=600,
                       skip_sovereign=True),
            timeout=25.0,
        )
        text = (resp or "").strip()
        if not text:
            if live_block:
                return live_block + "\n\n(LLM returned empty; raw scan above.)"
            return "(empty LLM reply)"
        return text
    except Exception as e:
        logger.warning(f"[skills] dev_skill {skill_name} LLM failed: {e}")
        if live_block:
            return (live_block
                    + f"\n\n(LLM unreachable — {type(e).__name__}; raw scan above.)")
        return (f"I loaded the {skill_name} skill but the LLM call "
                 f"failed ({type(e).__name__}). Try again in a moment.")


async def _gather_live_system_scan(db) -> str:
    """Run a real, fast audit of the AUREM platform and format it as a
    text block the LLM can interpret. Used by `dev_system-scan`.
    """
    import asyncio as _aio
    from datetime import datetime, timezone, timedelta

    lines: list[str] = ["=== LIVE SYSTEM SCAN ==="]

    # 1. Self-audit on aurem.live (deterministic, no PSI dependency)
    try:
        from services.self_audit import run_self_audit
        row = await _aio.wait_for(
            run_self_audit(db, target_url="https://aurem.live"),
            timeout=15.0,
        )
        lines.append(
            f"[aurem.live SEO] overall={row.get('overall_score')}/100 · "
            f"perf={row.get('performance')} seo={row.get('seo')} "
            f"a11y={row.get('accessibility')} bp={row.get('best_practices')}"
        )
    except Exception as e:
        lines.append(f"[aurem.live SEO] FAILED: {type(e).__name__}: {str(e)[:120]}")

    # 2. Pillars Map flow status
    try:
        from routers.pillars_map_router import _gather_flows
        flows = await _aio.wait_for(_gather_flows(), timeout=10.0)
        red = [f["id"] for f in flows if f.get("status") == "red"]
        yel = [f["id"] for f in flows if f.get("status") == "yellow"]
        grn = [f for f in flows if f.get("status") == "green"]
        lines.append(
            f"[Pillars] {len(grn)}/{len(flows)} green · "
            f"{len(yel)} yellow · {len(red)} red"
        )
        if red:
            lines.append("  red: " + ", ".join(red[:8]))
        if yel:
            lines.append("  yellow: " + ", ".join(yel[:8]))
    except Exception as e:
        lines.append(f"[Pillars] FAILED: {type(e).__name__}: {str(e)[:80]}")

    # 3. Scheduler
    try:
        from routers import registry as _r
        sched = getattr(_r, "aurem_scheduler", None)
        if sched is None:
            lines.append("[Scheduler] not initialised")
        else:
            jobs = sched.get_jobs()
            lines.append(f"[Scheduler] running={sched.running} · "
                          f"jobs={len(jobs)}")
    except Exception as e:
        lines.append(f"[Scheduler] FAILED: {type(e).__name__}: {str(e)[:60]}")

    # 4. Emails last 24h + intent breakdown
    if db is not None:
        try:
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
            emailed = await db.campaign_leads.count_documents(
                {"last_email_at": {"$gte": cutoff}},
            )
            inbound_24h = await db.inbound_replies.count_documents(
                {"received_at": {"$gte": datetime.now(timezone.utc) - timedelta(hours=24)}},
            )
            inbound_pos = await db.inbound_replies.count_documents(
                {"received_at": {"$gte": datetime.now(timezone.utc) - timedelta(hours=24)},
                 "intent": "positive"},
            )
            lines.append(
                f"[Outreach 24h] emails_sent={emailed} · "
                f"inbound={inbound_24h} (positive={inbound_pos})"
            )
        except Exception as e:
            lines.append(f"[Outreach 24h] FAILED: {type(e).__name__}: {str(e)[:60]}")

    # 5. Backend health
    try:
        import httpx
        async with httpx.AsyncClient(timeout=3.0) as c:
            r = await c.get("http://localhost:8001/api/health")
            lines.append(f"[Backend] /api/health → {r.status_code}")
    except Exception as e:
        lines.append(f"[Backend] /api/health FAILED: {type(e).__name__}: {str(e)[:60]}")

    return "\n".join(lines)


async def execute_skill(skill_name: str, user_message: str,
                        db=None, context: dict | None = None) -> str:
    """Run the skill. Always returns a string. Never raises."""
    context = context or {}
    try:
        if skill_name == "casl_check":
            result = await _run_casl(user_message, db, context)
        elif skill_name and skill_name.startswith("dev_"):
            # iter 282al — dev skills route through the LLM with
            # AUREM codebase context pre-loaded.
            result = await _run_dev_skill(skill_name, user_message, db, context)
        else:
            runner = SKILL_TO_AGENT.get(skill_name)
            if runner is None:
                return "Skill unavailable."
            result = await runner(user_message, db, context)
    except Exception as e:
        logger.warning(f"[skills] execute_skill {skill_name} failed: {e}")
        return f"I'll help with that. (skill {skill_name} temporarily unavailable: {type(e).__name__})"

    # Log invocation
    if db is not None:
        try:
            await db.skill_invocations.insert_one({
                "skill":        skill_name,
                "user_message": (user_message or "")[:200],
                "lead_id":      context.get("lead_id"),
                "ts":           datetime.now(timezone.utc),
            })
        except Exception:
            pass
    return str(result) if result is not None else ""


# ─────────────────────────────────────────────────────────────────────
# Sync wrappers for pytest
# ─────────────────────────────────────────────────────────────────────
def _run_sync(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                return ex.submit(lambda: asyncio.run(coro)).result()
    except RuntimeError:
        pass
    return asyncio.run(coro)


def route_sync(msg: str, db=None) -> str | None:
    return _run_sync(route_to_skill(msg, db))


def execute_skill_sync(skill: str, msg: str, db=None, context=None) -> str:
    return _run_sync(execute_skill(skill, msg, db, context))


# ─────────────────────────────────────────────────────────────────────
# Health chip
# ─────────────────────────────────────────────────────────────────────
async def skills_router_health() -> dict:
    missing = [s for s in SKILLS if not (SKILLS_DIR / f"{s}.md").exists()]
    if missing:
        return {"ok": False, "status": "red",
                "detail": f"missing skill files: {missing}"}
    try:
        r1 = await route_to_skill("scan this website", None)
        r2 = await route_to_skill("give me a brief", None)
        r3 = await route_to_skill("there's a bug in scout_agent.py fix it", None)
    except Exception as e:
        return {"ok": False, "status": "red",
                "detail": f"route_to_skill raised: {e}"}

    dev_present = [s for s in DEV_SKILLS if (SKILLS_DIR / f"{s}.md").exists()]
    aurem_ctx = (SKILLS_DIR / "dev_aurem_codebase.md").exists()

    base = {
        "sales_skills":     len(SKILLS),
        "dev_skills":       len(dev_present),
        "total":            len(SKILLS) + len(dev_present),
        "aurem_ctx_loaded": aurem_ctx,
        "routing_verified": r1 == "scout_scan" and r2 == "morning_brief"
                             and (r3 or "").startswith("dev_"),
    }
    if base["routing_verified"]:
        return {"ok": True, "status": "green",
                "detail": f"{len(SKILLS)} sales + {len(dev_present)} dev skills loaded, routing verified",
                **base}
    return {"ok": True, "status": "yellow",
            "detail": f"skill files exist but routing off (r1={r1}, r2={r2}, r3={r3})",
            **base}


__all__ = [
    "SKILLS",
    "DEV_SKILLS",
    "SKILL_TO_AGENT",
    "route_to_skill",
    "execute_skill",
    "route_sync",
    "execute_skill_sync",
    "extract_url",
    "skills_router_health",
    "detect_dev_intent",
]
