"""
AUREM — ORA Avatar Preference Router (Phase 2 + 8)
iter 322v · 2026-02-06

Endpoints:
  POST /api/ora/avatar-preference        — customer selects an avatar
  GET  /api/ora/avatar-preference/:uid   — read current selection

  GET   /api/admin/avatars               — admin list w/ stats
  POST  /api/admin/avatars               — admin add new avatar (draft)
  PATCH /api/admin/avatars/:id           — admin toggle status / edit

Source-of-truth for the *catalog* of avatars lives in
`frontend/src/config/ora_avatars.config.js` (lean, no DB hop).
This router persists ONLY:
  - per-user selection (collection: ora_avatar_preferences)
  - admin overrides (collection: ora_avatar_overrides)
  - per-avatar selection counters (aggregated on read)
"""

from datetime import datetime, timezone
from typing import Optional, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/ora", tags=["ORA Avatars"])
_admin_router = APIRouter(prefix="/admin", tags=["Admin · Avatars"])

# Module-level db handle, wired by registry.py at startup.
_db = None


def set_db(database) -> None:
    global _db
    _db = database


# ───────────────────────────────────────────────────────────────────
# Customer-facing endpoints
# ───────────────────────────────────────────────────────────────────
class AvatarPreferenceIn(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=128)
    avatar_id: str = Field(..., pattern=r"^ora_(female|male)_[1-6]$")


class AvatarPreferenceOut(BaseModel):
    user_id: str
    avatar_id: Optional[str] = None
    selected_at: Optional[str] = None


@router.post("/avatar-preference", response_model=AvatarPreferenceOut)
async def save_preference(payload: AvatarPreferenceIn):
    if _db is None:
        raise HTTPException(status_code=503, detail="DB not ready")
    now = datetime.now(timezone.utc)
    await _db.ora_avatar_preferences.update_one(
        {"user_id": payload.user_id},
        {
            "$set": {
                "user_id": payload.user_id,
                "avatar_id": payload.avatar_id,
                "selected_at": now,
            },
            "$inc": {"selection_count": 1},
        },
        upsert=True,
    )
    # Increment per-avatar counter (used by admin stats)
    await _db.ora_avatar_stats.update_one(
        {"avatar_id": payload.avatar_id},
        {
            "$inc": {"times_selected": 1},
            "$set": {"last_selected": now},
        },
        upsert=True,
    )
    return AvatarPreferenceOut(
        user_id=payload.user_id,
        avatar_id=payload.avatar_id,
        selected_at=now.isoformat(),
    )


@router.get("/avatar-preference/{user_id}", response_model=AvatarPreferenceOut)
async def get_preference(user_id: str):
    if _db is None:
        raise HTTPException(status_code=503, detail="DB not ready")
    doc = await _db.ora_avatar_preferences.find_one(
        {"user_id": user_id}, {"_id": 0, "user_id": 1, "avatar_id": 1, "selected_at": 1}
    )
    if not doc:
        return AvatarPreferenceOut(user_id=user_id)
    sel = doc.get("selected_at")
    return AvatarPreferenceOut(
        user_id=doc["user_id"],
        avatar_id=doc.get("avatar_id"),
        selected_at=sel.isoformat() if isinstance(sel, datetime) else sel,
    )


# ───────────────────────────────────────────────────────────────────
# Admin-facing endpoints (Phase 8)
# ───────────────────────────────────────────────────────────────────
class AvatarOverrideIn(BaseModel):
    avatar_id: str = Field(..., pattern=r"^ora_[a-z0-9_]+$")
    name: Optional[str] = None
    gender: Optional[Literal["female", "male"]] = None
    ethnicity: Optional[str] = None
    glb_url: Optional[str] = None
    thumbnail: Optional[str] = None
    voice_id: Optional[str] = None
    elevenlabs_voice_id: Optional[str] = None
    status: Optional[Literal["active", "draft"]] = None


class AvatarPatchIn(BaseModel):
    status: Optional[Literal["active", "draft"]] = None
    name: Optional[str] = None
    glb_url: Optional[str] = None
    thumbnail: Optional[str] = None
    voice_id: Optional[str] = None
    elevenlabs_voice_id: Optional[str] = None


@_admin_router.get("/avatars")
async def admin_list_avatars():
    """Return overrides + selection stats. Frontend merges with config."""
    if _db is None:
        raise HTTPException(status_code=503, detail="DB not ready")
    overrides = await _db.ora_avatar_overrides.find({}, {"_id": 0}).to_list(length=64)
    stats = await _db.ora_avatar_stats.find({}, {"_id": 0}).to_list(length=64)
    stats_by_id = {s["avatar_id"]: s for s in stats}
    return {
        "overrides": overrides,
        "stats": stats_by_id,
        "ts": datetime.now(timezone.utc).isoformat(),
    }


@_admin_router.post("/avatars")
async def admin_create_avatar(payload: AvatarOverrideIn):
    """Add a new avatar (default status=draft until founder activates)."""
    if _db is None:
        raise HTTPException(status_code=503, detail="DB not ready")
    body = payload.model_dump(exclude_none=True)
    body.setdefault("status", "draft")
    body["created_at"] = datetime.now(timezone.utc)
    await _db.ora_avatar_overrides.update_one(
        {"avatar_id": body["avatar_id"]},
        {"$setOnInsert": body},
        upsert=True,
    )
    return {"ok": True, "avatar_id": body["avatar_id"], "status": body["status"]}


@_admin_router.patch("/avatars/{avatar_id}")
async def admin_patch_avatar(avatar_id: str, payload: AvatarPatchIn):
    """Toggle status or edit fields on an existing avatar override."""
    if _db is None:
        raise HTTPException(status_code=503, detail="DB not ready")
    body = payload.model_dump(exclude_none=True)
    if not body:
        raise HTTPException(status_code=400, detail="No fields to update")
    body["updated_at"] = datetime.now(timezone.utc)
    res = await _db.ora_avatar_overrides.update_one(
        {"avatar_id": avatar_id},
        {"$set": body},
        upsert=True,
    )
    return {
        "ok": True,
        "avatar_id": avatar_id,
        "modified": res.modified_count,
        "upserted": bool(res.upserted_id),
    }


# Combined export so registry.py can include both with a single line each
__all__ = ["router", "_admin_router", "set_db"]
