"""
sovereignty_score_router.py — iter 323j

Live "Full Sovereignty" scoreboard for the founder.
═══════════════════════════════════════════════════════════════════════
Single read-only endpoint surfaces a real-time measurement of how much
of the AUREM stack is running on self-hosted / sovereign infrastructure
vs. cloud SaaS. The mission is migrating off Emergent + Atlas + Redis
Cloud onto Hetzner + local Mongo + Legion LLM — this endpoint is the
North-Star metric for that mission.

Components probed:
  1. MongoDB host        — localhost/127.* = sovereign, mongodb+srv = cloud
  2. Redis               — empty REDIS_URL + in-memory = sovereign (no
                           Redis Cloud dependency); rediss:// → cloud
  3. Legion LLM (Ollama) — HTTP probe `LEGION_OLLAMA_URL`/`OLLAMA_URL`
                           with a 2 s ceiling; reachable = sovereign
  4. Ingress / hosting   — AUREM_ENV=sovereign = sovereign (Hetzner);
                           preview/production on Emergent = cloud
  5. LLM cloud fallbacks — Groq/Claude/Emergent keys still set = warn
                           (these are lifelines, not full deficits)
  6. External SaaS deps  — Stripe/Twilio/Resend (necessary cloud)

Score weighting (sum = 100):
    MongoDB       25
    Ingress       25
    Legion LLM    20
    Redis         15
    LLM fallback   8  (penalty when ALL three cloud LLM keys present)
    SaaS deps      7  (informational only — never blocks 100%)

p95 latency target: < 2.5 s (dominated by the Legion HTTP probe).
═══════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import os
import logging
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, HTTPException, Request

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/sovereignty", tags=["admin-sovereignty"])

_db = None
_LEGION_PROBE_TIMEOUT_S = 2.0


def set_db(database) -> None:
    global _db
    _db = database


# ─────────────────────────────────────────────────────────────────────
# Auth — admin-only (mirrors customer_vanguard_router pattern)
# ─────────────────────────────────────────────────────────────────────
async def _require_admin(request: Request) -> Dict[str, Any]:
    user: Optional[Dict[str, Any]] = None
    try:
        from utils.auth_utils import get_current_user as _auth_get
        user = await _auth_get(request)
    except Exception:
        user = None

    if not user:
        try:
            import jwt as _jwt
            secret = os.environ.get("JWT_SECRET") or ""
            hdr = request.headers.get("Authorization") or ""
            if secret and hdr.lower().startswith("bearer "):
                payload = _jwt.decode(
                    hdr.split(" ", 1)[1].strip(),
                    secret,
                    algorithms=["HS256"],
                )
                user = {
                    "user_id": payload.get("user_id") or payload.get("sub"),
                    "email": payload.get("email"),
                    "is_admin": bool(payload.get("is_admin")),
                    "role": payload.get("role"),
                }
        except Exception:
            user = None

    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    if not (user.get("is_admin") or user.get("role") == "admin"):
        raise HTTPException(status_code=403, detail="Admin only")
    return user


# ─────────────────────────────────────────────────────────────────────
# Component probes
# ─────────────────────────────────────────────────────────────────────
def _probe_mongo() -> Dict[str, Any]:
    raw = (os.environ.get("MONGO_URL") or "").strip()
    if not raw:
        return {"status": "missing", "score": 0, "detail": "MONGO_URL not set"}
    try:
        parsed = urlparse(raw)
    except Exception:
        parsed = None

    host = (parsed.hostname if parsed else "") or ""
    scheme = (parsed.scheme if parsed else "") or ""

    if scheme.startswith("mongodb+srv") or "mongodb.net" in host:
        return {
            "status": "cloud",
            "score": 0,
            "detail": f"Atlas SRV cluster ({host or 'mongodb+srv://…'})",
        }
    if host in ("localhost", "127.0.0.1") or host.endswith(".local"):
        return {
            "status": "sovereign",
            "score": 100,
            "detail": f"Local Mongo at {host}",
        }
    # Self-hosted on a VPS — treat as sovereign too (Hetzner internal)
    return {
        "status": "sovereign",
        "score": 100,
        "detail": f"Self-hosted at {host or 'unknown host'}",
    }


def _probe_redis() -> Dict[str, Any]:
    url = (os.environ.get("REDIS_URL") or "").strip()
    if not url:
        return {
            "status": "sovereign",
            "score": 100,
            "detail": "Disconnected — in-memory rate limiter (iter 323e)",
        }
    try:
        parsed = urlparse(url)
        host = parsed.hostname or ""
    except Exception:
        host = ""
    if "redis-cloud.com" in host or "redislabs.com" in host or "upstash.io" in host:
        return {
            "status": "cloud",
            "score": 0,
            "detail": f"Redis Cloud at {host}",
        }
    if host in ("localhost", "127.0.0.1") or host.endswith(".local"):
        return {"status": "sovereign", "score": 100, "detail": f"Local Redis at {host}"}
    return {"status": "hybrid", "score": 50, "detail": f"External Redis at {host or 'unknown'}"}


async def _probe_legion() -> Dict[str, Any]:
    url = (
        (os.environ.get("LEGION_OLLAMA_URL") or "").strip()
        or (os.environ.get("OLLAMA_URL") or "").strip()
        or (os.environ.get("OLLAMA_HOST") or "").strip()
    )
    if not url:
        return {"status": "missing", "score": 0, "detail": "No Legion URL configured"}

    probe_url = url.rstrip("/") + "/api/tags"
    try:
        async with httpx.AsyncClient(timeout=_LEGION_PROBE_TIMEOUT_S) as c:
            r = await c.get(probe_url)
            if r.status_code == 200:
                model_count = 0
                try:
                    model_count = len((r.json() or {}).get("models") or [])
                except Exception:
                    pass
                short = url
                if len(short) > 48:
                    short = short[:45] + "…"
                return {
                    "status": "sovereign",
                    "score": 100,
                    "detail": f"Legion reachable ({model_count} models) — {short}",
                }
            return {
                "status": "degraded",
                "score": 25,
                "detail": f"Legion HTTP {r.status_code}",
            }
    except Exception as e:
        return {
            "status": "down",
            "score": 0,
            "detail": f"Unreachable: {type(e).__name__}",
        }


def _probe_ingress() -> Dict[str, Any]:
    env = (os.environ.get("AUREM_ENV") or "").strip().lower()
    if env == "sovereign":
        return {"status": "sovereign", "score": 100, "detail": "AUREM_ENV=sovereign (Hetzner)"}
    if env == "production":
        return {"status": "cloud", "score": 0, "detail": "AUREM_ENV=production (Emergent)"}
    if env == "preview":
        return {"status": "cloud", "score": 0, "detail": "AUREM_ENV=preview (Emergent)"}
    return {"status": "unknown", "score": 25, "detail": f"AUREM_ENV={env or 'unset'}"}


def _probe_llm_fallbacks() -> Dict[str, Any]:
    """All three cloud LLM keys set = full lifeline (penalty).
    None set = fully sovereign on Legion. Partial = warn."""
    keys = {
        "groq":    bool((os.environ.get("GROQ_API_KEY") or "").strip()),
        "claude":  bool(
            (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
            or (os.environ.get("CLAUDE_API_KEY") or "").strip()
        ),
        "emergent": bool((os.environ.get("EMERGENT_LLM_KEY") or "").strip()),
    }
    active = sum(1 for v in keys.values() if v)
    # 0 active = 100 (pure sovereign), 3 active = 0 (full lifeline)
    score = round(100 - (active * 33.3))
    score = max(0, min(100, score))
    if active == 0:
        status = "sovereign"
        detail = "No cloud LLM lifelines — Legion only"
    elif active == 3:
        status = "hybrid"
        detail = "All 3 cloud LLM keys active (Groq+Claude+Emergent)"
    else:
        active_names = ", ".join(k for k, v in keys.items() if v) or "none"
        status = "hybrid"
        detail = f"{active}/3 cloud LLM lifelines: {active_names}"
    return {"status": status, "score": score, "detail": detail, "keys": keys}


def _probe_saas_deps() -> Dict[str, Any]:
    """Informational. Stripe/Twilio/Resend are usually unavoidable cloud."""
    deps = {
        "stripe": bool((os.environ.get("STRIPE_SECRET_KEY") or "").strip()),
        "twilio": bool(
            (os.environ.get("TWILIO_ACCOUNT_SID") or "").strip()
            and (os.environ.get("TWILIO_AUTH_TOKEN") or "").strip()
        ),
        "resend": bool((os.environ.get("RESEND_API_KEY") or "").strip()),
    }
    count = sum(1 for v in deps.values() if v)
    detail = f"{count}/3 cloud SaaS active (necessary deps)"
    return {"status": "info", "score": 100, "detail": detail, "deps": deps}


# ─────────────────────────────────────────────────────────────────────
# Endpoint
# ─────────────────────────────────────────────────────────────────────
_WEIGHTS = {
    "mongo":         25,
    "ingress":       25,
    "legion":        20,
    "redis":         15,
    "llm_fallbacks":  8,
    "saas_deps":      7,
}


@router.get("/score")
async def sovereignty_score(request: Request) -> Dict[str, Any]:
    await _require_admin(request)

    mongo = _probe_mongo()
    redis_c = _probe_redis()
    legion = await _probe_legion()
    ingress = _probe_ingress()
    fallbacks = _probe_llm_fallbacks()
    saas = _probe_saas_deps()

    components = {
        "mongo": mongo,
        "ingress": ingress,
        "legion": legion,
        "redis": redis_c,
        "llm_fallbacks": fallbacks,
        "saas_deps": saas,
    }

    weighted_sum = 0.0
    for key, weight in _WEIGHTS.items():
        comp_score = float(components[key].get("score", 0))
        weighted_sum += (comp_score / 100.0) * weight

    overall = round(weighted_sum)

    if overall >= 80:
        tier = "sovereign"
    elif overall >= 50:
        tier = "hybrid"
    else:
        tier = "cloud"

    return {
        "score": overall,
        "tier": tier,
        "weights": _WEIGHTS,
        "components": components,
        "mission": "Full Sovereignty — Hetzner + local Mongo + Legion LLM",
    }


__all__ = ["router", "set_db"]
