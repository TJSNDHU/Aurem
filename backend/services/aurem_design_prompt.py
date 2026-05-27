"""
services/aurem_design_prompt.py — iter D-36

ONE source of truth for AUREM's frontend design rules. Every LLM surface
that emits or refines frontend code MUST inject this as a system message
before the user's turn.

Wired into:
  - services.dev_cto_chat        (AUREM CTO chat)
  - services.ora_brain           (ORA operator / website builder)
  - services.customer_edit       (live customer-site edit worker)
  - services.aurem_ai_service    (any other LLM-driven UI generation)
  - services.self_repair_loop    (auto-patch generator)

The prompt itself lives at:
  /app/backend/aurem_cto/prompts/aurem_design_system.md

Module is cached on first read (file is read once, kept in memory) so the
~25 KB content adds no measurable latency to chat turns.
"""
from __future__ import annotations

import logging
import pathlib
from functools import lru_cache
from typing import Any

logger = logging.getLogger(__name__)

# Resolve regardless of cwd (preview cwd=/app, prod cwd=/app/backend)
_PROMPT_PATH = (
    pathlib.Path(__file__).resolve().parent.parent
    / "aurem_cto" / "prompts" / "aurem_design_system.md"
)

# Sentinel marker that ALL tests look for to confirm the design prompt
# made it into the message stack. Keep it short so it survives token
# trimming, but unique so grep/assert can't false-positive.
DESIGN_PROMPT_SENTINEL = "[AUREM-DESIGN-SKILL-v1]"

_FALLBACK = (
    f"{DESIGN_PROMPT_SENTINEL}\n"
    "AUREM Frontend Design Rules:\n"
    "- Toasts: use Sonner (toast.success/error/loading). Never alert().\n"
    "- Mobile drawers: use Vaul (<Drawer.Root>). Never custom bottom-sheets.\n"
    "- Icons: lucide-react only. No emoji-as-icon.\n"
    "- Buttons: transform: scale(0.97) on :active, transition 160ms ease-out.\n"
    "- Animations: only transform + opacity. ease-out, never ease-in. <300ms.\n"
    "- Never animate from scale(0) — start from scale(0.95) + opacity 0.\n"
    "- Popovers: transform-origin = trigger. Modals stay centered.\n"
    "- Stagger lists 30-80ms between items.\n"
    "- Respect prefers-reduced-motion and (hover: hover).\n"
)


@lru_cache(maxsize=1)
def get_aurem_design_prompt() -> str:
    """Returns the full AUREM design-system prompt. Read once, cached.
    Falls back to a short embedded version if the markdown file goes
    missing — never crashes the LLM call."""
    try:
        text = _PROMPT_PATH.read_text(encoding="utf-8")
        # Prepend the sentinel marker so downstream tests can verify
        # the prompt actually made it into the message stack.
        if DESIGN_PROMPT_SENTINEL not in text:
            text = f"{DESIGN_PROMPT_SENTINEL}\n\n{text}"
        return text
    except Exception as e:
        logger.warning(
            f"[design-prompt] failed to read {_PROMPT_PATH}: {e} — "
            f"falling back to embedded short version"
        )
        return _FALLBACK


def inject_design_prompt(messages: list[dict[str, Any]],
                          position: int = 1) -> list[dict[str, Any]]:
    """Insert the design-system system message into a message stack.

    Default position = 1 (right AFTER the primary system prompt,
    BEFORE customer codebase context, search results, and the user turn).
    Idempotent — if the design prompt is already present, returns the
    list unchanged so repeat calls in nested layers don't pile up.

    Args:
        messages: OpenAI-style chat messages list (each has 'role' + 'content').
        position: Where to insert (0 = very first system msg, 1 = after primary).

    Returns:
        New list with the design prompt injected.
    """
    if not messages:
        return [{"role": "system", "content": get_aurem_design_prompt()}]
    # Idempotent — never inject twice.
    for m in messages:
        if (m.get("role") == "system"
                and DESIGN_PROMPT_SENTINEL in str(m.get("content", ""))):
            return messages
    msg = {"role": "system", "content": get_aurem_design_prompt()}
    new_list = list(messages)
    pos = max(0, min(position, len(new_list)))
    new_list.insert(pos, msg)
    return new_list


def design_prompt_for_native_provider() -> str:
    """For providers like Anthropic/Gemini that take a single `system`
    string instead of a messages list. Returns a string suitable for
    appending to the existing system prompt."""
    return "\n\n" + get_aurem_design_prompt()
