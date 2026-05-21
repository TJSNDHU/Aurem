"""
iter 326a — ORA Provider Health watchdog router.

Exposes a single endpoint the ORA-CTO panel + pillars-map drill-down
can hit to see live provider chain state:

  GET /api/admin/ora/providers/health

Returns the configured `ORA_AGENT_PROVIDER_ORDER` plus per-provider
status (ok / configured / latency / reason). Read-only; aux of all
existing provider helpers in `services/ora_agent`.

The endpoint is auth-gated (admin) but the underlying helpers are pure
(no DB writes), so wiring an internal /api watchdog probe is safe.
"""
import asyncio
import os
import time
from typing import Any, Optional

from fastapi import APIRouter, Header, HTTPException

from utils.admin_guard import verify_admin as _unified_verify_admin

router = APIRouter(prefix="/api/admin/ora/providers", tags=["ora-providers"])

# Tiny in-memory cache so the panel can poll every 5 s without hammering
# every upstream — cache TTL is 15 s.
_CACHE: dict[str, Any] = {"ts": 0.0, "payload": None}
_CACHE_TTL = 15.0


async def _check_deepseek() -> dict[str, Any]:
    """OpenRouter DeepSeek V3.1 — primary provider."""
    api_key = (os.environ.get("OPENROUTER_API_KEY") or "").strip()
    if not api_key:
        return {"ok": False, "configured": False,
                "reason": "OPENROUTER_API_KEY missing"}
    import httpx
    started = asyncio.get_event_loop().time()
    try:
        async with httpx.AsyncClient(timeout=8.0) as c:
            r = await c.get(
                "https://openrouter.ai/api/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
        elapsed_ms = int((asyncio.get_event_loop().time() - started) * 1000)
        if r.status_code != 200:
            return {"ok": False, "configured": True, "status": r.status_code,
                    "latency_ms": elapsed_ms,
                    "reason": f"HTTP {r.status_code}"}
        models = (r.json().get("data") or [])
        return {"ok": True, "configured": True, "status": 200,
                "models_total": len(models), "latency_ms": elapsed_ms,
                "reason": f"{len(models)} models routable"}
    except Exception as e:
        return {"ok": False, "configured": True,
                "reason": f"{type(e).__name__}: {str(e)[:120]}"}


async def _check_claude() -> dict[str, Any]:
    """Claude via Emergent Universal LLM key — fallback provider."""
    if not (os.environ.get("EMERGENT_LLM_KEY") or "").strip():
        return {"ok": False, "configured": False,
                "reason": "EMERGENT_LLM_KEY missing"}
    # Universal key has no cheap reachability probe — mark as configured.
    return {"ok": True, "configured": True,
            "reason": "EMERGENT_LLM_KEY present (Universal Key)"}


async def _check_groq() -> dict[str, Any]:
    api_key = (os.environ.get("GROQ_API_KEY") or "").strip()
    if not api_key:
        return {"ok": False, "configured": False,
                "reason": "GROQ_API_KEY missing"}
    import httpx
    started = asyncio.get_event_loop().time()
    try:
        async with httpx.AsyncClient(timeout=8.0) as c:
            r = await c.get(
                "https://api.groq.com/openai/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
        elapsed_ms = int((asyncio.get_event_loop().time() - started) * 1000)
        if r.status_code != 200:
            return {"ok": False, "configured": True, "status": r.status_code,
                    "latency_ms": elapsed_ms,
                    "reason": f"HTTP {r.status_code}"}
        models = (r.json().get("data") or [])
        return {"ok": True, "configured": True, "status": 200,
                "models_total": len(models), "latency_ms": elapsed_ms,
                "reason": f"{len(models)} models routable"}
    except Exception as e:
        return {"ok": False, "configured": True,
                "reason": f"{type(e).__name__}: {str(e)[:120]}"}


async def _check_freellmapi() -> dict[str, Any]:
    # Re-use the helper baked into ora_agent so logic stays in one place.
    from services.ora_agent import freellmapi_health
    return await freellmapi_health()


# iter 326f — Gemini + NVIDIA watchdog checks (helpers live in ora_agent)
async def _check_gemini() -> dict[str, Any]:
    from services.ora_agent import gemini_health
    return await gemini_health()


async def _check_nvidia() -> dict[str, Any]:
    from services.ora_agent import nvidia_health
    return await nvidia_health()


async def _check_ollama() -> dict[str, Any]:
    """Legion Ollama (laptop/sovereign). Optional; commonly offline."""
    url = (os.environ.get("OLLAMA_BASE_URL") or "").strip()
    if not url:
        return {"ok": False, "configured": False,
                "reason": "OLLAMA_BASE_URL not set (sovereign optional)"}
    import httpx
    started = asyncio.get_event_loop().time()
    try:
        async with httpx.AsyncClient(timeout=4.0) as c:
            r = await c.get(f"{url.rstrip('/')}/api/tags")
        elapsed_ms = int((asyncio.get_event_loop().time() - started) * 1000)
        if r.status_code != 200:
            return {"ok": False, "configured": True, "status": r.status_code,
                    "latency_ms": elapsed_ms,
                    "reason": f"HTTP {r.status_code}"}
        tags = (r.json().get("models") or [])
        return {"ok": True, "configured": True, "status": 200,
                "models_total": len(tags), "latency_ms": elapsed_ms,
                "reason": f"{len(tags)} local models"}
    except Exception as e:
        return {"ok": False, "configured": True,
                "reason": f"{type(e).__name__}: {str(e)[:120]}"}


_CHECKERS = {
    "deepseek":      _check_deepseek,
    "freellmapi":    _check_freellmapi,
    "gemini":        _check_gemini,
    "nvidia":        _check_nvidia,
    "claude":        _check_claude,
    "groq":          _check_groq,
    "legion_ollama": _check_ollama,
    "ollama":        _check_ollama,
    "legion":        _check_ollama,
}


@router.get("/health")
async def providers_health(authorization: Optional[str] = Header(None)):
    """Live status of every provider in the ORA chain.

    Response shape:
      {
        "order": ["deepseek", "freellmapi", "claude", ...],
        "providers": {
          "deepseek":   {"ok": true,  "latency_ms": 280, ...},
          "freellmapi": {"ok": false, "configured": false, "reason": "..."},
          ...
        },
        "primary_ok": true,
        "any_chat_provider_ok": true,
        "cached": false
      }
    """
    _unified_verify_admin(authorization=authorization)
    # Cache hit?
    if _CACHE["payload"] and (time.time() - _CACHE["ts"]) < _CACHE_TTL:
        cached = dict(_CACHE["payload"])
        cached["cached"] = True
        return cached

    order_env = os.environ.get(
        "ORA_AGENT_PROVIDER_ORDER",
        "deepseek,gemini,nvidia,claude,freellmapi,legion_ollama,groq",
    )
    order = [p.strip() for p in order_env.lower().split(",") if p.strip()]
    # De-dupe while preserving order
    seen, deduped = set(), []
    for p in order:
        if p not in seen:
            seen.add(p)
            deduped.append(p)

    results = await asyncio.gather(
        *(_CHECKERS.get(p, _check_freellmapi)() for p in deduped),
        return_exceptions=False,
    )
    providers = dict(zip(deduped, results))
    primary = deduped[0] if deduped else None
    primary_ok = bool(providers.get(primary, {}).get("ok")) if primary else False
    any_ok = any(r.get("ok") for r in results)

    payload = {
        "order":        deduped,
        "providers":    providers,
        "primary":      primary,
        "primary_ok":   primary_ok,
        "any_chat_provider_ok": any_ok,
        "cached":       False,
        "checked_at":   time.time(),
    }
    _CACHE["payload"] = payload
    _CACHE["ts"]      = time.time()
    return payload


@router.get("/health/public")
async def providers_health_public():
    """Same payload as /health but without admin auth — wired to the
    pillars-map drill-down so the founder can see chain status at a
    glance. Read-only / safe."""
    if _CACHE["payload"]:
        cached = dict(_CACHE["payload"])
        cached["cached"] = (time.time() - _CACHE["ts"]) < _CACHE_TTL
        # Strip latency/keys details — keep just status booleans for public.
        cached["providers"] = {
            k: {"ok": v.get("ok"), "configured": v.get("configured"),
                "reason": v.get("reason")}
            for k, v in cached.get("providers", {}).items()
        }
        return cached
    raise HTTPException(503, "no health snapshot yet — try /health (admin)")
