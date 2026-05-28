"""
routers/resend_webhook_router.py — iter D-57

Two endpoints the AUREM CTO chat depends on:

  POST /api/webhooks/resend
       Public alias for the existing /api/leads/webhook/resend handler.
       Founder asked for the cleaner path — we delegate to the original
       implementation so there's a single source of truth for signature
       verification + lifecycle transitions.

  GET  /api/leads/hot
       Admin-only. Returns campaign_leads with `hot_lead_flag=True`
       within the last `hours` window, ranked by recency. The CTO chat
       polls this every minute and renders:

         🔥 <business_name> opened your email N min ago

The Resend webhook itself was already implemented in
`lead_lifecycle_router.py` (touchpoint + lifecycle transitions). D-57
adds the `hot_lead_flag` mutation in that handler so this endpoint has
data to surface. We do NOT duplicate the signature-verify logic here.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query, Request

logger = logging.getLogger(__name__)
router = APIRouter(tags=["resend-webhook"])

_db = None


def set_db(database) -> None:
    global _db
    _db = database


async def _require_admin(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "missing_bearer_token")
    token = authorization.split(" ", 1)[1]
    try:
        import jwt as _jwt
        from config import JWT_SECRET, JWT_ALGORITHM
        payload = _jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if (payload.get("is_admin") or payload.get("is_super_admin") or
                payload.get("role") in ("admin", "super_admin", "founder")):
            return payload.get("email") or payload.get("sub") or "admin"
    except Exception:
        pass
    raise HTTPException(403, "admin_required")


# ── /api/webhooks/resend — clean alias ───────────────────────────────

@router.post("/api/webhooks/resend")
async def resend_webhook_alias(request: Request) -> dict[str, Any]:
    """Delegates to lead_lifecycle_router.resend_webhook so we keep ONE
    signature-verification + lifecycle path."""
    from routers.lead_lifecycle_router import resend_webhook
    return await resend_webhook(request)


# ── /api/cto/leads/hot — CTO chat surfaces these ─────────────────────
# Path was originally /api/leads/hot but that collides with the
# pre-existing /api/leads/{lead_id} parameterized route. Use a
# distinct prefix so the hot-leads list never gets routed to the
# single-lead handler.

@router.get("/api/cto/leads/hot")
async def hot_leads(
    hours: int = Query(24, ge=1, le=168),
    limit: int = Query(20, ge=1, le=100),
    authorization: str = Header(None),
) -> dict[str, Any]:
    actor = await _require_admin(authorization)
    if _db is None:
        return {"ok": True, "items": [], "ts": datetime.now(timezone.utc).isoformat()}

    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    q = {
        "hot_lead_flag":        True,
        "hot_lead_signal_at":   {"$gte": cutoff},
    }
    items: list[dict[str, Any]] = []
    async for d in _db.campaign_leads.find(
        q,
        {"_id": 0, "lead_id": 1, "business_name": 1,
         "email": 1, "phone": 1, "city": 1,
         "hot_lead_reason": 1, "hot_lead_signal_at": 1,
         "last_clicked_url": 1, "flame_score_boost": 1},
    ).sort("hot_lead_signal_at", -1).limit(limit):
        # Friendly "N min ago" string for the CTO chat pill
        try:
            ts = datetime.fromisoformat(
                d["hot_lead_signal_at"].replace("Z", "+00:00")
            )
            delta = datetime.now(timezone.utc) - ts
            mins  = max(0, int(delta.total_seconds() // 60))
            if mins < 60:
                ago = f"{mins} min ago"
            elif mins < 1440:
                ago = f"{mins // 60} hr ago"
            else:
                ago = f"{mins // 1440}d ago"
            d["ago"] = ago
        except Exception:
            d["ago"] = ""
        items.append(d)

    return {
        "ok":     True,
        "actor":  actor,
        "hours":  hours,
        "items":  items,
        "count":  len(items),
        "ts":     datetime.now(timezone.utc).isoformat(),
    }
