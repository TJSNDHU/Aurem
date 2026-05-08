"""
AUREM Hermes Identity System
=============================
Loads SOUL.md and USER.md into every ORA system prompt.
Manages procedural memory (skill docs) and dream consolidation.
Inspired by NousResearch/hermes-agent architecture.
"""
import os
import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict, List
from pathlib import Path

logger = logging.getLogger(__name__)

IDENTITY_DIR = Path(__file__).parent.parent / "identity"
SKILLS_DIR = Path(__file__).parent.parent / "skills"

# Ensure directories exist
IDENTITY_DIR.mkdir(exist_ok=True)
SKILLS_DIR.mkdir(exist_ok=True)


def load_soul() -> str:
    """Load ORA's permanent identity from SOUL.md."""
    soul_path = IDENTITY_DIR / "SOUL.md"
    try:
        if soul_path.exists():
            return soul_path.read_text(encoding="utf-8")
    except Exception as e:
        logger.warning(f"[Identity] Failed to load SOUL.md: {e}")
    return ""


def load_user() -> str:
    """Load operator preferences from USER.md."""
    user_path = IDENTITY_DIR / "USER.md"
    try:
        if user_path.exists():
            return user_path.read_text(encoding="utf-8")
    except Exception as e:
        logger.warning(f"[Identity] Failed to load USER.md: {e}")
    return ""


def get_identity_prompt() -> str:
    """Build the identity injection block for system prompts."""
    soul = load_soul()
    user = load_user()

    parts = []
    if soul:
        parts.append(f"=== ORA IDENTITY (SOUL) ===\n{soul}")
    if user:
        parts.append(f"\n=== OPERATOR PROFILE ===\n{user}")

    return "\n".join(parts)


# ═══════════════════════════════════════
# PROCEDURAL MEMORY — Skill Documents
# ═══════════════════════════════════════

def list_skills() -> List[Dict]:
    """List all available skill documents."""
    skills = []
    for f in SKILLS_DIR.glob("*.md"):
        try:
            content = f.read_text(encoding="utf-8")
            title = content.split("\n")[0].strip("# ").strip() if content else f.stem
            skills.append({
                "name": f.stem,
                "title": title,
                "path": str(f),
                "size": len(content),
                "modified": datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc).isoformat(),
            })
        except Exception:
            continue
    return skills


def get_skill(name: str) -> Optional[str]:
    """Retrieve a skill document by name."""
    skill_path = SKILLS_DIR / f"{name}.md"
    if skill_path.exists():
        return skill_path.read_text(encoding="utf-8")
    # Fuzzy match
    for f in SKILLS_DIR.glob("*.md"):
        if name.lower() in f.stem.lower():
            return f.read_text(encoding="utf-8")
    return None


def find_relevant_skills(query: str, max_skills: int = 2) -> List[str]:
    """Find skills relevant to a query using keyword matching."""
    query_lower = query.lower()
    query_words = set(query_lower.split())

    scored = []
    for f in SKILLS_DIR.glob("*.md"):
        try:
            content = f.read_text(encoding="utf-8").lower()
            # Score by keyword overlap
            score = sum(1 for w in query_words if w in content and len(w) > 3)
            if score > 0:
                scored.append((score, f))
        except Exception:
            continue

    scored.sort(key=lambda x: x[0], reverse=True)
    results = []
    for score, f in scored[:max_skills]:
        results.append(f.read_text(encoding="utf-8"))

    return results


async def generate_skill_document(
    task_description: str,
    steps_taken: List[str],
    outcome: str,
    use_sovereign: bool = True,
) -> Optional[str]:
    """
    Auto-generate a skill document after a complex task (5+ steps).
    Smart Toggle: Sovereign first → self-check → Cloud escalation.
    """
    prompt = f"""Analyze this completed task and create a concise skill document in markdown format.

TASK: {task_description}
STEPS TAKEN:
{chr(10).join(f'  {i+1}. {s}' for i, s in enumerate(steps_taken))}
OUTCOME: {outcome}

Create a skill document with:
1. A clear title (# Skill: ...)
2. When to use this skill (2-3 trigger conditions)
3. Step-by-step procedure (numbered)
4. Common pitfalls to avoid
5. Expected outcome

Keep it under 300 words. Be specific and actionable."""

    # Smart Toggle: Sovereign first, self-check, escalate
    response = await _call_sovereign(prompt) if use_sovereign else None
    brain = "sovereign"

    if response and (len(response) < 100 or "# Skill" not in response):
        logger.warning("[Skills] Sovereign skill doc failed quality check, escalating to Cloud")
        response = await _call_cloud(prompt)
        brain = "cloud_escalated"
    elif not response:
        response = await _call_cloud(prompt)
        brain = "cloud_fallback"

    if not response:
        return None

    # Save skill
    slug = task_description[:50].lower()
    slug = "".join(c if c.isalnum() or c == '-' else '-' for c in slug).strip('-')[:40]
    skill_path = SKILLS_DIR / f"{slug}.md"

    try:
        skill_path.write_text(response, encoding="utf-8")
        logger.info(f"[Skills] Generated skill via {brain}: {skill_path.name}")
        return str(skill_path)
    except Exception as e:
        logger.warning(f"[Skills] Failed to save skill: {e}")
        return None


# ═══════════════════════════════════════
# DREAM CONSOLIDATION — Session Learning
# ═══════════════════════════════════════

MISTAKES_PATH = IDENTITY_DIR / "MISTAKES.md"
HABITS_PATH = IDENTITY_DIR / "HABITS.md"


def load_mistakes() -> str:
    """Load the mistakes journal."""
    try:
        if MISTAKES_PATH.exists():
            return MISTAKES_PATH.read_text(encoding="utf-8")
    except Exception:
        pass
    return ""


def load_habits() -> str:
    """Load the habits (successful patterns) journal."""
    try:
        if HABITS_PATH.exists():
            return HABITS_PATH.read_text(encoding="utf-8")
    except Exception:
        pass
    return ""


async def dream_consolidation(
    session_transcript: List[Dict],
    session_id: str = "unknown",
    use_sovereign: bool = True,
    db=None,
) -> Dict:
    """
    Dream Consolidation — runs async after a session ends.
    Reviews the transcript and extracts Mistakes and Habits.
    
    Smart Toggle:
      - Default: Sovereign Brain ($0)
      - Auto-escalates to Cloud if:
        1. Session is "high complexity" (10+ messages or tool calls detected)
        2. Sovereign response fails self-check (missing required sections)
    """
    if not session_transcript:
        return {"status": "empty_session"}

    # ── Complexity Detection ──
    msg_count = len(session_transcript)
    tool_mentions = sum(1 for m in session_transcript if any(kw in str(m.get("content", "")).lower() for kw in ["error", "failed", "retry", "fix", "debug", "crash", "500", "exception"]))
    is_high_complexity = msg_count >= 10 or tool_mentions >= 3

    # Format transcript
    transcript_text = ""
    for msg in session_transcript[-20:]:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")[:300]
        transcript_text += f"[{role}]: {content}\n"

    # Load existing journals
    existing_mistakes = load_mistakes()
    existing_habits = load_habits()

    prompt = f"""You are analyzing a conversation session to extract learning patterns.

SESSION ID: {session_id}
DATE: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}
COMPLEXITY: {'HIGH' if is_high_complexity else 'STANDARD'} ({msg_count} messages, {tool_mentions} issues detected)

TRANSCRIPT (last messages):
{transcript_text}

EXISTING MISTAKES JOURNAL:
{existing_mistakes[-500:] if existing_mistakes else '(empty)'}

EXISTING HABITS JOURNAL:
{existing_habits[-500:] if existing_habits else '(empty)'}

Extract:
1. MISTAKES: Any errors, misunderstandings, or suboptimal approaches. Format as bullet points with date.
2. HABITS: Successful patterns, good approaches, things that worked well. Format as bullet points with date.
3. USER_PREFERENCES: Any new preferences the user expressed (communication style, tech choices, etc.)

Return in this exact format:
MISTAKES:
- [date] description

HABITS:
- [date] description

USER_PREFERENCES:
- description
"""

    # ── Smart Toggle: Sovereign first, self-check, Cloud escalation ──
    brain_used = "sovereign"
    escalated = False

    if is_high_complexity and not use_sovereign:
        # Forced cloud for high complexity when toggle is off
        response = await _call_cloud(prompt)
        brain_used = "cloud_forced"
    else:
        # Try Sovereign first ($0)
        response = await _call_sovereign(prompt)
        brain_used = "sovereign"

        # Self-check: did Sovereign produce a valid response?
        if response and not _passes_self_check(response):
            logger.warning(f"[Dream] Sovereign response failed self-check, escalating to Cloud")
            response = await _call_cloud(prompt)
            brain_used = "cloud_escalated"
            escalated = True
        elif not response and is_high_complexity:
            # Sovereign unavailable + high complexity = Cloud
            logger.info(f"[Dream] Sovereign offline + high complexity, using Cloud")
            response = await _call_cloud(prompt)
            brain_used = "cloud_fallback"
            escalated = True
        elif not response:
            # Sovereign unavailable + standard = try Cloud anyway
            response = await _call_cloud(prompt)
            brain_used = "cloud_fallback"
            escalated = True

    if not response:
        return {"status": "all_brains_unavailable", "brain_used": brain_used}

    # Parse and append to journals
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    new_mistakes = []
    new_habits = []
    new_prefs = []

    section = None
    for line in response.split("\n"):
        line = line.strip()
        if "MISTAKES:" in line.upper():
            section = "mistakes"
            continue
        elif "HABITS:" in line.upper():
            section = "habits"
            continue
        elif "USER_PREFERENCES:" in line.upper() or "PREFERENCES:" in line.upper():
            section = "prefs"
            continue

        if line.startswith("- ") or line.startswith("* "):
            entry = line[2:].strip()
            if not entry:
                continue
            if section == "mistakes":
                new_mistakes.append(entry)
            elif section == "habits":
                new_habits.append(entry)
            elif section == "prefs":
                new_prefs.append(entry)

    # Append to MISTAKES.md
    if new_mistakes:
        try:
            with open(MISTAKES_PATH, "a", encoding="utf-8") as f:
                f.write(f"\n## Session {session_id} ({today})\n")
                for m in new_mistakes:
                    f.write(f"- {m}\n")
            logger.info(f"[Dream] Added {len(new_mistakes)} mistakes to journal")
        except Exception as e:
            logger.warning(f"[Dream] Failed to write mistakes: {e}")

    # Append to HABITS.md
    if new_habits:
        try:
            with open(HABITS_PATH, "a", encoding="utf-8") as f:
                f.write(f"\n## Session {session_id} ({today})\n")
                for h in new_habits:
                    f.write(f"- {h}\n")
            logger.info(f"[Dream] Added {len(new_habits)} habits to journal")
        except Exception as e:
            logger.warning(f"[Dream] Failed to write habits: {e}")

    # Append new preferences to USER.md
    if new_prefs:
        try:
            user_path = IDENTITY_DIR / "USER.md"
            with open(user_path, "a", encoding="utf-8") as f:
                f.write(f"\n- {today}: " + "; ".join(new_prefs) + "\n")
            logger.info(f"[Dream] Added {len(new_prefs)} user preferences")
        except Exception as e:
            logger.warning(f"[Dream] Failed to update USER.md: {e}")

    # Store consolidation result in DB
    # Tag with stability score
    try:
        from services.bitnet_worker import tag_consolidation_stability
        stability_score = tag_consolidation_stability(session_id, len(new_mistakes), len(new_habits))
    except Exception:
        stability_score = 50

    result = {
        "session_id": session_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mistakes_extracted": len(new_mistakes),
        "habits_extracted": len(new_habits),
        "preferences_extracted": len(new_prefs),
        "brain_used": brain_used,
        "escalated_to_cloud": escalated,
        "complexity": "high" if is_high_complexity else "standard",
        "msg_count": msg_count,
        "issue_count": tool_mentions,
        "stability_score": stability_score,
        "status": "consolidated",
    }

    if db:
        try:
            await db.dream_consolidations.insert_one({**result, "raw_response": response[:1000]})
        except Exception:
            pass

    return result


def _passes_self_check(response: str) -> bool:
    """
    Self-check: verify the Sovereign Brain produced a structurally valid response.
    Must contain at least MISTAKES and HABITS sections with content.
    """
    if not response or len(response) < 50:
        return False
    upper = response.upper()
    has_mistakes = "MISTAKES:" in upper
    has_habits = "HABITS:" in upper
    has_bullets = response.count("- ") >= 2
    return has_mistakes and has_habits and has_bullets


async def _call_sovereign(prompt: str) -> Optional[str]:
    """Call the local Sovereign Brain (Ollama via Cloudflare Tunnel). $0 cost."""
    try:
        from services.local_llm_service import chat_local, is_available, get_config
        cfg = get_config()
        if not cfg.get("enabled"):
            return None
        avail = await asyncio.wait_for(is_available(), timeout=3.0)
        if not avail:
            return None
        resp = await asyncio.wait_for(
            chat_local(message=prompt, system_prompt="You are a precise analytical assistant. Follow instructions exactly. Output the exact format requested."),
            timeout=45.0,
        )
        if resp and len(resp) > 20:
            logger.info(f"[Identity] Sovereign response OK ({len(resp)} chars, $0.00)")
            return resp
    except asyncio.TimeoutError:
        logger.warning("[Identity] Sovereign brain timed out (45s)")
    except Exception as e:
        logger.debug(f"[Identity] Sovereign brain error: {e}")
    return None


async def _call_cloud(prompt: str) -> Optional[str]:
    """Call Cloud GPT-4o-mini. Used as escalation when Sovereign fails self-check or high complexity."""
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        key = os.environ.get("EMERGENT_LLM_KEY", "")
        if not key:
            return None
        chat = LlmChat(api_key=key, session_id=f"hermes-identity-{os.getpid()}", system_message="You are a precise analytical assistant. Follow instructions exactly.")
        chat = chat.with_model("openai", "gpt-4o-mini")
        resp = await asyncio.wait_for(chat.send_message(UserMessage(text=prompt)), timeout=15.0)
        if resp:
            logger.info(f"[Identity] Cloud response OK ({len(resp)} chars)")
            return resp
    except Exception as e:
        logger.warning(f"[Identity] Cloud fallback failed: {e}")
    return None


def get_identity_stats() -> Dict:
    """Get stats about the identity system for Overwatch."""
    return {
        "soul_loaded": (IDENTITY_DIR / "SOUL.md").exists(),
        "user_loaded": (IDENTITY_DIR / "USER.md").exists(),
        "skills_count": len(list(SKILLS_DIR.glob("*.md"))),
        "mistakes_entries": load_mistakes().count("- "),
        "habits_entries": load_habits().count("- "),
        "skills": [f.stem for f in SKILLS_DIR.glob("*.md")],
    }
