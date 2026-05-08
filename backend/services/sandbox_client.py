"""
SmolMachines Sandbox Client — Iteration 214
============================================
Graceful-degradation HTTP client for a smolvm (SmolMachines.com) sandbox
running on the user's Legion PC.

Purpose: sandbox Claude-generated code before we ever write it to disk.
If the sandbox rejects it (crash / timeout / forbidden syscalls), we drop
the change and flag the build as failed.

When SANDBOX_URL is empty, runs() returns `{ok: True, skipped: "offline"}`
so AUREM keeps working (just without the extra safety net).

ENV
---
SANDBOX_URL           — e.g. http://192.168.1.20:7776
SANDBOX_TIMEOUT_S     — per-call timeout (default 15)
SANDBOX_MAX_BYTES     — max code size to ship (default 64 KB)
SANDBOX_MODE          — "enforce" | "advisory" (default advisory — logs but
                         does NOT block). Flip to enforce once tuned.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict

import httpx

logger = logging.getLogger(__name__)

SANDBOX_URL = (os.environ.get("SANDBOX_URL") or "").rstrip("/")
SANDBOX_TIMEOUT_S = float(os.environ.get("SANDBOX_TIMEOUT_S", "15"))
SANDBOX_MAX_BYTES = int(os.environ.get("SANDBOX_MAX_BYTES", str(64 * 1024)))
SANDBOX_MODE = (os.environ.get("SANDBOX_MODE", "advisory") or "advisory").lower()


def is_configured() -> bool:
    return bool(SANDBOX_URL)


async def run_code(code: str, language: str = "python") -> Dict[str, Any]:
    """
    POST code to the smolvm sandbox for execution. Returns a normalized dict:
        {ok: bool, stdout, stderr, exit_code, duration_ms, skipped?, reason?}

    `ok=True` when the sandbox ran the snippet and exit_code==0.
    `ok=False` when it crashed, timed out, or was rejected.
    `skipped="offline"` when SANDBOX_URL is unset — treat as pass in advisory
    mode, fail in enforce mode at the CALLER's discretion.
    """
    if not is_configured():
        return {"ok": True, "skipped": "offline", "reason": "SANDBOX_URL not set"}

    if len(code.encode("utf-8", errors="ignore")) > SANDBOX_MAX_BYTES:
        return {"ok": False, "skipped": "too_large",
                "reason": f"code > {SANDBOX_MAX_BYTES} bytes"}

    try:
        async with httpx.AsyncClient(timeout=SANDBOX_TIMEOUT_S) as client:
            resp = await client.post(
                f"{SANDBOX_URL}/run",
                json={"language": language, "code": code, "mode": SANDBOX_MODE},
            )
        if resp.status_code >= 400:
            return {"ok": False, "reason": f"http_{resp.status_code}",
                    "body_preview": resp.text[:400]}
        data = resp.json() if resp.content else {}
        exit_code = int(data.get("exit_code", 0))
        return {
            "ok": exit_code == 0 and not data.get("crashed", False),
            "stdout": (data.get("stdout") or "")[:2000],
            "stderr": (data.get("stderr") or "")[:2000],
            "exit_code": exit_code,
            "duration_ms": data.get("duration_ms"),
            "mode": SANDBOX_MODE,
        }
    except Exception as e:
        logger.warning(f"[Sandbox] run failed: {e}")
        return {"ok": False, "reason": str(e)[:200]}


async def get_status() -> Dict[str, Any]:
    """Quick health check for Admin Control Center."""
    info: Dict[str, Any] = {
        "configured": is_configured(),
        "mode": SANDBOX_MODE,
        "max_bytes": SANDBOX_MAX_BYTES,
    }
    if not is_configured():
        info["reachable"] = False
        return info
    try:
        async with httpx.AsyncClient(timeout=4) as client:
            r = await client.get(f"{SANDBOX_URL}/status")
        info["reachable"] = r.status_code < 400
        if r.status_code < 400:
            try:
                info["remote"] = r.json()
            except Exception:
                info["remote"] = {"raw": r.text[:200]}
    except Exception as e:
        info["reachable"] = False
        info["error"] = str(e)[:200]
    return info
