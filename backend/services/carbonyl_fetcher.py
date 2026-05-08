"""
Carbonyl Fetcher — Iteration 214
=================================
Graceful-degradation headless-browser fetcher. Talks to a Carbonyl
(fathyb/carbonyl) instance running on the user's Legion PC via the
Chrome DevTools Protocol exposed on port 9222.

Use case: JavaScript-heavy customer websites that the raw httpx fallback
chain in `utils.resilient_fetch` can't render (React/Vue/Next SPAs, sites
that gate HTML behind hydration, etc.).

Behaviour:
    • When CARBONYL_URL is empty → returns {ok: False, reason: "offline"}.
      Callers MUST fall back to normal httpx fetch. No network calls made.
    • When configured → POST {url} to {CARBONYL_URL}/render, expect
      {html, title, final_url, screenshot_b64?}.

ENV
---
CARBONYL_URL        — e.g. http://192.168.1.20:9222
CARBONYL_TIMEOUT_S  — default 25
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict

import httpx

logger = logging.getLogger(__name__)

CARBONYL_URL = (os.environ.get("CARBONYL_URL") or "").rstrip("/")
CARBONYL_TIMEOUT_S = float(os.environ.get("CARBONYL_TIMEOUT_S", "25"))


def is_configured() -> bool:
    return bool(CARBONYL_URL)


async def render(url: str, wait_ms: int = 1500) -> Dict[str, Any]:
    """Render `url` in the remote Carbonyl instance and return rendered HTML."""
    if not is_configured():
        return {"ok": False, "reason": "offline", "configured": False}
    try:
        async with httpx.AsyncClient(timeout=CARBONYL_TIMEOUT_S) as client:
            r = await client.post(
                f"{CARBONYL_URL}/render",
                json={"url": url, "wait_ms": wait_ms},
            )
        if r.status_code >= 400:
            return {"ok": False, "reason": f"http_{r.status_code}",
                    "body_preview": r.text[:200]}
        d = r.json()
        return {
            "ok": True,
            "html": d.get("html") or "",
            "title": d.get("title"),
            "final_url": d.get("final_url") or url,
            "screenshot_b64": d.get("screenshot_b64"),
            "configured": True,
        }
    except Exception as e:
        logger.warning(f"[Carbonyl] render failed for {url}: {e}")
        return {"ok": False, "reason": str(e)[:200]}


async def get_status() -> Dict[str, Any]:
    info: Dict[str, Any] = {"configured": is_configured()}
    if not is_configured():
        info["reachable"] = False
        return info
    try:
        async with httpx.AsyncClient(timeout=4) as client:
            r = await client.get(f"{CARBONYL_URL}/status")
        info["reachable"] = r.status_code < 400
    except Exception as e:
        info["reachable"] = False
        info["error"] = str(e)[:160]
    return info
