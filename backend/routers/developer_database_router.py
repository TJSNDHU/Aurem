"""
routers/developer_database_router.py — iter D-44

Read-only info endpoints powering /developers/database.
Admin-only. Never returns the MONGO_URL plaintext — only a masked
version + the configured DB name.
"""
from __future__ import annotations

import os
import re

from fastapi import APIRouter, Depends, HTTPException

from utils.require_auth import require_admin

router = APIRouter(
    prefix="/api/developers/database",
    tags=["developer-database"],
    dependencies=[Depends(require_admin)],
)


def _mask_mongo_url(url: str) -> str:
    """Returns `mongodb+srv://****:****@cluster0.xxxxx.mongodb.net/db`
    (credentials and host body redacted)."""
    if not url:
        return ""
    try:
        # mongodb://user:pass@host/path  → strip user:pass, partial host
        m = re.match(r"^(mongodb(?:\+srv)?://)([^@]*@)?([^/]+)(/.*)?$", url)
        if not m:
            return "***masked***"
        scheme = m.group(1)
        host   = m.group(3)
        path   = m.group(4) or ""
        # Mask middle of host so the user can still recognize it
        if len(host) > 12:
            host = host[:4] + "…" + host[-6:]
        return f"{scheme}****:****@{host}{path}"
    except Exception:
        return "***masked***"


@router.get("/info")
async def db_info() -> dict:
    mongo_url = os.environ.get("MONGO_URL", "").strip()
    db_name   = os.environ.get("DB_NAME", "").strip()
    if not mongo_url:
        raise HTTPException(503, "MONGO_URL not configured")
    return {
        "app_name":  "AUREM Platform",
        "db_name":   db_name or "(default from connection string)",
        "mongo_url_masked": _mask_mongo_url(mongo_url),
        "atlas_link": "https://cloud.mongodb.com/",
        "provider":   "MongoDB Atlas" if "mongodb.net" in mongo_url
                       else "MongoDB",
    }
