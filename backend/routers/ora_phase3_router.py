"""
routers/ora_phase3_router.py — iter 326ff/gg/hh (Phase 3 P3.1–P3.3).

REST surface for the three Phase 3 P3 features:

  P3.1 — Multi-tenant ORA voice tuning
    GET  /api/admin/ora/voice-profile/{tenant_id}
    PUT  /api/admin/ora/voice-profile/{tenant_id}

  P3.2 — Mobile morning brief
    GET  /api/admin/ora/morning-brief
    GET  /api/admin/ora/morning-brief?tenant_id=...

  P3.3 — Skills marketplace
    GET  /api/admin/ora/skills?category=...
    GET  /api/admin/ora/skills/{skill_id}
    POST /api/admin/ora/skills                       — publish
    POST /api/admin/ora/skills/{skill_id}/install    — per-tenant install
    GET  /api/admin/ora/skills/installed/{tenant_id}
    DELETE /api/admin/ora/skills/{skill_id}/install/{tenant_id}
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from middleware.bin_context import get_bin_ctx
from services import ora_voice_profile, ora_morning_brief, ora_skills

logger = logging.getLogger(__name__)
router = APIRouter()
_db = None


def set_db(database) -> None:
    """Wire the same DB handle into all three Phase 3 services."""
    global _db
    _db = database
    ora_voice_profile.set_db(database)
    ora_morning_brief.set_db(database)
    ora_skills.set_db(database)


def _ensure_admin(request: Request):
    ctx = get_bin_ctx(request, required=True)
    if not ctx.is_admin:
        raise HTTPException(403, "admin only")
    return ctx


# ─────────────────────────────────────────────────────────────────────
# P3.1 — Voice profile
# ─────────────────────────────────────────────────────────────────────
class VoiceProfileBody(BaseModel):
    tone:      Optional[str] = Field(default=None, max_length=32)
    formality: Optional[str] = Field(default=None, max_length=32)
    signature: Optional[str] = Field(default=None, max_length=200)
    industry:  Optional[str] = Field(default=None, max_length=60)


@router.get("/api/admin/ora/voice-profile/{tenant_id}")
async def get_voice_profile(tenant_id: str, request: Request):
    _ensure_admin(request)
    return await ora_voice_profile.get_profile(tenant_id)


@router.put("/api/admin/ora/voice-profile/{tenant_id}")
async def put_voice_profile(
    tenant_id: str, body: VoiceProfileBody, request: Request,
):
    _ensure_admin(request)
    res = await ora_voice_profile.save_profile(
        tenant_id,
        tone=body.tone,
        formality=body.formality,
        signature=body.signature,
        industry=body.industry,
    )
    if not res.get("ok"):
        raise HTTPException(400, res.get("error", "save failed"))
    return res


# ─────────────────────────────────────────────────────────────────────
# P3.2 — Morning brief
# ─────────────────────────────────────────────────────────────────────
@router.get("/api/admin/ora/morning-brief")
async def get_morning_brief(
    request: Request, tenant_id: Optional[str] = None,
):
    ctx = _ensure_admin(request)
    founder_email = getattr(ctx, "email", None) or None
    return await ora_morning_brief.build_brief(
        tenant_id=tenant_id, founder_email=founder_email,
    )


# ─────────────────────────────────────────────────────────────────────
# P3.3 — Skills marketplace
# ─────────────────────────────────────────────────────────────────────
class SkillPublishBody(BaseModel):
    name:        str   = Field(min_length=2, max_length=120)
    description: str   = Field(min_length=4, max_length=1000)
    category:    str   = Field(min_length=2, max_length=60)
    version:     str   = Field(default="1.0.0", max_length=16)
    skill_id:    Optional[str]  = Field(default=None, max_length=80)
    manifest:    Optional[Dict[str, Any]] = None
    content:     Optional[Dict[str, Any]] = None
    pricing:     Optional[Dict[str, Any]] = None


class SkillInstallBody(BaseModel):
    tenant_id: str = Field(min_length=1, max_length=120)
    version:   Optional[str] = Field(default=None, max_length=16)


@router.get("/api/admin/ora/skills")
async def list_marketplace(
    request: Request,
    category: Optional[str] = None,
    limit:    int           = 50,
):
    _ensure_admin(request)
    rows = await ora_skills.list_skills(category=category, limit=limit)
    return {"ok": True, "count": len(rows), "skills": rows}


@router.get("/api/admin/ora/skills/installed/{tenant_id}")
async def list_installed(tenant_id: str, request: Request):
    _ensure_admin(request)
    rows = await ora_skills.list_installed_for_tenant(tenant_id)
    return {"ok": True, "tenant_id": tenant_id,
            "count": len(rows), "installed": rows}


@router.get("/api/admin/ora/skills/{skill_id}")
async def get_one_skill(skill_id: str, request: Request):
    _ensure_admin(request)
    skill = await ora_skills.get_skill(skill_id)
    if not skill:
        raise HTTPException(404, "skill not found")
    return skill


@router.post("/api/admin/ora/skills")
async def publish_marketplace_skill(
    body: SkillPublishBody, request: Request,
):
    ctx = _ensure_admin(request)
    author_email = getattr(ctx, "email", None) or "admin@aurem.live"
    res = await ora_skills.publish_skill(
        name=body.name,
        description=body.description,
        category=body.category,
        author_email=author_email,
        version=body.version,
        manifest=body.manifest,
        content=body.content,
        skill_id=body.skill_id,
        pricing=body.pricing,
    )
    if not res.get("ok"):
        raise HTTPException(400, res.get("error", "publish failed"))
    return res


@router.post("/api/admin/ora/skills/{skill_id}/install")
async def install_marketplace_skill(
    skill_id: str, body: SkillInstallBody, request: Request,
):
    _ensure_admin(request)
    res = await ora_skills.install_skill(
        body.tenant_id, skill_id, version=body.version,
    )
    if not res.get("ok"):
        raise HTTPException(400, res.get("error", "install failed"))
    return res


@router.delete("/api/admin/ora/skills/{skill_id}/install/{tenant_id}")
async def uninstall_marketplace_skill(
    skill_id: str, tenant_id: str, request: Request,
):
    _ensure_admin(request)
    return await ora_skills.uninstall_skill(tenant_id, skill_id)
