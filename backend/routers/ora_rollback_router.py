"""
ORA Rollback Router — iter 322es
=================================
Surface for /tmp/ora_backups/ — every safe_edit() writes a `.bak`
snapshot of the original file. This router lists them and offers a
one-click restore.

Endpoints (/api/admin/ora-rollback):
  GET   /list?limit=50              recent backups (newest first)
  POST  /restore                    body: {backup_name} → copy back + audit
  GET   /_/health
"""
from __future__ import annotations

import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/ora-rollback", tags=["ora-rollback"])

BACKUP_DIR = Path("/tmp/ora_backups")


def _verify_token(authorization: Optional[str] = None) -> str:
    if not authorization:
        raise HTTPException(401, "Authorization required")
    import jwt
    token = authorization.replace("Bearer ", "").strip()
    if not token:
        raise HTTPException(401, "Authorization required")
    try:
        secret = os.environ.get("JWT_SECRET") or os.environ.get("JWT_SECRET_KEY") or ""
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        return payload.get("email") or payload.get("user_id") or payload.get("sub") or "unknown"
    except Exception:
        raise HTTPException(401, "Invalid token")


def _get_db():
    from server import db
    if db is None:
        raise HTTPException(500, "Database not initialized")
    return db


def _backup_to_origpath(name: str) -> Path:
    """Reverse the encoding done by safe_edit:
    `<ts>__<encoded_path>.bak` where path's `/` were replaced with `__`.
    Returns the absolute original file path.
    """
    stem = name[:-4] if name.endswith(".bak") else name
    # Strip the leading <ts>__ token
    parts = stem.split("__", 1)
    encoded = parts[1] if len(parts) > 1 else stem
    # Backslash unescape: `__` ↔ `/`
    rel = encoded.replace("__", "/")
    if not rel.startswith("/"):
        rel = "/" + rel
    return Path(rel)


@router.get("/list")
async def list_backups(
    limit: int = 50,
    authorization: Optional[str] = Header(None),
):
    _verify_token(authorization)
    if not BACKUP_DIR.exists():
        return {"ok": True, "rows": [], "note": "no backup directory"}
    files = sorted(BACKUP_DIR.glob("*.bak"), key=lambda p: p.stat().st_mtime, reverse=True)
    rows = []
    for p in files[:limit]:
        st = p.stat()
        orig = _backup_to_origpath(p.name)
        rows.append({
            "backup_name":   p.name,
            "backup_path":   str(p),
            "original_path": str(orig),
            "size_bytes":    st.st_size,
            "mtime":         datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(),
            "still_exists":  orig.is_file(),
        })
    return {"ok": True, "rows": rows, "count": len(rows)}


class RestoreRequest(BaseModel):
    backup_name: str
    restart_service: Optional[str] = None  # e.g. "backend"


@router.post("/restore")
async def restore(req: RestoreRequest, authorization: Optional[str] = Header(None)):
    actor = _verify_token(authorization)
    db = _get_db()
    if "/" in req.backup_name or req.backup_name.startswith("."):
        raise HTTPException(400, "invalid backup_name")
    src = BACKUP_DIR / req.backup_name
    if not src.is_file():
        raise HTTPException(404, "backup not found")
    orig = _backup_to_origpath(req.backup_name)
    if not orig.is_absolute():
        raise HTTPException(400, "could not derive original path")
    # Safety — only restore inside the same write-allowed roots
    from services.ora_tools import _is_write_path_allowed
    ok_p, why = _is_write_path_allowed(str(orig))
    if not ok_p:
        raise HTTPException(400, f"refusing to restore outside allowed roots: {why}")
    try:
        # Atomic: write to tmp then os.replace
        tmp = orig.with_suffix(orig.suffix + ".restore.tmp")
        shutil.copy2(src, tmp)
        os.replace(tmp, orig)
    except Exception as e:
        raise HTTPException(500, f"restore failed: {type(e).__name__}: {e}")

    # Audit log
    try:
        await db.ora_rollback_log.insert_one({
            "ts":            datetime.now(timezone.utc).isoformat(),
            "actor":         actor,
            "backup_name":   req.backup_name,
            "original_path": str(orig),
            "restart_service": req.restart_service,
        })
    except Exception:
        pass

    # Optional supervisor restart
    restart_result = None
    if req.restart_service:
        try:
            from services.ora_tools import restart_service, set_db
            set_db(db)
            restart_result = await restart_service(req.restart_service)
        except Exception as e:
            restart_result = {"ok": False, "error": str(e)}

    return {
        "ok":             True,
        "restored_to":    str(orig),
        "backup_used":    str(src),
        "actor":          actor,
        "restart_result": restart_result,
    }


@router.get("/_/health")
async def health():
    n = len(list(BACKUP_DIR.glob("*.bak"))) if BACKUP_DIR.exists() else 0
    return {"ok": True, "scope": "ora_rollback",
             "backup_dir": str(BACKUP_DIR), "backups_count": n}
