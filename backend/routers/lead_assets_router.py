"""
Lead Assets Router — iter 282j / Task 1
========================================
Per-lead asset hosting on Cloudflare R2 (img.aurem.live custom domain).

Endpoints:
    POST   /api/admin/leads/{lead_id}/logo     — multipart logo upload
    DELETE /api/admin/leads/{lead_id}/logo     — remove logo

Storage layout:
    R2 key = `lead-assets/{lead_id}/logo.{ext}`
    Public URL = `https://img.aurem.live/lead-assets/{lead_id}/logo.{ext}`

The AWB site renderer reads `lead.logo_url` and embeds it as the hero
image when present.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, File, Header, HTTPException, UploadFile

from routers.ora_dev_actions_router import verify_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/leads", tags=["Admin Lead Assets"])

_db = None

# Upload constraints
MAX_LOGO_BYTES = 2 * 1024 * 1024  # 2MB
ALLOWED_EXT = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/webp": "webp",
    "image/svg+xml": "svg",
}


def set_db(database) -> None:
    global _db
    _db = database


def _get_db():
    global _db
    if _db is not None:
        return _db
    try:
        import server as _srv
        if hasattr(_srv, "db") and _srv.db is not None:
            _db = _srv.db
    except Exception:
        pass
    return _db


@router.post("/{lead_id}/logo")
async def upload_lead_logo(
    lead_id: str,
    file: UploadFile = File(...),
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    payload = verify_admin(authorization)
    db = _get_db()
    if db is None:
        raise HTTPException(503, "Database not ready")

    lead = await db.campaign_leads.find_one(
        {"lead_id": lead_id}, {"_id": 0, "lead_id": 1, "logo_key": 1},
    )
    if not lead:
        raise HTTPException(404, "Lead not found")

    content_type = (file.content_type or "").lower()
    if content_type not in ALLOWED_EXT:
        raise HTTPException(
            400,
            f"Unsupported type {content_type!r}. Allowed: png/jpg/webp/svg",
        )

    body = await file.read()
    if not body:
        raise HTTPException(400, "Empty file")
    if len(body) > MAX_LOGO_BYTES:
        raise HTTPException(
            413,
            f"File too large ({len(body)} bytes). Max {MAX_LOGO_BYTES} bytes (2MB)",
        )

    ext = ALLOWED_EXT[content_type]
    key = f"lead-assets/{lead_id}/logo.{ext}"

    # Delete previous logo with a different ext (so we don't leave orphans)
    prev_key = lead.get("logo_key")
    if prev_key and prev_key != key:
        try:
            from services.cloudflare_r2 import delete_asset
            await delete_asset(prev_key)
        except Exception as e:
            logger.warning(f"[lead-logo] cleanup of {prev_key} failed: {e}")

    from services.cloudflare_r2 import upload_asset
    res = await upload_asset(key, body, content_type, cache_seconds=86400)
    if not res.get("ok"):
        raise HTTPException(502, f"R2 upload failed: {res.get('error', 'unknown')}")

    public_url = res.get("public_url") or (
        f"https://img.aurem.live/{key}"
    )

    await db.campaign_leads.update_one(
        {"lead_id": lead_id},
        {"$set": {
            "logo_url": public_url,
            "logo_key": key,
            "logo_size": res.get("size"),
            "logo_uploaded_at": datetime.now(timezone.utc).isoformat(),
            "logo_uploaded_by": payload.get("email"),
        }},
    )

    return {
        "ok": True,
        "lead_id": lead_id,
        "logo_url": public_url,
        "size": res.get("size"),
        "etag": res.get("etag"),
    }


@router.delete("/{lead_id}/logo")
async def delete_lead_logo(
    lead_id: str,
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    verify_admin(authorization)
    db = _get_db()
    if db is None:
        raise HTTPException(503, "Database not ready")

    lead = await db.campaign_leads.find_one(
        {"lead_id": lead_id}, {"_id": 0, "logo_key": 1},
    )
    if not lead:
        raise HTTPException(404, "Lead not found")

    key = lead.get("logo_key")
    if key:
        try:
            from services.cloudflare_r2 import delete_asset
            await delete_asset(key)
        except Exception as e:
            logger.warning(f"[lead-logo] R2 delete failed: {e}")

    await db.campaign_leads.update_one(
        {"lead_id": lead_id},
        {"$unset": {"logo_url": "", "logo_key": "", "logo_size": "",
                    "logo_uploaded_at": "", "logo_uploaded_by": ""}},
    )
    return {"ok": True, "lead_id": lead_id, "removed": bool(key)}
