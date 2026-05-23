"""
services/ora_lessons_loader.py — iter 327n

Tiered memory injection for ORA's SYSTEM_PROMPT.

Why
---
Before this module, 29 instruction files (`/app/memory/*.md`,
`/app/backend/ora_skills/dev_*.md`) sat on disk but were NEVER read
by `ora_agent.py`. Founders wrote lessons into ORA_MEMORY.md and
ORA learned nothing.

Wholesale "inject everything" would blow the 128K context budget.
This module does a **tiered injection**:

Tier 1 — ALWAYS injected (every conversation), 8000-char cap
  • dev_zero-hallucination-charter.md
  • dev_322ey-ora-mistakes-lessons.md
  • WATCHDOG_MODE.md
  • WORKING_POLICY.md
  • SYSTEM_MAP.md (first 1500 chars only)

Tier 2 — Injected ONLY when the user message indicates relevance
  • SECURITY_PATTERNS.md → keywords: security, auth, jwt, casl,
    password, secret, token, encryption
  • CASL rules (extracted from SECURITY_PATTERNS) → keywords:
    campaign, outreach, email, blast, send, marketing, opt out
  • ARCHITECTURE.md (first 2000 chars) → keywords: fix, debug,
    error, broken, crash, why, how does

Tier 3 — Not in prompt. ORA has tools that search on demand:
  `search_codebase_semantic`, `git_log`, `view_file`.

Public API
----------
    build_lessons_block() -> str        # Tier 1, computed once at boot
    relevant_tier2_blocks(user_text)    # On-demand Tier 2 prepended per turn

Both functions are best-effort: missing files → log + skip, never
raise. The cap is enforced PER FILE then again on the assembled block.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────
_TIER1_CAP_TOTAL    = 8000   # founder-mandated budget
_TIER1_CAP_PER_FILE = 1500   # 1500 × 4 files + ~1500 for SYSTEM_MAP + headers ≈ 8000
_SYSTEM_MAP_HEAD    = 1500   # SYSTEM_MAP.md only its first chunk

_TIER2_CAP_PER_FILE = 4000   # tier-2 fires only on relevance, larger budget

# Tier 1 sources (always injected at module load).
_TIER1_FILES: list[tuple[str, str, int]] = [
    # (label,                       absolute path,                                   cap)
    ("ZERO-HALLUCINATION CHARTER",  "/app/backend/ora_skills/dev_zero-hallucination-charter.md",  _TIER1_CAP_PER_FILE),
    ("ORA MISTAKES — DO NOT REPEAT", "/app/backend/ora_skills/dev_322ey-ora-mistakes-lessons.md", _TIER1_CAP_PER_FILE),
    ("WATCHDOG MODE",               "/app/memory/WATCHDOG_MODE.md",                  _TIER1_CAP_PER_FILE),
    ("WORKING POLICY",              "/app/memory/WORKING_POLICY.md",                 _TIER1_CAP_PER_FILE),
    ("SYSTEM MAP (summary)",        "/app/memory/SYSTEM_MAP.md",                     _SYSTEM_MAP_HEAD),
]

# Tier 2 triggers: (regex-ish keywords, label, path, cap).
# We intentionally use plain substring matching (case-insensitive) — no
# regex magic so the founder can read the table and predict behavior.
_TIER2_RULES: list[tuple[tuple[str, ...], str, str, int]] = [
    (("security", "auth", "jwt", "password", "secret", "token", "encryption"),
     "SECURITY PATTERNS", "/app/memory/SECURITY_PATTERNS.md", _TIER2_CAP_PER_FILE),
    (("campaign", "outreach", "email blast", "blast", "marketing",
      "opt out", "opt-out", "unsubscribe", "casl"),
     "CASL + OUTREACH RULES (from SECURITY PATTERNS)",
     "/app/memory/SECURITY_PATTERNS.md", _TIER2_CAP_PER_FILE),
    (("fix", "debug", "broken", "crash", "why does", "how does", "error"),
     "ARCHITECTURE (summary)", "/app/memory/ARCHITECTURE.md", 2000),
]


# ── Helpers ─────────────────────────────────────────────────────────

def _read_capped(path: str, cap: int) -> str | None:
    """Read a file and clamp to `cap` chars. Returns None on any
    failure (missing, permission, decode error). Never raises."""
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        logger.debug(f"[lessons-loader] skip {path}: {e}")
        return None
    text = text.strip()
    if not text:
        return None
    if len(text) > cap:
        text = text[:cap] + f"\n…[truncated {len(text) - cap} chars]"
    return text


def _format_block(label: str, body: str) -> str:
    """Wrap a file body in a clear header/footer so the LLM can
    distinguish injected lessons from conversation."""
    return (
        f"\n\n=== {label} ===\n"
        f"{body}\n"
        f"=== END {label} ===\n"
    )


# ── Tier 1 — computed once at import, never recomputed per turn ─────

def build_lessons_block() -> str:
    """Assemble the always-injected Tier 1 block.

    Returns a single string ready to be appended to SYSTEM_PROMPT. The
    block is hard-capped at `_TIER1_CAP_TOTAL` characters even if
    individual files come in under their per-file cap — predictable
    token cost is more valuable than 100% inclusion.
    """
    parts: list[str] = []
    sources: list[str] = []
    for label, path, cap in _TIER1_FILES:
        body = _read_capped(path, cap)
        if body is None:
            continue
        parts.append(_format_block(label, body))
        sources.append(Path(path).name)
    if not parts:
        logger.info("[lessons-loader] tier-1 empty — no lesson files found")
        return ""
    assembled = (
        "\n\n# ─────────────────────────────────────────────\n"
        "# FOUNDER'S RULE BOOK — ORA must follow these\n"
        "# rules in every reply. They override the model's\n"
        "# default behaviour where they conflict.\n"
        "# ─────────────────────────────────────────────"
        + "".join(parts)
    )
    if len(assembled) > _TIER1_CAP_TOTAL:
        assembled = (
            assembled[:_TIER1_CAP_TOTAL]
            + f"\n…[total block truncated to {_TIER1_CAP_TOTAL} chars]"
        )
    logger.info(
        f"[ora-agent] Injected {len(assembled)} chars from "
        f"{len(parts)} lesson files: {', '.join(sources)}"
    )
    return assembled


# ── Tier 2 — keyword-gated, called once per user turn ────────────────

def relevant_tier2_blocks(user_text: str) -> str:
    """Return Tier 2 injections that match the user's turn, or "" if
    nothing relevant. Same-file dedup: if the same file matches two
    rules in one turn (e.g. SECURITY_PATTERNS for both 'security' AND
    'casl') it's only injected once.
    """
    if not user_text:
        return ""
    needle = user_text.lower()
    parts: list[str] = []
    seen_paths: set[str] = set()
    fired_labels: list[str] = []
    for keywords, label, path, cap in _TIER2_RULES:
        if path in seen_paths:
            continue
        if any(k in needle for k in keywords):
            body = _read_capped(path, cap)
            if body:
                parts.append(_format_block(label, body))
                seen_paths.add(path)
                fired_labels.append(label)
    if parts:
        logger.info(
            f"[ora-agent] tier-2 fired for this turn: {fired_labels}"
        )
    return "".join(parts)
