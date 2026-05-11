"""
Customer-facing Scout Hunt endpoint — `POST /api/scout/run`.

Gated via `@require_service("total_scout")`. Fires a real business scout
hunt through the existing fallback chain (Google Places → Tavily → DDG),
returning surface + (optional) deep enrichment.

This is the canonical entry-point for the dashboard "Run Scout" button and
the dogfood E2E proof.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, HTTPException, Request

from utils.service_gate import require_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/scout", tags=["Scout Hunt"])


@router.post("/run")
@require_service("total_scout", quota_kind="scout_limit")
async def scout_run(request: Request, body: Dict[str, Any] = Body(default={})):
    """Fire a real scout hunt.

    Body:
      - query / name / business_name: target business name (required)
      - location / city: optional location hint
      - full: bool — run all sources in parallel for deeper enrichment
    """
    name: str = (
        body.get("query") or body.get("name") or body.get("business_name") or ""
    ).strip()
    if not name:
        raise HTTPException(400, "Field 'query' or 'name' is required")

    location: str = (body.get("location") or body.get("city") or "").strip()
    full: bool = bool(body.get("full", False))

    from services.business_scout import scout_business, scout_business_full

    try:
        if full:
            result = await scout_business_full(name, location)
        else:
            result = await scout_business(name, location)
    except Exception as e:
        logger.warning(f"[scout/run] failed: {type(e).__name__}: {e}")
        raise HTTPException(502, f"scout hunt failed: {e}")

    ctx = getattr(request.state, "bin_ctx", None)
    # iter 322ar — ORA universal learning hook (fire-and-forget)
    try:
        import asyncio as _asyncio
        from services.ora_universal_learner import ora_learn as _ora_learn
        _asyncio.create_task(_ora_learn({
            "source": "scout",
            "event": "SCOUT_RUN",
            "category": "lead_intelligence",
            "summary": (
                f"Scout ran for '{name}' in {location or 'any'}. "
                f"Depth: {'full' if full else 'surface'}. "
                f"Sources: {(result or {}).get('sources_tried', '?')}."
            ),
            "outcome": "found" if (result or {}).get("found") else "not_found",
            "agent": "scout_ora",
            "bin_id": getattr(ctx, "business_id", None) or "system",
        }))
    except Exception:
        pass
    return {
        "ok": True,
        "query": name,
        "location": location or None,
        "depth": "full" if full else "surface",
        "business_id": getattr(ctx, "business_id", None),
        "result": result,
    }
