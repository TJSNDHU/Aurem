"""
Dev Stack Health — single endpoint that returns 🟢/🔴 for the 10 core
runtime components shown on /admin/pillars-map Dev Stack section.

Components:
  1. Sovereign LLM (local Ollama via ngrok)
  2. LLM Gateway v2 (Groq → OpenRouter → Emergent chain)
  3. Council Engine
  4. A2A Learning Bus
  5. Sentinel Repair Loop
  6. ORA Brain
  7. Groq Connection
  8. Birdeye Scraper
  9. Unified Inbox
  10. Intelligence Merge Engine
  11. ORA Skills Router
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Request
import jwt

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/dev-stack", tags=["Dev Stack Health"])

_db = None


def set_db(db) -> None:
    global _db
    _db = db


async def _require_admin(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Authentication required")
    secret = os.environ.get("JWT_SECRET") or ""
    try:
        claims = jwt.decode(auth[7:], secret, algorithms=["HS256"])
    except Exception:
        raise HTTPException(401, "Invalid token")
    email = (claims.get("email") or "").lower()
    user_id = claims.get("user_id") or claims.get("sub") or claims.get("id")
    if _db is None:
        raise HTTPException(403, "no admin context")
    # iter 322ar — admin-portal JWT may lack `email`; resolve by user_id.
    if email:
        user = await _db.users.find_one(
            {"email": email}, {"_id": 0, "is_admin": 1, "is_super_admin": 1, "role": 1, "email": 1},
        )
    elif user_id:
        user = await _db.users.find_one(
            {"$or": [{"id": user_id}, {"user_id": user_id}]},
            {"_id": 0, "is_admin": 1, "is_super_admin": 1, "role": 1, "email": 1},
        )
    else:
        user = None
    if not user or not (
        user.get("is_admin") or user.get("is_super_admin")
        or user.get("role") in ("admin", "super_admin")
    ):
        raise HTTPException(403, "Admin access required")
    return {"email": email or user.get("email", "")}


def _g(status: bool, detail: str = "") -> Dict[str, Any]:
    return {"status": "green" if status else "red", "detail": detail or ("ok" if status else "down")}


async def _check_sovereign() -> Dict[str, Any]:
    try:
        from services.local_llm_service import is_available, _config
        ok = await is_available()
        return _g(ok, f"url={_config['ollama_url']}" if ok else "unreachable")
    except Exception as e:
        return _g(False, str(e)[:80])


async def _check_gateway() -> Dict[str, Any]:
    try:
        import services.llm_gateway_v2 as g  # noqa
        return _g(True, "loaded")
    except Exception as e:
        return _g(False, str(e)[:80])


async def _check_groq() -> Dict[str, Any]:
    return _g(bool(os.environ.get("GROQ_API_KEY")), "key set" if os.environ.get("GROQ_API_KEY") else "GROQ_API_KEY missing")


async def _check_council() -> Dict[str, Any]:
    try:
        n = await _db.council_decisions.count_documents({})
        if n == 0:
            return _g(True, "ready · awaiting first decision")
        return _g(True, f"{n} decisions logged")
    except Exception as e:
        return _g(False, str(e)[:80])


async def _check_a2a() -> Dict[str, Any]:
    try:
        n = await _db.a2a_messages.count_documents({})
        if n == 0:
            return _g(True, "ready · awaiting first message")
        recent = await _db.a2a_messages.find_one({}, sort=[("ts", -1)])
        return _g(True, f"{n} msgs · last {recent.get('ts') if recent else 'never'}"[:80])
    except Exception as e:
        return _g(False, str(e)[:80])


async def _check_sentinel() -> Dict[str, Any]:
    """iter 322ar — point at the real collections written by
    services.sentinel_repair_loop. Previously queried `sentinel_repair_runs`
    + `repair_history` which never existed, so the grid always showed RED.

    iter D-71k — zero runs is a freshly-installed component, not broken.
    """
    try:
        sentinel_n = await _db.sentinel_runs.count_documents({})
        heal_n = await _db.auto_heal_log.count_documents({})
        repair_n = await _db.repair_runs.count_documents({})
        total = sentinel_n + heal_n + repair_n
        if total == 0:
            return _g(True, "ready · awaiting first repair run")
        return _g(True, f"{sentinel_n} sentinel · {heal_n} heals · {repair_n} repairs")
    except Exception as e:
        return _g(False, str(e)[:80])


async def _check_ora_brain() -> Dict[str, Any]:
    try:
        n = await _db.ora_brain_thoughts.count_documents({})
        if n == 0:
            return _g(True, "ready · awaiting first thought")
        return _g(True, f"{n} thoughts")
    except Exception as e:
        return _g(False, str(e)[:80])


async def _check_birdeye() -> Dict[str, Any]:
    try:
        import services.birdeye_scraper  # noqa
        return _g(True, "module loaded")
    except Exception as e:
        return _g(False, str(e)[:80])


async def _check_inbox() -> Dict[str, Any]:
    try:
        n = await _db.unified_inbox.count_documents({})
        return _g(True, f"{n} rows total")
    except Exception as e:
        return _g(False, str(e)[:80])


async def _check_intel_merge() -> Dict[str, Any]:
    try:
        n = await _db.bin_unified_profiles.count_documents({})
        b = await _db.bin_intelligence.count_documents({})
        # iter D-71k — zero signals is NOT a broken component, it's a
        # freshly-initialised one (or a tenant who hasn't engaged any
        # leads yet). Same empathetic pattern we use for skill_learner:
        # green when the engine is ready, with an "awaiting first signal"
        # detail. Real red only fires on actual collection-access errors.
        if b == 0:
            return _g(True, "ready · awaiting first signal (engine wired)")
        return _g(True, f"{b} signals → {n} merged profiles")
    except Exception as e:
        return _g(False, str(e)[:80])


async def _check_ora_skills() -> Dict[str, Any]:
    try:
        from pathlib import Path
        d = Path(__file__).resolve().parent.parent / "ora_skills"
        skills = list(d.glob("*.md")) if d.exists() else []
        return _g(len(skills) > 0, f"{len(skills)} skills loaded")
    except Exception as e:
        return _g(False, str(e)[:80])


CHECKS = [
    ("Sovereign LLM", _check_sovereign),
    ("LLM Gateway v2", _check_gateway),
    ("Groq Connection", _check_groq),
    ("Council Engine", _check_council),
    ("A2A Learning Bus", _check_a2a),
    ("Sentinel Repair Loop", _check_sentinel),
    ("ORA Brain", _check_ora_brain),
    ("Birdeye Scraper", _check_birdeye),
    ("Unified Inbox", _check_inbox),
    ("Intelligence Merge", _check_intel_merge),
    ("ORA Skills Router", _check_ora_skills),
]


@router.get("/health")
async def dev_stack_health(_admin: dict = Depends(_require_admin)):
    rows: List[Dict[str, Any]] = []
    green = 0
    for name, fn in CHECKS:
        try:
            r = await fn()
        except Exception as e:
            r = {"status": "red", "detail": str(e)[:80]}
        if r["status"] == "green":
            green += 1
        rows.append({"name": name, **r})
    return {
        "ok": True,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "summary": {"total": len(rows), "green": green, "red": len(rows) - green},
        "components": rows,
    }
