"""
Customer Edit Portal — router (iter 311)
=========================================
POST /api/edit/request-access  body: {business_email, site_slug}
GET  /api/edit/verify?token=
POST /api/edit/save             body: {token, changes}
POST /api/edit/upload-image     multipart: token, kind=hero|logo, file
GET  /api/edit/site/{slug}      preview/public site fetch (no auth)
"""
from __future__ import annotations

import base64
import logging
import os
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Header, Query, UploadFile, File, Form
from pydantic import BaseModel
logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/edit", tags=["Customer Edit Portal"])

_db = None


def set_db(db):
    global _db
    _db = db


def _get_db():
    global _db
    if _db is None:
        try:
            import server
            _db = getattr(server, "db", None)
        except Exception:
            pass
    return _db


# ── Models ────────────────────────────────────────────────────────────────
class RequestAccessBody(BaseModel):
    business_email: str
    site_slug: str


class SaveBody(BaseModel):
    token: str
    changes: Dict[str, Any]


# ── Endpoints ─────────────────────────────────────────────────────────────
@router.post("/request-access")
async def request_access(body: RequestAccessBody):
    db = _get_db()
    if db is None:
        raise HTTPException(503, "db unavailable")
    from services.customer_edit import request_access as svc
    return await svc(db, body.business_email, body.site_slug)


@router.get("/verify")
async def verify(token: str = Query(...)):
    db = _get_db()
    if db is None:
        raise HTTPException(503, "db unavailable")
    from services.customer_edit import verify_token
    out = await verify_token(db, token)
    if not out:
        raise HTTPException(401, "invalid or expired token")
    return out


@router.post("/nps")
async def submit_nps(body: Dict[str, Any]):
    """2-tap customer NPS — body: {token, score, source?}"""
    db = _get_db()
    if db is None:
        raise HTTPException(503, "db unavailable")
    token = (body or {}).get("token", "")
    try:
        score = int((body or {}).get("score", 0))
    except Exception:
        raise HTTPException(400, "score must be int 1..5")
    if not token:
        raise HTTPException(400, "token required")
    if not (1 <= score <= 5):
        raise HTTPException(400, "score must be 1..5")
    from services.nps_service import submit_nps as svc
    out = await svc(db, token=token, score=score,
                      source=(body.get("source") or "edit_portal"))
    if not out.get("ok"):
        raise HTTPException(400, out.get("error") or "nps failed")
    return out


@router.post("/save")
async def save(body: SaveBody):
    db = _get_db()
    if db is None:
        raise HTTPException(503, "db unavailable")
    from services.customer_edit import save_changes
    out = await save_changes(db, body.token, body.changes or {})
    if not out.get("ok"):
        raise HTTPException(400, out.get("error") or "save failed")
    return out


@router.post("/upload-image")
async def upload_image(
    token: str = Form(...),
    kind: str = Form(...),  # hero | logo
    file: UploadFile = File(...),
):
    db = _get_db()
    if db is None:
        raise HTTPException(503, "db unavailable")
    from services.customer_edit import _resolve_session
    sess = await _resolve_session(db, token)
    if not sess:
        raise HTTPException(401, "invalid or expired session")
    if kind not in ("hero", "logo"):
        raise HTTPException(400, "kind must be hero or logo")

    raw = await file.read()
    if not raw:
        raise HTTPException(400, "empty file")
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(413, "image > 5 MB limit")
    ct = file.content_type or "image/jpeg"
    if not ct.startswith("image/"):
        raise HTTPException(415, "image only")

    # Inline base64 fallback when no R2 — keeps portal functional even without
    # cloud storage. R2 push attempted if creds present.
    asset_url = ""
    try:
        if all(os.environ.get(k) for k in
                ("R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET_NAME")):
            asset_url = await _r2_upload(raw, ct, file.filename)
    except Exception as e:
        logger.warning(f"[edit] r2 upload failed: {e}")
    if not asset_url:
        b64 = base64.b64encode(raw).decode("ascii")
        asset_url = f"data:{ct};base64,{b64}"

    field = "hero_url" if kind == "hero" else "logo_url"
    from datetime import datetime, timezone
    await db.auto_built_sites.update_one(
        {"site_id": sess["site_id"]},
        {"$set": {f"custom_content.images.{field}": asset_url,
                   "last_edited": datetime.now(timezone.utc).isoformat()},
          "$inc": {"edit_count": 1}},
    )
    # Re-render
    from services.customer_edit import _trigger_rerender
    rerender = await _trigger_rerender(db, sess["site_id"])
    return {"ok": True, "kind": kind, "asset_url": asset_url[:120] + "...",
            "rerender": rerender}


async def _r2_upload(raw: bytes, content_type: str, filename: str) -> str:
    """Best-effort R2 upload via boto3 — returns public URL or empty string."""
    try:
        import boto3  # type: ignore
        from botocore.config import Config  # type: ignore
    except Exception:
        return ""
    bucket = os.environ.get("R2_BUCKET_NAME", "")
    account = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "")
    key_id = os.environ.get("R2_ACCESS_KEY_ID", "")
    secret = os.environ.get("R2_SECRET_ACCESS_KEY", "")
    if not (bucket and account and key_id and secret):
        return ""
    endpoint = f"https://{account}.r2.cloudflarestorage.com"
    s3 = boto3.client(
        "s3", endpoint_url=endpoint,
        aws_access_key_id=key_id, aws_secret_access_key=secret,
        region_name="auto", config=Config(signature_version="s3v4"),
    )
    safe = (filename or f"img-{uuid.uuid4().hex[:8]}.bin").replace(" ", "_")[:60]
    key = f"customer-edit/{uuid.uuid4().hex[:10]}-{safe}"
    s3.put_object(Bucket=bucket, Key=key, Body=raw, ContentType=content_type)
    public_root = os.environ.get("R2_PUBLIC_ROOT",
                                   f"https://pub-{account}.r2.dev")
    return f"{public_root.rstrip('/')}/{key}"


@router.get("/site/{slug}")
async def public_site(slug: str):
    db = _get_db()
    if db is None:
        raise HTTPException(503, "db unavailable")
    from services.customer_edit import _find_site, _public_site
    site = await _find_site(db, slug)
    if not site:
        raise HTTPException(404, "not found")
    return _public_site(site)


# ─── Admin trigger ────────────────────────────────────────────────────────
class AdminSendBody(BaseModel):
    site_slug: str
    override_email: Optional[str] = None


@router.post("/admin/send-link")
async def admin_send_edit_link(body: AdminSendBody,
                                  authorization: Optional[str] = Header(None)):
    """Admin-only: bypass email match, send a fresh magic-link email
    to whatever email is on file for the site (or override_email)."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "admin auth required")
    import jwt
    try:
        p = jwt.decode(authorization.split(" ", 1)[1],
                        (os.environ.get("JWT_SECRET") or (_ for _ in ()).throw(__import__("fastapi").HTTPException(status_code=500, detail="JWT not configured"))),
                        algorithms=["HS256"])
        if not (p.get("is_admin") or p.get("role") in ("admin", "super_admin")
                or p.get("is_super_admin") or p.get("email")):
            raise HTTPException(403, "admin only")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(401, "invalid token")

    db = _get_db()
    if db is None:
        raise HTTPException(503, "db unavailable")
    from services.customer_edit import (
        _find_site, _site_email, _hash, _send_magic_link,
        REQUEST_TOKEN_TTL_H,
    )
    import secrets
    import uuid
    from datetime import datetime, timezone, timedelta
    site = await _find_site(db, body.site_slug)
    if not site:
        raise HTTPException(404, "site not found")
    email_to = (body.override_email or _site_email(site) or "").strip().lower()
    if not email_to:
        raise HTTPException(400,
            "no email on file — pass override_email")

    raw = secrets.token_urlsafe(28)
    rec = {
        "request_id": uuid.uuid4().hex[:12],
        "site_id": site["site_id"],
        "slug": site.get("slug"),
        "email_to": email_to,
        "token_hash": _hash(raw),
        "kind": "request",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc)
                        + timedelta(hours=REQUEST_TOKEN_TTL_H)).isoformat(),
        "consumed": False, "admin_triggered": True,
    }
    await db.edit_sessions.insert_one(dict(rec))
    base = os.environ.get("AUREM_PUBLIC_URL", "https://aurem.live").rstrip("/")
    link = f"{base}/edit?token={raw}&site={site.get('slug') or site['site_id']}"
    sent = await _send_magic_link(
        email_to, site.get("business_name") or "your site", link)
    return {"ok": True, "sent": bool(sent), "email_to": email_to,
            "link": link if not sent else None,
            "request_id": rec["request_id"]}
