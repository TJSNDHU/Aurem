"""
iter 282al-20 — Council admin router (Pillars chip).
"""
from __future__ import annotations

from fastapi import APIRouter
from typing import Any, Dict

router = APIRouter(prefix="/api/admin/council", tags=["ORA Council"])

_db = None


def set_db(db):
    global _db
    _db = db


@router.get("/health")
async def council_health() -> Dict[str, Any]:
    from services.ora_council import get_council_health
    return await get_council_health(_db)
