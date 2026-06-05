"""
web_search_router.py — iter D-64
=================================
Direct REST endpoints over the Tavily skills so the founder, the
admin UI, and (later) the public commercialization API can invoke
web search / URL fetch without going through the full ORA chat path.

Endpoints:
    POST /api/admin/web/search      → cto_skills.web_search
    POST /api/admin/web/fetch       → cto_skills.fetch_url
    POST /api/admin/web/answer      → cto_skills.web_search_and_summarize
    GET  /api/admin/web/health      → quick connectivity probe

All require admin auth (verify_admin). Each call hits real Tavily API —
no mocks. Loud 503 when TAVILY_API_KEY missing.
"""
from __future__ import annotations

import logging
import os
from typing import Any, List, Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from utils.admin_guard import verify_admin

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/web", tags=["Web Search"])


def _require_key():
    k = os.environ.get("TAVILY_API_KEY", "").strip()
    if not k:
        raise HTTPException(
            status_code=503,
            detail=(
                "TAVILY_API_KEY not set. Add it to backend/.env to enable "
                "web search."
            ),
        )
    return k


class _SearchBody(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    max_results: int = Field(5, ge=1, le=20)
    search_depth: str = Field("basic", pattern="^(basic|advanced)$")
    include_domains: Optional[List[str]] = None
    exclude_domains: Optional[List[str]] = None


class _FetchBody(BaseModel):
    url: str = Field(..., min_length=8, max_length=2000)
    extract_depth: str = Field("basic", pattern="^(basic|advanced)$")


class _AnswerBody(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    max_results: int = Field(5, ge=1, le=10)


@router.get("/health")
async def health():
    return {
        "ok": True,
        "tavily_key_set": bool(os.environ.get("TAVILY_API_KEY", "").strip()),
    }


@router.post("/search")
async def web_search(body: _SearchBody,
                     authorization: Optional[str] = Header(None)):
    verify_admin(authorization)
    _require_key()
    try:
        from cto_skills import invoke
        out = await invoke(
            "web_search",
            query=body.query,
            max_results=body.max_results,
            search_depth=body.search_depth,
            include_domains=body.include_domains,
            exclude_domains=body.exclude_domains,
        )
    except Exception as e:
        raise HTTPException(500, f"skill_failure: {type(e).__name__}: {e}")
    if not out.get("ok"):
        raise HTTPException(502, out.get("error") or "skill_error")
    return out["result"]


@router.post("/fetch")
async def fetch_url(body: _FetchBody,
                    authorization: Optional[str] = Header(None)):
    verify_admin(authorization)
    _require_key()
    # Belt-and-braces: reuse the same internal-URL blocklist used by ORA chat
    # so admins can't accidentally curl their own admin routes through this.
    try:
        from services.dev_cto_chat import _is_internal_url
        if _is_internal_url(body.url):
            raise HTTPException(
                400,
                "internal URL refused — this endpoint is for external pages only",
            )
    except ImportError:
        pass
    try:
        from cto_skills import invoke
        out = await invoke(
            "fetch_url",
            url=body.url,
            extract_depth=body.extract_depth,
        )
    except Exception as e:
        raise HTTPException(500, f"skill_failure: {type(e).__name__}: {e}")
    if not out.get("ok"):
        raise HTTPException(502, out.get("error") or "skill_error")
    return out["result"]


@router.post("/answer")
async def search_and_summarize(body: _AnswerBody,
                                authorization: Optional[str] = Header(None)):
    verify_admin(authorization)
    _require_key()
    try:
        from cto_skills import invoke
        out = await invoke(
            "web_search_and_summarize",
            query=body.query,
            max_results=body.max_results,
        )
    except Exception as e:
        raise HTTPException(500, f"skill_failure: {type(e).__name__}: {e}")
    if not out.get("ok"):
        raise HTTPException(502, out.get("error") or "skill_error")
    return out["result"]
