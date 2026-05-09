"""
deploy_readiness_router.py — iter 322v.

Single-shot snapshot of whether the deployment is production-ready by
introspecting required env-var configuration (no live API calls — those
have their own health probes). Used by the Mission Control widget.

GET /api/admin/deploy-readiness
  →  {
       stripe: "live" | "test" | "missing",
       twilio: "configured" | "missing",
       vapid:  "configured" | "missing",
       resend: "configured" | "missing",
       llm:    "configured" | "missing",
       overall: "ready" | "not_ready",
       missing: [list of missing items],
       checked_at: iso ts
     }
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import jwt
from fastapi import APIRouter, HTTPException, Request

router = APIRouter()


def _require_admin(request: Request) -> Dict[str, Any]:
    auth = request.headers.get("Authorization", "")
    token = auth[7:] if auth.startswith("Bearer ") else ""
    if not token:
        raise HTTPException(401, "Auth required")
    secret = os.environ.get("JWT_SECRET") or os.environ.get("JWT_SECRET_KEY")
    if not secret:
        raise HTTPException(500, "JWT_SECRET not configured")
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
    except Exception:
        raise HTTPException(401, "Invalid token")
    if not (payload.get("is_admin") or payload.get("is_super_admin") or
            payload.get("role") in ("admin", "super_admin", "founder")):
        raise HTTPException(403, "Admin required")
    return payload


def _stripe_status() -> str:
    """live | test | missing — derived from STRIPE_SECRET_KEY prefix."""
    sk = os.environ.get("STRIPE_SECRET_KEY") or os.environ.get("STRIPE_API_KEY") or ""
    if not sk:
        return "missing"
    if sk.startswith("sk_live_"):
        return "live"
    if sk.startswith("sk_test_") or sk.startswith("sk_"):
        return "test"
    return "missing"


def _twilio_status() -> str:
    sid = os.environ.get("TWILIO_ACCOUNT_SID") or ""
    tok = os.environ.get("TWILIO_AUTH_TOKEN") or ""
    phone = os.environ.get("TWILIO_PHONE_NUMBER") or ""
    if sid and tok and phone:
        return "configured"
    return "missing"


def _vapid_status() -> str:
    pub = os.environ.get("VAPID_PUBLIC_KEY") or ""
    priv = os.environ.get("VAPID_PRIVATE_KEY") or ""
    subj = os.environ.get("VAPID_SUBJECT") or ""
    if pub and priv and subj:
        return "configured"
    return "missing"


def _resend_status() -> str:
    if (os.environ.get("RESEND_API_KEY") or "").startswith("re_"):
        return "configured"
    return "missing"


def _llm_status() -> str:
    """Emergent LLM key OR direct provider keys present."""
    if os.environ.get("EMERGENT_LLM_KEY"):
        return "configured"
    if (os.environ.get("OPENAI_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
            or os.environ.get("GEMINI_API_KEY")
            or os.environ.get("OPENROUTER_API_KEY")):
        return "configured"
    return "missing"


@router.get("/api/admin/deploy-readiness")
async def deploy_readiness(request: Request) -> Dict[str, Any]:
    _require_admin(request)
    stripe = _stripe_status()
    twilio = _twilio_status()
    vapid = _vapid_status()
    resend = _resend_status()
    llm = _llm_status()

    missing: List[str] = []
    if stripe == "missing":
        missing.append("stripe")
    if twilio == "missing":
        missing.append("twilio")
    if vapid == "missing":
        missing.append("vapid")
    if resend == "missing":
        missing.append("resend")
    if llm == "missing":
        missing.append("llm")

    overall = "ready" if not missing else "not_ready"
    return {
        "ok": True,
        "stripe": stripe,
        "twilio": twilio,
        "vapid": vapid,
        "resend": resend,
        "llm": llm,
        "overall": overall,
        "missing": missing,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
