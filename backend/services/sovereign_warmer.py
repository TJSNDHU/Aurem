"""
Sovereign Warmer — keeps the Legion (Ollama via ngrok) tunnel warm.

Pings the configured Sovereign URL every SOVEREIGN_WARMER_INTERVAL_S seconds
(default 240s = 4 min). On failure, logs a WARNING only — never raises, never
alerts, never crashes. Zero user impact.

The goal is to drop first-hit cold-start latency from ~20s to ~800ms.
"""
from __future__ import annotations

import asyncio
import logging
import os

import httpx

logger = logging.getLogger(__name__)

INTERVAL_S = int(os.environ.get("SOVEREIGN_WARMER_INTERVAL_S", "240"))
ENABLED = os.environ.get("SOVEREIGN_WARMER_ENABLED", "true").lower() == "true"


async def sovereign_warmer_loop() -> None:
    """Background task: ping /api/tags every INTERVAL_S seconds."""
    if not ENABLED:
        logger.info("[SovereignWarmer] disabled via SOVEREIGN_WARMER_ENABLED")
        return

    # iter 322g+ prod-guard: skip in production (no daemon tunnel reachable).
    try:
        from services.prod_guard import is_production_pod
        if is_production_pod():
            logger.info("[SovereignWarmer] skipped — production pod (no daemon tunnel)")
            return
    except Exception:
        pass

    # Resolve URL lazily so .env reloads / runtime overrides are honoured.
    try:
        from services.local_llm_service import _config as _llm_config
    except Exception as e:  # pragma: no cover - import-time safety
        logger.warning(f"[SovereignWarmer] could not import local_llm_service: {e}")
        return

    logger.warning(f"[SovereignWarmer] started — interval={INTERVAL_S}s")

    # Small initial delay so startup isn't slowed down.
    await asyncio.sleep(15)

    while True:
        url = (_llm_config.get("ollama_url") or "").rstrip("/")
        enabled = bool(_llm_config.get("enabled"))
        if enabled and url:
            try:
                async with httpx.AsyncClient(timeout=8.0) as client:
                    r = await client.get(
                        f"{url}/api/tags",
                        headers={"ngrok-skip-browser-warning": "1"},
                    )
                if r.status_code == 200:
                    logger.debug(f"[SovereignWarmer] ping ok — {url}")
                else:
                    logger.warning(
                        f"[SovereignWarmer] ping non-200 ({r.status_code}) — {url}"
                    )
            except Exception as e:
                logger.warning(f"[SovereignWarmer] ping failed ({type(e).__name__}): {e}")
        else:
            logger.debug("[SovereignWarmer] skipped — sovereign disabled or no URL")

        await asyncio.sleep(INTERVAL_S)
