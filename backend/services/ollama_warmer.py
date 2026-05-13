"""
ollama_warmer.py — Keep local Ollama model HOT (iter 322g local-only).
══════════════════════════════════════════════════════════════════════
Cold-start of llama3.1:8B = ~100s (loading 4.7GB into RAM). Cloudflare
ingress timeout = ~60s. So user's first chat after model evicts always
disconnects.

This service does a tiny no-op /v1/chat call every 3 minutes via the
Legion daemon. Ollama keeps recently-used models in RAM by default,
so as long as we ping more often than its keepalive window (5 min),
the model never evicts.

Cost: ~30 tokens per warmup, on local CPU/GPU — zero $.
"""
from __future__ import annotations

import asyncio
import json as _json
import logging
import os
import shlex
import time

logger = logging.getLogger("ollama_warmer")

_db = None
WARM_INTERVAL_S = 180  # 3 minutes


def set_db(database) -> None:
    global _db
    _db = database


async def _is_daemon_alive() -> bool:
    if _db is None:
        return False
    try:
        s = await _db.legion_daemon_status.find_one(
            {"_id": "global"}, {"_id": 0, "last_poll_ts": 1}
        )
        last = float((s or {}).get("last_poll_ts") or 0)
        return (time.time() - last) < 120 if last else False
    except Exception:
        return False


async def _warm_once() -> None:
    try:
        from services.legion_tool import legion_exec
    except Exception:
        return
    model = os.environ.get("LEGION_OLLAMA_MODEL", "llama3.1:latest")
    url = os.environ.get("LEGION_OLLAMA_URL", "http://host.docker.internal:11434")
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "hi"}],
        "stream": False,
        "max_tokens": 1,
        "temperature": 0.0,
    }
    body = _json.dumps(payload)
    cmd = (
        f"curl -sS --max-time 90 "
        f"-H 'Content-Type: application/json' "
        f"-d {shlex.quote(body)} "
        f"{url.rstrip('/')}/v1/chat/completions"
    )
    started = time.time()
    result = await legion_exec(
        cmd=cmd, cwd="/tmp", timeout_s=100, risk_hint="low", wait_max_s=110
    )
    elapsed = time.time() - started
    if result.get("ok"):
        logger.info(f"[warmer] OK in {elapsed:.1f}s (cold={elapsed>20}) model={model}")
    else:
        logger.warning(
            f"[warmer] FAIL in {elapsed:.1f}s exit={result.get('exit_code')} "
            f"err={result.get('error')!r}"
        )


async def warmer_loop() -> None:
    """Pillar-1 worker entrypoint. Pings Ollama every 3min if daemon alive."""
    print("[warmer] Ollama warmer alive — 30s grace, then 3min cycles", flush=True)
    await asyncio.sleep(30)
    while True:
        try:
            if await _is_daemon_alive():
                await _warm_once()
            else:
                logger.debug("[warmer] skipped: daemon offline")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"[warmer] loop error: {e}", exc_info=True)
        await asyncio.sleep(WARM_INTERVAL_S)
