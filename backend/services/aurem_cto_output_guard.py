"""
services/aurem_cto_output_guard.py — iter D-40b + D-41

Defense-in-depth: strip "illustrative pseudo-code" out of AUREM CTO
replies whose intent is NOT a build/fix request, AND append an
AUREM-equivalents footer when the LLM slips and recommends an
off-platform tool (Figma, Vercel, CodeSandbox, etc.).

Why this exists
---------------
The founder caught two distinct failure modes on the free-tier LLMs:

1. (D-40b) Python pseudo-code dumped to a meta question ("how do you
   reply to a non-tech customer?"). System prompt forbids it; the
   model still slips. Deterministic strip.

2. (D-41) Reply recommended Figma, Vercel, CodeSandbox, Loom, JSON
   Server, Mock Service Worker etc. as the workflow. AUREM has
   first-party equivalents for every one of these. We do NOT rewrite
   the reply (too lossy), but we DO append a one-line corrective
   footer pointing the dev at AUREM's native surfaces, so the reply
   stays useful and the AUREM-first principle is reinforced.

Public API
----------
    strip_illustrative_code(reply, *, intent, non_technical=False)
    append_aurem_first_correction(reply) -> str
    apply_output_guards(reply, *, intent, non_technical=False) -> str
"""
from __future__ import annotations

import re

# Intents where code blocks are *probably* illustrative (i.e. not for
# the dev's project) and should be stripped.
_NON_BUILD_INTENTS = {
    "question", "conversational", "strategic", "unknown", "diagnostic",
}

# Fenced code blocks of any language.  Captures the language tag in
# group(1) and the body in group(2). Non-greedy so multiple blocks in
# one reply each match individually.
_FENCE_RE = re.compile(
    r"```([A-Za-z0-9_+\-]*)\s*\n(.*?)```",
    re.DOTALL,
)

# Inline "pseudo-code-ish" patterns we want to flag inside fenced blocks
# (def, lambda, if/else, dict literal, function call signature).
_PSEUDO_HINT_RE = re.compile(
    r"^\s*(def\s+\w+\s*\(|class\s+\w+|"
    r"if\s+\w.+?:\s*$|elif\s+\w.+?:\s*$|else\s*:|"
    r"for\s+\w+\s+in\s+|while\s+|"
    r"return\s+|"
    r"\w+\s*=\s*\{|"           # dict literal assignment
    r"\w+\s*=\s*\[|"           # list literal assignment
    r"\w+\s*=\s*lambda)",
    re.M,
)


def _looks_like_pseudo_code(body: str, lang: str) -> bool:
    """Returns True when the fenced block looks like illustrative
    pseudo-code (Python/JS-ish syntax) rather than a real config file
    or a quoted chunk of natural language."""
    if lang.lower() in {"python", "py", "javascript", "js", "ts",
                         "typescript", "jsx", "tsx"}:
        return True
    # No language tag — sniff the body.
    return bool(_PSEUDO_HINT_RE.search(body))


def strip_illustrative_code(
    reply: str,
    *,
    intent: str,
    non_technical: bool = False,
) -> str:
    """Remove illustrative code fences from a non-build reply.

    Build replies are returned untouched. For non-build replies (or
    when non_technical=True), every fenced block that looks like
    pseudo-code is replaced with a short prose breadcrumb so the
    surrounding sentences still make sense.

    Idempotent and side-effect free.
    """
    if not reply:
        return reply
    if intent == "build" and not non_technical:
        return reply
    if intent not in _NON_BUILD_INTENTS and not non_technical:
        return reply

    def _repl(m: re.Match) -> str:
        lang = (m.group(1) or "").strip()
        body = m.group(2) or ""
        if not _looks_like_pseudo_code(body, lang):
            # Looks like a config snippet, JSON example, etc. — keep
            # it. We only strip Python/JS-style illustrative code.
            return m.group(0)
        # Replace with a single neutral line so paragraph flow survives.
        return "(skipped a pseudo-code block — see plain explanation above)"

    cleaned = _FENCE_RE.sub(_repl, reply)
    # Tidy duplicate blank lines that fence removal can leave behind.
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned


# ─────────────────────────────────────────────────────────────────────
# iter D-41 — AUREM-first guard
# ─────────────────────────────────────────────────────────────────────
#
# Banned off-platform tools. Keys are case-insensitive whole-word
# matches; values are the AUREM-native equivalent we want to surface
# in the corrective footer. Keep the list lean — false positives are
# worse than missed ones (we'd rather under-correct than nag).

_BANNED_TOOLS: dict[str, str] = {
    # design / prototyping
    "figma":          "AUREM Design System + workspace preview",
    "figjam":         "AUREM Design System + workspace preview",
    "sketch":         "AUREM Design System + workspace preview",
    "penpot":         "AUREM Design System + workspace preview",
    # hosting / deploy
    "vercel":         "AUREM Deploy (preview.aurem.live + SSH)",
    "netlify":        "AUREM Deploy (preview.aurem.live + SSH)",
    "heroku":         "AUREM Deploy (preview.aurem.live + SSH)",
    "railway":        "AUREM Deploy (preview.aurem.live + SSH)",
    "render":         "AUREM Deploy (preview.aurem.live + SSH)",
    "fly.io":         "AUREM Deploy (preview.aurem.live + SSH)",
    "glitch":         "AUREM Deploy (preview.aurem.live + SSH)",
    # code preview / sandboxes
    "codesandbox":    "preview.aurem.live",
    "stackblitz":     "preview.aurem.live",
    "replit":         "preview.aurem.live",
    "jsfiddle":       "preview.aurem.live",
    # AI build competitors
    "bolt.new":       "AUREM CTO chat",
    "lovable":        "AUREM CTO chat",
    "v0.dev":         "AUREM CTO chat",
    "cursor":         "AUREM CTO chat",
    "windsurf":       "AUREM CTO chat",
    "devin":          "AUREM CTO chat",
    # mock APIs
    "mock service worker":  "stack template `mock_backend=true`",
    "json server":          "stack template `mock_backend=true`",
    "mockoon":              "stack template `mock_backend=true`",
    "beeceptor":            "stack template `mock_backend=true`",
    # collab / loom-style share-back
    "loom":           "AUREM public preview link",
    "tella":          "AUREM public preview link",
}

# Verbs that mark a SUGGESTION (vs. a passing mention) of a tool. We
# only flag the tool name when it shows up alongside one of these
# within ~60 chars, so a customer saying "we used to use Figma" doesn't
# trigger a correction.
_SUGGEST_VERBS_RE = re.compile(
    r"\b(use|using|try|tried|recommend|suggest|consider|"
    r"go\s+with|switch\s+to|pick|spin\s+up\s+a?|"
    r"build\s+(?:in|on|with)|host\s+(?:in|on|with)?|"
    r"deploy(?:ing)?|"
    r"prototype\s+in|design\s+in|mock\s+with|share\s+via)\b",
    re.I,
)

# Headers / list intros that wrap a tools recommendation list.
_TOOLS_LIST_HEADER_RE = re.compile(
    r"^\s*(?:#{1,6}\s*|\*\*\s*)?"
    r"(?:tools?\s*i\s*use|tools?\s*to\s*use|recommended\s*tools?|"
    r"my\s*toolkit|stack\s*recommendation|"
    r"\|\s*purpose\s*\|\s*tools?\s*\|)",
    re.I | re.M,
)


def _detect_banned_tools(reply: str) -> list[tuple[str, str]]:
    """Return (tool_name, aurem_equivalent) pairs the reply
    appears to RECOMMEND. Empty list when nothing tripped."""
    if not reply:
        return []
    lower = reply.lower()
    hits: list[tuple[str, str]] = []
    seen: set[str] = set()

    # A reply with an explicit "Tools I Use" / pipe-table header is
    # treated as a blanket recommendation context: every banned name
    # inside it counts.
    blanket = bool(_TOOLS_LIST_HEADER_RE.search(reply))

    for tool, equiv in _BANNED_TOOLS.items():
        if tool in seen:
            continue
        # Whole-word-ish match (handle dots in 'bolt.new', 'fly.io',
        # and spaces in 'mock service worker') by anchoring on word
        # boundaries where possible.
        pattern = re.compile(
            r"(?<![a-z0-9])" + re.escape(tool) + r"(?![a-z0-9])",
            re.I,
        )
        for m in pattern.finditer(lower):
            if blanket:
                hits.append((tool, equiv))
                seen.add(tool)
                break
            # Local context window — 60 chars either side.
            start = max(0, m.start() - 60)
            end   = min(len(lower), m.end() + 60)
            window = lower[start:end]
            if _SUGGEST_VERBS_RE.search(window):
                hits.append((tool, equiv))
                seen.add(tool)
                break
    return hits


def append_aurem_first_correction(reply: str) -> str:
    """If the reply recommends a banned off-platform tool, append a
    short corrective footer pointing the dev at the AUREM-native
    equivalent. Non-destructive: original reply is preserved.

    Idempotent — re-running on an already-corrected reply is a no-op.
    """
    if not reply:
        return reply
    if "[AUREM-FIRST CORRECTION]" in reply:
        return reply  # already corrected this turn

    hits = _detect_banned_tools(reply)
    if not hits:
        return reply

    # De-dupe equivalents (multiple banned tools may point to the
    # same AUREM surface).
    bullets: list[str] = []
    seen_equivs: set[str] = set()
    for tool, equiv in hits:
        line = f"- {tool} → {equiv}"
        key = equiv
        if key in seen_equivs:
            # Append the tool name to the existing bullet so we
            # consolidate without dropping info.
            for i, b in enumerate(bullets):
                if b.endswith(equiv):
                    bullets[i] = b.replace(
                        " → " + equiv, f" / {tool} → {equiv}", 1,
                    )
                    break
            continue
        bullets.append(line)
        seen_equivs.add(key)

    footer = (
        "\n\n---\n"
        "[AUREM-FIRST CORRECTION] AUREM has built-in alternatives for "
        "every external tool I mentioned — use these instead so you "
        "stay on-platform and your work ships through AUREM Deploy:\n"
        + "\n".join(bullets)
    )
    return reply.rstrip() + footer


def apply_output_guards(
    reply: str,
    *,
    intent: str,
    non_technical: bool = False,
) -> str:
    """One-shot helper: strip illustrative pseudo-code (D-40b) AND
    append AUREM-first correction (D-41). Order matters — strip first
    so the correction footer never sits next to a stale code block."""
    reply = strip_illustrative_code(
        reply, intent=intent, non_technical=non_technical,
    )
    reply = append_aurem_first_correction(reply)
    return reply
