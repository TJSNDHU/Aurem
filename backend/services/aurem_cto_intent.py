"""
services/aurem_cto_intent.py — iter D-37

Heuristic intent classifier for AUREM CTO chat turns. Replaces the
single rigid SYSTEM_PROMPT with 5 intent-specific behavior branches so
greetings, simple questions, billing lookups, etc. no longer get the
full Plan + [step N/M] + NEXT_STEPS + progress JSON treatment.

Design choices (deliberate):
  - Pure heuristics. No extra LLM call per turn. Latency cost = ~0.1 ms.
  - Returns one of 5 buckets matching the watchdog-spec table.
  - Falls back to `build` when the message contains action verbs but no
    other strong signal — safer to over-scaffold than to under-scaffold.
  - The 'unknown' bucket exists for true ambiguity → caller can decide
    to ask one clarifying question instead of guessing.

Public API:
    classify_intent(text: str) -> str          # → one of INTENT_TYPES
    system_prompt_for(intent: str) -> str       # → system prompt suffix
"""
from __future__ import annotations

import re

# Five buckets that map to the table in the watchdog spec.
INTENT_TYPES = ("build", "question", "conversational",
                "diagnostic", "strategic", "unknown")

# ── Bucket signals ───────────────────────────────────────────────────
# Order matters: we check most-specific buckets first.

# Conversational — greetings, thanks, social. Short messages dominate.
_CONVERSATIONAL_RE = re.compile(
    r"\b(hi|hello|hey|yo|sup|hola|namaste|"
    r"good\s*(?:morning|afternoon|evening|night)|"
    r"how\s+(?:are|r)\s+you|"
    r"thanks|thank\s+you|thx|ty|cheers|appreciate|"
    r"bye|goodbye|cya|see\s+ya|peace|"
    r"sorry|apologies|my\s+bad|"
    r"lol|lmao|haha|nice|cool|awesome|"
    r"ok+\s*$|okay\s*$|yes\s*$|yep\s*$|yeah\s*$|no\s*$|nope\s*$)",
    re.I,
)

# Diagnostic — bugs, errors, logs, stack traces, broken behavior.
_DIAGNOSTIC_RE = re.compile(
    r"\b(error|exception|traceback|stacktrace|stack\s*trace|"
    r"broken|broke|crashing|crashed|crash|fail(?:ed|ing|s)?|"
    r"bug|defect|regression|wrong|incorrect|"
    r"not\s+work(?:ing)?|doesn'?t\s+work|isn'?t\s+work(?:ing)?|"
    r"500|502|503|504|timeout|timed?\s*out|hung|stuck|"
    r"why\s+(?:is|isn'?t|does|doesn'?t)|"
    r"what\s+(?:is\s+)?wrong|"
    r"debug)\b",
    re.I,
)

# Build — clear action verbs that demand code being produced.
_BUILD_VERBS_RE = re.compile(
    r"\b(build|create|make|wire|add|implement|generate|"
    r"scaffold|spin\s*up|set\s*up|install|configure|"
    r"refactor|rewrite|rework|restructure|"
    r"deploy|ship|launch|release|push|"
    r"connect|integrate|hook\s*up|plug\s*in|"
    r"design|draft|mock\s*up|prototype|"
    r"fix|patch|resolve|address|hotfix|"
    r"update|upgrade|bump|migrate|"
    r"remove|delete|drop|strip|"
    r"test|verify|prove|e2e|end[-\s]to[-\s]end)\b",
    re.I,
)

# Strategic — business / planning / future-tense thinking. The regex
# below is intentionally strict: a bare "should I" no longer counts as
# strategic (too generic — would swallow ordinary questions). The user
# must reference at least one business/planning anchor word.
_STRATEGIC_RE = re.compile(
    r"\b(roadmap|strategy|strategic|"
    r"funding|grant|loan|investor|pitch|"
    r"revenue|mrr|arr|pricing|tier|gtm|"
    r"competitor|competition|market(?:place)?|"
    r"prioriti[sz]e|priority|focus\s+on|"
    r"long[-\s]term|short[-\s]term|"
    r"compare|comparison|\bvs\.?\b|versus|"
    r"enterprise\s+(?:or|vs)|smb\s+(?:or|vs))\b",
    re.I,
)

# Introspective / "describe yourself" signals — these mean the dev is
# asking the AI about ITSELF, not asking for code. Beats build-verb hits.
_INTROSPECTIVE_RE = re.compile(
    r"\b(how\s+(?:do\s+)?you\s+(?:work|think|reason|process|reply|behave|decide|plan)|"
    r"how\s+r\s+u|how's\s+ur|"                # casual variants
    r"your\s+(?:workflow|process|architecture|capabilities|abilities|"
    r"limits?|prompt|model|memory|tools?|stack|system)|"
    r"what\s+(?:can|can'?t|do)\s+you\s+do|"
    r"what\s+are\s+you|who\s+are\s+you|"
    # Hinglish / Hindi introspection — covers the founder's own
    # phrasing examples (e.g. "tum kya kar sakte ho", "aap kaise kaam karte ho").
    r"tum\s+(?:kaise|kya)(?:\s+(?:kaam|sochte|samajhte|karte|karoge"
    r"|kar\s+sakte))?|"
    r"aap\s+(?:kaise|kya)(?:\s+(?:kaam|sochte|samajhte|karte|karoge"
    r"|kar\s+sakte))?)",
    re.I,
)

_QUESTION_OPENER_RE = re.compile(
    r"^\s*(what|how|why|where|when|which|who|whose|whom|"
    r"can|could|would|should|do|does|did|is|are|am|was|were|"
    r"will|may|might|tell\s+me|explain|describe|"
    r"show\s+me|list|enumerate)\b",
    re.I,
)
_QUESTION_MARK_RE = re.compile(r"\?")


def classify_intent(text: str) -> str:
    """Return one of INTENT_TYPES for a user message.

    Pure heuristic — no LLM call. Designed to be conservative: if a
    message is genuinely ambiguous the function returns 'unknown' and
    the caller can decide whether to ask for clarification or default
    to 'question'.
    """
    if not text or not text.strip():
        return "unknown"

    t = text.strip()
    t_lower = t.lower()
    word_count = len(t.split())

    # Strongest signal: error/exception/broken language → diagnostic.
    if _DIAGNOSTIC_RE.search(t_lower):
        return "diagnostic"

    # Introspective ("how do YOU work", "your workflow", "tum kaise
    # kaam karte ho") → question, ALWAYS. Beats build/strategic hits
    # because the word "plan" or "workflow" alone can otherwise misfire.
    if _INTROSPECTIVE_RE.search(t_lower):
        return "question"

    if _STRATEGIC_RE.search(t_lower):
        return "strategic"

    # Short conversational greetings (<= 12 words) win over the
    # generic "starts with question word" rule, because "how are you"
    # and "hi how's it going" should NOT be treated as questions.
    if _CONVERSATIONAL_RE.search(t_lower) and word_count <= 12:
        if not _BUILD_VERBS_RE.search(t_lower):
            return "conversational"

    # Question opener wins over build verbs ("how do I ADD a route"
    # is a question, not a build request).
    if _QUESTION_OPENER_RE.match(t_lower):
        return "question"

    # Explicit action verbs → build.
    if _BUILD_VERBS_RE.search(t_lower):
        return "build"

    # Trailing `?` fallback → question.
    if _QUESTION_MARK_RE.search(t):
        return "question"

    # Genuinely ambiguous.
    return "unknown"


# ── System-prompt suffix per intent ──────────────────────────────────
# These are SUFFIXES appended to the base AUREM CTO prompt. Each suffix
# tells the model which output contract to honor for THIS turn.

_PROMPT_BUILD = """\

INTENT FOR THIS TURN: build / fix / multi-step task.
Use the full output contract:
  - Open with `Plan (N steps): 1) ... 2) ...`
  - Prefix each section with `[step N/M]`
  - Emit `progress:`, `phase:`, and `MANIFEST_PATCH:` if there is a
    visible UI change.
  - End with `NEXT_STEPS: ["...", "...", "..."]`
"""

_PROMPT_QUESTION = """\

INTENT FOR THIS TURN: question / explanation request.
Reply naturally in 1-3 short paragraphs of plain English. NO Plan,
NO `[step N/M]` markers, NO progress / phase / MANIFEST_PATCH lines.

If the question is about YOU (the AUREM CTO platform — how you work,
what you can/can't do, your memory/tools), answer from the "WHAT YOU
ACTUALLY ARE" block in your base system prompt. Use plain sentences,
never Python pseudo-code. NEVER invent statistics about past work
(e.g. "I found N bugs across M rounds") — if a number is not in your
explicit context, say so plainly.

End with ONE NEXT_STEPS line containing follow-up actions like
[\"Show me the code\", \"Explain deeper\", \"Skip\"].
"""

_PROMPT_CONVERSATIONAL = """\

INTENT FOR THIS TURN: conversational / social.
Reply in 1-2 sentences, warm and natural. NO Plan, NO step markers,
NO progress lines, NO MANIFEST_PATCH. NO NEXT_STEPS line. Just answer
like a teammate would.
"""

_PROMPT_DIAGNOSTIC = """\

INTENT FOR THIS TURN: diagnostic / bug report.
Reproduce or hypothesize the root cause FIRST in 2-3 sentences. Then
propose ONE fix with its file path and a short code snippet. NO Plan,
NO `[step N/M]`, NO progress / phase / MANIFEST_PATCH unless you are
actually shipping a fix this turn. End with
NEXT_STEPS: [\"Apply the fix\", \"Show me the failing test\", \"Need more logs\"].
"""

_PROMPT_STRATEGIC = """\

INTENT FOR THIS TURN: strategic / planning / business question.
Pull real numbers from the developer's project context before
recommending anything. Reply in plain English, max 3 short paragraphs
or a small markdown table. NO Plan, NO step markers, NO progress lines.
End with NEXT_STEPS containing decision-style chips like
[\"Go with option A\", \"Show numbers\", \"Park for now\"].
"""

_PROMPT_UNKNOWN = """\

INTENT FOR THIS TURN: ambiguous.
Ask ONE short clarifying question before doing any work. NO Plan,
NO step markers, NO progress lines. End with NEXT_STEPS containing
2-3 likely interpretations the developer can click to confirm, e.g.
[\"Build it\", \"Just explain\", \"Show example\"].
"""

_PROMPT_MAP = {
    "build":          _PROMPT_BUILD,
    "question":       _PROMPT_QUESTION,
    "conversational": _PROMPT_CONVERSATIONAL,
    "diagnostic":     _PROMPT_DIAGNOSTIC,
    "strategic":      _PROMPT_STRATEGIC,
    "unknown":        _PROMPT_UNKNOWN,
}


# ── Non-tech audience detection (iter D-40) ───────────────────────────
#
# Customers describing an IDEA in business terms (no API/DB/React/deploy
# language) get a special suffix that tells the LLM: NO CODE, NO PYTHON,
# NO PSEUDO-CODE, use analogies + step-by-step plain words. This works
# ON TOP OF the regular intent classification — if non-tech is detected,
# the suffix below is appended to whichever intent branch fired.

_TECH_KEYWORDS = (
    "api", "endpoint", "database", "db", "mongodb", "postgres", "sql",
    "react", "fastapi", "node", "next.js", "vue", "django", "flask",
    "schema", "function", "method", "class", "variable", "import",
    "deploy", "container", "docker", "kubernetes", "k8s",
    "compile", "lint", "regex", "json", "yaml", "env var", "ssh",
    "framework", "library", "package", "git", "github", "branch",
    "merge", "pull request", "pr", "commit", "rebase",
    "auth", "jwt", "oauth", "saml", "scim", "webhook",
    "stack", "tech stack", "microservice", "graphql", "rest", "grpc",
    "middleware", "router", "controller", "model",
)

_NON_TECH_HINTS = (
    "i want to build", "i want to make", "i want to start",
    "i have an idea", "my idea", "my dream",
    "ek app", "ek website", "ek business",
    "ek idea", "ek startup",
    "banana chahta hoon", "banana chahti hoon",
    "shuru karna", "shuru karni",
    "kaise banaye", "kaise banaun", "kaise shuru",
    "kapde bechna", "khaana bechna", "bechna chahta",
    "customer", "users", "audience",
    "non-tech", "non technical", "non-technical",
    "business idea", "side hustle",
)


def is_non_technical(text: str) -> bool:
    """Heuristic: returns True when the user message looks like an
    idea-stage non-technical request. Used by the chat layer to inject
    the 'NON-TECH MODE' suffix on top of the intent branch."""
    if not text:
        return False
    t = text.lower()
    # If they used ANY tech keyword → definitely not non-tech.
    if any(kw in t for kw in _TECH_KEYWORDS):
        return False
    # If they used at least one non-tech hint → flag it.
    return any(h in t for h in _NON_TECH_HINTS)


_NON_TECH_SUFFIX = """\

NON-TECH MODE (iter D-40 — overrides any other format rule for this turn):
  Customer is non-technical. NO code, NO Python, NO pseudo-code,
  NO `def`, NO `if/else`, NO dictionaries, NO API/DB jargon, NO
  Plan + step + MANIFEST_PATCH format. Reply rules:
    1. Mirror their language exactly (Hinglish → Hinglish, etc.).
    2. Open with one short affirming line (\"Achchi idea\" / \"Good thinking\").
    3. Re-state their idea in plain words: \"basically tum X banana
       chahte ho — jaise Y lekin Z\".
    4. Give 2-3 concrete next steps. Numbered. Plain language. Each
       step ≤ 12 words. Include real prices / timelines if relevant
       (\"$29/month\", \"1 week\", \"start tomorrow\").
    5. End with ONE clarifying question — never more.
"""



def system_prompt_for(intent: str, non_technical: bool = False) -> str:
    """Return the system-prompt suffix for the given intent. When
    `non_technical=True`, the non-tech mode block is appended on top so
    the LLM strips code/jargon out of the reply regardless of bucket."""
    base = _PROMPT_MAP.get(intent, _PROMPT_UNKNOWN)
    if non_technical:
        return base + _NON_TECH_SUFFIX
    return base
