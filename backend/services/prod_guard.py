"""
prod_guard.py — Production environment detection & guards (iter 322g+).
══════════════════════════════════════════════════════════════════════
The AUREM platform runs in two environments:

  • PREVIEW (Emergent dev pod):
        - Founder's laptop reachable via reverse-poll Legion daemon
        - Local Ollama (qwen2.5:7b-instruct) serves ORA chat
        - All warmer/watchdog/autonomous loops are active
        - This is where ORA CTO actually thinks

  • PRODUCTION (https://aurem.live):
        - Containerised pod, no reverse-poll daemon, no laptop reach
        - host.docker.internal does NOT route to anything useful
        - Any LLM call that depends on Legion will hang for 60-270s
        - Cloud LLMs (Groq/Claude) are DISABLED per founder mandate
        - Therefore ORA CTO chat is **preview-only** in production

This module centralises the detection so we never branch on env strings
all over the codebase.

Founder mandate (iter 322g): "100% sovereign, NO cloud LLMs". So in
production we don't fall back to Groq — we surface a clean message:
"ORA CTO runs from the preview dashboard, not production."

Signals used (any true → production):
  1. AUREM_ENV=production    (set by server.py at boot)
  2. DISABLE_LEGION=true     (explicit override)
  3. APP_URL contains aurem.live or aurem.live (deployed domain)

We cache the answer so any module can call this hundreds of times per
second with zero overhead.
"""
from __future__ import annotations

import os
from functools import lru_cache


@lru_cache(maxsize=1)
def is_production_pod() -> bool:
    """Return True when this pod is the live production deployment.

    Cached for the lifetime of the process — env vars don't change at
    runtime, so we read them once and freeze the answer.
    """
    if (os.environ.get("AUREM_ENV", "").strip().lower() == "production"):
        return True
    if (os.environ.get("DISABLE_LEGION", "").strip().lower()
            in ("1", "true", "yes", "on")):
        return True
    app_url = (os.environ.get("APP_URL", "") or "").lower()
    if "aurem.live" in app_url or "aurem.live" in app_url:
        return True
    return False


def env_label() -> str:
    """Human-readable env label for logs / health responses."""
    return "production" if is_production_pod() else "preview"
