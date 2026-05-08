"""
iter 282al-21 — ORA Brain (God Mode) admin router.
"""
from __future__ import annotations

from fastapi import APIRouter
from typing import Any, Dict

router = APIRouter(prefix="/api/admin/ora-brain", tags=["ORA Brain"])

_db = None


def set_db(db):
    global _db
    _db = db


@router.get("/health")
async def ora_brain_health() -> Dict[str, Any]:
    from services.ora_god_mode import ora_brain_health as _h
    return await _h(_db)
