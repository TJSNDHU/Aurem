"""
AUREM Superpowers Skills — TDD + Debugging + Systematic Fixes
==============================================================
Extracted from obra/superpowers (156k stars).
Stored as knowledge patterns for Hermes/ORA to reference.
"""
import os
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

SKILLS_DIR = "/app/.claude/skills/superpowers/skills"

# Core skill patterns extracted from Superpowers
SKILL_PATTERNS = {
    "tdd": {
        "name": "Test-Driven Development",
        "trigger": "writing code, implementing features, fixing bugs",
        "process": [
            "1. Write a failing test that describes the expected behavior",
            "2. Run the test — confirm it FAILS (RED)",
            "3. Write the MINIMUM code to make the test pass",
            "4. Run the test — confirm it PASSES (GREEN)",
            "5. Refactor if needed — tests must still pass",
            "6. Commit after each green cycle",
        ],
        "rules": [
            "NEVER write code before writing a test",
            "If you wrote code first, DELETE it and start with a test",
            "Each test should test ONE behavior",
            "Tests must be deterministic — no random, no time-dependent",
        ],
    },
    "systematic_debugging": {
        "name": "Systematic Debugging",
        "trigger": "bug reports, errors, unexpected behavior",
        "process": [
            "Phase 1: OBSERVE — Reproduce the exact failure. Get error messages, stack traces, logs.",
            "Phase 2: HYPOTHESIZE — List possible causes ranked by probability. Don't guess — reason.",
            "Phase 3: TEST — Verify each hypothesis with minimal changes. One variable at a time.",
            "Phase 4: FIX — Apply the minimal fix. Verify the original failure is gone.",
        ],
        "rules": [
            "NEVER fix without reproducing first",
            "NEVER apply multiple fixes at once",
            "After fixing, verify NO regression in related functionality",
            "Root cause > symptom fix. Always trace to the root.",
        ],
    },
    "verification_before_completion": {
        "name": "Verification Before Completion",
        "trigger": "claiming a fix is done, declaring success",
        "process": [
            "1. Run ALL related tests — not just the one you wrote",
            "2. Manually verify the original reported behavior is fixed",
            "3. Check edge cases — empty input, large input, concurrent access",
            "4. Verify no regression in adjacent features",
            "5. ONLY THEN declare success",
        ],
        "rules": [
            "NEVER claim 'fixed' without running tests",
            "NEVER skip edge case verification",
            "If you can't test it, you can't claim it works",
        ],
    },
    "brainstorming": {
        "name": "Brainstorming & Spec-First",
        "trigger": "new feature request, unclear requirements",
        "process": [
            "1. Ask clarifying questions — don't assume",
            "2. Explore alternatives — at least 2 approaches",
            "3. Present design in digestible chunks",
            "4. Get sign-off before writing ANY code",
        ],
    },
    "writing_plans": {
        "name": "Implementation Planning",
        "trigger": "approved design, ready to implement",
        "process": [
            "1. Break into tasks of 2-5 minutes each",
            "2. Each task has: exact file paths, verification steps",
            "3. Tasks are ordered by dependency",
            "4. YAGNI — don't plan features not requested",
        ],
    },
}


def get_skill(skill_name: str) -> Dict:
    """Get a Superpowers skill pattern."""
    return SKILL_PATTERNS.get(skill_name, {"error": f"Unknown skill: {skill_name}"})


def get_all_skills() -> Dict:
    """List all available skill patterns."""
    return {k: {"name": v["name"], "trigger": v.get("trigger", "")} for k, v in SKILL_PATTERNS.items()}


def get_skill_for_context(context: str) -> List[Dict]:
    """Find relevant skills based on context (what the agent is doing)."""
    context_lower = context.lower()
    relevant = []
    for key, skill in SKILL_PATTERNS.items():
        trigger = skill.get("trigger", "").lower()
        if any(t.strip() in context_lower for t in trigger.split(",") if t.strip()):
            relevant.append({"skill": key, **skill})
    return relevant if relevant else [{"skill": "systematic_debugging", **SKILL_PATTERNS["systematic_debugging"]}]


def load_skill_file(skill_name: str) -> str:
    """Load the full SKILL.md file from Superpowers repo."""
    path = os.path.join(SKILLS_DIR, skill_name, "SKILL.md")
    if os.path.exists(path):
        with open(path, "r") as f:
            return f.read()[:5000]
    return f"Skill file not found: {path}"
