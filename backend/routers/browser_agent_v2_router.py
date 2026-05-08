"""
Browser Agent Actions Router — iter 282e
=========================================
Thin admin/ORA-facing router for the new `browser_agent_service`.

Endpoints
    GET  /api/browser-agent-v2/recent           → latest 50 actions (admin)
    POST /api/browser-agent-v2/screenshot       → { url, full_page?, slug_hint? }
        - Internal host (aurem.live, preview)  → fires immediately, returns image_url
        - External host                        → queues approval, returns proposal_id

All routes require the admin bearer token via the existing `verify_admin`
helper (reused so we don't split auth logic).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from routers.ora_dev_actions_router import verify_admin
from services.browser_agent_service import (
    list_recent_actions,
    screenshot_url,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/browser-agent-v2", tags=["Browser Agent v2"])


class ScreenshotRequest(BaseModel):
    url: str
    full_page: bool = True
    wait_ms: int = 1500
    slug_hint: Optional[str] = None
    reason: Optional[str] = None


@router.get("/recent")
async def recent_actions(
    limit: int = 50,
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    verify_admin(authorization)
    rows = await list_recent_actions(limit=limit)
    return {"ok": True, "actions": rows}


@router.post("/screenshot")
async def request_screenshot(
    body: ScreenshotRequest,
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    payload = verify_admin(authorization)
    if not body.url:
        raise HTTPException(400, "url is required")
    res = await screenshot_url(
        body.url,
        full_page=body.full_page,
        wait_ms=body.wait_ms,
        slug_hint=body.slug_hint,
        reason=body.reason or f"Admin-requested screenshot ({body.url})",
        triggered_by=f"admin:{payload.get('email', 'unknown')}",
    )
    return res
